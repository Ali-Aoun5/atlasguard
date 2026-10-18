"""Transfer-route comparison. All arithmetic is deterministic code (never the LLM).

IMPORTANT HONESTY NOTE: the provider fee/margin/speed numbers below are
ASSUMED pricing parameters for a simulated market, not quotes from real
companies. They are configurable and flagged `assumed_pricing` in every
result. The mid-market rate itself comes from tools.fx (real data).

v2: every quote shows the hidden exchange-rate cost next to the visible fee
(`total_cost`), and an optional `due_date` makes the result deadline-aware: the
recommendation is the cheapest route that arrives in time (1 day safety buffer).
"""
import datetime as dt

from ..sandbox.db import now
from . import fx

PROVIDERS = [
    # name, fixed fee (in source currency), percent fee, FX margin vs mid-market, hours
    {"name": "Bank Wire (simulated)", "fixed": 4500.0, "pct": 0.000, "margin": 0.0300, "hours": 72},
    {"name": "Remit App A (simulated)", "fixed": 600.0, "pct": 0.006, "margin": 0.0100, "hours": 24},
    {"name": "Remit App B (simulated)", "fixed": 0.0, "pct": 0.012, "margin": 0.0050, "hours": 12},
    {"name": "Fintech Card Transfer (simulated)", "fixed": 250.0, "pct": 0.004, "margin": 0.0150, "hours": 48},
]

SAFETY_BUFFER_HOURS = 24


def quote(provider: dict, target_amount: float, mid_rate: float) -> dict:
    """Amount of source currency needed so the recipient receives exactly
    `target_amount`. mid_rate = units of target per 1 unit of source."""
    eff = mid_rate * (1 - provider["margin"])
    # recipient gets (send - fee) * eff, fee = fixed + pct * send
    send = (target_amount / eff + provider["fixed"]) / (1 - provider["pct"])
    fee = provider["fixed"] + provider["pct"] * send
    fx_cost = (target_amount / eff) - (target_amount / mid_rate)
    return {
        "provider": provider["name"],
        "send_amount": round(send, 2),
        "fee": round(fee, 2),
        "fx_margin_cost": round(fx_cost, 2),
        "total_cost": round(fee + fx_cost, 2),
        "effective_rate": round(eff, 6),
        "hours": provider["hours"],
        "assumed_pricing": True,
    }


def compare_routes(source_currency: str, target_currency: str, target_amount: float,
                   due_date: str | None = None) -> dict:
    if target_amount <= 0:
        raise ValueError("target_amount must be positive")
    rate = fx.get_rate(source_currency, target_currency)
    quotes = [quote(p, target_amount, rate["rate"]) for p in PROVIDERS]
    quotes.sort(key=lambda q: q["send_amount"])
    cheapest = quotes[0]
    fastest = min(quotes, key=lambda q: q["hours"])
    for q in quotes:
        q["extra_vs_cheapest"] = round(q["send_amount"] - cheapest["send_amount"], 2)

    days_left = None
    note = None
    if due_date:
        days_left = (dt.date.fromisoformat(due_date) - now().date()).days
        usable_hours = max(days_left * 24 - SAFETY_BUFFER_HOURS, 0)
        for q in quotes:
            q["on_time"] = q["hours"] <= usable_hours
        on_time = [q for q in quotes if q["on_time"]]
        recommended = on_time[0] if on_time else None
        if recommended is None:
            note = ("No route can deliver before the deadline with a 1-day safety buffer. "
                    "Contact the payee about the deadline.")
        elif recommended is not cheapest:
            note = (f"The cheapest route ({cheapest['provider']}) would arrive too late. "
                    f"Recommended: {recommended['provider']}.")
    else:
        recommended = cheapest

    return {
        "source_currency": source_currency.upper(),
        "target_currency": target_currency.upper(),
        "target_amount": target_amount,
        "mid_market_rate": rate["rate"],
        "rate_source": rate["source"],
        "rate_as_of": rate["as_of"],
        "quotes": quotes,
        "cheapest": cheapest["provider"],
        "fastest": fastest["provider"],
        "due_date": due_date,
        "days_left": days_left,
        "recommended": recommended["provider"] if recommended else None,
        "deadline_note": note,
    }
