from pathlib import Path
import json

import httpx
import pytest

from modernizer_agent.ai import (
    AIProviderError,
    AIResponseBlockedError,
    AIResponseTruncatedError,
    GeminiClient,
)
from modernizer_agent.config import AgentConfig, GeminiConfig


def make_config(tmp_path: Path, **overrides) -> AgentConfig:
    values = dict(
        endpoint="https://api.genai.mil.test/v1/chat/completions",
        model="google/gemini-3.1-pro",
        api_key_env="GENAI_MIL_API_KEY",
        api_style="genai_mil",
        auth_style="header",
        api_key_header="x-api-key",
        allowed_hosts=["api.genai.mil.test"],
        max_retries=2,
        retry_backoff_seconds=0.0,
    )
    values.update(overrides)
    return AgentConfig(
        repo_root=tmp_path,
        state_dir=tmp_path / ".modernizer",
        gemini=GeminiConfig(**values),
    )


def chat_response(content: str = "ok", finish_reason: str = "stop") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "google/gemini-3.1-pro",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    }


def test_genai_mil_custom_header_and_openai_chat_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("GENAI_MIL_API_KEY", "super-secret")
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            headers={"x-request-id": "req-123"},
            json=chat_response('{"status":"ok"}'),
        )

    client = GeminiClient(make_config(tmp_path), transport=httpx.MockTransport(handler), sleep=lambda _: None)
    assert client.complete("hello", json_mode=True) == '{"status":"ok"}'
    assert seen["auth"] == "super-secret"
    assert seen["body"]["model"] == "google/gemini-3.1-pro"
    assert seen["body"]["messages"][0]["role"] == "system"
    assert "only valid JSON" in seen["body"]["messages"][0]["content"]
    assert seen["body"]["messages"][1] == {"role": "user", "content": "hello"}
    assert seen["body"]["max_tokens"] == 32768
    assert "contents" not in seen["body"]
    assert "generationConfig" not in seen["body"]


def test_retries_429_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("GENAI_MIL_API_KEY", "secret")
    calls = {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=chat_response("ok"))

    client = GeminiClient(make_config(tmp_path), transport=httpx.MockTransport(handler), sleep=lambda _: None)
    assert client.complete("hello") == "ok"
    assert calls["n"] == 2


def test_permanent_error_does_not_leak_key_or_body(tmp_path, monkeypatch):
    monkeypatch.setenv("GENAI_MIL_API_KEY", "do-not-print-me")

    def handler(request: httpx.Request):
        return httpx.Response(401, headers={"x-request-id": "abc"}, text="sensitive upstream message")

    client = GeminiClient(make_config(tmp_path), transport=httpx.MockTransport(handler), sleep=lambda _: None)
    with pytest.raises(AIProviderError) as exc:
        client.complete("proprietary source here")
    message = str(exc.value)
    assert "401" in message and "abc" in message
    assert "do-not-print-me" not in message
    assert "sensitive upstream message" not in message
    assert "proprietary source here" not in message


def test_truncated_and_blocked_responses_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GENAI_MIL_API_KEY", "secret")

    truncated = httpx.MockTransport(lambda req: httpx.Response(
        200, json=chat_response("partial", finish_reason="length")
    ))
    with pytest.raises(AIResponseTruncatedError):
        GeminiClient(make_config(tmp_path), transport=truncated, sleep=lambda _: None).complete("hello")

    blocked = httpx.MockTransport(lambda req: httpx.Response(
        200, json=chat_response("", finish_reason="content_filter")
    ))
    with pytest.raises(AIResponseBlockedError):
        GeminiClient(make_config(tmp_path), transport=blocked, sleep=lambda _: None).complete("hello")


def test_genai_mil_requires_explicit_allowed_host(tmp_path, monkeypatch):
    monkeypatch.setenv("GENAI_MIL_API_KEY", "secret")
    cfg = make_config(tmp_path, allowed_hosts=[])
    with pytest.raises(RuntimeError, match="requires gemini.allowed_hosts"):
        GeminiClient(cfg, transport=httpx.MockTransport(lambda req: httpx.Response(200))).complete("hello")
