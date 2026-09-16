# Human vs. LLM-Judge Agreement

15 examples scored by both the Groq judge and a human reviewer, blind to the judge's scores (see `src/human_judge_sample.py`).

| Dimension | Exact match | Within 1 point |
|---|---|---|
| Grounded in historical pattern (matches how @comcastcares actually resolves this) | 67% (n=15) | 93% (n=15) |
| Addresses the actual issue the customer raised | 7% (n=15) | 20% (n=15) |
| Appropriate tone (polite, professional, on-brand) | 47% (n=15) | 93% (n=15) |
