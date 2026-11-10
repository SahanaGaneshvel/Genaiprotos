"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getHealth, streamResearch } from "./api";
import type { FlowEvent, Health, RunState } from "./types";

export type Mode = "idle" | "replay" | "live";
export const SPEEDS = [10, 30, 100] as const;

/**
 * Drives the page in two modes that render identically:
 *  - replay: a recorded real run (public/recorded-run.json) played back with its real
 *            timing, sped up. This is what the deployed site shows;
 *  - live:   a new run streamed from the local API (only offered when the page itself
 *            is served from localhost, so visitors never get a local-network prompt).
 */
export function useFlowRun() {
  const [mode, setMode] = useState<Mode>("idle");
  const [recorded, setRecorded] = useState<RunState | null>(null);
  const [clock, setClock] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<number>(30);
  const [liveEvents, setLiveEvents] = useState<FlowEvent[]>([]);
  const [liveState, setLiveState] = useState<RunState | null>(null);
  const [liveNow, setLiveNow] = useState(0);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const clockRef = useRef(0);

  // The recorded run (also gives the page its default question).
  // ?replay=play starts the replay straight away; ?replay=end opens it finished (shareable links).
  useEffect(() => {
    fetch("/recorded-run.json")
      .then((r) => r.json())
      .then((data: RunState) => {
        setRecorded(data);
        const param = new URLSearchParams(window.location.search).get("replay");
        if (!param) return;
        setMode("replay");
        if (param === "end") {
          clockRef.current = data.events?.at(-1)?.t ?? 0;
          setClock(clockRef.current);
        } else {
          setPlaying(true);
        }
      })
      .catch(() => setError("Could not load the recorded run."));
  }, []);

  // Live mode is only offered when running locally.
  useEffect(() => {
    if (!["localhost", "127.0.0.1"].includes(window.location.hostname)) return;
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const end = useMemo(() => recorded?.events?.at(-1)?.t ?? 0, [recorded]);

  // Replay clock: advances by real elapsed time × speed on every animation frame, but only
  // re-renders when a new event becomes due or every 250 ms (for the time display).
  // Re-rendering 60×/s kept restarting the entrance animations and wasted CPU.
  useEffect(() => {
    if (mode !== "replay" || !playing) return;
    const times = (recorded?.events ?? []).map((e) => e.t);
    let last = performance.now();
    let lastRender = 0;
    let frame = requestAnimationFrame(function tick(now) {
      const prev = clockRef.current;
      clockRef.current = Math.min(prev + ((now - last) / 1000) * speed, end);
      last = now;
      const crossed = times.some((t) => t > prev && t <= clockRef.current);
      if (crossed || now - lastRender > 250 || clockRef.current >= end) {
        lastRender = now;
        setClock(clockRef.current);
      }
      if (clockRef.current >= end) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [mode, playing, speed, end, recorded]);

  // Live clock for "in progress for N s" labels.
  useEffect(() => {
    if (mode !== "live" || liveState) return;
    const startedAt = Date.now();
    const id = setInterval(() => setLiveNow((Date.now() - startedAt) / 1000), 1000);
    return () => clearInterval(id);
  }, [mode, liveState]);

  const replay = useCallback(() => {
    abortRef.current?.abort();
    setError(null);
    setMode("replay");
    clockRef.current = 0;
    setClock(0);
    setPlaying(true);
  }, []);

  const skipToEnd = useCallback(() => {
    clockRef.current = end;
    setClock(end);
    setPlaying(false);
  }, [end]);

  const runLive = useCallback((topic: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setMode("live");
    setLiveEvents([]);
    setLiveState(null);
    setLiveNow(0);
    setError(null);
    streamResearch(topic, "basic", (event, data) => {
      if (event === "agent") setLiveEvents((prev) => [...prev, data as FlowEvent]);
      else if (event === "done") {
        const state = data as RunState;
        setLiveState(state);
        if (state.abort_reason) setError(state.abort_reason);
      } else if (event === "error") setError((data as { message: string }).message);
    }, controller.signal).catch((err: Error) => {
      if (!controller.signal.aborted) setError(err.message || "Lost the connection to the local API.");
    });
  }, []);

  const events = useMemo(
    () => (mode === "replay" ? (recorded?.events ?? []).filter((e) => e.t <= clock) : mode === "live" ? liveEvents : []),
    [mode, recorded, clock, liveEvents],
  );

  const finished = mode === "replay" ? end > 0 && clock >= end : mode === "live" ? liveState != null : false;
  const result = mode === "replay" ? recorded : liveState;

  return {
    mode, recorded, health, error, events, finished, result,
    now: mode === "replay" ? clock : liveNow,
    end, playing, speed,
    liveAvailable: health?.ok === true,
    replay, runLive, skipToEnd,
    togglePlay: () => setPlaying((p) => !p),
    setSpeed,
  };
}
