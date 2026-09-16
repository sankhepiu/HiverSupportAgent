# Classifier Evaluation vs. Golden Set

Three classifiers evaluated against all 150 hand-labeled examples in `eval/golden_set.jsonl`: a trivial majority-class baseline, a keyword/rule-based baseline, and the main Groq few-shot classifier.

## Accuracy

| Classifier | Accuracy |
|---|---|
| Trivial | 17.3% |
| Simple | 42.0% |
| Main | 56.0% |

## Per-intent F1

| Intent | Support (n) | Trivial | Simple | Main |
|---|---|---|---|---|
| Equipment Issues | 12 | 0.00 | 0.30 | 0.40 |
| Service Outage | 26 | 0.30 | 0.39 | 0.53 |
| Streaming Content Issues | 10 | 0.00 | 0.69 | 0.84 |
| Channel Issues | 13 | 0.00 | 0.64 | 0.73 |
| Internet Performance | 24 | 0.00 | 0.67 | 0.82 |
| Billing Issues | 19 | 0.00 | 0.44 | 0.56 |
| Account Management | 2 | 0.00 | 0.00 | 0.20 |
| Technical Support | 21 | 0.00 | 0.00 | 0.07 |
| Service Availability & Scheduling | 6 | 0.00 | 0.00 | 0.71 |
| Escalation & Security | 17 | 0.00 | 0.20 | 0.53 |

## Caveat: small-support intents

The golden set's label distribution mirrors the underlying data and is naturally imbalanced (see `reports/intent_taxonomy.md`). Intents with fewer than 10 labeled examples in the golden set (**Account Management, Service Availability & Scheduling**) have F1 scores computed over a very small sample — a single misclassification can swing F1 by 10-50 points. Treat per-intent F1 for these as directional, not precise, and prefer the accuracy/macro comparisons and confusion patterns over any single rare-intent F1 number when judging the main classifier.

## Notes

- The main classifier's few-shot examples were drawn from Phase 2's 1500-message sample, explicitly excluding any thread that appears in the golden set, to avoid test-set leakage.
- The main classifier may predict "Other" (not one of the 10 intents) for messages it can't confidently place; since every golden-set label is one of the 10 intents, an "Other" prediction always counts as a miss in this evaluation.
