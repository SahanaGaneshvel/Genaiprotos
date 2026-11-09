"""Small, dependency-free helpers shared across the project."""

from __future__ import annotations

import json
import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply.

    Small models sometimes wrap JSON in ```json fences, prepend a sentence, or
    leak a <think> block. We strip those, then fall back to the outermost {...}.
    Raises ValueError if no JSON object can be recovered.
    """
    if not text or not text.strip():
        raise ValueError("Empty LLM response")
    cleaned = _THINK_BLOCK.sub("", text).strip()
    cleaned = _CODE_FENCE.sub("", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in LLM response") from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON in LLM response: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON is not an object")
    return data


def validate_topic(topic: str) -> str:
    """Reject empty / too short / too long / non-text research topics before any work starts."""
    topic = " ".join((topic or "").split())
    if len(topic) < 10:
        raise ValueError("Please describe the research topic in at least 10 characters.")
    if len(topic) > 1000:
        raise ValueError("Research topic is too long (max 1000 characters).")
    if sum(c.isalpha() for c in topic) < 5:
        raise ValueError("Research topic must contain words, not only numbers or symbols.")
    return topic


def dedupe_keep_order(items: list[str]) -> list[str]:
    """Case-insensitive de-duplication that keeps the first spelling seen."""
    seen, out = set(), []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown table; escapes pipes/newlines so cell text cannot break the layout."""

    def cell(value) -> str:
        return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def truncate(text: str, max_chars: int) -> str:
    """Cut text to max_chars on a word boundary (keeps prompts small for CPU inference)."""
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"
