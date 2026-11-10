"""DuckDuckGo web search (via the `ddgs` package, no API key)."""

from __future__ import annotations

import html
import time

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from schemas.research import Source
from services import cache
from services.errors import RetrievalError

# Domains that usually host official docs / model cards -> tagged "documentation"
DOC_DOMAINS = (
    "huggingface.co",
    "readthedocs.io",
    "docs.",
    "ollama.com",
    "ai.meta.com",
    "ai.google.dev",
    "qwenlm.github.io",
    "mistral.ai",
)


def _source_type(url: str) -> str:
    return "documentation" if any(d in url for d in DOC_DOMAINS) else "web"


# DuckDuckGo first. Free search engines often return nothing to automated clients
# (live testing: at one point only Bing answered, and "auto" did not reach it), so
# we try a short, fixed chain of free backends and record which one produced each
# result. Transparent, never silent, and bounded (no loops).
BACKENDS = ("duckduckgo", "bing", "brave", "auto")
RETRY_PAUSE_S = 1.0


def _ddgs_text(query: str, max_results: int) -> tuple[list[dict], str]:
    last_error: Exception | None = None
    for attempt, backend in enumerate(BACKENDS):
        if attempt:
            time.sleep(RETRY_PAUSE_S)  # be polite between engines
        try:
            raw = DDGS(timeout=15).text(query, max_results=max_results, backend=backend)
            if raw:
                return raw, backend
        except RatelimitException as exc:
            last_error = RetrievalError("Web search rate limit reached. Wait a minute and retry.")
            last_error.__cause__ = exc
        except TimeoutException as exc:
            last_error = RetrievalError("Web search timed out (check internet connection).")
            last_error.__cause__ = exc
        except DDGSException as exc:
            # ddgs raises DDGSException("No results found.") on empty results
            if "no results" not in str(exc).lower():
                last_error = RetrievalError(f"Web search failed: {exc}")
                last_error.__cause__ = exc
    if last_error:
        raise last_error
    return [], ""


def search_web(query: str, max_results: int = 4) -> list[Source]:
    cached = cache.get("web", f"{query}|{max_results}")
    if cached is not None:
        return [Source(**s) for s in cached]

    raw, backend = _ddgs_text(query, max_results)
    sources = []
    for r in raw:
        url, title = r.get("href", ""), html.unescape(r.get("title") or "").strip()
        if not url or not title:
            continue
        try:
            sources.append(
                Source(
                    title=title,
                    url=url,
                    source_type=_source_type(url),
                    snippet=html.unescape(r.get("body", "")),
                    metadata={"search_backend": backend},
                )
            )
        except ValueError:
            continue  # skip results with invalid URLs rather than fail the search
    cache.put("web", f"{query}|{max_results}", [s.model_dump() for s in sources])
    return sources
