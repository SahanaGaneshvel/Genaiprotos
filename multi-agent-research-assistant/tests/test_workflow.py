"""LangGraph workflow tests: execution order, shared state, routing and failure handling.
The real graph runs; only the LLM and the retrieval tools are faked."""

import pytest

from agents import research_agent as ra
from orchestration import workflow as wf
from orchestration.state import merge_dicts
from schemas.research import Source
from services.errors import RetrievalError
from services.ollama_client import OllamaResponseError
from tests.fakes import FakeLLM

TOPIC = "Open-source multimodal models for on-premise deployment"

RESPONSES = {
    "SearchPlan": {"web_queries": ["open vlm"], "arxiv_query": "open vlm", "github_query": "vlm"},
    "FindingExtraction": {"relevant": True, "summary": "Model A is a 7B VLM.",
                          "key_findings": ["7B", "MMMU 58.6"], "models_mentioned": ["Model A"]},
    "ModelSelection": {"models": ["Model A"]},
    "ComparisonRowLLM": {"parameter_sizes": "7B", "licence": "Apache-2.0"},
    "EvaluationLLMOutput": {"benchmarks": [{"model_name": "Model A", "benchmark": "MMMU",
                                            "score": "58.6", "source_id": "S1"}],
                            "assessments": [], "missing_evidence": ["No VRAM data."]},
    "ReportNarrative": {"executive_summary": "Model A is a 7B VLM [S1].", "comparative_analysis": "x [S1]",
                        "benchmark_discussion": "MMMU 58.6 [S1]", "recommendations": ["Pilot Model A [S1]."]},
}


@pytest.fixture
def tools(monkeypatch):
    card = Source(title="Model A card", url="https://huggingface.co/org/a", source_type="documentation",
                  content="Model A 7B vision-language model. MMMU 58.6. Apache-2.0.")
    monkeypatch.setattr(ra, "search_web", lambda q, n: [card.model_copy()])
    monkeypatch.setattr(ra, "search_models", lambda task, n: [])
    monkeypatch.setattr(ra, "search_arxiv", lambda q, n: [])
    monkeypatch.setattr(ra, "search_github", lambda q, n: [])
    monkeypatch.setattr(ra, "fetch_page", lambda url: None)


def _use_llm(monkeypatch, llm):
    monkeypatch.setattr(wf, "_llm", lambda: llm)
    return llm


def test_agents_execute_in_fixed_order_and_share_state(tools, monkeypatch):
    _use_llm(monkeypatch, FakeLLM(RESPONSES))
    events = []
    state = wf.run_workflow(TOPIC, "basic", events.append)

    assert state["execution_order"] == ["orchestrator", "research", "comparison", "evaluation", "report"]
    assert set(state["agent_status"].values()) == {"completed"}
    # shared state: each agent's output is present and built on the previous one
    assert state["sources"][0].source_id == "S1"
    assert state["research"].findings[0].source_id == "S1"
    assert state["comparison"].models[0].model_name == "Model A"
    assert state["evaluation"].benchmarks[0].verified_in_source
    assert "## 10. References" in state["report"].markdown
    assert state["report"].citation_check["unknown"] == []
    assert {"research", "comparison", "evaluation", "report", "total"} <= set(state["timings"])


def test_live_status_events_are_real_transitions(tools, monkeypatch):
    _use_llm(monkeypatch, FakeLLM(RESPONSES))
    events = []
    wf.run_workflow(TOPIC, "basic", events.append)
    transitions = [(e["agent"], e["status"]) for e in events if "status" in e]
    assert transitions == [
        ("research", "running"), ("research", "completed"),
        ("comparison", "running"), ("comparison", "completed"),
        ("evaluation", "running"), ("evaluation", "completed"),
        ("report", "running"), ("report", "completed"),
    ]


def test_missing_model_stops_before_any_agent(tools, monkeypatch):
    _use_llm(monkeypatch, FakeLLM(RESPONSES, healthy=(False, "Model 'qwen3.5:4b' is not downloaded.")))
    state = wf.run_workflow(TOPIC)
    assert state["execution_order"] == ["orchestrator"]
    assert "not downloaded" in state["abort_reason"]
    assert set(state["agent_status"].values()) == {"pending"}
    assert "report" not in state


def test_invalid_topic_is_rejected(monkeypatch):
    _use_llm(monkeypatch, FakeLLM(RESPONSES))
    state = wf.run_workflow("??")
    assert state["execution_order"] == ["orchestrator"] and "10 characters" in state["abort_reason"]


def test_no_sources_produces_honest_insufficient_report(monkeypatch):
    def offline(*a, **k):
        raise RetrievalError("no internet")

    for name in ("search_web", "search_models", "search_arxiv", "search_github"):
        monkeypatch.setattr(ra, name, offline)
    llm = _use_llm(monkeypatch, FakeLLM(RESPONSES))
    state = wf.run_workflow(TOPIC)

    assert state["execution_order"] == ["orchestrator", "research", "report"]
    assert state["agent_status"]["comparison"] == "skipped"
    assert state["report"].insufficient_evidence
    assert "no sources were retrieved" in state["report"].markdown
    assert not any(name == "ComparisonRowLLM" for name, _ in llm.calls)


def test_sources_but_no_relevant_findings_also_gives_insufficient_report(tools, monkeypatch):
    # real failure from the first live run: 2 off-topic papers, 0 findings, yet a "normal" report
    responses = {**RESPONSES, "FindingExtraction": {**RESPONSES["FindingExtraction"],
                                                    "relevant": False, "key_findings": []}}
    llm = _use_llm(monkeypatch, FakeLLM(responses))
    state = wf.run_workflow(TOPIC)
    assert state["execution_order"] == ["orchestrator", "research", "report"]
    assert state["report"].insufficient_evidence
    assert "none was judged relevant" in state["report"].markdown
    assert not any(name == "ReportNarrative" for name, _ in llm.calls)


def test_one_failing_agent_does_not_stop_the_pipeline(tools, monkeypatch):
    responses = {**RESPONSES, "ComparisonRowLLM": OllamaResponseError("garbage")}
    _use_llm(monkeypatch, FakeLLM(responses))
    state = wf.run_workflow(TOPIC)
    assert state["agent_status"]["comparison"] == "failed"
    assert state["agent_status"]["report"] == "completed"
    assert any("comparison agent failed" in e for e in state["errors"])


def test_reducer_merges_instead_of_overwriting():
    assert merge_dicts({"research": "completed"}, {"comparison": "running"}) == {
        "research": "completed", "comparison": "running"}
