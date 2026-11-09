"""AGENT 2 — Comparison Agent.

Responsibility: turn the Research Agent's findings into a model-by-model comparison
(modalities, size, context window, deployment, hardware, licence).

Input:  ResearchOutput.findings  (NOT raw web pages — it works on the research team's evidence)
LLM:    one structured call -> ComparisonLLMOutput
Code:   * removes citations to unknown sources and rows with no valid source
        * classifies each licence as OSI open-source vs open-weight (deterministic, see below)
"""

from __future__ import annotations

import re

from schemas.comparison import NOT_DOCUMENTED, ComparisonLLMOutput, ComparisonOutput, ModelComparison
from schemas.research import ResearchOutput
from services.ollama_client import OllamaClient
from utils.citations import keep_valid_ids, strip_invalid_citations

SYSTEM_PROMPT = """You are the COMPARISON AGENT in a team of AI research agents.
Your responsibility: compare the AI models/technologies found by the Research Agent.
You receive research findings, each labelled with a source ID like [S1].
Rules you must follow:
- Use ONLY facts present in the findings. Do not use outside knowledge.
- If a value (parameters, context window, hardware, licence...) is not in the findings, write exactly:
  "Not documented in retrieved sources".
- Every model row must list the source_ids (e.g. ["S1","S4"]) that support it.
- Report licence names exactly as written. "Open weights" is not the same as "open source".
- key_differences: 3-6 sentences that explain the most important differences between the models,
  each ending with the citation(s) that support it, e.g. "Model A supports audio while Model B does not [S2][S5]."
- Never invent model names, numbers, licences or source IDs.
- Answer with a JSON object that matches the requested schema. No extra text."""

USER_PROMPT = """Research topic: {topic}

Models/technologies mentioned by the Research Agent: {models}

RESEARCH FINDINGS:
{findings}

Build a comparison of at most {max_models} of the most relevant AI models above
(prefer specific models over generic tools). Return JSON only."""

# SPDX ids / names of OSI-approved licences commonly used for model weights.
OSI_LICENCES = re.compile(
    r"\b(apache[- ]?2(\.0)?|mit|bsd[- ]?[23]|gpl|lgpl|agpl|mpl[- ]?2|isc|unlicense|cc0)\b", re.I
)
# Signals of a custom/restricted licence. A model *family name* alone ("Qwen2.5") is not a
# licence, so family names only count when followed by licence/terms ("Qwen License").
RESTRICTED_HINTS = re.compile(
    r"(community licen|research[- ]only|non[- ]?commercial|openrail|\brail\b|cc[- ]by[- ]nc|custom|"
    r"acceptable use|restricted|(llama|gemma|qwen|deepseek|tongyi)[\w\s.\-]*(licen[cs]e|terms))",
    re.I,
)
PROPRIETARY_HINTS = re.compile(r"(proprietary|closed|api[- ]only|commercial licence only)", re.I)


def classify_licence(licence: str) -> str:
    """Deterministic licence classification — the LLM reports the licence text,
    code decides the category, so 'open source' is never claimed loosely."""
    text = (licence or "").strip()
    if not text or text == NOT_DOCUMENTED or text.lower() in ("unknown", "noassertion", "other"):
        return "Unknown"
    if RESTRICTED_HINTS.search(text):  # restrictions win: be conservative
        return "Open weights (custom / restricted licence)"
    if OSI_LICENCES.search(text):
        return "Open source (OSI-approved licence)"
    if PROPRIETARY_HINTS.search(text):
        return "Proprietary / API only"
    return "Unknown"


def format_findings(research: ResearchOutput) -> str:
    blocks = []
    for f in research.findings:
        facts = "; ".join(f.key_findings) or "(no specific facts extracted)"
        lims = "; ".join(f.limitations) or "none stated"
        blocks.append(
            f"[{f.source_id}] {f.title} ({f.source_type}, {f.published or 'no date'})\n"
            f"  Summary: {f.summary}\n  Facts: {facts}\n  Limitations: {lims}"
        )
    return "\n".join(blocks)


def run(
    topic: str,
    research: ResearchOutput,
    valid_ids: set[str],
    llm: OllamaClient | None = None,
    max_models: int = 5,
) -> ComparisonOutput:
    llm = llm or OllamaClient()
    if not research.findings:
        return ComparisonOutput()

    raw = llm.chat_structured(
        SYSTEM_PROMPT,
        USER_PROMPT.format(
            topic=topic,
            models=", ".join(research.models_identified) or "(none identified)",
            findings=format_findings(research),
            max_models=max_models,
        ),
        ComparisonLLMOutput,
        max_tokens=2000,
    )

    rows: list[ModelComparison] = []
    dropped: list[str] = []
    for row in raw.models[:max_models]:
        row.source_ids = keep_valid_ids(row.source_ids, valid_ids)
        if not row.source_ids:  # unverifiable row -> do not present it as evidence
            dropped.append(row.model_name)
            continue
        row.licence_category = classify_licence(row.licence)
        rows.append(row)

    differences = []
    for sentence in raw.key_differences:
        clean, _ = strip_invalid_citations(sentence, valid_ids)
        if clean.strip():
            differences.append(clean.strip())

    return ComparisonOutput(models=rows, key_differences=differences, dropped_models=dropped)
