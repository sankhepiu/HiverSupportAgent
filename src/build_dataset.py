"""
Phase 1: reconstruct and clean (customer -> comcastcares reply) threads
from data/twcs.csv into data/comcastcares_threads.jsonl.

No pandas — csv module only, consistent with explore_brands.py.

Usage: python3 src/build_dataset.py
"""

import csv
import json
import re
from pathlib import Path

DATA_PATH = Path("data/twcs.csv")
OUTPUT_PATH = Path("data/comcastcares_threads.jsonl")
DROPPED_LOG_PATH = Path("reports/dropped_deflections.jsonl")

BRAND = "comcastcares"

URL_RE = re.compile(r"https?://\S+|pic\.twitter\.com/\S+")
MENTION_RE = re.compile(r"@(\w+)")
WHITESPACE_RE = re.compile(r"\s+")

# A mention is kept if it's alphabetic (a real handle/brand name carrying
# semantic content, e.g. "@comcastcares" or a customer naming another
# company). Purely numeric mentions are the dataset's anonymized user ids
# and carry no information, so they're stripped as noise.
def clean_text(text):
    text = URL_RE.sub("", text)
    text = MENTION_RE.sub(lambda m: m.group(0) if not m.group(1).isdigit() else "", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


# Heuristic: a reply counts as a "pure deflection" only if it both (a) asks
# the customer to DM/message them AND (b) has almost nothing left once you
# strip greetings/apologies/boilerplate — i.e. it offers no troubleshooting
# detail, acknowledgment of specifics, or information beyond "contact us
# privately". A reply that deflects to DM *and* gives real content (an
# apology with specifics, a partial diagnosis, an outage acknowledgment)
# is kept.
DEFLECTION_PHRASES = [
    "dm us", "dm you", "dm'd", "send us a dm", "send you a dm",
    "direct message", "private message", "message us", "pm us",
]
BOILERPLATE_PHRASES = [
    "i'm sorry", "i am sorry", "sorry to hear", "sorry about that",
    "so we can", "so that we can", "so i can", "we can", "we'd",
    "we would", "like to help", "assist you", "look into this",
    "look into that", "further assist", "happy to help", "thank you",
    "thanks",
]
FILLER_WORDS = {
    "i", "im", "a", "an", "the", "to", "so", "that", "we", "you", "your",
    "us", "our", "this", "and", "for", "can", "will", "would", "like",
    "help", "assist", "further", "more", "please", "hi", "hello", "hey",
}
DEFLECTION_WORD_THRESHOLD = 4


def is_pure_deflection(cleaned_reply):
    text = cleaned_reply.lower()
    if not any(phrase in text for phrase in DEFLECTION_PHRASES):
        return False
    stripped = text
    for phrase in BOILERPLATE_PHRASES:
        stripped = stripped.replace(phrase, "")
    for phrase in DEFLECTION_PHRASES:
        stripped = stripped.replace(phrase, "")
    words = re.findall(r"[a-z0-9]+", stripped)
    remaining = [w for w in words if w not in FILLER_WORDS]
    return len(remaining) <= DEFLECTION_WORD_THRESHOLD


def load_rows():
    with DATA_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_customer_followup(rows_by_id, brand_reply):
    response_ids = brand_reply["response_tweet_id"]
    if not response_ids:
        return None
    for rid in response_ids.split(","):
        candidate = rows_by_id.get(rid.strip())
        if candidate is not None and candidate["inbound"] == "True":
            return candidate
    return None


def main():
    print(f"Loading {DATA_PATH} ...")
    rows = load_rows()
    rows_by_id = {row["tweet_id"]: row for row in rows}
    print(f"Loaded {len(rows)} tweets\n")

    brand_replies = [row for row in rows if row["author_id"] == BRAND]
    print(f"Found {len(brand_replies)} tweets from {BRAND}")

    total_threads = 0
    no_parent = 0
    dropped_deflection = 0
    kept = 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DROPPED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as out_f, \
         DROPPED_LOG_PATH.open("w", encoding="utf-8") as log_f:

        for brand_reply in brand_replies:
            parent_id = brand_reply["in_response_to_tweet_id"]
            if not parent_id:
                no_parent += 1
                continue

            customer_tweet = rows_by_id.get(parent_id)
            if customer_tweet is None or customer_tweet["inbound"] != "True":
                no_parent += 1
                continue

            total_threads += 1

            cleaned_customer_msg = clean_text(customer_tweet["text"])
            cleaned_reply = clean_text(brand_reply["text"])

            if is_pure_deflection(cleaned_reply):
                dropped_deflection += 1
                log_f.write(json.dumps({
                    "thread_id": f"{customer_tweet['tweet_id']}_{brand_reply['tweet_id']}",
                    "customer_message": cleaned_customer_msg,
                    "brand_reply": cleaned_reply,
                    "reason": "pure_deflection",
                }) + "\n")
                continue

            followup_tweet = find_customer_followup(rows_by_id, brand_reply)
            cleaned_followup = clean_text(followup_tweet["text"]) if followup_tweet else None

            record = {
                "thread_id": f"{customer_tweet['tweet_id']}_{brand_reply['tweet_id']}",
                "customer_message": cleaned_customer_msg,
                "brand_reply": cleaned_reply,
                "customer_followup": cleaned_followup,
            }
            out_f.write(json.dumps(record) + "\n")
            kept += 1

    print("\nSummary:")
    print(f"  Total {BRAND} reply tweets: {len(brand_replies)}")
    print(f"  Skipped (no linked customer message): {no_parent}")
    print(f"  Threads found (reply linked to a customer message): {total_threads}")
    print(f"  Dropped as pure deflection: {dropped_deflection}")
    print(f"  Kept after cleaning: {kept}")
    print(f"\nSaved cleaned dataset to {OUTPUT_PATH}")
    print(f"Saved dropped-deflection log to {DROPPED_LOG_PATH}")


if __name__ == "__main__":
    main()
