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
