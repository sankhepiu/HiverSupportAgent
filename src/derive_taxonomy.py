"""
Phase 2: derive an intent taxonomy from customer_message values in
data/comcastcares_threads.jsonl using the Groq API, rather than hand-picking
categories.

Three LLM stages, all batched (never one call per message):
  A. Open coding  - propose candidate intent labels for batches of messages.
  B. Consolidate  - merge all candidate labels into a final 6-10 taxonomy.
  C. Anchor       - classify the sample against the final taxonomy so the
                    report can show real example messages + a distribution,
                    not hallucinated ones.

Groq responses are cached to .cache/groq_cache.json keyed by request content,
so re-running the script costs no additional API calls unless prompts change.

Requires GROQ_API_KEY, either in the environment or a .env file
(GROQ_API_KEY=...) in the repo root.

Usage: python3 src/derive_taxonomy.py
"""

import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

INPUT_PATH = Path("data/comcastcares_threads.jsonl")
CACHE_PATH = Path(".cache/groq_cache.json")
REPORT_PATH = Path("reports/intent_taxonomy.md")
TAXONOMY_JSON_PATH = Path("data/intent_taxonomy.json")
ASSIGNMENTS_PATH = Path("data/intent_assignments.jsonl")

SAMPLE_SIZE = 1500
RANDOM_SEED = 42
OPEN_CODING_BATCH_SIZE = 50
CLASSIFY_BATCH_SIZE = 50
CONSOLIDATION_CHUNK_SIZE = 40
MAX_RUNNING_TAXONOMY_SIZE = 15
# gpt-oss-20b: this account's free tier caps it at 8000 tokens/minute, and
# gpt-oss-120b shares its (much lower) budget with the "compound" models, so
# 20b + low reasoning effort is what actually fits without constant 429s.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def load_api_key():
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_cache():
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def cache_key(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def call_groq(api_key, cache, messages, temperature=0.2):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "reasoning_effort": REASONING_EFFORT,
    }
    key = cache_key(payload)
    if key in cache:
        return cache[key]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    attempts = 5
    for attempt in range(attempts):
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429 and attempt < attempts - 1:
            time.sleep(8 * (attempt + 1))
            continue
        resp.raise_for_status()
        break

    content = resp.json()["choices"][0]["message"]["content"]
    cache[key] = content
    save_cache(cache)
    return content


def extract_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    start = min((i for i in (text.find("["), text.find("{")) if i != -1), default=-1)
    end = max(text.rfind("]"), text.rfind("}"))
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in response: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def load_sample():
    items = []
    with INPUT_PATH.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            msg = row.get("customer_message")
            if msg:
                items.append({"thread_id": row["thread_id"], "message": msg})
    random.seed(RANDOM_SEED)
    return random.sample(items, min(SAMPLE_SIZE, len(items)))


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


OPEN_CODING_PROMPT = """You are analyzing customer support messages sent to Comcast (@comcastcares) on Twitter.

Below is a numbered list of {n} customer messages. Identify the distinct underlying support \
intents/issue types present in this batch (e.g. billing dispute, service outage, equipment \
return, technical troubleshooting). Propose a short label (2-4 words) for each distinct intent \
you see, with a one-sentence definition, and list which message numbers belong to it.

Return ONLY a JSON array, no prose, in this exact form:
[{{"label": "...", "definition": "...", "example_indices": [1, 4, 7]}}]

Messages:
{numbered}
"""


def run_open_coding(api_key, cache, sample):
    candidates = []
    batches = list(batched(sample, OPEN_CODING_BATCH_SIZE))
    for i, batch in enumerate(batches, start=1):
        print(f"  Open coding batch {i}/{len(batches)} ({len(batch)} messages) ...")
        numbered = "\n".join(f"{j}. {item['message']}" for j, item in enumerate(batch, start=1))
        prompt = OPEN_CODING_PROMPT.format(n=len(batch), numbered=numbered)
        content = call_groq(api_key, cache, [{"role": "user", "content": prompt}])
        try:
            proposals = extract_json(content)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"    WARNING: skipping malformed batch response ({e})")
            continue
        for p in proposals:
            examples = [batch[idx - 1]["message"] for idx in p.get("example_indices", []) if 1 <= idx <= len(batch)]
            candidates.append({
                "label": p.get("label", "").strip(),
                "definition": p.get("definition", "").strip(),
                "examples": examples[:2],
            })
    return candidates


# Consolidation is map-reduce: a single call holding all ~150-600 raw
# candidate labels from stage A would need more tokens than this account's
# per-minute budget allows in one request. So candidates are folded into a
# running taxonomy in small chunks, then narrowed to the final 6-10 once at
# the end, keeping every call's token footprint small and bounded.
FOLD_PROMPT = """You are incrementally building a customer-support intent taxonomy for Comcast \
(@comcastcares) Twitter support, by merging newly observed candidate intents into a running \
taxonomy.

Current running taxonomy ({n_current} entries):
{current_list}

New candidate intents observed in more customer messages ({n_new} candidates):
{new_list}

Produce an UPDATED running taxonomy: merge new candidates into existing entries where they \
overlap conceptually, add new entries only for genuinely new/distinct concepts, and keep the \
total number of entries at {max_size} or fewer by folding narrow ones into a broader related \
entry. Definitions should stay one sentence.

Return ONLY a JSON array, no prose, in this exact form:
[{{"name": "...", "definition": "..."}}]
"""

NARROW_PROMPT = """Below is a running customer-support intent taxonomy for Comcast \
(@comcastcares) with {n} entries, some of which may still overlap or be too narrow.

{current_list}

Consolidate this into a FINAL set of 6 to 10 distinct, non-overlapping intents that together \
cover this space. Merge duplicates/near-duplicates, drop overly narrow entries by folding them \
into a broader related intent, and make sure every final intent is clearly distinguishable from \
the others.

Return ONLY a JSON array, no prose, in this exact form:
[{{"name": "...", "definition": "..."}}]
"""


def run_consolidation(api_key, cache, candidates):
    running = []
    chunks = list(batched(candidates, CONSOLIDATION_CHUNK_SIZE))
    for i, chunk in enumerate(chunks, start=1):
        print(f"  Folding candidate chunk {i}/{len(chunks)} into running taxonomy ...")
        current_list = "\n".join(f"- {t['name']}: {t['definition']}" for t in running) or "(none yet)"
        new_list = "\n".join(f"- {c['label']}: {c['definition']}" for c in chunk)
        prompt = FOLD_PROMPT.format(
            n_current=len(running), current_list=current_list,
            n_new=len(chunk), new_list=new_list, max_size=MAX_RUNNING_TAXONOMY_SIZE,
        )
        content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=0.1)
        try:
            running = extract_json(content)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"    WARNING: skipping malformed fold response ({e}), keeping previous running taxonomy")

    print(f"  Narrowing {len(running)} running entries into a final 6-10 taxonomy ...")
    current_list = "\n".join(f"- {t['name']}: {t['definition']}" for t in running)
    prompt = NARROW_PROMPT.format(n=len(running), current_list=current_list)
    content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=0.1)
    return extract_json(content)


CLASSIFY_PROMPT = """Classify each of the following customer support messages into exactly one \
of these intents:

{taxonomy_list}

Return ONLY a JSON array of length {n}, in the same order as the messages, containing just the \
intent name for each message. If a message doesn't clearly fit any intent, use "Other".

Messages:
{numbered}
"""


def run_classification(api_key, cache, sample, taxonomy):
    taxonomy_list = "\n".join(f"- {t['name']}: {t['definition']}" for t in taxonomy)
    assignments = []
    failed_count = 0
    batches = list(batched(sample, CLASSIFY_BATCH_SIZE))
    for i, batch in enumerate(batches, start=1):
        print(f"  Classifying batch {i}/{len(batches)} ({len(batch)} messages) ...")
        numbered = "\n".join(f"{j}. {item['message']}" for j, item in enumerate(batch, start=1))
        prompt = CLASSIFY_PROMPT.format(taxonomy_list=taxonomy_list, n=len(batch), numbered=numbered)
        content = call_groq(api_key, cache, [{"role": "user", "content": prompt}], temperature=0.0)
        try:
            labels = extract_json(content)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"    WARNING: malformed batch response ({e}); marking batch as classification failures")
            labels = []

        # Never silently drop messages: pad/truncate to the batch length so
        # every sampled message gets counted, and track how many needed it.
        if len(labels) < len(batch):
            failed_count += len(batch) - len(labels)
            labels = labels + ["__CLASSIFICATION_FAILED__"] * (len(batch) - len(labels))
        elif len(labels) > len(batch):
            labels = labels[:len(batch)]

        for item, label in zip(batch, labels):
            assignments.append((item["thread_id"], item["message"], label))
    return assignments, failed_count


FAILED_SENTINEL = "__CLASSIFICATION_FAILED__"


def build_report(taxonomy, assignments, sample_size, failed_count):
    valid_names = {t["name"] for t in taxonomy}
    examples_by_name = {t["name"]: [] for t in taxonomy}
    counts = {t["name"]: 0 for t in taxonomy}
    counts["Other"] = 0

    for _thread_id, msg, label in assignments:
        if label == FAILED_SENTINEL:
            continue
        if label not in valid_names:
            counts["Other"] += 1
            continue
        counts[label] += 1
        if len(examples_by_name[label]) < 3 and msg not in examples_by_name[label]:
            examples_by_name[label].append(msg)

    classified = sample_size - failed_count

    lines = ["# Intent Taxonomy — comcastcares Customer Messages\n"]
    lines.append(
        f"Derived via LLM-assisted open coding over a random sample of {sample_size} "
        f"customer messages (seed={RANDOM_SEED}) from `{INPUT_PATH}`, using Groq model "
        f"`{MODEL}`. Candidate labels were proposed in batches of {OPEN_CODING_BATCH_SIZE}, "
        f"then consolidated into the {len(taxonomy)} intents below.\n"
    )
    if failed_count:
        lines.append(
            f"Note: {failed_count} of {sample_size} sampled messages ({100 * failed_count / sample_size:.1f}%) "
            f"got no classification in the anchoring pass due to malformed/truncated LLM responses, and are "
            f"excluded from the distribution below (not counted as \"Other\" — that bucket is only messages "
            f"the model classified but judged didn't fit any intent).\n"
        )
    lines.append(f"## Distribution over the {classified} successfully classified messages\n")
    for name, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        pct = 100 * count / classified if classified else 0
        lines.append(f"- {name}: {count} ({pct:.1f}%)")
    lines.append("")

    for t in taxonomy:
        lines.append(f"## {t['name']}\n")
        lines.append(f"{t['definition']}\n")
        lines.append("Examples:")
        for ex in examples_by_name[t["name"]]:
            lines.append(f"- \"{ex}\"")
        lines.append("")

    return "\n".join(lines)


def save_assignments(assignments):
    ASSIGNMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ASSIGNMENTS_PATH.open("w", encoding="utf-8") as f:
        for thread_id, msg, label in assignments:
            failed = label == FAILED_SENTINEL
            f.write(json.dumps({
                "thread_id": thread_id,
                "customer_message": msg,
                "intent": None if failed else label,
                "failed": failed,
            }) + "\n")


def main():
    api_key = load_api_key()
    if not api_key:
        print(
            "ERROR: GROQ_API_KEY not found.\n"
            "Set it in your environment (export GROQ_API_KEY=...) or add a .env file\n"
            "in the repo root containing GROQ_API_KEY=... before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run src/build_dataset.py first.", file=sys.stderr)
        sys.exit(1)

    cache = load_cache()

    print(f"Loading sample from {INPUT_PATH} (seed={RANDOM_SEED}) ...")
    sample = load_sample()
    print(f"Sampled {len(sample)} customer messages\n")

    print("Stage A: open coding ...")
    candidates = run_open_coding(api_key, cache, sample)
    print(f"  {len(candidates)} candidate labels proposed\n")

    print("Stage B: consolidation ...")
    taxonomy = run_consolidation(api_key, cache, candidates)
    print(f"  Consolidated into {len(taxonomy)} final intents\n")

    print("Stage C: anchoring examples via classification ...")
    assignments, failed_count = run_classification(api_key, cache, sample, taxonomy)
    if failed_count:
        print(f"  WARNING: {failed_count}/{len(sample)} messages had no usable classification\n")
    else:
        print()

    report = build_report(taxonomy, assignments, len(sample), failed_count)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    TAXONOMY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    TAXONOMY_JSON_PATH.write_text(json.dumps(taxonomy, indent=2), encoding="utf-8")

    save_assignments(assignments)

    print(report)
    print(f"\nSaved taxonomy to {REPORT_PATH}")
    print(f"Saved machine-readable taxonomy to {TAXONOMY_JSON_PATH}")
    print(f"Saved per-thread intent assignments to {ASSIGNMENTS_PATH}")


if __name__ == "__main__":
    main()
