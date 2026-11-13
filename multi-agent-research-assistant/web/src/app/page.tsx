"use client";

import { motion } from "motion/react";
import { useMemo, useState } from "react";

import { FlowDiagram } from "@/components/flow/flow-diagram";
import { DetailsCard, NowPanel } from "@/components/flow/panels";
import { ReportView } from "@/components/flow/report-view";
import { buildStages, duration } from "@/lib/flow";
import { buildLayers, NODE_IDS, type NodeId } from "@/lib/layers";
import { SPEEDS, useFlowRun } from "@/lib/use-flow-run";

function LinkButton(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { strong?: boolean }) {
  const { strong, className, ...rest } = props;
  return (
    <button
      type="button"
      {...rest}
      className={`underline underline-offset-4 transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        strong ? "font-medium text-ink decoration-ink" : "text-ink-2 decoration-line hover:decoration-ink"
      } ${className ?? ""}`}
    />
  );
}

export default function Page() {
  const run = useFlowRun();
  const [edited, setEdited] = useState<string | null>(null);
  const [picked, setSelected] = useState<NodeId | null | undefined>(undefined); // undefined = not touched yet
  const selected = picked === undefined ? (NODE_IDS.includes(run.openOnLoad as NodeId) ? (run.openOnLoad as NodeId) : null) : picked;
  const topic = edited ?? run.recorded?.topic ?? ""; // defaults to the recorded run's question

  const started = run.mode !== "idle";
  const model = run.mode === "live" ? run.health?.model ?? "local model" : run.recorded?.model_name ?? "qwen3.5";
  const stages = useMemo(() => buildStages(run.events), [run.events]);
  const layers = useMemo(
    () => buildLayers(stages, {
      started,
      finished: run.finished,
      failed: run.error,
      totalSeconds: run.result?.timings?.total ?? run.now,
    }),
    [stages, started, run.finished, run.error, run.result, run.now],
  );
  const result = run.mode === "live" ? run.result : run.recorded;
  const recordedOn = run.recorded?.recorded_at
    ? new Date(run.recorded.recorded_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null;

  return (
    <div className="mx-auto max-w-6xl px-5 pb-24 sm:px-8">
      <header className="flex items-baseline justify-between gap-4 border-b border-line py-6 text-[0.85rem]">
        <span className="shrink-0 font-serif text-lg text-ink">Research Agents</span>
        <span className="min-w-0 truncate text-right text-muted">
          {run.mode === "live" ? `live on this computer · ${model}` : run.liveAvailable ? `${run.health?.model} is ready` : "a recorded run, played back"}
        </span>
      </header>

      {/* 1. the question */}
      <section className="mx-auto max-w-3xl pt-14 pb-10 sm:pt-20">
        <h1 className="font-serif text-[2.2rem] leading-[1.1] tracking-tight text-ink sm:text-[3rem]">
          Four agents research a question.
          <br />
          <span className="italic text-ink-2">Watch how they do it.</span>
        </h1>

        <label htmlFor="q" className="mt-10 block font-mono text-[0.72rem] uppercase tracking-wider text-muted">
          The question
        </label>
        {run.liveAvailable ? (
          <textarea
            id="q"
            rows={4}
            value={topic}
            onChange={(e) => setEdited(e.target.value)}
            className="mt-2 w-full resize-none border-b border-line bg-transparent pb-3 font-serif text-xl leading-snug text-ink outline-none focus:border-ink"
          />
        ) : (
          // on the website the question is fixed (it is the recorded one), so show it in full
          <p id="q" className="mt-2 border-b border-line pb-3 font-serif text-xl leading-snug text-ink">{topic}</p>
        )}
        {!run.liveAvailable && (
          <p className="mt-2 text-[0.8rem] text-muted">
            Answered{recordedOn ? ` on ${recordedOn}` : ""} by a small AI model on a laptop. The website plays that run back,
            faster.
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-baseline gap-x-6 gap-y-3 text-[0.95rem]">
          {run.liveAvailable && (
            <LinkButton strong onClick={() => { setSelected(null); run.runLive(topic); }} disabled={topic.trim().length < 10 || (run.mode === "live" && !run.finished)}>
              Start
            </LinkButton>
          )}
          <LinkButton strong={!run.liveAvailable} onClick={() => { setSelected(null); run.replay(); }} disabled={!run.recorded}>
            {run.mode === "replay" ? "Watch again" : "Watch the recorded run"}
          </LinkButton>
        </div>

        {run.mode === "replay" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 border-y border-line py-3 font-mono text-[0.75rem] text-ink-2"
          >
            <button type="button" onClick={run.finished ? run.replay : run.togglePlay} className="w-14 text-left text-ink hover:text-accent">
              {run.finished ? "again" : run.playing ? "pause" : "play"}
            </button>
            <span className="tabular-nums">
              {duration(run.now)} <span className="text-muted">of {duration(run.end)}</span>
            </span>
            <span className="flex gap-1">
              {SPEEDS.map((s) => (
                <button key={s} type="button" onClick={() => run.setSpeed(s)} aria-label={`Play at ${s} times speed`}
                  className={`px-1.5 py-1 ${run.speed === s ? "text-ink underline underline-offset-4" : "text-muted hover:text-ink"}`}>
                  {s}×
                </button>
              ))}
            </span>
            {!run.finished && (
              <button type="button" onClick={run.skipToEnd} className="ml-auto text-muted hover:text-ink">
                skip to the end
              </button>
            )}
            <span className="h-px w-full bg-line">
              <span className="block h-px bg-ink transition-[width] duration-200" style={{ width: `${run.end ? (run.now / run.end) * 100 : 0}%` }} />
            </span>
          </motion.div>
        )}
      </section>

      {/* 2. the flow */}
      <section aria-label="How the run flows" className={`transition-opacity duration-500 ${started ? "" : "opacity-70"}`}>
        <FlowDiagram layers={layers} selected={selected} onSelect={(id) => setSelected(selected === id ? null : id)} />
      </section>

      {/* 3. what is happening, and details for a clicked box */}
      <section className="mx-auto mt-10 grid max-w-5xl gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <NowPanel layers={layers} />
        {selected ? (
          <DetailsCard key={selected} id={selected} layers={layers} result={result} model={model} onClose={() => setSelected(null)} />
        ) : (
          <p className="fade-in self-center text-[0.92rem] text-muted">
            Click any box in the diagram to see what it does and what it found.
          </p>
        )}
      </section>

      {/* 4. the result */}
      {run.finished && result?.report && (
        <div className="mx-auto mt-16 max-w-3xl">
          <ReportView result={result} />
        </div>
      )}

      <footer className="mx-auto mt-24 max-w-3xl border-t border-line pt-6 text-[0.8rem] leading-relaxed text-muted">
        One small AI model ({model}) runs on the laptop, never online, and plain code checks its work. No paid services.
      </footer>
    </div>
  );
}
