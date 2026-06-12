# Diplomacy AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AI layer that runs a full game of Diplomacy between 7 LLM-controlled powers, with fixed-round negotiation, full press (private + global), per-power model config, and a reviewable transcript — driving the `diplomacy` engine as a black box.

**Architecture:** A single Python process owns one `diplomacy.Game`. The `Orchestrator` runs a phase loop: on movement phases it runs N negotiation rounds (all powers queried in parallel via asyncio), routes messages, then collects orders in parallel, validates them against the engine, and processes the phase. Two hard seams: `orchestrator.py` is the only module importing engine game logic; `provider.py` is the only module importing LiteLLM.

**Tech Stack:** Python 3.14, `diplomacy` 1.1.2 (engine), LiteLLM (provider abstraction), Pydantic v2 (config), stdlib `tomllib` (config parsing), `asyncio` (parallel queries), pytest + pytest-asyncio (tests).

---

## File Structure

```
diplomacy-ai/
├── pyproject.toml                 # package + deps + pytest config + console script
├── game.toml                      # sample run config
├── diplomacy_ai/
│   ├── __init__.py
│   ├── models.py                  # shared dataclasses (no deps)
│   ├── config.py                  # Pydantic config + tomllib loader
│   ├── provider.py                # LiteLLM async wrapper (only LLM-aware module)
│   ├── prompts.py                 # pure prompt builders + JSON schemas
│   ├── agent.py                   # PowerAgent: negotiate() / decide_orders()
│   ├── recorder.py                # persistence (game.json, transcripts, events.log)
│   ├── orchestrator.py            # phase loop (only engine-aware module)
│   └── cli.py                     # `diplomacy-ai run --config game.toml`
└── tests/
    ├── conftest.py                # FakeProvider, FakeAgent fixtures
    ├── test_config.py
    ├── test_provider.py
    ├── test_prompts.py
    ├── test_agent.py
    ├── test_recorder.py
    ├── test_orchestrator.py
    └── test_smoke.py              # opt-in real-Gemini test
```

---

## Task 1: Project scaffolding & dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `diplomacy_ai/__init__.py`
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "diplomacy-ai"
version = "0.1.0"
description = "LLM-powered Diplomacy game on the diplomacy engine"
requires-python = ">=3.11"
dependencies = [
    "diplomacy>=1.1.2",
    "litellm>=1.40",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[project.scripts]
diplomacy-ai = "diplomacy_ai.cli:main"

[tool.setuptools.packages.find]
include = ["diplomacy_ai*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package markers**

Create `diplomacy_ai/__init__.py`:
```python
"""LLM-powered Diplomacy on the diplomacy engine."""
```
Create empty `tests/__init__.py` (no content).

- [ ] **Step 3: Install in editable mode**

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: ends with `Successfully installed ... diplomacy-ai-0.1.0 litellm-... pydantic-... pytest-...`

- [ ] **Step 4: Verify pytest discovers an empty suite**

Run: `.venv/bin/pytest -q`
Expected: `no tests ran` (exit code 5 is fine at this stage).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml diplomacy_ai/__init__.py tests/__init__.py
git commit -m "chore: scaffold diplomacy_ai package and dev deps"
```

---

## Task 2: Shared data models

**Files:**
- Create: `diplomacy_ai/models.py`
- Test: `tests/test_models.py`

These are pure dataclasses with no imports from other project modules — they break dependency cycles between agent/orchestrator/recorder.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:
```python
import dataclasses
import pytest
from diplomacy_ai.models import (
    OutMessage, InMessage, NegotiationResult, OrderResult, Completion, PowerView,
)


def test_outmessage_is_frozen():
    m = OutMessage(to="FRANCE", body="hi")
    assert m.to == "FRANCE" and m.body == "hi"
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.body = "changed"


def test_results_default_to_empty_meta():
    n = NegotiationResult(reasoning="r", messages=[OutMessage("GLOBAL", "yo")])
    o = OrderResult(reasoning="r", orders=["A PAR H"])
    assert n.meta == {} and o.meta == {}


def test_powerview_holds_legal_orders_by_location():
    v = PowerView(
        power_name="FRANCE", phase="S1901M", board_text="...",
        own_units=["A PAR"], own_centers=["PAR"],
        legal_orders={"PAR": ["A PAR H", "A PAR - BUR"]},
    )
    assert v.legal_orders["PAR"][1] == "A PAR - BUR"
    assert Completion(data={"x": 1}, meta={}).data["x"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.models'`

- [ ] **Step 3: Write `diplomacy_ai/models.py`**

```python
"""Shared data models. Pure dataclasses, no project imports."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OutMessage:
    """A message a power wants to send. `to` is a power name or "GLOBAL"."""
    to: str
    body: str


@dataclass(frozen=True)
class InMessage:
    """A message a power received. `scope` is "private" or "global"."""
    sender: str
    body: str
    scope: str


@dataclass
class NegotiationResult:
    reasoning: str
    messages: list[OutMessage]
    meta: dict = field(default_factory=dict)


@dataclass
class OrderResult:
    reasoning: str
    orders: list[str]
    meta: dict = field(default_factory=dict)


@dataclass
class Completion:
    """Parsed LLM response plus call metadata (tokens/cost/latency)."""
    data: dict
    meta: dict


@dataclass
class PowerView:
    """Everything one power needs to reason about the current phase."""
    power_name: str
    phase: str
    board_text: str
    own_units: list[str]
    own_centers: list[str]
    legal_orders: dict[str, list[str]]  # location -> list of legal order strings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/models.py tests/test_models.py
git commit -m "feat: add shared data models"
```

---

## Task 3: Config loading

**Files:**
- Create: `diplomacy_ai/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:
```python
from diplomacy_ai.config import GameConfig, load_config


def test_defaults_apply_when_power_omitted():
    cfg = GameConfig(default_model="gemini/x")
    assert cfg.model_for("FRANCE") == "gemini/x"
    assert cfg.persona_for("FRANCE") == ""
    assert cfg.n_negotiation_rounds == 3


def test_per_power_overrides():
    cfg = GameConfig(
        default_model="gemini/x",
        powers={"FRANCE": {"model": "gemini/pro", "persona": "bold"}},
    )
    assert cfg.model_for("FRANCE") == "gemini/pro"
    assert cfg.persona_for("FRANCE") == "bold"
    # power present but no model -> falls back to default
    cfg2 = GameConfig(default_model="gemini/x", powers={"ITALY": {"persona": "shy"}})
    assert cfg2.model_for("ITALY") == "gemini/x"
    assert cfg2.persona_for("ITALY") == "shy"


def test_load_config_reads_toml_and_uppercases_powers(tmp_path):
    p = tmp_path / "game.toml"
    p.write_text(
        'n_negotiation_rounds = 2\n'
        'default_model = "gemini/flash"\n'
        '[powers.france]\n'
        'persona = "cautious"\n'
    )
    cfg = load_config(p)
    assert cfg.n_negotiation_rounds == 2
    assert cfg.persona_for("FRANCE") == "cautious"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.config'`

- [ ] **Step 3: Write `diplomacy_ai/config.py`**

```python
"""Game configuration: Pydantic models + tomllib loader."""
from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class PowerConfig(BaseModel):
    model: str | None = None
    persona: str = ""


class GameConfig(BaseModel):
    n_negotiation_rounds: int = 3
    max_year: int = 1920
    default_model: str = "gemini/gemini-2.5-pro"
    temperature: float = 0.7
    timeout: int = 60
    powers: dict[str, PowerConfig] = Field(default_factory=dict)

    def model_for(self, power: str) -> str:
        pc = self.powers.get(power)
        return pc.model if pc and pc.model else self.default_model

    def persona_for(self, power: str) -> str:
        pc = self.powers.get(power)
        return pc.persona if pc else ""


def load_config(path: str | Path) -> GameConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    powers = data.pop("powers", {})
    data["powers"] = {name.upper(): PowerConfig(**pc) for name, pc in powers.items()}
    return GameConfig(**data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/config.py tests/test_config.py
git commit -m "feat: add game config loading"
```

---

## Task 4: LiteLLM provider

**Files:**
- Create: `diplomacy_ai/provider.py`
- Test: `tests/test_provider.py`

The provider takes an injectable `completion_fn` (defaults to `litellm.acompletion`) so tests never hit the network. It retries on any error or malformed JSON, then raises `ProviderError`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_provider.py`:
```python
import pytest
from diplomacy_ai.provider import LiteLLMProvider, ProviderError


class _Msg:
    def __init__(self, content): self.content = content


class _Choice:
    def __init__(self, content): self.message = _Msg(content)


class _Resp:
    def __init__(self, content, usage=None):
        self.choices = [_Choice(content)]
        self.usage = usage


SCHEMA = {"type": "object", "properties": {"reasoning": {"type": "string"}},
          "required": ["reasoning"], "additionalProperties": False}


async def test_parses_json_content():
    async def fake(**kwargs):
        return _Resp('{"reasoning": "hello"}')
    prov = LiteLLMProvider(completion_fn=fake)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.data["reasoning"] == "hello"
    assert c.meta["model"] == "m" and "latency" in c.meta


async def test_retries_then_succeeds():
    calls = {"n": 0}
    async def fake(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("rate limited")
        return _Resp('{"reasoning": "ok"}')
    prov = LiteLLMProvider(completion_fn=fake, retries=2)
    c = await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
    assert c.data["reasoning"] == "ok" and calls["n"] == 2


async def test_malformed_json_raises_provider_error():
    async def fake(**kwargs):
        return _Resp("not json")
    prov = LiteLLMProvider(completion_fn=fake, retries=1)
    with pytest.raises(ProviderError):
        await prov.complete(model="m", system="s", user="u", schema=SCHEMA,
                            schema_name="t", temperature=0.5, timeout=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.provider'`

- [ ] **Step 3: Write `diplomacy_ai/provider.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_provider.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/provider.py tests/test_provider.py
git commit -m "feat: add LiteLLM provider with retries"
```

---

## Task 5: Prompt builders and schemas

**Files:**
- Create: `diplomacy_ai/prompts.py`
- Test: `tests/test_prompts.py`

Pure functions: `(PowerView, persona, inbox, ...) -> (system, user)`. They render the legal-order list and inbox into text. No I/O, no engine imports.

- [ ] **Step 1: Write the failing test**

Create `tests/test_prompts.py`:
```python
from diplomacy_ai.models import PowerView, InMessage
from diplomacy_ai.prompts import (
    negotiation_prompt, orders_prompt, NEGOTIATION_SCHEMA, ORDERS_SCHEMA,
)

VIEW = PowerView(
    power_name="FRANCE", phase="S1901M", board_text="FRANCE: units [A PAR]",
    own_units=["A PAR"], own_centers=["PAR"],
    legal_orders={"PAR": ["A PAR H", "A PAR - BUR"]},
)


def test_negotiation_prompt_includes_power_round_and_inbox():
    inbox = [InMessage(sender="ENGLAND", body="ally?", scope="private")]
    system, user = negotiation_prompt(VIEW, "cautious", inbox, round_num=2, total_rounds=3)
    assert "FRANCE" in system and "cautious" in system
    assert "round 2 of 3" in user.lower()
    assert "ENGLAND" in user and "ally?" in user
    assert "A PAR - BUR" in user  # legal orders surfaced for planning


def test_negotiation_prompt_handles_empty_inbox():
    system, user = negotiation_prompt(VIEW, "", [], round_num=1, total_rounds=3)
    assert "no messages" in user.lower()


def test_orders_prompt_lists_legal_orders_and_rejected():
    system, user = orders_prompt(VIEW, "bold", rejected=["A PAR - MOS"])
    assert "A PAR - BUR" in user
    assert "A PAR - MOS" in user  # rejected orders surfaced for repair
    assert "rejected" in user.lower()


def test_schemas_are_well_formed():
    assert NEGOTIATION_SCHEMA["required"] == ["reasoning", "messages"]
    assert ORDERS_SCHEMA["required"] == ["reasoning", "orders"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_prompts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.prompts'`

- [ ] **Step 3: Write `diplomacy_ai/prompts.py`**

```python
"""Pure prompt builders and JSON schemas. No I/O, no engine imports."""
from __future__ import annotations

from .models import InMessage, PowerView

RULES_PRIMER = (
    "You are playing Diplomacy, the classic 7-power strategy game set in pre-WWI "
    "Europe. Powers negotiate to coordinate moves, but all orders resolve "
    "simultaneously with no randomness. Support is needed to dislodge equal "
    "strength. You win by controlling 18 supply centers; otherwise survive and "
    "grow. Alliances are temporary and betrayal is part of the game."
)

NEGOTIATION_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reasoning", "messages"],
    "additionalProperties": False,
}

ORDERS_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "orders": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reasoning", "orders"],
    "additionalProperties": False,
}


def _persona_clause(persona: str) -> str:
    return f" Your temperament: {persona}." if persona else ""


def _legal_orders_block(view: PowerView) -> str:
    if not view.legal_orders:
        return "You have no orderable units this phase."
    lines = ["Your legal orders (choose only from these exact strings):"]
    for loc, orders in view.legal_orders.items():
        lines.append(f"  {loc}: {', '.join(orders)}")
    return "\n".join(lines)


def _inbox_block(inbox: list[InMessage]) -> str:
    if not inbox:
        return "You received no messages."
    lines = ["Messages you received:"]
    for m in inbox:
        tag = "GLOBAL" if m.scope == "global" else "private"
        lines.append(f"  [{tag}] {m.sender}: {m.body}")
    return "\n".join(lines)


def _system(view: PowerView, persona: str) -> str:
    return (
        f"{RULES_PRIMER}\n\n"
        f"You are {view.power_name}.{_persona_clause(persona)} "
        f"Play to win for {view.power_name}. Respond ONLY with JSON matching the schema."
    )


def negotiation_prompt(
    view: PowerView, persona: str, inbox: list[InMessage],
    round_num: int, total_rounds: int,
) -> tuple[str, str]:
    user = (
        f"Phase {view.phase}, negotiation round {round_num} of {total_rounds}.\n\n"
        f"Board state:\n{view.board_text}\n\n"
        f"{_inbox_block(inbox)}\n\n"
        f"{_legal_orders_block(view)}\n\n"
        "Decide who to talk to and what to say. Use \"to\": \"GLOBAL\" for a public "
        "broadcast, or a power name (e.g. \"ENGLAND\") for a private message. Send an "
        "empty messages list if you prefer to stay silent. Put your private analysis "
        "in \"reasoning\" (other powers never see it)."
    )
    return _system(view, persona), user


def orders_prompt(
    view: PowerView, persona: str, rejected: list[str] | None = None,
) -> tuple[str, str]:
    rejected_block = ""
    if rejected:
        rejected_block = (
            "\n\nThese orders you previously submitted were REJECTED as illegal; "
            "do not repeat them, pick valid alternatives:\n  " + "\n  ".join(rejected)
        )
    user = (
        f"Phase {view.phase}. Time to submit final orders.\n\n"
        f"Board state:\n{view.board_text}\n\n"
        f"{_legal_orders_block(view)}{rejected_block}\n\n"
        "Return your orders as a list of exact order strings chosen from the legal "
        "orders above. Put your private analysis in \"reasoning\"."
    )
    return _system(view, persona), user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_prompts.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/prompts.py tests/test_prompts.py
git commit -m "feat: add prompt builders and JSON schemas"
```

---

## Task 6: PowerAgent

**Files:**
- Create: `diplomacy_ai/agent.py`
- Create: `tests/conftest.py` (FakeProvider)
- Test: `tests/test_agent.py`

The agent wires prompts + provider, parses responses into result objects, sanitizes message recipients, and degrades gracefully (empty messages / hold) on `ProviderError`.

- [ ] **Step 1: Write the FakeProvider fixture**

Create `tests/conftest.py`:
```python
import pytest
from diplomacy_ai.models import Completion
from diplomacy_ai.provider import ProviderError


class FakeProvider:
    """Returns queued payloads (dicts) in order; a payload of None raises."""
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._payloads.pop(0)
        if payload is None:
            raise ProviderError("boom")
        return Completion(data=payload, meta={"model": kwargs["model"]})


@pytest.fixture
def make_provider():
    return lambda payloads: FakeProvider(payloads)
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_agent.py`:
```python
from diplomacy_ai.agent import PowerAgent
from diplomacy_ai.models import PowerView, InMessage

VIEW = PowerView(
    power_name="FRANCE", phase="S1901M", board_text="b",
    own_units=["A PAR"], own_centers=["PAR"],
    legal_orders={"PAR": ["A PAR H"]},
)


def _agent(provider):
    return PowerAgent(power_name="FRANCE", model="m", persona="bold",
                      provider=provider, temperature=0.5, timeout=10)


async def test_negotiate_parses_and_sanitizes_messages(make_provider):
    prov = make_provider([{
        "reasoning": "think",
        "messages": [
            {"to": "england", "body": "ally?"},   # lowercased -> ENGLAND
            {"to": "GLOBAL", "body": "hello all"},
            {"to": "FRANCE", "body": "to self"},   # self -> dropped
            {"to": "ATLANTIS", "body": "bad"},     # invalid -> dropped
            {"to": "ENGLAND", "body": "   "},        # empty body -> dropped
        ],
    }])
    res = await _agent(prov).negotiate(VIEW, [], round_num=1, total_rounds=3)
    assert res.reasoning == "think"
    sent = {(m.to, m.body) for m in res.messages}
    assert sent == {("ENGLAND", "ally?"), ("GLOBAL", "hello all")}


async def test_negotiate_degrades_on_provider_error(make_provider):
    prov = make_provider([None])
    res = await _agent(prov).negotiate(VIEW, [InMessage("ENGLAND", "hi", "private")], 1, 3)
    assert res.messages == []
    assert res.meta.get("error") is True


async def test_decide_orders_parses_orders(make_provider):
    prov = make_provider([{"reasoning": "r", "orders": ["A PAR H", "  ", "A PAR - BUR"]}])
    res = await _agent(prov).decide_orders(VIEW)
    assert res.orders == ["A PAR H", "A PAR - BUR"]


async def test_decide_orders_degrades_to_hold_on_error(make_provider):
    prov = make_provider([None])
    res = await _agent(prov).decide_orders(VIEW)
    assert res.orders == [] and res.meta.get("error") is True


async def test_decide_orders_passes_rejected_to_prompt(make_provider):
    prov = make_provider([{"reasoning": "r", "orders": ["A PAR H"]}])
    await _agent(prov).decide_orders(VIEW, rejected=["A PAR - MOS"])
    assert "A PAR - MOS" in prov.calls[0]["user"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.agent'`

- [ ] **Step 4: Write `diplomacy_ai/agent.py`**

```python
"""PowerAgent: turns game views into negotiation messages and orders."""
from __future__ import annotations

from .models import NegotiationResult, OrderResult, OutMessage, PowerView, InMessage
from .prompts import (
    NEGOTIATION_SCHEMA, ORDERS_SCHEMA, negotiation_prompt, orders_prompt,
)
from .provider import Provider, ProviderError

VALID_RECIPIENTS = {
    "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY", "GLOBAL",
}


class PowerAgent:
    def __init__(
        self, power_name: str, model: str, persona: str,
        provider: Provider, temperature: float, timeout: int,
    ):
        self.power_name = power_name
        self.model = model
        self.persona = persona
        self.provider = provider
        self.temperature = temperature
        self.timeout = timeout

    async def negotiate(
        self, view: PowerView, inbox: list[InMessage],
        round_num: int, total_rounds: int,
    ) -> NegotiationResult:
        system, user = negotiation_prompt(view, self.persona, inbox, round_num, total_rounds)
        try:
            c = await self.provider.complete(
                model=self.model, system=system, user=user,
                schema=NEGOTIATION_SCHEMA, schema_name="negotiation",
                temperature=self.temperature, timeout=self.timeout,
            )
        except ProviderError:
            return NegotiationResult(
                reasoning="[provider error: no messages sent]", messages=[],
                meta={"error": True},
            )
        messages = []
        for m in c.data.get("messages", []):
            to = str(m.get("to", "")).upper()
            body = str(m.get("body", "")).strip()
            if to in VALID_RECIPIENTS and to != self.power_name and body:
                messages.append(OutMessage(to=to, body=body))
        return NegotiationResult(
            reasoning=c.data.get("reasoning", ""), messages=messages, meta=c.meta,
        )

    async def decide_orders(
        self, view: PowerView, rejected: list[str] | None = None,
    ) -> OrderResult:
        system, user = orders_prompt(view, self.persona, rejected)
        try:
            c = await self.provider.complete(
                model=self.model, system=system, user=user,
                schema=ORDERS_SCHEMA, schema_name="orders",
                temperature=self.temperature, timeout=self.timeout,
            )
        except ProviderError:
            return OrderResult(reasoning="[provider error: holding]", orders=[],
                               meta={"error": True})
        orders = [str(o).strip() for o in c.data.get("orders", []) if str(o).strip()]
        return OrderResult(reasoning=c.data.get("reasoning", ""), orders=orders, meta=c.meta)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_agent.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add diplomacy_ai/agent.py tests/conftest.py tests/test_agent.py
git commit -m "feat: add PowerAgent with graceful degradation"
```

---

## Task 7: Recorder

**Files:**
- Create: `diplomacy_ai/recorder.py`
- Test: `tests/test_recorder.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_recorder.py`:
```python
import json
from diplomacy import Game
from diplomacy_ai.recorder import Recorder


def test_record_phase_writes_transcript(tmp_path):
    rec = Recorder(tmp_path / "run")
    rec.record_phase("S1901M", {"FRANCE": {"orders": {"orders_final": ["A PAR H"]}}})
    path = tmp_path / "run" / "transcript" / "S1901M.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["FRANCE"]["orders"]["orders_final"] == ["A PAR H"]


def test_save_game_writes_loadable_json(tmp_path):
    rec = Recorder(tmp_path / "run")
    rec.save_game(Game())
    data = json.loads((tmp_path / "run" / "game.json").read_text())
    assert "phases" in data and "map" in data


def test_log_appends_lines(tmp_path):
    rec = Recorder(tmp_path / "run")
    rec.log("first")
    rec.log("second")
    assert (tmp_path / "run" / "events.log").read_text() == "first\nsecond\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_recorder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.recorder'`

- [ ] **Step 3: Write `diplomacy_ai/recorder.py`**

```python
"""Persistence: saved-game JSON, per-phase transcripts, event log."""
from __future__ import annotations

import json
from pathlib import Path

from diplomacy.utils.export import to_saved_game_format


class Recorder:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        (self.run_dir / "transcript").mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.log"

    def save_game(self, game) -> None:
        data = to_saved_game_format(game)
        (self.run_dir / "game.json").write_text(json.dumps(data, indent=2))

    def record_phase(self, phase: str, phase_records: dict) -> None:
        path = self.run_dir / "transcript" / f"{phase}.json"
        path.write_text(json.dumps(phase_records, indent=2, default=str))

    def log(self, message: str) -> None:
        with self.events_path.open("a") as f:
            f.write(message + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_recorder.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/recorder.py tests/test_recorder.py
git commit -m "feat: add recorder for game json, transcripts, and log"
```

---

## Task 8: Orchestrator — views & order validation ladder

**Files:**
- Create: `diplomacy_ai/orchestrator.py`
- Test: `tests/test_orchestrator.py`

This task builds the engine-facing helpers and the validate → repair → drop ladder. Routing and the run loop come in Tasks 9 and 10. The `FakeAgent` is added to `conftest.py`.

- [ ] **Step 1: Add FakeAgent to `tests/conftest.py`**

Append to `tests/conftest.py`:
```python
from diplomacy_ai.models import NegotiationResult, OrderResult


class FakeAgent:
    """Scripted agent. `order_scripts` is a list of order-lists returned in sequence
    (first = initial, second = repair). `messages` returned every negotiate call."""
    def __init__(self, power_name, order_scripts=None, messages=None):
        self.power_name = power_name
        self._order_scripts = list(order_scripts or [[]])
        self._messages = messages or []
        self.order_calls = []

    async def negotiate(self, view, inbox, round_num, total_rounds):
        return NegotiationResult(reasoning="r", messages=list(self._messages))

    async def decide_orders(self, view, rejected=None):
        self.order_calls.append(rejected)
        orders = self._order_scripts.pop(0) if self._order_scripts else []
        return OrderResult(reasoning="r", orders=orders)
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_orchestrator.py`:
```python
from diplomacy import Game
from diplomacy_ai.config import GameConfig
from diplomacy_ai.orchestrator import Orchestrator, POWERS
from diplomacy_ai.recorder import Recorder
from tests.conftest import FakeAgent


def _orch(tmp_path, agents, **cfg):
    game = Game()
    config = GameConfig(**cfg)
    rec = Recorder(tmp_path / "run")
    return Orchestrator(game, agents, config, rec)


def test_build_view_exposes_units_and_legal_orders(tmp_path):
    orch = _orch(tmp_path, {p: FakeAgent(p) for p in POWERS})
    view = orch.build_view("FRANCE")
    assert "A PAR" in view.own_units or "F BRE" in view.own_units
    # PAR is a French home center with legal orders in S1901M
    assert "PAR" in view.legal_orders


async def test_collect_orders_keeps_valid_drops_invalid(tmp_path):
    # FRANCE submits one legal hold + one nonsense order; no repair needed for the hold.
    agents = {p: FakeAgent(p) for p in POWERS}
    agents["FRANCE"] = FakeAgent("FRANCE", order_scripts=[["A PAR H", "A PAR - MARS"]])
    orch = _orch(tmp_path, agents)
    view = orch.build_view("FRANCE")
    power, final, record = await orch.collect_power_orders("FRANCE", view)
    assert "A PAR H" in final
    assert "A PAR - MARS" in record["dropped"]


async def test_collect_orders_repairs_then_drops(tmp_path):
    # First attempt fully invalid -> triggers repair; repair returns a legal order.
    agents = {p: FakeAgent(p) for p in POWERS}
    agents["FRANCE"] = FakeAgent(
        "FRANCE", order_scripts=[["A PAR - MARS"], ["A PAR H"]])
    orch = _orch(tmp_path, agents)
    view = orch.build_view("FRANCE")
    power, final, record = await orch.collect_power_orders("FRANCE", view)
    assert final == ["A PAR H"]
    assert record["repaired"] is True
    assert agents["FRANCE"].order_calls == [None, ["A PAR - MARS"]]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.orchestrator'`

- [ ] **Step 4: Write `diplomacy_ai/orchestrator.py` (initial version)**

```python
"""Orchestrator: owns the Game and runs the phase loop.
The ONLY module that imports diplomacy engine game logic."""
from __future__ import annotations

import asyncio

import diplomacy.utils.common as common
from diplomacy import Message

from .models import InMessage, PowerView

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


class Orchestrator:
    def __init__(self, game, agents: dict, config, recorder):
        self.game = game
        self.agents = agents
        self.config = config
        self.recorder = recorder

    # --- engine-facing helpers ---

    def _render_board(self, state: dict) -> str:
        lines = []
        for p in POWERS:
            units = ", ".join(state["units"][p]) or "(none)"
            centers = ", ".join(state["centers"][p]) or "(none)"
            lines.append(f"{p}: units [{units}] centers [{centers}]")
        return "\n".join(lines)

    def build_view(self, power: str) -> PowerView:
        state = self.game.get_state()
        phase = self.game.get_current_phase()
        locs = self.game.get_orderable_locations(power)
        allpo = self.game.get_all_possible_orders()
        legal = {loc: allpo.get(loc, []) for loc in locs}
        return PowerView(
            power_name=power, phase=phase, board_text=self._render_board(state),
            own_units=list(state["units"][power]),
            own_centers=list(state["centers"][power]),
            legal_orders=legal,
        )

    def _legal_set(self) -> set:
        allpo = self.game.get_all_possible_orders()
        return {o for orders in allpo.values() for o in orders}

    # --- order collection with repair ladder ---

    async def collect_power_orders(self, power: str, view: PowerView):
        legal = self._legal_set()
        agent = self.agents[power]
        result = await agent.decide_orders(view)
        valid = [o for o in result.orders if o in legal]
        invalid = [o for o in result.orders if o not in legal]
        record = {
            "reasoning": result.reasoning, "orders_raw": list(result.orders),
            "meta": result.meta, "repaired": False,
        }
        if invalid:
            repair = await agent.decide_orders(view, rejected=invalid)
            valid = [o for o in repair.orders if o in legal]
            invalid = [o for o in repair.orders if o not in legal]
            record.update({
                "orders_raw": list(repair.orders), "reasoning": repair.reasoning,
                "meta": repair.meta, "repaired": True,
            })
        record["orders_final"] = valid
        record["dropped"] = invalid
        return power, valid, record
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add diplomacy_ai/orchestrator.py tests/conftest.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator views and order validation ladder"
```

---

## Task 9: Orchestrator — message routing

**Files:**
- Modify: `diplomacy_ai/orchestrator.py`
- Test: `tests/test_orchestrator.py`

Add `route()`: given each power's `NegotiationResult`, deliver private messages to recipient inboxes, global messages to everyone but the sender, and push every message into the engine so it lands in the saved game.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_orchestrator.py`:
```python
from diplomacy_ai.models import NegotiationResult, OutMessage


def test_route_delivers_private_and_global(tmp_path):
    orch = _orch(tmp_path, {p: FakeAgent(p) for p in POWERS})
    results = {
        "FRANCE": NegotiationResult("r", [
            OutMessage("ENGLAND", "secret"), OutMessage("GLOBAL", "hi all")]),
        "ENGLAND": NegotiationResult("r", []),
    }
    inboxes = orch.route(results)
    # private: only ENGLAND gets the secret
    eng = [m for m in inboxes["ENGLAND"] if m.body == "secret"]
    assert len(eng) == 1 and eng[0].scope == "private"
    assert all(m.body != "secret" for m in inboxes["GERMANY"])
    # global: everyone except sender FRANCE gets "hi all"
    assert any(m.body == "hi all" for m in inboxes["GERMANY"])
    assert all(m.body != "hi all" for m in inboxes["FRANCE"])
    # messages pushed into the engine
    assert len(orch.game.messages) == 2


def test_route_returns_inbox_for_every_power(tmp_path):
    orch = _orch(tmp_path, {p: FakeAgent(p) for p in POWERS})
    inboxes = orch.route({"FRANCE": NegotiationResult("r", [])})
    assert set(inboxes.keys()) == set(POWERS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'route'`

- [ ] **Step 3: Add `route()` to `diplomacy_ai/orchestrator.py`**

Add these methods to the `Orchestrator` class (after `collect_power_orders`):
```python
    def _alive_powers(self) -> list[str]:
        state = self.game.get_state()
        return [p for p in POWERS if state["units"][p] or state["centers"][p]]

    def route(self, round_results: dict) -> dict[str, list[InMessage]]:
        inboxes: dict[str, list[InMessage]] = {p: [] for p in POWERS}
        phase = self.game.get_current_phase()
        for sender, result in round_results.items():
            for m in result.messages:
                self.game.add_message(Message(
                    sender=sender, recipient=m.to, message=m.body,
                    phase=phase, time_sent=common.timestamp_microseconds(),
                ))
                if m.to == "GLOBAL":
                    for p in POWERS:
                        if p != sender:
                            inboxes[p].append(
                                InMessage(sender=sender, body=m.body, scope="global"))
                elif m.to in inboxes:
                    inboxes[m.to].append(
                        InMessage(sender=sender, body=m.body, scope="private"))
        return inboxes
```

Note: `common.timestamp_microseconds()` is strictly increasing per call, so messages get distinct timestamps.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add diplomacy_ai/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add message routing to orchestrator"
```

---

## Task 10: Orchestrator — phase loop & run

**Files:**
- Modify: `diplomacy_ai/orchestrator.py`
- Test: `tests/test_orchestrator.py`

Add `run_phase()` (negotiation rounds on movement phases, then parallel order collection, record, process) and `run()` (loop until solo win or `max_year`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_orchestrator.py`:
```python
async def test_run_terminates_at_max_year_and_records(tmp_path):
    # All powers hold (empty orders) -> game never ends on its own; max_year stops it.
    agents = {p: FakeAgent(p, order_scripts=[[]] * 50) for p in POWERS}
    orch = _orch(tmp_path, agents, n_negotiation_rounds=1, max_year=1901)
    await orch.run()
    # Game advanced past 1901 and stopped.
    assert int(orch.game.get_current_phase()[1:5]) >= 1902
    # Transcript + game.json written.
    assert (tmp_path / "run" / "game.json").exists()
    assert (tmp_path / "run" / "transcript" / "S1901M.json").exists()
    assert "max_year" in (tmp_path / "run" / "events.log").read_text()


async def test_run_phase_sets_valid_orders(tmp_path):
    # FRANCE orders a legal hold for one unit; engine should accept it.
    agents = {p: FakeAgent(p, order_scripts=[[]]) for p in POWERS}
    agents["FRANCE"] = FakeAgent("FRANCE", order_scripts=[["A PAR H"]])
    orch = _orch(tmp_path, agents, n_negotiation_rounds=1, max_year=1920)
    await orch.run_phase()
    # After processing S1901M we should be in a later phase.
    assert orch.game.get_current_phase() != "S1901M"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: FAIL — `AttributeError: 'Orchestrator' object has no attribute 'run_phase'`

- [ ] **Step 3: Add `run_phase()` and `run()` to `diplomacy_ai/orchestrator.py`**

Add these methods to the `Orchestrator` class:
```python
    async def _run_negotiation(self, phase_records: dict) -> None:
        alive = self._alive_powers()
        inboxes: dict[str, list[InMessage]] = {p: [] for p in alive}
        for p in alive:
            phase_records[p]["negotiation_sent"] = []
            phase_records[p]["negotiation_received"] = []
        total = self.config.n_negotiation_rounds
        for rnd in range(1, total + 1):
            views = {p: self.build_view(p) for p in alive}
            coros = [
                self.agents[p].negotiate(views[p], inboxes[p], rnd, total)
                for p in alive
            ]
            results = dict(zip(alive, await asyncio.gather(*coros)))
            for p, r in results.items():
                phase_records[p]["negotiation_sent"].append({
                    "round": rnd, "reasoning": r.reasoning,
                    "messages": [{"to": m.to, "body": m.body} for m in r.messages],
                    "meta": r.meta,
                })
            new_inboxes = self.route(results)
            for p in alive:
                phase_records[p]["negotiation_received"].extend(
                    {"round": rnd, "sender": m.sender, "body": m.body, "scope": m.scope}
                    for m in new_inboxes[p]
                )
            inboxes = {p: new_inboxes[p] for p in alive}

    async def run_phase(self) -> None:
        phase = self.game.get_current_phase()
        phase_records: dict = {p: {} for p in POWERS}
        if phase.endswith("M"):
            await self._run_negotiation(phase_records)
        order_powers = [p for p in POWERS if self.game.get_orderable_locations(p)]
        if order_powers:
            views = {p: self.build_view(p) for p in order_powers}
            collected = await asyncio.gather(
                *[self.collect_power_orders(p, views[p]) for p in order_powers]
            )
            for power, valid, record in collected:
                self.game.set_orders(power, valid)
                phase_records[power]["orders"] = record
        self.recorder.record_phase(phase, phase_records)
        self.recorder.log(f"Processing {phase}")
        self.game.process()
        self.recorder.save_game(self.game)

    async def run(self) -> None:
        self.recorder.save_game(self.game)
        while not self.game.is_game_done:
            year = int(self.game.get_current_phase()[1:5])
            if year > self.config.max_year:
                self.recorder.log(f"Reached max_year {self.config.max_year}; stopping.")
                break
            await self.run_phase()
        self.recorder.log("Game finished.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_orchestrator.py -q`
Expected: PASS (7 passed). May take a few seconds (real engine processes several phases).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: PASS (all tests green).

- [ ] **Step 6: Commit**

```bash
git add diplomacy_ai/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator phase loop and run loop"
```

---

## Task 11: CLI & sample config

**Files:**
- Create: `diplomacy_ai/cli.py`
- Create: `game.toml`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:
```python
from diplomacy_ai.cli import build_agents
from diplomacy_ai.config import GameConfig
from diplomacy_ai.orchestrator import POWERS


class _Prov:
    pass


def test_build_agents_covers_all_powers_with_config():
    cfg = GameConfig(default_model="gemini/x",
                     powers={"FRANCE": {"model": "gemini/pro", "persona": "bold"}})
    agents = build_agents(cfg, _Prov())
    assert set(agents.keys()) == set(POWERS)
    assert agents["FRANCE"].model == "gemini/pro"
    assert agents["FRANCE"].persona == "bold"
    assert agents["ITALY"].model == "gemini/x"  # default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'diplomacy_ai.cli'`

- [ ] **Step 3: Write `diplomacy_ai/cli.py`**

```python
"""Command-line entry point: `diplomacy-ai run --config game.toml`."""
from __future__ import annotations

import argparse
import asyncio
import datetime
from pathlib import Path

from diplomacy import Game

from .agent import PowerAgent
from .config import GameConfig, load_config
from .orchestrator import POWERS, Orchestrator
from .provider import LiteLLMProvider
from .recorder import Recorder


def build_agents(config: GameConfig, provider) -> dict[str, PowerAgent]:
    return {
        p: PowerAgent(
            power_name=p, model=config.model_for(p), persona=config.persona_for(p),
            provider=provider, temperature=config.temperature, timeout=config.timeout,
        )
        for p in POWERS
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="diplomacy-ai")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run a full game")
    run_p.add_argument("--config", required=True, help="Path to game.toml")
    run_p.add_argument("--out", default="runs", help="Output directory for runs")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    provider = LiteLLMProvider()
    game = Game()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    recorder = Recorder(Path(args.out) / ts)
    agents = build_agents(config, provider)
    orch = Orchestrator(game, agents, config, recorder)

    asyncio.run(orch.run())
    print(f"Done. Run saved to {recorder.run_dir}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_cli.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Write `game.toml` sample config**

```toml
# Sample Diplomacy AI config. Set GEMINI_API_KEY in your environment before running.
n_negotiation_rounds = 3
max_year = 1910
default_model = "gemini/gemini-2.5-pro"
temperature = 0.7
timeout = 60

[powers.FRANCE]
persona = "Cautious; prefers long-term alliances over early aggression."

[powers.TURKEY]
persona = "Opportunistic; strikes when neighbors are distracted."
```

- [ ] **Step 6: Verify the CLI parses and errors cleanly without a key**

Run: `.venv/bin/diplomacy-ai run --config game.toml --out /tmp/dipruns` (Ctrl-C after it starts making calls, or expect an auth error if no `GEMINI_API_KEY`).
Expected: It loads config and begins; without a key LiteLLM raises an auth error — confirming wiring is correct. No crash before that point.

- [ ] **Step 7: Commit**

```bash
git add diplomacy_ai/cli.py game.toml tests/test_cli.py
git commit -m "feat: add CLI entry point and sample config"
```

---

## Task 12: Opt-in smoke test & README

**Files:**
- Create: `tests/test_smoke.py`
- Create: `README.md`

- [ ] **Step 1: Write the opt-in smoke test**

Create `tests/test_smoke.py`:
```python
"""Real-Gemini smoke test. Skipped unless RUN_SMOKE=1 and GEMINI_API_KEY are set."""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SMOKE") != "1" or not os.environ.get("GEMINI_API_KEY"),
    reason="Set RUN_SMOKE=1 and GEMINI_API_KEY to run the live smoke test",
)


async def test_one_movement_phase_against_gemini(tmp_path):
    from diplomacy import Game
    from diplomacy_ai.cli import build_agents
    from diplomacy_ai.config import GameConfig
    from diplomacy_ai.orchestrator import Orchestrator
    from diplomacy_ai.provider import LiteLLMProvider
    from diplomacy_ai.recorder import Recorder

    config = GameConfig(n_negotiation_rounds=1, max_year=1901,
                        default_model="gemini/gemini-2.5-flash", timeout=60)
    game = Game()
    rec = Recorder(tmp_path / "run")
    agents = build_agents(config, LiteLLMProvider())
    orch = Orchestrator(game, agents, config, rec)
    await orch.run_phase()  # one real movement phase

    assert game.get_current_phase() != "S1901M"
    transcript = (tmp_path / "run" / "transcript" / "S1901M.json").read_text()
    assert "negotiation_sent" in transcript
```

- [ ] **Step 2: Verify it is skipped by default**

Run: `.venv/bin/pytest tests/test_smoke.py -q`
Expected: `1 skipped`

- [ ] **Step 3: Write `README.md`**

```markdown
# Diplomacy AI

Runs a full game of Diplomacy between 7 LLM-controlled powers on the
[`diplomacy`](https://github.com/diplomacy/diplomacy) engine. Powers negotiate
over a fixed number of rounds (private + global press) each movement phase, then
submit orders. All reasoning, messages, and orders are recorded for review.

## Setup

```bash
.venv/bin/pip install -e ".[dev]"
export GEMINI_API_KEY=...   # or any LiteLLM-supported provider key
```

## Run a game

```bash
.venv/bin/diplomacy-ai run --config game.toml
```

Output lands in `runs/<timestamp>/`:
- `game.json` — load in the official diplomacy web UI to watch the board + press.
- `transcript/<phase>.json` — each power's private reasoning, messages, and orders.
- `events.log` — running log.

## Configuration

Edit `game.toml`: set `n_negotiation_rounds`, `max_year`, `default_model`, and
optional per-power `model` / `persona` overrides. Switch models by changing the
model string (any LiteLLM-supported model, e.g. `gemini/gemini-2.5-pro`,
`openai/gpt-4o`, `anthropic/claude-...`).

## Tests

```bash
.venv/bin/pytest -q                       # fast, no network
RUN_SMOKE=1 .venv/bin/pytest tests/test_smoke.py   # live Gemini phase
```
```

- [ ] **Step 4: Run the full suite one final time**

Run: `.venv/bin/pytest -q`
Expected: PASS (all green; smoke test skipped).

- [ ] **Step 5: Commit**

```bash
git add tests/test_smoke.py README.md
git commit -m "test: add opt-in smoke test and README"
```

---

## Done

At this point you have: config loading, a swappable LiteLLM provider, prompt
builders, per-power agents, a recorder, an orchestrator running fixed-round
full-press negotiation with order validation/repair, a CLI, and tests. Set
`GEMINI_API_KEY` and run `diplomacy-ai run --config game.toml`, then load the
resulting `game.json` in the official diplomacy web UI to watch the game.
```
```
