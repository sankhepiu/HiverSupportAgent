# Golden Set: Sampling & Labeling Methodology

## What this is

200 hand-labeled (customer message → comcastcares reply [→ customer
follow-up]) threads, sampled from `data/comcastcares_threads.jsonl` and
labeled by hand using `src/label_golden_set.py`. Every label in
`eval/golden_set.jsonl` was assigned by a human reading the actual thread —
this tool does no automatic labeling.

## Why not pure random sampling

A uniform random sample of ~200 threads would be dominated by the most
common intents (Internet Performance, Service Outage, Escalation & Security
together account for ~45% of classified traffic — see
`reports/intent_taxonomy.md`) and would barely cover rare intents like
Equipment Issues (4.1%) or Account Management (4.6%). It would also be
almost entirely "easy" threads, since Phase 2's classification showed ~18%
of messages don't cleanly fit any of the 10 intents ("Other") and ~6.7%
failed classification outright — exactly the cases most likely to expose
weaknesses in a real classifier/RAG pipeline, and exactly the cases pure
random sampling underrepresents.

## Sampling strategy

Source pools come from `data/intent_assignments.jsonl` (Phase 2's per-thread
classification against the 10-intent taxonomy in `data/intent_taxonomy.json`):

1. **Stratified, proportional-with-oversampling (170 of 200 examples).**
   For each of the 10 intents, the number of examples pulled is a blend of
   its true share of the classified sample and an equal 1/10 share:

   `blended_share = 0.7 × proportional_share + 0.3 × uniform_share`

   The 0.7/0.3 blend keeps the set roughly tracking the real intent mix
   (so results generalize to production traffic) while ensuring the
   smallest intents still get a reasonable number of examples rather than
   1-2. Slot counts are apportioned via largest-remainder rounding and
   capped at each intent's available pool size. Actual allocation used
   (run `python3 src/label_golden_set.py --plan` to reproduce):

   | Intent | Pool size | Allocated |
   |---|---|---|
   | Service Outage | 210 | 27 |
   | Internet Performance | 213 | 27 |
   | Escalation & Security | 202 | 26 |
   | Billing Issues | 91 | 15 |
   | Streaming Content Issues | 82 | 14 |
   | Channel Issues | 81 | 13 |
   | Technical Support | 81 | 13 |
   | Service Availability & Scheduling | 66 | 12 |
   | Account Management | 64 | 12 |
   | Equipment Issues | 57 | 11 |

2. **Deliberately hard cases (30 of 200 examples).** Split proportionally
   between two pools that Phase 2 already flagged as difficult:
   - 21 from the **"Other" bucket** (252 available) — messages the
     classifier couldn't confidently place in any of the 10 intents.
   - 9 from **classification failures** (101 available) — messages where
     the classification LLM call returned malformed/truncated JSON and got
     no label at all.

   These are included on purpose so the golden set isn't all easy,
   well-separated examples — a classifier or RAG pipeline that only looks
   good on the "clean" 85% would otherwise pass every check.

Both stages sample without replacement using a fixed seed
(`SAMPLING_SEED = 20260916` in `src/label_golden_set.py`), and the final
candidate order is shuffled with that same seeded RNG so labeling isn't
done in intent-grouped blocks (avoids anchoring bias while labeling).
Re-running `--plan` reproduces the identical candidate list.

## Labeling procedure

For each sampled thread, the labeler (project owner) is shown the customer
message, comcastcares's historical reply, and the customer's follow-up
(if the thread continued), then records:

- **`label_intent`** — the customer's actual intent, chosen from the same
  10-item taxonomy Phase 2 produced (numbered menu, no free text — keeps
  labels directly comparable to the classifier's own output space).
- **`label_resolved`** — a quick judgment call on whether the historical
  reply actually resolved the issue (`yes` / `no` / `partial`), used later
  to sanity-check what "grounding in resolved threads" should mean for RAG.
- **`label_notes`** — optional free text for anything the two structured
  fields don't capture (ambiguity, sarcasm, multiple intents, etc.).

Each thread's `phase2_intent` (the classifier's original guess, or `null`
for classification failures) and `sample_reason` (`stratified` /
`other_bucket` / `classification_failure`) are carried into the label
record automatically, so `eval/golden_set.jsonl` doubles as ground truth for
measuring Phase 2's classifier accuracy, not just a fresh eval set.

Labels are appended to `eval/golden_set.jsonl` one line at a time as soon as
they're entered (not buffered), so an interrupted session loses nothing —
re-running `src/label_golden_set.py` skips threads whose `thread_id` is
already in the output file and resumes from there.
