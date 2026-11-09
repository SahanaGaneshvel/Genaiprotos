"""Headless UI smoke tests using Streamlit's AppTest (no browser, no Ollama)."""

import json

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


def _example_state() -> dict:
    """The saved state of the real example run, rebuilt into Pydantic objects."""
    from schemas.comparison import ComparisonOutput
    from schemas.evaluation import EvaluationOutput
    from schemas.report import ReportOutput
    from schemas.research import ResearchOutput, Source

    raw = json.loads((PROJECT_ROOT / "outputs" / "example_run.json").read_text(encoding="utf-8"))
    return {
        **raw,
        "sources": [Source(**s) for s in raw["sources"]],
        "research": ResearchOutput(**raw["research"]),
        "comparison": ComparisonOutput(**raw["comparison"]),
        "evaluation": EvaluationOutput(**raw["evaluation"]),
        "report": ReportOutput(**raw["report"]),
    }


def test_full_results_render_after_a_run(monkeypatch):
    import orchestration.workflow as wf

    state = _example_state()

    def fake_run(topic, depth, on_event):
        for agent in ("research", "comparison", "evaluation", "report"):
            on_event({"agent": agent, "status": "running"})
            on_event({"agent": agent, "status": "completed", "seconds": 1.0})
        return state

    monkeypatch.setattr(wf, "run_workflow", fake_run)
    monkeypatch.setattr(wf, "save_run", lambda s: {"markdown": "x.md", "json": "x.json"})
    at = _app(monkeypatch, healthy=True)
    at.button[0].click().run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Research Findings", "Model Comparison", "Evaluation", "Final Report"]
    assert at.metric[0].value == str(len(state["sources"]))  # sources retrieved
    page = " ".join(m.value for m in at.markdown)
    assert page.count("Completed") == 4  # all four agent cards show the real final status
    assert "## 10. References" in page  # rendered report
    assert any(d.proto.label.startswith("⬇️ Download report") for d in at.get("download_button"))


def test_start_button_disabled_and_error_shown_when_ollama_down(monkeypatch):
    at = _app(monkeypatch, healthy=False)
    assert at.button[0].disabled
    assert "Cannot reach Ollama" in at.error[0].value
