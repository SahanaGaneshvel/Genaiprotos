"""AGENT 4 — Report Agent.

Responsibility: consolidate the Research, Comparison and Evaluation outputs into one
coherent technical report with the 10 required sections.

Division of labour:
  LLM  -> ReportNarrative: executive summary, analysis prose, deployment notes, risks, recommendations
  CODE -> research objective, methodology (from real run statistics), every table,
          and the References section (from the source registry — real URLs only)
Afterwards code strips any citation ID that is not in the registry and audits the report.

If no sources were retrieved, build_insufficient_evidence_report() is used instead: the
report states that research failed and makes no claims.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from schemas.comparison import ComparisonOutput
from schemas.evaluation import BENCHMARK_DISCLAIMER, EvaluationOutput
from schemas.report import ReportNarrative, ReportOutput
from schemas.research import ResearchOutput, Source
from services.ollama_client import OllamaClient, OllamaConnectionError, OllamaError, OllamaModelNotFoundError
from utils.citations import check_consistency, find_citations, format_reference, strip_invalid_citations
from utils.helpers import dedupe_keep_order, md_table, truncate

SYSTEM_PROMPT = """You are the REPORT AGENT in a team of AI research agents.
Your responsibility: write the narrative parts of a technical research report by consolidating
the outputs of the Research, Comparison and Evaluation agents.
Rules you must follow:
- Use ONLY the information provided below. Do not add outside facts, models or numbers.
- Support factual statements with citations in the form [S1], [S2] using ONLY the source IDs provided.
- Remove duplication: say each point once, in the most relevant section.
- Clearly separate facts from judgement: prefix qualitative judgements with "Assessment:" and
  estimates with "Estimate:". Recommendations are advice, not facts.
- Never claim that any benchmark was run by this team; scores are only as reported by sources.
- Distinguish open-weight models from models under OSI-approved open-source licences.
- If evidence is thin, say so plainly.
- Answer with a JSON object that matches the requested schema. No extra text."""

USER_PROMPT = """Research topic: {topic}

== RESEARCH AGENT: key findings ==
{findings}

== COMPARISON AGENT: comparison table ==
{comparison}
Key differences: {differences}

== EVALUATION AGENT ==
Verified benchmark scores (as reported by sources, NOT run by us):
{benchmarks}
On-prem assessments:
{assessments}
Trade-offs: {trade_offs}
Missing evidence: {missing}
Evaluation recommendations: {recommendations}

Write the report narrative. Return JSON only."""


# ------------------------------------------------------------------ prompt context
def _findings_brief(research: ResearchOutput) -> str:
    return "\n".join(
        f"[{f.source_id}] {f.title}: {truncate(f.summary, 220)} Facts: {truncate('; '.join(f.key_findings), 300)}"
        for f in research.findings
    ) or "(none)"


def _comparison_brief(c: ComparisonOutput) -> str:
    return "\n".join(
        f"- {m.model_name}: modalities={', '.join(m.modalities) or 'n/d'}; params={m.parameter_sizes}; "
        f"context={m.context_window}; hardware={m.hardware_requirements}; licence={m.licence} "
        f"({m.licence_category}); sources={','.join(m.source_ids)}"
        for m in c.models
    ) or "(no comparison rows)"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- None reported."


# ------------------------------------------------------------------ code-built sections
def methodology_section(
    research: ResearchOutput, sources: list[Source], model_name: str, depth: str
) -> str:
    counts = Counter(s.source_type for s in sources)
    plan = research.search_plan
    queries = []
    if plan:
        queries = [f"Web: “{q}”" for q in plan.web_queries] + [
            f"arXiv: “{plan.arxiv_query}”",
            f"GitHub: “{plan.github_query}”",
            f"Model cards: “{plan.github_query} model card site:huggingface.co”",
        ]
    parts = [
        f"This report was produced automatically by four cooperating agents orchestrated with "
        f"LangGraph, using the local model `{model_name}` via Ollama (research depth: **{depth}**).",
        "",
        "1. **Research Agent** planned search queries, retrieved sources from DuckDuckGo web search, "
        "Hugging Face model cards (via web search), arXiv and GitHub, fetched page text, and extracted findings per source.",
        "2. **Comparison Agent** compared the identified models using only those findings.",
        "3. **Evaluation Agent** extracted reported benchmark scores and assessed on-premise suitability; "
        "every score was checked to appear in the cited source's text.",
        "4. **Report Agent** consolidated the outputs; tables and references were generated from structured data.",
        "",
        "**Queries executed:**",
        _bullets(queries) if queries else "- (no search plan recorded)",
        "",
        "**Sources retrieved:** "
        + (", ".join(f"{n} {t}" for t, n in sorted(counts.items())) or "none")
        + f" — {len(sources)} total, {len(research.findings)} judged relevant.",
    ]
    if research.retrieval_errors:
        parts += ["", "**Retrieval issues encountered:**", _bullets(research.retrieval_errors)]
    parts += [
        "",
        "**Legend:** statements with [S#] are taken from the cited source; text marked *Assessment* is a "
        "qualitative judgement by the agents; *Recommendations* are advice, not measured facts.",
    ]
    return "\n".join(parts)


def models_section(research: ResearchOutput, comparison: ComparisonOutput) -> str:
    lines = []
    compared = {m.model_name.lower() for m in comparison.models}
    for m in comparison.models:
        lines.append(f"- **{m.model_name}** — {m.developer}. " + "".join(f"[{s}]" for s in m.source_ids))
    others = [m for m in research.models_identified if m.lower() not in compared]
    if others:
        lines.append(f"- Also mentioned in sources (not compared in detail): {', '.join(others[:15])}")
    return "\n".join(lines) or "No specific models or technologies could be identified from the retrieved sources."


def comparison_table(comparison: ComparisonOutput) -> str:
    if not comparison.models:
        return "_No comparison table could be produced from the retrieved evidence._"
    rows = [
        [
            m.model_name,
            ", ".join(m.modalities),
            m.parameter_sizes,
            m.context_window,
            ", ".join(m.deployment_methods),
            m.hardware_requirements,
            m.licence,
            m.licence_category,
            "".join(f"[{s}]" for s in m.source_ids),
        ]
        for m in comparison.models
    ]
    headers = ["Model", "Modalities", "Parameters", "Context", "Deployment", "Hardware", "Licence",
               "Licence type", "Sources"]
    return md_table(headers, rows)


def benchmark_table(evaluation: EvaluationOutput) -> str:
    if not evaluation.benchmarks:
        return "_No benchmark scores could be verified in the retrieved sources._"
    return md_table(
        ["Model", "Benchmark", "Metric", "Reported score", "Reported by", "Source"],
        [[b.model_name, b.benchmark, b.metric, b.score, b.reported_by, f"[{b.source_id}]"]
         for b in evaluation.benchmarks],
    )


def deployment_table(evaluation: EvaluationOutput) -> str:
    if not evaluation.assessments:
        return ""
    return md_table(
        ["Model", "On-prem suitability (assessment)", "Memory / inference", "Quantisation", "Sources"],
        [[a.model_name, a.onprem_suitability, a.memory_and_inference, ", ".join(a.quantisation_options),
          "".join(f"[{s}]" for s in a.source_ids)] for a in evaluation.assessments],
    )


def references_section(markdown_body: str, sources: list[Source]) -> str:
    cited = set(find_citations(markdown_body))
    cited_src = [s for s in sources if s.source_id in cited]
    other = [s for s in sources if s.source_id not in cited]
    out = [format_reference(s) for s in cited_src] or ["- No sources were cited."]
    if other:
        out += ["", "**Other retrieved sources (consulted, not cited):**"] + [format_reference(s) for s in other]
    return "\n".join(out)


# ------------------------------------------------------------------ assembly
def assemble(
    topic: str,
    narrative: ReportNarrative | None,
    research: ResearchOutput,
    comparison: ComparisonOutput,
    evaluation: EvaluationOutput,
    sources: list[Source],
    model_name: str,
    depth: str,
) -> str:
    n = narrative
    no_narr = "_Narrative generation failed; this section is built from structured agent outputs only._"
    focus = research.search_plan.focus_points if research.search_plan else []

    risks = dedupe_keep_order((n.limitations_and_risks if n else []) + evaluation.missing_evidence)
    recs = dedupe_keep_order(n.recommendations if n and n.recommendations else evaluation.recommendations)
    deploy = dedupe_keep_order((n.deployment_considerations if n else []) + evaluation.trade_offs)

    body = f"""# Technical Research Report

**Topic:** {topic}
**Generated:** {datetime.now():%Y-%m-%d %H:%M} · **Local model:** `{model_name}` · **Sources:** {len(sources)}

## 1. Executive Summary
{n.executive_summary if n else no_narr}

## 2. Research Objective
{topic}

{"**Focus points:** " + "; ".join(focus) if focus else ""}

## 3. Research Methodology
{methodology_section(research, sources, model_name, depth)}

## 4. Models and Technologies Identified
{models_section(research, comparison)}

## 5. Comparative Analysis
{comparison_table(comparison)}

**Key differences**
{_bullets(comparison.key_differences)}

{n.comparative_analysis if n else ""}

## 6. Benchmark Evaluation
> {BENCHMARK_DISCLAIMER}

{benchmark_table(evaluation)}

{n.benchmark_discussion if n else ""}

{f"_{len(evaluation.rejected_benchmarks)} additional score(s) proposed during analysis were excluded because they could not be found in the cited source text._" if evaluation.rejected_benchmarks else ""}

## 7. On-Premise Deployment Considerations
{deployment_table(evaluation)}

{_bullets(deploy)}

## 8. Limitations and Risks
{_bullets(risks)}

- This report is limited to the {len(sources)} sources retrieved automatically; it is not a systematic review.
- Findings were extracted by a small local LLM and may contain extraction errors; verify critical facts in the cited sources.

## 9. Recommendations
_Recommendations are judgements based on the evidence above, not measured results._

{_bullets(recs)}
"""
    return body


def build_insufficient_evidence_report(topic: str, errors: list[str], model_name: str) -> ReportOutput:
    """Used when retrieval returned nothing: be honest, make no claims, no LLM call."""
    md = f"""# Technical Research Report — Insufficient Evidence

**Topic:** {topic}
**Generated:** {datetime.now():%Y-%m-%d %H:%M} · **Local model:** `{model_name}`

## Result
**The research could not be completed: no sources were retrieved.** No findings, comparisons,
benchmarks or recommendations are reported, because none could be supported by evidence.

## Retrieval issues
{_bullets(errors)}

## What to try
- Check your internet connection.
- Wait a minute if a rate limit was reported, then retry.
- Rephrase the topic with more specific technical keywords.
"""
    return ReportOutput(markdown=md, narrative_generated=False, insufficient_evidence=True,
                        citation_check={"cited": [], "unknown": [], "uncited": []})


def run(
    topic: str,
    research: ResearchOutput,
    comparison: ComparisonOutput,
    evaluation: EvaluationOutput,
    sources: list[Source],
    depth: str = "basic",
    llm: OllamaClient | None = None,
) -> ReportOutput:
    llm = llm or OllamaClient()
    valid = {s.source_id for s in sources}

    narrative: ReportNarrative | None = None
    try:
        narrative = llm.chat_structured(
            SYSTEM_PROMPT,
            USER_PROMPT.format(
                topic=topic,
                findings=_findings_brief(research),
                comparison=_comparison_brief(comparison),
                differences=" ".join(comparison.key_differences) or "(none)",
                benchmarks="\n".join(
                    f"- {b.model_name} {b.benchmark} ({b.metric}): {b.score} [{b.source_id}] ({b.reported_by})"
                    for b in evaluation.benchmarks
                ) or "(none verified)",
                assessments="\n".join(
                    f"- {a.model_name}: {a.onprem_suitability} — {a.rationale} memory: {a.memory_and_inference}"
                    for a in evaluation.assessments
                ) or "(none)",
                trade_offs=" ".join(evaluation.trade_offs) or "(none)",
                missing=" ".join(evaluation.missing_evidence) or "(none)",
                recommendations=" ".join(evaluation.recommendations) or "(none)",
            ),
            ReportNarrative,
            max_tokens=2500,
        )
    except (OllamaConnectionError, OllamaModelNotFoundError):
        raise
    except OllamaError:
        narrative = None  # fall back to a code-only report rather than failing the whole run

    body = assemble(topic, narrative, research, comparison, evaluation, sources, llm.model, depth)
    body, removed = strip_invalid_citations(body, valid)
    markdown = body + "\n## 10. References\n" + references_section(body, sources) + "\n"

    return ReportOutput(
        markdown=markdown,
        narrative_generated=narrative is not None,
        removed_citations=sorted(set(removed)),
        citation_check=check_consistency(markdown, sources),
    )
