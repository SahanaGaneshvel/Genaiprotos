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


def test_insufficient_evidence_report_makes_no_claims():
    out = rp.build_insufficient_evidence_report("topic", ["web: offline", "arXiv: offline"], "m")
    assert out.insufficient_evidence and "no sources were retrieved" in out.markdown
    assert "Recommendations" not in out.markdown and "[S" not in out.markdown


def test_insufficient_report_lists_irrelevant_sources_honestly():
    out = rp.build_insufficient_evidence_report("topic", [], "m", SOURCES)
    assert "none was judged relevant" in out.markdown
    assert all(s.url in out.markdown for s in SOURCES)
