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
            originally_invalid = list(invalid)
            repair = await agent.decide_orders(view, rejected=invalid)
            repair_valid = [o for o in repair.orders if o in legal]
            repair_invalid = [o for o in repair.orders if o not in legal]
            # Keep first-call valid + repair valid; dropped = originally invalid not fixed + new invalid
            repaired_set = set(repair_valid)
            still_invalid = [o for o in originally_invalid if o not in repaired_set]
            valid = valid + repair_valid
            invalid = still_invalid + repair_invalid
            record.update({
                "orders_raw": list(repair.orders), "reasoning": repair.reasoning,
                "meta": repair.meta, "repaired": True,
            })
        record["orders_final"] = valid
        record["dropped"] = invalid
        return power, valid, record
