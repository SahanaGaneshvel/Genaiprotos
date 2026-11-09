"""Fetch a public webpage and turn it into clean text with Requests + BeautifulSoup.

Respects robots.txt, only reads HTML/plain text, and never raises on failure —
it returns None so the caller can fall back to the search snippet.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from urllib import robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from services import cache
from utils.helpers import truncate

USER_AGENT = "multi-agent-research-assistant/0.1 (educational POC)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"}
DATE_META = (
    "article:published_time",
    "article:modified_time",
    "og:updated_time",
    "datePublished",
    "dateModified",
    "date",
    "citation_publication_date",
)


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    published: str | None


@lru_cache(maxsize=64)
def _robots(netloc: str, scheme: str) -> robotparser.RobotFileParser | None:
    rp = robotparser.RobotFileParser()
    try:
        resp = requests.get(f"{scheme}://{netloc}/robots.txt", headers=HEADERS, timeout=8)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None  # no robots.txt -> allowed
    rp.parse(resp.text.splitlines())
    return rp


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    rp = _robots(parsed.netloc, parsed.scheme)
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def extract_text(html: str, max_chars: int = 6000) -> tuple[str, str, str | None]:
    """HTML -> (title, main text, date). Drops scripts, nav, footers, etc."""
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""

    published = None
    for name in DATE_META:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            published = tag["content"][:10]
            break
    if not published and (t := soup.find("time", attrs={"datetime": True})):
        published = t["datetime"][:10]

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"]):
        tag.decompose()
    body = soup.find("main") or soup.find("article") or soup.body or soup
    text = truncate(body.get_text(" ", strip=True), max_chars)
    return title, text, published


def fetch_page(url: str, max_chars: int = 6000) -> FetchedPage | None:
    cached = cache.get("page", url)
    if cached is not None:
        return FetchedPage(**cached) if cached else None

    if not allowed_by_robots(url):
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException:
        return None
    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or not any(t in content_type for t in ("text/html", "text/plain")):
        return None

    if "text/plain" in content_type:
        page = FetchedPage(url=url, title="", text=truncate(resp.text, max_chars), published=None)
    else:
        title, text, published = extract_text(resp.text, max_chars)
        page = FetchedPage(url=url, title=title, text=text, published=published)
    if len(page.text) < 200:  # JS-only pages / cookie walls give almost nothing useful
        return None
    cache.put("page", url, page.__dict__)
    return page
