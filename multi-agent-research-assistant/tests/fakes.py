"""Test doubles shared by the test suite (no network, no Ollama)."""

from __future__ import annotations

from pydantic import BaseModel

from schemas.research import Source
from services.ollama_client import OllamaResponseError


class FakeLLM:
    """Stands in for OllamaClient. `responses` maps a schema class name to either
    a dict (returned as that schema), a callable(prompt) -> dict, or an Exception."""

    model = "fake-model"

    def __init__(self, responses: dict, healthy: tuple[bool, str] = (True, "ok")):
        self.responses = responses
        self.healthy = healthy
        self.calls: list[tuple[str, str]] = []  # (schema name, user prompt)

    def check_health(self):
        return self.healthy

    def chat_structured(self, system, user, schema: type[BaseModel], **kwargs):
        self.calls.append((schema.__name__, user))
        value = self.responses.get(schema.__name__)
        if value is None:
            raise OllamaResponseError(f"FakeLLM has no response for {schema.__name__}")
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(user)
        return schema.model_validate(value)

    def chat(self, system, user, **kwargs):
        self.calls.append(("text", user))
        value = self.responses.get("text", "")
        return value(user) if callable(value) else value


def make_sources() -> list[Source]:
    return [
        Source(
            source_id="S1",
            title="Model A model card",
            url="https://huggingface.co/org/model-a",
            source_type="documentation",
            published="2025-05-01",
            content="Model A is a 7B vision-language model. Apache-2.0. MMMU 58.6.",
        ),
        Source(
            source_id="S2",
            title="Model B paper",
            url="https://arxiv.org/abs/2501.00002",
            source_type="arxiv",
            published="2025-01-10",
            content="Model B, 3B parameters, supports image and audio input. Scores 61.2 on MMBench.",
        ),
        Source(
            source_id="S3",
            title="org/model-b",
            url="https://github.com/org/model-b",
            source_type="github",
            content="Run with 8 GB VRAM using 4-bit quantisation.",
            metadata={"license_spdx": "MIT", "stars": 900},
        ),
    ]
