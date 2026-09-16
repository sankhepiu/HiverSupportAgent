# HiverSupportAgent

## Reproduction

Run the pipeline scripts in order (each is idempotent and reads the previous phase's output):

```
python3 src/build_dataset.py
python3 src/derive_taxonomy.py
python3 src/label_golden_set.py       # interactive; skip if eval/golden_set.jsonl already has labels
python3 src/classify_intent.py
python3 src/generate_reply.py
python3 src/eval_harness.py
python3 src/human_judge_sample.py     # interactive; skip if eval/human_judge_scores.jsonl already has scores
python3 src/eval_harness.py --agreement
```

`.cache/groq_cache.json` is committed to the repo specifically so this whole pipeline reproduces instantly from cached Groq responses in well under 15 minutes; running from scratch without it will re-issue every LLM call and hit Groq's free-tier rate limits, as documented for Phase 6 in `reports/decision_log.md` (the judge run there had to be capped at 20/35 examples for exactly this reason).

## Report

### Problem Framing

This is an AI support agent for Comcast's Twitter handle, @comcastcares, built on the Kaggle "Customer Support on Twitter" dataset. "Good" here means three things: (1) correctly routing an incoming customer message to the right issue category, (2) drafting a reply that's grounded in how @comcastcares has actually resolved similar issues historically — not generic customer-service boilerplate — and (3) escalating to a human when the system is uncertain, with a stated reason rather than a bare label.

What was deliberately **not** built:
- **No multi-turn conversation handling** beyond what's reconstructed from the data itself — each example is (customer message → brand reply → at most one customer follow-up). No arbitrary-length back-and-forth.
- **No live deployment.** Everything here runs as offline batch scripts against a static dataset; there's no Twitter API integration, queueing, or real dispatch of replies.
- **No handling of DM-only resolutions.** A large share of @comcastcares's real resolution work happens after the customer is asked to move to a DM, and that content isn't in the dataset at all (see "What's misleading," below). The system can only ground on the public back-and-forth, not the actual fix.
- **No multi-intent handling.** Each message gets exactly one of 10 taxonomy intents, even though real messages sometimes raise more than one issue.

### Results vs. Baselines

Three classifiers evaluated against all 150 hand-labeled golden-set examples (`reports/classifier_eval.md`):

| Classifier | Accuracy | Why |
|---|---|---|
| Trivial | 17.3% | Always predicts the golden set's actual majority intent (Service Outage, 26/150) — the floor any real classifier must clear. |
| Simple | 42.0% | Keyword/rule matching using terms derived from each intent's taxonomy definition — catches obvious vocabulary (e.g. "outage", "bill", "channel") but has no way to resolve overlap between intents that share vocabulary. |
| Main | 56.0% | Groq few-shot classification using the taxonomy definitions plus real historical examples per intent. Best of the three, but still wrong on 44% of messages, and unevenly so — Streaming Content Issues F1 is 0.84 while Technical Support F1 is 0.07 despite a comparable 21-example support. |

### Failure Analysis: Top 5 Failure Modes

**1. Hallucinated specifics under weak/no grounding.** In thread `2864317_2864315`, the customer asked "Which IR extender works for the dvr?" — the retrieved grounding examples were all about an unrelated DVR-app feature removal, and the draft fabricated a specific product: *"the Xfinity IR Extender (model #XG-IR-EXT)"*. In thread `2962208_2962207`, asked about a one-month data-plan upgrade, the draft fabricated a contact number: *"call 1‑800‑CONFORT for a quick upgrade"* — not present in any retrieved example and not a real Comcast number. Both hallucinations still scored well on the judge's "grounded" and "tone" dimensions, since surface style matched the brand voice even though the content was invented.

**2. Low "addresses the actual issue" performance despite high tone/grounding scores.** The LLM judge averaged 4.45/5 on "grounded" and 4.90/5 on "tone" but only 3.95/5 on "addresses the actual issue" (`reports/judge_scores.md`, n=20). Most drafts, when they don't hallucinate, are well-toned, stylistically on-brand DM-deflections that don't substantively solve the customer's problem — mirroring the brand's own real historical pattern (see failure mode 5).

**3. Retrieval pulling topically mismatched historical examples.** In thread `1380678_1380677`, the customer's actual issue is a billing hold ("Bill has been paid for 10 days and still has a 'hold'"), blocking an HD add-on. The classifier mislabeled it "Service Availability & Scheduling" (human label: "Channel Issues"), so retrieval pulled three grounding examples all about delayed technician visits — and the draft reply promised to "get a tech scheduled ASAP," entirely orthogonal to a billing hold.

**4. Tone-deafness to specific complaints.** In thread `1531610_1531609`, the customer wrote "I cannot reach anyone over the phone and online chat is not helping. Held for 25 min" and asked for a supervisor callback — the draft replied "Please DM me your full account address and I'll connect you with a supervisor right away," asking for yet another contact round-trip through the exact channel type the customer just said wasn't working. In thread `2074098_2074097`, the customer had already called four times ("on the phone with for almost an hour and the 2 month long problem cant be fixed") — the draft still opened with "Please DM us your Xfinity ID and the exact issue," asking them to repeat information already given.

**5. Deflection-heavy training data.** Only 197 of 32,921 candidate threads were dropped in Phase 1 as "pure deflection" (nothing but a DM ask). That undercounts the real rate: of the 32,724 threads actually kept, 23,360 (71.4%) still contain a "DM us"/"direct message" ask somewhere in the reply — the real fix is deferred off-platform even in threads that "passed" cleaning. The golden set's own human judgments confirm this directly: only 24/150 (16.0%) of real historical replies were judged actually resolved, 105/150 (70.0%) were judged not resolved, 21/150 (14.0%) partial. Since the retrieval pool and few-shot examples are drawn from this same corpus, the system has learned deflection-to-DM as the dominant "successful" pattern — because that is the dominant pattern in its ground truth.

### What's Misleading About My Headline Number

- **The 56% main classifier accuracy** is measured against a golden set where every message was forced into one of 10 fixed intents by the human labeler (the labeling tool had no "Other" option). But Phase 2's own classification found 18.0% of a comparable sample (252/1399) doesn't cleanly fit any intent, plus 6.7% (101/1500) where classification failed outright — meaning some fraction of the main classifier's "errors" are on messages that are genuinely ambiguous, not classifier failure. 56% understates how well the classifier does on the clearly-resolvable subset, and overstates confidence on the inherently fuzzy one.
- **The 32/35 (91%) auto-handle rate** looks strong, but the escalation rule (`src/generate_reply.py`) is a simple score gated mainly on the classifier's self-reported confidence and whether *any* grounding examples were retrieved (plus a small bump for two intents flagged as sensitive). It doesn't weigh retrieval *relevance* (the mismatched billing-hold case above had 3 retrieved examples and "high" confidence — the same signal a good match would produce), hallucination risk, or the customer's own signaled frustration. A more conservative production system — especially one that had seen the two confirmed hallucinations above — would escalate meaningfully more often than 3/35.
- **The LLM judge is unreliable on exactly the dimension that matters most.** Checked against a blind human re-score of a 15-example overlap (`reports/judge_agreement.md`), the judge agrees with the human 67% exactly / 93% within one point on "grounded," and 47%/93% on "tone" — but only **7% exactly / 20% within one point** on "addresses the actual issue." The judge's 3.95/5 average on that dimension should be read as close to noise, not signal, while its surface-level style scores (tone, stylistic grounding) are comparatively trustworthy.
- **The grounding data is smaller and weaker than the raw thread count implies.** 197 threads were dropped in Phase 1 as pure deflections — but per failure mode 5, 71.4% of the remaining 32,724 kept threads are themselves also substantively deflections, with the real resolution happening off-platform in DMs this dataset never captured. In practice, "grounded in a historically resolved thread" most often means "grounded in a historical deflection to DM," not an actual fix.
- **4.2% of kept threads (1,385/32,724) are truncated multi-part reply fragments** — Comcast originally split some replies across two tweets, and only the second half survived thread reconstruction (e.g. a kept reply reading only "address, and phone number so I can assist further with this issue. -KW", with no visible first half). This was a known, deliberate choice to leave these in rather than build a heuristic filter for them, so a small slice of the grounding pool and downstream evaluation includes reply text that reads as a non-sequitur out of context.

### What I'd Do Next With One More Week

- Build actual DM-content access, or a better proxy for real resolution vs. deflection — this is the core grounding-quality bottleneck behind every other failure mode above.
- Redesign the escalation logic to weigh more risk signals beyond confidence + retrieval-found: retrieval-similarity thresholds (not just count>0), a lightweight hallucination check (a specific fact — phone number, model number, dollar amount — absent from every retrieved example), and the customer's own frustration/repeated-contact signals.
- Add a hallucination-detection guardrail given the two confirmed fabrication cases found in human review (threads `2864317_2864315` and `2962208_2962207`) — e.g. flag any digit sequence or model-number-shaped token in a draft that doesn't appear in its retrieved grounding examples.
- Expand the golden set beyond 150 examples, especially for rare intents — Account Management has only 2 labeled examples and Service Availability & Scheduling only 6, making their individual F1 scores close to meaningless.
- Investigate and improve retrieval quality for topically mismatched cases like thread `1380678_1380677` — the current TF-IDF retrieval has no relevance floor, so a misclassification cascades directly into fetching entirely wrong grounding examples.