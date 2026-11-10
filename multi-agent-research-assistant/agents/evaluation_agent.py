"""AGENT 3: Evaluation Agent.

Responsibility: judge the evidence: benchmarks, limitations, on-prem suitability,
memory/quantisation, trade-offs and *missing* evidence.

Input:  ResearchOutput.findings + the original Source texts (for verification)
LLM:    one structured call -> EvaluationLLMOutput
Code:   BENCHMARK VERIFICATION: a score is only kept if that exact number appears in
        the cited source's retrieved text. Anything else is moved to `rejected_benchmarks`
        and flagged as missing evidence. The app never runs benchmarks itself and says so.
        MEMORY ESTIMATES: arithmetic from API parameter counts, labelled as estimates.
"""

from __future__ import annotations

import re

from schemas.evaluation import BenchmarkResult, EvaluationLLMOutput, EvaluationOutput, MemoryEstimate
from schemas.research import ResearchOutput, Source
from services.ollama_client import OllamaClient
from utils.citations import keep_valid_ids, strip_invalid_citations
from utils.evidence import model_evidence, rank_models

SYSTEM_PROMPT = """You are the EVALUATION AGENT in a team of AI research agents.
Your responsibility: critically evaluate the evidence about AI models found by the Research Agent:
benchmark results, limitations, memory/inference requirements, quantisation options and
suitability for on-premise deployment.
Rules you must follow:
- Use ONLY the findings provided. Do not use outside knowledge.
- Only report a benchmark score if the findings state that number. Copy the score exactly.
  Never estimate, round or invent scores. Every benchmark needs the source_id that reports it.
- reported_by: "official" if the source is the model developers' own model card/paper/repo,
  "third-party" if someone else measured it, otherwise "unclear".
- Nobody in this team ran any benchmark. Never say a benchmark was run or reproduced.
- onprem_suitability is a qualitative judgement; use "insufficient evidence" when the findings
  do not cover hardware/memory needs.
- missing_evidence: list important things the findings do NOT tell us (e.g. no VRAM figures,
  no independent benchmarks, unclear licence).
- Cite sources with [S#] in rationale, trade_offs and recommendations.
- Answer with a JSON object that matches the requested schema. No extra text."""

USER_PROMPT = """Research topic: {topic}

Models identified so far: {models}

EVIDENCE BY MODEL (lines start with their source ID):
{by_model}

OTHER FINDINGS (summaries):
{findings}

Evaluate the evidence. Give one entry in "assessments" for each of the {max_models} most relevant
models above (use "insufficient evidence" when the findings say little about it). Return JSON only."""

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def score_in_source(result: BenchmarkResult, source: Source | None) -> bool:
    """True if every number in the reported score literally appears in the source text,
    AND the benchmark name appears too. Cheap, transparent fact-check."""
    if source is None:
        return False
    text = _norm(f"{source.title} {source.snippet} {source.content}")
    numbers = _NUMBER.findall(result.score)
    if not numbers:
        return False
    text_numbers = set(_NUMBER.findall(text))
    benchmark_words = [w for w in re.findall(r"[a-z0-9\-]+", result.benchmark.lower()) if len(w) > 2]
    return all(n in text_numbers for n in numbers) and any(w in text for w in benchmark_words)


BYTES_PER_PARAM = {"fp16_gb": 2.0, "int8_gb": 1.0, "int4_gb": 0.5}
OVERHEAD = 1.2


def memory_estimates(sources: list[Source]) -> list[MemoryEstimate]:
    """Deterministic, labelled estimate of weight memory for models whose parameter count
    came from the Hugging Face API (never from LLM text)."""
    out = []
    for s in sources:
        total = s.metadata.get("parameters_total")
        if not total:
            continue
        sizes = {k: round(total * b * OVERHEAD / 1e9, 1) for k, b in BYTES_PER_PARAM.items()}
        out.append(MemoryEstimate(
            model_name=s.metadata.get("model_id", s.title), parameters=s.metadata.get("parameters_hf", ""),
            source_id=s.source_id, **sizes,
        ))
    return out


def run(
    topic: str,
    research: ResearchOutput,
    sources: list[Source],
    llm: OllamaClient | None = None,
    max_models: int = 5,
    progress=None,
) -> EvaluationOutput:
    llm = llm or OllamaClient()
    progress = progress or (lambda *args, **kwargs: None)
    if not research.findings:
        return EvaluationOutput(missing_evidence=["No research findings were available to evaluate."])

    by_id = {s.source_id: s for s in sources}
    valid = set(by_id)
    top = rank_models(research)[: max_models + 2]
    by_model = []
    for name in top:
        lines, _ = model_evidence(name, research, by_id)
        if lines:
            by_model.append(f"## {name}\n" + "\n".join(lines[:12]))
    progress(f"Evaluating evidence for {len(by_model)} models", step="evaluate", models=top)
    raw = llm.chat_structured(
        SYSTEM_PROMPT,
        USER_PROMPT.format(
            topic=topic,
            models=", ".join(top) or "(none identified)",
            by_model="\n".join(by_model) or "(none)",
            findings="\n".join(f"[{f.source_id}] {f.title}: {f.summary}" for f in research.findings),
            max_models=max_models,
        ),
        EvaluationLLMOutput,
        max_tokens=2000,
    )

    verified, rejected = [], []
    for b in raw.benchmarks:
        b.verified_in_source = b.source_id in valid and score_in_source(b, by_id.get(b.source_id))
        if b.verified_in_source:
            # Code overrides the label for generic web pages: they are never the developer's own report.
            if by_id[b.source_id].source_type == "web" and b.reported_by == "official":
                b.reported_by = "unclear"
            verified.append(b)
        else:
            rejected.append(b)

    missing = list(raw.missing_evidence)
    if rejected:
        missing.append(
            f"{len(rejected)} benchmark score(s) suggested by the model could not be found in the cited "
            "source text and were excluded."
        )
    if not verified:
        missing.append("No benchmark scores could be verified in the retrieved sources.")

    def clean(items: list[str]) -> list[str]:
        return [t.strip() for t in (strip_invalid_citations(i, valid)[0] for i in items) if t.strip()]

    assessments = []
    for a in raw.assessments[:max_models]:
        a.source_ids = keep_valid_ids(a.source_ids, valid)
        a.rationale = strip_invalid_citations(a.rationale, valid)[0]
        if not a.source_ids and a.onprem_suitability != "insufficient evidence":
            a.onprem_suitability = "insufficient evidence"  # no evidence -> no confident verdict
        assessments.append(a)

    if not assessments:
        missing.append("No model-level on-premise assessment could be derived from the findings.")

    progress(
        f"Benchmark check: {len(verified)} verified, {len(rejected)} rejected", step="verify",
        proposed=len(raw.benchmarks), verified=[f"{b.model_name} · {b.benchmark} {b.score}" for b in verified],
        rejected=[f"{b.model_name} · {b.benchmark} {b.score} [{b.source_id}]" for b in rejected],
    )
    estimates = memory_estimates(sources)
    progress(
        f"{len(estimates)} memory estimates computed", step="memory",
        estimates=[{"model": m.model_name, "parameters": m.parameters, "int4_gb": m.int4_gb, "fp16_gb": m.fp16_gb}
                   for m in estimates],
        assessments=[{"model": a.model_name, "suitability": a.onprem_suitability} for a in assessments],
    )

    return EvaluationOutput(
        benchmarks=verified,
        rejected_benchmarks=rejected,
        assessments=assessments,
        memory_estimates=estimates,
        trade_offs=clean(raw.trade_offs),
        missing_evidence=missing,
        recommendations=clean(raw.recommendations),
    )
