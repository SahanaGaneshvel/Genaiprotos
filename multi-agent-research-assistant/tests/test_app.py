"""Headless UI smoke tests using Streamlit's AppTest (no browser, no Ollama)."""

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from config import PROJECT_ROOT
from services.ollama_client import OllamaClient

APP = PROJECT_ROOT / "app.py"


@pytest.fixture(autouse=True)
def clear_cache():
    st.cache_data.clear()


def _app(monkeypatch, healthy: bool):
    monkeypatch.setattr(OllamaClient, "check_health", lambda self: (healthy, "Cannot reach Ollama" if not healthy else "ok"))
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_app_renders_header_inputs_and_four_agent_cards(monkeypatch):
    at = _app(monkeypatch, healthy=True)
    assert at.title[0].value == "Multi-Agent AI Research Assistant"
    assert at.text_area[0].label == "Research topic"
    assert at.radio[0].options == ["Basic", "Detailed"]
    assert at.button[0].label == "Start Research" and not at.button[0].disabled
    page = " ".join(m.value for m in at.markdown)
    for name in ("Research Agent", "Comparison Agent", "Evaluation Agent", "Report Agent"):
        assert name in page
    assert page.count("Pending") == 4


def test_start_button_disabled_and_error_shown_when_ollama_down(monkeypatch):
    at = _app(monkeypatch, healthy=False)
    assert at.button[0].disabled
    assert "Cannot reach Ollama" in at.error[0].value
