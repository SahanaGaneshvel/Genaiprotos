// Thin client for the FastAPI server (api/server.py).
import type { Health, RunState } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const API_START_HINT = "python -m uvicorn api.server:app --port 8000";

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  return `HTTP ${res.status}`;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function getExample(): Promise<RunState> {
  const res = await fetch(`${API_URL}/api/example`, { cache: "no-store" });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

/**
 * Start a research run and read the Server-Sent Events stream.
 *
 * We use fetch + a small parser instead of the browser's EventSource because
 * EventSource hides HTTP errors: with fetch, "a run is already in progress" (409)
 * or "topic too short" (422) reach the user as readable messages.
 */
export async function streamResearch(
  topic: string,
  depth: "basic" | "detailed",
  onEvent: (event: string, data: unknown) => void,
  signal: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams({ topic, depth });
  const res = await fetch(`${API_URL}/api/research/stream?${params}`, {
    signal,
    headers: { Accept: "text/event-stream" },
  });
  if (!res.ok || !res.body) throw new Error(await errorMessage(res));

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    // Each SSE message ends with a blank line: "event: x\ndata: {...}\n\n"
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
        // lines starting with ":" are keep-alive comments
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}
