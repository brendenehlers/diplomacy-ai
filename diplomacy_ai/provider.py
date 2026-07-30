"""OpenAI-SDK async wrapper for the ngrok AI Gateway.

The ONLY module that imports the openai SDK.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Awaitable, Callable, Protocol

from openai import AsyncOpenAI

from .models import Completion

DEFAULT_BASE_URL = "https://gateway.ngrok.ai/v1"


class ProviderError(Exception):
    """Raised when a completion fails after all retries."""


class Provider(Protocol):
    async def complete(
        self, *, model: str, system: str, user: str, schema: dict,
        schema_name: str, temperature: float, timeout: int,
    ) -> Completion: ...


class OpenAIProvider:
    def __init__(
        self,
        completion_fn: Callable[..., Awaitable[Any]] | None = None,
        retries: int = 2,
        backoff_base: float = 2.0,
    ):
        if completion_fn is None:
            api_key = os.environ.get("NGROK_API_KEY")
            if not api_key:
                raise ProviderError(
                    "NGROK_API_KEY is not set. Add it to .env (see .env.example) "
                    "or export it before running."
                )
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=os.environ.get("NGROK_BASE_URL", DEFAULT_BASE_URL),
            )
            completion_fn = client.chat.completions.create
        self._completion_fn = completion_fn
        self._retries = retries
        self._backoff_base = backoff_base

    async def complete(
        self, *, model: str, system: str, user: str, schema: dict,
        schema_name: str, temperature: float, timeout: int,
    ) -> Completion:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        }
        last_err: Exception | None = None
        for attempt in range(self._retries + 1):
            start = time.perf_counter()
            try:
                resp = await self._completion_fn(
                    model=model, messages=messages,
                    response_format=response_format,
                    temperature=temperature, timeout=timeout,
                )
                content = resp.choices[0].message.content
                data = json.loads(content)
                meta = self._extract_meta(resp, model, time.perf_counter() - start)
                return Completion(data=data, meta=meta)
            except Exception as e:  # network errors, JSON errors, etc.
                last_err = e
                if attempt < self._retries and self._backoff_base:
                    await asyncio.sleep(self._backoff_base ** attempt)
        raise ProviderError(
            f"completion failed after {self._retries + 1} attempts: {last_err}"
        )

    def _extract_meta(self, resp: Any, model: str, latency: float) -> dict:
        meta: dict[str, Any] = {"model": model, "latency": round(latency, 3)}
        usage = getattr(resp, "usage", None)
        if usage is not None:
            meta["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
            meta["completion_tokens"] = getattr(usage, "completion_tokens", None)
        meta["cost"] = _usage_cost(usage) if usage is not None else None
        return meta


def _usage_cost(usage: Any) -> float | None:
    """Pull the gateway's reported cost off the usage object.

    The openai SDK surfaces non-standard response fields as plain attributes, so
    whichever name the gateway uses we read it here rather than recomputing.
    """
    for name in ("cost", "total_cost", "cost_usd"):
        value = getattr(usage, name, None)
        if isinstance(value, (int, float)):
            return float(value)
    return None
