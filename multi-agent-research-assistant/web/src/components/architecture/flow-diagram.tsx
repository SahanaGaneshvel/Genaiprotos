"use client";

import { motion, useReducedMotion } from "motion/react";

import type { AgentName } from "@/lib/types";
import { useRun } from "../run-provider";

export type NodeId =
  | "user" | "orchestrator" | "web" | "hf" | "arxiv" | "github" | "research"
  | "router" | "insufficient" | "comparison" | "evaluation" | "report" | "outputs" | "ollama";

interface NodeDef {
  id: NodeId;
  x: number; y: number; w: number; h: number;
  title: string;
  sub: string;
  kind: "agent" | "code" | "api" | "llm" | "io";
}

const NODES: NodeDef[] = [
  { id: "user", x: 20, y: 262, w: 130, h: 66, title: "User topic", sub: "topic + depth", kind: "io" },
  { id: "orchestrator", x: 190, y: 262, w: 150, h: 66, title: "Orchestrator", sub: "validate · health check", kind: "code" },
  { id: "web", x: 250, y: 56, w: 120, h: 46, title: "Web search", sub: "DDG → Bing → Brave", kind: "api" },
  { id: "hf", x: 382, y: 56, w: 120, h: 46, title: "Hugging Face", sub: "model cards API", kind: "api" },
  { id: "arxiv", x: 514, y: 56, w: 110, h: 46, title: "arXiv", sub: "papers API", kind: "api" },
  { id: "github", x: 636, y: 56, w: 110, h: 46, title: "GitHub", sub: "repos + README", kind: "api" },
  { id: "research", x: 380, y: 262, w: 160, h: 66, title: "Research Agent", sub: "plan · fetch · extract", kind: "agent" },
  { id: "router", x: 580, y: 262, w: 150, h: 66, title: "Shared state", sub: "registry · router", kind: "code" },
  { id: "insufficient", x: 580, y: 440, w: 150, h: 58, title: "Insufficient evidence", sub: "honest stop · no LLM", kind: "code" },
  { id: "comparison", x: 775, y: 168, w: 155, h: 66, title: "Comparison Agent", sub: "one row per model", kind: "agent" },
  { id: "evaluation", x: 775, y: 356, w: 155, h: 66, title: "Evaluation Agent", sub: "verify · estimate", kind: "agent" },
  { id: "report", x: 965, y: 262, w: 140, h: 66, title: "Report Agent", sub: "10 cited sections", kind: "agent" },
  { id: "outputs", x: 965, y: 440, w: 140, h: 58, title: "Outputs", sub: "report.md · run.json", kind: "io" },
  { id: "ollama", x: 390, y: 556, w: 330, h: 54, title: "Ollama · local LLM", sub: "", kind: "llm" },
];

const byId = Object.fromEntries(NODES.map((n) => [n.id, n])) as Record<NodeId, NodeDef>;

const right = (n: NodeDef) => [n.x + n.w, n.y + n.h / 2] as const;
const left = (n: NodeDef) => [n.x, n.y + n.h / 2] as const;
const top = (n: NodeDef) => [n.x + n.w / 2, n.y] as const;
const bottom = (n: NodeDef) => [n.x + n.w / 2, n.y + n.h] as const;

function curve([x1, y1]: readonly [number, number], [x2, y2]: readonly [number, number], vertical = false) {
  if (vertical) {
    const dy = (y2 - y1) / 2;
    return `M ${x1} ${y1} C ${x1} ${y1 + dy}, ${x2} ${y2 - dy}, ${x2} ${y2}`;
  }
  const dx = Math.max(30, (x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

interface EdgeDef { id: string; d: string; to: NodeId; style: "main" | "dashed" | "llm" | "tool"; label?: string }

const r = byId;
const EDGES: EdgeDef[] = [
  { id: "u-o", d: curve(right(r.user), left(r.orchestrator)), to: "orchestrator", style: "main" },
  { id: "o-r", d: curve(right(r.orchestrator), left(r.research)), to: "research", style: "main" },
  ...(["web", "hf", "arxiv", "github"] as const).map((t) => ({
    id: `${t}-r`, d: curve(bottom(r[t]), top(r.research), true), to: "research" as NodeId, style: "tool" as const,
  })),
  { id: "r-s", d: curve(right(r.research), left(r.router)), to: "router", style: "main" },
  { id: "s-c", d: curve(right(r.router), left(r.comparison)), to: "comparison", style: "main" },
  { id: "s-e", d: curve(right(r.router), left(r.evaluation)), to: "evaluation", style: "main" },
  { id: "s-i", d: curve(bottom(r.router), top(r.insufficient), true), to: "insufficient", style: "dashed", label: "0 relevant sources" },
  { id: "c-e", d: curve(bottom(r.comparison), top(r.evaluation), true), to: "evaluation", style: "dashed", label: "then" },
  { id: "c-rp", d: curve(right(r.comparison), left(r.report)), to: "report", style: "main" },
  { id: "e-rp", d: curve(right(r.evaluation), left(r.report)), to: "report", style: "main" },
  { id: "rp-out", d: curve(bottom(r.report), top(r.outputs), true), to: "outputs", style: "main" },
  ...(["research", "comparison", "evaluation", "report"] as const).map((a) => ({
    id: `llm-${a}`, d: curve(top(r.ollama), bottom(r[a]), true), to: a as NodeId, style: "llm" as const,
  })),
];

const KIND_STYLE = {
  agent: { fill: "rgba(99,102,241,0.14)", stroke: "rgba(129,140,248,0.55)", text: "#e0e7ff" },
  code: { fill: "rgba(16,185,129,0.10)", stroke: "rgba(52,211,153,0.45)", text: "#d1fae5" },
  api: { fill: "rgba(245,158,11,0.10)", stroke: "rgba(251,191,36,0.45)", text: "#fef3c7" },
  llm: { fill: "rgba(139,92,246,0.16)", stroke: "rgba(167,139,250,0.6)", text: "#ede9fe" },
  io: { fill: "rgba(148,163,184,0.08)", stroke: "rgba(148,163,184,0.35)", text: "#e2e8f0" },
} as const;

const AGENT_IDS: AgentName[] = ["research", "comparison", "evaluation", "report"];

export function FlowDiagram({ selected, onSelect }: { selected: NodeId; onSelect: (id: NodeId) => void }) {
  const reduce = useReducedMotion();
  const { agents, health, phase } = useRun();
  const model = health?.model && health.model !== "unknown" ? health.model : "qwen3.5";
  const liveAgent = AGENT_IDS.find((a) => agents[a].status === "running");

  const edgeColor = (e: EdgeDef) =>
    e.style === "llm" ? "#a78bfa" : e.style === "tool" ? "#fbbf24" : e.style === "dashed" ? "#94a3b8" : "#67e8f9";

  return (
    <div className="card relative overflow-x-auto p-3 scroll-thin">
      <svg viewBox="0 0 1125 630" className="h-auto w-full min-w-[860px]" role="img" aria-label="Architecture flow diagram">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#64748b" />
          </marker>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* lane labels */}
        <text x="250" y="36" className="fill-amber-200/60 text-[11px] tracking-[0.15em]">EXTERNAL PUBLIC SOURCES</text>
        <text x="390" y="546" className="fill-violet-200/60 text-[11px] tracking-[0.15em]">LOCAL INFERENCE — NEVER LEAVES THE MACHINE</text>

        {/* edges */}
        {EDGES.map((e, i) => {
          const live = liveAgent && e.to === liveAgent;
          const color = edgeColor(e);
          return (
            <g key={e.id}>
              <path d={e.d} fill="none" stroke={color} strokeOpacity={0.18} strokeWidth={2}
                strokeDasharray={e.style === "main" ? undefined : "4 6"} markerEnd={e.style === "llm" ? undefined : "url(#arrow)"} />
              <path d={e.d} fill="none" stroke={color} strokeWidth={live ? 2.5 : 1.6}
                strokeOpacity={live ? 0.95 : e.style === "llm" ? 0.35 : 0.55}
                className={reduce ? "" : "flow-dash"} />
              {!reduce && (e.style === "main" || e.style === "tool" || live) && (
                <circle r={live ? 4 : 3} fill={color} filter="url(#glow)" opacity={live ? 1 : 0.8}>
                  <animateMotion dur={`${live ? 1.2 : 2.6 + (i % 4) * 0.4}s`} repeatCount="indefinite" path={e.d} begin={`${(i % 5) * 0.45}s`} />
                </circle>
              )}
              {e.label && (() => {
                const m = e.d.match(/M ([\d.]+) ([\d.]+).* ([\d.]+) ([\d.]+)$/);
                if (!m) return null;
                const [x, y] = [(+m[1] + +m[3]) / 2, (+m[2] + +m[4]) / 2];
                return <text x={x + 8} y={y} className="fill-slate-400 text-[10px]">{e.label}</text>;
              })()}
            </g>
          );
        })}

        {/* nodes */}
        {NODES.map((n, i) => {
          const s = KIND_STYLE[n.kind];
          const isSel = selected === n.id;
          const isLive = liveAgent === n.id;
          const status = (AGENT_IDS as string[]).includes(n.id) ? agents[n.id as AgentName].status : null;
          return (
            <motion.g
              key={n.id}
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i, duration: 0.45 }}
              onClick={() => onSelect(n.id)}
              className="cursor-pointer"
              role="button"
              aria-label={`${n.title}: show details`}
              tabIndex={0}
              onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && onSelect(n.id)}
            >
              {isLive && !reduce && (
                <motion.rect x={n.x - 5} y={n.y - 5} width={n.w + 10} height={n.h + 10} rx={16} fill="none" stroke="#818cf8" strokeWidth={2}
                  animate={{ opacity: [0.2, 0.9, 0.2] }} transition={{ duration: 1.6, repeat: Infinity }} />
              )}
              <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={12} fill={s.fill}
                stroke={isSel ? "#e0e7ff" : s.stroke} strokeWidth={isSel ? 2.2 : 1.2} />
              <text x={n.x + n.w / 2} y={n.y + (n.id === "ollama" ? 24 : n.h / 2 - 3)} textAnchor="middle" fill={s.text} className="text-[13px] font-semibold">
                {n.title}
              </text>
              <text x={n.x + n.w / 2} y={n.y + (n.id === "ollama" ? 42 : n.h / 2 + 14)} textAnchor="middle" className="fill-slate-400 text-[10.5px]">
                {n.id === "ollama" ? `${model} · temp 0.1 · JSON schema output` : n.sub}
              </text>
              {status && status !== "pending" && (
                <g>
                  <circle cx={n.x + n.w - 10} cy={n.y + 10} r={5}
                    fill={status === "completed" ? "#34d399" : status === "running" ? "#818cf8" : status === "failed" ? "#fb7185" : "#64748b"} />
                </g>
              )}
            </motion.g>
          );
        })}
      </svg>
      <p className="px-2 pb-1 text-xs text-muted">
        {phase === "running" && liveAgent
          ? `Live: the ${liveAgent} agent is running now — its incoming edges are highlighted.`
          : "Click any box for its step-by-step detail. Particles show data flowing; violet dotted lines are calls to the local model."}
      </p>
    </div>
  );
}
