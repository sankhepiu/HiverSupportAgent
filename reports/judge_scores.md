# LLM-as-Judge Scores

Groq judge scored 20 of the 35 drafted replies from `reports/sample_outputs.jsonl` on a 1-5 rubric: grounded in historical pattern, addresses the actual issue, and appropriate tone. Same rubric `src/human_judge_sample.py` uses for the blind human re-scoring of a subset. Sample size was capped at 20 (per a tight-timeline call) after this account's Groq free-tier rate limit made scoring all 35 too slow - the remaining examples were never attempted, not scored-and-failed.

## Average scores

- **Grounded in historical pattern (matches how @comcastcares actually resolves this)**: 4.45 / 5 (n=20)
- **Addresses the actual issue the customer raised**: 3.95 / 5 (n=20)
- **Appropriate tone (polite, professional, on-brand)**: 4.90 / 5 (n=20)

## Per-example scores

### thread 831681_923437

**Customer:** @comcastcares I didn't get to watch a single play of the game cause of this outage what the hell
**Draft:** I’m sorry you missed the game. Please DM me your account phone number and I’ll investigate the outage right away. –MK

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same personalized, action-oriented style seen in the historical examples, including a direct request for account details and a signature.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the missed game and offers to investigate the outage, addressing the customer’s complaint.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is apologetic, polite, and professional, aligning with Comcast’s on-brand customer support voice.

### thread 1840835_1840837

**Customer:** @comcastcares I TYPED THIS 2HRS AGO U DENSE DUMMYS. AND U REALLY THINK THIS IS A ISSUE THT SHOULD BE DONE OVER 2HRS TEXT IN SOCIAL MEDIA.... THT IS AWFUL
**Draft:** I’m sorry you’re still having trouble. Please DM us your phone number so we can investigate and get this resolved. -JB

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same concise, action‑oriented style seen in the historical examples, including the signature and request for a DM.
- Addresses the actual issue the customer raised: **4/5** - It acknowledges the ongoing trouble and offers a next step, but it does not explicitly reference the 2‑hour delay mentioned by the customer.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on‑brand, with a clear apology and a friendly sign‑off.

### thread 1069001_1068999

**Customer:** @ComcastCares #mobile_Care once again horrible customer service
**Draft:** Hey, I’m sorry you’re having a tough time. Please DM me your full name, account phone number, and the address on the account so I can look into this right away. -JB

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and style as the historical examples, requesting a DM with personal details to investigate the issue.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the customer’s frustration and offers a concrete next step to resolve the problem.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and consistent with Comcast’s on‑brand customer‑service voice.

### thread 781942_781941

**Customer:** oops! just realized the game was on ESPN. my bad! thx
**Draft:** No worries—happy to help! If you need anything else, just let us know. Enjoy the game!

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **2/5** - The reply is generic and does not reflect any specific resolution style or content from historical examples.
- Addresses the actual issue the customer raised: **1/5** - The response does not acknowledge the customer’s realization about the ESPN game or respond to their brief thanks.
- Appropriate tone (polite, professional, on-brand): **4/5** - The tone is polite, friendly, and on-brand, though it could be more directly helpful.

### thread 1146256_1895842

**Customer:** @comcastcares I did that 2 weeks ago. You wouldn’t relent on the contract. All I wanted was the same monthly rate and channels, no contract. You wouldn’t.
**Draft:** Hi, I’m sorry you’re still having trouble. Please DM me your account or phone number so I can review the contract details and get this resolved for you. -EI

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same concise, action‑oriented style seen in the historical examples, requesting account details to investigate the contract.
- Addresses the actual issue the customer raised: **5/5** - It directly addresses the customer’s concern about the contract and rate by offering to review the contract details.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and consistent with Comcast’s on‑brand customer‑service voice.

### thread 1531610_1531609

**Customer:** @comcastcares I need a supervisor to call me please. I cannot reach anyone over the phone and online chat is not helping. Held for 25 min
**Draft:** Hi, I’m sorry you’re having trouble getting through. Please DM me your full account address and I’ll connect you with a supervisor right away. –CSR

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **4/5** - The reply follows the historical pattern of asking for account details via DM and offering to connect with a supervisor, matching the style of prior responses.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the customer’s request for a supervisor and the difficulty reaching anyone.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand for Comcast customer support.

### thread 2458529_2458528

**Customer:** Dear please look into your gigabit infrastructure. I should not have to reboot my modem every day to reduce my ping in online games!
**Draft:** Hi! I’m sorry you’re having trouble. Please DM me your account number or the phone number on the account so I can look into the gigabit performance for you. –Comcast Cares

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same style and content pattern as the historical examples, requesting account details via DM to investigate the issue.
- Addresses the actual issue the customer raised: **3/5** - It acknowledges the problem and offers to look into gigabit performance, but it does not specifically mention ping or the daily reboot requirement.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and consistent with Comcast Cares’ brand.

### thread 2499559_2499557

**Customer:** help me
**Draft:** Sure! Can you let us know what you need help with? Once we have a bit more detail, we’ll get it sorted right away.

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **2/5** - Without historical examples, the reply cannot be confidently matched to a known resolution style, so it is only somewhat grounded.
- Addresses the actual issue the customer raised: **2/5** - The reply asks for more detail instead of directly addressing the customer's terse request for help.
- Appropriate tone (polite, professional, on-brand): **4/5** - The tone is polite, professional, and on-brand, though it could be more proactive.

### thread 1355300_1355301

**Customer:** @comcastcares Sent Acct #
**Draft:** Hi! I can help with that. Please send me a DM with your account number and the phone number on the account. Thanks!

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and tone as the historical examples, requesting account details via DM.
- Addresses the actual issue the customer raised: **5/5** - It directly responds to the customer’s request to send an account number by asking for the account number and phone number.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand.

### thread 726012_726013

**Customer:** @ComcastCares #mobile_CareXI nothing is working right now ? We had this problem forever ????!!! What’s going on ?!
**Draft:** Hi there! I’m sorry you’re still having trouble. Please DM us your full address and the phone number linked to the account so we can investigate further. Thank you!

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same style as the historical examples, asking for address and phone number via DM to investigate.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the ongoing trouble and offers a next step to resolve it.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand for Comcast Cares.

### thread 400501_400502

**Customer:** @comcastcares spent half an hour on the phone w someone who could barely speak English and my internet still doesn’t work. Please help
**Draft:** Hi, sorry to hear about the trouble. Please DM us your name and account number so we can investigate and get your internet working again. Thanks!

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same pattern as the historical examples, asking for name and account number via DM to investigate the issue.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the internet problem and offers a next step to resolve it.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand for Comcast support.

### thread 2074098_2074097

**Customer:** When you’re on the phone with for almost an hour and the 2 month long problem cant be fixed. #what #help
**Draft:** I’m sorry you’re still stuck. Please DM us your Xfinity ID and the exact issue so I can pull up a priority ticket and get a technician on site ASAP. -LT

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **4/5** - The reply follows the informal, supportive style seen in the historical examples, offering direct assistance rather than generic boilerplate.
- Addresses the actual issue the customer raised: **4/5** - It acknowledges the frustration of a long phone call and offers a concrete next step to resolve the issue.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand, with a friendly sign‑off.

### thread 104456_104454

**Customer:** HA HA YOU SO FUNNY JEFFREY 😄😄😄
**Draft:** Hey! Glad we could bring a smile. How can we help you today?

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **2/5** - The reply lacks specific reference to any known resolution style or content from historical examples, making it generic.
- Addresses the actual issue the customer raised: **3/5** - The reply acknowledges the customer's tone but does not directly respond to any specific request or concern, offering help instead.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is friendly, polite, and on-brand for customer support.

### thread 1972252_1972251

**Customer:** @comcastcares my modem went down with the power and it is still blinking. Is there an outage?
**Draft:** I’m checking for a local outage. Please DM us your account number and address so we can resolve this quickly. -IB

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the historical pattern of offering a local outage check and requesting account details via DM, matching the style of previous responses.
- Addresses the actual issue the customer raised: **5/5** - It directly addresses the modem blinking issue and asks for information to investigate.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand, with a concise sign‑off.

### thread 114157_114155

**Customer:** @comcastcares Who can I contact to have your services extended to my area?
**Draft:** I’d be happy to check availability for you. Please DM me the phone number linked to your account and the service address. –Jules

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same concise, action‑oriented style seen in the historical examples, requesting account details in a friendly manner.
- Addresses the actual issue the customer raised: **2/5** - The customer asked who can contact to extend services to their area, but the reply instead asks for account details, not directly addressing the request.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and consistent with Comcast’s brand voice.

### thread 1380678_1380677

**Customer:** Hey , just ordered uverse because you planks can’t add HD to the account. Bill has been paid for 10 days and still has a “hold”.
**Draft:** Hi! I’m sorry about the delay. Please DM us your account number or address so we can check the status and get a tech scheduled ASAP. Thanks! -CF

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same concise, action‑oriented style seen in the historical examples, including a friendly greeting, apology, and a request for account details.
- Addresses the actual issue the customer raised: **3/5** - While it acknowledges a delay and offers to help, it does not specifically address the customer’s mention of a payment hold, so it partially addresses the issue.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on‑brand, using a friendly greeting and a courteous closing.

### thread 2745191_2745190

**Customer:** @comcastcares slowest WiFi internet EVER!!!!!!!!!
**Draft:** Hi! We’d love to help speed up your Wi‑Fi. Please DM us your account number, full address, and phone number so we can investigate right away. Thank you!

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and wording pattern as the historical examples, requesting account details via DM.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the slow WiFi complaint and offers to investigate.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is friendly, professional, and consistent with Comcast’s brand.

### thread 568164_568163

**Customer:** Where does all of Comcast fucking money to do where they can't provide a single second of good fucking internet??? Must know... because I can't play anything without lagging every second.
**Draft:** I’m sorry you’re having this issue. Please DM me your full name, address, and account number so I can investigate and get your internet back to smooth play. –Comcast Cares

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and wording pattern as the historical examples, requesting the same personal details to investigate the issue.
- Addresses the actual issue the customer raised: **4/5** - It acknowledges the problem and offers to investigate, but it does not explicitly mention the lagging or gaming context mentioned by the customer.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand, with a clear apology and a helpful next step.

### thread 2133772_2133771

**Customer:** shoutout for causing yet another stream to end early :-) u guys are garbage
**Draft:** I’m sorry you’re having trouble with your stream. Could you DM me your full name and address so I can look into this for you? – Noah

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and style as the historical examples, asking for a DM with name and address.
- Addresses the actual issue the customer raised: **3/5** - It acknowledges the stream issue but does not directly address the specific complaint about the stream ending early.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand.

### thread 670736_670735

**Customer:** Y'all Fucking Me Over Tonight , shitty ass internet
**Draft:** I’m sorry you’re having trouble. Please DM us your full name, account number or phone number, and the name on the account so we can look into this right away. - @comcastcares

- Grounded in historical pattern (matches how @comcastcares actually resolves this): **5/5** - The reply follows the same structure and content style as the historical examples, requesting account details in a similar manner.
- Addresses the actual issue the customer raised: **5/5** - It directly acknowledges the customer's frustration and offers a solution by asking for account information.
- Appropriate tone (polite, professional, on-brand): **5/5** - The tone is polite, professional, and on-brand, avoiding profanity and maintaining a courteous approach.
