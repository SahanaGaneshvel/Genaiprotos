"""AGENT 2 — Comparison Agent.

Responsibility: turn the Research Agent's findings into a model-by-model comparison
(modalities, size, context window, deployment, hardware, licence).

Input:  ResearchOutput.findings  (NOT raw web pages — it works on the research team's evidence)

Small focused steps instead of one big prompt (a single prompt produced an empty
table with a 2B model during live testing):
  1. SELECT    code -> models with their own model card / repo are always included;
               LLM  -> picks the remaining slots (code rejects names not in the research)
  2. EVIDENCE  code -> the finding lines about each model + its supporting source IDs
  3. ROW       LLM  -> one small call per model: fill the row from that evidence only
  4. ENRICH    code -> fill undocumented licence / parameter cells from API metadata;
                       classify licence: OSI open source vs open weights (deterministic)
  5. DIFFER    LLM  -> key differences written from the finished table; code attaches the
                       citations of the models each sentence names, and de-duplicates
"""

from __future__ import annotations

import re

from schemas.comparison import (
    NOT_DOCUMENTED,
    ComparisonOutput,
    ComparisonRowLLM,
    DifferencesLLM,
    ModelComparison,
    ModelSelection,
)
from schemas.research import ResearchOutput, Source
from services.ollama_client import OllamaClient, OllamaConnectionError, OllamaError, OllamaModelNotFoundError
from utils.citations import strip_invalid_citations
from utils.evidence import has_own_source, mentions, model_evidence, rank_models

SYSTEM_PROMPT = """You are the COMPARISON AGENT in a team of AI research agents.
Your responsibility: compare the AI models found by the Research Agent.
Rules you must follow:
- Use ONLY the evidence given in the prompt. Do not use outside knowledge.
- If a value is not stated in the evidence, write exactly: "Not documented in retrieved sources".
- Copy numbers and licence names exactly as written. "Open weights" is not the same as "open source".
- Never invent model names, numbers, licences or source IDs.
- Answer with a JSON object that matches the requested schema. No extra text."""

SELECT_PROMPT = """Research topic: {topic}

Candidate names found in the research (most evidence first):
{candidates}

Which of these are specific AI models (not serving tools/frameworks like vLLM, not companies,
not methods)? Pick at most {max_models}, most relevant to the topic first.
Copy names EXACTLY from the list. Return JSON only."""

ROW_PROMPT = """Research topic: {topic}

MODEL: {model}

EVIDENCE about this model (each line starts with its source ID):
{evidence}

Fill the comparison row for {model} using ONLY this evidence:
developer, modalities (e.g. text, image, audio, video), parameter_sizes, context_window,
deployment_methods (e.g. Ollama, vLLM, llama.cpp, transformers), hardware_requirements,
licence (exactly as written), usage_restrictions. Return JSON only."""

DIFF_PROMPT = """Research topic: {topic}

COMPARISON TABLE (built from cited evidence):
{table}

Write 3-5 sentences explaining the most important differences between these models for the topic
(size, modalities, licence, hardware). Each sentence must be different and must end with the
source IDs from the table that support it, e.g. "... [S2][S4]". Return JSON only."""

# SPDX ids / names of OSI-approved licences commonly used for model weights.
OSI_LICENCES = re.compile(
    r"\b(apache[- ]?2(\.0)?|mit|bsd[- ]?[23]|gpl|lgpl|agpl|mpl[- ]?2|isc|unlicense|cc0)\b", re.I
)
# Signals of a custom/restricted licence. A model *family name* alone ("Qwen2.5") is not a
# licence, so family names only count when followed by licence/terms ("Qwen License").
RESTRICTED_HINTS = re.compile(
    r"(community licen|research[- ]only|non[- ]?commercial|openrail|\brail\b|cc[- ]by[- ]nc|custom|"
    r"acceptable use|restricted|modified|(llama|gemma|qwen|deepseek|tongyi|kimi)[\w\s.\-]*(licen[cs]e|terms))",
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
    """Flat list of findings (used by the Evaluation Agent's prompt)."""
    blocks = []
    for f in research.findings:
        facts = "; ".join(f.key_findings) or "(no specific facts extracted)"
        lims = "; ".join(f.limitations) or "none stated"
        blocks.append(
            f"[{f.source_id}] {f.title} ({f.source_type}, {f.published or 'no date'})\n"
            f"  Summary: {f.summary}\n  Facts: {facts}\n  Limitations: {lims}"
        )
    return "\n".join(blocks)


def enrich_from_metadata(row: ModelComparison, by_id: dict[str, Source]) -> None:
    """Fill gaps with facts the retrieval APIs returned for the row's own sources.
    A live run lost 'Parameters: 752M / Licence: apache-2.0' between research and comparison;
    API metadata is more trustworthy than LLM copying, and the origin is labelled."""
    for sid in row.source_ids:
        meta = by_id[sid].metadata
        if meta.get("model_id") and not mentions(meta["model_id"], row.model_name):
            continue  # a model card only describes its own model ("Kimi-K3.1-Pro" card ≠ "Kimi K3")
        licence = meta.get("license_hf") or meta.get("license_spdx")
        if row.licence == NOT_DOCUMENTED and licence and licence not in ("NOASSERTION", "other"):
            api = "Hugging Face" if meta.get("license_hf") else "GitHub"
            row.licence = f"{licence} ({api} metadata [{sid}])"
        if row.parameter_sizes == NOT_DOCUMENTED and meta.get("parameters_hf"):
            row.parameter_sizes = f"{meta['parameters_hf']} (Hugging Face weight files [{sid}])"


def select_models(
    llm, topic: str, candidates: list[str], max_models: int, guaranteed: list[str] | None = None
) -> list[str]:
    """Models with their own model card / repo are always compared (most reliable evidence);
    the LLM picks the remaining slots, and code keeps only names that are in the candidate list.
    Live run: the LLM picked architecture components ("SiTU-GLU") over the Kimi K3.1-Pro card."""
    if not candidates:
        return []
    chosen = list(dict.fromkeys(guaranteed or []))[:max_models]
    if len(chosen) >= max_models:
        return chosen
    allowed = {c.lower(): c for c in candidates}
    try:
        picked = llm.chat_structured(
            SYSTEM_PROMPT,
            SELECT_PROMPT.format(topic=topic, candidates="\n".join(f"- {c}" for c in candidates[:20]),
                                 max_models=max_models),
            ModelSelection, max_tokens=300,
        ).models
    except (OllamaConnectionError, OllamaModelNotFoundError):
        raise
    except OllamaError:
        picked = []
    for name in picked:
        real = allowed.get(name.strip().lower())
        if real and real not in chosen:
            chosen.append(real)
    if not chosen:  # fallback: most-evidenced names
        chosen = candidates[:max_models]
    return chosen[:max_models]


def _row_table(rows: list[ModelComparison]) -> str:
    return "\n".join(
        f"- {r.model_name}: modalities={', '.join(r.modalities) or 'n/d'}; parameters={r.parameter_sizes}; "
        f"context={r.context_window}; hardware={r.hardware_requirements}; licence={r.licence}; "
        f"sources={''.join(f'[{s}]' for s in r.source_ids)}"
        for r in rows
    )


NOT_A_LICENCE = re.compile(r"[$€£]|\bper\b|\btokens?\b|/\s?1?M\b|pricing|price", re.I)


def sanitize_licence(value: str) -> str:
    """A live run put a price ("$0.07/1M tokens") in the licence field. Reject non-licences."""
    return NOT_DOCUMENTED if NOT_A_LICENCE.search(value or "") else value


def attach_citations(sentence: str, rows: list[ModelComparison]) -> str:
    """Citations for a difference sentence are always decided by code: the sources of the
    table rows whose models the sentence names. Live runs showed the model both omitting
    citations and citing the wrong ones (Kimi described, Qwen's sources cited).
    A sentence that names no model in the table is unsupported -> ''."""
    ids: list[str] = []
    for row in rows:
        if mentions(row.model_name, sentence):
            ids += [s for s in row.source_ids if s not in ids]
    if not ids:
        return ""
    text = re.sub(r"\s*\[S\d+\]", "", sentence).rstrip(" .")
    return text + " " + "".join(f"[{i}]" for i in ids) + "."


def _dedupe_sentences(sentences: list[str]) -> list[str]:
    seen, out = set(), []
    for s in sentences:
        key = re.sub(r"\W+", " ", s.lower())[:80]
        if s.strip() and key not in seen:
            seen.add(key)
            out.append(s.strip())
    return out


def run(
    topic: str,
    research: ResearchOutput,
    sources: list[Source],
    llm: OllamaClient | None = None,
    max_models: int = 5,
    progress=None,
) -> ComparisonOutput:
    llm = llm or OllamaClient()
    progress = progress or (lambda *args, **kwargs: None)
    if not research.findings:
        return ComparisonOutput()
    by_id = {s.source_id: s for s in sources}
    valid_ids = set(by_id)

    # 1. SELECT
    candidates = rank_models(research)
    with_cards = [c for c in candidates if has_own_source(c, research)]
    progress(f"{len(candidates)} candidate names ranked by evidence", step="candidates",
             candidates=candidates[:12], with_cards=with_cards)
    chosen = select_models(llm, topic, candidates, max_models, guaranteed=with_cards)
    progress(f"Selected {len(chosen)} models", step="selected", models=chosen, guaranteed=with_cards)

    # 2-4. EVIDENCE -> ROW -> ENRICH
    rows: list[ModelComparison] = []
    dropped: list[str] = []
    for name in chosen:
        evidence, ids = model_evidence(name, research, by_id)
        if not ids:
            dropped.append(name)
            progress(f"{name}: no supporting evidence — dropped", step="row_dropped", model=name)
            continue
        progress(f"Filling the row for {name}", step="row", model=name, evidence_lines=len(evidence), source_ids=ids)
        fields = llm.chat_structured(
            SYSTEM_PROMPT,
            ROW_PROMPT.format(topic=topic, model=name, evidence="\n".join(evidence[:25])),
            ComparisonRowLLM, max_tokens=500,
        )
        row = ModelComparison(model_name=name, source_ids=ids, **fields.model_dump())
        row.licence = sanitize_licence(row.licence)
        enrich_from_metadata(row, by_id)
        row.licence_category = classify_licence(row.licence)
        rows.append(row)
        progress(
            f"Row ready: {name}", step="row_done", model=name, parameters=row.parameter_sizes,
            context=row.context_window, modalities=row.modalities, licence=row.licence,
            licence_category=row.licence_category, source_ids=ids,
        )

    # 5. DIFFERENCES (only meaningful with 2+ rows)
    differences: list[str] = []
    warnings: list[str] = []
    if len(rows) >= 2:
        progress("Explaining the differences", step="differences")
        try:
            raw = llm.chat_structured(
                SYSTEM_PROMPT, DIFF_PROMPT.format(topic=topic, table=_row_table(rows)),
                DifferencesLLM, max_tokens=600,
            )
            cleaned = [strip_invalid_citations(s, valid_ids)[0] for s in raw.key_differences]
            cited = [attach_citations(s, rows) for s in cleaned]
            differences = [s for s in cited if s]  # sentences about no known model are dropped
            if raw.key_differences and not differences:
                warnings.append("No key-difference sentence could be tied to a cited model; all were dropped.")
        except (OllamaConnectionError, OllamaModelNotFoundError):
            raise
        except OllamaError as exc:
            warnings.append(f"Key-differences step failed and was skipped: {str(exc)[:150]}")
        progress(f"{len(differences)} cited differences", step="differences_done",
                 sentences=_dedupe_sentences(differences))

    return ComparisonOutput(models=rows, key_differences=_dedupe_sentences(differences),
                            dropped_models=dropped, warnings=warnings)
