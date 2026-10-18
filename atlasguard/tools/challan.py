"""Fee-letter (challan) analysis: read -> extract fields -> check against history.

`parse_challan` is a deterministic parser for letters with labelled lines
(Payee / IBAN / Amount due / Due date). For free-form letters the AI agent reads the
text itself and then calls `check_new_challan` with the fields it found.
"""
import datetime as dt
import re

from ..sandbox.db import audit
from . import documents, memory, routes

CURRENCIES = "EUR|USD|GBP|CAD|AUD|PKR"
DATE_FORMATS = ["%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]


def _parse_date(s: str) -> str | None:
    s = s.strip().rstrip(".")
    for f in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    return None


def parse_challan(text: str) -> dict:
    payee = re.search(r"(?:Payee|Beneficiary|Pay to)\s*[:\-]\s*(.+)", text, re.I)
    iban = re.search(r"(?:IBAN|Account(?: number)?)\s*(?:\(IBAN\))?\s*[:\-]\s*"
                     r"([A-Z]{2}\d{2}[A-Z0-9 ]{10,32})", text)
    amt = re.search(rf"(?:Amount(?: due)?|Total(?: due)?)\s*[:\-]\s*(?:({CURRENCIES})\s*)?"
                    rf"([\d,]+(?:\.\d+)?)\s*({CURRENCIES})?", text, re.I)
    due = re.search(r"(?im)^\s*Due(?: date)?\s*[:\-]\s*([^\n]+)", text)
    fields = {
        "payee": payee.group(1).strip() if payee else None,
        "iban": re.sub(r"\s+$", "", iban.group(1)).strip() if iban else None,
        "amount": float(amt.group(2).replace(",", "")) if amt else None,
        "currency": ((amt.group(1) or amt.group(3) or "").upper() or None) if amt else None,
        "due_date": _parse_date(due.group(1)) if due else None,
    }
    fields["missing"] = [k for k in ("payee", "iban", "amount", "currency", "due_date")
                         if not fields[k]]
    return fields


def analyze_challan(path: str, account_id: str = "ACC-001") -> dict:
    """One call for the screen's upload box: fields + history check + route advice."""
    doc = documents.read_document(path)
    f = parse_challan(doc["text"])
    if f["missing"]:
        return {"status": "needs_review", "fields": f, "security_scan": doc["security_scan"],
                "note": "Some fields could not be read. A human must check the letter."}
    check = memory.check_new_challan(f["payee"], f["iban"], f["amount"], f["currency"], doc["text"])
    out = {"status": "ok", "fields": f, "check": check, "security_scan": doc["security_scan"],
           "routes": None}
    if check["allow_payment"]:
        try:
            from ..sandbox.db import conn
            with conn() as c:
                cur = c.execute("SELECT currency FROM accounts WHERE id=?", (account_id,)).fetchone()
            out["routes"] = routes.compare_routes(cur["currency"], f["currency"], f["amount"],
                                                  f["due_date"])
        except Exception as e:  # e.g. no rate available
            out["routes_error"] = str(e)
    audit("agent", "analyze_challan", 1, "allow" if check["allow_payment"] else "block",
          f"{path}: payee={f['payee']} level={check['level']}")
    return out
