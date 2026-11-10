"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { domain, duration, explain, type Row } from "@/lib/flow";

const WHO_LABEL = { model: "the local model", code: "plain code", api: "a public API" } as const;

function Q({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[0.82em] text-ink">“{children}”</span>;
}

function Id({ id }: { id: string }) {
  return <span className="mr-1.5 font-mono text-[0.78em] text-muted">{id}</span>;
}

function List({ items, struck = false }: { items: React.ReactNode[]; struck?: boolean }) {
  return (
    <ul className="mt-1.5 space-y-1">
      {items.map((item, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className={`text-[0.85rem] leading-snug ${struck ? "text-muted line-through decoration-muted/60" : "text-ink-2"}`}
        >
          {item}
        </motion.li>
      ))}
    </ul>
  );
}

/** What the row says, in plain words, with its real data. */
function Body({ row }: { row: Row }) {
  const d = row.data;
  const busy = row.open;
  switch (row.kind) {
    case "plan":
      if (busy) return <p>Asking the model to plan the searches…</p>;
      return (
        <>
          <p>Planned the searches{d.fallback ? " (the model's plan failed, so a keyword plan was used)" : ""}.</p>
          <List items={[
            ...(d.web_queries ?? []).map((q: string) => <>Web <Q>{q}</Q></>),
            <>arXiv <Q>{d.arxiv_query}</Q></>,
            <>GitHub <Q>{d.github_query}</Q></>,
            <>Hugging Face — trending <span className="font-mono text-[0.82em]">{d.hub_task}</span> models</>,
          ]} />
        </>
      );
    case "search": {
      const name = d.tool === "web" ? "the web" : d.tool;
      if (busy) return <p>Searching {name} for <Q>{d.query}</Q>…</p>;
      const results: { title: string; url: string }[] = d.results ?? [];
      return (
        <>
          <p>
            Searched {name} for <Q>{d.query}</Q> —{" "}
            {results.length ? `${results.length} result${results.length > 1 ? "s" : ""}` : <span className="text-muted">nothing came back{d.error ? ` (${d.error})` : ""}</span>}
          </p>
          {results.length > 0 && (
            <List items={results.map((r) => (
              <a key={r.url} href={r.url} target="_blank" rel="noreferrer" className="hover:text-accent hover:underline">
                {r.title} <span className="text-muted">· {domain(r.url)}</span>
              </a>
            ))} />
          )}
        </>
      );
    }
    case "fetch":
      if (busy) return <p>Opening {domain(d.url)}…</p>;
      return d.ok ? (
        <p>Read the page at {domain(d.url)} <span className="text-muted">· {Number(d.chars).toLocaleString()} characters kept</span></p>
      ) : (
        <p>{domain(d.url)} wouldn&apos;t load <span className="text-muted">— keeping the search snippet instead</span></p>
      );
    case "register": {
      const sources: { id: string; title: string; url: string }[] = d.sources ?? [];
      return (
        <>
          <p>{sources.length} unique sources, numbered so they can be cited.</p>
          <List items={sources.map((s) => (
            <a key={s.id} href={s.url} target="_blank" rel="noreferrer" className="hover:text-accent hover:underline">
              <Id id={s.id} />{s.title}
            </a>
          ))} />
        </>
      );
    }
    case "read":
      if (busy) return <p>Reading <Id id={d.source_id} />{d.title}…</p>;
      if (!d.kept) return <p className="text-muted"><Id id={d.source_id} /><span className="line-through">{d.title}</span> — set aside, nothing relevant</p>;
      return (
        <>
          <p><Id id={d.source_id} />{d.title} {d.fallback ? <span className="text-muted">— the model&apos;s answer was unusable, so the snippet was kept</span> : <span className="text-muted">— kept</span>}</p>
          {(d.facts ?? []).length > 0 && <List items={d.facts} />}
        </>
      );
    case "candidates":
      return <p>Found {(d.candidates ?? []).length} model names in the research <span className="text-muted">— {(d.candidates ?? []).slice(0, 8).join(", ")}</span></p>;
    case "selected":
      return (
        <p>
          Comparing <span className="font-medium text-ink">{(d.models ?? []).join(", ")}</span>
          {(d.guaranteed ?? []).length > 0 && <span className="text-muted"> — {(d.guaranteed as string[]).join(" and ")} {d.guaranteed.length > 1 ? "have" : "has"} an official model card, so {d.guaranteed.length > 1 ? "they're" : "it's"} always included</span>}
        </p>
      );
    case "row": {
      if (busy) return <p>Filling in <span className="font-medium text-ink">{d.model}</span> from {d.evidence_lines} lines of evidence…</p>;
      const known = (v: unknown) => typeof v === "string" && v.trim() !== "" && !/^not (documented|specified|stated)/i.test(v);
      const facts = [
        known(d.parameters) && d.parameters,
        known(d.context) && `context ${d.context}`,
        (d.modalities ?? []).join(" + "),
      ].filter(Boolean);
      return (
        <div className="grid gap-x-6 gap-y-0.5 sm:grid-cols-[minmax(0,11rem)_1fr]">
          <span className="font-medium text-ink">{d.model}</span>
          <span className="text-ink-2">
            {facts.join(" · ") || <span className="text-muted">size not documented</span>}
            <span className="block text-[0.8rem] text-muted">
              licence: {known(d.licence) ? `${d.licence} — ${String(d.licence_category).toLowerCase()}` : "not documented"}{" "}
              <span className="font-mono">{(d.source_ids ?? []).map((s: string) => `[${s}]`).join("")}</span>
            </span>
          </span>
        </div>
      );
    }
    case "row_dropped":
      return <p className="text-muted"><span className="line-through">{d.model}</span> — no source supports it, dropped</p>;
    case "differences":
      if (busy) return <p>Writing down the key differences…</p>;
      return (
        <>
          <p>Key differences</p>
          <List items={(d.sentences ?? []).map((s: string) => s)} />
        </>
      );
    case "evaluate":
      if (busy) return <p>Looking for benchmark scores and judging what could run on your own hardware…</p>;
      return <p>Evaluated the evidence for {(d.models ?? []).length || "the"} models.</p>;
    case "verify":
      return (
        <>
          <p>
            Checked every benchmark score against its source — {d.proposed} proposed, {(d.verified ?? []).length} confirmed
            {(d.rejected ?? []).length > 0 && `, ${(d.rejected ?? []).length} rejected`}.
          </p>
          {(d.verified ?? []).length > 0 && <List items={d.verified} />}
          {(d.rejected ?? []).length > 0 && <List items={d.rejected} struck />}
        </>
      );
    case "memory": {
      const est: { model: string; parameters: string; int4_gb: number }[] = d.estimates ?? [];
      if (!est.length) return <p className="text-muted">No parameter counts available, so no memory estimate.</p>;
      const max = Math.log10(Math.max(...est.map((e) => e.int4_gb)) + 1);
      return (
        <>
          <p>Memory needed just for the weights at 4-bit <span className="text-muted">(estimate)</span></p>
          <div className="mt-2 space-y-1.5">
            {est.map((e, i) => (
              <div key={e.model} className="grid grid-cols-[minmax(0,10rem)_1fr_5.5rem] items-center gap-3 text-[0.82rem]">
                <span className="truncate text-ink-2" title={e.model}>{e.model.split("/").at(-1)}</span>
                <span className="h-[3px] bg-line">
                  <motion.span
                    className="block h-full bg-ink"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(2, (Math.log10(e.int4_gb + 1) / max) * 100)}%` }}
                    transition={{ duration: 0.8, delay: i * 0.1 }}
                  />
                </span>
                <span className="text-right font-mono text-ink">{e.int4_gb.toLocaleString()} GB</span>
              </div>
            ))}
          </div>
        </>
      );
    }
    case "narrative":
      return busy ? <p>The model is writing the report…</p> : <p>Report narrative written.</p>;
    case "attribution":
      return (
        <>
          <p>Checked each sentence against the sources it cites — {(d.removed ?? []).length ? `${d.removed.length} removed` : "nothing to remove"}.</p>
          {(d.removed ?? []).length > 0 && <List items={d.removed} struck />}
        </>
      );
    case "assemble":
      return (
        <p>
          Report put together — {d.sections} sections, {(d.cited ?? []).length} sources cited,{" "}
          {(d.unknown ?? []).length} unknown citations.
        </p>
      );
  }
}

export function RowView({ row, now, model }: { row: Row; now: number; model: string }) {
  const [open, setOpen] = useState(false);
  const info = explain(row);
  const took = row.tEnd != null ? row.tEnd - row.t : now - row.t;
  const who = info.who === "model" ? `the local model, ${model}` : info.whoLabel ?? WHO_LABEL[info.who];

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="relative pl-6"
    >
      <span className="absolute left-0 top-[0.55rem] flex h-2 w-2 items-center justify-center">
        {row.open ? (
          <>
            <span className="absolute h-2 w-2 animate-ping rounded-full bg-accent/50" />
            <span className="h-2 w-2 rounded-full bg-accent" />
          </>
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-ink/70" />
        )}
      </span>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="group w-full text-left text-[0.92rem] leading-relaxed text-ink-2"
        aria-expanded={open}
      >
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1"><Body row={row} /></div>
          <span className="shrink-0 pt-0.5 font-mono text-[0.72rem] text-muted opacity-0 transition group-hover:opacity-100">
            {open ? "close" : "how?"}
          </span>
        </div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <p className="mt-2 border-l border-line pl-3 text-[0.85rem] leading-relaxed text-ink-2">
              <span className="text-ink">Done by {who}</span>
              {info.who === "model" && <span className="text-muted"> (through Ollama, on the machine running the agents)</span>}
              {took > 0.5 && <span className="text-muted"> · {row.open ? "running for" : "took"} {duration(took)}</span>}
              <br />
              {info.text}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}
