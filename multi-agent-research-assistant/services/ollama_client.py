"""Reusable client for a local Ollama server (REST API, no SDK).

Why plain HTTP instead of LangChain/ollama-python? It is ~150 lines you can read
end-to-end, has no version conflicts, and makes every request explicit:

    POST {OLLAMA_HOST}/api/chat
    {"model": ..., "messages": [system, user], "format": <JSON schema>,
     "stream": false, "think": false, "options": {"temperature": ..., "num_ctx": ...}}

`format` = a JSON schema makes Ollama constrain generation so the reply is JSON
of that shape ("structured outputs"). We still validate with Pydantic because
constrained JSON can be well-formed yet semantically wrong.
"""

from __future__ import annotations

import copy
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from config import Settings, get_settings
from utils.helpers import extract_json

T = TypeVar("T", bound=BaseModel)


class OllamaError(Exception):
    """Base class: any problem talking to the local LLM."""


class OllamaConnectionError(OllamaError):
    """Server not running / unreachable / timed out."""


class OllamaModelNotFoundError(OllamaError):
    """Configured model has not been pulled."""


class OllamaResponseError(OllamaError):
    """Server answered, but the output was unusable (malformed / failed validation)."""


def _inline_refs(schema: dict) -> dict:
    """Pydantic emits nested models as {"$ref": "#/$defs/X"}. Inline them so the
    schema is self-contained (safer for Ollama's grammar converter)."""
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return resolve(copy.deepcopy(defs[name]))
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


class OllamaClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model = self.settings.ollama_model
        self.base_url = self.settings.ollama_host

    # ------------------------------------------------------------------ health
    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}. Is it running? "
                f"Start it with `ollama serve` (or open the Ollama app). Details: {exc}"
            ) from exc
        return [m.get("name", "") for m in resp.json().get("models", [])]

    def check_health(self) -> tuple[bool, str]:
        """Returns (ok, human-readable message). Never raises — used by the UI."""
        try:
            models = self.list_models()
        except OllamaConnectionError as exc:
            return False, str(exc)
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if wanted not in models:
            return False, (
                f"Model '{self.model}' is not downloaded. Run `ollama pull {self.model}` "
                f"or set OLLAMA_MODEL to one of: {', '.join(models) or 'none installed'}."
            )
        return True, f"Ollama is running and '{self.model}' is available."

    # -------------------------------------------------------------------- chat
    def chat(
        self,
        system: str,
        user: str,
        *,
        json_schema: dict | None = None,
        temperature: float | None = None,
    ) -> str:
        """Send one system+user exchange; return the assistant's text."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # Qwen3.x "thinking" mode multiplies latency on CPU; we want direct answers.
            "think": False,
            "options": {
                "temperature": self.settings.temperature if temperature is None else temperature,
                "num_ctx": self.settings.num_ctx,
            },
        }
        if json_schema is not None:
            payload["format"] = json_schema

        resp = self._post(payload)
        # Some models reject the `think` flag entirely — retry once without it.
        if resp.status_code == 400 and "think" in resp.text.lower():
            payload.pop("think")
            resp = self._post(payload)

        if resp.status_code == 404 and "not found" in resp.text.lower():
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' not found on the Ollama server. Run `ollama pull {self.model}`."
            )
        if resp.status_code >= 400:
            raise OllamaResponseError(f"Ollama returned HTTP {resp.status_code}: {resp.text[:300]}")

        content = resp.json().get("message", {}).get("content", "")
        if not content.strip():
            raise OllamaResponseError("Ollama returned an empty response.")
        return content

    def chat_structured(
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        temperature: float | None = None,
        retries: int = 1,
    ) -> T:
        """Ask for JSON matching `schema`, validate it with Pydantic.

        On malformed/invalid output we retry, showing the model its own error —
        a cheap, bounded self-correction (max `retries` extra attempts, no loops).
        """
        json_schema = _inline_refs(schema.model_json_schema())
        prompt = user
        last_error = ""
        for _ in range(retries + 1):
            raw = self.chat(system, prompt, json_schema=json_schema, temperature=temperature)
            try:
                return schema.model_validate(extract_json(raw))
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)[:500]
                prompt = (
                    f"{user}\n\nYour previous reply was invalid: {last_error}\n"
                    "Reply again with ONLY a JSON object that matches the schema."
                )
        raise OllamaResponseError(f"LLM output failed validation for {schema.__name__}: {last_error}")

    def _post(self, payload: dict) -> requests.Response:
        try:
            return requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.settings.timeout
            )
        except requests.Timeout as exc:
            raise OllamaConnectionError(
                f"Ollama did not respond within {self.settings.timeout}s. "
                "Try a smaller model (OLLAMA_MODEL) or raise OLLAMA_TIMEOUT."
            ) from exc
        except requests.RequestException as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}. Is it running? Details: {exc}"
            ) from exc
