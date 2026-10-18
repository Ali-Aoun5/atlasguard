"""Attack Lab page: attack list, run button, green or red results."""
import streamlit as st

from atlasguard import api
from theme import COLORS, banner, hero, pill


def _card(r: dict) -> None:
    if r["passed"]:
        level, label = "green", "BLOCKED AS EXPECTED"
    elif r.get("known_limit"):
        level, label = "amber", "KNOWN GAP"
    else:
        level, label = "red", "FAIL"
    c = COLORS[level]
    with st.container(border=True):
        st.markdown(f"**{r['id']} - {r['name']}** &nbsp; {pill(level, label)}", unsafe_allow_html=True)
        st.caption(f"Expected: {r['expected']}")
        st.markdown(f"<span style='color:{c}'>Observed: {r['observed']}</span>", unsafe_allow_html=True)


def render() -> None:
    hero("Attack Lab", "We attack our own agent. Green = the attack was stopped.")
    st.caption("Prepared attacks run against the real safety rules on a throw-away bank. "
               "No AI needed. Your demo data is not touched.")
    if st.button("▶ Run all attacks", type="primary"):
        with st.spinner("Running attacks..."):
            st.session_state["attack_result"] = api.attack_run()
    res = st.session_state.get("attack_result")
    if not res:
        st.subheader("Attacks ready to run")
        st.dataframe(api.attack_list(), use_container_width=True)
        return

    st.metric("Stopped as expected", f"{res['passed']} / {res['total']}")
    st.progress(res["passed"] / max(res["total"], 1))
    if res["passed"] == res["total"]:
        banner("green", "Every attack was stopped.")
    elif res["known_gaps"]:
        banner("amber", "Known gap (reported honestly): " +
               "; ".join(f"{g['id']} {g['name']}" for g in res["known_gaps"]))
    else:
        banner("red", "At least one attack got through. See the red cards.")
    cols = st.columns(2, gap="medium")
    for i, r in enumerate(res["results"]):
        with cols[i % 2]:
            _card(r)
