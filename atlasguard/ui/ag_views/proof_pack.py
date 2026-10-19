"""Proof Pack: the evidence. Test numbers, a tamper-evident chain, and the full log."""
import os

import streamlit as st

import ag_data as data
import ag_theme as theme
from ag_theme import COL, e, status

SHOWN = ("id", "ts", "actor", "action", "detail", "prev_hash", "hash")


def _chain(log: list, bad_id=None, verified: bool = False) -> None:
    if not log:
        return
    blocks = []
    for ent in log[-8:]:
        bad = bad_id is not None and ent.get("id") == bad_id
        lc = COL["red"] if bad else COL["green"] if verified else COL["idle"]
        h = str(ent.get("hash", ""))[:12]
        what = ent.get("action") or ent.get("event") or ent.get("type") or "entry"
        blocks.append(
            f"<div class='ag-block' style='--lc:{lc};{'border-color:' + lc if verified or bad else ''}'>"
            f"<div class='bid'>#{e(ent.get('id', ''))}</div><div class='ba'>{e(what)}</div>"
            f"<div class='bh'>{e(h) if h else 'no hash in this entry'}</div></div>")
    st.markdown("<div class='ag-chain'>" + "".join(blocks) + "</div>", unsafe_allow_html=True)


def render() -> None:
    theme.pagehead("Proof Pack", "The evidence for a reviewer: test results and a tamper-evident log of everything "
                                 "the agent and you did.")
    log = data.get_audit_log(200) or []
    res = st.session_state.get("attack_result")
    ver = st.session_state.get("verify_result")

    gaps = len(res.get("known_gaps", [])) if res else None
    tiles = [
        theme.tile("Actions logged", str(len(log))),
        theme.tile("Log integrity", "Not checked" if not ver else "Intact" if ver["ok"] else "Changed",
                   "" if not ver else "green" if ver["ok"] else "red"),
        theme.tile("Attacks stopped", f"{res['passed']} / {res['total']}" if res else "Not run",
                   "" if not res else "green" if res["passed"] == res["total"] else "amber",
                   "" if res else "Run them in Attack Lab"),
        theme.tile("Known gaps", "-" if gaps is None else str(gaps), "" if not gaps else "amber",
                   "Reported honestly" if gaps else ""),
    ]
    cols = st.columns(4, gap="small")
    for c, t in zip(cols, tiles):
        c.markdown(t, unsafe_allow_html=True)

    with st.container(border=True):
        theme.heading("Hash chain", "Each entry carries the fingerprint of the one before it. Change one and every later link breaks.")
        _chain(log, None if not ver or ver["ok"] else ver.get("first_bad_id"), bool(ver and ver["ok"]))
        if st.button("Verify log", type="primary", key="verify_go"):
            with st.spinner("Checking every link..."):
                st.session_state["verify_result"] = data.verify_audit_log()
            st.rerun()
        if ver:
            if ver["ok"]:
                status("green", f"All {ver['entries']} entries check out. Nothing has been changed.", "Log intact")
            else:
                status("red", f"Entry {ver.get('first_bad_id')} does not match its fingerprint, so the log was changed.",
                       "Log was changed")

    with st.container(border=True):
        theme.heading("Action log")
        q = st.text_input("Search the log", "", key="log_q", placeholder="Search by action, actor or detail")
        rows = [x for x in log if not q or q.lower() in str(x).lower()]
        if not rows:
            st.markdown("<div class='ag-sub'>No entries match.</div>", unsafe_allow_html=True)
        out = []
        for x in list(reversed(rows))[:40]:
            extra = " | ".join(f"{k}: {v}" for k, v in x.items() if k not in SHOWN and v not in ("", None))
            title = x.get("action") or x.get("event") or x.get("type") or "entry"
            sub = " | ".join(str(v) for v in (x.get("ts"), x.get("actor")) if v)
            out.append(f"<div class='ag-row'><div class='av'>{e(x.get('id', '#'))}</div>"
                       f"<div class='tx'><div class='t1' style='white-space:normal'>{e(title)}</div>"
                       f"<div class='t2'>{e(sub)}</div>"
                       f"<div class='t2'>{e(x.get('detail') or extra)}</div></div>"
                       f"<div class='ag-mono ag-muted'>{e(str(x.get('hash', ''))[:10])}</div></div>")
        st.markdown("".join(out), unsafe_allow_html=True)
        d1, d2, _ = st.columns([1, 1, 2])
        d1.download_button("Download log (JSON)", data.to_json(log), file_name="atlasguard_audit_log.json",
                           mime="application/json", use_container_width=True)
        ev = os.path.join(os.getcwd(), "evidence", "evaluation_results.md")
        if os.path.exists(ev):
            d2.download_button("Download evaluation results", open(ev, encoding="utf-8").read(),
                               file_name="evaluation_results.md", use_container_width=True)
