"""Smoke tests: every screen opens without an error in demo mode.

Updated for the v3 screen: navigation is a radio in the main area (key "nav"),
not in the sidebar; the first button on every page is the dock's Lock button;
the confirmation card is titled "Approve payment".
"""
import os
import re

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "app.py")
PAGES = ["Assistant", "Money", "Payees", "Attack Lab", "Proof Pack"]


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setenv("AG_MOCK", "1")


def all_text(at) -> str:
    """Join every piece of text the page shows, so tests do not depend on layout."""
    parts = []
    for group in (at.markdown, at.caption, at.text, at.subheader, at.header, at.title):
        parts += [str(el.value) for el in group]
    parts += [str(m.value) for m in at.metric]
    parts += [str(b.label) for b in at.button]
    try:
        parts += [str(el.proto) for el in at.get("html")]
    except Exception:
        pass
    return "\n".join(parts)


def open_page(page: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    at.radio(key="nav").set_value(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_opens(page):
    at = open_page(page)
    assert not at.exception, [e.value for e in at.exception]


def test_attack_lab_runs():
    at = open_page("Attack Lab")
    run_buttons = [b for b in at.button if "run all" in str(b.label).lower()]
    assert run_buttons, "Run all attacks button not found"
    run_buttons[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert re.search(r"19\s*/\s*19", all_text(at)), "expected 19/19 attacks stopped"


def test_assistant_chat_and_confirm_card():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.chat_input[0].set_value("compare routes and draft payment of 500 EUR").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Approve payment" in all_text(at)