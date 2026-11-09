"""Schemas for the Evaluation Agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BENCHMARK_DISCLAIMER = (
    "No benchmarks were executed by this application. All scores below are as reported by "
    "the cited sources and were only checked to appear verbatim in the retrieved source text."
)


class BenchmarkResult(BaseModel):
    model_name: str
    benchmark: str = Field(description="dataset / benchmark name, e.g. MMMU, MMBench")
    metric: str = Field(default="not stated", description="e.g. accuracy, F1")
    score: str = Field(description="score exactly as written in the source, e.g. '58.6'")
    source_id: str = Field(description="ID of the source that reports this score, e.g. S2")
    reported_by: Literal["official", "third-party", "unclear"] = Field(
        default="unclear",
        description="official = the model's own developers (model card / paper / repo); third-party = others",
    )
    # set by code:
    verified_in_source: bool = False


class ModelAssessment(BaseModel):
    model_name: str
    onprem_suitability: Literal["high", "medium", "low", "insufficient evidence"]
    rationale: str = Field(description="1-2 sentences with [S#] citations")
    memory_and_inference: str = Field(default="Not documented in retrieved sources")
    quantisation_options: list[str] = Field(default_factory=list, description="e.g. GGUF Q4_K_M, AWQ, 4-bit")
    limitations: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    assessment_type: Literal["qualitative"] = "qualitative"  # suitability is a judgement, not a measurement


class EvaluationLLMOutput(BaseModel):
    benchmarks: list[BenchmarkResult] = Field(default_factory=list)
    assessments: list[ModelAssessment] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list, description="each with [S#] citations")
    missing_evidence: list[str] = Field(
        default_factory=list, description="what could NOT be found, e.g. 'No VRAM figures for Model B'"
    )
    recommendations: list[str] = Field(default_factory=list)


class EvaluationOutput(BaseModel):
    benchmarks: list[BenchmarkResult] = Field(default_factory=list)  # verified only
    rejected_benchmarks: list[BenchmarkResult] = Field(
        default_factory=list, description="scores the LLM reported that could not be found in the source"
    )
    assessments: list[ModelAssessment] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    disclaimer: str = BENCHMARK_DISCLAIMER
