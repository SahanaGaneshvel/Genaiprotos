// Single source of truth describing the pipeline, step by step.
// Mirrors the Python code — file references are given so every claim can be checked.
// Used by the About page, the Architecture diagram and the dashboard agent cards.

import type { AgentName } from "./types";

/** Who executes a step: the local LLM, deterministic code, or an external public API. */
export type Executor =
  | { kind: "llm"; schema: string; maxTokens: number }
  | { kind: "code" }
  | { kind: "api"; service: string };

export interface Step {
  title: string;
  executor: Executor;
  detail: string;
  guard?: string; // the anti-fabrication / robustness rule applied in this step
}

export interface Stage {
  id: "orchestrator" | AgentName | "router";
  name: string;
  tagline: string;
  file: string;
  reads: string[];
  writes: string[];
  steps: Step[];
}

/** Generation settings shared by every LLM call (config.py + services/ollama_client.py). */
export const LLM_SETTINGS = [
  { label: "Runtime", value: "Ollama (local REST API, port 11434)" },
  { label: "Temperature", value: "0.1 — conservative, factual" },
  { label: "Context window", value: "8,192 tokens (num_ctx)" },
  { label: "Thinking mode", value: "off (think: false) — much faster on CPU" },
  { label: "Output format", value: "JSON constrained by a Pydantic JSON schema" },
  { label: "Validation", value: "Pydantic, 1 bounded retry with the error shown to the model" },
  { label: "Cloud models", value: "refused (*-cloud tags) — inference never leaves the machine" },
];

export const STAGES: Stage[] = [
  {
    id: "orchestrator",
    name: "Orchestrator",
    tagline: "Validates the request and checks the local model before any agent runs.",
    file: "orchestration/workflow.py · orchestrator_node",
    reads: ["topic", "depth"],
    writes: ["topic (normalised)", "abort_reason"],
    steps: [
      {
        title: "Validate the topic",
        executor: { kind: "code" },
        detail: "10–1,000 characters, must contain real words; whitespace normalised.",
        guard: "Invalid topics stop here with a readable message.",
      },
      {
        title: "Health-check the local LLM",
        executor: { kind: "api", service: "Ollama /api/tags" },
        detail: "Ollama must be running and the configured model must be pulled.",
        guard: "Missing model → exact `ollama pull …` command shown; cloud models refused.",
      },
      {
        title: "Route",
        executor: { kind: "code" },
        detail: "LangGraph conditional edge: abort → END, otherwise → Research Agent.",
      },
    ],
  },
  {
    id: "research",
    name: "Research Agent",
    tagline: "Turns a topic into real, citable evidence from four kinds of sources.",
    file: "agents/research_agent.py",
    reads: ["topic", "depth"],
    writes: ["sources (citation registry S1…Sn)", "research.findings", "research.models_identified"],
    steps: [
      {
        title: "Plan the searches",
        executor: { kind: "llm", schema: "SearchPlan", maxTokens: 400 },
        detail: "Writes web queries, arXiv and GitHub keywords, a Hugging Face task category and focus points.",
        guard: "Bad JSON twice → keyword fallback plan built by code; the run continues.",
      },
      {
        title: "Clean & guard the plan",
        executor: { kind: "code" },
        detail: "Strips brackets, quotes and AND/OR that small models add; multimodal topics force the Hub task image-text-to-text.",
      },
      {
        title: "Web search",
        executor: { kind: "api", service: "DuckDuckGo → Bing → Brave → auto (ddgs)" },
        detail: "Fixed fallback chain of free engines, 1 s apart; records which engine answered.",
        guard: "Empty or rate-limited results are recorded, never fatal, never cached.",
      },
      {
        title: "Official model cards",
        executor: { kind: "api", service: "Hugging Face Hub API" },
        detail: "Trending models for the task; skips GGUF/AWQ re-uploads; reads licence, parameter count, dates and the model card README.",
      },
      {
        title: "Academic papers",
        executor: { kind: "api", service: "arXiv Atom API" },
        detail: "Generic words (on-premise, licence, benchmark…) removed; relaxed to 2 keywords if empty — at most 2 attempts.",
      },
      {
        title: "Code repositories",
        executor: { kind: "api", service: "GitHub REST API" },
        detail: "Repositories sorted by stars + their README; licence from the API; optional GITHUB_TOKEN.",
      },
      {
        title: "Fetch & clean pages",
        executor: { kind: "code" },
        detail: "Requests + BeautifulSoup; robots.txt respected; scripts, menus and footers removed; ≤ 12,000 characters; 24 h JSON cache.",
      },
      {
        title: "Register sources",
        executor: { kind: "code" },
        detail: "De-duplicates URLs (including arXiv v1/v2) and assigns citation IDs S1…Sn.",
        guard: "From here on the LLM can only refer to sources by ID — it never writes a URL.",
      },
      {
        title: "Pick the best passages",
        executor: { kind: "code" },
        detail: "Scores 500-character chunks by topic keywords + evidence signals (numbers, licences, VRAM, benchmarks); keeps 1,500 (Basic) or 2,500 (Detailed) characters.",
      },
      {
        title: "Extract findings — one call per source",
        executor: { kind: "llm", schema: "FindingExtraction", maxTokens: 600 },
        detail: "Summary, key facts, limitations and models mentioned, from that source's text only.",
        guard: "If extraction fails the original snippet is kept and labelled — nothing is invented.",
      },
    ],
  },
  {
    id: "router",
    name: "Evidence router",
    tagline: "Stops the run honestly when there is nothing to analyse.",
    file: "orchestration/workflow.py · route_after_research",
    reads: ["sources", "research.findings", "agent_status"],
    writes: ["report (insufficient-evidence mode)"],
    steps: [
      {
        title: "Decide the next step",
        executor: { kind: "code" },
        detail: "Research failed → END. No sources or no relevant findings → insufficient-evidence report (no LLM, no claims). Otherwise → Comparison.",
        guard: "A run whose retrieval failed can never produce a confident report.",
      },
    ],
  },
  {
    id: "comparison",
    name: "Comparison Agent",
    tagline: "Builds the model-by-model table: modalities, size, context, hardware, licence.",
    file: "agents/comparison_agent.py",
    reads: ["research.findings", "sources"],
    writes: ["comparison.models", "comparison.key_differences"],
    steps: [
      {
        title: "Rank candidate models",
        executor: { kind: "code" },
        detail: "Counts the findings that mention each name; a model's own model card or repository adds a bonus.",
      },
      {
        title: "Select models",
        executor: { kind: "llm", schema: "ModelSelection", maxTokens: 300 },
        detail: "Models with their own card/repo are always included by code; the LLM fills the remaining slots (4 Basic / 6 Detailed).",
        guard: "Any name that is not in the research is rejected.",
      },
      {
        title: "Gather evidence per model",
        executor: { kind: "code" },
        detail: "Collects only the finding lines about that model (version-aware: “K3” ≠ “K3.1”), plus API metadata from its own card.",
        guard: "The supporting source IDs are set by code, not chosen by the LLM.",
      },
      {
        title: "Fill one row — one call per model",
        executor: { kind: "llm", schema: "ComparisonRowLLM", maxTokens: 500 },
        detail: "Developer, modalities, parameters, context window, deployment, hardware, licence, restrictions.",
        guard: "Empty / “N/A” answers become “Not documented in retrieved sources”.",
      },
      {
        title: "Enrich & classify",
        executor: { kind: "code" },
        detail: "Fills undocumented licence/parameters from Hugging Face or GitHub metadata (labelled); rejects non-licences such as prices; classifies OSI open source vs open weights vs unknown.",
      },
      {
        title: "Explain the differences",
        executor: { kind: "llm", schema: "DifferencesLLM", maxTokens: 600 },
        detail: "3–5 sentences written from the finished table.",
        guard: "Code attaches the citations of the models each sentence names; sentences about no known model are dropped.",
      },
    ],
  },
  {
    id: "evaluation",
    name: "Evaluation Agent",
    tagline: "Judges the evidence: benchmarks, on-prem suitability, memory and missing data.",
    file: "agents/evaluation_agent.py",
    reads: ["research.findings", "sources"],
    writes: ["evaluation.benchmarks", "evaluation.assessments", "evaluation.memory_estimates", "evaluation.missing_evidence"],
    steps: [
      {
        title: "Group evidence by model",
        executor: { kind: "code" },
        detail: "Same per-model evidence builder as the Comparison Agent (utils/evidence.py).",
      },
      {
        title: "Evaluate",
        executor: { kind: "llm", schema: "EvaluationLLMOutput", maxTokens: 2000 },
        detail: "Reported benchmark scores, on-prem suitability (qualitative), quantisation, trade-offs, missing evidence.",
      },
      {
        title: "Verify every benchmark score",
        executor: { kind: "code" },
        detail: "The number AND the benchmark name must appear in the cited source's retrieved text.",
        guard: "Unverifiable scores are excluded and counted. The app never runs benchmarks itself and says so.",
      },
      {
        title: "Downgrade unsupported verdicts",
        executor: { kind: "code" },
        detail: "An assessment with no valid source becomes “insufficient evidence”.",
      },
      {
        title: "Estimate weight memory",
        executor: { kind: "code" },
        detail: "Parameters (from the Hugging Face API) × bytes per parameter (FP16 2 · 8-bit 1 · 4-bit 0.5) × 1.2 overhead — labelled Estimate.",
      },
    ],
  },
  {
    id: "report",
    name: "Report Agent",
    tagline: "Consolidates everything into a 10-section, fully cited Markdown report.",
    file: "agents/report_agent.py",
    reads: ["research", "comparison", "evaluation", "sources"],
    writes: ["report.markdown", "report.citation_check", "outputs/*.md + *.json"],
    steps: [
      {
        title: "Write the narrative",
        executor: { kind: "llm", schema: "ReportNarrative", maxTokens: 2500 },
        detail: "Executive summary, comparative analysis, benchmark discussion, deployment notes, risks, recommendations.",
      },
      {
        title: "Attribution check",
        executor: { kind: "code" },
        detail: "A sentence that names a model must cite sources that actually mention that model.",
        guard: "Misattributed sentences are removed and counted in the report.",
      },
      {
        title: "Assemble 10 sections",
        executor: { kind: "code" },
        detail: "Methodology from real run statistics; comparison, benchmark, deployment and memory tables; rule-based recommendations from licence + memory.",
      },
      {
        title: "Citations & references",
        executor: { kind: "code" },
        detail: "Unknown [S#] stripped; References built from the registry (real URLs only); consistency audit.",
        guard: "Every URL in the report was actually retrieved.",
      },
      {
        title: "Save",
        executor: { kind: "code" },
        detail: "outputs/report_<timestamp>.md and run_<timestamp>.json (the full structured state).",
      },
    ],
  },
];

export const AGENT_STAGES = STAGES.filter((s): s is Stage & { id: AgentName } =>
  ["research", "comparison", "evaluation", "report"].includes(s.id),
);

export function llmCallCount(stage: Stage): number {
  return stage.steps.filter((s) => s.executor.kind === "llm").length;
}

/** The anti-fabrication guards, in plain words (About page). */
export const GUARDS = [
  { title: "Citation registry", text: "Sources are created by code from real API responses. The model only ever writes IDs like [S3]." },
  { title: "Invalid citations removed", text: "Any [S#] that is not in the registry is stripped before the report is written." },
  { title: "References built by code", text: "Every URL in the report was actually retrieved — the model never writes one." },
  { title: "Benchmark verification", text: "A score survives only if the number and benchmark name appear in the cited source." },
  { title: "Attribution check", text: "A sentence that names a model must cite sources that mention that model." },
  { title: "Code-set citations", text: "Which sources support a comparison row is decided by code, not by the model." },
  { title: "Facts from APIs", text: "Licences and parameter counts come from Hugging Face / GitHub metadata, labelled." },
  { title: "Rule-based advice", text: "Recommendations computed from licence category and memory estimates, with citations." },
  { title: "Honest failure", text: "No relevant sources → an insufficient-evidence report with no claims. Failed steps are shown." },
];
