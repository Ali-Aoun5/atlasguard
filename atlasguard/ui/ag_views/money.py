"""Money page: balance, reserve bar, free to spend, transactions, Spend button, alerts."""
import streamlit as st

from atlasguard import api
from theme import banner, hero


def render() -> None:
    hero("Money", "What you have, what is set aside for bills, and what is safe to spend.")
    r = api.get_reserve()

    c1, c2, c3 = st.columns(3)
    c1.metric("Balance", f"{r['balance']:,.0f} {r['currency']}")
    c2.metric("Reserved for bills", f"{r['reserved']:,.0f}")
    c3.metric("Free to spend", f"{r['free_to_spend']:,.0f}")

    banner(r["level"], r["message"])  # the alert
    if r["reserved"] > 0:
        share = min(1.0, max(0.0, r["free_to_spend"] / max(r["balance"], 1)))
        st.progress(share, text=f"Reserve bar: {share:.0%} of your balance is free, "
                                f"{1 - share:.0%} is kept for bills")
    st.caption(f"Exchange rate source: {r['rate_source']}")

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Try spending")
        with st.container(border=True):
            amt = st.number_input("Amount (PKR)", min_value=0.0, value=100000.0, step=10000.0)
            cat = st.selectbox("Category", ["shopping", "food", "travel", "misc"])
            if st.button("Spend", type="primary"):
                res = api.spend(amt, cat, "demo purchase")
                if res["status"] == "ok":
                    banner(res["reserve"]["level"], res["reserve"]["message"])
                else:
                    banner("red", res["reason"])
        with st.expander("Add a bill by hand"):
            label = st.text_input("What is it", "Spring tuition")
            a2 = st.number_input("Amount", min_value=1.0, value=3000.0)
            cur = st.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"])
            due = st.date_input("Due date")
            if st.button("Add bill"):
                api.add_bill(label, a2, cur, due.isoformat())
                banner("green", "Added. Reload the page to see it in the reserve.")
    with right:
        st.subheader("Bills counted (next 30 days)")
        st.table(r["bills"] or [{"label": "none"}])

    st.subheader("Recent transactions")
    st.dataframe(api.recent_transactions(), use_container_width=True)
