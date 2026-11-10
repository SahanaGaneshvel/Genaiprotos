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
        return str(value if value not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


# Words that signal concrete technical evidence in a passage.
EVIDENCE_SIGNALS = re.compile(
    r"\b(\d+(\.\d+)?\s?[bBmM]\b|parameters?|params|licen[cs]e|apache|mit\b|vram|gpu|memory|ram\b|"
    r"quantiz|quantis|gguf|int4|int8|4-bit|8-bit|context|tokens|benchmark|mmmu|mmbench|docvqa|"
    r"chartqa|mathvista|ocrbench|score|accuracy|ollama|vllm|llama\.cpp)",
    re.I,
)


def select_relevant_text(text: str, keywords: list[str], max_chars: int, chunk_chars: int = 500) -> str:
    """Pick the most informative passages of a long document instead of its first N characters.

    A tiny, transparent retrieval step (keyword scoring, no embeddings): split into chunks,
    score each by topic keywords + evidence signals (numbers, licences, VRAM, benchmarks),
    keep the best chunks within the budget, and return them in their original order.
    Why: live runs showed page starts are bylines, menus and intros — the model lists come later.
    """
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return text
    words = text.split(" ")
    chunks, current = [], []
    for w in words:
        current.append(w)
        if sum(len(x) + 1 for x in current) >= chunk_chars:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    kws = [k.lower() for k in keywords if len(k) > 2]

    def score(chunk: str) -> float:
        low = chunk.lower()
        return sum(low.count(k) for k in kws) + 2 * len(EVIDENCE_SIGNALS.findall(chunk))

    ranked = sorted(range(len(chunks)), key=lambda i: score(chunks[i]), reverse=True)
    keep, used = set(), 0
    for i in ranked:
        if used + len(chunks[i]) > max_chars:
            continue
        keep.add(i)
        used += len(chunks[i]) + 3
    return " … ".join(chunks[i] for i in sorted(keep))


def truncate(text: str, max_chars: int) -> str:
    """Cut text to max_chars on a word boundary (keeps prompts small for CPU inference)."""
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"
