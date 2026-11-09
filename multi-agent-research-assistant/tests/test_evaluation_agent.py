"""Evaluation Agent tests — focus: fabricated benchmark numbers never survive."""

from agents import evaluation_agent as ea
from schemas.evaluation import BenchmarkResult
from schemas.research import ResearchFinding, ResearchOutput
from tests.fakes import FakeLLM, make_sources

SOURCES = make_sources()  # S1 text contains "MMMU 58.6"; S2 "61.2 on MMBench"
RESEARCH = ResearchOutput(
    findings=[
        ResearchFinding(source_id="S1", title="Model A model card", summary="s",
                        source_url="https://huggingface.co/org/model-a", source_type="documentation",
                        key_findings=["MMMU 58.6"]),
    ],
    models_identified=["Model A", "Model B"],
)

LLM_REPLY = {
    "benchmarks": [
        {"model_name": "Model A", "benchmark": "MMMU", "score": "58.6", "source_id": "S1", "reported_by": "official"},
        {"model_name": "Model B", "benchmark": "MMBench", "score": "61.2", "source_id": "S2"},
        # fabricated: number not in S1
        {"model_name": "Model A", "benchmark": "MMMU", "score": "72.4", "source_id": "S1"},
        # fabricated: source does not exist
        {"model_name": "Model C", "benchmark": "MMMU", "score": "58.6", "source_id": "S9"},
    ],
    "assessments": [
        {"model_name": "Model B", "onprem_suitability": "high", "rationale": "Small [S2][S9]",
         "source_ids": ["S2", "S9"], "quantisation_options": ["4-bit"]},
        {"model_name": "Model Z", "onprem_suitability": "high", "rationale": "Trust me", "source_ids": []},
    ],
    "trade_offs": ["Smaller models trade accuracy for memory [S3]."],
    "missing_evidence": ["No VRAM figures for Model A."],
    "recommendations": ["Start with Model B [S2]."],
}


def _run():
    return ea.run("topic", RESEARCH, SOURCES, llm=FakeLLM({"EvaluationLLMOutput": LLM_REPLY}))


def test_only_scores_found_in_source_text_are_kept():
    out = _run()
    assert [(b.model_name, b.score) for b in out.benchmarks] == [("Model A", "58.6"), ("Model B", "61.2")]
    assert all(b.verified_in_source for b in out.benchmarks)
    assert {b.score for b in out.rejected_benchmarks} == {"72.4", "58.6"}
    assert any("could not be found" in m for m in out.missing_evidence)


def test_assessment_without_evidence_is_downgraded():
    out = _run()
    model_z = next(a for a in out.assessments if a.model_name == "Model Z")
    assert model_z.onprem_suitability == "insufficient evidence"
    model_b = next(a for a in out.assessments if a.model_name == "Model B")
    assert model_b.source_ids == ["S2"] and "[S9]" not in model_b.rationale


def test_disclaimer_says_no_benchmarks_were_run():
    assert "No benchmarks were executed" in _run().disclaimer


def test_score_check_requires_benchmark_name_too():
    src = SOURCES[0]  # mentions MMMU 58.6
    assert ea.score_in_source(BenchmarkResult(model_name="A", benchmark="MMMU", score="58.6", source_id="S1"), src)
    assert not ea.score_in_source(BenchmarkResult(model_name="A", benchmark="DocVQA", score="58.6", source_id="S1"), src)


def test_memory_estimates_come_only_from_api_parameter_counts():
    srcs = make_sources()
    srcs[0].metadata.update({"model_id": "org/model-a", "parameters_total": 8_000_000_000, "parameters_hf": "8.00B"})
    [est] = ea.memory_estimates(srcs)  # S2/S3 have no API parameter count -> no estimate
    assert est.model_name == "org/model-a" and est.source_id == "S1"
    assert (est.fp16_gb, est.int8_gb, est.int4_gb) == (19.2, 9.6, 4.8)  # params x bytes x 1.2


def test_no_findings_means_no_llm_call_and_missing_evidence():
    llm = FakeLLM({})
    out = ea.run("topic", ResearchOutput(), [], llm=llm)
    assert llm.calls == [] and out.missing_evidence
