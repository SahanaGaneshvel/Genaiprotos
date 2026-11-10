"use client";

import { motion } from "motion/react";
import { useMemo, useState } from "react";

import { ReportView } from "@/components/flow/report-view";
import { StageView } from "@/components/flow/stage-view";
import { buildStages, duration } from "@/lib/flow";
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
  const topic = edited ?? run.recorded?.topic ?? ""; // defaults to the recorded run's question
  const setTopic = setEdited;
  const stages = useMemo(() => buildStages(run.events), [run.events]);
  const model = run.mode === "live" ? run.health?.model ?? "local model" : run.recorded?.model_name ?? "qwen3.5";
  const recordedOn = run.recorded?.recorded_at
    ? new Date(run.recorded.recorded_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null;
  const started = run.mode !== "idle";

  return (
    <div className="mx-auto max-w-3xl px-5 pb-24 sm:px-8">
      <header className="flex items-baseline justify-between gap-4 border-b border-line py-6 text-[0.85rem]">
        <span className="shrink-0 font-serif text-lg text-ink">Research Agents</span>
        <span className="min-w-0 truncate text-right text-muted">
          {run.mode === "live" ? `live · ${model} on this computer` : run.liveAvailable ? `${run.health?.model} is ready` : "replay of a recorded run"}
        </span>
      </header>

      <section className="pt-16 pb-12 sm:pt-24">
        <h1 className="font-serif text-[2.4rem] leading-[1.1] tracking-tight text-ink sm:text-[3.4rem]">
          Four agents research a question.
          <br />
          <span className="italic text-ink-2">Here&apos;s everything they do.</span>
        </h1>
        <p className="mt-6 max-w-xl text-[1.02rem] leading-relaxed text-ink-2">
          They search the web, papers, model cards and code, read what they find, compare the models, check the evidence
          and write a report — using a small model running locally. Every step below is real. Tap any line to see how it
          works.
        </p>
      </section>

      <section className="mb-16">
        <label htmlFor="q" className="font-mono text-[0.72rem] uppercase tracking-wider text-muted">
          The question
        </label>
        <textarea
          id="q"
          rows={3}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          readOnly={!run.liveAvailable}
          className="mt-2 w-full resize-none border-b border-line bg-transparent pb-3 font-serif text-xl leading-snug text-ink outline-none focus:border-ink"
        />
        {!run.liveAvailable && (
          <p className="mt-2 text-[0.8rem] text-muted">
            Answered{recordedOn ? ` on ${recordedOn}` : ""} by {run.recorded?.model_name ?? "a local model"} on a laptop
            CPU. Live runs need the project running locally.
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-baseline gap-x-6 gap-y-3 text-[0.95rem]">
          <LinkButton strong onClick={run.replay} disabled={!run.recorded}>
            {run.mode === "replay" ? "Replay from the start" : "Replay the recorded run"}
          </LinkButton>
          {run.liveAvailable && (
            <LinkButton onClick={() => run.runLive(topic)} disabled={topic.trim().length < 10}>
              Run it live (~12 min)
            </LinkButton>
          )}
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
            <span className="flex gap-2">
              {SPEEDS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => run.setSpeed(s)}
                  className={run.speed === s ? "text-ink underline underline-offset-4" : "text-muted hover:text-ink"}
                >
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

        {run.error && <p className="mt-4 text-[0.9rem] text-accent">{run.error}</p>}
      </section>

      <div className={started ? "" : "opacity-60"}>
        {stages.map((stage, i) => (
          <StageView key={stage.agent} stage={stage} index={i} now={run.now} model={model} />
        ))}
      </div>

      {run.finished && run.result && <ReportView result={run.result} />}

      <footer className="mt-24 border-t border-line pt-6 text-[0.8rem] leading-relaxed text-muted">
        Built with LangGraph, Ollama and a {model} model. No paid APIs; the model never leaves the machine it runs on.
        Timings in the replay are the real ones from the recorded run, played back faster.
      </footer>
    </div>
  );
}
