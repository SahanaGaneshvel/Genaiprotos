"""AGENT 1 — Research Agent.

Responsibility: turn a topic into real, citable evidence.

Pipeline (code does the tool calls; the LLM does the reading):
  1. PLAN      LLM  -> SearchPlan (web / arXiv / GitHub queries)
  2. RETRIEVE  code -> DuckDuckGo, Hugging Face model cards via web search, arXiv, GitHub
  3. ENRICH    code -> fetch full page text for web/documentation hits
  4. REGISTER  code -> de-duplicate URLs, assign IDs S1..Sn  (the citation registry)
  5. EXTRACT   LLM  -> one FindingExtraction per source, using ONLY that source's text

Why code-driven tool use instead of letting the LLM pick tools? A 4B model is
unreliable at multi-step tool calling; a fixed retrieval plan is predictable,
testable and easy to explain. The LLM still decides *what* to search for.
"""

from __future__ import annotations

import re
from typing import Callable

from schemas.research import (
    FindingExtraction,
    ResearchFinding,
    ResearchOutput,
    SearchPlan,
    Source,
)
from services.arxiv_search import search_arxiv
from services.document_fetcher import fetch_page
from services.errors import RetrievalError
from services.github_search import search_github
from services.ollama_client import OllamaClient, OllamaConnectionError, OllamaError, OllamaModelNotFoundError
from services.web_search import search_web
from utils.helpers import dedupe_keep_order, truncate

SYSTEM_PROMPT = """You are the RESEARCH AGENT in a team of AI research agents.
Your responsibility: find and extract technical evidence about a research topic.
Rules you must follow:
- Use ONLY the information given to you in the prompt. Never use outside memory to add facts.
- Never invent model names, numbers, benchmark scores, licences, dates or URLs.
- If something is not stated in the source text, leave it out or say it is not stated.
- Copy numbers and licence names exactly as written in the source.
- An "open-weight" model (weights downloadable, possibly with usage restrictions) is NOT
  the same as an OSI-approved open-source licence (e.g. Apache-2.0, MIT). Report the licence
  exactly as written; do not upgrade "open weights" to "open source".
- Answer with a JSON object that matches the requested schema. No extra text."""

PLAN_PROMPT = """Research topic from the user:
\"\"\"{topic}\"\"\"

Create a search plan:
- web_queries: {n_web} short web search queries (5-10 words) that find official docs, model cards,
  comparison articles and benchmark pages for this topic.
- arxiv_query: 3-6 keywords for finding relevant academic papers on arXiv.
- github_query: 2-5 keywords for finding relevant open-source GitHub repositories.
- focus_points: the aspects the user wants compared or evaluated (e.g. licensing, hardware).
Return JSON only."""

EXTRACT_PROMPT = """Research topic: {topic}

SOURCE [{source_id}] ({source_type})
Title: {title}
URL: {url}
{metadata}
--- SOURCE TEXT START ---
{text}
--- SOURCE TEXT END ---

Extract evidence from THIS SOURCE ONLY:
- relevant: false if the source has nothing useful for the topic.
- summary: 1-3 sentences on what the source says that matters for the topic.
- key_findings: up to 6 specific facts (capabilities, modalities, parameter sizes, context window,
  hardware/VRAM needs, quantisation, licence, benchmark results WITH their numbers as written).
- limitations: up to 4 limitations or caveats the source mentions (or obvious gaps, e.g. "no benchmarks reported").
- models_mentioned: names of AI models/tools discussed in the source text.
Return JSON only."""

# How much work each depth level does (kept small: CPU inference is slow)
DEPTH = {
    "basic": {"per_category": 2, "web_queries": 1, "fetch_pages": 3, "chars": 1500},
    "detailed": {"per_category": 4, "web_queries": 2, "fetch_pages": 5, "chars": 2500},
}

Progress = Callable[[str], None]

_STOPWORDS = set(
    "research the latest compare their and of for to a an in on with suitable models model "
    "capabilities benchmarks hardware requirements licensing limitations deployment".split()
)


def fallback_plan(topic: str, n_web: int) -> SearchPlan:
    """Keyword plan used if the LLM cannot produce a valid plan (keeps the run alive)."""
    words = [w for w in re.findall(r"[A-Za-z0-9\-]+", topic) if w.lower() not in _STOPWORDS]
    core = " ".join(words[:6]) or topic[:60]
    return SearchPlan(
        web_queries=[topic[:100], f"{core} comparison benchmark"][:n_web],
        arxiv_query=" ".join(words[:4]) or core,
        github_query=" ".join(words[:3]) or core,
        focus_points=[],
    )


def _normalise_url(url: str) -> str:
    url = url.split("#")[0].rstrip("/").lower()
    return re.sub(r"^https?://(www\.)?", "", re.sub(r"v\d+$", "", url))  # arXiv v1/v2 -> same paper


def register_sources(sources: list[Source]) -> list[Source]:
    """De-duplicate by URL and assign stable citation IDs S1..Sn."""
    unique, seen = [], set()
    for src in sources:
        key = _normalise_url(src.url)
        if key not in seen:
            seen.add(key)
            unique.append(src)
    for i, src in enumerate(unique, start=1):
        src.source_id = f"S{i}"
    return unique


def _source_text(src: Source, max_chars: int) -> tuple[str, str]:
    meta = []
    if src.published:
        meta.append(f"Date: {src.published}")
    if src.metadata.get("license_spdx"):
        meta.append(f"Licence (from GitHub API): {src.metadata['license_spdx']}")
    if src.metadata.get("stars") is not None:
        meta.append(f"GitHub stars: {src.metadata['stars']}")
    if src.metadata.get("authors"):
        meta.append(f"Authors: {', '.join(src.metadata['authors'])}")
    return "\n".join(meta), truncate(src.content or src.snippet, max_chars)


def retrieve(plan: SearchPlan, cfg: dict, errors: list[str], progress: Progress) -> list[Source]:
    """Run every retrieval tool independently; one failure never stops the others."""
    n = cfg["per_category"]
    docs_query = f"{plan.github_query} model card site:huggingface.co"
    jobs = [(f"web search: {q}", search_web, q, n) for q in plan.web_queries[: cfg["web_queries"]]]
    jobs += [
        ("model cards (Hugging Face)", search_web, docs_query, n),
        (f"arXiv: {plan.arxiv_query}", search_arxiv, plan.arxiv_query, n),
        (f"GitHub: {plan.github_query}", search_github, plan.github_query, n),
    ]
    collected: list[Source] = []
    for label, tool, query, limit in jobs:
        progress(f"Searching {label}")
        try:
            results = tool(query, limit)
            if label.startswith("model cards"):
                for r in results:
                    if "huggingface.co" in r.url:
                        r.source_type = "documentation"
            collected.extend(results)
            if not results:
                errors.append(f"{label}: no results")
        except RetrievalError as exc:
            errors.append(f"{label}: {exc}")
    return collected


def enrich(sources: list[Source], max_pages: int, progress: Progress) -> None:
    """Fetch full text for web/documentation results (arXiv/GitHub already have text)."""
    fetched = 0
    for src in sources:
        if src.source_type not in ("web", "documentation") or fetched >= max_pages:
            continue
        progress(f"Fetching page {src.url}")
        page = fetch_page(src.url)
        fetched += 1
        if page:
            src.content = page.text
            src.published = src.published or page.published
        # on failure we keep the search snippet as the source text (noted in limitations)


def extract_finding(llm: OllamaClient, topic: str, src: Source, max_chars: int) -> ResearchFinding | None:
    metadata, text = _source_text(src, max_chars)
    base = dict(
        source_id=src.source_id,
        title=src.title,
        source_url=src.url,
        source_type=src.source_type,
        published=src.published,
    )
    prompt = EXTRACT_PROMPT.format(
        topic=topic, source_id=src.source_id, source_type=src.source_type,
        title=src.title, url=src.url, metadata=metadata, text=text or "(no text available)",
    )
    try:
        ex = llm.chat_structured(SYSTEM_PROMPT, prompt, FindingExtraction, max_tokens=600)
    except (OllamaConnectionError, OllamaModelNotFoundError):
        raise  # infrastructure failure: the agent cannot work at all -> let the node fail
    except OllamaError:
        # Bad LLM output for this one source: keep the source, but say honestly what happened.
        return ResearchFinding(
            **base,
            summary=truncate(src.snippet or text, 300) or "No summary available.",
            limitations=["Automatic extraction failed; summary is the original search snippet."],
        )
    if not ex.relevant:
        return None
    limitations = list(ex.limitations)
    if not src.content:
        limitations.append("Only the search snippet was available (full page could not be fetched).")
    return ResearchFinding(
        **base,
        summary=ex.summary,
        key_findings=ex.key_findings,
        limitations=limitations,
        models_mentioned=ex.models_mentioned,
    )


def run(
    topic: str,
    depth: str = "basic",
    llm: OllamaClient | None = None,
    progress: Progress | None = None,
) -> tuple[list[Source], ResearchOutput]:
    """Research Agent entry point. Returns (source registry, structured findings)."""
    llm = llm or OllamaClient()
    progress = progress or (lambda msg: None)
    cfg = DEPTH.get(depth, DEPTH["basic"])
    errors: list[str] = []

    # 1. PLAN
    progress("Planning search queries")
    try:
        plan = llm.chat_structured(
            SYSTEM_PROMPT,
            PLAN_PROMPT.format(topic=topic, n_web=cfg["web_queries"]),
            SearchPlan,
            max_tokens=400,
        )
    except (OllamaConnectionError, OllamaModelNotFoundError):
        raise
    except OllamaError as exc:
        errors.append(f"Search planning by LLM failed ({exc}); used keyword fallback plan.")
        plan = fallback_plan(topic, cfg["web_queries"])

    # 2-4. RETRIEVE, ENRICH, REGISTER
    sources = register_sources(retrieve(plan, cfg, errors, progress))
    enrich(sources, cfg["fetch_pages"], progress)

    # 5. EXTRACT (one bounded LLM call per source)
    findings: list[ResearchFinding] = []
    for i, src in enumerate(sources, start=1):
        progress(f"Reading source {i}/{len(sources)}: {src.title[:60]}")
        finding = extract_finding(llm, topic, src, cfg["chars"])
        if finding:
            findings.append(finding)

    models = dedupe_keep_order([m for f in findings for m in f.models_mentioned])
    return sources, ResearchOutput(
        findings=findings, models_identified=models, search_plan=plan, retrieval_errors=errors
    )
