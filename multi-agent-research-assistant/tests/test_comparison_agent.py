"""Comparison Agent tests (LLM faked): select -> evidence -> one row per model -> differences."""

from agents import comparison_agent as ca
from schemas.research import ResearchFinding, ResearchOutput, Source
from tests.fakes import FakeLLM, make_sources
from utils.evidence import is_own_source, mentions, model_evidence, rank_models

SOURCES = make_sources()  # S1 card, S2 paper, S3 GitHub repo (licence metadata "MIT")
RESEARCH = ResearchOutput(
    findings=[
        ResearchFinding(source_id="S1", title="org/Model-A — model card", summary="7B VLM",
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


def test_code_attaches_citations_from_the_models_a_sentence_names():
    # real output of qwen3.5:2b: sensible sentences, but no citations at all
    responses = {**RESPONSES, "DifferencesLLM": {"key_differences": [
        "Model B supports audio while Model A does not.", "Both are interesting."]}}
    out, _ = _run(responses)
    assert out.key_differences == ["Model B supports audio while Model A does not [S2][S3][S1]."]


def test_models_with_their_own_card_are_always_compared():
    # live bug: the LLM picked "SiTU-GLU" (an architecture component) instead of the model with a card
    responses = {**RESPONSES, "ModelSelection": {"models": ["Model B"]}}
    out, _ = _run(responses)
    assert {m.model_name for m in out.models} == {"Model A", "Model B"}


def test_placeholder_values_become_not_documented_so_metadata_can_fill_them():
    from schemas.comparison import ComparisonRowLLM

    row = ComparisonRowLLM(parameter_sizes="", licence="N/A", context_window="  ")
    assert row.parameter_sizes == row.licence == row.context_window == ca.NOT_DOCUMENTED


def test_price_in_licence_field_is_rejected():
    # real output: licence="$0.07/1M tokens"
    assert ca.sanitize_licence("$0.07/1M tokens") == ca.NOT_DOCUMENTED
    assert ca.sanitize_licence("Apache-2.0") == "Apache-2.0"


def test_failed_differences_step_is_reported_not_hidden():
    # real issue: in a live run the step failed silently and the list was just empty
    from services.ollama_client import OllamaResponseError

    out, _ = _run({**RESPONSES, "DifferencesLLM": OllamaResponseError("bad json")})
    assert out.models and out.key_differences == []
    assert "Key-differences step failed" in out.warnings[0]


def test_selection_failure_falls_back_to_most_evidenced_models():
    responses = {**RESPONSES, "ModelSelection": {"models": ["Totally Unknown"]}}
    out, _ = _run(responses)
    assert out.models[0].model_name == "Model B"  # mentioned by 2 findings


def test_comparison_with_no_findings_skips_llm():
    llm = FakeLLM({})
    out = ca.run("topic", ResearchOutput(), [], llm=llm)
    assert out.models == [] and llm.calls == []


# ---------------------------------------------------------------- evidence grouping
def test_mentions_matches_name_variants_but_not_other_versions():
    assert mentions("Qwen/Qwen3.8-27B", "the qwen3.8 27b model")
    assert mentions("Kimi K3.1-Pro", "moonshotai/Kimi-K3.1-Pro")
    assert not mentions("Kimi-K3.1-Pro", "Kimi K3")
    # live bug: "Kimi K3" matched "Kimi K3.1-Pro" and inherited its 2.78T parameter count
    assert not mentions("Kimi K3", "Kimi K3.1-Pro has 2780B parameters")
    assert mentions("Kimi K3", "Kimi K3 handles video")
    assert mentions("AuK", "AuK is an audio model") and not mentions("AuK", "Baukasten")


def test_own_source_requires_exact_card_or_repo_name():
    card = ResearchFinding(source_id="S3", title="moonshotai/Kimi-K3.1-Pro — model card", summary="s",
                           source_url="https://huggingface.co/moonshotai/Kimi-K3.1-Pro", source_type="documentation")
    assert is_own_source("Kimi K3.1-Pro", card)
    assert not is_own_source("Kimi K3", card)


def test_rank_models_orders_by_evidence_and_drops_unmentioned():
    research = RESEARCH.model_copy(update={"models_identified": ["Ghost", "Model A", "Model B"]})
    # Model A: 1 mention + own model card bonus (2) = 3; Model B: 2 mentions + own repo (2) = 4
    assert rank_models(research) == ["Model B", "Model A"]


def test_rank_models_prefers_models_with_their_own_model_card():
    card = ResearchFinding(source_id="S1", title="org/Model-X — model card", summary="s",
                           source_url="https://huggingface.co/org/Model-X", source_type="documentation")
    listing = ResearchFinding(source_id="S2", title="Top models", summary="Model Y and Model Y2 and Model-X",
                              source_url="https://example.com/top", source_type="web",
                              key_findings=["Model Y is fast", "Model Y is cheap"])
    listing2 = listing.model_copy(update={"source_id": "S3", "source_url": "https://example.com/top2"})
    research = ResearchOutput(findings=[card, listing, listing2], models_identified=["Model Y", "Model-X"])
    # Model Y: 2 mentions; Model-X: 3 mentions (card + both listings) + bonus -> first
    assert rank_models(research)[0] == "Model-X"


def test_model_card_contributes_all_its_facts_and_api_metadata():
    card = Source(source_id="S9", title="org/Model-C — model card", url="https://huggingface.co/org/Model-C",
                  source_type="documentation", metadata={"license_hf": "apache-2.0", "parameters_hf": "4.2B"})
    research = ResearchOutput(findings=[ResearchFinding(
        source_id="S9", title=card.title, summary="s", source_url=card.url, source_type="documentation",
        key_findings=["Context: 32k tokens"])])
    lines, ids = model_evidence("Model-C", research, {"S9": card})
    assert ids == ["S9"]
    assert "[S9] Context: 32k tokens" in lines and "[S9] Licence (Hugging Face metadata): apache-2.0" in lines
