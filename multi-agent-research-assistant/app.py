"""Streamlit frontend — Multi-Agent AI Research Assistant.

Run:  streamlit run app.py

The page only *displays* the workflow. Agent cards change state from real LangGraph
events emitted by the nodes (running -> completed/failed), not from timers.
"""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from config import get_settings
from orchestration.state import AGENTS
from orchestration.workflow import run_workflow, save_run
from schemas.evaluation import MEMORY_ESTIMATE_BASIS
from services.ollama_client import OllamaClient

EXAMPLE_TOPIC = (
    "Research the latest open-source multimodal models suitable for on-premise deployment. "
    "Compare their capabilities, benchmarks, hardware requirements, licensing and limitations."
)
AGENT_INFO = {
    "research": ("Research Agent", "Plans queries · searches web, model cards, arXiv, GitHub · extracts findings"),
    "comparison": ("Comparison Agent", "Compares modalities, size, context, hardware and licences"),
    "evaluation": ("Evaluation Agent", "Verifies reported benchmarks · assesses on-prem suitability"),
    "report": ("Report Agent", "Consolidates everything into a cited 10-section report"),
}
STATUS_STYLE = {
    "pending": ("Pending", "#6b7280"),
    "running": ("Running", "#2563eb"),
    "completed": ("Completed", "#16a34a"),
    "failed": ("Failed", "#dc2626"),
    "skipped": ("Skipped", "#9ca3af"),
}

st.set_page_config(page_title="Multi-Agent AI Research Assistant", page_icon="🔎", layout="wide")
st.markdown(
    """
<style>
  .block-container {padding-top: 2rem; max-width: 1300px;}
  .pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem;
         font-weight:600; border:1px solid currentColor;}
  .agent-title {font-weight:600; font-size:1rem; margin-bottom:2px;}
  .agent-desc {font-size:0.8rem; opacity:0.7; min-height:2.4em;}
  .agent-detail {font-size:0.78rem; opacity:0.85; margin-top:6px; min-height:2.4em;
                 overflow:hidden; text-overflow:ellipsis;}
  .model-chip {font-family:monospace; padding:2px 8px; border-radius:6px;
               background:rgba(127,127,127,0.15);}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ helpers
@st.cache_data(ttl=20, show_spinner=False)
def ollama_health(model: str) -> tuple[bool, str]:
    return OllamaClient().check_health()


def render_card(slot, agent: str, status: str, detail: str = "", seconds: float | None = None) -> None:
    title, desc = AGENT_INFO[agent]
    label, colour = STATUS_STYLE.get(status, STATUS_STYLE["pending"])
    timing = f" · {seconds:.1f}s" if seconds is not None else ""
    with slot.container(border=True):
        st.markdown(
            f'<div class="agent-title">{title}</div>'
            f'<div class="agent-desc">{desc}</div>'
            f'<span class="pill" style="color:{colour}">{label}{timing}</span>'
            f'<div class="agent-detail">{html.escape(detail[:110])}</div>',
            unsafe_allow_html=True,
        )


def link_df(rows: list[dict]) -> None:
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={"URL": st.column_config.LinkColumn("URL")},
    )


# ------------------------------------------------------------------ header
settings = get_settings()
st.title("Multi-Agent AI Research Assistant")
st.caption(
    "Four specialised agents — Research, Comparison, Evaluation and Report — collaborate through a "
    "LangGraph workflow to produce a cited technical report. All inference runs locally via Ollama."
)
healthy, health_msg = ollama_health(settings.ollama_model)
st.markdown(
    f'Local model: <span class="model-chip">{html.escape(settings.ollama_model)}</span> &nbsp; '
    + ("🟢 Ollama ready" if healthy else "🔴 Ollama not ready"),
    unsafe_allow_html=True,
)
if not healthy:
    st.error(health_msg)

# ------------------------------------------------------------------ input
with st.container(border=True):
    topic = st.text_area("Research topic", value=EXAMPLE_TOPIC, height=90, max_chars=1000)
    c1, c2, _ = st.columns([2, 1.2, 3])
    depth = c1.radio(
        "Research depth", ["Basic", "Detailed"], horizontal=True,
        help="Basic: ~2 sources per category (faster). Detailed: ~4 per category (slower on CPU).",
    )
    start = c2.button("Start Research", type="primary", disabled=not healthy, width="stretch")
    st.caption("On a CPU-only machine a Basic run takes several minutes — every source is read by the local model.")

# ------------------------------------------------------------------ agent cards
st.subheader("Agent execution")
# st.empty() placeholders: each update REPLACES the card. (Writing into the column itself
# appended a new card per status event — found by tests/test_app.py.)
slots = {agent: col.empty() for agent, col in zip(AGENTS, st.columns(4))}
result = st.session_state.get("result")
for agent in AGENTS:
    status = result["agent_status"].get(agent, "pending") if result else "pending"
    secs = result.get("timings", {}).get(agent) if result else None
    render_card(slots[agent], agent, status, seconds=secs)
activity = st.empty()

if start:
    st.session_state.pop("result", None)
    log: list[str] = []
    live = {a: {"status": "pending", "detail": "", "seconds": None} for a in AGENTS}

    def on_event(ev: dict) -> None:
        agent = ev.get("agent")
        if agent not in live:
            return
        if "status" in ev:
            live[agent]["status"] = ev["status"]
            live[agent]["seconds"] = ev.get("seconds")
        if "message" in ev:
            live[agent]["detail"] = ev["message"]
            log.append(f"{datetime.now():%H:%M:%S}  {AGENT_INFO[agent][0]}: {ev['message']}")
            activity.code("\n".join(log[-8:]), language=None)
        render_card(slots[agent], agent, live[agent]["status"], live[agent]["detail"], live[agent]["seconds"])

    with st.spinner("Agents are working…"):
        state = run_workflow(topic, depth.lower(), on_event)
    for agent in AGENTS:  # final, authoritative statuses (e.g. "skipped")
        render_card(slots[agent], agent, state["agent_status"].get(agent, "pending"),
                    seconds=state.get("timings", {}).get(agent))
    try:
        state["saved"] = save_run(state)
    except OSError as exc:
        state.setdefault("errors", []).append(f"Could not save outputs: {exc}")
    st.session_state["result"] = state
    result = state

# ------------------------------------------------------------------ results
if not result:
    st.info("Enter a topic and press **Start Research**. Results will appear here.")
    st.stop()

if result.get("abort_reason"):
    st.error(f"Research could not start: {result['abort_reason']}")
    st.stop()

sources = result.get("sources", [])
research = result.get("research")
comparison = result.get("comparison")
evaluation = result.get("evaluation")
report = result.get("report")

m = st.columns(5)
m[0].metric("Sources retrieved", len(sources))
m[1].metric("Relevant findings", len(research.findings) if research else 0)
m[2].metric("Models compared", len(comparison.models) if comparison else 0)
m[3].metric("Verified benchmarks", len(evaluation.benchmarks) if evaluation else 0)
m[4].metric("Total time", f"{result.get('timings', {}).get('total', 0):.0f} s")

if result.get("errors"):
    with st.expander(f"⚠️ {len(result['errors'])} warning(s) / error(s) during the run"):
        for e in result["errors"]:
            st.markdown(f"- {e}")

if report and report.insufficient_evidence:
    st.warning("No sources could be retrieved, so no findings are reported. See the Final Report tab.")

tab1, tab2, tab3, tab4 = st.tabs(["Research Findings", "Model Comparison", "Evaluation", "Final Report"])

with tab1:
    if research and research.search_plan:
        p = research.search_plan
        st.caption(
            f"Search plan — web: {' | '.join(p.web_queries)} · arXiv: {p.arxiv_query} · GitHub: {p.github_query}"
        )
    if not research or not research.findings:
        st.info("No relevant findings.")
    for f in research.findings if research else []:
        with st.expander(f"[{f.source_id}] {f.title}  ·  {f.source_type}  ·  {f.published or 'no date'}"):
            st.markdown(f"**Source:** [{f.source_url}]({f.source_url})")
            st.markdown(f"**Summary:** {f.summary}")
            if f.key_findings:
                st.markdown("**Key findings**\n" + "\n".join(f"- {k}" for k in f.key_findings))
            if f.limitations:
                st.markdown("**Limitations**\n" + "\n".join(f"- {k}" for k in f.limitations))
    if sources:
        st.markdown("##### All retrieved sources")
        link_df([{"ID": s.source_id, "Title": s.title, "Type": s.source_type,
                  "Date": s.published or "—", "URL": s.url} for s in sources])

with tab2:
    if not comparison or not comparison.models:
        st.info("No comparison could be produced from the retrieved evidence.")
    else:
        st.dataframe(
            pd.DataFrame([{
                "Model": c.model_name, "Developer": c.developer, "Modalities": ", ".join(c.modalities),
                "Parameters": c.parameter_sizes, "Context": c.context_window,
                "Deployment": ", ".join(c.deployment_methods), "Hardware": c.hardware_requirements,
                "Licence": c.licence, "Licence type": c.licence_category,
                "Restrictions": c.usage_restrictions, "Sources": ", ".join(c.source_ids),
            } for c in comparison.models]),
            hide_index=True, width="stretch",
        )
        st.caption("Licence type is classified by code from the licence text: OSI-approved open source "
                   "vs. open weights under a custom/restricted licence.")
        st.markdown("##### Important differences")
        st.markdown("\n".join(f"- {d}" for d in comparison.key_differences) or "_None reported._")
        if comparison.dropped_models:
            st.caption(f"Removed (no valid supporting source): {', '.join(comparison.dropped_models)}")

with tab3:
    if evaluation:
        st.info(evaluation.disclaimer)
        st.markdown("##### Reported benchmark results (verified in source text)")
        if evaluation.benchmarks:
            st.dataframe(pd.DataFrame([{
                "Model": b.model_name, "Benchmark": b.benchmark, "Metric": b.metric, "Score": b.score,
                "Reported by": b.reported_by, "Source": b.source_id} for b in evaluation.benchmarks]),
                hide_index=True, width="stretch")
        else:
            st.markdown("_No benchmark scores could be verified._")
        if evaluation.rejected_benchmarks:
            st.caption(f"{len(evaluation.rejected_benchmarks)} score(s) excluded: not found in the cited source text.")
        st.markdown("##### On-premise suitability (qualitative assessment)")
        if evaluation.assessments:
            st.dataframe(pd.DataFrame([{
                "Model": a.model_name, "Suitability": a.onprem_suitability, "Rationale": a.rationale,
                "Memory / inference": a.memory_and_inference, "Quantisation": ", ".join(a.quantisation_options),
                "Limitations": "; ".join(a.limitations), "Sources": ", ".join(a.source_ids)}
                for a in evaluation.assessments]), hide_index=True, width="stretch")
        if evaluation.memory_estimates:
            st.markdown("##### Estimated weight memory (computed, not measured)")
            st.dataframe(pd.DataFrame([{
                "Model": m.model_name, "Parameters": m.parameters, "FP16 (GB)": m.fp16_gb,
                "8-bit (GB)": m.int8_gb, "4-bit (GB)": m.int4_gb, "Source": m.source_id}
                for m in evaluation.memory_estimates]), hide_index=True, width="stretch")
            st.caption(MEMORY_ESTIMATE_BASIS)
        c1, c2 = st.columns(2)
        c1.markdown("##### Trade-offs\n" + ("\n".join(f"- {t}" for t in evaluation.trade_offs) or "_None._"))
        c2.markdown("##### Missing evidence\n" + ("\n".join(f"- {t}" for t in evaluation.missing_evidence) or "_None._"))
    else:
        st.info("Evaluation did not run.")

with tab4:
    if report:
        st.download_button(
            "⬇️ Download report (.md)", report.markdown,
            file_name=f"research_report_{datetime.now():%Y%m%d_%H%M}.md", mime="text/markdown",
        )
        chk = report.citation_check
        st.caption(
            f"Citation check — cited: {len(chk.get('cited', []))}, unknown IDs: {len(chk.get('unknown', []))}, "
            f"invalid citations removed: {len(report.removed_citations)}, "
            f"misattributed sentences removed: {len(report.removed_claims)}"
            + ("" if report.narrative_generated else " · narrative fell back to structured output")
        )
        st.divider()
        st.markdown(report.markdown)
    else:
        st.info("The report was not generated. See the warnings above.")

if result.get("saved"):
    st.caption(f"Saved to: {result['saved'].get('markdown', '')}  ·  {result['saved'].get('json', '')}")
