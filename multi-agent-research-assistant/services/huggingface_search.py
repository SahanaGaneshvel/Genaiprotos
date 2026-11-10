"""Hugging Face Hub model-card search via the public REST API (no key required).

Why: model cards are the *official* documentation for open models. The API also
returns structured facts we can trust more than LLM extraction:
  * licence           (cardData.license)
  * parameter count   (safetensors.total)
  * created / updated dates
"""

from __future__ import annotations

import re

import requests

from schemas.research import Source
from services import cache
from services.errors import RetrievalError
from utils.helpers import truncate

API = "https://huggingface.co/api/models"
HEADERS = {"User-Agent": "multi-agent-research-assistant/0.1 (educational POC)"}
# Re-uploads / quantised copies by third parties: skip, prefer the original model card.
DERIVATIVE = re.compile(r"(gguf|awq|gptq|mlx|exl2|bnb|4bit|8bit|uncensored|abliterated|heretic)", re.I)
FRONTMATTER = re.compile(r"^---\s*\n.*?\n---\s*\n", re.S)


def format_params(total: int | None) -> str | None:
    if not total:
        return None
    return f"{total / 1e9:.2f}B" if total >= 1e9 else f"{total / 1e6:.0f}M"


def _card_text(model_id: str, max_chars: int) -> str:
    try:
        resp = requests.get(f"https://huggingface.co/{model_id}/raw/main/README.md", headers=HEADERS, timeout=15)
    except requests.RequestException:
        return ""
    if resp.status_code != 200:
        return ""
    return truncate(FRONTMATTER.sub("", resp.text, count=1), max_chars)


def _details(model_id: str) -> dict:
    try:
        resp = requests.get(f"{API}/{model_id}", headers=HEADERS, timeout=15)
        return resp.json() if resp.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        return {}


def search_models(
    task: str = "any", max_results: int = 4, search: str | None = None, max_chars: int = 12000
) -> list[Source]:
    """Currently trending models for a Hub task (e.g. 'image-text-to-text'), with their model cards.

    Sorted by trendingScore, not all-time downloads: downloads favour old classics
    (a live run returned GPT-2 for a "latest models" question)."""
    key = f"{task}|{search}|{max_results}"
    cached = cache.get("hf", key)
    if cached is not None:
        return [Source(**s) for s in cached]

    params = {"sort": "trendingScore", "limit": max_results * 4}
    if task and task != "any":
        params["pipeline_tag"] = task
    if search:
        params["search"] = search
    try:
        resp = requests.get(API, params=params, headers=HEADERS, timeout=20)
    except requests.RequestException as exc:
        raise RetrievalError(f"Hugging Face request failed (check internet connection): {exc}") from exc
    if resp.status_code == 429:
        raise RetrievalError("Hugging Face API rate limit reached. Retry in a minute.")
    if resp.status_code != 200:
        raise RetrievalError(f"Hugging Face API returned HTTP {resp.status_code}.")

    ids = [m["id"] for m in resp.json() if not DERIVATIVE.search(m.get("id", ""))][:max_results]
    sources = []
    for model_id in ids:
        info = _details(model_id)
        card = info.get("cardData") or {}
        licence = card.get("license") or card.get("license_name")
        sources.append(
            Source(
                title=f"{model_id} (model card)",
                url=f"https://huggingface.co/{model_id}",
                source_type="documentation",
                published=(info.get("createdAt") or "")[:10] or None,
                snippet=f"Hugging Face model {model_id} ({info.get('pipeline_tag', task)})",
                content=_card_text(model_id, max_chars),
                metadata={
                    "model_id": model_id,
                    "license_hf": licence if isinstance(licence, str) else None,
                    "parameters_hf": format_params((info.get("safetensors") or {}).get("total")),
                    "parameters_total": (info.get("safetensors") or {}).get("total"),
                    "pipeline_tag": info.get("pipeline_tag"),
                    "last_modified": (info.get("lastModified") or "")[:10] or None,
                    "downloads": info.get("downloads"),
                },
            )
        )
    cache.put("hf", key, [s.model_dump() for s in sources])
    return sources
