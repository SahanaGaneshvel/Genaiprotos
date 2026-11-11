"use client";

import { motion, useReducedMotion } from "motion/react";

import type { Layers, NodeId, NodeState } from "@/lib/layers";

// ------------------------------------------------------------------ layout (desktop SVG)
interface Box { id: NodeId; x: number; y: number; w: number; h: number; title: string }

const MAIN_Y = 176;
const MAIN_H = 76;
const BOXES: Box[] = [
  { id: "question", x: 10, y: MAIN_Y, w: 120, h: MAIN_H, title: "Question" },
  { id: "check", x: 160, y: MAIN_Y, w: 120, h: MAIN_H, title: "Check" },
  { id: "research", x: 310, y: MAIN_Y, w: 160, h: MAIN_H, title: "Research" },
  { id: "compare", x: 500, y: MAIN_Y, w: 150, h: MAIN_H, title: "Compare" },
  { id: "evaluate", x: 680, y: MAIN_Y, w: 150, h: MAIN_H, title: "Evaluate" },
  { id: "write", x: 860, y: MAIN_Y, w: 150, h: MAIN_H, title: "Write" },
  { id: "report", x: 1040, y: MAIN_Y, w: 120, h: MAIN_H, title: "Report" },
  // the four kinds of sources, centred above Research
  { id: "web", x: 146, y: 30, w: 112, h: 58, title: "Web" },
  { id: "cards", x: 272, y: 30, w: 112, h: 58, title: "Model cards" },
  { id: "papers", x: 398, y: 30, w: 112, h: 58, title: "Papers" },
  { id: "code", x: 524, y: 30, w: 112, h: 58, title: "Code" },
  // the local AI model, below the agents
  { id: "model", x: 420, y: 330, w: 410, h: 58, title: "Local AI model" },
];
const box = Object.fromEntries(BOXES.map((b) => [b.id, b])) as Record<NodeId, Box>;

const MAIN_ORDER: NodeId[] = ["question", "check", "research", "compare", "evaluate", "write", "report"];
const AGENT_BOXES: NodeId[] = ["research", "compare", "evaluate", "write"];

function edge(a: Box, b: Box) {
  const y = a.y + a.h / 2;
  return `M ${a.x + a.w} ${y} L ${b.x} ${y}`;
}
function down(a: Box, b: Box) {
  const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y;
  const my = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
}
function up(model: Box, b: Box) {
  const x2 = b.x + b.w / 2, y1 = model.y, y2 = b.y + b.h;
  const x1 = Math.min(Math.max(x2, model.x + 30), model.x + model.w - 30);
  const my = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
}

const INK = "#1d1c1a", LINE = "#d9d4c8", MUTED = "#8a877f", ACCENT = "#b4532a", CARD = "#fffdf9";

function stroke(s: NodeState) {
  return s.status === "working" ? ACCENT : s.status === "done" ? INK : s.status === "failed" ? ACCENT : LINE;
}

function SvgNode({ b, s, selected, onSelect, reduce }: {
  b: Box; s: NodeState; selected: boolean; onSelect: (id: NodeId) => void; reduce: boolean;
}) {
  const working = s.status === "working";
  return (
    <g
      role="button"
      tabIndex={0}
      aria-label={`${b.title}: ${s.line}. Show details`}
      onClick={() => onSelect(b.id)}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(b.id)}
      className="cursor-pointer outline-none"
    >
      {working && !reduce && (
        <motion.rect
          x={b.x - 5} y={b.y - 5} width={b.w + 10} height={b.h + 10} rx={14}
          fill="none" stroke={ACCENT} strokeWidth={1.5}
          animate={{ opacity: [0.15, 0.7, 0.15] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <rect
        x={b.x} y={b.y} width={b.w} height={b.h} rx={10}
        fill={CARD} stroke={selected ? INK : stroke(s)} strokeWidth={selected ? 2 : working ? 1.6 : 1.2}
        strokeDasharray={s.status === "skipped" ? "4 4" : undefined}
        style={{ transition: "stroke 0.4s" }}
      />
      <text
        x={b.x + b.w / 2} y={b.y + b.h / 2 - 4} textAnchor="middle"
        fill={s.status === "waiting" ? MUTED : INK}
        style={{ fontFamily: "var(--font-newsreader)", fontSize: b.h > 70 ? 19 : 16, transition: "fill 0.4s" }}
      >
        {b.title}
      </text>
      <text
        x={b.x + b.w / 2} y={b.y + b.h / 2 + 15} textAnchor="middle"
        fill={working ? ACCENT : MUTED}
        style={{ fontFamily: "var(--font-plex-sans)", fontSize: 11.5 }}
      >
        {s.line}
      </text>
      {s.status === "done" && b.id !== "model" && (
        <circle cx={b.x + b.w - 11} cy={b.y + 11} r={3.5} fill={INK} />
      )}
    </g>
  );
}

function Flow({ d, active, done, modelLink, reduce }: { d: string; active: boolean; done: boolean; modelLink?: boolean; reduce: boolean }) {
  return (
    <g>
      <path
        d={d} fill="none"
        stroke={active ? ACCENT : done ? INK : LINE}
        strokeWidth={active ? 1.6 : 1.2}
        strokeDasharray={modelLink ? "3 5" : undefined}
        strokeOpacity={modelLink && !active ? 0.6 : 1}
        style={{ transition: "stroke 0.4s" }}
      />
      {active && !reduce && (
        <circle r={3.5} fill={ACCENT}>
          <animateMotion dur={modelLink ? "1.1s" : "1.4s"} repeatCount="indefinite" path={d} />
        </circle>
      )}
    </g>
  );
}

function DesktopDiagram({ layers, selected, onSelect }: Props) {
  const reduce = !!useReducedMotion();
  const n = layers.nodes;
  return (
    <svg viewBox="0 0 1170 400" className="hidden h-auto w-full md:block" role="img" aria-label="How a research run flows">
      {/* sources feed into Research */}
      {(["web", "cards", "papers", "code"] as NodeId[]).map((id) => (
        <Flow key={id} d={down(box[id], box.research)} active={n[id].status === "working"} done={n[id].status === "done"} reduce={reduce} />
      ))}
      {/* the main line, left to right */}
      {MAIN_ORDER.slice(0, -1).map((id, i) => {
        const next = MAIN_ORDER[i + 1];
        return (
          <Flow key={id} d={edge(box[id], box[next])}
            active={n[next].status === "working"} done={n[id].status === "done" && n[next].status !== "waiting"} reduce={reduce} />
        );
      })}
      {/* the AI model, shared by the four agents */}
      {AGENT_BOXES.map((id) => (
        <Flow key={id} d={up(box.model, box[id])} modelLink active={layers.modelBusyFor === id} done={false} reduce={reduce} />
      ))}
      {BOXES.map((b) => (
        <SvgNode key={b.id} b={b} s={n[b.id]} selected={selected === b.id} onSelect={onSelect} reduce={reduce} />
      ))}
      <text x={585} y={16} textAnchor="middle" fill={MUTED} style={{ fontFamily: "var(--font-plex-sans)", fontSize: 11, letterSpacing: 1.2 }}>
        WHERE THE RESEARCH COMES FROM
      </text>
    </svg>
  );
}

// ------------------------------------------------------------------ phones: the same flow, top to bottom
function MobileDiagram({ layers, selected, onSelect }: Props) {
  const n = layers.nodes;
  const steps: { id: NodeId; title: string }[] = [
    { id: "question", title: "Question" }, { id: "check", title: "Check" }, { id: "research", title: "Research" },
    { id: "compare", title: "Compare" }, { id: "evaluate", title: "Evaluate" }, { id: "write", title: "Write" },
    { id: "report", title: "Report" },
  ];
  return (
    <ol className="md:hidden">
      {steps.map((s, i) => {
        const st = n[s.id];
        return (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => onSelect(s.id)}
              className={`flex w-full items-baseline justify-between rounded-lg border bg-card px-4 py-3 text-left transition-colors ${
                selected === s.id ? "border-ink" : st.status === "working" ? "border-accent" : st.status === "done" ? "border-ink/40" : "border-line"
              }`}
            >
              <span className={`font-serif text-lg ${st.status === "waiting" ? "text-muted" : "text-ink"}`}>{s.title}</span>
              <span className={`text-[0.8rem] ${st.status === "working" ? "text-accent" : "text-muted"}`}>
                {st.line}
                {s.id !== "question" && layers.modelBusyFor === s.id && " · AI model"}
              </span>
            </button>
            {s.id === "research" && (
              <div className="mt-2 flex flex-wrap gap-1.5 pl-4">
                {(["web", "cards", "papers", "code"] as NodeId[]).map((id) => (
                  <button key={id} type="button" onClick={() => onSelect(id)}
                    className={`rounded-full border px-2.5 py-0.5 text-[0.75rem] ${n[id].status === "working" ? "border-accent text-accent" : n[id].status === "done" ? "border-ink/40 text-ink-2" : "border-line text-muted"}`}>
                    {{ web: "Web", cards: "Model cards", papers: "Papers", code: "Code" }[id as "web"]} · {n[id].line}
                  </button>
                ))}
              </div>
            )}
            {i < steps.length - 1 && <div className={`mx-auto h-5 w-px ${n[steps[i + 1].id].status !== "waiting" ? "bg-ink/50" : "bg-line"}`} />}
          </li>
        );
      })}
    </ol>
  );
}

interface Props {
  layers: Layers;
  selected: NodeId | null;
  onSelect: (id: NodeId) => void;
}

export function FlowDiagram(props: Props) {
  return (
    <div>
      <DesktopDiagram {...props} />
      <MobileDiagram {...props} />
    </div>
  );
}
