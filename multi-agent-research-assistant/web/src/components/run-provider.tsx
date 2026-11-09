"use client";

// Holds the research run for the whole app. It lives in the root layout, so a run
// keeps streaming while you browse the About or Architecture pages (Next.js hides
// inactive pages with <Activity> and cleans up their effects — a stream owned by a
// page would be cut off).

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { API_START_HINT, API_URL, getExample, getHealth, streamResearch } from "@/lib/api";
import type { AgentEvent, AgentName, AgentStatus, Health, RunState } from "@/lib/types";

export const AGENTS: AgentName[] = ["research", "comparison", "evaluation", "report"];

export interface AgentView {
  status: AgentStatus;
  seconds?: number;
  detail?: string;
}

export interface LogLine {
  id: number;
  time: string;
  agent: AgentName;
  text: string;
}

type Phase = "idle" | "running" | "done" | "error";

interface RunContextValue {
  health: Health | null;
  apiReachable: boolean;
  phase: Phase;
  agents: Record<AgentName, AgentView>;
  log: LogLine[];
  result: RunState | null;
  error: string | null;
  isExample: boolean;
  startedAt: number | null;
  start: (topic: string, depth: "basic" | "detailed") => void;
  cancel: () => void;
  loadExample: () => Promise<void>;
  reset: () => void;
}

const RunContext = createContext<RunContextValue | null>(null);

const pendingAgents = (): Record<AgentName, AgentView> =>
  Object.fromEntries(AGENTS.map((a) => [a, { status: "pending" as AgentStatus }])) as Record<AgentName, AgentView>;

function agentsFromState(state: RunState): Record<AgentName, AgentView> {
  return Object.fromEntries(
    AGENTS.map((a) => [a, { status: state.agent_status[a] ?? "pending", seconds: state.timings[a] }]),
  ) as Record<AgentName, AgentView>;
}

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [apiReachable, setApiReachable] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [agents, setAgents] = useState(pendingAgents);
  const [log, setLog] = useState<LogLine[]>([]);
  const [result, setResult] = useState<RunState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExample, setIsExample] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const logId = useRef(0);

  // Health polling (every 20 s while idle).
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) {
          setHealth(h);
          setApiReachable(true);
        }
      } catch {
        if (!cancelled) {
          setApiReachable(false);
          setHealth({
            ok: false,
            model: "unknown",
            message: `API server not reachable at ${API_URL}. Start it with: ${API_START_HINT}`,
          });
        }
      }
    };
    check();
    const timer = setInterval(() => phase !== "running" && check(), 20000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [phase]);

  const pushLog = useCallback((agent: AgentName, text: string) => {
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLog((prev) => [...prev.slice(-60), { id: logId.current++, time, agent, text }]);
  }, []);

  const handleEvent = useCallback(
    (event: string, data: unknown) => {
      if (event === "agent") {
        const ev = data as AgentEvent;
        setAgents((prev) => ({
          ...prev,
          [ev.agent]: {
            status: ev.status ?? prev[ev.agent].status,
            seconds: ev.seconds ?? prev[ev.agent].seconds,
            detail: ev.message ?? (ev.status === "running" ? "Starting…" : prev[ev.agent].detail),
          },
        }));
        if (ev.message) pushLog(ev.agent, ev.message);
        else if (ev.status && ev.status !== "running")
          pushLog(ev.agent, `${ev.status}${ev.seconds != null ? ` in ${ev.seconds.toFixed(1)} s` : ""}`);
      } else if (event === "done") {
        const state = data as RunState;
        setResult(state);
        setAgents(agentsFromState(state));
        setError(state.abort_reason ?? null);
        setPhase(state.abort_reason ? "error" : "done");
      } else if (event === "error") {
        setError((data as { message: string }).message);
        setPhase("error");
      }
    },
    [pushLog],
  );

  const start = useCallback(
    (topic: string, depth: "basic" | "detailed") => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setPhase("running");
      setAgents(pendingAgents());
      setLog([]);
      setResult(null);
      setError(null);
      setIsExample(false);
      setStartedAt(Date.now());
      streamResearch(topic, depth, handleEvent, controller.signal)
        .then(() => setPhase((p) => (p === "running" ? "error" : p)))
        .catch((err: Error) => {
          if (controller.signal.aborted) return;
          setError(err.message || "Connection to the API was lost.");
          setPhase("error");
        });
    },
    [handleEvent],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    setError("Stopped watching this run. The server finishes the current run in the background.");
  }, []);

  const loadExample = useCallback(async () => {
    try {
      const state = await getExample();
      setResult(state);
      setAgents(agentsFromState(state));
      setLog([]);
      setError(null);
      setIsExample(true);
      setStartedAt(null);
      setPhase("done");
    } catch (err) {
      setError(`Could not load the example run: ${(err as Error).message}`);
      setPhase("error");
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    setAgents(pendingAgents());
    setLog([]);
    setResult(null);
    setError(null);
    setIsExample(false);
    setStartedAt(null);
  }, []);

  return (
    <RunContext.Provider
      value={{ health, apiReachable, phase, agents, log, result, error, isExample, startedAt, start, cancel, loadExample, reset }}
    >
      {children}
    </RunContext.Provider>
  );
}

export function useRun(): RunContextValue {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside <RunProvider>");
  return ctx;
}
