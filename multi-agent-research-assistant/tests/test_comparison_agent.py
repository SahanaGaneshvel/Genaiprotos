"""Comparison Agent tests (LLM faked)."""

from agents import comparison_agent as ca
from schemas.research import ResearchFinding, ResearchOutput
from tests.fakes import FakeLLM

RESEARCH = ResearchOutput(
    findings=[
        ResearchFinding(
            source_id="S1", title="Model A card", summary="7B VLM",
            source_url="https://huggingface.co/org/a", source_type="documentation",
            key_findings=["7B parameters", "Apache-2.0"],
        ),
        ResearchFinding(
            source_id="S2", title="Model B paper", summary="3B omni model",
            source_url="https://arxiv.org/abs/2501.2", source_type="arxiv",
            key_findings=["3B parameters", "image and audio"],
        ),
    ],
    models_identified=["Model A", "Model B"],
)

LLM_REPLY = {
    "models": [
        {"model_name": "Model A", "parameter_sizes": "7B", "licence": "Apache-2.0", "source_ids": ["S1"]},
        {"model_name": "Model B", "parameter_sizes": "3B", "licence": "Llama 3 Community License",
         "source_ids": ["S2", "S42"]},
        {"model_name": "Hallucinated Model", "parameter_sizes": "70B", "source_ids": ["S99"]},
    ],
    "key_differences": ["A is larger than B [S1][S2].", "A beats everything [S77]."],
}


def test_comparison_uses_research_findings_in_prompt():
    llm = FakeLLM({"ComparisonLLMOutput": LLM_REPLY})
    ca.run("topic", RESEARCH, {"S1", "S2"}, llm=llm)
    prompt = llm.calls[0][1]
    assert "[S1] Model A card" in prompt and "3B parameters" in prompt


def test_comparison_drops_unsupported_rows_and_citations():
    out = ca.run("topic", RESEARCH, {"S1", "S2"}, llm=FakeLLM({"ComparisonLLMOutput": LLM_REPLY}))
    assert [m.model_name for m in out.models] == ["Model A", "Model B"]
    assert out.dropped_models == ["Hallucinated Model"]
    assert out.models[1].source_ids == ["S2"]  # S42 removed
    assert "[S77]" not in " ".join(out.key_differences)


def test_comparison_licence_category_set_by_code():
    out = ca.run("topic", RESEARCH, {"S1", "S2"}, llm=FakeLLM({"ComparisonLLMOutput": LLM_REPLY}))
    assert out.models[0].licence_category == "Open source (OSI-approved licence)"
    assert out.models[1].licence_category == "Open weights (custom / restricted licence)"


def test_comparison_with_no_findings_skips_llm():
    llm = FakeLLM({})
    out = ca.run("topic", ResearchOutput(), set(), llm=llm)
    assert out.models == [] and llm.calls == []
