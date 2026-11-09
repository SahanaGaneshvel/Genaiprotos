"""LangGraph workflow: a fixed, loop-free pipeline of four agents.

    START -> orchestrator --(cannot start)--> END
                 |
                 v
              research --(0 sources)--> insufficient_report -> END
                 |      --(agent crashed)--> END
                 v
             comparison -> evaluation -> report -> END

Comparison and Evaluation both read only the Research Agent's output (they are
logically parallel) but run sequentially: with one local model on a CPU, Ollama
would queue parallel requests anyway, and sequential steps keep status display simple.

Live status for the UI: each node emits {"agent", "status"/"message"} events through
LangGraph's custom stream (get_stream_writer). The app consumes them with
graph.stream(..., stream_mode=["custom", "values"]).
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Callable

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from agents import comparison_agent, evaluation_agent, report_agent, research_agent
from config import get_settings
from orchestration.state import ResearchState, initial_state
from schemas.comparison import ComparisonOutput
from schemas.evaluation import EvaluationOutput
from services.ollama_client import OllamaClient
from utils.helpers import validate_topic

MAX_MODELS = {"basic": 4, "detailed": 6}


def _emit(event: dict) -> None:
    """Send a live event to whoever is streaming the graph (no-op outside a graph run)."""
    try:
        get_stream_writer()(event)
    except Exception:
        pass


def _llm() -> OllamaClient:
    return OllamaClient()


def run_agent(name: str, state: ResearchState, work: Callable[[], dict]) -> dict:
    """Common wrapper for every agent node: status, timing, error capture.

    `work()` does the agent's real job and returns its partial state update.
    Exceptions are caught so one failing agent never crashes the app.
    """
    _emit({"agent": name, "status": "running"})
    start = time.perf_counter()
    update: dict = {"execution_order": [name]}
    try:
        update.update(work())
        status = "completed"
    except Exception as exc:  # noqa: BLE001 - we want to record ANY agent failure
        status = "failed"
        update["errors"] = [f"{name} agent failed: {exc}"]
    elapsed = round(time.perf_counter() - start, 2)
    update["agent_status"] = {name: status}
    update["timings"] = {name: elapsed}
    _emit({"agent": name, "status": status, "seconds": elapsed})
    return update


# ------------------------------------------------------------------ nodes
def orchestrator_node(state: ResearchState) -> dict:
    """Validate input and check the local LLM before any agent runs."""
    try:
        topic = validate_topic(state.get("topic", ""))
    except ValueError as exc:
        return {"abort_reason": str(exc), "errors": [str(exc)], "execution_order": ["orchestrator"]}
    ok, message = _llm().check_health()
    if not ok:
        return {"abort_reason": message, "errors": [message], "execution_order": ["orchestrator"]}
    return {"topic": topic, "execution_order": ["orchestrator"]}


def research_node(state: ResearchState) -> dict:
    def work():
        progress = lambda msg: _emit({"agent": "research", "message": msg})  # noqa: E731
        sources, output = research_agent.run(state["topic"], state.get("depth", "basic"), _llm(), progress)
        errors = [f"retrieval: {e}" for e in output.retrieval_errors]
        return {"sources": sources, "research": output, "errors": errors}

    return run_agent("research", state, work)


def comparison_node(state: ResearchState) -> dict:
    def work():
        _emit({"agent": "comparison", "message": "Comparing models from research findings"})
        out = comparison_agent.run(
            state["topic"], state["research"], state["sources"], _llm(), MAX_MODELS.get(state.get("depth"), 4)
        )
        return {"comparison": out, "errors": [f"comparison: {w}" for w in out.warnings]}

    update = run_agent("comparison", state, work)
    update.setdefault("comparison", ComparisonOutput())  # downstream agents always get a value
    return update


def evaluation_node(state: ResearchState) -> dict:
    def work():
        _emit({"agent": "evaluation", "message": "Evaluating benchmarks and deployment evidence"})
        out = evaluation_agent.run(
            state["topic"], state["research"], state["sources"], _llm(), MAX_MODELS.get(state.get("depth"), 4)
        )
        return {"evaluation": out}

    update = run_agent("evaluation", state, work)
    update.setdefault(
        "evaluation", EvaluationOutput(missing_evidence=["The Evaluation Agent failed; no evaluation available."])
    )
    return update


def report_node(state: ResearchState) -> dict:
    def work():
        _emit({"agent": "report", "message": "Writing the final report"})
        out = report_agent.run(
            state["topic"], state["research"], state["comparison"], state["evaluation"],
            state["sources"], state.get("depth", "basic"), _llm(),
        )
        return {"report": out}

    return run_agent("report", state, work)


def insufficient_report_node(state: ResearchState) -> dict:
    """Report Agent's honest mode when retrieval found nothing — no LLM, no claims."""

    def work():
        errors = state["research"].retrieval_errors if state.get("research") else []
        return {"report": report_agent.build_insufficient_evidence_report(
            state["topic"], errors or ["No sources were returned by any retrieval tool."],
            state.get("model_name", ""), state.get("sources", []))}

    update = run_agent("report", state, work)
    update["agent_status"] = {**update["agent_status"], "comparison": "skipped", "evaluation": "skipped"}
    return update


# ------------------------------------------------------------------ routing
def route_after_orchestrator(state: ResearchState) -> str:
    return "end" if state.get("abort_reason") else "research"


def route_after_research(state: ResearchState) -> str:
    if state["agent_status"].get("research") == "failed":
        return "end"
    research = state.get("research")
    if not state.get("sources") or not research or not research.findings:
        return "insufficient"  # nothing relevant to analyse -> honest report, no LLM claims
    return "comparison"


def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("research", research_node)
    g.add_node("comparison", comparison_node)
    g.add_node("evaluation", evaluation_node)
    g.add_node("report", report_node)
    g.add_node("insufficient_report", insufficient_report_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", route_after_orchestrator, {"research": "research", "end": END})
    g.add_conditional_edges(
        "research",
        route_after_research,
        {"comparison": "comparison", "insufficient": "insufficient_report", "end": END},
    )
    g.add_edge("comparison", "evaluation")
    g.add_edge("evaluation", "report")
    g.add_edge("report", END)
    g.add_edge("insufficient_report", END)
    return g.compile()


# ------------------------------------------------------------------ running + saving
def run_workflow(
    topic: str, depth: str = "basic", on_event: Callable[[dict], None] | None = None
) -> ResearchState:
    """Run the graph, forwarding live events to `on_event`; returns the final state."""
    settings = get_settings()
    graph = build_graph()
    final: ResearchState = initial_state(topic, depth, settings.ollama_model)
    start = time.perf_counter()
    for mode, chunk in graph.stream(final, stream_mode=["custom", "values"]):
        if mode == "custom" and on_event:
            on_event(chunk)
        elif mode == "values":
            final = chunk
    final["timings"] = {**final.get("timings", {}), "total": round(time.perf_counter() - start, 2)}
    return final


def save_run(state: ResearchState) -> dict[str, str]:
    """Persist the report (.md) and the full structured run (.json) to outputs/."""
    out_dir = get_settings().output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = {}
    if state.get("report"):
        md_path = out_dir / f"report_{stamp}.md"
        md_path.write_text(state["report"].markdown, encoding="utf-8")
        paths["markdown"] = str(md_path)
    json_path = out_dir / f"run_{stamp}.json"
    json_path.write_text(json.dumps(to_jsonable(state), indent=2, ensure_ascii=False), encoding="utf-8")
    paths["json"] = str(json_path)
    return paths


def to_jsonable(state: ResearchState) -> dict:
    def conv(v):
        if hasattr(v, "model_dump"):
            return v.model_dump()
        if isinstance(v, list):
            return [conv(i) for i in v]
        if isinstance(v, dict):
            return {k: conv(i) for k, i in v.items()}
        return v

    return {k: conv(v) for k, v in state.items()}


if __name__ == "__main__":  # CLI: python -m orchestration.workflow "topic" [basic|detailed]
    topic_arg = sys.argv[1] if len(sys.argv) > 1 else (
        "Research the latest open-source multimodal models suitable for on-premise deployment. "
        "Compare their capabilities, benchmarks, hardware requirements, licensing and limitations."
    )
    depth_arg = sys.argv[2] if len(sys.argv) > 2 else "basic"

    def show(ev: dict) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {ev.get('agent', ''):<10} {ev.get('status') or ev.get('message')}", flush=True)

    result = run_workflow(topic_arg, depth_arg, show)
    print("\nStatus:", result.get("agent_status"), "\nTimings:", result.get("timings"))
    print("Errors:", *result.get("errors", []), sep="\n  ")
    print("Saved:", save_run(result))
