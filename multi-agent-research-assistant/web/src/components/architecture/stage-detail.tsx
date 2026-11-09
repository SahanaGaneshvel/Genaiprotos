"use client";

import { ArrowDownToLine, ArrowUpFromLine, FileCode2, ShieldCheck } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import { LLM_SETTINGS, STAGES, llmCallCount, type Stage } from "@/lib/pipeline";
import { useRun } from "../run-provider";
import { ExecutorBadge, Pill } from "../ui";
import type { NodeId } from "./flow-diagram";

const TOOL_STEP: Partial<Record<NodeId, string>> = {
  web: "Web search",
  hf: "Official model cards",
  arxiv: "Academic papers",
  github: "Code repositories",
};

function stageFor(id: NodeId): Stage | undefined {
  const map: Partial<Record<NodeId, Stage["id"]>> = {
    orchestrator: "orchestrator", research: "research", web: "research", hf: "research", arxiv: "research",
    github: "research", router: "router", insufficient: "router", comparison: "comparison",
    evaluation: "evaluation", report: "report", outputs: "report",
  };
  return STAGES.find((s) => s.id === map[id]);
}

export function useModelName() {
  const { health } = useRun();
  return health?.model && health.model !== "unknown" ? health.model : "qwen3.5 (configured model)";
}

function OllamaPanel({ model }: { model: string }) {
  const calls = STAGES.flatMap((s) => s.steps.filter((st) => st.executor.kind === "llm").map((st) => ({ stage: s.name, step: st })));
  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs uppercase tracking-wider text-violet-300">Local LLM</p>
        <h3 className="mt-1 text-xl font-semibold">Ollama · {model}</h3>
        <p className="mt-2 text-sm text-muted">
          One small open-weight model serves every agent. Each agent gets its own system prompt, its own slice of the
          shared state and its own output schema — the model is shared, the responsibilities are not.
        </p>
      </div>
      <dl className="grid gap-2 text-sm">
        {LLM_SETTINGS.map((s) => (
          <div key={s.label} className="flex justify-between gap-4 border-b border-line/60 pb-2">
            <dt className="text-muted">{s.label}</dt>
            <dd className="text-right">{s.value}</dd>
          </div>
        ))}
      </dl>
      <div>
        <p className="mb-2 text-sm font-medium">Every LLM call in a run</p>
        <ul className="space-y-1.5 text-sm">
          {calls.map(({ stage, step }) => step.executor.kind === "llm" && (
            <li key={`${stage}-${step.title}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-2/60 px-3 py-2">
              <span><span className="text-muted">{stage} ·</span> {step.title}</span>
              <span className="font-mono text-[11px] text-violet-200">{step.executor.schema} · ≤{step.executor.maxTokens} tokens</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function StagePanel({ stage, model, highlight }: { stage: Stage; model: string; highlight?: string }) {
  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="indigo">{stage.steps.length} steps</Pill>
          <Pill tone={llmCallCount(stage) ? "slate" : "emerald"}>
            {llmCallCount(stage) ? `${llmCallCount(stage)} LLM step${llmCallCount(stage) > 1 ? "s" : ""} · ${model}` : "no LLM — pure code"}
          </Pill>
        </div>
        <h3 className="mt-3 text-xl font-semibold">{stage.name}</h3>
        <p className="mt-1 text-sm text-muted">{stage.tagline}</p>
        <p className="mt-2 inline-flex items-center gap-1.5 font-mono text-[11px] text-muted"><FileCode2 size={12} /> {stage.file}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-xs text-muted"><ArrowDownToLine size={13} /> Reads from shared state</p>
          <div className="flex flex-wrap gap-1">{stage.reads.map((r) => <Pill key={r}>{r}</Pill>)}</div>
        </div>
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 text-xs text-muted"><ArrowUpFromLine size={13} /> Writes</p>
          <div className="flex flex-wrap gap-1">{stage.writes.map((r) => <Pill key={r} tone="cyan">{r}</Pill>)}</div>
        </div>
      </div>
      <ol className="space-y-2.5">
        {stage.steps.map((step, i) => (
          <motion.li
            key={step.title}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className={`rounded-xl border p-3 ${highlight === step.title ? "border-amber-400/50 bg-amber-500/5" : "border-line bg-surface-2/40"}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="grid h-5 w-5 place-items-center rounded-full bg-surface-2 font-mono text-[10px] text-muted">{i + 1}</span>
              <span className="text-sm font-medium">{step.title}</span>
              <span className="ml-auto"><ExecutorBadge executor={step.executor} model={model} /></span>
            </div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink/75">{step.detail}</p>
            {step.executor.kind === "llm" && (
              <p className="mt-1 font-mono text-[11px] text-violet-200/80">output schema: {step.executor.schema} · max {step.executor.maxTokens} tokens</p>
            )}
            {step.guard && (
              <p className="mt-1.5 flex gap-1.5 text-[12px] text-emerald-200/90"><ShieldCheck size={13} className="mt-0.5 shrink-0" /> {step.guard}</p>
            )}
          </motion.li>
        ))}
      </ol>
    </div>
  );
}

function UserPanel() {
  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wider text-muted">Input</p>
      <h3 className="text-xl font-semibold">Research topic + depth</h3>
      <p className="text-sm text-muted">
        A free-text question (10–1,000 characters) and a depth: <b className="text-ink">Basic</b> keeps ~2 sources per category and
        reads 1,500 characters of each; <b className="text-ink">Detailed</b> keeps ~4 and reads 2,500. The browser sends both to
        the FastAPI server, which starts the LangGraph workflow and streams every agent event back as Server-Sent Events.
      </p>
    </div>
  );
}

export function StageDetail({ selected }: { selected: NodeId }) {
  const model = useModelName();
  const stage = stageFor(selected);
  return (
    <div className="card h-full p-5 sm:p-6">
      <AnimatePresence mode="wait">
        <motion.div key={selected} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
          {selected === "ollama" ? <OllamaPanel model={model} /> : selected === "user" ? <UserPanel /> : stage ? (
            <StagePanel stage={stage} model={model} highlight={TOOL_STEP[selected]} />
          ) : null}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
