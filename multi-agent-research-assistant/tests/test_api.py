"""FastAPI tests: health, example, streaming events, validation, one-run-at-a-time."""

import json

import pytest
from fastapi.testclient import TestClient

from api import server
from services.ollama_client import OllamaClient


@pytest.fixture
def client():
    return TestClient(server.app)


def _events(body: str) -> list[tuple[str, dict]]:
    out = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health_reports_model_and_status(client, monkeypatch):
    monkeypatch.setattr(OllamaClient, "check_health", lambda self: (False, "Cannot reach Ollama"))
    body = client.get("/api/health").json()
    assert body["ok"] is False and "Cannot reach Ollama" in body["message"] and body["model"]


def test_example_run_is_served(client):
    body = client.get("/api/example").json()
    assert "## 10. References" in body["report"]["markdown"]
    assert set(body["agent_status"]) == {"research", "comparison", "evaluation", "report"}


def test_stream_sends_live_agent_events_then_final_state(client, monkeypatch):
    def fake_run(topic, depth, on_event):
        on_event({"agent": "research", "status": "running"})
        on_event({"agent": "research", "message": "Searching arXiv"})
        on_event({"agent": "research", "status": "completed", "seconds": 1.0})
        return {"topic": topic, "agent_status": {"research": "completed"}}

    monkeypatch.setattr(server.workflow, "run_workflow", fake_run)
    monkeypatch.setattr(server.workflow, "save_run", lambda s: {"json": "x.json"})
    resp = client.get("/api/research/stream", params={"topic": "open multimodal models on-prem"})
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _events(resp.text)
    assert [e for e, _ in events] == ["started", "agent", "agent", "agent", "done"]
    assert events[2][1] == {"agent": "research", "message": "Searching arXiv"}
    assert events[-1][1]["saved"] == {"json": "x.json"}
    assert not server.RUN_LOCK.locked()  # released after the run


def test_workflow_crash_is_reported_as_error_event(client, monkeypatch):
    def boom(topic, depth, on_event):
        raise RuntimeError("disk full")

    monkeypatch.setattr(server.workflow, "run_workflow", boom)
    events = _events(client.get("/api/research/stream", params={"topic": "open multimodal models"}).text)
    assert events[-1] == ("error", {"message": "disk full"})
    assert not server.RUN_LOCK.locked()


def test_invalid_topic_and_depth_rejected(client):
    assert client.get("/api/research/stream", params={"topic": "hi"}).status_code == 422
    assert client.get("/api/research/stream", params={"topic": "valid topic here", "depth": "deep"}).status_code == 422


def test_only_one_run_at_a_time(client):
    server.RUN_LOCK.acquire()
    try:
        resp = client.get("/api/research/stream", params={"topic": "open multimodal models"})
        assert resp.status_code == 409
    finally:
        server.RUN_LOCK.release()
