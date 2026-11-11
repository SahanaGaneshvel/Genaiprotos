// Turns the run's events into plain-language state for each box of the flow diagram,
// plus the "What's happening now" sentences. No technical terms on purpose.

import { domain, duration, type Row, type Stage } from "./flow";
import type { AgentName } from "./types";

export type NodeId =
  | "question" | "check" | "web" | "cards" | "papers" | "code"
  | "research" | "compare" | "evaluate" | "write" | "report" | "model";

export const NODE_IDS: NodeId[] = [
  "question", "check", "web", "cards", "papers", "code", "research", "compare", "evaluate", "write", "report", "model",
];

export type NodeStatus = "waiting" | "working" | "done" | "skipped" | "failed";

export interface NodeState {
  status: NodeStatus;
  line: string; // one short status line shown inside the box
}

export const SOURCE_NODES = ["web", "cards", "papers", "code"] as const;
export type SourceNode = (typeof SOURCE_NODES)[number];

const TOOL_TO_NODE: Record<string, SourceNode> = {
  web: "web",
  "Hugging Face model cards": "cards",
  arXiv: "papers",
  GitHub: "code",
};

export const SOURCE_PLAIN: Record<SourceNode, string> = {
  web: "the web",
  cards: "Hugging Face model cards",
  papers: "arXiv papers",
  code: "GitHub",
};

const AGENT_NODE: Record<AgentName, NodeId> = {
  research: "research",
  comparison: "compare",
  evaluation: "evaluate",
  report: "write",
};

// Steps where the local AI model is doing the work (everything else is plain code or a search).
const MODEL_STEPS = new Set(["plan", "read", "row", "differences", "evaluate", "narrative"]);

export const stripCitations = (s: string) => s.replace(/\s*\[S\d+\]/g, "");
const short = (name: string) => name.split("/").at(-1) ?? name;

export interface Layers {
  nodes: Record<NodeId, NodeState>;
  modelBusyFor: NodeId | null; // which agent is using the AI model right now
  now: { title: string; lines: string[] };
  // produced data, for the details card
  sources: { id: string; title: string; url: string }[];
  results: Record<SourceNode, { query: string; items: { title: string; url: string }[] }[]>;
  reads: { id: string; title: string; kept: boolean; facts: string[] }[];
  rows: { model: string; size: string; licence: string; open: boolean }[];
  differences: string[];
  checks: { proposed: number; confirmed: number };
  memory: { model: string; gb: number }[];
  removed: string[];
  sections: number;
}

function stageRows(stages: Stage[], agent: AgentName): Row[] {
  return stages.find((s) => s.agent === agent)?.rows ?? [];
}

function notDocumented(v: unknown): boolean {
  const s = typeof v === "string" ? v.trim().replace(/^\[(.*)\]$/, "$1") : "";
  return !s || /^(not (explicitly |clearly )?(documented|specified|stated|mentioned|provided|available|given)|unknown)/i.test(s);
}

export function buildLayers(
  stages: Stage[],
  opts: { started: boolean; finished: boolean; failed: string | null; totalSeconds: number },
): Layers {
  const st = (a: AgentName) => stages.find((s) => s.agent === a)!;
  const research = stageRows(stages, "research");
  const compare = stageRows(stages, "comparison");
  const evaluate = stageRows(stages, "evaluation");
  const write = stageRows(stages, "report");

  // ---------------------------------------------------------------- data produced so far
  const results = { web: [], cards: [], papers: [], code: [] } as Layers["results"];
  const searchState: Partial<Record<SourceNode, { open: boolean; count: number }>> = {};
  for (const r of research.filter((r) => r.kind === "search")) {
    const node = TOOL_TO_NODE[r.data.tool];
    if (!node) continue;
    const items = (r.data.results ?? []) as { title: string; url: string }[];
    if (!r.open) results[node].push({ query: r.data.query, items });
    searchState[node] = { open: r.open, count: r.open ? searchState[node]?.count ?? 0 : items.length || searchState[node]?.count || 0 };
  }
  const register = research.find((r) => r.kind === "register");
  const sources = ((register?.data.sources ?? []) as { id: string; title: string; url: string }[]);
  const readRows = research.filter((r) => r.kind === "read");
  const reads = readRows.filter((r) => !r.open).map((r) => ({
    id: r.data.source_id, title: r.data.title, kept: !!r.data.kept, facts: (r.data.facts ?? []) as string[],
  }));
  const kept = reads.filter((r) => r.kept).length;

  const rows = compare.filter((r) => r.kind === "row").map((r) => ({
    model: r.data.model as string,
    size: notDocumented(r.data.parameters) ? "not stated" : String(r.data.parameters).replace(/^\[(.*)\]$/, "$1"),
    licence: notDocumented(r.data.licence) ? "not stated" : `${r.data.licence}`,
    open: r.open,
  }));
  const differences = ((compare.find((r) => r.kind === "differences" && !r.open)?.data.sentences ?? []) as string[]).map(stripCitations);
  const verify = evaluate.find((r) => r.kind === "verify");
  const memoryRow = evaluate.find((r) => r.kind === "memory");
  const memory = ((memoryRow?.data.estimates ?? []) as { model: string; int4_gb: number }[]).map((e) => ({ model: short(e.model), gb: e.int4_gb }));
  const attribution = write.find((r) => r.kind === "attribution");
  const assemble = write.find((r) => r.kind === "assemble");

  // ---------------------------------------------------------------- box states
  const stageStatus = (a: AgentName): NodeStatus => {
    const s = st(a).status;
    return s === "running" ? "working" : s === "completed" ? "done" : s === "failed" ? "failed" : s === "skipped" ? "skipped" : "waiting";
  };
  const openIn = (rs: Row[]) => [...rs].reverse().find((r) => r.open);

  const nodes = {} as Record<NodeId, NodeState>;
  nodes.question = { status: opts.started ? "done" : "waiting", line: "your question" };
  const researchStarted = st("research").status !== "pending";
  if (opts.failed && !researchStarted) nodes.check = { status: "failed", line: "not ready" };
  else if (researchStarted) nodes.check = { status: "done", line: "ready" };
  else if (opts.started) nodes.check = { status: "working", line: "checking" };
  else nodes.check = { status: "waiting", line: "waiting" };

  for (const n of SOURCE_NODES) {
    const s = searchState[n];
    nodes[n] = !s
      ? { status: "waiting", line: "waiting" }
      : s.open
        ? { status: "working", line: "searching" }
        : { status: "done", line: s.count ? `${s.count} found` : "none found" };
  }

  // Research
  const rOpen = openIn(research);
  const rStatus = stageStatus("research");
  let rLine = rStatus === "waiting" ? "waiting" : "";
  if (rStatus === "working") {
    if (!rOpen || rOpen.kind === "plan") rLine = "planning searches";
    else if (rOpen.kind === "search") rLine = "searching";
    else if (rOpen.kind === "fetch") rLine = "opening pages";
    else if (rOpen.kind === "read") rLine = `reading ${readRows.length} of ${sources.length || "?"}`;
  } else if (rStatus === "done") rLine = `${kept} of ${sources.length} kept`;
  else if (rStatus === "failed") rLine = "failed";
  nodes.research = { status: rStatus, line: rLine };

  // Compare
  const cOpen = openIn(compare);
  const cStatus = stageStatus("comparison");
  const doneRows = rows.filter((r) => !r.open).length;
  nodes.compare = {
    status: cStatus,
    line: cStatus === "working"
      ? cOpen?.kind === "row" ? `model ${rows.length} of ${(compare.find((r) => r.kind === "selected")?.data.models ?? []).length || "?"}`
        : cOpen?.kind === "differences" ? "summing up" : "choosing models"
      : cStatus === "done" ? `${doneRows} models` : cStatus === "skipped" ? "skipped" : cStatus === "failed" ? "failed" : "waiting",
  };

  // Evaluate
  const eStatus = stageStatus("evaluation");
  nodes.evaluate = {
    status: eStatus,
    line: eStatus === "working" ? "checking evidence" : eStatus === "done" ? "evidence checked" : eStatus === "skipped" ? "skipped" : eStatus === "failed" ? "failed" : "waiting",
  };

  // Write
  const wStatus = stageStatus("report");
  nodes.write = {
    status: wStatus,
    line: wStatus === "working" ? (attribution ? "checking sentences" : "writing") : wStatus === "done" ? `${assemble?.data.sections ?? 10} sections` : wStatus === "failed" ? "failed" : "waiting",
  };
  nodes.report = { status: opts.finished && wStatus === "done" ? "done" : "waiting", line: opts.finished && wStatus === "done" ? "ready" : "waiting" };

  // Is the AI model in use, and by whom?
  let modelBusyFor: NodeId | null = null;
  for (const a of ["research", "comparison", "evaluation", "report"] as AgentName[]) {
    const open = openIn(stageRows(stages, a));
    if (st(a).status === "running" && open && MODEL_STEPS.has(open.kind)) modelBusyFor = AGENT_NODE[a];
    if (st(a).status === "running" && !open && a === "research") modelBusyFor = "research"; // planning starts immediately
  }
  nodes.model = { status: modelBusyFor ? "working" : opts.started ? "done" : "waiting", line: modelBusyFor ? "thinking" : "idle" };

  // ---------------------------------------------------------------- "What's happening now"
  let now: Layers["now"];
  if (opts.failed) now = { title: "The run stopped", lines: [opts.failed] };
  else if (!opts.started) now = { title: "Ready", lines: ["Press start to watch the four agents work through the question, step by step."] };
  else if (opts.finished) {
    now = {
      title: `All done in ${duration(opts.totalSeconds)}`,
      lines: [
        `${sources.length} sources found, ${kept} kept, ${doneRows} models compared.`,
        attribution?.data.removed?.length
          ? `${attribution.data.removed.length} sentences were removed for crediting the wrong source.`
          : "Every sentence in the report was checked against its sources.",
        "The report is ready below.",
      ],
    };
  } else if (rStatus === "working") {
    const lines: string[] = [];
    if (!rOpen || rOpen.kind === "plan") lines.push("The AI model is turning your question into search queries.");
    else if (rOpen.kind === "search") {
      const node = TOOL_TO_NODE[rOpen.data.tool];
      lines.push(`Searching ${node ? SOURCE_PLAIN[node] : "the web"} for “${rOpen.data.query}”.`);
    } else if (rOpen.kind === "fetch") lines.push(`Opening ${domain(rOpen.data.url)} to read the full page.`);
    else if (rOpen.kind === "read") {
      lines.push(`Reading source ${readRows.length} of ${sources.length}: “${rOpen.data.title}”.`);
      lines.push("Only facts that are actually in the text are kept.");
    }
    if (sources.length) lines.push(`So far: ${sources.length} sources found, ${kept} kept.`);
    now = { title: "Research", lines };
  } else if (cStatus === "working") {
    now = {
      title: "Compare",
      lines: cOpen?.kind === "row"
        ? [`Filling in ${short(cOpen.data.model)}, using only what the sources say about it.`, `${doneRows} of ${rows.length > doneRows ? rows.length : doneRows} models done.`]
        : cOpen?.kind === "differences" ? ["Writing down how the models differ."] : ["Choosing which models are worth comparing."],
    };
  } else if (eStatus === "working") {
    now = { title: "Evaluate", lines: ["Checking every number against the source it came from.", "Estimating how much memory each model needs."] };
  } else if (wStatus === "working") {
    now = {
      title: "Write",
      lines: attribution
        ? ["Removing any sentence that credits a source that never said it.", "Putting the report together."]
        : ["Writing the report from everything the other agents found."],
    };
  } else now = { title: "Getting ready", lines: ["Checking the question and the local AI model."] };

  return {
    nodes, modelBusyFor, now, sources, results, reads, rows, differences,
    checks: { proposed: verify?.data.proposed ?? 0, confirmed: (verify?.data.verified ?? []).length },
    memory, removed: (attribution?.data.removed ?? []).map(stripCitations), sections: assemble?.data.sections ?? 0,
  };
}
