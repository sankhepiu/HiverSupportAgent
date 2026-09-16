"""
Phase 4: intent classifier + two baselines, evaluated against the
hand-labeled golden set.

Three classifiers, all predicting one of the 10 taxonomy intents for a
customer_message:
  1. TRIVIAL   - always predicts the golden set's actual majority label.
  2. SIMPLE    - keyword/rule matching derived from the taxonomy definitions.
  3. MAIN      - Groq few-shot classification (definitions + real examples),
                 batched and cached like Phase 2's classification calls.

Usage: python3 src/classify_intent.py
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from derive_taxonomy import call_groq, extract_json, load_api_key, load_cache, batched  # noqa: E402

GOLDEN_SET_PATH = Path("eval/golden_set.jsonl")
TAXONOMY_PATH = Path("data/intent_taxonomy.json")
ASSIGNMENTS_PATH = Path("data/intent_assignments.jsonl")
REPORT_PATH = Path("reports/classifier_eval.md")

MAIN_BATCH_SIZE = 25
FEWSHOT_PER_INTENT = 2
FEWSHOT_SEED = 20260917

# Keyword lists derived from each intent's definition in
# reports/intent_taxonomy.md. First keyword hit wins by count; ties broken
# by taxonomy order, no match falls back to the trivial majority label.
KEYWORDS = {
    "Equipment Issues": ["equipment", "box", "router", "gateway", "modem", "return",
                          "rent", "reset the", "install", "malfunction", "device"],
    "Service Outage": ["outage", "is down", "down again", "not working", "went out",
                        "everything is down", "service is out", "no service"],
    "Streaming Content Issues": ["on demand", "stream", "app", "episode", "xfinity app",
                                  "record function", "watch", "content", "playback"],
    "Channel Issues": ["channel", "hd", "lineup", "package", "espn", "guide", "programming"],
    "Internet Performance": ["slow", "speed", "wifi", "wi-fi", "mbps", "throttle",
                              "data cap", "connection", "drop", "lag", "buffering"],
    "Billing Issues": ["bill", "charge", "refund", "credit", "payment", "price",
                        "fee", "invoice", "overcharge", "rate"],
    "Account Management": ["account", "login", "password", "sign in", "update my info",
                            "cancel my service", "change my plan"],
    "Technical Support": ["error code", "troubleshoot", "reboot", "restart", "signal",
                           "configure", "vpn", "technical"],
    "Service Availability & Scheduling": ["available in", "availability", "schedule",
                                           "appointment", "technician", "reschedule",
                                           "move my service", "activate"],
    "Escalation & Security": ["supervisor", "manager", "escalate", "fraud", "hack",
                               "unauthorized", "breach", "scam", "unacceptable",
                               "ridiculous", "cancelling"],
}


def load_golden_set():
    with GOLDEN_SET_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_taxonomy():
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def load_assignments():
    with ASSIGNMENTS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def majority_label(golden):
    return Counter(rec["label_intent"] for rec in golden).most_common(1)[0][0]


def classify_trivial(golden):
    label = majority_label(golden)
    return [label] * len(golden)


def classify_simple(golden, taxonomy):
    names = [t["name"] for t in taxonomy]
    fallback = majority_label(golden)
    predictions = []
    for rec in golden:
        text = rec["customer_message"].lower()
        scores = {name: sum(1 for kw in KEYWORDS[name] if kw in text) for name in names}
        best_score = max(scores.values())
        if best_score == 0:
            predictions.append(fallback)
            continue
        best = next(name for name in names if scores[name] == best_score)
        predictions.append(best)
    return predictions


def pick_fewshot_examples(assignments, taxonomy, exclude_thread_ids):
    rng = random.Random(FEWSHOT_SEED)
    examples = {}
    for t in taxonomy:
        name = t["name"]
        pool = [a for a in assignments
                if a["intent"] == name and not a["failed"] and a["thread_id"] not in exclude_thread_ids]
        examples[name] = [a["customer_message"] for a in rng.sample(pool, min(FEWSHOT_PER_INTENT, len(pool)))]
    return examples


FEWSHOT_CLASSIFY_PROMPT = """Classify each of the following customer support messages sent to \
Comcast (@comcastcares) into exactly one of these intents. Each intent's definition is given \
along with real example messages.

{taxonomy_block}

Return ONLY a JSON array of length {n}, in the same order as the messages, containing just the \
intent name for each message. If a message doesn't clearly fit any intent, use "Other".

Messages:
{numbered}
"""


def build_taxonomy_block(taxonomy, fewshot_examples):
    lines = []
    for t in taxonomy:
        lines.append(f"- {t['name']}: {t['definition']}")
        for ex in fewshot_examples.get(t["name"], []):
            lines.append(f"    e.g. \"{ex}\"")
    return "\n".join(lines)


def looks_degenerate(labels):
    """Small models at temperature=0 occasionally collapse into repeating one
    label for most of a batch - valid JSON of the right length, but not a
    real classification. No golden-set intent exceeds ~20% share, so a
    batch where one label is >50% of the output is almost certainly this
    failure mode, not a genuine skew."""
    if len(labels) < 10:
        return False
    return Counter(labels).most_common(1)[0][1] / len(labels) > 0.5


def classify_main(api_key, cache, golden, taxonomy, assignments):
    golden_ids = {rec["thread_id"] for rec in golden}
    fewshot_examples = pick_fewshot_examples(assignments, taxonomy, golden_ids)
    taxonomy_block = build_taxonomy_block(taxonomy, fewshot_examples)
    fallback = majority_label(golden)
    valid_names = {t["name"] for t in taxonomy}

    predictions = [None] * len(golden)
    batches = list(batched(list(enumerate(golden)), MAIN_BATCH_SIZE))
    for i, batch in enumerate(batches, start=1):
        print(f"  Main classifier batch {i}/{len(batches)} ({len(batch)} messages) ...")
        numbered = "\n".join(f"{j}. {rec['customer_message']}" for j, (_, rec) in enumerate(batch, start=1))
        prompt = FEWSHOT_CLASSIFY_PROMPT.format(taxonomy_block=taxonomy_block, n=len(batch), numbered=numbered)

        labels = []
        for temperature in (0.0, 0.4):
            content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=temperature)
            try:
                labels = extract_json(content)
            except (ValueError, json.JSONDecodeError):
                labels = []
            if labels and not looks_degenerate(labels):
                break
            print(f"    WARNING: degenerate/malformed response at temperature={temperature}, retrying" if temperature == 0.0
                  else "    WARNING: still degenerate after retry, falling back to majority for this batch")
            labels = []  # discard degenerate output so the fallback path below fills the whole batch

        for (idx, _rec), label in zip(batch, labels):
            predictions[idx] = label if label in valid_names else fallback
        for idx, _rec in batch[len(labels):]:
            predictions[idx] = fallback  # malformed/truncated/degenerate: fall back rather than crash

    return predictions


def evaluate(golden, predictions):
    gold_labels = [rec["label_intent"] for rec in golden]
    n = len(gold_labels)
    accuracy = sum(g == p for g, p in zip(gold_labels, predictions)) / n

    per_intent = {}
    for name in sorted(set(gold_labels) | set(predictions)):
        tp = sum(1 for g, p in zip(gold_labels, predictions) if g == name and p == name)
        fp = sum(1 for g, p in zip(gold_labels, predictions) if g != name and p == name)
        fn = sum(1 for g, p in zip(gold_labels, predictions) if g == name and p != name)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_intent[name] = {"precision": precision, "recall": recall, "f1": f1, "support": gold_labels.count(name)}

    return accuracy, per_intent


def print_comparison(taxonomy, golden, results):
    names = [t["name"] for t in taxonomy]
    support = Counter(rec["label_intent"] for rec in golden)

    print(f"\n{'Classifier':<12} {'Accuracy':>10}")
    for name, (acc, _) in results.items():
        print(f"{name:<12} {acc:>9.1%}")

    print(f"\n{'Intent':<36} {'n':>4} " + " ".join(f"{name:>10}" for name in results))
    for intent in names:
        row = f"{intent:<36} {support.get(intent, 0):>4} "
        row += " ".join(f"{results[name][1].get(intent, {}).get('f1', 0.0):>10.2f}" for name in results)
        print(row)


def build_report(taxonomy, golden, results):
    names = [t["name"] for t in taxonomy]
    support = Counter(rec["label_intent"] for rec in golden)

    lines = ["# Classifier Evaluation vs. Golden Set\n"]
    lines.append(
        f"Three classifiers evaluated against all {len(golden)} hand-labeled examples in "
        f"`{GOLDEN_SET_PATH}`: a trivial majority-class baseline, a keyword/rule-based baseline, "
        f"and the main Groq few-shot classifier.\n"
    )
    lines.append("## Accuracy\n")
    lines.append("| Classifier | Accuracy |")
    lines.append("|---|---|")
    for name, (acc, _) in results.items():
        lines.append(f"| {name} | {acc:.1%} |")
    lines.append("")

    lines.append("## Per-intent F1\n")
    lines.append("| Intent | Support (n) | " + " | ".join(results.keys()) + " |")
    lines.append("|---|---|" + "---|" * len(results))
    for intent in names:
        row = f"| {intent} | {support.get(intent, 0)} | "
        row += " | ".join(f"{results[name][1].get(intent, {}).get('f1', 0.0):.2f}" for name in results) + " |"
        lines.append(row)
    lines.append("")

    lines.append("## Caveat: small-support intents\n")
    rare = [intent for intent in names if support.get(intent, 0) < 10]
    lines.append(
        "The golden set's label distribution mirrors the underlying data and is naturally "
        f"imbalanced (see `reports/intent_taxonomy.md`). Intents with fewer than 10 labeled "
        f"examples in the golden set (**{', '.join(rare) if rare else 'none'}**) have F1 scores "
        "computed over a very small sample — a single misclassification can swing F1 by "
        "10-50 points. Treat per-intent F1 for these as directional, not precise, and prefer "
        "the accuracy/macro comparisons and confusion patterns over any single rare-intent F1 "
        "number when judging the main classifier.\n"
    )

    lines.append("## Notes\n")
    lines.append(
        "- The main classifier's few-shot examples were drawn from Phase 2's 1500-message "
        "sample, explicitly excluding any thread that appears in the golden set, to avoid "
        "test-set leakage.\n"
        "- The main classifier may predict \"Other\" (not one of the 10 intents) for messages "
        "it can't confidently place; since every golden-set label is one of the 10 intents, "
        "an \"Other\" prediction always counts as a miss in this evaluation.\n"
    )

    return "\n".join(lines)


def main():
    for path in (GOLDEN_SET_PATH, TAXONOMY_PATH, ASSIGNMENTS_PATH):
        if not path.exists():
            print(f"ERROR: {path} not found. Run earlier phase scripts first.")
            return

    golden = load_golden_set()
    taxonomy = load_taxonomy()
    assignments = load_assignments()
    print(f"Loaded {len(golden)} golden-set examples\n")

    missing_keywords = [t["name"] for t in taxonomy if t["name"] not in KEYWORDS]
    if missing_keywords:
        print(f"ERROR: KEYWORDS dict is missing entries for: {missing_keywords}. "
              f"Taxonomy names changed since this script was written.", file=sys.stderr)
        sys.exit(1)

    print("Running TRIVIAL baseline ...")
    trivial_preds = classify_trivial(golden)

    print("Running SIMPLE keyword baseline ...")
    simple_preds = classify_simple(golden, taxonomy)

    api_key = load_api_key()
    if not api_key:
        print("ERROR: GROQ_API_KEY not found (env or .env). Cannot run the main classifier.", file=sys.stderr)
        sys.exit(1)
    cache = load_cache()
    print("Running MAIN Groq few-shot classifier ...")
    main_preds = classify_main(api_key, cache, golden, taxonomy, assignments)

    results = {
        "Trivial": evaluate(golden, trivial_preds),
        "Simple": evaluate(golden, simple_preds),
        "Main": evaluate(golden, main_preds),
    }

    print_comparison(taxonomy, golden, results)

    report = build_report(taxonomy, golden, results)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nSaved comparison report to {REPORT_PATH}")


if __name__ == "__main__":
    main()
