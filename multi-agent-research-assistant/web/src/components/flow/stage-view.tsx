"use client";

import { duration, type Stage } from "@/lib/flow";
import { RowView } from "./row-view";

const STAGE_COPY = {
  research: { name: "Research", line: "Finds sources and reads them." },
  comparison: { name: "Comparison", line: "Puts the models side by side." },
  evaluation: { name: "Evaluation", line: "Checks the evidence." },
  report: { name: "Report", line: "Writes it up, with citations." },
} as const;

function Status({ stage, now }: { stage: Stage; now: number }) {
  switch (stage.status) {
    case "running":
      return (
        <span className="text-accent">
          working{stage.startedAt != null && ` · ${duration(now - stage.startedAt)}`}
        </span>
      );
    case "completed":
      return <span className="text-ink-2">done{stage.seconds != null && ` in ${duration(stage.seconds)}`}</span>;
    case "failed":
      return <span className="text-accent">failed</span>;
    case "skipped":
      return <span className="text-muted">skipped, nothing to work with</span>;
    default:
      return <span className="text-muted">waiting</span>;
  }
}

export function StageView({ stage, index, now, model }: { stage: Stage; index: number; now: number; model: string }) {
  const copy = STAGE_COPY[stage.agent];
  const active = stage.status === "running";
  const started = stage.status !== "pending";

  return (
    <section className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-x-3 sm:grid-cols-[3.5rem_minmax(0,1fr)] sm:gap-x-4">
      <div className="relative flex flex-col items-center">
        <span
          className={`font-serif text-2xl leading-none transition-colors sm:text-3xl ${started ? "text-ink" : "text-line"}`}
        >
          {index + 1}
        </span>
        <span className={`mt-3 w-px flex-1 transition-colors ${active ? "bg-accent/40" : started ? "bg-ink/15" : "bg-line"}`} />
      </div>

      <div className="pb-12">
        <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 className={`font-serif text-2xl transition-colors sm:text-[1.7rem] ${started ? "text-ink" : "text-muted"}`}>
            {copy.name}
          </h2>
          <span className="font-mono text-[0.75rem] uppercase tracking-wider">
            <Status stage={stage} now={now} />
          </span>
        </header>
        <p className="mt-0.5 text-[0.9rem] text-muted">{copy.line}</p>

        {active && stage.rows.length === 0 && (
          <p className="mt-5 flex items-center gap-3 pl-0.5 text-[0.92rem] text-ink-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" /> Getting started…
          </p>
        )}

        {stage.rows.length > 0 && (
          <ol className="mt-5 space-y-3.5">
            {stage.rows.map((row) => (
              <RowView key={row.id} row={row} now={now} model={model} />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
