"use client";

import { ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";

import { STAGES } from "@/lib/pipeline";
import { ExecutorBadge, Legend, Reveal, SectionHeading } from "../ui";
import { FlowDiagram, type NodeId } from "./flow-diagram";
import { StageDetail, useModelName } from "./stage-detail";

const STATE_KEYS = [
  { key: "topic · depth · model_name", writer: "Caller / Orchestrator", note: "input, validated" },
  { key: "sources", writer: "Research", note: "citation registry S1…Sn — real URLs only" },
  { key: "research", writer: "Research", note: "findings, models identified, search plan, retrieval errors" },
  { key: "comparison", writer: "Comparison", note: "table rows, key differences, warnings" },
  { key: "evaluation", writer: "Evaluation", note: "verified benchmarks, assessments, memory estimates" },
  { key: "report", writer: "Report", note: "Markdown + citation audit" },
  { key: "agent_status · timings", writer: "every node (merge reducer)", note: "pending → running → completed / failed / skipped" },
  { key: "errors · execution_order", writer: "every node (append reducer)", note: "nothing overwrites another agent's entries" },
];

/** Global step number where each stage starts (01, 02, … across the whole pipeline). */
const STEP_OFFSETS = STAGES.map((_, i) => STAGES.slice(0, i).reduce((sum, s) => sum + s.steps.length, 0));

export function ArchitectureView() {
  const [selected, setSelected] = useState<NodeId>("research");
  const model = useModelName();

  return (
    <div className="mx-auto max-w-7xl space-y-20 px-4 py-10 sm:px-6 sm:py-14">
      <header className="max-w-3xl">
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-accent-2">
          Architecture
        </motion.p>
        <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="text-4xl font-semibold tracking-tight sm:text-5xl">
          How a research run <span className="text-gradient">flows</span>
        </motion.h1>
        <motion.p initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="mt-4 text-lg text-muted">
          A fixed, loop-free LangGraph pipeline. Every step is done by one of three things — the local LLM (
          <span className="font-mono text-violet-200">{model}</span>), deterministic code, or a public API. Click a box to see
          exactly what happens inside.
        </motion.p>
        <div className="mt-5"><Legend /></div>
      </header>

      <section className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <FlowDiagram selected={selected} onSelect={setSelected} />
        <StageDetail selected={selected} />
      </section>

      <section>
        <SectionHeading
          eyebrow="Shared state"
          title="One dictionary connects the agents"
          text="Agents never call each other. Each node reads what it needs from the shared LangGraph state and returns only the keys it changed; reducers merge bookkeeping so nothing is overwritten."
        />
        <div className="card overflow-x-auto scroll-thin">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead><tr className="border-b border-line text-xs uppercase tracking-wider text-muted"><th className="px-4 py-3">Key</th><th className="px-4 py-3">Written by</th><th className="px-4 py-3">Contents</th></tr></thead>
            <tbody>
              {STATE_KEYS.map((k, i) => (
                <motion.tr key={k.key} initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-[12px] text-cyan-200">{k.key}</td>
                  <td className="px-4 py-2.5">{k.writer}</td>
                  <td className="px-4 py-2.5 text-muted">{k.note}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <SectionHeading
          eyebrow="Every step, in order"
          title="The complete pipeline, step by step"
          text="Numbered in the order they execute in a normal run. Violet steps call the local model; green steps are plain code; amber steps call a public API."
        />
        <div className="relative space-y-10 border-l border-line pl-6 sm:pl-10">
          {STAGES.map((stage, si) => (
            <div key={stage.id}>
              <Reveal>
                <div className="relative mb-4">
                  <span className="absolute -left-[33px] top-1 h-3 w-3 rounded-full border-2 border-bg bg-gradient-to-br from-indigo-400 to-cyan-400 sm:-left-[49px]" />
                  <h3 className="text-lg font-semibold">{stage.name}</h3>
                  <p className="text-sm text-muted">{stage.tagline}</p>
                </div>
              </Reveal>
              <div className="grid gap-3 md:grid-cols-2">
                {stage.steps.map((step, i) => {
                  const n = STEP_OFFSETS[si] + i + 1;
                  return (
                    <Reveal key={step.title} y={12} delay={0.03}>
                      <div className="card h-full p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-muted">{String(n).padStart(2, "0")}</span>
                          <span className="font-medium">{step.title}</span>
                        </div>
                        <div className="mt-2"><ExecutorBadge executor={step.executor} model={model} /></div>
                        <p className="mt-2 text-[13px] leading-relaxed text-ink/75">{step.detail}</p>
                        {step.executor.kind === "llm" && (
                          <p className="mt-1 font-mono text-[11px] text-violet-200/80">{step.executor.schema} · ≤{step.executor.maxTokens} output tokens</p>
                        )}
                        {step.guard && (
                          <p className="mt-2 flex gap-1.5 text-[12px] text-emerald-200/90"><ShieldCheck size={13} className="mt-0.5 shrink-0" /> {step.guard}</p>
                        )}
                      </div>
                    </Reveal>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
