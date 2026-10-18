"""Draft -> human confirm -> execute.

Key security property: the LLM can only DRAFT. Execution requires a one-time
token that is shown to the human in the UI/CLI and entered by the human. The
LLM never sees the token and has no execute tool. The Guardian is re-run at
execution time so conditions cannot change between draft and confirm.
"""
import hmac
import secrets

from ..guardian.rules import check_transfer
from ..sandbox.db import audit, conn, now
from . import routes


def draft_transfer(account_id: str, beneficiary_id: str, target_amount: float,
                   target_currency: str, provider_name: str,
                   claimed_iban: str | None = None, source_text: str | None = None) -> dict:
    with conn() as c:
        acc = c.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not acc:
        return {"status": "blocked", "reasons": ["Unknown account."]}
    comp = routes.compare_routes(acc["currency"], target_currency, target_amount)
    q = next((x for x in comp["quotes"] if x["provider"] == provider_name), None)
    if not q:
        return {"status": "blocked", "reasons": ["Unknown provider."]}

    d = check_transfer(account_id, beneficiary_id, q["send_amount"], claimed_iban, source_text)
    audit("agent", "draft_transfer", d.tier, d.verdict,
          f"{account_id}->{beneficiary_id} {q['send_amount']} via {provider_name}: {d.reasons}")
    if d.verdict == "block":
        return {"status": "blocked", "tier": d.tier, "reasons": d.reasons}

    pid = "TRF-" + secrets.token_hex(4).upper()
    token = secrets.token_hex(3).upper()
    with conn() as c:
        c.execute(
            "INSERT INTO pending_transfers VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (pid, account_id, beneficiary_id, provider_name, q["send_amount"], target_amount,
             target_currency.upper(), q["fee"], token, "pending", now().isoformat()))
    # NOTE: token is intentionally NOT returned to the agent. The UI fetches it
    # via get_confirmation_token() for the human only.
    return {"status": "pending_human_confirmation", "pending_id": pid, "tier": d.tier,
            "send_amount": q["send_amount"], "fee": q["fee"], "target_amount": target_amount,
            "target_currency": target_currency.upper(), "provider": provider_name,
            "hours": q["hours"], "guardian_notes": d.reasons,
            "instruction": "Ask the user to confirm in the app. You cannot execute this."}


def get_pending(pending_id: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM pending_transfers WHERE id=?", (pending_id,)).fetchone()
    return dict(r) if r else None


def get_confirmation_token(pending_id: str) -> str | None:
    """For the human-facing UI only. Never expose this to the LLM."""
    p = get_pending(pending_id)
    return p["token"] if p and p["status"] == "pending" else None


def confirm_transfer(pending_id: str, human_token: str) -> dict:
    p = get_pending(pending_id)
    if not p or p["status"] != "pending":
        audit("human", "confirm_transfer", 3, "block", f"{pending_id}: not pending")
        return {"status": "failed", "reasons": ["No such pending transfer."]}
    if not hmac.compare_digest(p["token"], (human_token or "").strip().upper()):
        audit("human", "confirm_transfer", 3, "block", f"{pending_id}: bad token")
        return {"status": "failed", "reasons": ["Wrong confirmation token."]}

    d = check_transfer(p["account_id"], p["beneficiary_id"], p["send_amount"], for_execution=True)
    if d.verdict != "allow":
        with conn() as c:
            c.execute("UPDATE pending_transfers SET status='rejected' WHERE id=?", (pending_id,))
        audit("guardian", "confirm_transfer", d.tier, "block", f"{pending_id}: {d.reasons}")
        return {"status": "blocked", "reasons": d.reasons}

    ts = now().isoformat()
    with conn() as c:
        c.execute("UPDATE accounts SET balance = balance - ? WHERE id=?",
                  (p["send_amount"], p["account_id"]))
        c.execute("INSERT INTO transactions(account_id,ts,amount,category,memo) VALUES(?,?,?,?,?)",
                  (p["account_id"], ts, -p["send_amount"], "transfer_out",
                   f"{pending_id} to {p['beneficiary_id']} via {p['provider']}"))
        c.execute("UPDATE pending_transfers SET status='executed' WHERE id=?", (pending_id,))
        ben = c.execute("SELECT iban FROM beneficiaries WHERE id=?",
                        (p["beneficiary_id"],)).fetchone()
        # Remember this payment: the payment memory grows with every confirmed transfer.
        c.execute("INSERT INTO payments(account_id,beneficiary_id,iban,amount,currency,ts,source) "
                  "VALUES(?,?,?,?,?,?,?)",
                  (p["account_id"], p["beneficiary_id"], ben["iban"] if ben else "",
                   p["target_amount"], p["target_currency"], ts, "atlasguard"))
    audit("human", "confirm_transfer", 2, "allow", f"{pending_id} executed in SANDBOX")
    return {"status": "executed_in_sandbox", "pending_id": pending_id,
            "debited": p["send_amount"], "beneficiary": p["beneficiary_id"], "ts": ts}
