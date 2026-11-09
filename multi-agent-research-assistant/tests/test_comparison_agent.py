"""Comparison Agent tests (LLM faked): select -> evidence -> one row per model -> differences."""

from agents import comparison_agent as ca
from schemas.research import ResearchFinding, ResearchOutput, Source
from tests.fakes import FakeLLM, make_sources
from utils.evidence import mentions, model_evidence, rank_models

SOURCES = make_sources()  # S1 card, S2 paper, S3 GitHub repo (licence metadata "MIT")
RESEARCH = ResearchOutput(
    findings=[
        ResearchFinding(source_id="S1", title="Model A model card", summary="7B VLM",
                        source_url="https://huggingface.co/org/model-a", source_type="documentation",
                        key_findings=["7B parameters", "Apache-2.0"], models_mentioned=["Model A"]),
        ResearchFinding(source_id="S2", title="Model B paper", summary="Model B is a 3B omni model",
                        source_url="https://arxiv.org/abs/2501.00002", source_type="arxiv",
                        key_findings=["Model B has 3B parameters", "image and audio"],
                        models_mentioned=["Model B", "vLLM"]),
        ResearchFinding(source_id="S3", title="org/model-b", summary="Model B code",
                        source_url="https://github.com/org/model-b", source_type="github",
                        key_findings=["Model B runs with 8 GB VRAM"], models_mentioned=["Model B"]),
    ],
    models_identified=["Model A", "Model B", "vLLM"],
)


def _row(prompt: str) -> dict:
    if "MODEL: Model A" in prompt:
        return {"parameter_sizes": "7B", "licence": "Apache-2.0", "modalities": ["text", "image"]}
    return {"parameter_sizes": "3B", "modalities": ["image", "audio"]}  # licence left undocumented


RESPONSES = {
    "ModelSelection": {"models": ["Model B", "Hallucinated Model", "model a"]},
    "ComparisonRowLLM": _row,
    "DifferencesLLM": {"key_differences": [
        "A is larger than B [S1][S2].", "A is larger than B [S1][S2].", "A beats everything [S77]."]},
}


def _run(responses=RESPONSES):
    llm = FakeLLM(responses)
    return ca.run("topic", RESEARCH, SOURCES, llm=llm), llm


def test_selection_keeps_only_names_from_the_research():
    out, _ = _run()
    assert [m.model_name for m in out.models] == ["Model B", "Model A"]  # "Hallucinated Model" ignored


def test_each_row_prompt_contains_only_that_models_evidence():
    _, llm = _run()
    row_prompts = [p for name, p in llm.calls if name == "ComparisonRowLLM"]
    b_prompt = next(p for p in row_prompts if "MODEL: Model B" in p)
    assert "[S2] Model B has 3B parameters" in b_prompt and "8 GB VRAM" in b_prompt
    assert "7B parameters" not in b_prompt  # Model A's facts are not shown


def test_source_ids_are_set_by_code_from_evidence():
    out, _ = _run()
    b = next(m for m in out.models if m.model_name == "Model B")
    assert b.source_ids == ["S2", "S3"]


def test_undocumented_licence_filled_from_api_metadata_with_label():
    out, _ = _run()
    b = next(m for m in out.models if m.model_name == "Model B")
    assert b.licence == "MIT (GitHub metadata [S3])"
    assert b.licence_category == "Open source (OSI-approved licence)"


def test_differences_deduplicated_and_uncited_claims_dropped():
    out, _ = _run()
    # duplicate removed; "A beats everything [S77]" has no valid citation left -> dropped
    assert out.key_differences == ["A is larger than B [S1][S2]."]


def test_selection_failure_falls_back_to_most_evidenced_models():
    responses = {**RESPONSES, "ModelSelection": {"models": ["Totally Unknown"]}}
    out, _ = _run(responses)
    assert out.models[0].model_name == "Model B"  # mentioned by 2 findings


def test_comparison_with_no_findings_skips_llm():
    llm = FakeLLM({})
    out = ca.run("topic", ResearchOutput(), [], llm=llm)
    assert out.models == [] and llm.calls == []


# ---------------------------------------------------------------- evidence grouping
def test_mentions_matches_name_variants_but_not_substrings_of_short_names():
    assert mentions("Qwen/Qwen3.8-27B", "the qwen3.8 27b model")
    assert mentions("Kimi K3.1-Pro", "moonshotai/Kimi-K3.1-Pro")
    assert not mentions("Kimi-K3.1-Pro", "Kimi K3")  # a K3.1-Pro card must not describe "Kimi K3"
    assert mentions("AuK", "AuK is an audio model") and not mentions("AuK", "Baukasten")


def test_rank_models_orders_by_evidence_and_drops_unmentioned():
    research = RESEARCH.model_copy(update={"models_identified": ["Ghost", "Model A", "Model B"]})
    assert rank_models(research) == ["Model B", "Model A"]


def test_model_card_contributes_all_its_facts_and_api_metadata():
    card = Source(source_id="S9", title="org/Model-C — model card", url="https://huggingface.co/org/Model-C",
                  source_type="documentation", metadata={"license_hf": "apache-2.0", "parameters_hf": "4.2B"})
    research = ResearchOutput(findings=[ResearchFinding(
        source_id="S9", title=card.title, summary="s", source_url=card.url, source_type="documentation",
        key_findings=["Context: 32k tokens"])])
    lines, ids = model_evidence("Model-C", research, {"S9": card})
    assert ids == ["S9"]
    assert "[S9] Context: 32k tokens" in lines and "[S9] Licence (Hugging Face metadata): apache-2.0" in lines
