"""Proof Pack page: test numbers, action log, download, verify log."""
import json
import os

import streamlit as st

from atlasguard import api
from theme import banner, hero


def render() -> None:
    hero("Proof Pack", "Evidence for the judges: test results and a tamper-evident log of every action.")
    log = api.get_audit_log(200)

    st.subheader("Test numbers")
    res = st.session_state.get("attack_result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Actions logged", len(log))
    if res:
        c2.metric("Attacks stopped", f"{res['passed']} / {res['total']}")
        c3.metric("Known gaps", len(res.get("known_gaps", [])))
    else:
        c2.metric("Attacks stopped", "not run yet")
        c3.metric("Known gaps", "-")
        st.caption("Open the Attack Lab and click 'Run all attacks' to fill in these numbers.")

    ev = os.path.join(os.getcwd(), "evidence", "evaluation_results.md")
    if os.path.exists(ev):
        text = open(ev, encoding="utf-8").read()
        with st.expander("Evaluation results"):
            st.markdown(text)
        st.download_button("Download evaluation results", text, file_name="evaluation_results.md")

    st.subheader("Action log")
    if st.button("🔒 Verify log", type="primary"):
        v = api.verify_audit_log()
        if v["ok"]:
            banner("green", f"Log intact: {v['entries']} entries verified.")
        else:
            banner("red", f"Log was changed! First bad entry: {v['first_bad_id']}")
    st.dataframe(log, use_container_width=True)
    st.download_button("⬇ Download log (JSON)", json.dumps(log, indent=2, default=str),
                       file_name="atlasguard_audit_log.json", mime="application/json")
