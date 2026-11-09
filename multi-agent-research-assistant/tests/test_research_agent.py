"""Research Agent tests: tools and LLM are faked, so we test the agent's own logic."""

import pytest

from agents import research_agent as ra
from schemas.research import Source
from services.errors import RetrievalError
from services.ollama_client import OllamaModelNotFoundError
from tests.fakes import FakeLLM

PLAN = {
    "web_queries": ["open multimodal models on-prem"],
    "arxiv_query": "open multimodal model",
    "github_query": "vision language model",
    "focus_points": ["licensing"],
}


def _extraction(prompt: str) -> dict:
    off_topic = "Cooking blog" in prompt
    return {
        "relevant": not off_topic,
        "summary": "A relevant summary.",
        "key_findings": ["7B parameters"],
        "limitations": [],
        "models_mentioned": ["Model A", "model a", "Model B"],
    }


@pytest.fixture
def fake_tools(monkeypatch):
    def web(query, n):
        if "site:huggingface.co" in query:
            return [Source(title="Model A card", url="https://huggingface.co/org/a", source_type="web")]
        return [
            Source(title="Comparison", url="https://example.com/compare", source_type="web", snippet="cmp"),
            Source(title="Cooking blog", url="https://example.com/food", source_type="web", snippet="food"),
        ]

    def arxiv(query, n):
        raise RetrievalError("arXiv is rate-limiting requests")

    def github(query, n):
        return [Source(title="org/a", url="https://github.com/org/a", source_type="github", content="readme")]

    monkeypatch.setattr(ra, "search_web", web)
    monkeypatch.setattr(ra, "search_arxiv", arxiv)
    monkeypatch.setattr(ra, "search_github", github)
    monkeypatch.setattr(ra, "fetch_page", lambda url: None)  # every page fetch fails


def test_research_agent_survives_one_failed_tool(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN, "FindingExtraction": _extraction})
    sources, out = ra.run("open multimodal models for on-prem use", llm=llm)

    assert [s.source_id for s in sources] == ["S1", "S2", "S3", "S4"]
    assert any("arXiv" in e for e in out.retrieval_errors)  # failure recorded, not raised
    # off-topic source dropped from findings, but every finding points to a registered source
    assert {f.source_url for f in out.findings} <= {s.url for s in sources}
    assert "Cooking blog" not in [f.title for f in out.findings]
    # Hugging Face hits from the model-card query are tagged as documentation
    assert next(s for s in sources if "huggingface" in s.url).source_type == "documentation"
    # models are de-duplicated case-insensitively
    assert out.models_identified == ["Model A", "Model B"]


def test_failed_page_fetch_is_flagged_as_limitation(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN, "FindingExtraction": _extraction})
    _, out = ra.run("open multimodal models for on-prem use", llm=llm)
    web_finding = next(f for f in out.findings if f.source_url == "https://example.com/compare")
    assert any("snippet" in lim for lim in web_finding.limitations)


def test_bad_plan_output_uses_fallback_plan(fake_tools):
    llm = FakeLLM({"FindingExtraction": _extraction})  # no SearchPlan -> OllamaResponseError
    sources, out = ra.run("open multimodal models for on-prem use", llm=llm)
    assert sources and any("fallback" in e for e in out.retrieval_errors)


def test_bad_extraction_keeps_source_with_honest_note(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN})  # every extraction fails
    _, out = ra.run("open multimodal models for on-prem use", llm=llm)
    assert out.findings
    assert all("extraction failed" in f.limitations[0] for f in out.findings)
    assert all(f.key_findings == [] for f in out.findings)  # nothing invented


def test_missing_model_is_not_swallowed(fake_tools):
    llm = FakeLLM({"SearchPlan": OllamaModelNotFoundError("pull it")})
    with pytest.raises(OllamaModelNotFoundError):
        ra.run("open multimodal models for on-prem use", llm=llm)


def test_register_sources_dedupes_urls_and_arxiv_versions():
    srcs = [
        Source(title="a", url="https://arxiv.org/abs/2501.1v1", source_type="arxiv"),
        Source(title="a2", url="https://arxiv.org/abs/2501.1v2", source_type="arxiv"),
        Source(title="b", url="https://www.example.com/x/", source_type="web"),
        Source(title="b2", url="https://example.com/x", source_type="web"),
    ]
    out = ra.register_sources(srcs)
    assert [(s.source_id, s.title) for s in out] == [("S1", "a"), ("S2", "b")]


def test_extract_prompt_contains_only_that_source(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN, "FindingExtraction": _extraction})
    ra.run("open multimodal models for on-prem use", llm=llm)
    extraction_prompts = [p for name, p in llm.calls if name == "FindingExtraction"]
    assert "SOURCE [S1]" in extraction_prompts[0] and "SOURCE [S2]" not in extraction_prompts[0]
