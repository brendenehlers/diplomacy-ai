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
        provider: Provider, temperature: float, timeout: int, end_year: int,
    ):
        self.power_name = power_name
        self.model = model
        self.persona = persona
        self.provider = provider
        self.temperature = temperature
        self.timeout = timeout
        self.end_year = end_year

    async def negotiate(
        self, view: PowerView, inbox: list[InMessage],
        round_num: int, total_rounds: int,
    ) -> NegotiationResult:
        system, user = negotiation_prompt(
            view, self.persona, inbox, round_num, total_rounds, self.end_year)
        try:
            c = await self.provider.complete(
                model=self.model, system=system, user=user,
                schema=NEGOTIATION_SCHEMA, schema_name="negotiation",
                temperature=self.temperature, timeout=self.timeout,
            )
        except ProviderError as e:
            return NegotiationResult(
                reasoning=f"[provider error: no messages sent] {e}", messages=[],
                meta={"error": str(e)},
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
        system, user = orders_prompt(view, self.persona, self.end_year, rejected)
        try:
            c = await self.provider.complete(
                model=self.model, system=system, user=user,
                schema=ORDERS_SCHEMA, schema_name="orders",
                temperature=self.temperature, timeout=self.timeout,
            )
        except ProviderError as e:
            return OrderResult(reasoning=f"[provider error: holding] {e}", orders=[],
                               meta={"error": str(e)})
        orders = [str(o).strip() for o in c.data.get("orders", []) if str(o).strip()]
        return OrderResult(reasoning=c.data.get("reasoning", ""), orders=orders, meta=c.meta)
