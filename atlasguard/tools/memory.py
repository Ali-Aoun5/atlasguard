"""Payment memory: compare a new payment request with the student's own history.

This is pattern checking on past payments (not a trained ML model), so every
verdict can be explained in one sentence. Levels:
  green  - matches what the student normally pays
  amber  - allowed, but check carefully
  red    - blocked (never paid this account / look-alike account / unknown payee /
           instructions aimed at an AI)
"""
import datetime as dt
import re
import statistics

from ..guardian.rules import scan_text
from ..sandbox.db import audit, conn

LOOKALIKE_MAX_DISTANCE = 3      # account numbers this close to a known one look suspicious
AMOUNT_DEVIATION_AMBER = 0.20   # more than 20% away from the usual amount


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "").upper()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _payees() -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM beneficiaries")]


def payee_profile(beneficiary_id: str) -> dict:
    """What the system remembers about one payee (the 'Trust Card')."""
    with conn() as c:
        ben = c.execute("SELECT * FROM beneficiaries WHERE id=?", (beneficiary_id,)).fetchone()
        rows = c.execute("SELECT * FROM payments WHERE beneficiary_id=? ORDER BY ts",
                         (beneficiary_id,)).fetchall()
    if not ben:
        return {"error": "Unknown payee."}
    pays = [dict(r) for r in rows]
    last3 = [p["amount"] for p in pays[-3:]]
    return {
        "id": ben["id"], "name": ben["name"], "bank": ben["bank"], "iban": ben["iban"],
        "currency": ben["currency"], "verified": bool(ben["verified"]),
        "payments": len(pays),
        "first_seen": pays[0]["ts"][:10] if pays else None,
        "last_paid": pays[-1]["ts"][:10] if pays else None,
        "usual_amount": statistics.median(last3) if last3 else None,
        "accounts_used": sorted({_norm(p["iban"]) for p in pays}),
        "history": [{"date": p["ts"][:10], "amount": p["amount"], "currency": p["currency"]}
                    for p in pays],
    }


def check_new_challan(beneficiary_name: str, claimed_iban: str, amount: float | None = None,
                      currency: str | None = None, message_text: str = "") -> dict:
    """Check a new fee letter / payment request against payment history."""
    reasons: list[str] = []
    level = "green"
    payee_id = None
    usual = None
    deviation = None

    payees = _payees()
    iban_n = _norm(claimed_iban)
    by_name = next((p for p in payees
                    if p["name"].strip().lower() == (beneficiary_name or "").strip().lower()), None)
    exact = next((p for p in payees if iban_n and _norm(p["iban"]) == iban_n), None)
    near = [(p, levenshtein(iban_n, _norm(p["iban"]))) for p in payees if iban_n]
    near = [(p, d) for p, d in near if 0 < d <= LOOKALIKE_MAX_DISTANCE]

    sc = scan_text(message_text)

    def red(msg: str):
        nonlocal level
        level = "red"
        reasons.append(msg)

    if not iban_n:
        red("No account number was found in the request.")
    elif exact and by_name and exact["id"] == by_name["id"]:
        payee_id = exact["id"]
        prof = payee_profile(payee_id)
        usual = prof["usual_amount"]
        if prof["payments"] == 0:
            level = "amber"
            reasons.append("Verified payee, but you have never paid them before. "
                           "Check the letter carefully.")
        else:
            reasons.append(f"Matches your payment history: {prof['payments']} earlier payment(s) "
                           f"to this payee and account.")
        if usual and amount is not None and (currency is None or currency == prof["currency"]):
            deviation = abs(amount - usual) / usual
            if deviation > AMOUNT_DEVIATION_AMBER:
                level = "amber" if level != "red" else level
                reasons.append(f"Amount {amount:,.2f} is {deviation:.0%} away from your usual "
                               f"{usual:,.2f}. Check the letter.")
            else:
                reasons.append(f"Amount is in line with your usual {usual:,.2f}.")
    elif exact and (not by_name or exact["id"] != by_name["id"]):
        payee_id = exact["id"]
        red(f"This account belongs to '{exact['name']}', but the request names "
            f"'{beneficiary_name}'.")
    elif by_name:
        payee_id = by_name["id"]
        close = [p for p, _ in near if p["id"] == by_name["id"]] or [p for p, _ in near]
        if close:
            red(f"Account number looks almost identical to the real account of "
                f"'{close[0]['name']}' (look-alike). Classic scam pattern. Do not pay; "
                f"verify with the payee through a known contact.")
        else:
            red(f"You have never paid this account. '{by_name['name']}' is a known payee, "
                f"but with a different account number. Verify with them before paying.")
    else:
        if near:
            red(f"Account number looks almost identical to the real account of "
                f"'{near[0][0]['name']}' (look-alike). Classic scam pattern.")
        else:
            red("Unknown payee: not on your verified list. Add and verify the payee "
                "yourself first.")

    if sc["injection_hits"]:
        red("The text contains instructions aimed at an AI system. Documents cannot give orders.")
    if sc["urgency_hits"]:
        reasons.append(f"{sc['urgency_hits']} pressure/urgency signal(s) in the message.")
        if level == "green":
            level = "amber"

    allow = level != "red"
    audit("agent", "check_new_challan", 1, "allow" if allow else "block",
          f"{beneficiary_name}: level={level} payee={payee_id}")
    return {"level": level, "allow_payment": allow, "reasons": reasons, "payee_id": payee_id,
            "usual_amount": usual, "deviation_pct": round(deviation * 100, 1) if deviation is not None else None}


def predicted_recurring(account_id: str, horizon_days: int = 30) -> list[dict]:
    """Bills we expect soon because the student paid the same payee about monthly."""
    today = dt.datetime.now()
    out = []
    with conn() as c:
        bens = [dict(r) for r in c.execute("SELECT * FROM beneficiaries")]
        open_ben = {r["beneficiary_id"] for r in c.execute(
            "SELECT beneficiary_id FROM obligations WHERE account_id=? AND status='open'",
            (account_id,))}
        for b in bens:
            if b["id"] in open_ben:
                continue
            pays = [dict(r) for r in c.execute(
                "SELECT * FROM payments WHERE account_id=? AND beneficiary_id=? ORDER BY ts",
                (account_id, b["id"]))]
            dates = [dt.datetime.fromisoformat(p["ts"]) for p in pays]
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            if not any(25 <= g <= 35 for g in gaps):
                continue
            due = dates[-1] + dt.timedelta(days=30)
            if today.date() < due.date() <= (today + dt.timedelta(days=horizon_days)).date():
                out.append({"beneficiary_id": b["id"], "label": f"{b['name']} (usual monthly payment)",
                            "amount": statistics.median([p["amount"] for p in pays[-3:]]),
                            "currency": pays[-1]["currency"], "due_date": due.date().isoformat(),
                            "source": "predicted"})
    return out
