"""arXiv paper search via the public Atom API (https://info.arxiv.org/help/api).

No extra library: the response is Atom XML, parsed with the standard library.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests

from schemas.research import Source
from services import cache
from services.errors import RetrievalError

ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}
HEADERS = {"User-Agent": "multi-agent-research-assistant/0.1 (educational POC)"}


def build_query(keywords: str) -> str:
    """'multimodal LLM open source' -> 'all:multimodal AND all:LLM AND ...' (max 5 terms)."""
    terms = [t for t in re.split(r"[^\w\-]+", keywords) if len(t) > 1][:5]
    return " AND ".join(f"all:{t}" for t in terms)


def parse_feed(xml_text: str) -> list[Source]:
    root = ET.fromstring(xml_text)
    sources = []
    for entry in root.findall("atom:entry", NS):
        title = " ".join((entry.findtext("atom:title", "", NS)).split())
        url = (entry.findtext("atom:id", "", NS)).strip()
        if not title or not url or "arxiv.org" not in url:
            continue  # arXiv returns an "Error" entry for bad queries
        published = (entry.findtext("atom:published", "", NS) or "")[:10] or None
        updated = (entry.findtext("atom:updated", "", NS) or "")[:10] or None
        authors = [a.findtext("atom:name", "", NS) for a in entry.findall("atom:author", NS)]
        abstract = " ".join((entry.findtext("atom:summary", "", NS)).split())
        sources.append(
            Source(
                title=title,
                url=url.replace("http://", "https://"),
                source_type="arxiv",
                published=published,
                snippet=abstract,
                content=abstract,  # the abstract is the content we use (no PDF parsing)
                metadata={"authors": authors[:6], "updated": updated},
            )
        )
    return sources


def search_arxiv(keywords: str, max_results: int = 4) -> list[Source]:
    query = build_query(keywords)
    if not query:
        return []
    cached = cache.get("arxiv", f"{query}|{max_results}")
    if cached is not None:
        return [Source(**s) for s in cached]

    params = {"search_query": query, "start": 0, "max_results": max_results, "sortBy": "relevance"}
    try:
        resp = requests.get(ARXIV_API, params=params, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        raise RetrievalError(f"arXiv request failed (check internet connection): {exc}") from exc
    if resp.status_code in (429, 503):
        raise RetrievalError("arXiv is rate-limiting requests — retry in a few seconds.")
    if resp.status_code != 200:
        raise RetrievalError(f"arXiv returned HTTP {resp.status_code}.")

    try:
        sources = parse_feed(resp.text)
    except ET.ParseError as exc:
        raise RetrievalError(f"Could not parse arXiv response: {exc}") from exc
    cache.put("arxiv", f"{query}|{max_results}", [s.model_dump() for s in sources])
    return sources
