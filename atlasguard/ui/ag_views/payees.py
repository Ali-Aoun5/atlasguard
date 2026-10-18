"""Payees page: verified payees, add-payee form, and the Trust Card."""
import streamlit as st

from atlasguard import api
from theme import banner, hero, pill


def _trust_card(p: dict) -> None:
    with st.container(border=True):
        level = "green" if p["verified"] else "amber"
        st.markdown(f"**{p['name']}** &nbsp; `{p['id']}` &nbsp; "
                    f"{pill(level, 'VERIFIED' if p['verified'] else 'NOT VERIFIED')}",
                    unsafe_allow_html=True)
        st.write(f"{p['payments']} payment(s) in history, usual amount "
                 f"{p['usual_amount'] or 0:,.2f} {p['currency']}")
        if p["payments"]:
            prof = api.payee_profile(p["id"])
            st.caption(f"Trust Card: first seen {prof['first_seen']}, last paid {prof['last_paid']}")
            with st.expander("Payment history"):
                st.table(prof["history"])
        elif not p["verified"]:
            st.caption("No history yet. Treat with care until you verify it yourself.")


def render() -> None:
    hero("Payees and trust", "Only pay people you know. New or changed details get flagged.")
    payees = api.list_payees()
    st.subheader("Verified payees")
    cols = st.columns(2, gap="large")
    for i, p in enumerate(payees):
        with cols[i % 2]:
            _trust_card(p)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Add a payee")
        with st.container(border=True):
            nn = st.text_input("Name", key="np_name")
            ni = st.text_input("Account number", key="np_iban")
            nc = st.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"], key="np_cur")
            ver = st.checkbox("I verified this myself (through a contact I already trust)")
            if not ver:
                st.caption("Unticked payees are saved as NOT verified and need extra approval.")
            if st.button("Save payee", type="primary"):
                res = api.add_payee(nn, ni, nc, "", ver)
                if res["status"] == "ok":
                    banner("green" if ver else "amber", f"Saved as {res['id']}")
                else:
                    banner("red", res["reason"])
    with right:
        st.subheader("Check a fee letter by hand")
        with st.container(border=True):
            n = st.text_input("Payee name", "Example University Bursar")
            i = st.text_input("Account number (IBAN)", "DE89 3704 0044 0532 0130 00")
            a = st.number_input("Amount", min_value=0.0, value=3000.0)
            cur = st.selectbox("Currency ", ["EUR", "USD", "GBP", "CAD", "AUD"])
            msg = st.text_area("Message text (optional)")
            if st.button("Check against my history"):
                r = api.check_letter_fields(n, i, a, cur, msg)
                banner(r["level"], "; ".join(r["reasons"]))
