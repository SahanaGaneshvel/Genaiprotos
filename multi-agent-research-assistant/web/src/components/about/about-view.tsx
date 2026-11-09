"use client";

import {
  ArrowRight, Bot, Boxes, Code2, Cpu, FileText, FlaskConical, GitCompareArrows, Layers, Network,
  Server, ShieldCheck, Sparkles, Telescope, Workflow,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { AGENT_STAGES, GUARDS, llmCallCount } from "@/lib/pipeline";
import type { AgentName } from "@/lib/types";
import { useModelName } from "../architecture/stage-detail";
import { AnimatedNumber, Pill, Reveal, SectionHeading } from "../ui";

const AGENT_COPY: Record<AgentName, { icon: typeof Telescope; color: string; llm: string[]; code: string[] }> = {
  research: {
    icon: Telescope,
    color: "from-indigo-500 to-blue-500",
    llm: ["Plans the web, arXiv, GitHub and Hugging Face searches", "Reads each source and extracts facts, limitations and model names"],
    code: ["Calls four public APIs with fallbacks and caching", "Fetches pages (robots.txt respected) and picks the most informative passages", "De-duplicates URLs and assigns citation IDs S1…Sn"],
  },
  comparison: {
    icon: GitCompareArrows,
    color: "from-cyan-500 to-teal-500",
    llm: ["Chooses which candidates are real AI models", "Fills one table row per model from that model's evidence", "Explains the key differences"],
    code: ["Ranks candidates and always includes models with their own model card", "Decides which sources support each row", "Fills licence / parameters from API metadata and classifies licences"],
  },
  evaluation: {
    icon: FlaskConical,
    color: "from-violet-500 to-fuchsia-500",
    llm: ["Finds reported benchmark scores", "Judges on-premise suitability, trade-offs and missing evidence"],
    code: ["Verifies every score appears in the cited source text", "Downgrades verdicts with no valid source", "Computes memory estimates from parameter counts"],
  },
  report: {
    icon: FileText,
    color: "from-amber-500 to-orange-500",
    llm: ["Writes the executive summary, analysis and advice"],
    code: ["Removes sentences that misattribute a model to a source", "Assembles 10 sections, tables and rule-based recommendations", "Builds References from the registry and audits every citation"],
  },
};

const STACK = [
  { icon: Cpu, name: "Ollama + Qwen3.5", text: "Local open-weight LLM. Default qwen3.5:4b; 2b on 8 GB machines." },
  { icon: Workflow, name: "LangGraph", text: "Explicit state graph: fixed order, conditional routing, no loops." },
  { icon: Layers, name: "Pydantic", text: "Every agent's output is a validated schema, never free text." },
  { icon: Server, name: "FastAPI + SSE", text: "Streams live agent events to the browser as they happen." },
  { icon: Sparkles, name: "Next.js + Motion", text: "This interface: animated, real-time, three pages." },
  { icon: Boxes, name: "Streamlit", text: "The original lightweight dashboard, still included." },
];

const LIMITS = [
  "A 2–4B model extracts facts well but reasons weakly; narrative sentences can contain reasoning errors.",
  "Free web search engines often block automated clients; results vary between runs.",
  "Benchmark scores are rarely in the retrieved text, so many runs verify none — honestly reported.",
  "Memory figures are arithmetic estimates, not measurements. No benchmark is ever executed.",
  "A Basic run takes ~10–13 minutes on a laptop CPU.",
];

function Hero() {
  const reduce = useReducedMotion();
  const steps = [
    { icon: Sparkles, title: "Ask", text: "Type a technical research question." },
    { icon: Network, title: "Four agents work", text: "Research → Comparison → Evaluation → Report, live." },
    { icon: ShieldCheck, title: "Get a cited report", text: "Every claim tied to a real, retrieved source." },
  ];
  return (
    <section className="relative">
      <motion.p initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-accent-2">
        About the project
      </motion.p>
      <motion.h1
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="max-w-4xl text-4xl font-semibold tracking-tight sm:text-6xl"
      >
        An AI research team that <span className="text-gradient">runs on your laptop</span>
      </motion.h1>
      <motion.p initial={reduce ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.6 }} className="mt-5 max-w-3xl text-lg text-muted">
        Four specialised agents investigate a topic independently and collaborate through a shared state to produce a
        structured technical report. Built as a proof of concept for multi-agent orchestration, local LLM integration,
        source retrieval and evidence evaluation — with a hard rule: <b className="text-ink">nothing is invented</b>.
      </motion.p>

      <div className="mt-8 flex flex-wrap gap-3">
        {[
          { v: 4, l: "specialised agents" },
          { v: 4, l: "public data sources" },
          { v: 0, l: "paid APIs" },
          { v: 9, l: "anti-fabrication guards" },
        ].map((s, i) => (
          <motion.div key={s.l} initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.07 }} className="card px-5 py-3">
            <p className="text-2xl font-semibold tabular-nums"><AnimatedNumber value={s.v} /></p>
            <p className="text-xs text-muted">{s.l}</p>
          </motion.div>
        ))}
      </div>

      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {steps.map((s, i) => (
          <Reveal key={s.title} delay={0.1 * i}>
            <div className="card relative h-full overflow-hidden p-5">
              <span className="absolute right-4 top-3 font-mono text-5xl font-bold text-white/[0.04]">{i + 1}</span>
              <s.icon className="text-accent-2" size={22} />
              <p className="mt-3 font-semibold">{s.title}</p>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Agents() {
  const model = useModelName();
  return (
    <section>
      <SectionHeading
        eyebrow="Meet the agents"
        title="Four agents, four responsibilities"
        text="They share one local model but nothing else: each has its own system prompt, its own input from the shared state and its own validated output schema."
      />
      <div className="grid gap-5 lg:grid-cols-2">
        {AGENT_STAGES.map((stage, i) => {
          const copy = AGENT_COPY[stage.id];
          const Icon = copy.icon;
          return (
            <Reveal key={stage.id} delay={(i % 2) * 0.08}>
              <motion.article whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300, damping: 24 }} className="card group relative h-full overflow-hidden p-6">
                <div className={`pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-gradient-to-br ${copy.color} opacity-10 blur-2xl transition-opacity group-hover:opacity-25`} />
                <div className="flex items-center gap-3">
                  <span className={`grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br ${copy.color} text-white shadow-lg`}>
                    <Icon size={20} />
                  </span>
                  <div>
                    <p className="text-[11px] uppercase tracking-wider text-muted">Agent {i + 1}</p>
                    <h3 className="text-lg font-semibold">{stage.name}</h3>
                  </div>
                  <span className="ml-auto"><Pill tone="indigo">{llmCallCount(stage)} LLM step{llmCallCount(stage) > 1 ? "s" : ""}</Pill></span>
                </div>
                <p className="mt-4 text-sm text-ink/80">{stage.tagline}</p>

                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-violet-200"><Bot size={13} /> The model ({model})</p>
                    <ul className="space-y-1.5 text-[13px] text-ink/75">
                      {copy.llm.map((t) => <li key={t} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-violet-400" />{t}</li>)}
                    </ul>
                  </div>
                  <div>
                    <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-emerald-200"><Code2 size={13} /> The code</p>
                    <ul className="space-y-1.5 text-[13px] text-ink/75">
                      {copy.code.map((t) => <li key={t} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />{t}</li>)}
                    </ul>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-1.5 border-t border-line pt-4 text-[11px]">
                  <span className="text-muted">writes →</span>
                  {stage.writes.map((w) => <Pill key={w} tone="cyan">{w}</Pill>)}
                </div>
              </motion.article>
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}

function Guards() {
  return (
    <section>
      <SectionHeading
        eyebrow="Trust"
        title="Why you can check every claim"
        text="Small local models make mistakes. The design assumes they will — and puts code between the model and the report wherever a fact can be checked."
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {GUARDS.map((g, i) => (
          <Reveal key={g.title} delay={(i % 3) * 0.06}>
            <div className="card h-full p-4">
              <p className="flex items-center gap-2 font-medium"><ShieldCheck size={16} className="text-emerald-300" /> {g.title}</p>
              <p className="mt-1.5 text-sm text-muted">{g.text}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Stack() {
  return (
    <section>
      <SectionHeading eyebrow="Built with" title="Technology stack" text="Free, local and open: the application never calls a paid API, and the LLM never leaves the machine." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {STACK.map((s, i) => (
          <Reveal key={s.name} delay={(i % 3) * 0.06}>
            <div className="card flex h-full gap-3 p-4">
              <s.icon size={20} className="mt-0.5 shrink-0 text-accent" />
              <div>
                <p className="font-medium">{s.name}</p>
                <p className="mt-0.5 text-sm text-muted">{s.text}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function Limits() {
  return (
    <section className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
      <SectionHeading eyebrow="Honesty" title="Known limitations" text="Found by running the full pipeline nine times against a real model and real internet — and documented rather than hidden." />
      <Reveal>
        <ul className="card divide-y divide-line">
          {LIMITS.map((l) => <li key={l} className="px-5 py-3 text-sm text-ink/80">{l}</li>)}
        </ul>
      </Reveal>
    </section>
  );
}

export function AboutView() {
  return (
    <div className="mx-auto max-w-7xl space-y-24 px-4 py-10 sm:px-6 sm:py-16">
      <Hero />
      <Agents />
      <Guards />
      <Stack />
      <Limits />
      <Reveal>
        <div className="card relative overflow-hidden p-8 text-center sm:p-12">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-indigo-500/10 via-transparent to-cyan-500/10" />
          <h2 className="text-2xl font-semibold sm:text-3xl">See every step, in detail</h2>
          <p className="mx-auto mt-2 max-w-xl text-muted">The architecture page shows each step of the pipeline and which model, code or API performs it.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/architecture" className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950">
              Explore the architecture <ArrowRight size={15} />
            </Link>
            <Link href="/" className="inline-flex items-center gap-2 rounded-full border border-line px-5 py-2.5 text-sm hover:bg-surface-2">
              Run a research task
            </Link>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
