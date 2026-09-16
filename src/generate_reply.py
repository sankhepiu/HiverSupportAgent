"""
Phase 5: reply drafting grounded in historically resolved threads, plus an
auto-handle vs escalate decision, run over a sample of golden-set examples.

Pipeline per query message:
  1. Classify intent + confidence (batched Groq call, same style as Phase 4).
  2. Retrieve the top-3 most similar, well-resolved historical threads for
     that intent via TF-IDF cosine similarity (no vector DB needed at this
     scale - pool is ~60-215 threads per intent).
  3. Draft a reply grounded in those retrieved threads (Groq).
  4. Decide auto-handle vs escalate from confidence + intent risk + whether
     grounding was found, always with a plain-text reason.

Requires Phases 1-4 to have already produced their output files. Groq calls
are cached in .cache/groq_cache.json, same as Phase 2 and 4.

Usage: python3 src/generate_reply.py
"""

import json
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from derive_taxonomy import call_groq, extract_json, load_api_key, load_cache, batched  # noqa: E402
from classify_intent import (  # noqa: E402
    load_golden_set, load_taxonomy, load_assignments,
    pick_fewshot_examples, build_taxonomy_block, looks_degenerate, majority_label,
)

THREADS_PATH = Path("data/comcastcares_threads.jsonl")
REPORT_PATH = Path("reports/sample_outputs.md")

SAMPLE_SIZE = 35
SAMPLE_SEED = 20260918
CLASSIFY_BATCH_SIZE = 25
TOP_K_RETRIEVAL = 3
# Named explicitly in the brief as the intents that should lean toward
# escalation more readily (financial disputes, security/harassment cases).
RISKY_INTENTS = {"Billing Issues", "Escalation & Security"}


# ---------------------------------------------------------------------------
# "Well-resolved" heuristic + validation against the golden set's own labels
# ---------------------------------------------------------------------------

POSITIVE_FOLLOWUP_MARKERS = ["thank", "thanks", "thx", "appreciate", "great", "awesome",
                             "perfect", "resolved", "fixed", "works now", "worked", "got it", "all set"]
NEGATIVE_FOLLOWUP_MARKERS = ["still not", "still doesn't", "still no", "not fixed", "not working",
                             "worse", "ridiculous", "unacceptable", "no help", "useless",
                             "still waiting", "never", "not resolved", "didn't work", "doesn't work"]


def heuristic_resolved(customer_followup):
    """Returns 'resolved' / 'not_resolved' / 'unknown' (no follow-up to judge from)."""
    if not customer_followup:
        return "unknown"
    text = customer_followup.lower()
    pos = sum(1 for m in POSITIVE_FOLLOWUP_MARKERS if m in text)
    neg = sum(1 for m in NEGATIVE_FOLLOWUP_MARKERS if m in text)
    if pos > neg:
        return "resolved"
    if neg > pos:
        return "not_resolved"
    return "unknown"


def validate_heuristic_against_golden(golden):
    confusion = Counter()
    for rec in golden:
        followup = rec.get("customer_followup")
        if not followup:
            continue
        confusion[(heuristic_resolved(followup), rec["label_resolved"])] += 1
    return confusion


# ---------------------------------------------------------------------------
# Lightweight TF-IDF retrieval (pure stdlib, no vector DB)
# ---------------------------------------------------------------------------

def tokenize(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def build_tfidf_index(docs_tokens):
    n = len(docs_tokens)
    df = Counter()
    for tokens in docs_tokens:
        for term in set(tokens):
            df[term] += 1
    idf = {term: math.log((n + 1) / (count + 1)) + 1 for term, count in df.items()}

    def vectorize(tokens):
        length = len(tokens) or 1
        tf = Counter(tokens)
        return {term: (count / length) * idf.get(term, 0) for term, count in tf.items()}

    doc_vectors = [vectorize(tokens) for tokens in docs_tokens]
    return idf, vectorize, doc_vectors


def cosine_sim(vec_a, vec_b):
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_retrieval_pools(assignments, threads_by_id, exclude_thread_ids, taxonomy):
    """One TF-IDF index per intent, over well-resolved (or unknown-resolution)
    historical threads for that intent, excluding golden-set threads."""
    pools = {}
    for t in taxonomy:
        name = t["name"]
        docs = []
        for a in assignments:
            if a["intent"] != name or a["failed"] or a["thread_id"] in exclude_thread_ids:
                continue
            thread = threads_by_id.get(a["thread_id"])
            if thread is None:
                continue
            if heuristic_resolved(thread.get("customer_followup")) == "not_resolved":
                continue
            docs.append(thread)
        idf, vectorize, doc_vectors = build_tfidf_index([tokenize(d["customer_message"]) for d in docs])
        pools[name] = {"docs": docs, "vectorize": vectorize, "doc_vectors": doc_vectors}
    return pools


def retrieve(pools, intent, query_message, k=TOP_K_RETRIEVAL):
    pool = pools.get(intent)
    if not pool or not pool["docs"]:
        return []
    query_vec = pool["vectorize"](tokenize(query_message))
    scored = [(cosine_sim(query_vec, dv), doc) for dv, doc in zip(pool["doc_vectors"], pool["docs"])]
    scored = [(s, d) for s, d in scored if s > 0]
    scored.sort(key=lambda sd: sd[0], reverse=True)
    return [d for _s, d in scored[:k]]


# ---------------------------------------------------------------------------
# Stage 1: batched classify intent + confidence
# ---------------------------------------------------------------------------

CLASSIFY_CONFIDENCE_PROMPT = """Classify each of the following customer support messages sent to \
Comcast (@comcastcares) into exactly one of these intents, and estimate your confidence.

{taxonomy_block}

Return ONLY a JSON array of length {n}, in the same order as the messages. Each element must be \
{{"intent": "<one of the intent names above, or \\"Other\\">", "confidence": "high"|"medium"|"low"}}.

Messages:
{numbered}
"""


def classify_with_confidence(api_key, cache, messages, taxonomy, fewshot_examples):
    taxonomy_block = build_taxonomy_block(taxonomy, fewshot_examples)
    valid_names = {t["name"] for t in taxonomy}
    results = [None] * len(messages)

    batches = list(batched(list(enumerate(messages)), CLASSIFY_BATCH_SIZE))
    for i, batch in enumerate(batches, start=1):
        print(f"  Classify+confidence batch {i}/{len(batches)} ({len(batch)} messages) ...")
        numbered = "\n".join(f"{j}. {msg}" for j, (_, msg) in enumerate(batch, start=1))
        prompt = CLASSIFY_CONFIDENCE_PROMPT.format(taxonomy_block=taxonomy_block, n=len(batch), numbered=numbered)

        parsed = []
        for temperature in (0.0, 0.4):
            content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=temperature)
            try:
                parsed = extract_json(content)
            except (ValueError, json.JSONDecodeError):
                parsed = []
            intents_only = [p.get("intent") if isinstance(p, dict) else None for p in parsed]
            if parsed and not looks_degenerate(intents_only):
                break
            parsed = []

        for (idx, _msg), item in zip(batch, parsed):
            intent = item.get("intent") if isinstance(item, dict) else None
            confidence = item.get("confidence") if isinstance(item, dict) else None
            if intent not in valid_names:
                intent, confidence = "Other", "low"
            if confidence not in ("high", "medium", "low"):
                confidence = "medium"
            results[idx] = {"intent": intent, "confidence": confidence}
        for idx, _msg in batch[len(parsed):]:
            results[idx] = {"intent": "Other", "confidence": "low"}

    return results


# ---------------------------------------------------------------------------
# Stage 2: draft reply grounded in retrieved examples
# ---------------------------------------------------------------------------

DRAFT_PROMPT = """You are drafting a reply as @comcastcares, Comcast's Twitter customer support \
account. Match their real tone and resolution style shown in the historical examples below - \
concise, polite, pointing to a concrete next step - not generic customer-service boilerplate.

Customer's message (intent: {intent}):
"{message}"

Historical examples of @comcastcares resolving similar issues:
{examples_block}

Draft ONLY the reply text @comcastcares would send. No quotes, no preamble, no explanation.
"""


def draft_reply(api_key, cache, message, intent, retrieved):
    if retrieved:
        examples_block = "\n".join(
            f'{i}. Customer: "{d["customer_message"]}"\n   @comcastcares: "{d["brand_reply"]}"'
            for i, d in enumerate(retrieved, start=1)
        )
    else:
        examples_block = "(no well-resolved historical examples were found for this intent)"

    prompt = DRAFT_PROMPT.format(intent=intent, message=message, examples_block=examples_block)
    content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=0.3)
    return content.strip().strip('"')


# ---------------------------------------------------------------------------
# Stage 3: auto-handle vs escalate decision
# ---------------------------------------------------------------------------

def decide_escalation(intent, confidence, retrieved):
    score = 0
    concerns = []

    if not retrieved:
        score += 2
        concerns.append("no well-resolved historical examples found for this intent")
    if confidence == "low":
        score += 2
        concerns.append("classifier confidence is low")
    elif confidence == "medium":
        score += 1
        concerns.append("classifier confidence is only medium")
    is_risky = intent in RISKY_INTENTS
    if is_risky:
        score += 1
        concerns.append(f"'{intent}' is a sensitive intent (billing/security) that escalates more readily")

    escalate = score >= 2
    if escalate:
        reason = "Escalate to human: " + "; ".join(concerns) + "."
    elif is_risky:
        reason = (f"Auto-handle: '{intent}' is a sensitive intent, but {confidence} classifier confidence "
                  f"and {len(retrieved)} well-resolved historical examples were judged sufficient to proceed.")
    else:
        reason = (f"Auto-handle: {confidence}-confidence classification in a low-risk intent, with "
                  f"{len(retrieved)} well-resolved historical examples for grounding.")
    return escalate, reason


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def build_report(golden_sample, classifications, retrieved_lists, drafts, decisions, confusion):
    lines = ["# Phase 5 Sample Outputs: Reply Drafting + Escalation Decisions\n"]
    lines.append(
        f"Run over a random sample of {len(golden_sample)} golden-set examples (seed={SAMPLE_SEED}). "
        "For each: intent + confidence are classified fresh (few-shot Groq, same approach as Phase 4's "
        "main classifier), the top-3 most similar well-resolved historical threads for that intent are "
        "retrieved via TF-IDF, a reply is drafted grounded in those threads, and an auto-handle/escalate "
        "decision is made with a stated reason.\n"
    )

    lines.append("## \"Well-resolved\" heuristic validation\n")
    lines.append(
        "The retrieval pool prefers threads whose customer follow-up reads as resolved "
        "(keyword heuristic on positive/negative language), and excludes ones that read as "
        "unresolved; threads with no follow-up are kept (no evidence either way), not discarded. "
        "Checked against the golden set's own human `label_resolved` judgments, for the "
        f"{sum(confusion.values())} golden examples that have a customer follow-up:\n"
    )
    lines.append("| Heuristic says | Human said yes | Human said partial | Human said no |")
    lines.append("|---|---|---|---|")
    for pred in ("resolved", "not_resolved", "unknown"):
        row = f"| {pred} | {confusion.get((pred, 'yes'), 0)} | {confusion.get((pred, 'partial'), 0)} | {confusion.get((pred, 'no'), 0)} |"
        lines.append(row)
    lines.append(
        "\nThe heuristic is deliberately conservative (only used to *exclude* clearly-bad threads "
        "from retrieval, not to certify good ones), so some disagreement here is expected and "
        "acceptable for that purpose.\n"
    )

    escalate_count = sum(1 for e, _ in decisions if e)
    lines.append(f"## Summary: {escalate_count}/{len(decisions)} escalated, {len(decisions) - escalate_count}/{len(decisions)} auto-handled\n")

    for i, rec in enumerate(golden_sample):
        cls = classifications[i]
        retrieved = retrieved_lists[i]
        draft = drafts[i]
        escalate, reason = decisions[i]

        lines.append(f"## Example {i + 1}: thread {rec['thread_id']}\n")
        lines.append(f"**Customer:** {rec['customer_message']}\n")
        lines.append(f"**Classified intent:** {cls['intent']} (confidence: {cls['confidence']}) "
                      f"| **Human label:** {rec['label_intent']}\n")
        lines.append(f"**Retrieved grounding examples:** {len(retrieved)}")
        for d in retrieved:
            lines.append(f"  - \"{d['customer_message']}\" → \"{d['brand_reply']}\"")
        lines.append("")
        lines.append(f"**Drafted reply:** {draft}\n")
        lines.append(f"**Decision:** {'ESCALATE' if escalate else 'AUTO-HANDLE'} — {reason}\n")
        lines.append(f"**Actual historical reply (for comparison):** {rec['brand_reply']}\n")
        lines.append("---\n")

    return "\n".join(lines)


def main():
    for path in (THREADS_PATH,):
        if not path.exists():
            print(f"ERROR: {path} not found. Run earlier phase scripts first.")
            return

    api_key = load_api_key()
    if not api_key:
        print("ERROR: GROQ_API_KEY not found (env or .env).", file=sys.stderr)
        sys.exit(1)
    cache = load_cache()

    golden = load_golden_set()
    taxonomy = load_taxonomy()
    assignments = load_assignments()

    print(f"Loading {THREADS_PATH} ...")
    threads_by_id = {}
    with THREADS_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            threads_by_id[row["thread_id"]] = row

    confusion = validate_heuristic_against_golden(golden)
    print("Well-resolved heuristic vs. human label_resolved (on golden examples with a follow-up):")
    for pred in ("resolved", "not_resolved", "unknown"):
        print(f"  {pred}: yes={confusion.get((pred, 'yes'), 0)} "
              f"partial={confusion.get((pred, 'partial'), 0)} no={confusion.get((pred, 'no'), 0)}")

    golden_ids = {rec["thread_id"] for rec in golden}
    print("\nBuilding per-intent retrieval pools ...")
    pools = build_retrieval_pools(assignments, threads_by_id, golden_ids, taxonomy)
    for name, pool in pools.items():
        print(f"  {name}: {len(pool['docs'])} candidate threads")

    rng = random.Random(SAMPLE_SEED)
    golden_sample = rng.sample(golden, min(SAMPLE_SIZE, len(golden)))
    print(f"\nSampled {len(golden_sample)} golden-set examples for this run\n")

    fewshot_examples = pick_fewshot_examples(assignments, taxonomy, golden_ids)

    print("Stage 1: classify intent + confidence ...")
    messages = [rec["customer_message"] for rec in golden_sample]
    classifications = classify_with_confidence(api_key, cache, messages, taxonomy, fewshot_examples)

    print("\nStage 2+3: retrieve grounding, draft replies, decide escalation ...")
    retrieved_lists, drafts, decisions = [], [], []
    for i, (rec, cls) in enumerate(zip(golden_sample, classifications), start=1):
        print(f"  [{i}/{len(golden_sample)}] thread {rec['thread_id']} -> {cls['intent']} ({cls['confidence']})")
        retrieved = retrieve(pools, cls["intent"], rec["customer_message"])
        draft = draft_reply(api_key, cache, rec["customer_message"], cls["intent"], retrieved)
        escalate, reason = decide_escalation(cls["intent"], cls["confidence"], retrieved)
        retrieved_lists.append(retrieved)
        drafts.append(draft)
        decisions.append((escalate, reason))

    report = build_report(golden_sample, classifications, retrieved_lists, drafts, decisions, confusion)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    escalate_count = sum(1 for e, _ in decisions if e)
    print(f"\n{escalate_count}/{len(decisions)} escalated, {len(decisions) - escalate_count}/{len(decisions)} auto-handled")
    print(f"Saved sample outputs to {REPORT_PATH}")


if __name__ == "__main__":
    main()
