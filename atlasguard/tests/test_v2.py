"""Tests for v2: memory, reserve, deadline routes, log chain, letters, attacks, evaluation."""
import datetime as dt
import os

from atlasguard import attacks, evaluate
from atlasguard.sandbox import db
from atlasguard.sandbox.db import conn
from atlasguard.tools import challan, memory, reserve, routes, transfers

UNI = "Example University Bursar"
IBAN = "DE89 3704 0044 0532 0130 00"
SAMPLES = attacks.SAMPLES


def setup_function(_):
    db.init_db(reset=True)


def test_usual_payment_green():
    assert memory.check_new_challan(UNI, IBAN, 3000, "EUR", "")["level"] == "green"


def test_lookalike_account_red():
    r = memory.check_new_challan(UNI, "DE89 3704 0044 0532 0130 09", 3000, "EUR", "")
    assert r["level"] == "red" and any("look-alike" in x for x in r["reasons"])


def test_amount_deviation_amber():
    assert memory.check_new_challan(UNI, IBAN, 4500, "EUR", "")["level"] == "amber"


def test_unknown_payee_red():
    assert memory.check_new_challan("Nobody Ltd", "DE55 9999 8888 7777 6666 55", 5, "EUR", "")["level"] == "red"


def test_reserve_amber_then_red():
    r = reserve.reserve_status()
    a = reserve.add_purchase("ACC-001", r["free_to_spend"] - 0.1 * r["reserved"])["reserve"]
    assert a["level"] == "amber"
    b = reserve.add_purchase("ACC-001", a["free_to_spend"] + 1)["reserve"]
    assert b["level"] == "red"


def test_real_bill_replaces_prediction():
    due = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    reserve.add_obligation("ACC-001", "BEN-UNI", "Spring tuition", 3000, "EUR", due)
    uni = [b for b in reserve.reserve_status()["bills"] if "uni" in b["label"].lower()
           or "tuition" in b["label"].lower()]
    assert len(uni) == 1


def test_deadline_routes():
    ok = routes.compare_routes("PKR", "EUR", 3000, (dt.date.today() + dt.timedelta(days=10)).isoformat())
    assert ok["recommended"]
    late = routes.compare_routes("PKR", "EUR", 3000, (dt.date.today() + dt.timedelta(days=1)).isoformat())
    assert late["recommended"] is None and late["deadline_note"]


def test_total_cost_includes_fx_margin():
    for q in routes.compare_routes("PKR", "EUR", 3000)["quotes"]:
        assert q["total_cost"] >= q["fee"]


def test_hash_chain_tamper_detected():
    db.audit("t", "x", 0, "allow", "one")
    db.audit("t", "x", 0, "allow", "two")
    assert db.verify_audit_log()["ok"]
    with conn() as c:
        c.execute("UPDATE audit_log SET detail='edited' WHERE id=1")
    assert not db.verify_audit_log()["ok"]


def test_sample_letters():
    g = challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_genuine.pdf"))
    assert g["check"]["level"] == "green" and g["fields"]["due_date"] == "2026-11-05"
    assert challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_scam.pdf"))["check"]["level"] == "red"
    assert challan.analyze_challan(os.path.join(SAMPLES, "fee_letter_injection.pdf"))["check"]["level"] == "red"


def test_confirm_records_payment():
    before = memory.payee_profile("BEN-UNI")["payments"]
    d = transfers.draft_transfer("ACC-001", "BEN-UNI", 3000, "EUR", "Remit App B (simulated)")
    transfers.confirm_transfer(d["pending_id"], transfers.get_confirmation_token(d["pending_id"]))
    assert memory.payee_profile("BEN-UNI")["payments"] == before + 1


def test_new_payee_first_payment_cap():
    with conn() as c:
        c.execute("INSERT INTO beneficiaries VALUES('BEN-X','X Ltd','B','DE11 1111 1111 1111 1111 11','EUR',1)")
    d = transfers.draft_transfer("ACC-001", "BEN-X", 3000, "EUR", "Remit App B (simulated)")
    assert d["status"] == "blocked"


def test_all_attacks_pass_and_known_gap_reported():
    res = attacks.run_attacks()
    assert res["passed"] == res["total"], [r for r in res["results"] if not r["passed"] and not r["known_limit"]]
    assert len(res["known_gaps"]) == 1


def test_evaluation_all_pass():
    rep = evaluate.run_evaluation(write=False)
    assert rep["tasks"]["passed"] == rep["tasks"]["total"]
    assert rep["attacks"]["passed"] == rep["attacks"]["total"]
