// TypeScript mirrors of the Python Pydantic schemas (schemas/*.py).
// The API sends the LangGraph state as JSON; these types describe that JSON.

export type AgentName = "research" | "comparison" | "evaluation" | "report";
export type AgentStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type SourceType = "web" | "documentation" | "arxiv" | "github";

export interface Source {
  source_id: string;
  title: string;
  url: string;
  source_type: SourceType;
  published: string | null;
  snippet: string;
  content: string;
  metadata: Record<string, unknown>;
}

export interface SearchPlan {
  web_queries: string[];
  arxiv_query: string;
  github_query: string;
  hub_task: string;
  focus_points: string[];
}

export interface Finding {
  source_id: string;
  title: string;
  summary: string;
  source_url: string;
  source_type: SourceType;
  published: string | null;
  key_findings: string[];
  limitations: string[];
  models_mentioned: string[];
}

export interface ResearchOutput {
  findings: Finding[];
  models_identified: string[];
  search_plan: SearchPlan | null;
  retrieval_errors: string[];
}

export interface ModelRow {
  model_name: string;
  developer: string;
  modalities: string[];
  parameter_sizes: string;
  context_window: string;
  deployment_methods: string[];
  hardware_requirements: string;
  licence: string;
  usage_restrictions: string;
  source_ids: string[];
  licence_category: string;
}

export interface ComparisonOutput {
  models: ModelRow[];
  key_differences: string[];
  dropped_models: string[];
  warnings?: string[];
}

export interface Benchmark {
  model_name: string;
  benchmark: string;
  metric: string;
  score: string;
  source_id: string;
  reported_by: string;
  verified_in_source: boolean;
}

export interface Assessment {
  model_name: string;
  onprem_suitability: string;
  rationale: string;
  memory_and_inference: string;
  quantisation_options: string[];
  limitations: string[];
  source_ids: string[];
}

export interface MemoryEstimate {
  model_name: string;
  parameters: string;
  source_id: string;
  fp16_gb: number;
  int8_gb: number;
  int4_gb: number;
}

export interface EvaluationOutput {
  benchmarks: Benchmark[];
  rejected_benchmarks: Benchmark[];
  assessments: Assessment[];
  memory_estimates?: MemoryEstimate[];
  trade_offs: string[];
  missing_evidence: string[];
  recommendations: string[];
  disclaimer: string;
}

export interface ReportOutput {
  markdown: string;
  narrative_generated: boolean;
  removed_citations: string[];
  removed_claims?: string[];
  citation_check: { cited?: string[]; unknown?: string[]; uncited?: string[] };
  insufficient_evidence: boolean;
}

export interface RunState {
  topic: string;
  depth: string;
  model_name: string;
  abort_reason?: string;
  sources?: Source[];
  research?: ResearchOutput;
  comparison?: ComparisonOutput;
  evaluation?: EvaluationOutput;
  report?: ReportOutput;
  agent_status: Partial<Record<AgentName, AgentStatus>>;
  timings: Partial<Record<AgentName | "total", number>>;
  errors: string[];
  execution_order: string[];
  saved?: Record<string, string>;
}

export interface Health {
  ok: boolean;
  message: string;
  model: string;
}

/** One live event from the workflow (orchestration/workflow.py `_emit`). */
export interface AgentEvent {
  agent: AgentName;
  status?: AgentStatus;
  message?: string;
  seconds?: number;
}
