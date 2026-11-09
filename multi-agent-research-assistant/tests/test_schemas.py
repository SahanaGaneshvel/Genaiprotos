"""Pydantic schema validation: the contracts between agents."""

import pytest
from pydantic import ValidationError

from schemas.comparison import NOT_DOCUMENTED, ModelComparison
from schemas.evaluation import EvaluationLLMOutput
from schemas.research import ResearchFinding, SearchPlan, Source, validate_http_url
from utils.helpers import md_table, select_relevant_text, validate_topic


@pytest.mark.parametrize("url", ["https://arxiv.org/abs/1", "http://example.com/a?b=c"])
def test_valid_urls_accepted(url):
    assert validate_http_url(url) == url


@pytest.mark.parametrize("url", ["", "example.com", "ftp://x.org/f", "javascript:alert(1)", "https://", "https://a b.com"])
def test_invalid_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_http_url(url)


def test_source_rejects_bad_url_and_unknown_type():
    with pytest.raises(ValidationError):
        Source(title="t", url="not-a-url", source_type="web")
    with pytest.raises(ValidationError):
        Source(title="t", url="https://x.org", source_type="blog")


def test_research_finding_requires_registry_style_id():
    base = dict(title="t", summary="s", source_url="https://x.org", source_type="web")
    assert ResearchFinding(source_id="S12", **base).source_id == "S12"
    for bad in ("12", "source1", "S", "S1a"):
        with pytest.raises(ValidationError):
            ResearchFinding(source_id=bad, **base)


def test_search_plan_needs_at_least_one_web_query():
    with pytest.raises(ValidationError):
        SearchPlan(web_queries=[], arxiv_query="vlm", github_query="vlm")


def test_search_plan_cleans_bracketed_queries_from_small_models():
    # real output of qwen3.5:2b during the first live run
    plan = SearchPlan(
        web_queries=['"open models" AND on-prem'],
        arxiv_query="[multimodal model] [on-premise] [benchmark]",
        github_query="[multimodal model] [on-premise] [license]",
    )
    assert plan.arxiv_query == "multimodal model on-premise benchmark"
    assert plan.github_query == "multimodal model on-premise license"
    assert plan.web_queries == ["open models on-prem"]
    assert plan.hub_task == "any"


def test_search_plan_rejects_unknown_hub_task():
    with pytest.raises(ValidationError):
        SearchPlan(web_queries=["x y"], arxiv_query="a b", github_query="a b", hub_task="robots")


def test_comparison_row_defaults_to_not_documented():
    row = ModelComparison(model_name="Model A")
    assert row.parameter_sizes == NOT_DOCUMENTED and row.licence_category == "Unknown"


def test_evaluation_rejects_unknown_suitability_level():
    with pytest.raises(ValidationError):
        EvaluationLLMOutput.model_validate(
            {"assessments": [{"model_name": "A", "onprem_suitability": "amazing", "rationale": "x"}]}
        )


@pytest.mark.parametrize("topic", ["", "short", "1234567890 !!!", "x" * 1001])
def test_invalid_topics_rejected(topic):
    with pytest.raises(ValueError):
        validate_topic(topic)


def test_valid_topic_is_normalised():
    assert validate_topic("  open   multimodal models  ") == "open multimodal models"


def test_select_relevant_text_skips_boilerplate_and_keeps_order():
    # real failure: page starts with a nav menu; the model list comes later
    menu = "Home Pricing Blog Login Careers " * 40
    intro = "Multimodal models process text and images. " * 15
    facts = "Qwen2.5-VL-7B has 8.3B parameters, Apache-2.0 licence, needs 16 GB VRAM. "
    text = menu + intro + facts + menu
    out = select_relevant_text(text, ["multimodal", "models"], max_chars=700)
    assert "8.3B parameters" in out and "Pricing Blog" not in out
    assert out.index("Multimodal") < out.index("8.3B")  # original order preserved


def test_md_table_escapes_pipes():
    table = md_table(["A"], [["x | y"]])
    assert "x \\| y" in table
