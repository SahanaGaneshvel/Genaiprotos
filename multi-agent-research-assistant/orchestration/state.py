"""The shared state that flows through the LangGraph workflow.

Every agent node READS what it needs from this dict and RETURNS only the keys it
changed. LangGraph merges that partial update into the state.

Keys annotated with a reducer (merge_dicts / operator.add) are *combined* instead of
overwritten, so each node can add its own status/timing/error without erasing the
others' entries.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from schemas.comparison import ComparisonOutput
from schemas.evaluation import EvaluationOutput
from schemas.report import ReportOutput
from schemas.research import ResearchOutput, Source

AgentName = Literal["research", "comparison", "evaluation", "report"]
AgentStatus = Literal["pending", "running", "completed", "failed", "skipped"]
AGENTS: tuple[AgentName, ...] = ("research", "comparison", "evaluation", "report")


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer: combine two dicts (right wins on the same key)."""
    return {**(left or {}), **(right or {})}


class ResearchState(TypedDict, total=False):
    # --- input (set once by the caller / orchestrator)
    topic: str
    depth: str  # "basic" | "detailed"
    model_name: str
    abort_reason: str  # set by the orchestrator if the run cannot start

    # --- agent outputs (each written by exactly one agent)
    sources: list[Source]  # citation registry, written by Research Agent
    research: ResearchOutput
    comparison: ComparisonOutput
    evaluation: EvaluationOutput
    report: ReportOutput

    # --- bookkeeping (written by every agent, merged by reducers)
    agent_status: Annotated[dict[str, AgentStatus], merge_dicts]
    timings: Annotated[dict[str, float], merge_dicts]  # seconds per agent
    errors: Annotated[list[str], operator.add]
    execution_order: Annotated[list[str], operator.add]

    # --- recorded by run_workflow after the graph finishes: every live event with its
    #     time offset, so a saved run can be replayed step by step
    events: list[dict]


def initial_state(topic: str, depth: str, model_name: str) -> ResearchState:
    return ResearchState(
        topic=topic,
        depth=depth,
        model_name=model_name,
        agent_status={a: "pending" for a in AGENTS},
        timings={},
        errors=[],
        execution_order=[],
    )
