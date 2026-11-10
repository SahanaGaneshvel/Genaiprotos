"""Schemas for the Comparison Agent."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NOT_DOCUMENTED = "Not documented in retrieved sources"

LicenceCategory = Literal[
    "Open source (OSI-approved licence)",
    "Open weights (custom / restricted licence)",
    "Proprietary / API only",
    "Unknown",
]


class ModelComparison(BaseModel):
    """One row of the comparison table. Every value must come from the cited findings."""

    model_name: str = Field(min_length=1)
    developer: str = NOT_DOCUMENTED
    modalities: list[str] = Field(default_factory=list, description="e.g. text, image, audio, video")
    parameter_sizes: str = NOT_DOCUMENTED
    context_window: str = NOT_DOCUMENTED
    deployment_methods: list[str] = Field(default_factory=list, description="e.g. Ollama, vLLM, llama.cpp")
    hardware_requirements: str = NOT_DOCUMENTED
    licence: str = Field(default=NOT_DOCUMENTED, description="licence name exactly as stated")
    usage_restrictions: str = NOT_DOCUMENTED
    source_ids: list[str] = Field(default_factory=list, description="set by code: findings that mention the model")
    # filled in by code, not by the LLM:
    licence_category: LicenceCategory = "Unknown"


# ------------------------------------------------------------------ LLM steps
class ModelSelection(BaseModel):
    """Step 1: which candidate names are actual AI models worth comparing."""

    models: list[str] = Field(default_factory=list, description="names copied exactly from the candidate list")


PLACEHOLDERS = {"", "none", "null", "n/a", "na", "unknown", "not specified", "not stated", "-", "—"}
# "Not specified in source text", "Not explicitly stated in the text", "Unknown (not given)", ...
NOTHING_KNOWN = re.compile(r"^(not (explicitly |clearly )?(specified|documented|stated|mentioned|provided|available|given)|unknown)")


class ComparisonRowLLM(BaseModel):
    """Step 2 (one call per model): fill the row from that model's evidence only."""

    developer: str = NOT_DOCUMENTED
    modalities: list[str] = Field(default_factory=list)
    parameter_sizes: str = NOT_DOCUMENTED
    context_window: str = NOT_DOCUMENTED
    deployment_methods: list[str] = Field(default_factory=list)
    hardware_requirements: str = NOT_DOCUMENTED
    licence: str = NOT_DOCUMENTED
    usage_restrictions: str = NOT_DOCUMENTED

    @field_validator(
        "developer", "parameter_sizes", "context_window", "hardware_requirements", "licence", "usage_restrictions"
    )
    @classmethod
    def _placeholder_means_not_documented(cls, v: str) -> str:
        # live runs: "" blocked filling 27.78B from API metadata; "Not specified in source text"
        # showed up as cell text. Every "nothing known" phrasing becomes the one standard value.
        text = (v or "").strip()
        low = text.lower().rstrip(".")
        if low in PLACEHOLDERS or NOTHING_KNOWN.match(low):
            return NOT_DOCUMENTED
        return text


class DifferencesLLM(BaseModel):
    """Step 3: explain the most important differences, from the finished table."""

    key_differences: list[str] = Field(default_factory=list, max_length=6)


class ComparisonOutput(BaseModel):
    """What the Comparison Agent puts into the shared state (after code-side checks)."""

    models: list[ModelComparison] = Field(default_factory=list)
    key_differences: list[str] = Field(default_factory=list)
    dropped_models: list[str] = Field(
        default_factory=list, description="Candidates removed: not in the research, or no supporting evidence"
    )
    warnings: list[str] = Field(default_factory=list, description="Steps that failed and were skipped")
