"""Shared look for every page: colours, banners, cards.

Rule used everywhere:  green = fine,  amber = check,  red = blocked.
Every coloured box ALWAYS carries one reason sentence.
"""
import html

import streamlit as st

COLORS = {"green": "#1b8a3a", "amber": "#d98a00", "red": "#c62828"}
ICON = {"green": "🟢", "amber": "🟠", "red": "🔴"}
WORD = {"green": "FINE", "amber": "CHECK", "red": "BLOCKED"}

_CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
.ag-banner {padding: 12px 16px; border-radius: 10px; margin: 8px 0; line-height: 1.45;}
.ag-pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem;
          font-weight:700; color:#fff; letter-spacing:.03em;}
.ag-hero {padding: 18px 22px; border-radius: 14px; margin-bottom: 14px;
          background: linear-gradient(135deg, #0f3d3e 0%, #1b6b5a 100%); color: #fff;}
.ag-hero h1 {margin:0; font-size:1.7rem; color:#fff;}
.ag-hero p {margin:4px 0 0 0; opacity:.9;}
.ag-side {border-left: 3px solid #1b6b5a55; padding-left: 14px;}
.ag-small {font-size: .85rem; opacity: .75;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def level_of(value, default: str = "amber") -> str:
    """Turn anything (green/amber/red, ok/warn/block...) into one of the 3 levels."""
    v = str(value or "").lower()
    if v in COLORS:
        return v
    if v in ("ok", "safe", "pass", "passed", "allow", "allowed", "verified", "executed_in_sandbox"):
        return "green"
    if v in ("block", "blocked", "fail", "failed", "scam", "deny", "denied", "rejected"):
        return "red"
    return default


def banner(level: str, text: str) -> None:
    level = level_of(level)
    c = COLORS[level]
    st.markdown(
        f"<div class='ag-banner' style='background:{c}22;border-left:6px solid {c}'>"
        f"<b>{ICON[level]} {WORD[level]}</b> &nbsp; {html.escape(str(text))}</div>",
        unsafe_allow_html=True)


def pill(level: str, label: str = "") -> str:
    """Small coloured tag, returned as HTML (use inside st.markdown(..., unsafe_allow_html=True))."""
    level = level_of(level)
    return f"<span class='ag-pill' style='background:{COLORS[level]}'>{html.escape(label or WORD[level])}</span>"


def hero(title: str, subtitle: str) -> None:
    st.markdown(f"<div class='ag-hero'><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>",
                unsafe_allow_html=True)


def ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]
