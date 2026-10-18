"""Money reserve: protect the money that is already promised to upcoming bills.

free_to_spend = balance - (bills due in the next `horizon_days`, converted to the
account currency with the live exchange rate).
Alert levels: red when free <= 0, amber when free < 20% of the reserved amount.
All calculations are plain code.
"""
import datetime as dt

from ..sandbox.db import audit, conn, now
from . import fx
from .memory import predicted_recurring

AMBER_FRACTION = 0.20


def add_obligation(account_id: str, beneficiary_id: str | None, label: str, amount: float,
                   currency: str, due_date: str, source: str = "challan") -> dict:
    dt.date.fromisoformat(due_date)  # validates format
    if amount <= 0:
        raise ValueError("amount must be positive")
    with conn() as c:
        cur = c.execute(
            "INSERT INTO obligations(account_id,beneficiary_id,label,amount,currency,due_date,"
            "source,status) VALUES(?,?,?,?,?,?,?,'open')",
            (account_id, beneficiary_id, label, amount, currency.upper(), due_date, source))
    audit("human", "add_obligation", 1, "allow", f"{label} {amount} {currency} due {due_date}")
    return {"id": cur.lastrowid, "label": label, "amount": amount, "currency": currency.upper(),
            "due_date": due_date}


def reserve_status(account_id: str = "ACC-001", horizon_days: int = 30) -> dict:
    with conn() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise ValueError("unknown account")
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM obligations WHERE account_id=? AND status='open'", (account_id,))]
    today = now().date()
    limit = today + dt.timedelta(days=horizon_days)
    items = [r for r in rows if dt.date.fromisoformat(r["due_date"]) <= limit]
    items += predicted_recurring(account_id, horizon_days)

    acc_cur = acc["currency"]
    rate_source = "identity"
    bills = []
    reserved = 0.0
    for it in items:
        rate = fx.get_rate(it["currency"], acc_cur)
        rate_source = rate["source"] if rate["source"] != "identity" else rate_source
        in_acc = it["amount"] * rate["rate"]
        reserved += in_acc
        bills.append({"label": it["label"], "amount": it["amount"], "currency": it["currency"],
                      "due_date": it["due_date"], "source": it["source"],
                      "amount_in_account_currency": round(in_acc, 2)})
    bills.sort(key=lambda b: b["due_date"])

    balance = acc["balance"]
    free = balance - reserved
    if reserved == 0:
        level, msg = "green", "No upcoming bills are reserved."
    elif free <= 0:
        level = "red"
        msg = (f"Your balance ({balance:,.0f} {acc_cur}) is at or below what is reserved for "
               f"upcoming bills ({reserved:,.0f} {acc_cur}). Spending more will leave you short.")
    elif free < AMBER_FRACTION * reserved:
        level = "amber"
        msg = (f"Only {free:,.0f} {acc_cur} is free to spend. The rest is reserved for "
               f"upcoming bills.")
    else:
        level, msg = "green", f"{free:,.0f} {acc_cur} is free to spend after reserving your bills."
    audit("system", "reserve_status", 0, "allow", f"{account_id}: level={level} free={free:,.0f}")
    return {"account_id": account_id, "currency": acc_cur, "balance": round(balance, 2),
            "reserved": round(reserved, 2), "free_to_spend": round(free, 2), "level": level,
            "message": msg, "bills": bills, "horizon_days": horizon_days,
            "rate_source": rate_source}


def add_purchase(account_id: str, amount: float, category: str = "misc", memo: str = "") -> dict:
    """'Spend' simulator for the demo: adds a purchase and re-checks the reserve."""
    if amount <= 0:
        return {"status": "refused", "reason": "Amount must be positive."}
    with conn() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            return {"status": "refused", "reason": "Unknown account."}
        if amount > acc["balance"]:
            audit("human", "add_purchase", 1, "block", f"{amount} exceeds balance")
            return {"status": "refused", "reason": "Purchase is larger than the balance."}
        c.execute("UPDATE accounts SET balance = balance - ? WHERE id=?", (amount, account_id))
        c.execute("INSERT INTO transactions(account_id,ts,amount,category,memo) VALUES(?,?,?,?,?)",
                  (account_id, now().isoformat(), -amount, category, memo or category))
    audit("human", "add_purchase", 1, "allow", f"{amount} {category}")
    return {"status": "ok", "reserve": reserve_status(account_id)}
