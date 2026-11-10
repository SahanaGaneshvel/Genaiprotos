"""HTTP API for the Next.js frontend (the Streamlit app does not need it).

    GET /api/health                       Ollama + model status
    GET /api/example                      the saved example run (instant demo)
    GET /api/research/stream?topic=&depth= run the LangGraph workflow, streamed as Server-Sent Events

Why Server-Sent Events? The workflow already emits live events (agent running /
completed / progress messages). SSE pushes each one to the browser the moment it
happens over one long-lived HTTP response — simpler than WebSockets, one direction only,
and the browser's EventSource reconnects automatically.

The workflow is synchronous and CPU-bound, so it runs in a worker thread that puts
events on a queue; the HTTP response reads from that queue. Only one run at a time:
a single local model on a CPU cannot serve two research runs usefully.

Run:  python -m uvicorn api.server:app --port 8000
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import get_settings
from orchestration import workflow
from services.ollama_client import OllamaClient
from utils.helpers import validate_topic

app = FastAPI(title="Multi-Agent AI Research Assistant API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    # the deployed frontend may talk to an API running on the visitor's own machine
    allow_origin_regex=r"https://[a-z0-9-]+\.vercel\.app",
    allow_methods=["GET"],
    allow_headers=["*"],
)

RUN_LOCK = threading.Lock()
KEEPALIVE_SECONDS = 15
EXAMPLE_FILE = get_settings().output_dir / "example_run.json"


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/health")
def health() -> dict:
    ok, message = OllamaClient().check_health()
    return {"ok": ok, "message": message, "model": get_settings().ollama_model}


@app.get("/api/example")
def example() -> dict:
    if not EXAMPLE_FILE.exists():
        raise HTTPException(404, "No example run saved yet.")
    return json.loads(EXAMPLE_FILE.read_text(encoding="utf-8"))


def _run_stream(topic: str, depth: str) -> Iterator[str]:
    events: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            state = workflow.run_workflow(topic, depth, events.put)
            try:
                state["saved"] = workflow.save_run(state)
            except OSError as exc:
                state.setdefault("errors", []).append(f"Could not save outputs: {exc}")
            events.put({"__done__": workflow.to_jsonable(state)})
        except Exception as exc:  # noqa: BLE001 - report any failure to the browser
            events.put({"__error__": str(exc)})
        finally:
            RUN_LOCK.release()

    threading.Thread(target=worker, daemon=True).start()
    yield sse("started", {"topic": topic, "depth": depth, "model": get_settings().ollama_model})
    while True:
        try:
            item = events.get(timeout=KEEPALIVE_SECONDS)
        except queue.Empty:
            yield ": keep-alive\n\n"  # comment line: stops proxies/browsers timing out
            continue
        if "__done__" in item:
            yield sse("done", item["__done__"])
            return
        if "__error__" in item:
            yield sse("error", {"message": item["__error__"]})
            return
        yield sse("agent", item)


@app.get("/api/research/stream")
def research_stream(
    topic: str = Query(..., max_length=1000),
    depth: str = Query("basic", pattern="^(basic|detailed)$"),
) -> StreamingResponse:
    try:
        topic = validate_topic(topic)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not RUN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "A research run is already in progress. Please wait for it to finish.")
    return StreamingResponse(
        _run_stream(topic, depth),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
