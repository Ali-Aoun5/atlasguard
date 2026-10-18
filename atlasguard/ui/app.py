"""AtlasGuard screen.  Run from the folder that CONTAINS `atlasguard`:

    streamlit run atlasguard/ui/app.py                (real AI, needs ANTHROPIC_API_KEY)
    set AG_MOCK=1 && streamlit run atlasguard/ui/app.py   (demo mode, no key; Windows)

This file talks ONLY to atlasguard/api.py. Do not import anything else from atlasguard.
Hajira: you may change everything in this `ui/` folder freely.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from atlasguard import api  # noqa: E402

st.set_page_config(page_title="AtlasGuard", page_icon="🛡️", layout="wide")
api.start()

COLORS = {"green": "#1b8a3a", "amber": "#d98a00", "red": "#c62828"}
ICON = {"green": "🟢", "amber": "🟠", "red": "🔴"}


def banner(level: str, text: str) -> None:
    st.markdown(
        f"<div style='padding:12px 16px;border-radius:10px;background:{COLORS[level]}22;"
        f"border-left:6px solid {COLORS[level]};margin:8px 0'>"
        f"<b>{ICON[level]} {level.upper()}</b> &nbsp; {text}</div>", unsafe_allow_html=True)


def ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🛡️ AtlasGuard")
    st.caption("Cross-border student finance agent. **Sandbox only - no real money.**")
    if api.is_mock():
        st.warning("Demo mode: real safety rules, no AI service. Set ANTHROPIC_API_KEY for the full AI.")
    page = st.radio("Go to", ["Assistant", "Money", "Payees", "Attack Lab", "Proof Pack"])
    b = api.balance_summary()
    st.metric("Balance", f"{b['balance']:,.0f} {b['currency']}")
    st.caption("Not financial advice. Provider fees are simulated.")


# ------------------------------------------------------------------ Assistant
def confirmation_card(pending_id: str) -> None:
    p = api.pending_info(pending_id)
    if not p:
        return
    with st.container(border=True):
        st.subheader(f"Confirm payment {pending_id}")
        if p["status"] != "pending":
            st.info(f"Status: {p['status']}")
            return
        st.write(f"Send **{p['send_amount']:,.0f}** to **{p['beneficiary_id']}** via "
                 f"{p['provider']} so they receive **{p['target_amount']:,.2f} "
                 f"{p['target_currency']}**. Fee {p['fee']:,.0f}.")
        code = api.confirmation_code(pending_id)
        st.caption(f"Your one-time code (shown only to you, never to the AI): **{code}**")
        typed = st.text_input("Type the code to confirm", key=f"code_{pending_id}")
        c1, c2 = st.columns(2)
        if c1.button("Confirm payment", key=f"ok_{pending_id}", type="primary"):
            res = api.confirm(pending_id, typed.strip())
            if res["status"] == "executed_in_sandbox":
                st.success("Done (sandbox). The payment is now part of your history.")
            else:
                st.error("Not executed: " + "; ".join(res.get("reasons", [res["status"]])))
        if c2.button("Cancel", key=f"no_{pending_id}"):
            st.info("Cancelled. Nothing was sent.")


def render_trace(trace: list) -> None:
    with st.expander("Agent trace (what the agent did)", expanded=False):
        for t in trace:
            if t.get("step") == "plan":
                st.markdown(f"**Plan:** {t['text']}")
            elif t.get("step") == "tool":
                st.markdown(f"**Tool:** `{t['name']}`")
                st.code(json.dumps({"input": t["input"], "output": t["output"]},
                                   indent=2, default=str)[:1800], language="json")


def page_assistant() -> None:
    st.header("Assistant")
    agent = ss("agent", api.get_agent())
    history = ss("chat", [])
    pending = ss("pending_ids", [])

    st.subheader("Upload a fee letter")
    up = st.file_uploader("PDF or text", type=["pdf", "txt"], key="letter")
    if up is not None and st.button("Check this letter"):
        suffix = os.path.splitext(up.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(up.getvalue())
        r = api.analyze_letter(f.name)
        if r["status"] != "ok":
            banner("amber", "Some fields could not be read. Check the letter by hand.")
        else:
            c = r["check"]
            banner(c["level"], "; ".join(c["reasons"]))
            fl = r["fields"]
            st.write(f"**{fl['payee']}** - {fl['amount']:,.2f} {fl['currency']} - due {fl['due_date']}")
            if r.get("routes"):
                rt = r["routes"]
                st.table([{"Provider": q["provider"], "Send (PKR)": round(q["send_amount"]),
                           "Fee": round(q["fee"]), "Hidden FX cost": round(q["fx_margin_cost"]),
                           "Hours": q["hours"], "On time": q.get("on_time", "")}
                          for q in rt["quotes"]])
                if rt.get("recommended"):
                    st.success(f"Recommended: {rt['recommended']}")
            if r["security_scan"]:
                st.caption("Hidden-instruction scan: " + json.dumps(r["security_scan"], default=str)[:300])

    st.divider()
    for role, text in history:
        with st.chat_message(role):
            st.markdown(text)
    q = st.chat_input("Ask AtlasGuard, e.g. 'Compare routes to pay 3000 EUR by 5 Nov'")
    if q:
        history.append(("user", q))
        with st.spinner("Working..."):
            agent.trace.clear()
            try:
                answer = agent.ask(q)
            except Exception as e:
                answer = f"Something went wrong: {e}"
        history.append(("assistant", answer))
        st.session_state["last_trace"] = list(agent.trace)
        for t in agent.trace:
            if t.get("name") == "draft_transfer" and \
                    t["output"].get("status") == "pending_human_confirmation":
                pending.append(t["output"]["pending_id"])
        st.rerun()
    if st.session_state.get("last_trace"):
        render_trace(st.session_state["last_trace"])
    for pid in pending:
        confirmation_card(pid)


# ------------------------------------------------------------------ Money
def page_money() -> None:
    st.header("Money")
    r = api.get_reserve()
    c1, c2, c3 = st.columns(3)
    c1.metric("Balance", f"{r['balance']:,.0f} {r['currency']}")
    c2.metric("Reserved for bills", f"{r['reserved']:,.0f}")
    c3.metric("Free to spend", f"{r['free_to_spend']:,.0f}")
    banner(r["level"], r["message"])
    if r["reserved"] > 0:
        st.progress(min(1.0, max(0.0, r["free_to_spend"] / max(r["balance"], 1))),
                    text="Share of your balance that is free")
    st.caption(f"Exchange rate source: {r['rate_source']}")
    st.subheader("Bills counted (next 30 days)")
    st.table(r["bills"] or [{"label": "none"}])

    st.subheader("Try spending")
    amt = st.number_input("Amount (PKR)", min_value=0.0, value=100000.0, step=10000.0)
    cat = st.selectbox("Category", ["shopping", "food", "travel", "misc"])
    if st.button("Spend"):
        res = api.spend(amt, cat, "demo purchase")
        if res["status"] == "ok":
            lvl = res["reserve"]["level"]
            banner(lvl, res["reserve"]["message"])
        else:
            st.error(res["reason"])

    with st.expander("Add a bill by hand"):
        label = st.text_input("What is it", "Spring tuition")
        a2 = st.number_input("Amount", min_value=1.0, value=3000.0)
        cur = st.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"])
        due = st.date_input("Due date")
        if st.button("Add bill"):
            api.add_bill(label, a2, cur, due.isoformat())
            st.success("Added. Reload the page to see it in the reserve.")

    st.subheader("Recent transactions")
    st.dataframe(api.recent_transactions(), use_container_width=True)


# ------------------------------------------------------------------ Payees
def page_payees() -> None:
    st.header("Payees and trust")
    payees = api.list_payees()
    for p in payees:
        with st.container(border=True):
            st.markdown(f"**{p['name']}** - `{p['id']}` - "
                        f"{'✅ verified' if p['verified'] else '⚠️ not verified'}")
            st.write(f"{p['payments']} payment(s) in history, usual amount "
                     f"{p['usual_amount'] or 0:,.2f} {p['currency']}")
            if p["payments"]:
                prof = api.payee_profile(p["id"])
                st.caption(f"First seen {prof['first_seen']}, last paid {prof['last_paid']}")
                st.table(prof["history"])
    st.subheader("Check a new fee letter by hand")
    n = st.text_input("Payee name", "Example University Bursar")
    i = st.text_input("Account number (IBAN)", "DE89 3704 0044 0532 0130 00")
    a = st.number_input("Amount", min_value=0.0, value=3000.0)
    cur = st.selectbox("Currency ", ["EUR", "USD", "GBP", "CAD", "AUD"])
    msg = st.text_area("Message text (optional)")
    if st.button("Check against my history"):
        r = api.check_letter_fields(n, i, a, cur, msg)
        banner(r["level"], "; ".join(r["reasons"]))
    with st.expander("Add a new payee"):
        nn = st.text_input("Name", key="np_name")
        ni = st.text_input("Account number", key="np_iban")
        nc = st.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"], key="np_cur")
        ver = st.checkbox("I verified this payee through a contact I already trust")
        if st.button("Save payee"):
            res = api.add_payee(nn, ni, nc, "", ver)
            st.success(f"Saved as {res['id']}") if res["status"] == "ok" else st.error(res["reason"])


# ------------------------------------------------------------------ Attack Lab
def page_attacks() -> None:
    st.header("Attack Lab")
    st.caption("Prepared attacks run against the real safety rules on a throw-away bank. "
               "No AI needed. Your demo data is not touched.")
    if st.button("Run all attacks", type="primary"):
        res = api.attack_run()
        st.session_state["attack_result"] = res
    res = st.session_state.get("attack_result")
    if res:
        st.metric("Blocked or detected as expected", f"{res['passed']} / {res['total']}")
        rows = []
        for r in res["results"]:
            state = "PASS" if r["passed"] else ("KNOWN GAP" if r["known_limit"] else "FAIL")
            rows.append({"ID": r["id"], "Attack": r["name"], "Expected": r["expected"],
                         "Observed": r["observed"], "Result": state})
        st.dataframe(rows, use_container_width=True)
        if res["known_gaps"]:
            st.warning("Known gap (reported honestly): " +
                       "; ".join(f"{g['id']} {g['name']}" for g in res["known_gaps"]))
    else:
        st.dataframe(api.attack_list(), use_container_width=True)


# ------------------------------------------------------------------ Proof Pack
def page_proof() -> None:
    st.header("Proof Pack")
    st.caption("Every action the agent or you took is written to a tamper-evident log.")
    if st.button("Verify log"):
        v = api.verify_audit_log()
        if v["ok"]:
            st.success(f"Log intact: {v['entries']} entries verified.")
        else:
            st.error(f"Log was changed! First bad entry: {v['first_bad_id']}")
    log = api.get_audit_log(200)
    st.dataframe(log, use_container_width=True)
    st.download_button("Download log (JSON)", json.dumps(log, indent=2, default=str),
                       file_name="atlasguard_audit_log.json", mime="application/json")
    ev = os.path.join(os.getcwd(), "evidence", "evaluation_results.md")
    if os.path.exists(ev):
        st.download_button("Download evaluation results", open(ev, encoding="utf-8").read(),
                           file_name="evaluation_results.md")


{"Assistant": page_assistant, "Money": page_money, "Payees": page_payees,
 "Attack Lab": page_attacks, "Proof Pack": page_proof}[page]()
