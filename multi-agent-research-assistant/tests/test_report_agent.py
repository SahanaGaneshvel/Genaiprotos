"""Report Agent tests — structure, citation integrity, honest failure modes."""

import re

from agents import report_agent as rp
from schemas.comparison import ComparisonOutput, ModelComparison
from schemas.evaluation import BenchmarkResult, EvaluationOutput
from schemas.research import ResearchFinding, ResearchOutput
from services.ollama_client import OllamaResponseError
from tests.fakes import FakeLLM, make_sources

SOURCES = make_sources()
RESEARCH = ResearchOutput(
    findings=[ResearchFinding(source_id="S1", title="Model A card", summary="7B VLM",
                              source_url="https://huggingface.co/org/model-a", source_type="documentation")],
    models_identified=["Model A"],
)
COMPARISON = ComparisonOutput(models=[ModelComparison(model_name="Model A", licence="Apache-2.0",
                                                      licence_category="Open source (OSI-approved licence)",
                                                      source_ids=["S1"])])
EVALUATION = EvaluationOutput(
    benchmarks=[BenchmarkResult(model_name="Model A", benchmark="MMMU", score="58.6", source_id="S1",
                                verified_in_source=True)],
    missing_evidence=["No VRAM figures."],
)
NARRATIVE = {
    "executive_summary": "Model A is a 7B VLM [S1]. It is the best model ever [S42].",
    "comparative_analysis": "Only one model compared [S1].",
    "benchmark_discussion": "MMMU 58.6 as reported [S1].",
    "deployment_considerations": ["Assessment: fits on a single GPU [S3]."],
    "limitations_and_risks": ["Few sources."],
    "recommendations": ["Pilot Model A [S1]."],
}

SECTIONS = [
    "Executive Summary", "Research Objective", "Research Methodology", "Models and Technologies Identified",
    "Comparative Analysis", "Benchmark Evaluation", "On-Premise Deployment Considerations",
    "Limitations and Risks", "Recommendations", "References",
]


def _report(llm_reply=NARRATIVE):
    llm = FakeLLM({"ReportNarrative": llm_reply})
    return rp.run("open multimodal models", RESEARCH, COMPARISON, EVALUATION, SOURCES, llm=llm), llm


def test_report_has_all_ten_sections_in_order():
    out, _ = _report()
    headings = re.findall(r"^## \d+\. (.+)$", out.markdown, re.M)
    assert headings == SECTIONS


def test_invalid_citations_removed_and_references_are_real_urls():
    out, _ = _report()
    assert "[S42]" not in out.markdown and out.removed_citations == ["S42"]
    assert out.citation_check["unknown"] == []
    refs = out.markdown.split("## 10. References")[1]
    for url in re.findall(r"<(https?://[^>]+)>", refs):
        assert url in {s.url for s in SOURCES}


def test_report_prompt_uses_all_three_agent_outputs():
    _, llm = _report()
    prompt = llm.calls[0][1]
    assert "RESEARCH AGENT" in prompt and "Model A card" in prompt  # research
    assert "Apache-2.0" in prompt  # comparison
    assert "MMMU" in prompt and "No VRAM figures" in prompt  # evaluation


def test_report_states_benchmarks_were_not_run():
    out, _ = _report()
    assert "No benchmarks were executed by this application" in out.markdown


def test_narrative_failure_falls_back_to_code_only_report():
    out, _ = _report(OllamaResponseError("bad json"))
    assert not out.narrative_generated
    assert "Narrative generation failed" in out.markdown
    assert "| Model A |" in out.markdown  # tables still present


def test_misattributed_narrative_sentence_is_removed():
    # live bug: "Kimi K3.1-Pro is best for OCR [S2]" while S2 said that about Qwen3-VL
    reply = {**NARRATIVE, "comparative_analysis":
             "Model A is a 7B VLM [S1]. Model B is the best OCR model [S1]. Both are open [S1][S2]."}
    research = RESEARCH.model_copy(update={"models_identified": ["Model A", "Model B"]})
    out = rp.run("topic", research, COMPARISON, EVALUATION, SOURCES,
                 llm=FakeLLM({"ReportNarrative": reply}))
    assert "Model B is the best OCR model" not in out.markdown  # S1 never mentions Model B
    assert "Model A is a 7B VLM [S1]." in out.markdown
    assert out.removed_claims == ["Model B is the best OCR model [S1]."]
    assert "1 narrative sentence(s) were removed" in out.markdown


def test_attribution_check_is_strict_for_versions_lenient_for_descriptive_names():
    from schemas.research import Source

    src = Source(source_id="S8", title="allenzren/open-pi-zero", url="https://github.com/allenzren/open-pi-zero",
                 source_type="github", content="We fine-tune the PaliGemma model, a VLM with 3B parameters.")
    by_id = {"S8": src}
    models = ["open-pi-zero", "PaliGemma VLM", "Kimi K3.1-Pro"]
    # live false positive: "PaliGemma VLM" written differently in the source -> must be KEPT
    kept, removed = rp.check_attribution("open-pi-zero builds on the PaliGemma VLM [S8].", models, by_id)
    assert removed == [] and kept
    # versioned model name absent from the cited source -> still REMOVED
    _, removed = rp.check_attribution("Kimi K3.1-Pro is great at OCR [S8].", models, by_id)
    assert removed == ["Kimi K3.1-Pro is great at OCR [S8]."]


def test_rule_based_recommendations_use_licence_and_memory_estimate():
    from schemas.evaluation import MemoryEstimate

    evaluation = EVALUATION.model_copy(update={"memory_estimates": [MemoryEstimate(
        model_name="org/Model-A", parameters="8.00B", source_id="S1", fp16_gb=19.2, int8_gb=9.6, int4_gb=4.8)]})
    recs = rp.rule_based_recommendations(COMPARISON, evaluation)
    assert recs == ["**Model A**: OSI-approved licence (Apache-2.0) and ~4.8 GB of weights at 4-bit (estimate): "
                    "candidate for a single-GPU on-prem pilot; measure VRAM and run your own evaluation first [S1]."]


def test_memory_estimate_only_applies_to_exactly_that_model():
    # live bug: "P-H3-Image-Comfy" was given the estimate of "P-H3-Image"
    from schemas.comparison import ComparisonOutput, ModelComparison
    from schemas.evaluation import MemoryEstimate

    comparison = ComparisonOutput(models=[
        ModelComparison(model_name="PrunaAI/P-H3-Image", source_ids=["S1"]),
        ModelComparison(model_name="PrunaAI/P-H3-Image-Comfy", source_ids=["S2"]),
    ])
    evaluation = EVALUATION.model_copy(update={"memory_estimates": [MemoryEstimate(
        model_name="PrunaAI/P-H3-Image", parameters="33.12B", source_id="S1", fp16_gb=79.5, int8_gb=39.7, int4_gb=19.9)]})
    recs = rp.rule_based_recommendations(comparison, evaluation)
    assert "19.9 GB" in recs[0] and "19.9 GB" not in recs[1]


def test_recommendations_section_always_has_grounded_advice():
    out, _ = _report({**NARRATIVE, "recommendations": []})
    section = out.markdown.split("## 9. Recommendations")[1].split("## 10.")[0]
    assert "Rule-based" in section and "**Model A**" in section and "[S1]" in section


def test_insufficient_evidence_report_makes_no_claims():
    out = rp.build_insufficient_evidence_report("topic", ["web: offline", "arXiv: offline"], "m")
    assert out.insufficient_evidence and "no sources were retrieved" in out.markdown
    assert "Recommendations" not in out.markdown and "[S" not in out.markdown


def test_insufficient_report_lists_irrelevant_sources_honestly():
    out = rp.build_insufficient_evidence_report("topic", [], "m", SOURCES)
    assert "none was judged relevant" in out.markdown
    assert all(s.url in out.markdown for s in SOURCES)
