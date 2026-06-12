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
