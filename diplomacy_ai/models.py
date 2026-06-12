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
