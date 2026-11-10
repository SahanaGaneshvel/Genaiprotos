"""Ollama client tests: all HTTP calls are mocked, no server needed."""

import json
from unittest.mock import MagicMock

import pytest
import requests
from pydantic import BaseModel

from services import ollama_client as oc
from utils.helpers import extract_json


class Answer(BaseModel):
    answer: str
    confidence: float


def _resp(status: int, body: dict | str):
    r = MagicMock()
    r.status_code = status
    r.text = body if isinstance(body, str) else json.dumps(body)
    r.json.return_value = body if isinstance(body, dict) else {}
    return r


def _chat_reply(content: str):
    return _resp(200, {"message": {"role": "assistant", "content": content}})


def test_structured_output_is_validated(monkeypatch):
    monkeypatch.setattr(oc.requests, "post", lambda *a, **k: _chat_reply('{"answer": "hi", "confidence": 0.9}'))
    result = oc.OllamaClient().chat_structured("sys", "user", Answer)
    assert result == Answer(answer="hi", confidence=0.9)


def test_malformed_output_retries_then_succeeds(monkeypatch):
    replies = iter([_chat_reply("sorry, not json"), _chat_reply('{"answer": "ok", "confidence": 1}')])
    post = MagicMock(side_effect=lambda *a, **k: next(replies))
    monkeypatch.setattr(oc.requests, "post", post)
    result = oc.OllamaClient().chat_structured("sys", "user", Answer, retries=1)
    assert result.answer == "ok"
    # the retry prompt tells the model what was wrong
    assert "previous reply was invalid" in post.call_args.kwargs["json"]["messages"][1]["content"]


def test_malformed_output_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(oc.requests, "post", lambda *a, **k: _chat_reply('{"answer": "missing confidence"}'))
    with pytest.raises(oc.OllamaResponseError):
        oc.OllamaClient().chat_structured("sys", "user", Answer, retries=1)


def test_missing_model_raises_model_not_found(monkeypatch):
    monkeypatch.setattr(oc.requests, "post", lambda *a, **k: _resp(404, {"error": "model 'x' not found"}))
    with pytest.raises(oc.OllamaModelNotFoundError):
        oc.OllamaClient().chat("sys", "user")


def test_out_of_memory_gives_actionable_message(monkeypatch):
    body = {"error": "llama-server reported out-of-memory during startup: failed to allocate buffer"}
    monkeypatch.setattr(oc.requests, "post", lambda *a, **k: _resp(500, body))
    with pytest.raises(oc.OllamaOutOfMemoryError, match="smaller model"):
        oc.OllamaClient().chat("sys", "user")


def test_connection_failure_raises_connection_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(oc.requests, "post", boom)
    with pytest.raises(oc.OllamaConnectionError):
        oc.OllamaClient().chat("sys", "user")


def test_health_check_reports_missing_model(monkeypatch):
    monkeypatch.setattr(oc.requests, "get", lambda *a, **k: _resp(200, {"models": [{"name": "llama3.2:3b"}]}))
    client = oc.OllamaClient()
    client.model = "qwen3.5:4b"
    ok, msg = client.check_health()
    assert not ok and "ollama pull qwen3.5:4b" in msg


def test_cloud_models_are_refused(monkeypatch):
    post = MagicMock()
    monkeypatch.setattr(oc.requests, "post", post)
    client = oc.OllamaClient()
    client.model = "gpt-oss:120b-cloud"
    with pytest.raises(oc.OllamaModelNotFoundError, match="cloud"):
        client.chat("sys", "user")
    post.assert_not_called()  # nothing is ever sent off the machine
    assert client.check_health()[0] is False


def test_health_check_server_down(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(oc.requests, "get", boom)
    ok, msg = oc.OllamaClient().check_health()
    assert not ok and "Cannot reach Ollama" in msg


def test_schema_refs_are_inlined():
    class Inner(BaseModel):
        x: int

    class Outer(BaseModel):
        items: list[Inner]

    schema = oc._inline_refs(Outer.model_json_schema())
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here you go: {"a": 1} hope it helps',
        '<think>hmm</think>{"a": 1}',
    ],
)
def test_extract_json_handles_common_llm_noise(raw):
    assert extract_json(raw) == {"a": 1}


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        extract_json("no json here")
