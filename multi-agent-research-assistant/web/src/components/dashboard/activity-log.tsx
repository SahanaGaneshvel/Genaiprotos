"use client";

import { Activity } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

import { useRun } from "../run-provider";
import { AGENT_META } from "./pipeline-live";

export function ActivityLog() {
  const { log, phase } = useRun();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" });
  }, [log.length]);

  if (phase !== "running" && log.length === 0) return null;

  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5 text-xs text-muted">
        <Activity size={14} className="text-accent-2" />
        Live activity — real events streamed from the LangGraph workflow
      </div>
      <div ref={box} className="scroll-thin max-h-44 overflow-y-auto px-4 py-2 font-mono text-[12px]">
        <AnimatePresence initial={false}>
          {log.map((line) => (
            <motion.div
              key={line.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex gap-3 py-0.5"
            >
              <span className="text-muted/70">{line.time}</span>
              <span className="w-24 shrink-0 text-indigo-300">{AGENT_META[line.agent].name}</span>
              <span className="truncate text-ink/85" title={line.text}>
                {line.text}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
        {phase === "running" && (
          <div className="flex items-center gap-1 py-1 text-muted">
            <span className="animate-pulse">▍</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}
