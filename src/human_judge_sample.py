"""
Phase 6: blind human re-scoring of a subset of Phase 5's drafted replies, on
the same rubric given to the Groq LLM judge (src/eval_harness.py). This does
NOT show the judge's scores - it's meant to be independent, so agreement
between the two means something.

Usage:
  python3 src/human_judge_sample.py            interactive scoring session
  python3 src/human_judge_sample.py --summary   print scoring progress only
"""

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_OUTPUTS_PATH = Path("reports/sample_outputs.jsonl")
OUTPUT_PATH = Path("eval/human_judge_scores.jsonl")

HUMAN_SAMPLE_SIZE = 28
HUMAN_SAMPLE_SEED = 20260919

RUBRIC = [
    ("grounded", "Grounded in historical pattern (matches how @comcastcares actually resolves this)"),
    ("addresses_issue", "Addresses the actual issue the customer raised"),
    ("tone", "Appropriate tone (polite, professional, on-brand)"),
]


def load_sample_outputs():
    with SAMPLE_OUTPUTS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_existing_scores():
    if not OUTPUT_PATH.exists():
        return []
    with OUTPUT_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def print_summary():
    scores = load_existing_scores()
    print(f"Scored so far: {len(scores)} / {HUMAN_SAMPLE_SIZE}")
    for dim, label in RUBRIC:
        vals = [s[f"{dim}_score"] for s in scores if s.get(f"{dim}_score") is not None]
        avg = sum(vals) / len(vals) if vals else 0
        print(f"  {label}: avg {avg:.2f}/5 (n={len(vals)})")


def prompt_score(label):
    print(f"{label} (1-5):")
    while True:
        raw = input("> ").strip().lower()
        if raw in ("q", "quit"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= 5:
            return int(raw)
        print("Please enter a number 1-5, or 'q' to quit.")


def score_session():
    if not SAMPLE_OUTPUTS_PATH.exists():
        print(f"ERROR: {SAMPLE_OUTPUTS_PATH} not found - run src/generate_reply.py first.")
        return

    records = load_sample_outputs()
    rng = random.Random(HUMAN_SAMPLE_SEED)
    sample = rng.sample(records, min(HUMAN_SAMPLE_SIZE, len(records)))

    already_scored = {s["thread_id"] for s in load_existing_scores()}
    remaining = [r for r in sample if r["thread_id"] not in already_scored]

    if not remaining:
        print("All sampled examples are already scored.")
        print_summary()
        return

    print(f"Resuming: {len(already_scored)} already scored, {len(remaining)} remaining "
          f"(target {len(sample)}). Type 'q' at any prompt to save and quit.\n")
    print("You will NOT be shown the LLM judge's scores - score independently.\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as out_f:
        for rec in remaining:
            print("=" * 70)
            print(f"[{len(already_scored) + 1}/{len(sample)}] thread {rec['thread_id']} "
                  f"(intent: {rec['classified_intent']})")
            print("-" * 70)
            print(f"CUSTOMER:  {rec['customer_message']}\n")
            print("HISTORICAL EXAMPLES USED FOR GROUNDING:")
            if rec["retrieved_examples"]:
                for i, ex in enumerate(rec["retrieved_examples"], start=1):
                    print(f"  {i}. Customer: {ex['customer_message']}")
                    print(f"     @comcastcares: {ex['brand_reply']}")
            else:
                print("  (none retrieved)")
            print(f"\nDRAFTED REPLY:  {rec['draft_reply']}\n")

            scores = {}
            quit_now = False
            for dim, label in RUBRIC:
                score = prompt_score(label)
                if score is None:
                    quit_now = True
                    break
                scores[dim] = score
            if quit_now:
                break

            notes = input("Notes (optional, Enter to skip): ").strip()

            record = {
                "thread_id": rec["thread_id"],
                "customer_message": rec["customer_message"],
                "draft_reply": rec["draft_reply"],
                **{f"{dim}_score": scores[dim] for dim, _ in RUBRIC},
                "notes": notes,
                "scored_at": datetime.now(timezone.utc).isoformat(),
            }
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()
            already_scored.add(rec["thread_id"])
            print()

    print("\nSession ended.\n")
    print_summary()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Print scoring progress and exit")
    args = parser.parse_args()

    if args.summary:
        print_summary()
        return

    score_session()


if __name__ == "__main__":
    main()
