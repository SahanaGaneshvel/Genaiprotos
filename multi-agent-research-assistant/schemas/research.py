"""Schemas for retrieved sources and the Research Agent's findings.

Two layers on purpose:
  * Source           — produced by CODE (retrieval tools). Ground truth: real URL, real title.
  * ResearchFinding  — produced by the LLM *about* one Source. It can only reference
                       a source_id that exists; it can never invent a URL.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["web", "documentation", "arxiv", "github"]


def validate_http_url(url: str) -> str:
    """Accept only absolute http(s) URLs with a host. Shared by several schemas."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in url:
        raise ValueError(f"Invalid source URL: {url!r}")
    return url


class Source(BaseModel):
    """One retrieved document. Created only by retrieval tools, never by the LLM."""

    source_id: str = ""  # assigned after de-duplication: S1, S2, ...
    title: str = Field(min_length=1)
    url: str
    source_type: SourceType
    published: str | None = None  # ISO date (YYYY-MM-DD) when the source exposes one
    snippet: str = ""  # search snippet / abstract / repo description
    content: str = ""  # fetched page / README text (truncated)
    metadata: dict = Field(default_factory=dict)  # e.g. stars, licence, authors

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return validate_http_url(v)


# ----------------------------------------------------------------- LLM outputs
class SearchPlan(BaseModel):
    """Research Agent step 1: the LLM turns the user topic into search queries."""

    web_queries: list[str] = Field(min_length=1, max_length=3)
    arxiv_query: str = Field(min_length=2, description="3-6 keywords for arXiv")
    github_query: str = Field(min_length=2, description="2-5 keywords for GitHub repos")
    focus_points: list[str] = Field(
        default_factory=list, description="What the user wants compared/evaluated"
    )


class FindingExtraction(BaseModel):
    """Research Agent step 2: what the LLM extracts from ONE source text."""

    relevant: bool = Field(description="False if the source is off-topic")
    summary: str
    key_findings: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=5)
    models_mentioned: list[str] = Field(default_factory=list, max_length=10)


class ResearchFinding(BaseModel):
    """Final Research Agent record = Source metadata (from code) + extraction (from LLM)."""

    source_id: str = Field(pattern=r"^S\d+$")
    title: str
    summary: str
    source_url: str
    source_type: SourceType
    published: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    models_mentioned: list[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        return validate_http_url(v)


class ResearchOutput(BaseModel):
    findings: list[ResearchFinding] = Field(default_factory=list)
    models_identified: list[str] = Field(default_factory=list)
    search_plan: SearchPlan | None = None
    retrieval_errors: list[str] = Field(default_factory=list)
