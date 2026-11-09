import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Nav } from "@/components/nav";
import { RunProvider } from "@/components/run-provider";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Multi-Agent AI Research Assistant", template: "%s · Multi-Agent AI Research Assistant" },
  description:
    "Four specialised AI agents — Research, Comparison, Evaluation and Report — orchestrated with LangGraph and a local LLM produce a cited technical report.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="relative min-h-full flex flex-col overflow-x-hidden">
        {/* animated backdrop */}
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
          <div className="backdrop-grid absolute inset-0" />
          <div className="orb -top-40 -left-32 h-[28rem] w-[28rem] bg-indigo-600" />
          <div className="orb top-1/3 -right-40 h-[26rem] w-[26rem] bg-cyan-600" style={{ animationDelay: "-8s" }} />
          <div className="orb bottom-0 left-1/3 h-[22rem] w-[22rem] bg-violet-700" style={{ animationDelay: "-14s" }} />
        </div>
        <RunProvider>
          <Nav />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-line py-6 text-center text-xs text-muted">
            Local-first POC · LangGraph · Ollama · FastAPI · Next.js — no paid APIs, inference never leaves this machine.
          </footer>
        </RunProvider>
      </body>
    </html>
  );
}
