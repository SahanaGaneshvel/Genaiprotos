"""Retrieval tool tests — every network call is mocked (no internet needed)."""

from unittest.mock import MagicMock

import pytest
import requests

from services import arxiv_search, document_fetcher, github_search, web_search
from services.errors import RetrievalError

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <published>2025-01-02T00:00:00Z</published>
    <updated>2025-02-03T00:00:00Z</updated>
    <title>A Small   Open Multimodal
      Model</title>
    <summary>We present a vision-language model.</summary>
    <author><name>A. Author</name></author>
  </entry>
</feed>"""


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    """Tests must not read/write the real on-disk cache."""
    for mod in (web_search, arxiv_search, github_search, document_fetcher):
        monkeypatch.setattr(mod.cache, "get", lambda *a, **k: None)
        monkeypatch.setattr(mod.cache, "put", lambda *a, **k: None)


def _resp(status=200, text="", json_body=None, headers=None):
    r = MagicMock()
    r.status_code, r.text, r.headers = status, text, headers or {}
    r.json.return_value = json_body or {}
    return r


# ---------------------------------------------------------------- arXiv
def test_arxiv_query_builder():
    assert arxiv_search.build_query("open-source multimodal LLM!") == (
        "all:open-source AND all:multimodal AND all:LLM"
    )


def test_arxiv_parses_atom_feed(monkeypatch):
    monkeypatch.setattr(arxiv_search.requests, "get", lambda *a, **k: _resp(text=ARXIV_XML))
    [src] = arxiv_search.search_arxiv("multimodal model")
    assert src.title == "A Small Open Multimodal Model"
    assert src.url == "https://arxiv.org/abs/2501.00001v1"
    assert src.published == "2025-01-02" and src.source_type == "arxiv"


def test_arxiv_rate_limit_raises_retrieval_error(monkeypatch):
    monkeypatch.setattr(arxiv_search.requests, "get", lambda *a, **k: _resp(status=429))
    with pytest.raises(RetrievalError, match="rate"):
        arxiv_search.search_arxiv("multimodal")


def test_arxiv_offline_raises_retrieval_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(arxiv_search.requests, "get", boom)
    with pytest.raises(RetrievalError, match="internet"):
        arxiv_search.search_arxiv("multimodal")


# ---------------------------------------------------------------- GitHub
def test_github_maps_repo_fields(monkeypatch):
    body = {
        "items": [
            {
                "full_name": "org/vlm",
                "html_url": "https://github.com/org/vlm",
                "description": "A VLM",
                "stargazers_count": 1200,
                "pushed_at": "2025-03-01T10:00:00Z",
                "license": {"spdx_id": "Apache-2.0"},
                "topics": ["multimodal"],
            }
        ]
    }
    monkeypatch.setattr(github_search.requests, "get", lambda *a, **k: _resp(json_body=body))
    [src] = github_search.search_github("vlm", with_readme=False)
    assert src.url == "https://github.com/org/vlm"
    assert src.metadata["license_spdx"] == "Apache-2.0" and src.published == "2025-03-01"


def test_github_rate_limit_message(monkeypatch):
    monkeypatch.setattr(
        github_search.requests,
        "get",
        lambda *a, **k: _resp(status=403, text="API rate limit exceeded", headers={"X-RateLimit-Remaining": "0"}),
    )
    with pytest.raises(RetrievalError, match="GITHUB_TOKEN"):
        github_search.search_github("vlm")


def test_github_token_sent_when_configured(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    assert github_search._headers()["Authorization"] == "Bearer secret-token"
    monkeypatch.setenv("GITHUB_TOKEN", "")
    assert "Authorization" not in github_search._headers()


# ---------------------------------------------------------------- DuckDuckGo
def test_web_search_skips_invalid_urls_and_tags_docs(monkeypatch):
    fake = MagicMock()
    fake.return_value.text.return_value = [
        {"title": "Model card", "href": "https://huggingface.co/org/model", "body": "card"},
        {"title": "Broken", "href": "javascript:void(0)", "body": "x"},
        {"title": "Blog", "href": "https://example.com/post", "body": "post"},
    ]
    monkeypatch.setattr(web_search, "DDGS", fake)
    results = web_search.search_web("vlm")
    assert [s.source_type for s in results] == ["documentation", "web"]


def test_web_search_rate_limit(monkeypatch):
    fake = MagicMock()
    fake.return_value.text.side_effect = web_search.RatelimitException("202 Ratelimit")
    monkeypatch.setattr(web_search, "DDGS", fake)
    with pytest.raises(RetrievalError, match="rate limit"):
        web_search.search_web("vlm")


def test_web_search_falls_back_to_auto_backend(monkeypatch):
    def text(query, max_results, backend):
        if backend == "duckduckgo":
            raise web_search.DDGSException("No results found.")
        return [{"title": "Blog", "href": "https://example.com/post", "body": "post"}]

    fake = MagicMock()
    fake.return_value.text.side_effect = text
    monkeypatch.setattr(web_search, "DDGS", fake)
    [src] = web_search.search_web("vlm")
    assert src.metadata["search_backend"] == "auto"


def test_web_search_empty_results(monkeypatch):
    fake = MagicMock()
    fake.return_value.text.side_effect = web_search.DDGSException("No results found.")
    monkeypatch.setattr(web_search, "DDGS", fake)
    assert web_search.search_web("zzzz") == []


# ---------------------------------------------------------------- page fetcher
def test_extract_text_strips_boilerplate_and_finds_date():
    html = """<html><head><title>Docs</title>
      <meta property="article:published_time" content="2025-04-05T00:00:00Z"></head>
      <body><nav>menu</nav><script>evil()</script><main>Real content here.</main></body></html>"""
    title, text, date = document_fetcher.extract_text(html)
    assert title == "Docs" and text == "Real content here." and date == "2025-04-05"


def test_fetch_page_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(document_fetcher, "allowed_by_robots", lambda url: True)

    def boom(*a, **k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(document_fetcher.requests, "get", boom)
    assert document_fetcher.fetch_page("https://example.com") is None


def test_fetch_page_respects_robots(monkeypatch):
    monkeypatch.setattr(document_fetcher, "allowed_by_robots", lambda url: False)
    get = MagicMock()
    monkeypatch.setattr(document_fetcher.requests, "get", get)
    assert document_fetcher.fetch_page("https://example.com/private") is None
    get.assert_not_called()
