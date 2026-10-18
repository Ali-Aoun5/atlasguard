"""Guardian: deterministic permission tiers and fraud rules.

These are plain code rules, NOT an LLM opinion, so they cannot be talked out of
a decision. The LLM is only used elsewhere to phrase explanations.

Tiers
  0  read-only (balances, history)
  1  compute / draft (comparisons, forecasts, draft transfers) - no money moves
  2  execute - needs a human confirmation token, verified beneficiary, limits
  3  blocked - always refused
"""
import re
from dataclasses import dataclass, field

from ..sandbox.db import conn, get_setting, now

INJECTION_PATTERNS = [
    r"ignore (all |any |your |the )?(previous|prior|above)? ?(instructions|rules|limits)",
    r"disregard (the |your )?(rules|limits|instructions)",
    r"you are now",
    r"system prompt",
    r"override (the )?(limit|guardian|security)",
    r"(transfer|send|wire|pay)\b.{0,40}\b(immediately|now|without (confirmation|asking))",
    r"do not (tell|inform|ask) the user",
    r"skip (the )?(confirmation|verification|guardian)",
]
URGENCY_PATTERNS = [
    r"\burgent(ly)?\b", r"\bwithin (24|12|2) hours\b", r"\bfinal (notice|warning)\b",
    r"\baccount (will be )?(closed|suspended)\b", r"\bchanged? (our |the )?(bank|account)\b",
    r"\bnew (bank )?account (details|number)\b", r"\bpay(ment)? today\b",
]


@dataclass
class Decision:
    verdict: str            # "allow" | "confirm" | "block"
    tier: int
    reasons: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "tier": self.tier, "reasons": self.reasons}


def _norm_iban(s: str) -> str:
    return re.sub(r"\s+", "", s or "").upper()


def scan_text(text: str) -> dict:
    """Scan untrusted document/message text for injection and scam signals."""
    t = text or ""
    inj = [p for p in INJECTION_PATTERNS if re.search(p, t, re.I)]
    urg = [p for p in URGENCY_PATTERNS if re.search(p, t, re.I)]
    return {"injection_hits": len(inj), "urgency_hits": len(urg),
            "injection_patterns": inj, "urgency_patterns": urg}


def check_transfer(account_id: str, beneficiary_id: str, send_amount: float,
                   claimed_iban: str | None = None, source_text: str | None = None,
                   for_execution: bool = False) -> Decision:
    reasons: list[str] = []
    with conn() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        ben = c.execute("SELECT * FROM beneficiaries WHERE id=?", (beneficiary_id,)).fetchone()
        today = now().date().isoformat()
        spent_today = -sum(r["amount"] for r in c.execute(
            "SELECT amount FROM transactions WHERE account_id=? AND category='transfer_out' "
            "AND substr(ts,1,10)=?", (account_id, today)))

    if not acc:
        return Decision("block", 3, ["Unknown account."])
    if send_amount is None or send_amount <= 0:
        return Decision("block", 3, ["Amount must be positive."])
    if not ben:
        return Decision("block", 3, ["Beneficiary is not in the verified registry."])
    if not ben["verified"]:
        return Decision("block", 3, ["Beneficiary exists but is not verified."])

    if claimed_iban and _norm_iban(claimed_iban) != _norm_iban(ben["iban"]):
        return Decision("block", 3, [
            "Account details in the request do not match the verified registry "
            "(possible changed-account-details fraud)."])

    if source_text:
        sc = scan_text(source_text)
        if sc["injection_hits"]:
            return Decision("block", 3, [
                "Instruction-like text found inside an uploaded document/message. "
                "Documents are untrusted data and cannot trigger payments."])
        if sc["urgency_hits"] >= 2:
            reasons.append("Multiple urgency/pressure signals in the request; "
                           "verify with the beneficiary through a known channel.")

    if acc["balance"] < send_amount:
        return Decision("block", 3, ["Insufficient balance."])

    limit = float(get_setting("daily_limit_pkr", "2000000"))
    if spent_today + send_amount > limit:
        return Decision("block", 3, [
            f"Daily limit exceeded ({spent_today + send_amount:,.0f} > {limit:,.0f})."])

    # First payment to a brand-new payee is capped until it has a payment history.
    with conn() as c:
        history = c.execute("SELECT COUNT(*) n FROM payments WHERE beneficiary_id=?",
                            (beneficiary_id,)).fetchone()["n"]
    new_limit = float(get_setting("new_beneficiary_limit_pkr", "0"))
    if history == 0 and new_limit > 0 and send_amount > new_limit:
        return Decision("block", 3, [
            f"First payment to a new payee is capped at {new_limit:,.0f} until the payee has "
            f"a payment history ({send_amount:,.0f} requested)."])

    reasons.append("Beneficiary verified; details match; within daily limit.")
    return Decision("allow" if for_execution else "confirm", 2, reasons)
