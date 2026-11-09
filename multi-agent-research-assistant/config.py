"""Central configuration. Every tunable setting is read from environment variables
(or a local .env file) here, so the rest of the code never calls os.getenv directly."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    ollama_host: str
    ollama_model: str
    temperature: float
    num_ctx: int
    timeout: int
    github_token: str | None
    max_results_per_source: int
    cache_ttl_hours: int
    cache_dir: Path
    output_dir: Path


def get_settings() -> Settings:
    return Settings(
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        temperature=_float("OLLAMA_TEMPERATURE", 0.1),
        num_ctx=_int("OLLAMA_NUM_CTX", 8192),
        timeout=_int("OLLAMA_TIMEOUT", 600),
        github_token=os.getenv("GITHUB_TOKEN") or None,
        max_results_per_source=_int("MAX_RESULTS_PER_SOURCE", 4),
        cache_ttl_hours=_int("CACHE_TTL_HOURS", 24),
        cache_dir=PROJECT_ROOT / ".cache",
        output_dir=PROJECT_ROOT / "outputs",
    )
