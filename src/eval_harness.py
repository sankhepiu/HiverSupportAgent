"""
Phase 6: evaluation harness - consolidates Phase 4's classifier metrics and
runs an LLM-as-judge over Phase 5's 35 sample outputs.

Usage:
  python3 src/eval_harness.py               classifier summary + run LLM judge
  python3 src/eval_harness.py --agreement    compute human-vs-judge agreement
                                              (run after src/human_judge_sample.py)
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from derive_taxonomy import call_groq, extract_json, load_api_key, load_cache  # noqa: E402

CLASSIFIER_EVAL_PATH = Path("reports/classifier_eval.md")
SAMPLE_OUTPUTS_PATH = Path("reports/sample_outputs.jsonl")
JUDGE_SCORES_MD_PATH = Path("reports/judge_scores.md")
JUDGE_SCORES_JSONL_PATH = Path("reports/judge_scores.jsonl")
HUMAN_SCORES_PATH = Path("eval/human_judge_scores.jsonl")
AGREEMENT_REPORT_PATH = Path("reports/judge_agreement.md")

RUBRIC_DIMENSIONS = ["grounded", "addresses_issue", "tone"]
RUBRIC_LABELS = {
    "grounded": "Grounded in historical pattern (matches how @comcastcares actually resolves this)",
    "addresses_issue": "Addresses the actual issue the customer raised",
    "tone": "Appropriate tone (polite, professional, on-brand)",
}


# ---------------------------------------------------------------------------
# Part 1: consolidate Phase 4's classifier metrics
# ---------------------------------------------------------------------------

def parse_markdown_table(lines, start_idx):
    """Parses a '| a | b |' table starting at start_idx (the header row).
    Returns (rows, next_idx) where rows is a list of lists of cell strings."""
    header = [c.strip() for c in lines[start_idx].strip().strip("|").split("|")]
    rows = []
    i = start_idx + 2  # skip header + separator row
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
        i += 1
    return header, rows, i


def load_classifier_metrics():
    if not CLASSIFIER_EVAL_PATH.exists():
        return None
    lines = CLASSIFIER_EVAL_PATH.read_text(encoding="utf-8").splitlines()
    accuracy, per_intent_f1 = {}, {}
    for i, line in enumerate(lines):
        if line.strip() == "## Accuracy":
            _header, rows, _ = parse_markdown_table(lines, i + 2)
            for name, acc in rows:
                accuracy[name] = acc
        if line.strip() == "## Per-intent F1":
            header, rows, _ = parse_markdown_table(lines, i + 2)
            classifiers = header[2:]
            for row in rows:
                intent, support = row[0], row[1]
                per_intent_f1[intent] = {"support": support, **dict(zip(classifiers, row[2:]))}
    return {"accuracy": accuracy, "per_intent_f1": per_intent_f1}


def print_classifier_summary(metrics):
    print("=" * 70)
    print("Phase 4 classifier metrics (from reports/classifier_eval.md)")
    print("=" * 70)
    if metrics is None:
        print("  reports/classifier_eval.md not found - run src/classify_intent.py first.")
        return
    print(f"\n{'Classifier':<12} {'Accuracy':>10}")
    for name, acc in metrics["accuracy"].items():
        print(f"{name:<12} {acc:>10}")
    classifiers = list(metrics["accuracy"].keys())
    print(f"\n{'Intent':<36} {'n':>4} " + " ".join(f"{c:>10}" for c in classifiers))
    for intent, row in metrics["per_intent_f1"].items():
        print(f"{intent:<36} {row['support']:>4} " + " ".join(f"{row.get(c, ''):>10}" for c in classifiers))
    print()


# ---------------------------------------------------------------------------
# Part 2: LLM-as-judge over Phase 5's 35 sample outputs
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are judging a drafted customer-support reply from @comcastcares (Comcast's \
Twitter support account). Score it 1-5 (5 = best) on each dimension below, with a brief \
one-sentence justification for each score.

1. grounded: Does the reply match the resolution style/content shown in the historical examples \
below (not generic boilerplate)?
2. addresses_issue: Does the reply directly address what the customer actually said?
3. tone: Is the tone polite, professional, and on-brand?

Customer message:
"{customer_message}"

Historical examples the reply was grounded in:
{examples_block}

Drafted reply being judged:
"{draft_reply}"

Return ONLY JSON in this exact form:
{{"grounded": {{"score": <1-5>, "justification": "..."}}, "addresses_issue": {{"score": <1-5>, "justification": "..."}}, "tone": {{"score": <1-5>, "justification": "..."}}}}
"""


def format_examples_block(retrieved_examples):
    if not retrieved_examples:
        return "(none retrieved)"
    return "\n".join(
        f'{i}. Customer: "{ex["customer_message"]}"\n   @comcastcares: "{ex["brand_reply"]}"'
        for i, ex in enumerate(retrieved_examples, start=1)
    )


def judge_one(api_key, cache, record):
    prompt = JUDGE_PROMPT.format(
        customer_message=record["customer_message"],
        examples_block=format_examples_block(record["retrieved_examples"]),
        draft_reply=record["draft_reply"],
    )
    content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=0.2)
    try:
        parsed = extract_json(content)
    except (ValueError, json.JSONDecodeError):
        parsed = {}

    result = {}
    for dim in RUBRIC_DIMENSIONS:
        entry = parsed.get(dim) if isinstance(parsed, dict) else None
        score = entry.get("score") if isinstance(entry, dict) else None
        justification = entry.get("justification") if isinstance(entry, dict) else None
        if not isinstance(score, (int, float)) or not (1 <= score <= 5):
            score = None
        result[dim] = {"score": score, "justification": justification or "(judge response unparseable)"}
    return result


MIN_JUDGED_TARGET = 20


def run_llm_judge(api_key, cache):
    if not SAMPLE_OUTPUTS_PATH.exists():
        print(f"ERROR: {SAMPLE_OUTPUTS_PATH} not found - run src/generate_reply.py first.")
        return None

    with SAMPLE_OUTPUTS_PATH.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f]

    # Reuse any already-successfully-judged examples from a prior run (this
    # account's free-tier Groq rate limit means a full 35-example pass can
    # take a while with retries; no need to redo the ones that already worked).
    prior = {r["thread_id"]: r for r in load_jsonl(JUDGE_SCORES_JSONL_PATH)}

    judged = []
    for rec in records:
        p = prior.get(rec["thread_id"])
        if p is not None and p.get("grounded_score") is not None:
            scores = {dim: {"score": p[f"{dim}_score"], "justification": p[f"{dim}_justification"]}
                      for dim in RUBRIC_DIMENSIONS}
            judged.append({"record": rec, "scores": scores})

    print(f"Reusing {len(judged)} already-successfully-judged examples from a prior run.")
    remaining = [rec for rec in records if rec["thread_id"] not in {j["record"]["thread_id"] for j in judged}]
    stopped_early = False

    for i, rec in enumerate(remaining, start=1):
        if len(judged) >= MIN_JUDGED_TARGET:
            print(f"Reached target of {MIN_JUDGED_TARGET} judged examples; stopping early per tight-timeline "
                  f"request ({len(remaining) - i + 1} of the 35 sample outputs left unjudged).")
            stopped_early = True
            break

        print(f"  [{i}/{len(remaining)} remaining] thread {rec['thread_id']}")
        scores = None
        for retry in range(4):
            try:
                scores = judge_one(api_key, cache, rec)
                break
            except requests.exceptions.HTTPError as e:
                if retry == 3:
                    print(f"    WARNING: judge call failed after retries ({e}); skipping this example")
                else:
                    wait = 20 * (retry + 1)
                    print(f"    rate limited, waiting {wait}s before retry ...")
                    time.sleep(wait)
        if scores is not None:
            judged.append({"record": rec, "scores": scores})
        time.sleep(2.5)  # pacing gap; this account's Groq tier is rate-limited per minute

    return judged, stopped_early


def build_judge_report(judged, stopped_early):
    lines = ["# LLM-as-Judge Scores\n"]
    coverage_note = (
        f"Groq judge scored {len(judged)} of the 35 drafted replies from `reports/sample_outputs.jsonl` "
        "on a 1-5 rubric: grounded in historical pattern, addresses the actual issue, and "
        "appropriate tone. Same rubric `src/human_judge_sample.py` uses for the blind human "
        "re-scoring of a subset."
    )
    if stopped_early:
        coverage_note += (
            f" Sample size was capped at {MIN_JUDGED_TARGET} (per a tight-timeline call) after this "
            "account's Groq free-tier rate limit made scoring all 35 too slow - the remaining examples "
            "were never attempted, not scored-and-failed."
        )
    lines.append(coverage_note + "\n")

    avg = {dim: [] for dim in RUBRIC_DIMENSIONS}
    for j in judged:
        for dim in RUBRIC_DIMENSIONS:
            score = j["scores"][dim]["score"]
            if score is not None:
                avg[dim].append(score)

    lines.append("## Average scores\n")
    for dim in RUBRIC_DIMENSIONS:
        scores = avg[dim]
        mean = sum(scores) / len(scores) if scores else 0
        lines.append(f"- **{RUBRIC_LABELS[dim]}**: {mean:.2f} / 5 (n={len(scores)})")
    lines.append("")

    lines.append("## Per-example scores\n")
    for j in judged:
        rec = j["record"]
        lines.append(f"### thread {rec['thread_id']}\n")
        lines.append(f"**Customer:** {rec['customer_message']}")
        lines.append(f"**Draft:** {rec['draft_reply']}\n")
        for dim in RUBRIC_DIMENSIONS:
            s = j["scores"][dim]
            lines.append(f"- {RUBRIC_LABELS[dim]}: **{s['score']}/5** - {s['justification']}")
        lines.append("")

    return "\n".join(lines)


def save_judge_scores(judged, stopped_early):
    JUDGE_SCORES_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JUDGE_SCORES_JSONL_PATH.open("w", encoding="utf-8") as f:
        for j in judged:
            rec = j["record"]
            f.write(json.dumps({
                "thread_id": rec["thread_id"],
                "customer_message": rec["customer_message"],
                "draft_reply": rec["draft_reply"],
                **{f"{dim}_score": j["scores"][dim]["score"] for dim in RUBRIC_DIMENSIONS},
                **{f"{dim}_justification": j["scores"][dim]["justification"] for dim in RUBRIC_DIMENSIONS},
            }) + "\n")

    report = build_judge_report(judged, stopped_early)
    JUDGE_SCORES_MD_PATH.write_text(report, encoding="utf-8")


# ---------------------------------------------------------------------------
# Part 4: human-vs-judge agreement (run after src/human_judge_sample.py)
# ---------------------------------------------------------------------------

def load_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def compute_agreement():
    judge_scores = {r["thread_id"]: r for r in load_jsonl(JUDGE_SCORES_JSONL_PATH)}
    human_scores = {r["thread_id"]: r for r in load_jsonl(HUMAN_SCORES_PATH)}

    if not human_scores:
        print(f"No human scores found at {HUMAN_SCORES_PATH} yet. "
              f"Run src/human_judge_sample.py first, then re-run with --agreement.")
        return
    if not judge_scores:
        print(f"No judge scores found at {JUDGE_SCORES_JSONL_PATH}. Run src/eval_harness.py first.")
        return

    shared_ids = [tid for tid in human_scores if tid in judge_scores]
    print(f"Comparing {len(shared_ids)} examples scored by both judge and human.\n")

    lines = ["# Human vs. LLM-Judge Agreement\n"]
    lines.append(f"{len(shared_ids)} examples scored by both the Groq judge and a human reviewer, "
                 f"blind to the judge's scores (see `src/human_judge_sample.py`).\n")
    lines.append("| Dimension | Exact match | Within 1 point |")
    lines.append("|---|---|---|")

    for dim in RUBRIC_DIMENSIONS:
        exact, within_one, total = 0, 0, 0
        for tid in shared_ids:
            j_score = judge_scores[tid].get(f"{dim}_score")
            h_score = human_scores[tid].get(f"{dim}_score")
            if j_score is None or h_score is None:
                continue
            total += 1
            diff = abs(j_score - h_score)
            if diff == 0:
                exact += 1
            if diff <= 1:
                within_one += 1
        exact_pct = exact / total if total else 0
        within_pct = within_one / total if total else 0
        print(f"  {RUBRIC_LABELS[dim]}: exact={exact_pct:.0%} within_1={within_pct:.0%} (n={total})")
        lines.append(f"| {RUBRIC_LABELS[dim]} | {exact_pct:.0%} (n={total}) | {within_pct:.0%} (n={total}) |")

    AGREEMENT_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nSaved agreement report to {AGREEMENT_REPORT_PATH}")


# ---------------------------------------------------------------------------

def main():
    if "--agreement" in sys.argv:
        compute_agreement()
        return

    metrics = load_classifier_metrics()
    print_classifier_summary(metrics)

    api_key = load_api_key()
    if not api_key:
        print("ERROR: GROQ_API_KEY not found (env or .env). Cannot run the LLM judge.", file=sys.stderr)
        sys.exit(1)
    cache = load_cache()

    result = run_llm_judge(api_key, cache)
    if result is None:
        return
    judged, stopped_early = result
    save_judge_scores(judged, stopped_early)
    print(f"\nJudged {len(judged)} examples. Saved to {JUDGE_SCORES_MD_PATH} and {JUDGE_SCORES_JSONL_PATH}")
    print("Next: run src/human_judge_sample.py to blind-score a subset yourself, "
          "then `python3 src/eval_harness.py --agreement`.")


if __name__ == "__main__":
    main()
