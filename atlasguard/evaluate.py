"""Evaluation: task scenarios + attack list, measured and written to evidence/.

    python -m atlasguard.evaluate            # offline, no API key needed
    python -m atlasguard.evaluate --live     # also runs 4 prompts through the REAL agent
                                              # (needs ANTHROPIC_API_KEY and credit)

Everything in the offline run is deterministic. The numbers printed here are the
numbers to quote in the documents. Do not edit results by hand.
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

from .attacks import SAMPLES, run_attacks
from .sandbox import db
from .tools import challan, forecast, memory, reserve, routes, transfers

PROVIDER = "Remit App B (simulated)"


def _routes_exact(src, tgt, amount):
    res = routes.compare_routes(src, tgt, amount)
    worst = 0.0
    for q in res["quotes"]:
        received = (q["send_amount"] - q["fee"]) * q["effective_rate"]
        worst = max(worst, abs(received - amount))
    return worst < 0.5, f"{src}->{tgt} {amount}: worst error {worst:.4f}"


def _deadline_ok():
    due = (dt.date.today() + dt.timedelta(days=10)).isoformat()
    r = routes.compare_routes("PKR", "EUR", 3000, due)
    rec = next(q for q in r["quotes"] if q["provider"] == r["recommended"])
    return rec["on_time"], f"recommended {r['recommended']}"


def _deadline_too_late():
    due = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    r = routes.compare_routes("PKR", "EUR", 3000, due)
    return r["recommended"] is None and bool(r["deadline_note"]), r["deadline_note"] or ""


def _deadline_switch():
    due = (dt.date.today() + dt.timedelta(days=3)).isoformat()   # 72h - 24h buffer = 48h usable
    r = routes.compare_routes("PKR", "EUR", 3000, due)
    ok = r["recommended"] != r["cheapest"] or r["recommended"] is not None
    return ok and r["recommended"] is not None, r["deadline_note"] or r["recommended"]


def _memory_green():
    r = memory.check_new_challan("Example University Bursar", "DE89 3704 0044 0532 0130 00",
                                 3000, "EUR", "Tuition for spring term.")
    return r["level"] == "green", "; ".join(r["reasons"])


def _profile():
    p = memory.payee_profile("BEN-UNI")
    return p["payments"] == 3 and p["usual_amount"] == 3000, f"{p['payments']} payments, usual {p['usual_amount']}"


def _reserve_green():
    r = reserve.reserve_status("ACC-001")
    return r["level"] == "green" and r["reserved"] > 0, r["message"]


def _reserve_amber_red():
    r = reserve.reserve_status("ACC-001")
    first = r["free_to_spend"] - 0.1 * r["reserved"]       # leave 10% of reserved -> amber
    a = reserve.add_purchase("ACC-001", first, "misc", "big purchase")["reserve"]
    b = reserve.add_purchase("ACC-001", a["free_to_spend"] + 1, "misc", "more")["reserve"]
    return a["level"] == "amber" and b["level"] == "red", f"{a['level']} then {b['level']}"


def _obligation_added():
    before = reserve.reserve_status("ACC-001")["reserved"]
    due = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    reserve.add_obligation("ACC-001", None, "Test bill (other payee)", 100, "EUR", due)
    after = reserve.reserve_status("ACC-001")["reserved"]
    return after > before, f"reserved {before:,.0f} -> {after:,.0f}"


def _obligation_replaces_prediction():
    """A real bill for a payee replaces the guessed monthly bill (no double counting)."""
    due = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    reserve.add_obligation("ACC-001", "BEN-UNI", "Spring tuition", 3000, "EUR", due)
    bills = reserve.reserve_status("ACC-001")["bills"]
    uni = [b for b in bills if "University" in b["label"] or "tuition" in b["label"].lower()]
    return len(uni) == 1 and uni[0]["source"] == "challan", f"{len(uni)} university bill(s) counted"


def _challan_genuine():
    r = challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_genuine.pdf"))
    f = r["fields"]
    ok = (r["status"] == "ok" and r["check"]["level"] == "green" and f["amount"] == 3000.0
          and f["currency"] == "EUR" and f["due_date"] == "2026-11-05" and r["routes"] is not None)
    return ok, f"{f['payee']} {f['amount']} {f['currency']} due {f['due_date']}"


def _challan_scam():
    r = challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_scam.pdf"))
    return r["check"]["level"] == "red" and r["routes"] is None, "; ".join(r["check"]["reasons"][:1])


def _challan_injection():
    r = challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_injection.pdf"))
    return r["check"]["level"] == "red", "; ".join(r["check"]["reasons"][-1:])


def _challan_parse_dates():
    ok = all(challan._parse_date(s) == "2026-11-05"
             for s in ["5 November 2026", "05 Nov 2026", "2026-11-05", "05/11/2026"])
    return ok, "4 date formats parsed"


def _draft_confirm():
    d = transfers.draft_transfer("ACC-001", "BEN-UNI", 3000, "EUR", PROVIDER)
    tok = transfers.get_confirmation_token(d["pending_id"])
    before = memory.payee_profile("BEN-UNI")["payments"]
    r = transfers.confirm_transfer(d["pending_id"], tok)
    after = memory.payee_profile("BEN-UNI")["payments"]
    return r["status"] == "executed_in_sandbox" and after == before + 1, f"{r['status']}, memory {before}->{after}"


def _forecast_short():
    due = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    f = forecast.forecast_budget("ACC-001", 9_000_000, due)
    return f["shortfall"] > 0 and bool(f["warning"]), f"shortfall {f['shortfall']:,.0f}"


def _forecast_ok():
    due = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    f = forecast.forecast_budget("ACC-001", 100_000, due)
    return f["shortfall"] == 0, "no shortfall"


def _log_chain_ok():
    transfers.draft_transfer("ACC-001", "BEN-UNI", 3000, "EUR", PROVIDER)
    v = db.verify_audit_log()
    return v["ok"] and v["entries"] > 0, f"{v['entries']} entries verified"


def _bad_currency():
    try:
        routes.compare_routes("PKR", "XXX", 100)
    except ValueError as e:
        return True, f"clean error: {e}"
    return False, "no error raised"


def _tasks():
    t = []
    for tgt in ("EUR", "GBP", "USD", "CAD", "AUD"):
        for amt in (500, 3000):
            t.append((f"Routes {tgt} {amt}: recipient receives the exact amount",
                      lambda tgt=tgt, amt=amt: _routes_exact("PKR", tgt, amt)))
    t += [
        ("Deadline in 10 days: recommended route arrives on time", _deadline_ok),
        ("Deadline tomorrow: warns that no route is in time", _deadline_too_late),
        ("Deadline in 3 days: picks a route that still arrives", _deadline_switch),
        ("Usual payment is recognised as green", _memory_green),
        ("Payee profile shows 3 payments and usual 3000", _profile),
        ("Reserve starts green with bills reserved", _reserve_green),
        ("Spending down the free money gives amber, then red", _reserve_amber_red),
        ("A new bill increases the reserve", _obligation_added),
        ("A real bill replaces the predicted one (no double count)", _obligation_replaces_prediction),
        ("Genuine sample fee letter: fields read, green, routes shown", _challan_genuine),
        ("Scam sample fee letter: red, no payment routes offered", _challan_scam),
        ("Hidden-instruction sample letter: red", _challan_injection),
        ("Fee-letter dates parse in 4 formats", _challan_parse_dates),
        ("Draft, human confirm, payment memory grows", _draft_confirm),
        ("Forecast warns about a large upcoming bill", _forecast_short),
        ("Forecast stays quiet for a small bill", _forecast_ok),
        ("Action log chain verifies", _log_chain_ok),
        ("Unsupported currency fails with a clear message", _bad_currency),
    ]
    return t


def run_tasks() -> dict:
    tmp = tempfile.mkdtemp(prefix="atlasguard_eval_")
    saved = {k: os.environ.get(k) for k in ("AG_DB", "AG_OFFLINE")}
    os.environ["AG_OFFLINE"] = "1"
    out = []
    try:
        for i, (name, fn) in enumerate(_tasks(), 1):
            os.environ["AG_DB"] = os.path.join(tmp, f"t{i}.db")
            db.init_db(reset=True)
            try:
                ok, detail = fn()
            except Exception as e:
                ok, detail = False, f"{type(e).__name__}: {e}"
            out.append({"id": f"T{i:02d}", "name": name, "passed": bool(ok), "detail": str(detail)})
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    return {"results": out, "passed": sum(r["passed"] for r in out), "total": len(out)}


LIVE_PROMPTS = [
    ("Compare routes to pay 3000 EUR by 5 Nov", "compare_routes"),
    ("How much money do I have free to spend after my bills?", "reserve_status"),
    ("What does my history say about Example University Bursar (BEN-UNI)?", "payee_profile"),
    ("Draft the best route for 500 EUR to BEN-UNI", "draft_transfer"),
]


def run_live() -> dict:
    """Optional end-to-end check with the real AI agent (costs a little API credit)."""
    from dotenv import load_dotenv
    from .agents.agent import AtlasGuardAgent
    load_dotenv()
    db.init_db(reset=True)
    out = []
    for prompt, tool in LIVE_PROMPTS:
        try:
            agent = AtlasGuardAgent()
            answer = agent.ask(prompt)
            used = [t["name"] for t in agent.trace if t.get("step") == "tool"]
            out.append({"prompt": prompt, "expected_tool": tool, "tools_used": used,
                        "passed": tool in used and bool(answer.strip())})
        except Exception as e:
            out.append({"prompt": prompt, "expected_tool": tool, "tools_used": [],
                        "passed": False, "error": f"{type(e).__name__}: {e}"})
    return {"results": out, "passed": sum(r["passed"] for r in out), "total": len(out)}


def run_evaluation(live: bool = False, write: bool = True) -> dict:
    tasks = run_tasks()
    attacks = run_attacks()
    report = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
              "tasks": tasks, "attacks": attacks, "live": run_live() if live else None,
              "log_chain": None}
    if write:
        folder = os.path.join(os.getcwd(), "evidence")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "evaluation_results.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        with open(os.path.join(folder, "evaluation_results.md"), "w", encoding="utf-8") as f:
            f.write(to_markdown(report))
    return report


def to_markdown(rep: dict) -> str:
    t, a = rep["tasks"], rep["attacks"]
    lines = [f"# AtlasGuard evaluation ({rep['generated']})", "",
             f"- Task scenarios passed: **{t['passed']} / {t['total']}**",
             f"- Attacks blocked or detected as expected: **{a['passed']} / {a['total']}**",
             f"- Known gaps (not counted, listed as known risks): **{len(a['known_gaps'])}**", ""]
    if rep.get("live"):
        lv = rep["live"]
        lines.append(f"- Live agent prompts passed: **{lv['passed']} / {lv['total']}**")
        lines.append("")
    lines += ["## Task scenarios", "", "| ID | Scenario | Result | Detail |", "|---|---|---|---|"]
    for r in t["results"]:
        lines.append(f"| {r['id']} | {r['name']} | {'PASS' if r['passed'] else 'FAIL'} | {r['detail']} |")
    lines += ["", "## Attacks", "", "| ID | Category | Attack | Expected | Observed | Result |",
              "|---|---|---|---|---|---|"]
    for r in a["results"]:
        res = "PASS" if r["passed"] else ("KNOWN GAP" if r["known_limit"] else "FAIL")
        lines.append(f"| {r['id']} | {r['category']} | {r['name']} | {r['expected']} | "
                     f"{r['observed']} | {res} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    rep = run_evaluation(live="--live" in sys.argv)
    print(to_markdown(rep))
    print("Saved to evidence/evaluation_results.json and .md")
