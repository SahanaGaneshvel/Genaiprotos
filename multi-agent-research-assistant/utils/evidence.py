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
    """Does `text` talk about model `name`? 'Qwen/Qwen3.8-27B' matches 'qwen3.8 27b'.

    A match may not continue with more version digits: 'Kimi K3' must NOT match
    'Kimi K3.1-Pro' (live bug: K3 inherited K3.1-Pro's 2.78T parameter count)."""
    short = name.split("/")[-1]
    key = _squash(short)
    if len(key) < 5:  # short names ("AuK") need whole-word matching to avoid false hits
        return re.search(rf"\b{re.escape(short.lower())}\b", text.lower()) is not None
    return re.search(rf"{re.escape(key)}(?![0-9])", _squash(text)) is not None


def source_mentions(name: str, corpus: str) -> bool:
    """Lenient variant used to check attributions against a source's text.

    Versioned names ("Kimi K3.1-Pro") need an exact match — version confusion is the error we guard
    against. Descriptive names without digits ("PaliGemma VLM") only need every word to occur:
    a live run wrongly flagged a sentence because the source said "PaliGemma" and "VLM" separately."""
    if mentions(name, corpus):
        return True
    if re.search(r"\d", name):
        return False
    # every word, as a whole word — short tokens are often the distinguishing part ("Model B")
    words = re.findall(r"[a-z]+", name.split("/")[-1].lower())
    low = corpus.lower()
    return bool(words) and all(re.search(rf"\b{re.escape(w)}\b", low) for w in words)


def _finding_text(f: ResearchFinding) -> str:
    return " ".join([f.title, f.summary, *f.key_findings, *f.models_mentioned])


def _identifier(title: str) -> str:
    """'moonshotai/Kimi-K3.1-Pro (model card)' -> 'kimik31pro'; 'org/moondream' -> 'moondream'."""
    return _squash(re.split(r" \(model card\)| — ", title)[0].split("/")[-1])


def is_own_source(name: str, finding: ResearchFinding) -> bool:
    """The finding IS the model's own model card or repository: exact name match only."""
    if finding.source_type not in ("documentation", "github"):
        return False
    return _identifier(finding.title) == _squash(name.split("/")[-1])


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


OWN_SOURCE_BONUS = 2  # a model's own model card / repo is the richest, most official evidence


def has_own_source(name: str, research: ResearchOutput) -> bool:
    return any(is_own_source(name, f) for f in research.findings)


def rank_models(research: ResearchOutput) -> list[str]:
    """Candidate model names ordered by evidence: findings that mention them, with a bonus
    when one of those findings is the model's own model card or repository."""
    counts = Counter()
    for name in research.models_identified:
        mentioned = sum(mentions(name, _finding_text(f)) for f in research.findings)
        own = any(is_own_source(name, f) for f in research.findings)
        counts[name] = mentioned + (OWN_SOURCE_BONUS if own and mentioned else 0)
    return [n for n, c in counts.most_common() if c > 0]
