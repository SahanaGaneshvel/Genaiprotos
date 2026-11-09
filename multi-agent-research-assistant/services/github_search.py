"""GitHub repository search via the public REST API.

Unauthenticated by default (10 search requests/min). If GITHUB_TOKEN is set it is
sent as a Bearer token — it is never logged or shown in the UI.
"""

from __future__ import annotations

import requests

from config import get_settings
from schemas.research import Source
from services import cache
from services.errors import RetrievalError
from utils.helpers import truncate

API = "https://api.github.com"


def _headers(raw: bool = False) -> dict:
    headers = {
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "User-Agent": "multi-agent-research-assistant",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = get_settings().github_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_rate_limit(resp: requests.Response) -> None:
    if resp.status_code in (403, 429) and (
        resp.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in resp.text.lower()
    ):
        raise RetrievalError(
            "GitHub API rate limit reached. Wait a minute or set GITHUB_TOKEN in .env."
        )


def fetch_readme(full_name: str, max_chars: int = 12000) -> str:
    """Best-effort README download. Returns '' on any failure."""
    try:
        resp = requests.get(f"{API}/repos/{full_name}/readme", headers=_headers(raw=True), timeout=15)
        return truncate(resp.text, max_chars) if resp.status_code == 200 else ""
    except requests.RequestException:
        return ""


def search_github(keywords: str, max_results: int = 4, with_readme: bool = True) -> list[Source]:
    key = f"{keywords}|{max_results}|{with_readme}"
    cached = cache.get("github", key)
    if cached is not None:
        return [Source(**s) for s in cached]

    params = {"q": keywords, "sort": "stars", "order": "desc", "per_page": max_results}
    try:
        resp = requests.get(f"{API}/search/repositories", params=params, headers=_headers(), timeout=20)
    except requests.RequestException as exc:
        raise RetrievalError(f"GitHub request failed (check internet connection): {exc}") from exc
    _raise_for_rate_limit(resp)
    if resp.status_code != 200:
        raise RetrievalError(f"GitHub search returned HTTP {resp.status_code}.")

    sources = []
    for repo in resp.json().get("items", [])[:max_results]:
        licence = (repo.get("license") or {}).get("spdx_id")
        description = repo.get("description") or ""
        sources.append(
            Source(
                title=repo["full_name"],
                url=repo["html_url"],
                source_type="github",
                published=(repo.get("pushed_at") or "")[:10] or None,  # last push = "updated"
                snippet=description,
                content=fetch_readme(repo["full_name"]) if with_readme else description,
                metadata={
                    "stars": repo.get("stargazers_count"),
                    "license_spdx": licence,
                    "topics": repo.get("topics", [])[:8],
                    "date_kind": "last updated",
                },
            )
        )
    cache.put("github", key, [s.model_dump() for s in sources])
    return sources
