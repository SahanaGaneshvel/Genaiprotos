"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { RunState } from "@/lib/types";
import { Markdown } from "../markdown";

export function ReportView({ result }: { result: RunState }) {
  const [open, setOpen] = useState(false);
  const report = result.report;
  if (!report) return null;

  const download = () => {
    const url = URL.createObjectURL(new Blob([report.markdown], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "research-report.md" });
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="border-t border-ink pt-8"
    >
      <h2 className="font-serif text-3xl">The report</h2>
      <p className="mt-2 max-w-xl text-ink-2">
        {report.insufficient_evidence
          ? "No relevant sources were found, so the report says so instead of guessing."
          : `Ten sections, ${report.citation_check.cited?.length ?? 0} sources cited, and every link in it was actually retrieved.`}
      </p>
      <div className="mt-5 flex flex-wrap gap-5 text-[0.92rem]">
        <button type="button" onClick={() => setOpen((o) => !o)} className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink">
          {open ? "Hide the report" : "Read the report"}
        </button>
        <button type="button" onClick={download} className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink">
          Download as Markdown
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
            <div className="mt-8 rounded-sm border border-line bg-card px-6 py-8 sm:px-10">
              <Markdown text={report.markdown} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
}
