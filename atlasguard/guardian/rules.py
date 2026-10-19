"""Guardian: deterministic permission tiers and fraud rules.

These are plain code rules, NOT an LLM opinion, so they cannot be talked out of
a decision. The LLM is only used elsewhere to phrase explanations.

Tiers
  0  read-only (balances, history)
  1  compute / draft (comparisons, forecasts, draft transfers) - no money moves
  2  execute - needs a human confirmation token, verified beneficiary, limits
  3  blocked - always refused

v2.1 (red-team fix): untrusted text is NORMALISED before it is scanned, and a small,
conservative fuzzy matcher catches misspelled or disguised wording (found by
manual attacks M05/M06 and Attack Lab A20). The fuzzy layer can only ADD signals.
It never removes a signal the original exact rules would have raised.
"""
import re
import unicodedata
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

# ------------------------------------------------------------------ text normalisation
# Cyrillic letters that look like Latin ones (a classic way to dodge keyword filters).
_HOMOGLYPHS = str.maketrans({
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0443": "y", "\u0445": "x", "\u0456": "i", "\u0455": "s", "\u0458": "j",
})
# Digits and symbols commonly used in place of letters ("1gnore", "p@y", "$end").
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def normalize_text(text: str) -> str:
    """Turn disguised text into plain lowercase words so the rules can read it.

    Steps: Unicode fold, drop invisible characters, map look-alike letters, lowercase,
    strip accents, undo digit/symbol swaps, remove separators inside words (i.g.n.o.r.e),
    join letter-spaced words (i g n o r e), and squash long repeated letters.
    """
    t = unicodedata.normalize("NFKC", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Cf")   # zero-width etc.
    t = t.translate(_HOMOGLYPHS).lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.translate(_LEET)
    t = t.replace("-", " ")
    t = re.sub(r"(?<=[a-z])[._*|]+(?=[a-z])", "", t)                   # i.g.n.o.r.e -> ignore
    t = re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda m: m.group(0).replace(" ", ""), t)
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)                               # pleeease -> pleease
    return re.sub(r"\s+", " ", t).strip()                             # after joining, so words stay apart


# ------------------------------------------------------------------ conservative fuzzy matching
def _osa(a: str, b: str) -> int:
    """Edit distance where swapping two neighbouring letters counts as ONE edit."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


# Real words that sit one edit away from a scam word. They must never match fuzzily.
_SAFE = {"charged", "changes", "change", "changer", "changing", "chance", "chanced", "chances",
         "hanged", "urgency", "toady", "holiday", "payday"}


def _close(tok: str, target: str) -> bool:
    """True if tok is the target word or a small typo of it (stricter for short words)."""
    if tok == target:
        return True
    if tok in _SAFE:
        return False
    n = len(target)
    limit = 0 if n <= 4 else (1 if n <= 7 else 2)       # short words must match exactly
    if limit == 0 or abs(len(tok) - n) > limit:
        return False
    return _osa(tok, target) <= limit


_INJ_VERBS = ("ignore", "disregard", "override", "bypass", "disable", "forget", "skip")
_INJ_OBJECTS = ("rules", "instructions", "limits", "guardian", "confirmation",
                "verification", "checks", "guidance", "safeguards")
_FILLERS = {"our", "the", "my", "its", "their", "your", "new"}
# Exact-form regexes for the signals the fuzzy layer can also raise (used to avoid double counting).
_SIGNAL_EXACT = {
    "urgent": r"\burgent(ly)?\b",
    "pay_today": r"\bpay(ment)? today\b",
    "changed_account": r"\bchanged? (our |the )?(bank|account)\b",
}


def _fuzzy_injection(tokens: list) -> list:
    """A command verb (ignore, skip, disable...) followed within 3 words by a safety object."""
    hits = []
    for i, tok in enumerate(tokens):
        verb = next((v for v in _INJ_VERBS if _close(tok, v)), None)
        if not verb:
            continue
        for w in tokens[i + 1:i + 4]:
            obj = next((o for o in _INJ_OBJECTS if _close(w, o)), None)
            if obj:
                hits.append(f"fuzzy:{verb}+{obj}")
                break
    return sorted(set(hits))


def _fuzzy_urgency(tokens: list) -> set:
    found = set()
    for i, tok in enumerate(tokens):
        if _close(tok, "urgent"):
            found.add("urgent")
        if tok in ("pay", "payment") and i + 1 < len(tokens) and _close(tokens[i + 1], "today"):
            found.add("pay_today")
        if _close(tok, "changed"):
            j = i + 1
            while j < len(tokens) and j - i <= 3 and tokens[j] in _FILLERS:
                j += 1
            if j < len(tokens) and (tokens[j] == "bank" or _close(tokens[j], "account")):
                found.add("changed_account")
    return found


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
    """Scan untrusted document/message text for injection and scam signals.

    The exact regexes run on the raw text AND on the normalised text. If they find no
    injection, the fuzzy matcher looks for disguised command wording. Urgency signals
    found only through misspellings are added once, never double counted.
    """
    t = text or ""
    clean = normalize_text(t)
    inj = [p for p in INJECTION_PATTERNS if re.search(p, t, re.I) or re.search(p, clean, re.I)]
    urg = [p for p in URGENCY_PATTERNS if re.search(p, t, re.I) or re.search(p, clean, re.I)]
    tokens = re.findall(r"[a-z]+", clean)
    if not inj:
        inj = _fuzzy_injection(tokens)
    for name in sorted(_fuzzy_urgency(tokens)):
        if not re.search(_SIGNAL_EXACT[name], clean, re.I):
            urg.append(f"fuzzy:{name}")
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