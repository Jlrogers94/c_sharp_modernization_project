from __future__ import annotations

import json
import re
from typing import Any
import httpx

from .config import AgentConfig


class GeminiClient:
    """Tiny completion client. Python remains the agent; Gemini only completes prompts."""

    def __init__(self, config: AgentConfig):
        self.config = config

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        cfg = self.config.gemini
        api_key = self.config.api_key()
        endpoint = cfg.endpoint.format(model=cfg.model)
        headers = {"Content-Type": "application/json"}

        if cfg.api_style == "google":
            # Works with the Google Generative Language generateContent shape and with
            # many enterprise gateways that proxy that API unchanged.
            if "key=" not in endpoint:
                join = "&" if "?" in endpoint else "?"
                endpoint = f"{endpoint}{join}key={api_key}"
            body: dict[str, Any] = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": cfg.temperature,
                    "maxOutputTokens": cfg.max_output_tokens,
                },
            }
            if json_mode:
                body["generationConfig"]["responseMimeType"] = "application/json"
        elif cfg.api_style == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
            body = {"model": cfg.model, "prompt": prompt, "temperature": cfg.temperature, "max_tokens": cfg.max_output_tokens}
        else:
            headers["X-API-Key"] = api_key
            body = {"prompt": prompt, "model": cfg.model}

        with httpx.Client(timeout=cfg.timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()

        if cfg.api_style == "google":
            try:
                return "".join(part.get("text", "") for part in payload["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Unexpected Gemini response shape: {payload}") from exc
        for key in ("text", "completion", "response", "content"):
            if isinstance(payload.get(key), str):
                return payload[key]
        raise RuntimeError(f"Could not find completion text in response: {payload}")


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
