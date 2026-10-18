"""AtlasGuard screen.  Run from the folder that CONTAINS `atlasguard`:

    streamlit run atlasguard/ui/app.py                (real AI, needs ANTHROPIC_API_KEY)
    set AG_MOCK=1 && streamlit run atlasguard/ui/app.py   (demo mode, no key; Windows)

This UI talks ONLY to atlasguard/api.py. Do not import anything else from atlasguard.
Files:  theme.py (colours)  |  ag_views/*.py (one file per page)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from atlasguard import api  # noqa: E402

st.set_page_config(page_title="AtlasGuard", page_icon="🛡️", layout="wide")
api.start()

import theme  # noqa: E402
from ag_views import assistant, attack_lab, money, payees, proof_pack  # noqa: E402

theme.inject_css()

PAGES = {"Assistant": assistant.render, "Money": money.render, "Payees": payees.render,
         "Attack Lab": attack_lab.render, "Proof Pack": proof_pack.render}

with st.sidebar:
    st.title("🛡️ AtlasGuard")
    st.caption("Cross-border student finance agent. **Sandbox only - no real money.**")
    if api.is_mock():
        st.warning("Demo mode: real safety rules, no AI service. Set ANTHROPIC_API_KEY for the full AI.")
    page = st.radio("Go to", list(PAGES))
    b = api.balance_summary()
    st.metric("Balance", f"{b['balance']:,.0f} {b['currency']}")
    st.markdown(f"{theme.pill('green', 'GREEN')} fine &nbsp; {theme.pill('amber', 'AMBER')} check "
                f"&nbsp; {theme.pill('red', 'RED')} blocked", unsafe_allow_html=True)
    st.caption("Not financial advice. Provider fees are simulated.")

PAGES[page]()
