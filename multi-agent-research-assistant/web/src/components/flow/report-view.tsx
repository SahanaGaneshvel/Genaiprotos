"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { RunState } from "@/lib/types";
import { Markdown } from "../markdown";

/** The finished report: read inline or download. `compact` drops the heading (used inside a details card). */
export function ReportView({ result, compact = false }: { result: RunState; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const report = result.report;
  if (!report) return null;

  const download = () => {
    const url = URL.createObjectURL(new Blob([report.markdown], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "research-report.md" });
    a.click();
    URL.revokeObjectURL(url);
  };

  const summary = report.insufficient_evidence
    ? "No useful sources were found, so the report says so instead of guessing."
    : `Ten sections, ${report.citation_check.cited?.length ?? 0} sources cited, and every link in it was actually opened.`;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={compact ? "" : "border-t border-ink pt-8"}
    >
      {!compact && <h2 className="font-serif text-3xl">The report is ready</h2>}
      <p className={`max-w-xl text-ink-2 ${compact ? "text-[0.92rem]" : "mt-2"}`}>{summary}</p>
      <div className="mt-4 flex flex-wrap gap-5 text-[0.92rem]">
        <button type="button" onClick={() => setOpen((o) => !o)} className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink">
          {open ? "Hide the report" : "Read the report"}
        </button>
        <button type="button" onClick={download} className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink">
          Download
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className={`mt-6 rounded-sm border border-line bg-card ${compact ? "px-4 py-5" : "px-6 py-8 sm:px-10"}`}>
              <Markdown text={report.markdown} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}
