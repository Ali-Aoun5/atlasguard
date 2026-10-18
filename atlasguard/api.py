"""The ONE file the screen (ui/app.py) talks to.

Hajira only needs to know the functions in this file. Each one returns plain
dicts / lists, so the screen never touches the database or the AI directly.

Demo mode: set AG_MOCK=1 (or leave ANTHROPIC_API_KEY empty). The assistant is then
`MockAgent`, which has the same ask()/trace interface as the real agent and calls the
REAL tools (rules, memory, reserve, routes). It just does not use an AI service to
choose the tools or to write the reply. The screen shows a "Demo mode" label.
"""
import os
import re
import secrets

from .attacks import list_attacks, run_attacks  # noqa: F401  (re-exported for the screen)
from .sandbox import db
from .sandbox.db import conn
from .tools import challan, memory, reserve, routes, transfers

ACCOUNT = "ACC-001"
PROVIDER_DEFAULT = "Remit App B (simulated)"


# ----------------------------------------------------------------- mode
def is_mock() -> bool:
    if os.environ.get("AG_MOCK", "").strip() in {"1", "true", "yes"}:
        return True
    return not os.environ.get("ANTHROPIC_API_KEY", "").strip()


def get_agent():
    if is_mock():
        return MockAgent()
    from .agents.agent import AtlasGuardAgent
    return AtlasGuardAgent(ACCOUNT)


def start() -> None:
    """Create the practice bank if it does not exist yet."""
    db.init_db(reset=False)


# ----------------------------------------------------------------- money
def balance_summary() -> dict:
    with conn() as c:
        a = dict(c.execute("SELECT * FROM accounts WHERE id=?", (ACCOUNT,)).fetchone())
    return {"account_id": a["id"], "owner": a["owner"], "currency": a["currency"],
            "balance": round(a["balance"], 2)}


def recent_transactions(limit: int = 15) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT ts,amount,category,memo FROM transactions WHERE account_id=? "
                         "ORDER BY ts DESC LIMIT ?", (ACCOUNT, limit)).fetchall()
    return [dict(r) for r in rows]


def get_reserve() -> dict:
    return reserve.reserve_status(ACCOUNT)


def spend(amount: float, category: str = "misc", memo: str = "") -> dict:
    return reserve.add_purchase(ACCOUNT, amount, category, memo)


def add_bill(label: str, amount: float, currency: str, due_date: str,
             beneficiary_id: str | None = None) -> dict:
    return reserve.add_obligation(ACCOUNT, beneficiary_id, label, amount, currency, due_date, "manual")


# ----------------------------------------------------------------- payees
def list_payees() -> list[dict]:
    with conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM beneficiaries ORDER BY name")]
    for r in rows:
        p = memory.payee_profile(r["id"])
        r["payments"] = p["payments"]
        r["usual_amount"] = p["usual_amount"]
    return rows


def payee_profile(beneficiary_id: str) -> dict:
    return memory.payee_profile(beneficiary_id)


def add_payee(name: str, iban: str, currency: str, bank: str = "", verified: bool = False) -> dict:
    """`verified` must be ticked by the HUMAN after checking the payee through a known contact."""
    name, iban = name.strip(), iban.strip()
    if not name or not iban:
        return {"status": "refused", "reason": "Name and account number are required."}
    pid = "BEN-" + secrets.token_hex(2).upper()
    with conn() as c:
        c.execute("INSERT INTO beneficiaries(id,name,bank,iban,currency,verified) VALUES(?,?,?,?,?,?)",
                  (pid, name, bank, iban, currency.upper(), 1 if verified else 0))
    db.audit("human", "add_payee", 1, "allow", f"{pid} {name} verified={bool(verified)}")
    return {"status": "ok", "id": pid, "verified": bool(verified)}


# ----------------------------------------------------------------- letters
def analyze_letter(path: str) -> dict:
    return challan.analyze_challan(path, ACCOUNT)


def check_letter_fields(name: str, iban: str, amount: float | None, currency: str | None,
                        text: str = "") -> dict:
    return memory.check_new_challan(name, iban, amount, currency, text)


# ----------------------------------------------------------------- confirmation
def pending_info(pending_id: str) -> dict | None:
    return transfers.get_pending(pending_id)


def confirmation_code(pending_id: str) -> str | None:
    """The one-time code is shown to the HUMAN only. It is never given to the AI."""
    return transfers.get_confirmation_token(pending_id)


def confirm(pending_id: str, code: str) -> dict:
    return transfers.confirm_transfer(pending_id, code)


# ----------------------------------------------------------------- proof
def get_audit_log(limit: int = 100) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT id,ts,actor,tool,tier,verdict,detail FROM audit_log "
                         "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def verify_audit_log() -> dict:
    return db.verify_audit_log()


def attack_list() -> list[dict]:
    return list_attacks()


def attack_run(only_id: str | None = None) -> dict:
    return run_attacks(only_id)


# ----------------------------------------------------------------- demo assistant
_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(EUR|USD|GBP|CAD|AUD)?", re.I)
_CCY = re.compile(r"\b(EUR|USD|GBP|CAD|AUD)\b", re.I)


class MockAgent:
    """Demo assistant: picks tools by keywords, calls the REAL tools, writes a plain reply.

    It has the same interface as the real agent: ask(text, file_path=None) -> str and
    a `trace` list of {"step": "tool", "name", "input", "output"}.
    """

    def __init__(self):
        self.trace: list = []

    def _call(self, name: str, args: dict, fn):
        out = fn()
        self.trace.append({"step": "tool", "name": name, "input": args, "output": out})
        return out

    def ask(self, text: str, file_path: str | None = None) -> str:
        t = text.lower()
        self.trace.append({"step": "plan", "text": "Demo mode: keyword routing to real tools."})

        if file_path:
            r = self._call("analyze_challan", {"path": file_path},
                           lambda: challan.analyze_challan(file_path, ACCOUNT))
            return self._explain_letter(r)

        if any(k in t for k in ("free to spend", "reserve", "afford", "how much can i spend")):
            r = self._call("reserve_status", {"account_id": ACCOUNT},
                           lambda: reserve.reserve_status(ACCOUNT))
            return f"**{r['level'].upper()}** - {r['message']} (Rates: {r['rate_source']}.)"

        if any(k in t for k in ("history", "profile", "usual", "remember")):
            r = self._call("payee_profile", {"beneficiary_id": "BEN-UNI"},
                           lambda: memory.payee_profile("BEN-UNI"))
            return (f"I remember {r['payments']} payment(s) to this payee, usually "
                    f"{r['usual_amount']:,.2f} {r['currency']}, first seen {r['first_seen']}, last paid "
                    f"{r['last_paid']}. Known accounts: {', '.join(r['accounts_used']) or 'n/a'}.")

        ccy = _CCY.search(text)
        amt = None
        for m in _AMOUNT.finditer(text.replace(",", "")):
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if v >= 10:
                amt = v
                break
        if amt and ccy and any(k in t for k in ("route", "compare", "send", "pay", "cheapest", "draft")):
            args = {"source_currency": "PKR", "target_currency": ccy.group(1).upper(),
                    "target_amount": amt}
            r = self._call("compare_routes", args, lambda: routes.compare_routes(**args))
            lines = [f"To deliver {amt:,.2f} {args['target_currency']} (rate: {r['rate_source']}; "
                     f"provider prices are simulated):", ""]
            for q in r["quotes"]:
                lines.append(f"- {q['provider']}: send {q['send_amount']:,.0f} PKR, fee "
                             f"{q['fee']:,.0f}, hidden FX cost {q['fx_margin_cost']:,.0f}, "
                             f"{q['hours']}h")
            lines.append(f"\nCheapest overall: **{r['cheapest']}**.")
            if any(k in t for k in ("draft", "send", "pay")):
                d = self._call("draft_transfer", {"beneficiary_id": "BEN-UNI",
                               "target_amount": amt, "target_currency": args["target_currency"],
                               "provider_name": r["cheapest"]},
                               lambda: transfers.draft_transfer(ACCOUNT, "BEN-UNI", amt,
                                                                args["target_currency"],
                                                                r["cheapest"]))
                if d["status"] == "pending_human_confirmation":
                    lines.append(f"\nDraft **{d['pending_id']}** is ready. Only you can confirm it.")
                else:
                    lines.append(f"\nThe Guardian blocked it: {'; '.join(d.get('reasons', []))}")
            return "\n".join(lines)

        return ("Demo mode. Try: 'compare routes to pay 3000 EUR', 'how much is free to spend', "
                "'what is my history with the university', or upload a fee letter.")

    def _explain_letter(self, r: dict) -> str:
        if r["status"] != "ok":
            return "I could not read every field of this letter. A human must check it."
        f, c = r["fields"], r["check"]
        head = {"green": "Looks consistent with your history.",
                "amber": "Be careful - something is unusual.",
                "red": "Do NOT pay this."}[c["level"]]
        lines = [f"**{c['level'].upper()}** - {head}", "",
                 f"Payee: {f['payee']}  |  Amount: {f['amount']:,.2f} {f['currency']}  |  "
                 f"Due: {f['due_date']}", ""]
        lines += [f"- {x}" for x in c["reasons"]]
        if r.get("routes"):
            rt = r["routes"]
            lines.append(f"\nRecommended route: **{rt.get('recommended')}** "
                         f"({rt.get('days_left')} days left).")
        return "\n".join(lines)
