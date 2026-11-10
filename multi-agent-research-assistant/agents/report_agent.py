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

import re
from collections import Counter
from datetime import datetime

from schemas.comparison import ComparisonOutput
from schemas.evaluation import BENCHMARK_DISCLAIMER, MEMORY_ESTIMATE_BASIS, EvaluationOutput
from schemas.report import ReportNarrative, ReportOutput
from schemas.research import ResearchOutput, Source
from services.ollama_client import OllamaClient, OllamaConnectionError, OllamaError, OllamaModelNotFoundError
from utils.citations import check_consistency, find_citations, format_reference, strip_invalid_citations
from utils.evidence import mentions, source_mentions
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
Estimated weight memory (computed by code from parameter counts; label as Estimate):
{memory}
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
            f"Hugging Face Hub API: trending models for task “{plan.hub_task}”",
            f"arXiv: “{plan.arxiv_query}” (relaxed to fewer keywords if empty)",
            f"GitHub: “{plan.github_query}” (relaxed to fewer keywords if empty)",
        ]
    parts = [
        f"This report was produced automatically by four cooperating agents orchestrated with "
        f"LangGraph, using the local model `{model_name}` via Ollama (research depth: **{depth}**).",
        "",
        "1. **Research Agent** planned search queries, retrieved sources from web search, the Hugging Face "
        "Hub API (model cards), arXiv and GitHub, selected the most informative passages of each page, and "
        "extracted findings per source.",
        "2. **Comparison Agent** selected the models, gathered the evidence about each one, and filled one table "
        "row per model; licence and parameter gaps were filled from API metadata.",
        "3. **Evaluation Agent** extracted reported benchmark scores (each checked to appear in the cited "
        "source's text), assessed on-premise suitability, and computed memory estimates from parameter counts.",
        "4. **Report Agent** consolidated the outputs; tables, references and rule-based recommendations were "
        "generated by code, and narrative sentences were checked for correct model-to-source attribution.",
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


SINGLE_GPU_GB = 24  # a common single workstation/server GPU size used as the pilot threshold


def _memory_for(model_name: str, evaluation: EvaluationOutput):
    """The estimate for exactly this model. Loose matching gave 'P-H3-Image-Comfy' the
    estimate of 'P-H3-Image' in a live run."""
    def key(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.split("/")[-1].lower())

    return next((m for m in evaluation.memory_estimates if key(m.model_name) == key(model_name)), None)


def rule_based_recommendations(comparison: ComparisonOutput, evaluation: EvaluationOutput) -> list[str]:
    """Deterministic, cited suggestions computed from the tables (licence + memory estimate).
    They do not depend on the LLM, so the report always has grounded, explainable advice."""
    recs = []
    for row in comparison.models:
        est = _memory_for(row.model_name, evaluation)
        ids = list(dict.fromkeys(row.source_ids + ([est.source_id] if est else [])))
        cites = "".join(f"[{i}]" for i in ids)
        lic = row.licence.split(" (")[0]
        if row.licence_category.startswith("Open source"):
            if est and est.int4_gb <= SINGLE_GPU_GB:
                recs.append(f"**{row.model_name}** — OSI-approved licence ({lic}) and ~{est.int4_gb} GB of weights "
                            f"at 4-bit (estimate): candidate for a single-GPU on-prem pilot; measure VRAM and run "
                            f"your own evaluation first {cites}.")
            elif est:
                recs.append(f"**{row.model_name}** — OSI-approved licence ({lic}), but ~{est.int4_gb} GB at 4-bit "
                            f"(estimate) needs multi-GPU / server hardware {cites}.")
            else:
                recs.append(f"**{row.model_name}** — OSI-approved licence ({lic}); size/hardware not documented in "
                            f"the retrieved sources — measure memory before committing {cites}.")
        elif row.licence_category.startswith("Open weights"):
            recs.append(f"**{row.model_name}** — open weights under a custom licence ({lic}): review usage "
                        f"restrictions before commercial on-prem use {cites}.")
        else:
            size = f"; ~{est.int4_gb} GB at 4-bit (estimate)" if est else ""
            recs.append(f"**{row.model_name}** — licence not established from the retrieved sources{size}: "
                        f"verify on the official model card before use {cites}.")
    return recs


def check_attribution(text: str, models: list[str], by_id: dict[str, Source]) -> tuple[str, list[str]]:
    """Claim-level guard for LLM prose: if a sentence names a model and cites sources, at least
    the cited sources must mention that model. Live run: "Kimi K3.1-Pro is best for OCR [S2]"
    while S2 said that about Qwen3-VL. Such sentences are removed and counted."""
    kept, removed = [], []
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        cited = [by_id[i] for i in find_citations(sentence) if i in by_id]
        named = [m for m in models if mentions(m, sentence)]
        if cited and named:
            corpus = " ".join(f"{s.title} {s.snippet} {s.content}" for s in cited)
            if any(not source_mentions(m, corpus) for m in named):
                removed.append(sentence)
                continue
        kept.append(sentence)
    return " ".join(kept), removed


def memory_table(evaluation: EvaluationOutput) -> str:
    if not evaluation.memory_estimates:
        return ""
    table = md_table(
        ["Model", "Parameters", "FP16 (GB)", "8-bit (GB)", "4-bit (GB)", "Source of param count"],
        [[m.model_name, m.parameters, m.fp16_gb, m.int8_gb, m.int4_gb, f"[{m.source_id}]"]
         for m in evaluation.memory_estimates],
    )
    return f"**Estimated weight memory**\n\n{table}\n\n_{MEMORY_ESTIMATE_BASIS}_"


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
    removed_claims: int = 0,
) -> str:
    n = narrative
    no_narr = "_Narrative generation failed; this section is built from structured agent outputs only._"
    focus = research.search_plan.focus_points if research.search_plan else []

    risks = dedupe_keep_order((n.limitations_and_risks if n else []) + evaluation.missing_evidence)
    if removed_claims:
        risks.append(f"{removed_claims} narrative sentence(s) were removed because they attributed a model to a "
                     "source that does not mention it.")
    rule_recs = rule_based_recommendations(comparison, evaluation)
    agent_recs = dedupe_keep_order(n.recommendations if n and n.recommendations else evaluation.recommendations)
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

{memory_table(evaluation)}

{_bullets(deploy)}

## 8. Limitations and Risks
{_bullets(risks)}

- This report is limited to the {len(sources)} sources retrieved automatically; it is not a systematic review.
- Findings were extracted by a small local LLM and may contain extraction errors; verify critical facts in the cited sources.

## 9. Recommendations
_Recommendations are judgements based on the evidence above, not measured results._

**Rule-based (computed by code from licence category and memory estimates):**
{_bullets(rule_recs)}

**Agent recommendations:**
{_bullets(agent_recs)}
"""
    return body


def build_insufficient_evidence_report(
    topic: str, errors: list[str], model_name: str, sources: list[Source] | None = None
) -> ReportOutput:
    """Used when retrieval found nothing usable: be honest, make no claims, no LLM call."""
    sources = sources or []
    if sources:
        result = (f"**The research could not be completed: {len(sources)} source(s) were retrieved, but none "
                  "was judged relevant to the topic.**")
        consulted = "\n## Sources retrieved (judged not relevant)\n" + "\n".join(
            format_reference(s) for s in sources) + "\n"
    else:
        result = "**The research could not be completed: no sources were retrieved.**"
        consulted = ""
    md = f"""# Technical Research Report — Insufficient Evidence

**Topic:** {topic}
**Generated:** {datetime.now():%Y-%m-%d %H:%M} · **Local model:** `{model_name}`

## Result
{result} No findings, comparisons, benchmarks or recommendations are reported, because none
could be supported by evidence.

## Retrieval issues
{_bullets(errors)}
{consulted}
## What to try
- Check your internet connection.
- Wait a minute if a rate limit was reported, then retry.
- Rephrase the topic with more specific technical keywords.
"""
    return ReportOutput(markdown=md, narrative_generated=False, insufficient_evidence=True,
                        citation_check={"cited": [], "unknown": [], "uncited": [s.source_id for s in sources]})


def run(
    topic: str,
    research: ResearchOutput,
    comparison: ComparisonOutput,
    evaluation: EvaluationOutput,
    sources: list[Source],
    depth: str = "basic",
    llm: OllamaClient | None = None,
    progress=None,
) -> ReportOutput:
    llm = llm or OllamaClient()
    progress = progress or (lambda *args, **kwargs: None)
    valid = {s.source_id for s in sources}

    narrative: ReportNarrative | None = None
    progress("Writing the narrative", step="narrative")
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
                memory="\n".join(
                    f"- {m.model_name} ({m.parameters}): ~{m.int4_gb} GB at 4-bit, ~{m.fp16_gb} GB at FP16 [{m.source_id}]"
                    for m in evaluation.memory_estimates
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

    removed_claims: list[str] = []
    if narrative:
        narrative, removed_claims = verify_narrative(narrative, research, comparison, evaluation, sources)
    progress(f"Attribution check removed {len(removed_claims)} sentence(s)", step="attribution",
             generated=narrative is not None, removed=removed_claims)

    body = assemble(topic, narrative, research, comparison, evaluation, sources, llm.model, depth,
                    removed_claims=len(removed_claims))
    body, removed = strip_invalid_citations(body, valid)
    markdown = body + "\n## 10. References\n" + references_section(body, sources) + "\n"
    check = check_consistency(markdown, sources)
    progress("Report assembled and citations audited", step="assemble", sections=10,
             cited=check["cited"], unknown=check["unknown"], removed_citations=sorted(set(removed)))

    return ReportOutput(
        markdown=markdown,
        narrative_generated=narrative is not None,
        removed_citations=sorted(set(removed)),
        removed_claims=removed_claims,
        citation_check=check,
    )


def verify_narrative(
    n: ReportNarrative, research: ResearchOutput, comparison: ComparisonOutput,
    evaluation: EvaluationOutput, sources: list[Source],
) -> tuple[ReportNarrative, list[str]]:
    """Run the attribution check over every LLM-written field."""
    by_id = {s.source_id: s for s in sources}
    models = dedupe_keep_order([m.model_name for m in comparison.models] + research.models_identified
                               + [m.model_name for m in evaluation.memory_estimates])
    removed: list[str] = []

    def text(value: str) -> str:
        clean, dropped = check_attribution(value, models, by_id)
        removed.extend(dropped)
        return clean

    def items(values: list[str]) -> list[str]:
        return [t for t in (text(v) for v in values) if t.strip()]

    return ReportNarrative(
        executive_summary=text(n.executive_summary),
        comparative_analysis=text(n.comparative_analysis),
        benchmark_discussion=text(n.benchmark_discussion),
        deployment_considerations=items(n.deployment_considerations),
        limitations_and_risks=items(n.limitations_and_risks),
        recommendations=items(n.recommendations),
    ), removed
