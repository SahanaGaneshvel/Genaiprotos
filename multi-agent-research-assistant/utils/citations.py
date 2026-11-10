"""Citation registry helpers: the anti-fabrication layer.

The LLM only ever writes citation IDs like [S3]. Code then:
  * drops IDs that do not exist in the source registry (fabricated citations),
  * builds the References list from the registry (real URLs only),
  * checks the final report for consistency.
"""

from __future__ import annotations

import re

from schemas.research import Source

CITATION = re.compile(r"\[(S\d+)\]")
# also catches grouped forms the model sometimes writes: [S1, S2] / [S1][S2]
GROUPED = re.compile(r"\[((?:S\d+)(?:\s*[,;]\s*S\d+)+)\]")


def registry(sources: list[Source]) -> dict[str, Source]:
    return {s.source_id: s for s in sources}


def normalise_grouped(text: str) -> str:
    """'[S1, S2]' -> '[S1][S2]' so every citation has one canonical form."""
    return GROUPED.sub(lambda m: "".join(f"[{i.strip()}]" for i in re.split(r"[,;]", m.group(1))), text)


def find_citations(text: str) -> list[str]:
    return CITATION.findall(normalise_grouped(text or ""))


def keep_valid_ids(ids: list[str], valid: set[str]) -> list[str]:
    seen, out = set(), []
    for i in ids:
        i = i.strip().strip("[]")
        if i in valid and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def strip_invalid_citations(text: str, valid: set[str]) -> tuple[str, list[str]]:
    """Remove [S#] markers that are not in the registry. Returns (clean text, removed IDs)."""
    removed: list[str] = []

    def repl(m: re.Match) -> str:
        if m.group(1) in valid:
            return m.group(0)
        removed.append(m.group(1))
        return ""

    clean = CITATION.sub(repl, normalise_grouped(text or ""))
    clean = re.sub(r"[ \t]+([.,;:])", r"\1", clean) if removed else clean  # "fact [S99]." -> "fact."
    return re.sub(r"[ \t]{2,}", " ", clean), removed


def format_reference(src: Source) -> str:
    date = f" ({src.published})" if src.published else " (date not available)"
    return f"- **[{src.source_id}]** {src.title}{date}. *{src.source_type}*. <{src.url}>"


def check_consistency(markdown: str, sources: list[Source]) -> dict:
    """Report-level audit used by tests and shown in the UI."""
    valid = set(registry(sources))
    cited = set(find_citations(markdown))
    return {
        "cited": sorted(cited & valid, key=lambda s: int(s[1:])),
        "unknown": sorted(cited - valid),
        "uncited": sorted(valid - cited, key=lambda s: int(s[1:])),
    }
