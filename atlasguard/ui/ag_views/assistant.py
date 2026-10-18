"""Assistant page: chat box, upload box, and the transparency panel on the side."""
import json
import os
import tempfile

import streamlit as st

from atlasguard import api
from theme import banner, hero, pill, ss


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
        banner("amber", "A human must approve this payment. The AI cannot approve it for you.")
        code = api.confirmation_code(pending_id)
        st.caption(f"Your one-time code (shown only to you, never to the AI): **{code}**")
        typed = st.text_input("Type the code to confirm", key=f"code_{pending_id}")
        c1, c2 = st.columns(2)
        if c1.button("Confirm payment", key=f"ok_{pending_id}", type="primary"):
            res = api.confirm(pending_id, typed.strip())
            if res["status"] == "executed_in_sandbox":
                banner("green", "Done (sandbox). The payment is now part of your history.")
            else:
                banner("red", "Not executed: " + "; ".join(res.get("reasons", [res["status"]])))
        if c2.button("Cancel", key=f"no_{pending_id}"):
            banner("amber", "Cancelled. Nothing was sent.")


def _upload_box() -> None:
    st.markdown("##### 📄 Check a fee letter")
    up = st.file_uploader("PDF or text", type=["pdf", "txt"], key="letter",
                          label_visibility="collapsed")
    if up is not None and st.button("Check this letter", type="primary"):
        suffix = os.path.splitext(up.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(up.getvalue())
        with st.spinner("Reading and checking the letter..."):
            st.session_state["letter_result"] = api.analyze_letter(f.name)
    r = st.session_state.get("letter_result")
    if not r:
        return
    if r["status"] != "ok":
        banner("amber", "Some fields could not be read. Check the letter by hand.")
        return
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
            banner("green", f"Cheapest safe route: {rt['recommended']}")
    if r.get("security_scan"):
        st.caption("Hidden-instruction scan: " + json.dumps(r["security_scan"], default=str)[:300])


def _transparency_panel() -> None:
    """Right-hand panel: what the agent did, step by step."""
    st.markdown("##### 🔎 Transparency panel")
    st.caption("Everything the agent did for your last question.")
    trace = st.session_state.get("last_trace") or []
    if not trace:
        st.info("Nothing yet. Ask a question and the agent's steps will appear here.")
        return
    for t in trace:
        if t.get("step") == "plan":
            st.markdown(f"**📝 Plan**  \n{t['text']}")
        elif t.get("step") == "tool":
            out = t.get("output")
            status = out.get("status", "") if isinstance(out, dict) else ""
            tag = pill(status) if status else ""
            st.markdown(f"**🛠 Tool** `{t['name']}` {tag}", unsafe_allow_html=True)
            with st.expander("See input and output"):
                st.code(json.dumps({"input": t["input"], "output": out},
                                   indent=2, default=str)[:1800], language="json")


def render() -> None:
    hero("Assistant", "Ask about fees, routes and payees. Every step the agent takes is shown on the right.")
    agent = ss("agent", api.get_agent())
    history = ss("chat", [])
    pending = ss("pending_ids", [])

    left, right = st.columns([3, 2], gap="large")
    with left:
        _upload_box()
        st.divider()
        if not history:
            st.caption("Try: *Compare routes to pay 3000 EUR by 5 Nov*")
        for role, text in history:
            with st.chat_message(role):
                st.markdown(text)
        for pid in pending:
            confirmation_card(pid)
    with right:
        st.markdown("<div class='ag-side'>", unsafe_allow_html=True)
        _transparency_panel()
        st.markdown("</div>", unsafe_allow_html=True)

    q = st.chat_input("Ask AtlasGuard, e.g. 'Compare routes to pay 3000 EUR by 5 Nov'")
    if q:
        history.append(("user", q))
        with st.spinner("Working..."):
            agent.trace.clear()
            try:
                answer = agent.ask(q)
            except Exception as e:  # show the problem instead of crashing the page
                answer = f"Something went wrong: {e}"
        history.append(("assistant", answer))
        st.session_state["last_trace"] = list(agent.trace)
        for t in agent.trace:
            if t.get("name") == "draft_transfer" and \
                    isinstance(t.get("output"), dict) and \
                    t["output"].get("status") == "pending_human_confirmation":
                pending.append(t["output"]["pending_id"])
        st.rerun()
