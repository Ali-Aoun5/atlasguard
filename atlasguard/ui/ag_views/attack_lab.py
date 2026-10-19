"""Attack Lab: we attack our own agent. Results reveal one by one."""
import time

import streamlit as st

import ag_data as data
import ag_theme as theme
from ag_theme import COL, e, status


def _tile(a: dict, state: str, r: dict = None) -> None:
    """state: queued | green | amber | red"""
    if state == "queued":
        lv, word, body = "idle", "Ready", e(a.get("description") or a.get("expected") or "Waiting to run.")
    else:
        lv = state
        word = {"green": "Stopped", "amber": "Known gap", "red": "Got through"}[state]
        body = (f"<div class='ag-sub' style='margin:0'>Tried: {e(r['expected'])}</div>"
                f"<div style='margin-top:6px;font-weight:600'>{e(r['observed'])}</div>")
    st.markdown(
        f"<div class='ag-tile ag-flip' style='border-top:5px solid {COL[lv]};margin-bottom:12px'>"
        f"<div style='display:flex;justify-content:space-between;gap:8px;align-items:center'>"
        f"<div class='ag-h' style='margin:0'>{e(a.get('name', a.get('id', 'Attack')))}</div>{theme.chip(lv, word)}</div>"
        f"<div class='ag-mono ag-muted' style='margin:2px 0 8px 0'>{e(a.get('id', ''))}</div>{body}</div>",
        unsafe_allow_html=True)


def _state(r: dict) -> str:
    return "green" if r["passed"] else ("amber" if r.get("known_limit") else "red")


def _grid(items, states, results, slots=None) -> None:
    cols = st.columns(2, gap="small")
    for i, a in enumerate(items):
        with cols[i % 2]:
            _tile(a, states[i], results[i] if results else None)


def render() -> None:
    pagehead_text = ("We attack our own agent before anyone else can. Green means the attack was stopped. "
                     "A known gap is reported honestly, not hidden.")
    theme.pagehead("Attack Lab", pagehead_text)

    attacks = data.attack_list() or []
    res = st.session_state.get("attack_result")

    top, _ = st.columns([1, 0.001])
    with st.container(border=True):
        c1, c2 = st.columns([1, 2.2], gap="medium")
        with c1:
            if res:
                lv = "green" if res["passed"] == res["total"] else "amber"
                st.markdown(theme.ring(res["passed"], res["total"], lv, "attacks stopped"), unsafe_allow_html=True)
            else:
                st.markdown(theme.ring(0, max(len(attacks), 1), "idle", "attacks ready to run"), unsafe_allow_html=True)
        with c2:
            if res:
                if res["passed"] == res["total"]:
                    status("green", "Every prepared attack was stopped by the safety rules.", "All stopped")
                elif res.get("known_gaps") and all(r["passed"] or r.get("known_limit") for r in res["results"]):
                    gaps = "; ".join(f"{g['id']} {g['name']}" for g in res["known_gaps"])
                    status("amber", f"Everything else was stopped. Known gap, reported honestly: {gaps}.", "Mostly stopped")
                else:
                    status("red", "At least one attack got through. See the red cards below.", "Attack got through")
            else:
                status("idle", "Attacks run against the real safety rules on a throw-away bank. "
                               "Your demo data is not touched. No AI is needed.", "Not run yet")
            run = st.button("Run all attacks", type="primary", key="atk_run")

    if run:
        with st.spinner("Preparing the throw-away bank..."):
            result = data.attack_run()
        st.session_state["attack_result"] = result
        st.session_state["attack_reveal"] = True
        st.rerun()

    res = st.session_state.get("attack_result")
    if not res:
        _grid(attacks, ["queued"] * len(attacks), None)
        return

    filt = st.radio("Show", ["All", "Stopped", "Known gap", "Got through"], horizontal=True, key="atk_filter")
    results = res["results"]
    keep = [r for r in results if filt == "All" or
            (filt == "Stopped" and _state(r) == "green") or
            (filt == "Known gap" and _state(r) == "amber") or
            (filt == "Got through" and _state(r) == "red")]
    if not keep:
        st.markdown("<div class='ag-sub'>No attacks match this filter.</div>", unsafe_allow_html=True)
        return
    if st.session_state.pop("attack_reveal", False) and filt == "All":
        # one orchestrated moment: tiles flip from Ready to their result, one by one
        holders = st.columns(2, gap="small")
        slots = []
        for i, r in enumerate(keep):
            with holders[i % 2]:
                slots.append(st.empty())
        for i, r in enumerate(keep):
            slots[i].markdown(
                f"<div class='ag-tile' style='border-top:5px solid {COL['idle']};margin-bottom:12px'>"
                f"<div class='ag-h' style='margin:0'>{e(r['name'])}</div>"
                f"<div class='ag-sub'>Running...</div></div>", unsafe_allow_html=True)
        for i, r in enumerate(keep):
            time.sleep(0.18)
            with slots[i].container():
                _tile(r, _state(r), r)
    else:
        _grid(keep, [_state(r) for r in keep], keep)
