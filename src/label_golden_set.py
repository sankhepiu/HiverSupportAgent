"""
Phase 3: interactive tool for hand-labeling the golden evaluation set.

This does NOT auto-label anything. It samples a candidate list of threads
(stratified by Phase 2's intent distribution, with rare-intent oversampling
and deliberately hard cases), then walks a human labeler through them one
at a time in the terminal.

Requires Phase 1 (data/comcastcares_threads.jsonl) and Phase 2
(data/intent_taxonomy.json, data/intent_assignments.jsonl) to already exist.

Usage:
  python3 src/label_golden_set.py            interactive labeling session
  python3 src/label_golden_set.py --plan      print the sampling plan only
  python3 src/label_golden_set.py --summary   print labeling progress only
"""

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

THREADS_PATH = Path("data/comcastcares_threads.jsonl")
TAXONOMY_PATH = Path("data/intent_taxonomy.json")
ASSIGNMENTS_PATH = Path("data/intent_assignments.jsonl")
OUTPUT_PATH = Path("eval/golden_set.jsonl")

GOLDEN_SET_TARGET = 200
HARD_CASE_FRACTION = 0.15  # share of the target reserved for deliberately hard cases
# Blend between true proportional share and an equal per-intent share, so
# rare intents aren't reduced to 1-2 examples but the set still roughly
# tracks the real distribution. 1.0 = pure proportional, 0.0 = pure uniform.
PROPORTIONAL_WEIGHT = 0.7
SAMPLING_SEED = 20260916  # fixed seed for candidate selection, independent of Phase 2's seed


def load_taxonomy():
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def load_assignments():
    with ASSIGNMENTS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_threads_by_id():
    threads = {}
    with THREADS_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            threads[row["thread_id"]] = row
    return threads


def largest_remainder_allocation(shares, n_slots):
    """Apportion n_slots across `shares` (name -> weight, sums to ~1) using
    largest-remainder rounding so the total is exactly n_slots."""
    raw = {name: n_slots * share for name, share in shares.items()}
    floors = {name: int(v) for name, v in raw.items()}
    remainder = n_slots - sum(floors.values())
    remainders = sorted(raw.items(), key=lambda kv: kv[1] - floors[kv[0]], reverse=True)
    for name, _ in remainders[:remainder]:
        floors[name] += 1
    return floors


def cap_and_redistribute(allocation, available):
    """Cap each allocation at its pool's availability, then hand any
    resulting shortfall to categories that still have room, largest
    remaining capacity first. Repeats until stable."""
    allocation = dict(allocation)
    while True:
        shortfall = 0
        for name, n in allocation.items():
            cap = available.get(name, 0)
            if n > cap:
                shortfall += n - cap
                allocation[name] = cap
        if shortfall == 0:
            return allocation
        room = {name: available.get(name, 0) - allocation[name] for name in allocation}
        room = {name: r for name, r in room.items() if r > 0}
        if not room:
            return allocation  # nowhere left to put the shortfall
        total_room = sum(room.values())
        for name, r in sorted(room.items(), key=lambda kv: kv[1], reverse=True):
            take = min(r, round(shortfall * r / total_room))
            allocation[name] += take


def build_sampling_plan(taxonomy, assignments):
    by_intent = {t["name"]: [] for t in taxonomy}
    other_pool = []
    failed_pool = []
    for a in assignments:
        if a["failed"]:
            failed_pool.append(a)
        elif a["intent"] == "Other":
            other_pool.append(a)
        elif a["intent"] in by_intent:
            by_intent[a["intent"]].append(a)

    hard_target = round(GOLDEN_SET_TARGET * HARD_CASE_FRACTION)
    hard_pool_total = len(other_pool) + len(failed_pool)
    other_target = min(len(other_pool), round(hard_target * len(other_pool) / hard_pool_total)) if hard_pool_total else 0
    failed_target = min(len(failed_pool), hard_target - other_target)

    stratified_target = GOLDEN_SET_TARGET - other_target - failed_target
    total_intent_pool = sum(len(v) for v in by_intent.values())
    n_intents = len(taxonomy)
    shares = {}
    for name, pool in by_intent.items():
        proportional = (len(pool) / total_intent_pool) if total_intent_pool else 0
        uniform = 1 / n_intents
        shares[name] = PROPORTIONAL_WEIGHT * proportional + (1 - PROPORTIONAL_WEIGHT) * uniform
    share_total = sum(shares.values()) or 1
    shares = {name: s / share_total for name, s in shares.items()}

    allocation = largest_remainder_allocation(shares, stratified_target)
    allocation = cap_and_redistribute(allocation, {name: len(pool) for name, pool in by_intent.items()})

    rng = random.Random(SAMPLING_SEED)
    candidates = []
    for name in sorted(by_intent):
        pool = by_intent[name]
        n = min(allocation.get(name, 0), len(pool))
        for a in rng.sample(pool, n):
            candidates.append({**a, "sample_reason": "stratified"})
    for a in rng.sample(other_pool, other_target):
        candidates.append({**a, "sample_reason": "other_bucket"})
    for a in rng.sample(failed_pool, failed_target):
        candidates.append({**a, "sample_reason": "classification_failure"})

    rng.shuffle(candidates)

    plan_info = {
        "hard_target": hard_target,
        "other_target": other_target,
        "failed_target": failed_target,
        "stratified_target": stratified_target,
        "allocation": allocation,
        "pool_sizes": {name: len(pool) for name, pool in by_intent.items()},
        "other_pool_size": len(other_pool),
        "failed_pool_size": len(failed_pool),
    }
    return candidates, plan_info


def print_plan(plan_info, taxonomy):
    print(f"Target golden set size: {GOLDEN_SET_TARGET}")
    print(f"Hard cases: {plan_info['hard_target']} "
          f"({plan_info['other_target']} from Other bucket [pool={plan_info['other_pool_size']}], "
          f"{plan_info['failed_target']} from classification failures [pool={plan_info['failed_pool_size']}])")
    print(f"Stratified across {len(taxonomy)} intents: {plan_info['stratified_target']}\n")
    print(f"{'Intent':<40} {'pool':>6} {'allocated':>10}")
    for t in taxonomy:
        name = t["name"]
        print(f"{name:<40} {plan_info['pool_sizes'][name]:>6} {plan_info['allocation'].get(name, 0):>10}")


def load_existing_labels():
    if not OUTPUT_PATH.exists():
        return []
    with OUTPUT_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def print_summary(taxonomy):
    labels = load_existing_labels()
    print(f"Labeled so far: {len(labels)} / {GOLDEN_SET_TARGET}\n")
    counts = {t["name"]: 0 for t in taxonomy}
    resolved_counts = {"yes": 0, "no": 0, "partial": 0}
    for rec in labels:
        counts[rec["label_intent"]] = counts.get(rec["label_intent"], 0) + 1
        resolved_counts[rec["label_resolved"]] = resolved_counts.get(rec["label_resolved"], 0) + 1
    print("Label distribution by intent:")
    for name, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {name}: {count}")
    print("\nResolved judgment:")
    for k, v in resolved_counts.items():
        print(f"  {k}: {v}")


def prompt_choice(prompt_text, options):
    print(prompt_text)
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("> ").strip().lower()
        if raw in ("q", "quit"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"Please enter a number 1-{len(options)}, or 'q' to quit.")


def label_session(taxonomy, threads_by_id):
    candidates, _ = build_sampling_plan(taxonomy, load_assignments())
    labeled_ids = {rec["thread_id"] for rec in load_existing_labels()}
    remaining = [c for c in candidates if c["thread_id"] not in labeled_ids]

    if not remaining:
        print("All sampled candidates are already labeled.")
        print_summary(taxonomy)
        return

    intent_names = [t["name"] for t in taxonomy]
    resolved_options = ["yes", "no", "partial"]

    print(f"Resuming: {len(labeled_ids)} already labeled, {len(remaining)} remaining "
          f"(target {GOLDEN_SET_TARGET}). Type 'q' at any prompt to save and quit.\n")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("a", encoding="utf-8") as out_f:
        for i, cand in enumerate(remaining, start=1):
            thread = threads_by_id.get(cand["thread_id"])
            if thread is None:
                continue

            print("=" * 70)
            print(f"[{len(labeled_ids) + 1}/{GOLDEN_SET_TARGET}] thread {cand['thread_id']} "
                  f"(sampled as: {cand['sample_reason']}, phase2 guess: {cand['intent']})")
            print("-" * 70)
            print(f"CUSTOMER:  {thread['customer_message']}")
            print(f"COMCASTCARES:  {thread['brand_reply']}")
            if thread.get("customer_followup"):
                print(f"CUSTOMER FOLLOW-UP:  {thread['customer_followup']}")
            print()

            intent = prompt_choice("What is the customer's actual intent?", intent_names)
            if intent is None:
                break

            resolved = prompt_choice("Does the historical reply look well-resolved?", resolved_options)
            if resolved is None:
                break

            notes = input("Notes (optional, Enter to skip): ").strip()

            record = {
                "thread_id": cand["thread_id"],
                "customer_message": thread["customer_message"],
                "brand_reply": thread["brand_reply"],
                "customer_followup": thread.get("customer_followup"),
                "sample_reason": cand["sample_reason"],
                "phase2_intent": cand["intent"],
                "label_intent": intent,
                "label_resolved": resolved,
                "label_notes": notes,
                "labeled_at": datetime.now(timezone.utc).isoformat(),
            }
            out_f.write(json.dumps(record) + "\n")
            out_f.flush()
            labeled_ids.add(cand["thread_id"])
            print()

    print("\nSession ended.\n")
    print_summary(taxonomy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="Print the sampling plan and exit")
    parser.add_argument("--summary", action="store_true", help="Print labeling progress and exit")
    args = parser.parse_args()

    for path in (THREADS_PATH, TAXONOMY_PATH, ASSIGNMENTS_PATH):
        if not path.exists():
            print(f"ERROR: {path} not found. Run earlier phase scripts first.")
            return

    taxonomy = load_taxonomy()

    if args.plan:
        _, plan_info = build_sampling_plan(taxonomy, load_assignments())
        print_plan(plan_info, taxonomy)
        return

    if args.summary:
        print_summary(taxonomy)
        return

    threads_by_id = load_threads_by_id()
    label_session(taxonomy, threads_by_id)


if __name__ == "__main__":
    main()
