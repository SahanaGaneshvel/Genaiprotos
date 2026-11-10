// Turns the raw event stream into a readable "behind the scenes" view.
// A step that has a start and an end (e.g. read → read_done) becomes one row that is
// first "in progress" and later "done" with its real result. Live runs and replays use
// exactly the same code.

import type { AgentName, AgentStatus, FlowEvent } from "./types";

export const AGENTS: AgentName[] = ["research", "comparison", "evaluation", "report"];

export type RowKind =
  | "plan" | "search" | "fetch" | "register" | "read"
  | "candidates" | "selected" | "row" | "row_dropped" | "differences"
  | "evaluate" | "verify" | "memory"
  | "narrative" | "attribution" | "assemble";

export interface Row {
  id: string;
  kind: RowKind;
  agent: AgentName;
  open: boolean; // still in progress
  t: number;
  tEnd?: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
}

export interface Stage {
  agent: AgentName;
  status: AgentStatus;
  startedAt?: number;
  seconds?: number;
  rows: Row[];
}

type Key = (d: Record<string, unknown>) => string;

// Steps that open a row, and the key that the matching "done" event will carry.
const OPENERS: Partial<Record<string, { kind: RowKind; key: Key }>> = {
  plan: { kind: "plan", key: () => "plan" },
  search: { kind: "search", key: (d) => `${d.tool}|${d.query}` },
  fetch: { kind: "fetch", key: (d) => String(d.url) },
  read: { kind: "read", key: (d) => String(d.source_id) },
  row: { kind: "row", key: (d) => String(d.model) },
  differences: { kind: "differences", key: () => "differences" },
  evaluate: { kind: "evaluate", key: () => "evaluate" },
  narrative: { kind: "narrative", key: () => "narrative" },
};

// Steps that close an open row. Some (verify, attribution) also add their own row.
const CLOSERS: Partial<Record<string, { opens: RowKind; key: Key; alsoRow?: RowKind }>> = {
  plan_done: { opens: "plan", key: () => "plan" },
  search_done: { opens: "search", key: (d) => `${d.tool}|${d.query}` },
  fetch_done: { opens: "fetch", key: (d) => String(d.url) },
  read_done: { opens: "read", key: (d) => String(d.source_id) },
  row_done: { opens: "row", key: (d) => String(d.model) },
  differences_done: { opens: "differences", key: () => "differences" },
  verify: { opens: "evaluate", key: () => "evaluate", alsoRow: "verify" },
  attribution: { opens: "narrative", key: () => "narrative", alsoRow: "attribution" },
};

const INSTANT = new Set<RowKind>(["register", "candidates", "selected", "row_dropped", "memory", "assemble"]);

export function buildStages(events: FlowEvent[]): Stage[] {
  const stages = new Map<AgentName, Stage>(AGENTS.map((a) => [a, { agent: a, status: "pending", rows: [] }]));
  const openRows = new Map<string, Row>();
  let n = 0;

  for (const ev of events) {
    const stage = stages.get(ev.agent);
    if (!stage) continue;
    if (ev.status) {
      stage.status = ev.status;
      if (ev.status === "running") stage.startedAt = ev.t;
      if (ev.seconds != null) stage.seconds = ev.seconds;
      if (ev.status !== "running") {
        // anything still open when the agent ends is closed as-is
        for (const r of stage.rows) if (r.open) Object.assign(r, { open: false, tEnd: ev.t });
      }
    }
    if (!ev.step) continue;
    const data = ev.data ?? {};

    const closer = CLOSERS[ev.step];
    if (closer) {
      const id = `${ev.agent}:${closer.opens}:${closer.key(data)}`;
      const row = openRows.get(id);
      if (row) {
        Object.assign(row, { open: false, tEnd: ev.t, data: { ...row.data, ...data, message: ev.message } });
        openRows.delete(id);
      }
      if (closer.alsoRow) {
        stage.rows.push({ id: `r${n++}`, kind: closer.alsoRow, agent: ev.agent, open: false, t: ev.t, data: { ...data, message: ev.message } });
      }
      continue;
    }
    const opener = OPENERS[ev.step];
    if (opener) {
      const row: Row = { id: `r${n++}`, kind: opener.kind, agent: ev.agent, open: true, t: ev.t, data: { ...data, message: ev.message } };
      stage.rows.push(row);
      openRows.set(`${ev.agent}:${opener.kind}:${opener.key(data)}`, row);
      continue;
    }
    if (INSTANT.has(ev.step as RowKind)) {
      stage.rows.push({ id: `r${n++}`, kind: ev.step as RowKind, agent: ev.agent, open: false, t: ev.t, data: { ...data, message: ev.message } });
    }
  }
  return AGENTS.map((a) => stages.get(a)!);
}

// ------------------------------------------------------------------ explanations

export type Who = "model" | "code" | "api";

const TOOL_TEXT: Record<string, string> = {
  web: "Free search engines, tried in a fixed order (DuckDuckGo, then Bing, then Brave) until one answers. Which engine answered is recorded.",
  "Hugging Face model cards": "The Hugging Face Hub API. Licence, parameter count and dates come straight from the API, so the model never has to guess them.",
  arXiv: "arXiv's public paper API. Words like “on-premise” or “licence” are removed first; if nothing comes back, the query is shortened once.",
  GitHub: "GitHub's search API, sorted by stars, plus each repository's README. Shortened once if nothing comes back.",
};

export function explain(row: Row): { who: Who; whoLabel?: string; text: string } {
  switch (row.kind) {
    case "plan":
      return { who: "model", text: "The model turns the question into search queries for each kind of source. Code then cleans up anything small models tend to add, like stray brackets or quotes." };
    case "search":
      return { who: "api", whoLabel: `${row.data.tool === "web" ? "Web search" : row.data.tool} API`, text: TOOL_TEXT[row.data.tool] ?? "A public search API." };
    case "fetch":
      return { who: "code", text: "Downloads the page (only if robots.txt allows it), strips menus, scripts and footers, and keeps the readable text." };
    case "register":
      return { who: "code", text: "Duplicate links are removed and every source gets an ID. From here on the model can only refer to sources by these IDs. It never writes a link itself, so it can't invent one." };
    case "read":
      return { who: "model", text: "One call per source. Code first picks the most informative passages of the page; the model then pulls out facts from that text only. Sources with nothing useful are set aside." };
    case "candidates":
      return { who: "code", text: "Every model name the research mentioned, ranked by how many sources talk about it." };
    case "selected":
      return { who: "model", text: "Models that have their own model card or repository are always included by code. The model picks the rest, and any name that isn't in the research is rejected." };
    case "row":
      return { who: "model", text: "The model fills in this model's row using only the evidence about it. Code then fills gaps from the API data, rejects anything that isn't really a licence, and decides whether the licence is truly open source." };
    case "row_dropped":
      return { who: "code", text: "No source actually supports this model, so it isn't shown as evidence." };
    case "differences":
      return { who: "model", text: "Written from the finished table. Code attaches the sources of each model a sentence mentions and drops sentences about models it can't tie to a source." };
    case "evaluate":
      return { who: "model", text: "The model looks for reported benchmark scores, judges how practical each model is to run on your own hardware, and lists what's missing." };
    case "verify":
      return { who: "code", text: "Every score the model reported must appear in the text of the source it cites, both the number and the benchmark name. Anything else is rejected. No benchmark is ever run by this app." };
    case "memory":
      return { who: "code", text: "Memory for the weights = parameters × bytes per parameter (2 at FP16, 1 at 8-bit, 0.5 at 4-bit) × 1.2. An estimate, not a measurement." };
    case "narrative":
      return { who: "model", text: "The model writes the summary, analysis and advice from everything the other agents produced." };
    case "attribution":
      return { who: "code", text: "Each sentence that names a model must cite sources that actually mention that model. Sentences that don't are removed." };
    case "assemble":
      return { who: "code", text: "The ten sections, tables and reference list are built from the data. Every citation is checked against the list of sources that were really retrieved." };
  }
}

// ------------------------------------------------------------------ formatting

export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  return s % 60 ? `${m} min ${s % 60} s` : `${m} min`;
}

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
