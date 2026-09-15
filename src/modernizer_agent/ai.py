from __future__ import annotations

import json
import re
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .config import AgentConfig


class AIProviderError(RuntimeError):
    pass


class AIResponseBlockedError(AIProviderError):
    pass


class AIResponseTruncatedError(AIProviderError):
    pass


class GeminiClient:
    """Completion client for Gemini-shaped APIs, including configurable enterprise gateways.

    Python remains the agent. This class only sends bounded prompts and extracts completion text.
    It intentionally avoids including response bodies or secrets in exceptions.
    """

    def __init__(
        self,
        config: AgentConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self.transport = transport
        self.sleep = sleep

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        cfg = self.config.gemini
        api_key = self.config.api_key()
        endpoint = cfg.endpoint.format(model=cfg.model)
        cfg.validate_endpoint(endpoint)
        headers = {"Content-Type": "application/json"}
        endpoint = self._apply_auth(endpoint, headers, api_key)
        body = self._build_body(prompt, json_mode=json_mode)

        last_exc: Exception | None = None
        with httpx.Client(timeout=cfg.timeout_seconds, transport=self.transport) as client:
            for attempt in range(cfg.max_retries + 1):
                try:
                    response = client.post(endpoint, headers=headers, json=body)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = exc
                    if attempt >= cfg.max_retries:
                        raise AIProviderError(
                            f"AI request failed after {attempt + 1} attempts: {type(exc).__name__}"
                        ) from exc
                    self._backoff(attempt)
                    continue

                request_id = self._request_id(response)
                if response.status_code in cfg.retry_status_codes:
                    if attempt >= cfg.max_retries:
                        raise AIProviderError(
                            f"AI endpoint returned retryable HTTP {response.status_code} after {attempt + 1} attempts"
                            + self._request_id_suffix(request_id)
                        )
                    self._backoff(attempt, response)
                    continue

                if response.is_error:
                    raise AIProviderError(
                        f"AI endpoint returned HTTP {response.status_code}" + self._request_id_suffix(request_id)
                    )

                try:
                    payload = response.json()
                except (ValueError, json.JSONDecodeError) as exc:
                    raise AIProviderError(
                        "AI endpoint returned a non-JSON response" + self._request_id_suffix(request_id)
                    ) from exc
                return self._extract_text(payload, request_id=request_id)

        # Defensive fallback; the loop above always returns or raises.
        raise AIProviderError("AI request failed") from last_exc

    def _build_body(self, prompt: str, *, json_mode: bool) -> dict[str, Any]:
        cfg = self.config.gemini
        if cfg.api_style in {"google", "genai_mil"}:
            body: dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": cfg.temperature,
                    "maxOutputTokens": cfg.max_output_tokens,
                },
            }
            if json_mode:
                body["generationConfig"]["responseMimeType"] = "application/json"
            return body
        if cfg.api_style == "bearer":
            return {
                "model": cfg.model,
                "prompt": prompt,
                "temperature": cfg.temperature,
                "max_tokens": cfg.max_output_tokens,
            }
        return {"prompt": prompt, "model": cfg.model}

    def _apply_auth(self, endpoint: str, headers: dict[str, str], api_key: str) -> str:
        cfg = self.config.gemini
        auth_style = cfg.auth_style
        if auth_style == "auto":
            if cfg.api_style == "google":
                auth_style = "query"
            elif cfg.api_style == "bearer":
                auth_style = "bearer"
            else:
                auth_style = "header"

        if auth_style == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
            return endpoint
        if auth_style == "header":
            headers[cfg.api_key_header] = f"{cfg.api_key_prefix}{api_key}"
            return endpoint
        if auth_style == "query":
            parts = urlsplit(endpoint)
            query = dict(parse_qsl(parts.query, keep_blank_values=True))
            query.setdefault(cfg.api_key_query_param, api_key)
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        raise AIProviderError(f"Unsupported AI auth_style: {auth_style}")

    def _extract_text(self, payload: Any, *, request_id: str | None) -> str:
        cfg = self.config.gemini
        if not isinstance(payload, dict):
            raise AIProviderError("AI response JSON was not an object" + self._request_id_suffix(request_id))

        if cfg.api_style in {"google", "genai_mil"}:
            feedback = payload.get("promptFeedback")
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                raise AIResponseBlockedError(
                    f"AI request was blocked ({feedback.get('blockReason')})" + self._request_id_suffix(request_id)
                )
            try:
                candidate = payload["candidates"][0]
            except (KeyError, IndexError, TypeError) as exc:
                raise AIProviderError(
                    "AI response did not contain a completion candidate" + self._request_id_suffix(request_id)
                ) from exc

            finish_reason = str(candidate.get("finishReason", "")).upper()
            if finish_reason == "MAX_TOKENS":
                raise AIResponseTruncatedError(
                    "AI response was truncated at the output-token limit" + self._request_id_suffix(request_id)
                )
            if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                raise AIResponseBlockedError(
                    f"AI response was blocked ({finish_reason})" + self._request_id_suffix(request_id)
                )
            try:
                text = "".join(
                    part.get("text", "")
                    for part in candidate["content"]["parts"]
                    if isinstance(part, dict)
                ).strip()
            except (KeyError, TypeError) as exc:
                raise AIProviderError(
                    "AI completion candidate had an unexpected shape" + self._request_id_suffix(request_id)
                ) from exc
            if not text:
                raise AIProviderError("AI completion was empty" + self._request_id_suffix(request_id))
            return text

        for key in ("text", "completion", "response", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        raise AIProviderError("Could not find completion text in AI response" + self._request_id_suffix(request_id))

    def _backoff(self, attempt: int, response: httpx.Response | None = None) -> None:
        cfg = self.config.gemini
        retry_after: float | None = None
        if response is not None:
            raw = response.headers.get("Retry-After")
            if raw:
                try:
                    retry_after = max(0.0, float(raw))
                except ValueError:
                    retry_after = None
        delay = retry_after if retry_after is not None else cfg.retry_backoff_seconds * (2 ** attempt)
        self.sleep(delay)

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        for key in ("x-request-id", "request-id", "x-correlation-id", "traceparent"):
            value = response.headers.get(key)
            if value:
                return value[:200]
        return None

    @staticmethod
    def _request_id_suffix(request_id: str | None) -> str:
        return f"; request_id={request_id}" if request_id else ""


def parse_json_response(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min([p for p in (text.find("{"), text.find("[")) if p >= 0], default=-1)
        if start < 0:
            raise
        for end in range(len(text), start, -1):
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                continue
        raise
