"use client";

import { Play, RotateCcw, Sparkles, Square } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

import { useRun } from "../run-provider";

export const EXAMPLE_TOPIC =
  "Research the latest open-source multimodal models suitable for on-premise deployment. Compare their capabilities, benchmarks, hardware requirements, licensing and limitations.";

export function ResearchForm() {
  const { health, phase, start, cancel, loadExample, reset, result } = useRun();
  const [topic, setTopic] = useState(EXAMPLE_TOPIC);
  const [depth, setDepth] = useState<"basic" | "detailed">("basic");
  const running = phase === "running";
  const tooShort = topic.trim().length < 10;
  const ready = health?.ok === true;

  return (
    <div className="card p-5 sm:p-6">
      <label htmlFor="topic" className="mb-2 block text-sm font-medium">
        Research topic
      </label>
      <textarea
        id="topic"
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        maxLength={1000}
        rows={3}
        disabled={running}
        className="w-full resize-none rounded-xl border border-line bg-bg/60 px-4 py-3 text-sm leading-relaxed outline-none transition focus:border-indigo-400/60 focus:ring-4 focus:ring-indigo-500/10 disabled:opacity-60"
        placeholder="e.g. Compare open-weight speech recognition models for on-premise deployment"
      />
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <div role="radiogroup" aria-label="Research depth" className="relative flex rounded-full border border-line bg-bg/60 p-1 text-xs">
          {(["basic", "detailed"] as const).map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={depth === d}
              disabled={running}
              onClick={() => setDepth(d)}
              className={`relative z-10 rounded-full px-4 py-1.5 capitalize transition-colors ${depth === d ? "text-ink" : "text-muted hover:text-ink"}`}
            >
              {depth === d && (
                <motion.span layoutId="depth-pill" className="absolute inset-0 -z-10 rounded-full bg-surface-2 ring-1 ring-line-strong" />
              )}
              {d}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted">
          {depth === "basic" ? "~2 sources per category · ~10–13 min on a laptop CPU" : "~4 sources per category · slower"}
        </span>

        <div className="ml-auto flex flex-wrap gap-2">
          {result && !running && (
            <button type="button" onClick={reset} className="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2 text-sm text-muted transition hover:text-ink">
              <RotateCcw size={15} /> Clear
            </button>
          )}
          <button
            type="button"
            onClick={loadExample}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-full border border-line px-4 py-2 text-sm transition hover:border-line-strong hover:bg-surface-2 disabled:opacity-50"
            title="Show the saved example run instantly (no LLM needed)"
          >
            <Sparkles size={15} className="text-accent-2" /> Load example run
          </button>
          {running ? (
            <button type="button" onClick={cancel} className="inline-flex items-center gap-2 rounded-full border border-rose-400/40 bg-rose-500/10 px-5 py-2 text-sm text-rose-200">
              <Square size={14} /> Stop watching
            </button>
          ) : (
            <motion.button
              type="button"
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => start(topic, depth)}
              disabled={!ready || tooShort}
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 shadow-lg shadow-indigo-500/25 disabled:cursor-not-allowed disabled:opacity-40"
              title={!ready ? health?.message : tooShort ? "Topic must be at least 10 characters" : undefined}
            >
              <Play size={15} fill="currentColor" /> Start research
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
}
