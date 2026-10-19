"""Payees: pick someone on the left, read their Trust Card on the right."""
import streamlit as st

import ag_data as data
import ag_theme as theme
from ag_theme import e, status


def _initials(name: str) -> str:
    parts = [p for p in str(name).replace("(", " ").replace(")", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _signals(p: dict, prof: dict) -> list:
    """Each signal is a fact we really have, with a reason."""
    sig = []
    if p["verified"]:
        sig.append(("green", "Verified by you", "You confirmed this payee through a contact you trust."))
    else:
        sig.append(("amber", "Not verified", "Nobody has confirmed this payee yet. Verify by phone or in person."))
    n = p.get("payments", 0)
    if n >= 3:
        sig.append(("green", f"{n} past payments", "A steady history makes a swapped account easier to spot."))
    elif n > 0:
        sig.append(("amber", f"{n} past payment{'s' if n > 1 else ''}", "A short history. Check details on each payment."))
    else:
        sig.append(("amber", "No history", "First payment to this payee will need extra approval."))
    if p.get("usual_amount"):
        sig.append(("green", f"Usual amount {p['usual_amount']:,.0f} {p['currency']}",
                    "A request far from this amount gets held for a check."))
    if prof.get("first_seen"):
        sig.append(("green", f"Known since {prof['first_seen']}", f"Last paid {prof.get('last_paid') or 'never'}."))
    return sig


def _trust_card(p: dict) -> None:
    prof = data.payee_profile(p["id"]) if p.get("payments") else {}
    with st.container(border=True):
        lv = "green" if p["verified"] else "amber"
        st.markdown(
            f"<div style='display:flex;gap:16px;align-items:center'>"
            f"<div class='av' style='width:62px;height:62px;border-radius:20px;background:#EEF1FA;display:flex;"
            f"align-items:center;justify-content:center;font-family:Sora;font-weight:700;font-size:1.3rem;color:#3547F5'>"
            f"{e(_initials(p['name']))}</div><div><div class='ag-h' style='font-size:1.4rem;margin:0'>{e(p['name'])}</div>"
            f"<div class='ag-mono ag-muted'>{e(p['id'])}</div></div>"
            f"<div style='margin-left:auto'>{theme.chip(lv, 'Verified' if p['verified'] else 'Not verified')}</div></div>",
            unsafe_allow_html=True)
        st.markdown("<div class='ag-h' style='margin-top:16px'>Trust signals</div>", unsafe_allow_html=True)
        rows = "".join(
            f"<div class='ag-row'><div>{theme.chip(l)}</div><div class='tx'><div class='t1' style='white-space:normal'>{e(t)}</div>"
            f"<div class='t2'>{e(w)}</div></div></div>" for l, t, w in _signals(p, prof))
        st.markdown(rows, unsafe_allow_html=True)
        if prof.get("history"):
            with st.expander("Payment history"):
                out = []
                for h in prof["history"]:
                    out.append(f"<div class='ag-row'><div class='tx'><div class='t1'>{e(h.get('date', ''))}</div>"
                               f"<div class='t2'>{e(h.get('status', ''))}</div></div>"
                               f"<div class='am'>{h.get('amount', 0):,.0f} {e(h.get('currency', ''))}</div></div>")
                st.markdown("".join(out), unsafe_allow_html=True)


def _check_letter() -> None:
    with st.container(border=True):
        theme.heading("Check a fee letter by hand", "Type what the letter says. We compare it with your records.")
        n = st.text_input("Payee name", "Example University Bursar", key="cl_name")
        i = st.text_input("Account number (IBAN)", "DE89 3704 0044 0532 0130 00", key="cl_iban")
        c1, c2 = st.columns(2)
        a = c1.number_input("Amount", min_value=0.0, value=3000.0, key="cl_amt")
        cur = c2.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"], key="cl_cur")
        msg = st.text_area("Message text (optional)", key="cl_msg", height=90)
        if st.button("Check against my records", type="primary", use_container_width=True, key="cl_go"):
            r = data.check_letter_fields(n, i, a, cur, msg)
            status(r["level"], "; ".join(r["reasons"]))


def _add_payee() -> None:
    with st.container(border=True):
        theme.heading("Add a payee")
        nn = st.text_input("Name", key="np_name")
        ni = st.text_input("Account number", key="np_iban")
        nc = st.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD", "PKR"], key="np_cur")
        ver = st.checkbox("I verified this myself, through a contact I already trust", key="np_ver")
        if not ver:
            st.caption("Without the tick, the payee is saved as not verified and every payment needs extra approval.")
        if st.button("Save payee", type="primary", use_container_width=True, key="np_go"):
            res = data.add_payee(nn, ni, nc, "", ver)
            if res["status"] == "ok":
                st.session_state["payee_msg"] = ("green" if ver else "amber", f"Saved as {res['id']}.")
                st.rerun()
            else:
                status("red", res.get("reason", "Could not save."), "Not saved")
        pm = st.session_state.pop("payee_msg", None)
        if pm:
            status(pm[0], pm[1], "Saved")


def render() -> None:
    payees = data.list_payees()
    theme.pagehead("Payees", "Only pay people you know. New or changed details are held for a check.")
    if not payees:
        status("amber", "No payees yet. Add one on the right to start.", "Empty")
    left, right = st.columns([1, 2], gap="medium")
    with left:
        with st.container(border=True):
            theme.heading("Your payees", f"{len(payees)} saved")
            ids = [p["id"] for p in payees]
            names = {p["id"]: ("[Verified] " if p["verified"] else "[Not verified] ") + p["name"] for p in payees}
            if ids:
                sel = st.radio("Payee", ids, format_func=lambda x: names[x], key="payee_sel",
                               label_visibility="collapsed")
        _add_payee()
    with right:
        if payees:
            sel = st.session_state.get("payee_sel", payees[0]["id"])
            p = next((x for x in payees if x["id"] == sel), payees[0])
            _trust_card(p)
        _check_letter()
