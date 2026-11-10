"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders the Report Agent's Markdown (GitHub-flavoured: tables, autolinks). */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="report">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a> }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
