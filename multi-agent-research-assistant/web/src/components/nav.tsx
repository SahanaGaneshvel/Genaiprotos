"use client";

import { Network } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useRun } from "./run-provider";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/architecture", label: "Architecture" },
  { href: "/about", label: "About" },
] as const;

export function Nav() {
  const pathname = usePathname();
  const { health, phase, agents } = useRun();
  const running = Object.entries(agents).find(([, a]) => a.status === "running")?.[0];

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/70 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400 text-slate-950 shadow-lg shadow-indigo-500/30">
            <Network size={17} strokeWidth={2.4} />
          </span>
          <span className="hidden sm:inline">Research Agents</span>
        </Link>

        <ul className="flex items-center gap-1 text-sm">
          {LINKS.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <li key={href} className="relative">
                <Link
                  href={href}
                  className={`relative z-10 block rounded-full px-3.5 py-1.5 transition-colors ${
                    active ? "text-ink" : "text-muted hover:text-ink"
                  }`}
                >
                  {label}
                </Link>
                {active && (
                  <motion.span
                    layoutId="nav-pill"
                    className="absolute inset-0 rounded-full border border-line-strong bg-surface-2"
                    transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  />
                )}
              </li>
            );
          })}
        </ul>

        <div className="ml-auto flex items-center gap-3 text-xs">
          {phase === "running" && (
            <Link href="/" className="hidden items-center gap-2 rounded-full border border-indigo-400/30 bg-indigo-500/10 px-3 py-1 text-indigo-200 md:flex">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-400" />
              </span>
              {running ? `${running[0].toUpperCase()}${running.slice(1)} agent running` : "Run in progress"}
            </Link>
          )}
          <span className="flex items-center gap-2 rounded-full border border-line px-3 py-1 text-muted" title={health?.message}>
            <span
              className={`h-2 w-2 rounded-full ${health == null ? "bg-slate-500" : health.ok ? "bg-emerald-400" : "bg-rose-400"}`}
            />
            <span className="font-mono text-ink/90">{health?.model ?? "…"}</span>
            <span className="hidden lg:inline">· local via Ollama</span>
          </span>
        </div>
      </nav>
    </header>
  );
}
