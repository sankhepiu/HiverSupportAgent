# Project: Hiver SDE Intern Take-Home — comcastcares Support Agent

## What this is
An AI support agent for Comcast's Twitter support handle (@comcastcares),
built from the Kaggle "Customer Support on Twitter" dataset
(thoughtvector/customer-support-on-twitter). This is a take-home assignment
for a Hiver SDE Intern application.

## Brand choice
comcastcares — chosen after comparing tweet volume and thread quality against
AmericanAir and British_Airways (see reports/brand_exploration.md). Comcast's
replies tend to be substantive in-thread (troubleshooting/billing resolutions)
rather than deflecting to DMs, which matters because replies must be
grounded in historically resolved threads.

## What the agent must do
1. Classify each incoming customer message into a small set of intents
   (derived from the data itself, not hand-guessed — target 6-10 intents).
2. Draft a reply grounded in how @comcastcares has historically resolved
   similar issues (RAG over past resolved threads).
3. Decide auto-handle vs. escalate-to-human, with a stated reason.

## Tech choices
- Python, standard library / lightweight deps preferred over heavy frameworks
- LLM: Groq (via its API) for classification, reply drafting, and the
  LLM-as-judge eval — chosen for inference speed and generous free-tier
  rate limits given the volume of calls this pipeline needs (classification
  across sampled tweets, reply drafting, and judging the golden set).
  If judge quality on nuanced groundedness/quality checks turns out weak,
  revisit using a stronger model just for the judge step — note that as a
  decision if it happens.
- No pandas installed yet — scripts so far use the built-in csv module

## Repo structure
- data/       — twcs.csv (gitignored, not committed) + any derived files
- src/        — pipeline scripts
- eval/       — golden set, eval harness, LLM-judge code
- notebooks/  — exploratory work
- reports/    — brand_exploration.md, final report, failure analysis

## Deliverables (from the assignment PDF)
1. Runnable repo, README reproducible in under 15 minutes
2. Golden eval set: 150-250 hand-labelled examples, with sampling/labeling
   methodology noted
3. Evaluation harness: automated metrics + LLM-as-judge rubric for reply
   quality, with evidence of judge-vs-human agreement
4. Report (max 6 pages): problem framing, results vs. 2 baselines (trivial +
   simple), top 5 failure modes with real examples, "what's misleading about
   my headline number" section, next-week plan
5. Decision log: 10-15 non-obvious decisions with reasoning

## Working conventions
- Work one pipeline phase at a time, don't build everything in one session
- Commit after every working phase with a descriptive message
- Subsample the dataset (full 3M rows not expected or needed)
- Cache LLM API calls to avoid burning credits/time on repeated runs