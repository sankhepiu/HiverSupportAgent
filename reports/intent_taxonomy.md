# Intent Taxonomy — comcastcares Customer Messages

Derived via LLM-assisted open coding over a random sample of 1500 customer messages (seed=42) from `data/comcastcares_threads.jsonl`, using Groq model `openai/gpt-oss-20b`. Candidate labels were proposed in batches of 50, then consolidated into the 10 intents below.

Note: 101 of 1500 sampled messages (6.7%) got no classification in the anchoring pass due to malformed/truncated LLM responses, and are excluded from the distribution below (not counted as "Other" — that bucket is only messages the model classified but judged didn't fit any intent).

## Distribution over the 1399 successfully classified messages

- Other: 252 (18.0%)
- Internet Performance: 213 (15.2%)
- Service Outage: 210 (15.0%)
- Escalation & Security: 202 (14.4%)
- Billing Issues: 91 (6.5%)
- Streaming Content Issues: 82 (5.9%)
- Channel Issues: 81 (5.8%)
- Technical Support: 81 (5.8%)
- Service Availability & Scheduling: 66 (4.7%)
- Account Management: 64 (4.6%)
- Equipment Issues: 57 (4.1%)

## Equipment Issues

Customer requests related to returned, rented, reset, malfunctioning, or incorrectly installed equipment such as set‑top boxes, routers, gateways, or modems, including removal or return.

Examples:
- "@ComcastCares #mobile_Care please remove returned box from my account"
- "I can't believe that CMT is part of a sports package with . A package that I definitely don't need."
- "@comcastcares Techs need to stop lying to people trying to get people to rent your devices we don’t want!"

## Service Outage

Customer reports loss or interruption of TV, internet, or cable service, including widespread or localized outages and requests for status updates.

Examples:
- "Once again. is down. This is why we must break up monopolies and actually INVEST in quality internet infrastructure."
- "@comcastcares Everything is down bruh"
- "@ComcastCares #mobile_Care cable outage South Boston, Ma"

## Streaming Content Issues

Customer cannot access on‑demand, streaming apps, or specific content, including missing episodes, licensing restrictions, or live streaming app access.

Examples:
- "@comcastcares oh nvm i guess its just in the show on the on demand part. it just stays at 12 seconds and doesnt go away so i guess i cant watch the show GEE THANKS COMCAST"
- "just found out via a call you guys removed the record function from the Xfinity apps. Not cool Comcast not cool!!!"
- "So I’m literally forced to watch an empty racetrack without racing because &amp; @comcastcares are the dumbest fuckers this side of Trump #GoDawgs"

## Channel Issues

Customer cannot view a channel, has problems with channel lineup, HD quality, or package changes, including cable TV or streaming issues.

Examples:
- "@comcastcares how do we get espn3?"
- "thanks for ruining my Sunday again with only one game on at noon in Nashville"
- "@comcastcares Can you tell me why I haven’t had access to a channel I pay for all night?"

## Internet Performance

Customer reports slow, inconsistent, or unreliable internet speeds, connectivity drops, data throttling, data caps, or locked‑out Wi‑Fi.

Examples:
- "Comcast's connection keeps dropping every 30 min and I keep having to reset the modem..."
- "Dear your wifi is complete shit and it's giving me horrible anxiety that I can't do my homework"
- "@comcastcares Only getting 12MBs download, paying for 100. What gives?"

## Billing Issues

Customer disputes charges, requests refunds or credits, or has billing errors, including late fees, payment status concerns, rate disputes, price increases, or hidden fees.

Examples:
- "That's great - how about discontinuing channel bundles. And your pricing is outrageous."
- "@comcastcares internet erratic in Fairlington Va last night and this morning - very annoying, what is going on?"
- "@comcastcares Too late, you all do this to people every month. I’m currently in the process of discontinue my services #TeamFirestick"

## Account Management

Customer requests account status, billing, contact info, login assistance, changes to services, or login/account access issues.

Examples:
- "I'm going to pretend that did not just send me an e-mail asking if I'm paying too much for my cellphone. You know what I am paying too much for? My cable. How about lower that?"
- "#comcast internet down for 2nd day in a row. Why am I paying for such crappy service? #comcastcares"
- "hey , Comcast why don’t you want our money?"

## Technical Support

Customer needs help troubleshooting equipment, error codes, signal quality, Wi‑Fi, speed, device configuration, VPN/security queries, or general technical issues.

Examples:
- "And that’s why you sir are smarter then me"
- "like ⏲️@comcastcares strikes again. as is often the case they'll ask2 DM 2resolve the issue like they have since I got signd on ovr 1 yr ago"
- "@comcastcares Dont worry after rebooting 4 times it finally worked."

## Service Availability & Scheduling

Customer asks if service is available in a specific location, requests new service activation, move, or activation, and wants to schedule, reschedule, or discuss a technician visit for repair or installation.

Examples:
- "@ComcastCares #mobile_CareXI"
- "@ComcastCares #mobile_Care can I schedule an appointment from the my account app?"
- "@comcastcares if y’all seriously make me wait a whole week to get a technician out to fix my cable and internet y’all will lose a life long customer shit is insane"

## Escalation & Security

Customer requests a supervisor or higher‑level assistance, includes harassment/rude language, retention offers, lack of response, or alleges unauthorized access, data breaches, or fraudulent activity and requests protection or investigation.

Examples:
- "y'all bullshiting on my service. I've now waited 4days 4 invisible technician. #overpromise #overprice #underdeliver #blamecustomer"
- "Fuck !!!! My service hasn't worked reliably since November started!!! I'm taking my business to"
- "Cancelling all of my HORRIBLE services as soon as they open tomorrow. DONE WITH THIS CRAP CABLE AND INTERNET 👋🏼"
