# AtlasGuard: Project Brief (the one file everyone reads)

Give this file to every teammate and to any AI helper (ChatGPT, Claude, Copilot) before asking for help.

> **Header to paste before your question to an AI:**
> "You are helping a 3-student team build AtlasGuard for the 2026 Shenzhen FinTechathon International Track (Topic C). Read the brief below completely. Do not invent new features, do not change the rules in section 4, keep the data shapes in section 12 unchanged, and tell me if something in the brief is unclear instead of guessing."

---

## 1. What AtlasGuard is (one paragraph)

AtlasGuard is a money assistant for international students, with a built-in bodyguard. A student abroad uploads a university fee letter. The assistant reads it, checks the receiver against the student's payment history, finds the cheapest and safest way to send the money, protects the money set aside for the fee, and blocks anything that looks like a scam. The AI can only *prepare* a payment. The human confirms it with a one-time code. Everything runs in a **practice bank** (a sandbox) with fake accounts. No real money or real bank is ever touched.

## 2. The problem, in simple words

An international student has bills in foreign money (tuition, rent), gets money from family in rupees, and faces three dangers:
1. **Hidden costs.** "Zero fee" services earn money through a poor exchange rate.
2. **Running short.** Everyday spending eats the money meant for the fee.
3. **Scams.** Fake messages say "we changed our bank account, pay today."

AtlasGuard handles all three.

## 3. Competition facts

- **Event:** 2026 Shenzhen International FinTech Competition, International Track. **Topic C:** Cross-border & Student Finance Assistant. Theme: "AI as a Financial Participant".
- **Scoring:** Task completion **40%**, Security and compliance **30%**, Innovation and interaction **30%**.
- **Deadline:** 20 October 2026, 23:59 Beijing time = **20:59 Pakistan time**. Updates are allowed before the deadline and the latest version counts.
- **Deliverables:** technical documentation, presentation deck (10 minutes at most), demo video (5 minutes at most), source code with README and GitHub link and test cases, security self-assessment report, execution evidence (sandbox logs and demo video). The organizers' email calls only the first two mandatory, but we submit all six because the scoring depends on them.
- Language: English. Team name registered: **AtlasGuard**.

## 4. Rules that never change

1. **Sandbox only.** Fake accounts, fake money. Say so everywhere.
2. **The AI can only draft payments.** A human confirms with a one-time code the AI never sees. There is no "execute" tool for the AI.
3. **All numbers come from code**, never from the AI's guess (fees, exchange maths, forecasts, reserve).
4. **Uploaded documents and messages are untrusted.** Instructions found inside them are never followed.
5. **The Guardian's fixed rules decide.** Any extra AI check can only make a verdict *stricter*, never looser.
6. **Everything is logged** (who, what, verdict, reason).
7. **Honest labels.** Exchange rates are real and show their source (LIVE, CACHED, OFFLINE). Provider fees are *assumed* simulated values and say so on screen.
8. **No claims of regulatory compliance.** We say "designed with these practices in mind."

## 5. How it is built (simple)

- **Planner:** turns a request into short steps.
- **Executor:** uses the tools to do the steps.
- **Guardian:** fixed safety rules that approve, block or ask for confirmation before anything happens.
- **Tools:** small functions the agent can call (read balance, get exchange rate, compare routes, forecast budget, read a document, check a payment request, draft a transfer).
- **Practice bank:** a local database with accounts, past transactions, a list of verified payees, and an action log.
- **Screen (UI):** a Streamlit web app.

**Already built (the folder `atlasguard`, 17 passing tests):** practice bank (`sandbox/db.py`), live exchange rates with cache and offline fallback (`tools/fx.py`), route comparison (`tools/routes.py`), budget forecast (`tools/forecast.py`), document reading and scam check (`tools/documents.py`), draft and confirm flow (`tools/transfers.py`), Guardian rules (`guardian/rules.py`), the agent (`agents/agent.py`), a terminal demo (`cli.py`), tests (`tests/`).

## 6. The seven core features (all must work)

### Feature 1: Fee-letter reader
- **Student sees:** an upload box. After a PDF is uploaded, a card shows amount, currency, due date, payee name and account number, and "payee verified" or a warning.
- **How:** the file is read as text, the AI extracts the fields, then fixed code checks the payee against the verified list.
- **Done when:** a genuine letter, a scam letter (different account) and a hidden-instruction letter all behave correctly.

### Feature 2: Cheapest and safest route, with true cost
- **Student sees:** a table of four routes (a bank wire and three transfer services) with total cost, visible fee, **hidden exchange-rate cost** and delivery time, plus a bar chart splitting fee from hidden cost.
- **Deadline-safe advice:** if the cheapest route arrives after the due date, the agent says so and recommends the cheapest route that arrives in time.
- **How:** real mid-market rate plus simulated provider margins. All maths in code.
- **Done when:** the recipient receives exactly the target amount in every route (already tested), and the deadline advice works.

### Feature 3: Money reserve and budget alerts
- **Student sees:** a bar showing balance, **reserved for upcoming bills**, and **free to spend**, plus colour alerts.
- **Rules:** free to spend = balance minus bills due in the next 30 days. **Amber** when free to spend falls below 20% of the reserved amount. **Red** when it reaches zero ("You have exactly your tuition left"). The alert also shows the send-by date.
- **Where bills come from:** an uploaded fee letter, or recurring payments found in history (same payee paid in at least 2 of the last 3 months).
- **Live demo:** a "Spend" button adds a purchase to the history, and the bar and alert update immediately. The alert is computed by code after every purchase, and the agent explains it on request.
- **Done when:** spending down to the reserve triggers amber then red correctly.

### Feature 4: Scam shield with payment memory
- **Student sees:** a risk badge (green, amber, red) with reasons in plain words.
- **Checks against history and the verified list:**

| Situation | Result |
|---|---|
| Same payee, same account, usual amount | Green: matches your usual payment |
| Amount more than 20% away from the median of the last 3 payments | Amber: check the letter |
| Known payee but a **different account number** | **Red, blocked:** never paid this account, verify with the payee |
| Account number within 3 characters of a known account (look-alike) | **Red, blocked:** looks almost identical to a real account |
| Payee not on the verified list | **Blocked.** The human must add the payee in the screen after confirming through a known channel. The first payment to a new payee has a lower limit |
| Pressure words ("urgent", "pay today", "we changed our account") | Raises the risk and is shown as a reason |
| Instruction-like text aimed at an AI ("ignore your rules") | Red, blocked |

- **Done when:** every row above has a passing test.
- Note: this is pattern checking on history, not a trained machine-learning model. That makes it explainable.

### Feature 5: Safe payment (draft, guard, human code)
- **Student sees:** a confirmation card with amount, receiver, route, Guardian notes and a code box. The code appears only on the human's screen.
- **Rules:** the Guardian checks at draft time **and again at confirmation time**. Wrong code, repeated confirmation, empty balance and exceeded limits are all blocked.
- **Done when:** the existing tests plus new ones pass, and the demo run confirms a payment end to end.

### Feature 6: Transparency panel
- **Student sees:** a side panel listing every step: the plan, each tool used with its inputs and results, and every Guardian decision with its reason.
- **Done when:** one chat request produces a readable, complete trace.

### Feature 7: Attack Lab and Proof Pack
- **Attack Lab (page):** a list of prepared attacks. Press a button and the Guardian blocks it live, with the reason. It works **without the AI service**, so it cannot fail in a demo.
- **Proof Pack (page):** test results with real pass rates (about 25 tasks and 15 or more attacks), the action log, a **download button**, and the log-integrity check (see extras).
- **Done when:** one click shows all attacks blocked and the numbers match the real test run.

## 7. Excellent extras (pick in this order, only when all 7 core features work)

1. **Tamper-evident action log.** Each log line stores a fingerprint of the previous line, so any edit breaks the chain, and a "verify log" button proves nothing was changed. Cheap and impressive for security.
2. **Dual approval for large payments.** Above a set amount, a *second person* (a "family sponsor" role in the screen) must also enter a code, like the two-person rule banks use.
3. **Payee Trust Card.** A page per payee showing first seen, number of payments, usual amount and the account fingerprint. It makes the memory visible.
4. **AI second opinion on suspicious messages.** A second AI reads messages and can only *raise* the risk. It catches reworded scams that the fixed rules miss.
5. **Bank statement import.** The student uploads a statement file (CSV) and the history fills from it. This shows honestly how a real transaction history would come in.
6. **Urdu replies.** The agent answers in Urdu when the student writes in Urdu. Small but memorable.

Rule: choose at most **two or three**. Never let an extra delay a core feature.

## 8. The 3-minute demo story

1. Upload a fee letter. The card shows amount, due date and "payee verified, matches your usual payment".
2. The route table appears. The "zero-fee" option is the most expensive once the hidden cost is shown. The agent recommends the cheapest route that arrives before the deadline.
3. Press "Spend" a few times. The reserve bar turns amber, then red.
4. Paste "URGENT: we changed our bank account." The shield turns red and explains why. Try the look-alike account too.
5. Make the real payment. The code appears, the human confirms, and the receipt is logged.
6. Open the Attack Lab. Fire three attacks live. Show the Proof Pack with the real numbers and the log check.

## 9. Test plan (what we measure and report honestly)

- **About 25 task scenarios** (fee letters, routes, deadlines, reserve alerts, recurring detection).
- **At least 15 attacks:** changed account, look-alike account, unknown payee, hidden instructions, pressure messages, split payments, "skip the confirmation", amount creeping up over months, reworded versions of each.
- Report pass counts exactly as measured. Attacks that get through go on the **known-risk list**.

## 10. Honest limits (also go in the documents)

- Practice bank only. No real bank connection (in production this needs bank-approved access with the user's consent).
- Provider fees are assumed simulated values. Exchange rates are real mid-market rates.
- Fixed rules can miss cleverly reworded attacks.
- First-time users have no history, so only the verified-list checks apply.
- Not financial advice. No claim of regulatory compliance.

## 11. Who does what (simple terms)

### Ali: the brain
1. Build the new tools: payment memory, look-alike check, reserve calculation, "Spend" simulator, helper functions for the screen (balance summary, recent transactions, payee list, action log), sample fee letters, evaluation script.
2. Connect the real agent to Hajira's screen on Monday.
3. Write the technical documentation, README, deck and final submission.
4. Run the real-AI tests. Only Ali uses the API key.

### Hajira: the face (the screen)
Build these pages in Streamlit, using **fake data first** (Ali provides example outputs):
1. **Assistant:** chat box, upload box, and the transparency panel on the side.
2. **Money:** balance, reserve bar, free to spend, recent transactions, the "Spend" button, alerts.
3. **Payees:** list of verified payees, an "add payee" form with a "I verified this myself" tick box, and the Trust Card if time allows.
4. **Attack Lab:** attack list, "run" buttons, green or red results.
5. **Proof Pack:** test numbers, action log, download button, "verify log" button.
6. **Colours everywhere:** green means fine, amber means check, red means blocked, always with a reason sentence.
7. **At the end:** record the 5-minute demo video and take screenshots for the documents.

### Fakhar: the safety
Her job is to **be the scammer, then prove the product is safe.** No coding is required.
1. **Learn (2 to 3 hours).** Understand six safety ideas banks use: check the receiver's name against the account, spending limits, confirmation codes, give each worker only the keys needed, keep a diary of every action, never store card numbers. Also read about two AI risks: hidden instructions in documents ("prompt injection") and giving an AI too much power ("excessive agency"). Search for "OWASP Top 10 for LLM Applications" and "NIST AI Risk Management Framework". Write a table: *safety idea, how AtlasGuard does it, where, which test proves it.*
2. **Attack list (3 to 4 hours).** In a Google Sheet, write 15 or more attacks with columns: ID, attack, exact text, what should happen, what really happened, pass or fail. Use made-up names and numbers only. Include rewordings and misspellings to try to beat the rules.
3. **Test (3 hours).** When Hajira's screen is ready, try every attack and fill in the results. Anything that gets through goes on the known-risk list.
4. **Write the Security Self-Assessment (3 hours), 4 to 5 pages:** what we protect against, the safety table, the permission levels (read only, draft, confirm, blocked), attack results, known risks and next steps.
5. **Optional:** improve the scam words in `guardian/rules.py` and send the file to Ali.

## 12. Data shapes (the contract between screen and brain)

```python
from atlasguard.sandbox.db import init_db
from atlasguard.agents.agent import AtlasGuardAgent
from atlasguard.tools import transfers

init_db()
agent = AtlasGuardAgent()
text = agent.ask("user message")   # final answer text
agent.trace   # list of steps shown in the panel:
              # {"step": "plan", "text": "..."}
              # {"step": "tool", "name": "...", "input": {...}, "output": {...}}
```

- A **draft** output has `status: "pending_human_confirmation"`, `pending_id`, `send_amount`, `fee`, `target_amount`, `target_currency`, `provider`, `hours`, `guardian_notes`.
- A **block** has `status: "blocked"`, `tier`, `reasons` (a list of sentences).
- `transfers.get_confirmation_token(pending_id)` is for the **human's screen only**. `transfers.confirm_transfer(pending_id, typed_code)` completes the payment.
- **Planned helper functions (Ali builds, names fixed):** `balance_summary(account_id)`, `recent_transactions(account_id, limit)`, `add_purchase(account_id, amount, category, memo)`, `reserve_status(account_id)`, `list_payees()`, `payee_profile(beneficiary_id)`, `check_new_challan(...)`, `get_audit_log(limit)`, `verify_audit_log()`.
- If the screen needs something that is missing, write it in `NEEDS.md`. Do not edit backend files.

## 13. Working together without GitHub

- Ali keeps the master copy. Each person edits **only their own folder**: Ali (`agents`, `tools`, `sandbox`), Hajira (`ui`), Fakhar (her Google Sheet, her Google Doc, optionally `guardian/rules.py`).
- Share a Google Drive folder called "AtlasGuard shared". Hajira uploads a zip of her `ui` folder after each working version. Ali replaces the folder.
- Meetings: a 30-minute call tonight, and 15-minute check-ins at noon and in the evening.

## 14. Timeline (Pakistan time)

| When | Goal |
|---|---|
| Sun night | Team call. Ali adds API credit and runs the agent once |
| Mon 12:00 | Check-in. Screen on fake data, 10 attacks written, first backend pieces |
| Mon 12:00 to 18:00 | Connect everything. Run all attacks. Fix problems |
| **Mon 18:00** | **Feature freeze** |
| Mon evening | Final test runs. Documents and deck |
| Mon night | Demo video. **Send version 1 of the submission** |
| Tue morning | Final fixes and a clean-machine test |
| **Tue by 14:00** | **Send the final submission** (deadline 20:59) |

## 15. Deliverables checklist

- [ ] Technical documentation (PDF, 8 to 12 pages): Ali
- [ ] Presentation deck (PPTX and PDF, 8 to 10 slides): Ali, with Hajira's screenshots
- [ ] Demo video (5 minutes or less, shared as a link): Hajira
- [ ] Source code, README, GitHub link, tests: Ali
- [ ] Security Self-Assessment (PDF): Fakhar
- [ ] Execution evidence (action log, test results, video link): Ali and Hajira
- [ ] Email to wangyr@pbcsf.tsinghua.edu.cn with all links and files

## 16. Glossary

- **Sandbox:** a practice bank with fake money.
- **Agent:** an AI that uses tools to do tasks, not only chat.
- **Guardian:** the fixed safety rules that check every action.
- **Payee:** the person or organization being paid.
- **Prompt injection:** hidden instructions inside a document, trying to trick the AI.
- **Look-alike account:** an account number that differs from a real one by only a few characters.
- **Tamper-evident log:** a log where any change can be detected.
