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
        "key_findings": [] if off_topic else ["7B parameters"],
        "limitations": [],
        "models_mentioned": ["Model A", "model a", "Model B"],
    }


@pytest.fixture
def fake_tools(monkeypatch):
    def web(query, n):
        return [
            Source(title="Comparison", url="https://example.com/compare", source_type="web", snippet="cmp"),
            Source(title="Cooking blog", url="https://example.com/food", source_type="web", snippet="food"),
        ]

    def arxiv(query, n):
        raise RetrievalError("arXiv is rate-limiting requests")

    def github(query, n):
        return [Source(title="org/a", url="https://github.com/org/a", source_type="github", content="readme")]

    def hub(task, n):
        return [Source(title="org/a — model card", url="https://huggingface.co/org/a",
                       source_type="documentation", metadata={"license_hf": "apache-2.0"})]

    monkeypatch.setattr(ra, "search_web", web)
    monkeypatch.setattr(ra, "search_models", hub)
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
    # Hugging Face model cards are tagged as documentation
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


def test_hub_metadata_is_given_to_the_llm_as_labelled_fact(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN, "FindingExtraction": _extraction})
    ra.run("open multimodal models for on-prem use", llm=llm)
    hf_prompt = next(p for name, p in llm.calls if name == "FindingExtraction" and "huggingface.co" in p)
    assert "Licence (from Hugging Face model card metadata): apache-2.0" in hf_prompt


def test_keyword_variants_drop_generic_terms_and_relax():
    # real failure: "on-premise" matched an arXiv paper about "premise-induced" hallucination
    assert ra.keyword_variants("multimodal model on-premise benchmark license") == ["multimodal model"]
    assert ra.keyword_variants("open vision language model") == ["open vision language model", "open vision"]


def test_empty_github_query_is_relaxed_once(fake_tools, monkeypatch):
    seen = []

    def github(query, n):
        seen.append(query)
        return [] if len(seen) == 1 else [Source(title="r", url="https://github.com/o/r", source_type="github")]

    monkeypatch.setattr(ra, "search_github", github)
    plan = {**PLAN, "github_query": "open vision language model"}
    ra.run("open multimodal models for on-prem use", llm=FakeLLM({"SearchPlan": plan, "FindingExtraction": _extraction}))
    assert seen == ["open vision language model", "open vision"]  # bounded: exactly 2 attempts


def test_multimodal_topic_overrides_wrong_hub_task(fake_tools, monkeypatch):
    tasks = []
    monkeypatch.setattr(ra, "search_models", lambda task, n: tasks.append(task) or [])
    plan = {**PLAN, "hub_task": "text-generation"}  # real mistake by qwen3.5:2b
    ra.run("open multimodal models for on-prem use", llm=FakeLLM({"SearchPlan": plan, "FindingExtraction": _extraction}))
    assert tasks == ["image-text-to-text"]


def test_source_marked_irrelevant_but_with_findings_is_kept(fake_tools):
    # real failure: a "Best open-source multimodal models" article had findings but relevant=false
    def extraction(prompt):
        return {"relevant": False, "summary": "s", "key_findings": ["Benchmarks rarely reflect production"]}

    _, out = ra.run("open multimodal models for on-prem use",
                    llm=FakeLLM({"SearchPlan": PLAN, "FindingExtraction": extraction}))
    assert len(out.findings) == 4


def test_extract_prompt_contains_only_that_source(fake_tools):
    llm = FakeLLM({"SearchPlan": PLAN, "FindingExtraction": _extraction})
    ra.run("open multimodal models for on-prem use", llm=llm)
    extraction_prompts = [p for name, p in llm.calls if name == "FindingExtraction"]
    assert "SOURCE [S1]" in extraction_prompts[0] and "SOURCE [S2]" not in extraction_prompts[0]
