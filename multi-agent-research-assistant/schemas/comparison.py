"""Schemas for the Comparison Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    source_ids: list[str] = Field(default_factory=list, description="IDs like S1 that support this row")
    # filled in by code, not by the LLM:
    licence_category: LicenceCategory = "Unknown"


class ComparisonLLMOutput(BaseModel):
    """What we ask the LLM for."""

    models: list[ModelComparison] = Field(default_factory=list)
    key_differences: list[str] = Field(
        default_factory=list, description="Sentences explaining differences, each citing [S#]"
    )


class ComparisonOutput(BaseModel):
    """What the Comparison Agent puts into the shared state (after code-side checks)."""

    models: list[ModelComparison] = Field(default_factory=list)
    key_differences: list[str] = Field(default_factory=list)
    dropped_models: list[str] = Field(
        default_factory=list, description="Rows removed because no valid source supported them"
    )
