"use client";

import { Ban, CircleCheck, CircleDashed, CircleX, FileText, FlaskConical, GitCompareArrows, LoaderCircle, Telescope } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

import type { AgentName, AgentStatus } from "@/lib/types";
import { AGENTS, useRun, type AgentView } from "../run-provider";

export const AGENT_META: Record<AgentName, { name: string; icon: typeof Telescope; blurb: string }> = {
  research: { name: "Research", icon: Telescope, blurb: "Searches web, model cards, arXiv & GitHub; extracts findings" },
  comparison: { name: "Comparison", icon: GitCompareArrows, blurb: "One row per model: size, context, hardware, licence" },
  evaluation: { name: "Evaluation", icon: FlaskConical, blurb: "Verifies benchmarks, estimates memory, flags gaps" },
  report: { name: "Report", icon: FileText, blurb: "10-section report with verified citations" },
};

const STATUS_UI: Record<AgentStatus, { label: string; ring: string; text: string }> = {
  pending: { label: "Pending", ring: "border-line", text: "text-muted" },
  running: { label: "Running", ring: "border-indigo-400/60", text: "text-indigo-200" },
  completed: { label: "Completed", ring: "border-emerald-400/40", text: "text-emerald-300" },
  failed: { label: "Failed", ring: "border-rose-400/50", text: "text-rose-300" },
  skipped: { label: "Skipped", ring: "border-dashed border-line-strong", text: "text-muted" },
};

function StatusIcon({ status }: { status: AgentStatus }) {
  const common = { size: 16 };
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.span
        key={status}
        initial={{ scale: 0.4, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.4, opacity: 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 26 }}
        className={STATUS_UI[status].text}
      >
        {status === "running" && <LoaderCircle {...common} className="animate-spin" />}
        {status === "completed" && <CircleCheck {...common} />}
        {status === "failed" && <CircleX {...common} />}
        {status === "skipped" && <Ban {...common} />}
        {status === "pending" && <CircleDashed {...common} />}
      </motion.span>
    </AnimatePresence>
  );
}

/** Seconds since `active` became true; state is only set from the timer callback. */
function useElapsed(active: boolean) {
  const [elapsed, setElapsed] = useState<number | null>(null);
  useEffect(() => {
    if (!active) return;
    const t0 = Date.now();
    const id = setInterval(() => setElapsed((Date.now() - t0) / 1000), 1000);
    return () => {
      clearInterval(id);
      setElapsed(null);
    };
  }, [active]);
  return active ? (elapsed ?? 0) : null;
}

function AgentCard({ agent, view, index }: { agent: AgentName; view: AgentView; index: number }) {
  const reduce = useReducedMotion();
  const meta = AGENT_META[agent];
  const ui = STATUS_UI[view.status];
  const running = view.status === "running";
  const elapsed = useElapsed(running);
  const Icon = meta.icon;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.45 }}
      className={`card relative flex-1 border p-4 transition-colors ${ui.ring}`}
    >
      {running && !reduce && (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl"
          animate={{ boxShadow: ["0 0 0 0 rgba(129,140,248,0.0)", "0 0 0 6px rgba(129,140,248,0.18)", "0 0 0 0 rgba(129,140,248,0.0)"] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={`grid h-10 w-10 place-items-center rounded-xl border ${
              running ? "border-indigo-400/40 bg-indigo-500/15 text-indigo-200" : "border-line bg-surface-2 text-ink/80"
            }`}
          >
            <Icon size={19} />
          </span>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted">Agent {index + 1}</p>
            <p className="font-semibold">{meta.name}</p>
          </div>
        </div>
        <StatusIcon status={view.status} />
      </div>
      <p className="mt-3 min-h-[2.5rem] text-xs leading-relaxed text-muted">{meta.blurb}</p>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className={`font-medium ${ui.text}`}>{ui.label}</span>
        <span className="font-mono text-muted">
          {view.seconds != null ? `${view.seconds.toFixed(1)} s` : elapsed != null ? `${Math.floor(elapsed)} s` : "—"}
        </span>
      </div>
      <AnimatePresence mode="wait">
        {running && view.detail && (
          <motion.p
            key={view.detail}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="mt-2 truncate rounded-md bg-surface-2 px-2 py-1 font-mono text-[11px] text-indigo-200/90"
            title={view.detail}
          >
            {view.detail}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/** Line between two agent cards: fills when the left agent is done, streams particles into a running agent. */
function Connector({ from, to }: { from: AgentView; to: AgentView }) {
  const reduce = useReducedMotion();
  const filled = from.status === "completed" || from.status === "skipped";
  const flowing = to.status === "running";
  return (
    <div aria-hidden className="relative flex shrink-0 items-center justify-center md:w-10 md:self-center h-6 w-full md:h-auto">
      <div className="relative h-full w-[2px] overflow-hidden rounded bg-line md:h-[2px] md:w-full">
        <motion.div
          className="absolute inset-0 origin-top bg-gradient-to-b from-indigo-400 to-cyan-400 md:origin-left md:bg-gradient-to-r"
          initial={false}
          animate={{ scaleX: 1, scaleY: 1, opacity: filled ? 1 : 0 }}
          transition={{ duration: 0.6 }}
        />
        {flowing && !reduce &&
          [0, 0.5].map((delay) => (
            <motion.span
              key={delay}
              className="absolute top-1/2 hidden h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-cyan-300 shadow-[0_0_10px_2px_rgba(34,211,238,0.7)] md:block"
              animate={{ left: ["0%", "100%"], opacity: [0, 1, 0] }}
              transition={{ duration: 1, repeat: Infinity, delay, ease: "linear" }}
            />
          ))}
      </div>
    </div>
  );
}

export function PipelineLive() {
  const { agents } = useRun();
  return (
    <div className="flex flex-col items-stretch gap-0 md:flex-row">
      {AGENTS.map((agent, i) => (
        <div key={agent} className="contents">
          <AgentCard agent={agent} view={agents[agent]} index={i} />
          {i < AGENTS.length - 1 && <Connector from={agents[agent]} to={agents[AGENTS[i + 1]]} />}
        </div>
      ))}
    </div>
  );
}
