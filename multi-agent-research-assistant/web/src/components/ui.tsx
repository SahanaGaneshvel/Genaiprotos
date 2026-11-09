"use client";

import { Bot, Code2, Globe } from "lucide-react";
import { animate, motion, useInView, useReducedMotion } from "motion/react";
import { Fragment, useEffect, useRef, useState } from "react";

import type { Executor } from "@/lib/pipeline";
import type { Source } from "@/lib/types";

/** Fades + slides children in when they scroll into view. */
export function Reveal({
  children,
  delay = 0,
  className,
  y = 18,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  y?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function SectionHeading({ eyebrow, title, text }: { eyebrow: string; title: string; text?: string }) {
  return (
    <Reveal className="mb-8 max-w-3xl">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent-2">{eyebrow}</p>
      <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>
      {text && <p className="mt-3 text-muted">{text}</p>}
    </Reveal>
  );
}

const EXECUTOR_STYLE = {
  llm: { icon: Bot, cls: "border-violet-400/30 bg-violet-500/10 text-violet-200" },
  code: { icon: Code2, cls: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" },
  api: { icon: Globe, cls: "border-amber-400/30 bg-amber-500/10 text-amber-200" },
} as const;

/** Who runs a step: the local LLM (with model name), code, or an external API. */
export function ExecutorBadge({ executor, model }: { executor: Executor; model: string }) {
  const { icon: Icon, cls } = EXECUTOR_STYLE[executor.kind];
  const label =
    executor.kind === "llm" ? `LLM · ${model}` : executor.kind === "code" ? "Code · no model" : executor.service;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      <Icon size={12} />
      {label}
    </span>
  );
}

export function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
      <ExecutorBadge executor={{ kind: "llm", schema: "", maxTokens: 0 }} model="local model" />
      <span>reads &amp; writes language</span>
      <ExecutorBadge executor={{ kind: "code" }} model="" />
      <span>checks facts deterministically</span>
      <ExecutorBadge executor={{ kind: "api", service: "External API" }} model="" />
      <span>public data source</span>
    </div>
  );
}

/** Counts up to `value` when scrolled into view. */
export function AnimatedNumber({ value, decimals = 0, suffix = "" }: { value: number; decimals?: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView || reduce) return;
    const controls = animate(0, value, { duration: 1.1, ease: "easeOut", onUpdate: setShown });
    return () => controls.stop();
  }, [inView, value, reduce]);

  return (
    <span ref={ref}>
      {(reduce ? value : shown).toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Renders text, turning [S3] markers into chips that link to the real source URL. */
export function Cited({ text, sources }: { text: string; sources: Source[] }) {
  const byId = new Map(sources.map((s) => [s.source_id, s]));
  const parts = text.split(/(\[S\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = part.match(/^\[(S\d+)\]$/);
        const src = m ? byId.get(m[1]) : undefined;
        if (!m) return <Fragment key={i}>{part}</Fragment>;
        return src ? (
          <a
            key={i}
            href={src.url}
            target="_blank"
            rel="noreferrer"
            title={src.title}
            className="mx-0.5 inline-flex translate-y-[-1px] items-center rounded border border-cyan-400/30 bg-cyan-500/10 px-1 font-mono text-[10px] text-cyan-200 hover:bg-cyan-500/20"
          >
            {m[1]}
          </a>
        ) : (
          <span key={i} className="mx-0.5 font-mono text-[10px] text-muted">
            {m[1]}
          </span>
        );
      })}
    </>
  );
}

export function Pill({ children, tone = "slate" }: { children: React.ReactNode; tone?: "slate" | "emerald" | "amber" | "rose" | "indigo" | "cyan" }) {
  const tones = {
    slate: "border-slate-400/20 bg-slate-500/10 text-slate-300",
    emerald: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-400/30 bg-amber-500/10 text-amber-200",
    rose: "border-rose-400/30 bg-rose-500/10 text-rose-200",
    indigo: "border-indigo-400/30 bg-indigo-500/10 text-indigo-200",
    cyan: "border-cyan-400/30 bg-cyan-500/10 text-cyan-200",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>;
}
