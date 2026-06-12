"""LiteLLM async wrapper. The ONLY module that imports litellm."""
from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable, Protocol

import litellm

from .models import Completion


class ProviderError(Exception):
    """Raised when a completion fails after all retries."""


class Provider(Protocol):
    async def complete(
        self, *, model: str, system: str, user: str, schema: dict,
        schema_name: str, temperature: float, timeout: int,
    ) -> Completion: ...


class LiteLLMProvider:
    def __init__(
        self,
        completion_fn: Callable[..., Awaitable[Any]] | None = None,
        retries: int = 2,
    ):
        self._completion_fn = completion_fn or litellm.acompletion
        self._retries = retries

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
        for _ in range(self._retries + 1):
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
        raise ProviderError(
            f"completion failed after {self._retries + 1} attempts: {last_err}"
        )

    def _extract_meta(self, resp: Any, model: str, latency: float) -> dict:
        meta: dict[str, Any] = {"model": model, "latency": round(latency, 3)}
        usage = getattr(resp, "usage", None)
        if usage is not None:
            meta["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
            meta["completion_tokens"] = getattr(usage, "completion_tokens", None)
        try:
            meta["cost"] = litellm.completion_cost(completion_response=resp)
        except Exception:
            meta["cost"] = None
        return meta
