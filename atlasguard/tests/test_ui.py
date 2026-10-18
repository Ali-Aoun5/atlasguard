"""Smoke tests: every screen opens without an error in demo mode."""
import os

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui", "app.py")
PAGES = ["Assistant", "Money", "Payees", "Attack Lab", "Proof Pack"]


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setenv("AG_MOCK", "1")


@pytest.mark.parametrize("page", PAGES)
def test_page_opens(page):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_attack_lab_runs():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.radio[0].set_value("Attack Lab").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("19 / 19" in m.value for m in at.metric)


def test_assistant_chat_and_confirm_card():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.chat_input[0].set_value("compare routes and draft payment of 500 EUR").run()
    assert not at.exception
    assert any("Confirm payment" in s.value for s in at.subheader)
