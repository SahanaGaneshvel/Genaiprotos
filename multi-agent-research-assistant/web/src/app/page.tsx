"use client";

import { ArrowRight, TriangleAlert } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { ActivityLog } from "@/components/dashboard/activity-log";
import { PipelineLive } from "@/components/dashboard/pipeline-live";
import { ResearchForm } from "@/components/dashboard/research-form";
import { Results } from "@/components/dashboard/results";
import { useRun } from "@/components/run-provider";

export default function DashboardPage() {
  const { health, error, phase } = useRun();
  const reduce = useReducedMotion();

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 sm:py-14">
      <motion.header
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="max-w-3xl"
      >
        <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1 text-xs text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> 100% local inference · no paid APIs
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          Multi-Agent <span className="text-gradient">AI Research</span> Assistant
        </h1>
        <p className="mt-4 text-lg text-muted">
          Four specialised agents research a technical topic, compare the models they find, check the evidence and write
          a fully cited report — every source is real, every citation is verified by code.
        </p>
        <Link href="/architecture" className="mt-4 inline-flex items-center gap-1.5 text-sm text-accent-2 hover:underline">
          See how it works, step by step <ArrowRight size={14} />
        </Link>
      </motion.header>

      {health && !health.ok && (
        <div className="flex gap-3 rounded-xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          <TriangleAlert size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Live research is unavailable</p>
            <p className="mt-0.5 font-mono text-xs text-rose-100/80">{health.message}</p>
            <p className="mt-1 text-xs text-rose-100/70">You can still explore the saved example run.</p>
          </div>
        </div>
      )}

      <ResearchForm />

      <section aria-label="Agent execution" className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Agent execution</h2>
          <span className="text-xs text-muted">
            {phase === "running" ? "Streaming live from the workflow…" : "Status updates come from real workflow events"}
          </span>
        </div>
        <PipelineLive />
        <ActivityLog />
      </section>

      {error && (
        <div className="flex gap-3 rounded-xl border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          <TriangleAlert size={18} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      <Results />
    </div>
  );
}
