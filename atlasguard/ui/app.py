"""AtlasGuard screen.  Run from the folder that CONTAINS `atlasguard`:

    streamlit run atlasguard/ui/app.py                (real AI, needs ANTHROPIC_API_KEY)
    set AG_MOCK=1 && streamlit run atlasguard/ui/app.py   (demo mode, no key; Windows)

Files in this folder:
  app.py          floating dock (navigation) + page routing
  ag_theme.py     colours, fonts, shared components (status, journey, tiles)
  ag_data.py      asks atlasguard/api.py; falls back to sample data so every button works
  ag_views/       one file per page: assistant, money, payees, attack_lab, proof_pack
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st  # noqa: E402

try:  # best effort: ask Streamlit for its light theme so form widgets match
    st._config.set_option("theme.base", "light")
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(page_title="AtlasGuard", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="collapsed")

import ag_data as data  # noqa: E402
import ag_theme as theme  # noqa: E402
from ag_views import assistant, attack_lab, money, payees, proof_pack  # noqa: E402

data.reset_flag()
data.start()
theme.inject_css()

PAGES = {"Assistant": assistant.render, "Money": money.render, "Payees": payees.render,
         "Attack Lab": attack_lab.render, "Proof Pack": proof_pack.render}


def _toggle_lock() -> None:
    st.session_state["locked"] = not st.session_state.get("locked", False)


locked = theme.ss("locked", False)

# ------------------------------------------------------------------ dock
brand, nav, state = st.columns([1.35, 4.2, 2.5], gap="small")
with brand:
    st.markdown(f"<div class='ag-dock ag-brand'>{theme.LOGO}<div><b>AtlasGuard</b>"
                f"<small>Student finance</small></div></div>", unsafe_allow_html=True)
with nav:
    page = st.radio("Navigate", list(PAGES), horizontal=True, key="nav", label_visibility="collapsed")
with state:
    chips_col, lock_col = st.columns([2.2, 1], gap="small")
    chips_slot = chips_col.empty()
    lock_col.button("Unlock" if locked else "Lock", on_click=_toggle_lock, key="lockbtn",
                    help="Locks this screen: payment buttons stop working until you unlock.")

# ------------------------------------------------------------------ page
PAGES[page]()

# dock chips are filled last, because we only know about sample data after the page ran
lv = "red" if st.session_state.get("locked") else "green"
txt = "Screen locked" if st.session_state.get("locked") else "Guard active"
sample = ("<span class='ag-dockchip'><span class='ag-dot' style='background:#FBBF24'></span>Sample data</span>"
          if data.sample_used() else "")
chips_slot.markdown(
    f"<div class='ag-dockstate'><span class='ag-dockchip'><span class='ag-dot' style='background:"
    f"{'#FB7185' if lv == 'red' else '#34D399'}'></span>{txt}</span>{sample}"
    f"</div>", unsafe_allow_html=True)

st.markdown("<div class='ag-sub' style='text-align:center;margin-top:28px'>Sandbox only: no real money moves. "
            "Not financial advice. Provider fees are simulated.</div>", unsafe_allow_html=True)
