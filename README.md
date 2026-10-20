# AtlasGuard

**A money assistant for international students, with a security guard built in.**
Team AtlasGuard: Ali Aoun Mehdi, Hajira Awan, Fakhar Arooj.
2026 Shenzhen International FinTech Competition, International Track, Topic C (Cross-border & Student Finance Assistant).

> **Sandbox only.** All accounts, balances and payees are simulated. No real money, bank or payment network is touched. Exchange rates are real mid-market rates; provider fees, margins and delivery times are simulated assumptions. This is not financial advice, and we make no claim of regulatory compliance.

## What it does
- **True cost.** Compares four routes by visible fee plus hidden exchange-rate margin, so the recipient gets the exact amount, and recommends the cheapest route that arrives before the due date.
- **Payment memory and scam shield.** Reads a fee letter and checks the payee, account and amount against the student's payment history (green / amber / red). Detects look-alike accounts and instructions aimed at the AI.
- **Money reserve.** Sets aside money for upcoming bills and warns (amber, then red) when spending eats into it.
- **Human in control.** The AI can only draft a payment. A person confirms with a one-time code that the AI never sees.
- **Proof.** Tamper-evident action log, an Attack Lab with 23 prepared attacks, and automated tests.

## Results (reproducible)
47 tests pass; 28 of 28 task scenarios; 23 of 23 attacks stopped; 4 of 4 live agent prompts.
See `evidence/evaluation_results.md`.

## Run it (Windows PowerShell, from this folder)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r atlasguard\requirements.txt
python -m pytest atlasguard\tests -q
python -m atlasguard.evaluate
```
Demo mode (no API key): `$env:AG_MOCK=1` then `streamlit run atlasguard\ui\app.py`

Real agent: create a `.env` file next to the `atlasguard` folder containing `ANTHROPIC_API_KEY=your_key`, then run `streamlit run atlasguard\ui\app.py`.
Sample fee letters (genuine, scam, hidden instruction) are in `atlasguard/samples/`.

## Layout
`agents/` agent loop · `guardian/` fixed safety rules · `tools/` rates, routes, memory, reserve, transfers · `sandbox/` practice bank and action log · `ui/` screen · `api.py` the only door the screen uses · `attacks.py`, `evaluate.py`, `tests/`

## Known limits
Fixed rules can still be beaten by fully reworded instructions or other languages; no code expiry; the log hash chain is not anchored outside the database. Full list in the security self-assessment.
