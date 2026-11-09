"""Group research evidence by model — done by code, shared by Comparison and Evaluation.

Why: a single prompt with every finding asked a 2B model to do too much at once
(a live run produced an empty comparison table). Giving it only the lines that are
about ONE model makes each call small and focused, and the supporting source IDs
are decided by code (which findings mention the model), not by the LLM.
"""

from __future__ import annotations

import re
from collections import Counter

from schemas.research import ResearchFinding, ResearchOutput, Source


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def mentions(name: str, text: str) -> bool:
    """Does `text` talk about model `name`? 'Qwen/Qwen3.8-27B' matches 'qwen3.8 27b'."""
    short = name.split("/")[-1]
    key = _squash(short)
    if len(key) < 5:  # short names ("AuK") need whole-word matching to avoid false hits
        return re.search(rf"\b{re.escape(short.lower())}\b", text.lower()) is not None
    return key in _squash(text)


def _finding_text(f: ResearchFinding) -> str:
    return " ".join([f.title, f.summary, *f.key_findings, *f.models_mentioned])


def is_own_source(name: str, finding: ResearchFinding) -> bool:
    """The finding comes from the model's own model card / repo (title names the model)."""
    return mentions(name, finding.title)


def model_evidence(
    name: str, research: ResearchOutput, by_id: dict[str, Source]
) -> tuple[list[str], list[str]]:
    """Return (evidence lines prefixed with [S#], supporting source IDs) for one model."""
    lines: list[str] = []
    ids: list[str] = []
    for f in research.findings:
        if not mentions(name, _finding_text(f)):
            continue
        own = is_own_source(name, f)
        picked = f.key_findings if own else [k for k in f.key_findings if mentions(name, k)]
        if not picked and mentions(name, f.summary):
            picked = [f.summary]
        meta = by_id.get(f.source_id).metadata if f.source_id in by_id else {}
        if own and meta.get("license_hf"):
            picked = picked + [f"Licence (Hugging Face metadata): {meta['license_hf']}"]
        if own and meta.get("parameters_hf"):
            picked = picked + [f"Parameters (Hugging Face weight files): {meta['parameters_hf']}"]
        if own and meta.get("license_spdx"):
            picked = picked + [f"Licence (GitHub metadata): {meta['license_spdx']}"]
        if picked:
            ids.append(f.source_id)
            lines += [f"[{f.source_id}] {p}" for p in picked]
    return lines, ids


def rank_models(research: ResearchOutput) -> list[str]:
    """Candidate model names ordered by how many findings mention them (most evidence first)."""
    counts = Counter()
    for name in research.models_identified:
        counts[name] = sum(mentions(name, _finding_text(f)) for f in research.findings)
    return [n for n, c in counts.most_common() if c > 0]
