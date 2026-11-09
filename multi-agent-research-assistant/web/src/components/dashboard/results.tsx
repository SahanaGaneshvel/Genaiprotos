"use client";

import { BookOpen, Download, ExternalLink, FileText, FlaskConical, GitBranch, GitCompareArrows, Globe, Newspaper, Telescope, TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { RunState, Source, SourceType } from "@/lib/types";
import { Markdown } from "../markdown";
import { useRun } from "../run-provider";
import { AnimatedNumber, Cited, Pill } from "../ui";

const SOURCE_ICON: Record<SourceType, typeof Globe> = {
  web: Globe,
  documentation: BookOpen,
  arxiv: Newspaper,
  github: GitBranch,
};

const TABS = [
  { id: "findings", label: "Research Findings", icon: Telescope },
  { id: "comparison", label: "Model Comparison", icon: GitCompareArrows },
  { id: "evaluation", label: "Evaluation", icon: FlaskConical },
  { id: "report", label: "Final Report", icon: FileText },
] as const;
type TabId = (typeof TABS)[number]["id"];

function licenceTone(category: string) {
  if (category.startsWith("Open source")) return "emerald" as const;
  if (category.startsWith("Open weights")) return "amber" as const;
  if (category.startsWith("Proprietary")) return "rose" as const;
  return "slate" as const;
}

function suitabilityTone(level: string) {
  return level === "high" ? "emerald" : level === "medium" ? "amber" : level === "low" ? "rose" : "slate";
}

function Metrics({ state }: { state: RunState }) {
  const items = [
    { label: "Sources retrieved", value: state.sources?.length ?? 0 },
    { label: "Relevant findings", value: state.research?.findings.length ?? 0 },
    { label: "Models compared", value: state.comparison?.models.length ?? 0 },
    { label: "Verified benchmarks", value: state.evaluation?.benchmarks.length ?? 0 },
    { label: "Total time", value: state.timings.total ?? 0, suffix: " s" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((m, i) => (
        <motion.div
          key={m.label}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06 }}
          className="card px-4 py-3"
        >
          <p className="text-[11px] uppercase tracking-wider text-muted">{m.label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">
            <AnimatedNumber value={m.value} suffix={m.suffix} />
          </p>
        </motion.div>
      ))}
    </div>
  );
}

function SourceLink({ source }: { source: Source }) {
  const Icon = SOURCE_ICON[source.source_type];
  return (
    <a href={source.url} target="_blank" rel="noreferrer" className="group flex items-center gap-3 rounded-lg px-3 py-2 transition hover:bg-surface-2">
      <span className="w-8 font-mono text-[11px] text-cyan-300">{source.source_id}</span>
      <Icon size={14} className="shrink-0 text-muted" />
      <span className="truncate text-sm">{source.title}</span>
      <span className="ml-auto shrink-0 text-[11px] text-muted">{source.published ?? "no date"}</span>
      <ExternalLink size={13} className="shrink-0 text-muted opacity-0 transition group-hover:opacity-100" />
    </a>
  );
}

function FindingsTab({ state, sources }: { state: RunState; sources: Source[] }) {
  const research = state.research;
  if (!research) return <Empty text="Research did not produce output." />;
  const plan = research.search_plan;
  return (
    <div className="space-y-6">
      {plan && (
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="text-muted">Search plan:</span>
          {plan.web_queries.map((q) => <Pill key={q} tone="indigo">web · {q}</Pill>)}
          <Pill tone="amber">HF task · {plan.hub_task}</Pill>
          <Pill tone="cyan">arXiv · {plan.arxiv_query}</Pill>
          <Pill tone="emerald">GitHub · {plan.github_query}</Pill>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {research.findings.map((f, i) => {
          const Icon = SOURCE_ICON[f.source_type];
          return (
            <motion.article
              key={f.source_id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="card p-4"
            >
              <div className="mb-2 flex items-center gap-2 text-xs text-muted">
                <span className="rounded border border-cyan-400/30 bg-cyan-500/10 px-1.5 font-mono text-cyan-200">{f.source_id}</span>
                <Icon size={13} /> {f.source_type} · {f.published ?? "no date"}
              </div>
              <a href={f.source_url} target="_blank" rel="noreferrer" className="font-medium hover:text-accent-2">
                {f.title} <ExternalLink size={12} className="inline opacity-60" />
              </a>
              <p className="mt-2 text-sm text-ink/80">{f.summary}</p>
              {f.key_findings.length > 0 && (
                <ul className="mt-3 space-y-1 text-sm text-ink/80">
                  {f.key_findings.map((k) => (
                    <li key={k} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-emerald-400" />{k}</li>
                  ))}
                </ul>
              )}
              {f.limitations.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-muted">
                  {f.limitations.map((k) => (
                    <li key={k} className="flex gap-2"><span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-amber-400" />{k}</li>
                  ))}
                </ul>
              )}
            </motion.article>
          );
        })}
      </div>
      <div className="card p-2">
        <p className="px-3 pt-2 pb-1 text-xs font-semibold uppercase tracking-wider text-muted">All retrieved sources (citation registry)</p>
        {sources.map((s) => <SourceLink key={s.source_id} source={s} />)}
      </div>
    </div>
  );
}

function ComparisonTab({ state, sources }: { state: RunState; sources: Source[] }) {
  const c = state.comparison;
  if (!c || c.models.length === 0) return <Empty text="No comparison could be produced from the retrieved evidence." />;
  const cols = ["Model", "Modalities", "Parameters", "Context", "Deployment", "Hardware", "Licence", "Sources"];
  return (
    <div className="space-y-6">
      <div className="card overflow-x-auto scroll-thin">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-wider text-muted">
              {cols.map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {c.models.map((m, i) => (
              <motion.tr
                key={m.model_name}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.07 }}
                className="border-b border-line/60 align-top last:border-0"
              >
                <td className="px-4 py-3 font-medium">{m.model_name}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">{m.modalities.map((x) => <Pill key={x}>{x}</Pill>)}</div>
                </td>
                <td className="px-4 py-3 text-ink/80">{m.parameter_sizes}</td>
                <td className="px-4 py-3 text-ink/80">{m.context_window}</td>
                <td className="px-4 py-3 text-ink/80">{m.deployment_methods.join(", ") || "—"}</td>
                <td className="px-4 py-3 text-ink/80">{m.hardware_requirements}</td>
                <td className="px-4 py-3">
                  <p className="text-ink/80">{m.licence}</p>
                  <div className="mt-1"><Pill tone={licenceTone(m.licence_category)}>{m.licence_category}</Pill></div>
                </td>
                <td className="px-4 py-3"><Cited text={m.source_ids.map((s) => `[${s}]`).join("")} sources={sources} /></td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        Licence type is decided by code from the licence text: OSI-approved open source vs open weights under a custom licence.
      </p>
      {c.key_differences.length > 0 && (
        <div className="card p-5">
          <h3 className="mb-3 font-semibold">Important differences</h3>
          <ul className="space-y-2 text-sm text-ink/85">
            {c.key_differences.map((d) => (
              <li key={d} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" /><span><Cited text={d} sources={sources} /></span></li>
            ))}
          </ul>
        </div>
      )}
      {(c.warnings?.length ?? 0) > 0 && <Notice items={c.warnings ?? []} />}
    </div>
  );
}

function MemoryBars({ state }: { state: RunState }) {
  const items = state.evaluation?.memory_estimates ?? [];
  if (items.length === 0) return null;
  const max = Math.log10(Math.max(...items.map((m) => m.fp16_gb)) + 1);
  const bar = (gb: number) => `${Math.max(4, (Math.log10(gb + 1) / max) * 100)}%`;
  return (
    <div className="card p-5">
      <h3 className="font-semibold">Estimated weight memory</h3>
      <p className="mb-4 text-xs text-muted">Computed by code from Hugging Face parameter counts · log scale · not measured · excludes KV cache</p>
      <div className="space-y-4">
        {items.map((m) => (
          <div key={m.model_name}>
            <div className="mb-1.5 flex justify-between text-sm">
              <span className="font-medium">{m.model_name}</span>
              <span className="text-muted">{m.parameters} params · [{m.source_id}]</span>
            </div>
            {([["4-bit", m.int4_gb, "from-emerald-400 to-cyan-400"], ["8-bit", m.int8_gb, "from-cyan-400 to-indigo-400"], ["FP16", m.fp16_gb, "from-indigo-400 to-violet-500"]] as const).map(([label, gb, grad]) => (
              <div key={label} className="mb-1 flex items-center gap-3 text-xs">
                <span className="w-10 text-muted">{label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <motion.div
                    className={`h-full rounded-full bg-gradient-to-r ${grad}`}
                    initial={{ width: 0 }}
                    whileInView={{ width: bar(gb) }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.9, ease: "easeOut" }}
                  />
                </div>
                <span className="w-20 text-right font-mono tabular-nums">{gb.toLocaleString()} GB</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function EvaluationTab({ state, sources }: { state: RunState; sources: Source[] }) {
  const e = state.evaluation;
  if (!e) return <Empty text="Evaluation did not run." />;
  return (
    <div className="space-y-6">
      <div className="flex gap-3 rounded-xl border border-indigo-400/25 bg-indigo-500/10 p-4 text-sm text-indigo-100">
        <FlaskConical size={18} className="mt-0.5 shrink-0" />
        {e.disclaimer}
      </div>
      <div className="card p-5">
        <h3 className="mb-3 font-semibold">Reported benchmark results</h3>
        {e.benchmarks.length === 0 ? (
          <p className="text-sm text-muted">No benchmark scores could be verified in the retrieved source text.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead><tr className="text-xs uppercase tracking-wider text-muted">{["Model", "Benchmark", "Metric", "Score", "Reported by", "Source"].map((h) => <th key={h} className="py-2 pr-4 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {e.benchmarks.map((b) => (
                <tr key={`${b.model_name}-${b.benchmark}-${b.score}`} className="border-t border-line/60">
                  <td className="py-2 pr-4">{b.model_name}</td><td className="pr-4">{b.benchmark}</td><td className="pr-4">{b.metric}</td>
                  <td className="pr-4 font-mono">{b.score}</td><td className="pr-4">{b.reported_by}</td>
                  <td><Cited text={`[${b.source_id}]`} sources={sources} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {e.rejected_benchmarks.length > 0 && (
          <p className="mt-3 text-xs text-amber-200">{e.rejected_benchmarks.length} score(s) excluded: not found in the cited source text.</p>
        )}
      </div>
      <MemoryBars state={state} />
      {e.assessments.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {e.assessments.map((a) => (
            <div key={a.model_name} className="card p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="font-medium">{a.model_name}</p>
                <Pill tone={suitabilityTone(a.onprem_suitability)}>on-prem: {a.onprem_suitability}</Pill>
              </div>
              <p className="text-sm text-ink/80"><Cited text={a.rationale} sources={sources} /></p>
              <p className="mt-2 text-xs text-muted">Memory / inference: {a.memory_and_inference}</p>
              {a.quantisation_options.length > 0 && <p className="mt-1 text-xs text-muted">Quantisation: {a.quantisation_options.join(", ")}</p>}
            </div>
          ))}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <ListCard title="Trade-offs" items={e.trade_offs} sources={sources} dot="bg-cyan-400" />
        <ListCard title="Missing evidence" items={e.missing_evidence} sources={sources} dot="bg-amber-400" />
      </div>
    </div>
  );
}

function ReportTab({ state }: { state: RunState }) {
  const r = state.report;
  if (!r) return <Empty text="The report was not generated — see the warnings above." />;
  const download = () => {
    const blob = new Blob([r.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: `research_report_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "")}.md` });
    a.click();
    URL.revokeObjectURL(url);
  };
  const chk = r.citation_check;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={download}
          className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950">
          <Download size={15} /> Download report (.md)
        </motion.button>
        <Pill tone="emerald">{chk.cited?.length ?? 0} sources cited</Pill>
        <Pill tone={(chk.unknown?.length ?? 0) ? "rose" : "emerald"}>{chk.unknown?.length ?? 0} unknown citations</Pill>
        <Pill tone="slate">{r.removed_citations.length} invalid citations removed</Pill>
        <Pill tone="slate">{r.removed_claims?.length ?? 0} misattributed sentences removed</Pill>
        {!r.narrative_generated && <Pill tone="amber">narrative fell back to structured output</Pill>}
      </div>
      <div className="card p-6 sm:p-8"><Markdown text={r.markdown} /></div>
    </div>
  );
}

function ListCard({ title, items, sources, dot }: { title: string; items: string[]; sources: Source[]; dot: string }) {
  return (
    <div className="card p-5">
      <h3 className="mb-3 font-semibold">{title}</h3>
      {items.length === 0 ? <p className="text-sm text-muted">None reported.</p> : (
        <ul className="space-y-2 text-sm text-ink/85">
          {items.map((t) => <li key={t} className="flex gap-2"><span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} /><span><Cited text={t} sources={sources} /></span></li>)}
        </ul>
      )}
    </div>
  );
}

function Notice({ items }: { items: string[] }) {
  return (
    <div className="rounded-xl border border-amber-400/25 bg-amber-500/10 p-4 text-sm text-amber-100">
      <p className="mb-1 flex items-center gap-2 font-medium"><TriangleAlert size={16} /> Warnings from this run</p>
      <ul className="list-disc space-y-0.5 pl-6 text-amber-100/85">{items.map((t) => <li key={t}>{t}</li>)}</ul>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="card p-8 text-center text-sm text-muted">{text}</div>;
}

export function Results() {
  const { result, isExample } = useRun();
  const [tab, setTab] = useState<TabId>("findings");
  if (!result) return null;
  const sources = result.sources ?? [];

  return (
    <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {isExample && (
        <p className="text-xs text-muted">
          Showing the saved example run (<span className="font-mono">outputs/example_run.json</span>) — produced by a real run with{" "}
          <span className="font-mono">{result.model_name}</span>.
        </p>
      )}
      <Metrics state={result} />
      {result.errors.length > 0 && <Notice items={result.errors} />}
      {result.report?.insufficient_evidence && (
        <div className="rounded-xl border border-amber-400/25 bg-amber-500/10 p-4 text-sm text-amber-100">
          No relevant sources were found, so no findings are reported. See the Final Report tab.
        </div>
      )}

      <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line scroll-thin">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`relative flex shrink-0 items-center gap-2 px-4 py-3 text-sm transition-colors ${tab === id ? "text-ink" : "text-muted hover:text-ink"}`}
          >
            <Icon size={15} /> {label}
            {tab === id && (
              <motion.span layoutId="tab-underline" className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-gradient-to-r from-indigo-400 to-cyan-400" />
            )}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.22 }}>
          {tab === "findings" && <FindingsTab state={result} sources={sources} />}
          {tab === "comparison" && <ComparisonTab state={result} sources={sources} />}
          {tab === "evaluation" && <EvaluationTab state={result} sources={sources} />}
          {tab === "report" && <ReportTab state={result} />}
        </motion.div>
      </AnimatePresence>
    </motion.section>
  );
}
