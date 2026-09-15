"""
Quick data-quality exploration of data/twcs.csv for brand selection.

For each candidate brand handle: counts outbound tweets, then reconstructs
a handful of sample (customer -> brand reply) threads so we can eyeball
data quality before committing to a brand.

Usage: python3 src/explore_brands.py
"""

import csv
from pathlib import Path

DATA_PATH = Path("data/twcs.csv")
REPORT_PATH = Path("reports/brand_exploration.md")

CANDIDATES = ["sprintcare", "AmericanAir", "British_Airways", "AskLyft", "comcastcares"]
TOP_N_BRANDS = 3
SAMPLE_THREADS = 10


def load_rows():
    with DATA_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_by_author(rows):
    counts = {brand: 0 for brand in CANDIDATES}
    for row in rows:
        author = row["author_id"]
        if author in counts:
            counts[author] += 1
    return counts


def build_thread(rows_by_id, brand_tweet):
    """Given a brand's reply tweet, walk back to the customer tweet it replies to."""
    parent_id = brand_tweet["in_response_to_tweet_id"]
    if not parent_id:
        return None
    customer_tweet = rows_by_id.get(parent_id)
    if customer_tweet is None or customer_tweet["inbound"] != "True":
        return None
    return customer_tweet, brand_tweet


def sample_threads(rows, rows_by_id, brand, n):
    threads = []
    for row in rows:
        if row["author_id"] != brand:
            continue
        thread = build_thread(rows_by_id, row)
        if thread:
            threads.append(thread)
        if len(threads) >= n:
            break
    return threads


def format_thread(customer_tweet, brand_tweet, brand):
    return (
        f"Customer (tweet {customer_tweet['tweet_id']}): {customer_tweet['text']}\n"
        f"{brand} (tweet {brand_tweet['tweet_id']}): {brand_tweet['text']}\n"
    )


def main():
    print(f"Loading {DATA_PATH} ...")
    rows = load_rows()
    print(f"Loaded {len(rows)} tweets\n")

    counts = count_by_author(rows)
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)

    print("Tweet counts by candidate brand:")
    for brand, count in ranked:
        print(f"  {brand}: {count}")
    print()

    top_brands = [brand for brand, _ in ranked[:TOP_N_BRANDS]]

    print("Indexing tweets by tweet_id for thread lookup ...")
    rows_by_id = {row["tweet_id"]: row for row in rows}

    report_lines = ["# Brand Exploration\n"]
    report_lines.append("## Tweet counts by candidate brand\n")
    for brand, count in ranked:
        report_lines.append(f"- {brand}: {count}")
    report_lines.append("")

    for brand in top_brands:
        print(f"\n=== Sample threads for {brand} ===\n")
        report_lines.append(f"## Sample threads: {brand}\n")

        threads = sample_threads(rows, rows_by_id, brand, SAMPLE_THREADS)
        for i, (customer_tweet, brand_tweet) in enumerate(threads, start=1):
            text = format_thread(customer_tweet, brand_tweet, brand)
            print(f"--- Thread {i} ---")
            print(text)
            report_lines.append(f"### Thread {i}\n")
            report_lines.append("```")
            report_lines.append(text.strip())
            report_lines.append("```\n")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nSaved thread samples to {REPORT_PATH}")


if __name__ == "__main__":
    main()
