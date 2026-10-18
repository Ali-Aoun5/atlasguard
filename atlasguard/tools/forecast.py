"""Cash-flow forecast from the account's own transaction history."""
import datetime as dt

from ..sandbox.db import conn, now


def forecast_budget(account_id: str, obligation_amount: float = 0.0,
                    obligation_due: str | None = None, lookback_days: int = 60,
                    transfer_hours: int = 48) -> dict:
    since = (now() - dt.timedelta(days=lookback_days)).isoformat()
    with conn() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not acc:
            raise ValueError("unknown account")
        rows = c.execute(
            "SELECT amount, category FROM transactions WHERE account_id=? AND ts>=?",
            (account_id, since)).fetchall()
    spend = -sum(r["amount"] for r in rows if r["amount"] < 0)
    income = sum(r["amount"] for r in rows if r["amount"] > 0)
    daily_spend = spend / lookback_days
    daily_income = income / lookback_days
    net_daily = daily_spend - daily_income
    balance = acc["balance"]
    out = {
        "balance": round(balance, 2),
        "avg_daily_spend": round(daily_spend, 2),
        "avg_daily_income": round(daily_income, 2),
        "net_daily_burn": round(net_daily, 2),
        "lookback_days": lookback_days,
    }
    out["runway_days"] = round(balance / net_daily, 1) if net_daily > 0 else None
    if obligation_amount and obligation_due:
        due = dt.date.fromisoformat(obligation_due)
        days_left = (due - now().date()).days
        projected = balance - net_daily * max(days_left, 0) - obligation_amount
        send_by = due - dt.timedelta(hours=transfer_hours + 24)
        out.update({
            "obligation_amount": obligation_amount,
            "due": obligation_due,
            "days_left": days_left,
            "projected_balance_after_obligation": round(projected, 2),
            "shortfall": round(-projected, 2) if projected < 0 else 0.0,
            "send_by": send_by.isoformat(),
            "warning": ("Projected balance goes negative; arrange more funds before sending."
                        if projected < 0 else None),
        })
    return out
