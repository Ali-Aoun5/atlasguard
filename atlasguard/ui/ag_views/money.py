"""Money: balance and what is kept for bills, a live spend check, bills, transactions."""
from datetime import date, datetime

import streamlit as st

import ag_data as data
import ag_theme as theme
from ag_theme import COL, e, status

SIM = {"PKR": 1.0, "EUR": 305.0, "GBP": 355.0, "USD": 280.0}  # simulated, for display only


def _days_left(due: str):
    try:
        return (datetime.fromisoformat(str(due)[:10]).date() - date.today()).days
    except Exception:
        return None


def _fmt(v: float, cur: str) -> str:
    return f"{v:,.0f}" if cur == "PKR" else f"{v:,.2f}"


def _preview(r: dict, amt: float) -> tuple:
    """Local what-if so the person sees the effect before pressing Spend."""
    free_after = r["free_to_spend"] - amt
    if amt <= 0:
        return "idle", "Enter an amount to see what it does to your free money."
    if free_after < 0:
        return "red", f"This would use {-free_after:,.0f} PKR that is kept for bills."
    if free_after < 0.1 * r["balance"]:
        return "amber", f"You would have only {free_after:,.0f} PKR free after this."
    return "green", f"You would still have {free_after:,.0f} PKR free after this."


def _bills(r: dict) -> None:
    with st.container(border=True):
        theme.heading("Bills kept aside", "Money reserved for what is due in the next 30 days.")
        rows = r.get("bills") or []
        if not rows:
            st.markdown("<div class='ag-sub'>No bills yet. Add one below and it is reserved straight away.</div>",
                        unsafe_allow_html=True)
        out = []
        for b in rows:
            d = _days_left(b.get("due"))
            lv = "idle" if d is None else "red" if d < 0 else "amber" if d <= 7 else "green"
            when = "" if d is None else "overdue" if d < 0 else "due today" if d == 0 else f"in {d} days"
            amt = f"{b.get('amount', 0):,.0f} {e(b.get('currency', ''))}"
            out.append(
                f"<div class='ag-row'><div class='av'>{e(str(b.get('label', '?'))[:1])}</div>"
                f"<div class='tx'><div class='t1'>{e(b.get('label', 'Bill'))}</div>"
                f"<div class='t2'>Due {e(b.get('due', '-'))}</div></div>"
                f"<div style='text-align:right'><div class='am'>{amt}</div>"
                f"<div>{theme.chip(lv, when) if when else ''}</div></div></div>")
        st.markdown("".join(out), unsafe_allow_html=True)
        with st.expander("Add a bill"):
            label = st.text_input("What is it", "Spring tuition", key="bill_label")
            c1, c2 = st.columns(2)
            a2 = c1.number_input("Amount", min_value=1.0, value=3000.0, key="bill_amt")
            cur = c2.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"], key="bill_cur")
            due = st.date_input("Due date", key="bill_due")
            if st.button("Add bill", key="bill_add"):
                data.add_bill(label, a2, cur, due.isoformat())
                st.rerun()


def _transactions() -> None:
    txns = data.recent_transactions() or []
    with st.container(border=True):
        theme.heading("Recent activity")
        if not txns:
            st.markdown("<div class='ag-sub'>No activity yet.</div>", unsafe_allow_html=True)
            return
        out = []
        for t in list(txns)[:8]:
            title = next((t[k] for k in ("description", "note", "label", "payee", "beneficiary_id", "type")
                          if t.get(k)), "Payment")
            amt = t.get("amount")
            when = t.get("date") or t.get("ts") or t.get("created_at") or ""
            cat = t.get("category", "")
            sub = " | ".join(str(x) for x in (str(when)[:10], cat) if x)
            out.append(
                f"<div class='ag-row'><div class='av'>{e(str(title)[:1].upper())}</div>"
                f"<div class='tx'><div class='t1'>{e(title)}</div><div class='t2'>{e(sub)}</div></div>"
                f"<div class='am'>{'-' + format(amt, ',.0f') if isinstance(amt, (int, float)) else ''}</div></div>")
        st.markdown("".join(out), unsafe_allow_html=True)


def render() -> None:
    locked = st.session_state.get("locked", False)
    r = data.get_reserve()
    theme.pagehead("Money", "What you have, what is kept aside for bills, and what is safe to spend today.")

    main, side = st.columns([1.55, 1], gap="medium")
    with main:
        with st.container(border=True):
            cur = st.radio("Show in", list(SIM), horizontal=True, key="money_cur")
            f = SIM[cur] / SIM["PKR"]
            bal, res, free = r["balance"] / f, r["reserved"] / f, r["free_to_spend"] / f
            st.markdown(
                f"<div class='ag-sub' style='margin:6px 0 0 0'>Total balance</div>"
                f"<div class='ag-num' style='font-size:2.9rem;line-height:1.1'>{_fmt(bal, cur)} "
                f"<span style='font-size:1.2rem;color:#59647F'>{cur}</span></div>", unsafe_allow_html=True)
            tot = max(r["balance"], 1)
            a = min(max(r["reserved"], 0), tot) / tot * 100
            over = r["reserved"] > r["balance"]
            st.markdown(
                f"<div class='ag-ledger'><div class='a' style='width:{a:.1f}%'></div>"
                f"<div class='{'c' if over else 'b'}' style='width:{100 - a:.1f}%'></div></div>"
                f"<div class='ag-legend'><span><i style='background:#3547F5'></i>Kept for bills {_fmt(res, cur)}</span>"
                f"<span><i style='background:{'#D6334A' if over else '#0E9F6E'}'></i>Free to spend {_fmt(free, cur)}</span></div>",
                unsafe_allow_html=True)
            status(r["level"], r["message"])
            if cur != "PKR":
                st.caption("Other currencies use simulated indicative rates. Your sandbox balance is in PKR.")
            st.caption(f"Exchange rate source: {r.get('rate_source', 'n/a')}")
        _transactions()
    with side:
        with st.container(border=True):
            theme.heading("Spend check", "See the effect first, then spend.")
            amt = st.number_input("Amount (PKR)", min_value=0.0, value=50000.0, step=5000.0, key="spend_amt")
            cat = st.selectbox("Category", ["shopping", "food", "travel", "misc"], key="spend_cat")
            lv, why = _preview(r, amt)
            status(lv, why, "Preview" if lv == "idle" else None)
            if st.button("Spend", type="primary", disabled=locked, use_container_width=True, key="spend_go"):
                res_ = data.spend(amt, cat, "demo purchase")
                if res_["status"] == "ok":
                    st.session_state["spend_result"] = ("green" if res_["reserve"]["level"] == "green" else
                                                         res_["reserve"]["level"], res_["reserve"]["message"])
                else:
                    st.session_state["spend_result"] = ("red", res_["reason"])
                st.rerun()
            sr = st.session_state.pop("spend_result", None)
            if sr:
                status(sr[0], sr[1], "Spent" if sr[0] != "red" else "Not spent")
        _bills(r)
