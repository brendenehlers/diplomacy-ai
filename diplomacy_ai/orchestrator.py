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

    # --- progress logging helpers ---

    @staticmethod
    def _usage_summary(metas: list[dict]) -> str:
        """One-line token/cost/latency roll-up for a batch of LLM calls."""
        tokens = sum(
            (m.get("prompt_tokens") or 0) + (m.get("completion_tokens") or 0)
            for m in metas
        )
        latency = max((m.get("latency") or 0) for m in metas) if metas else 0
        costs = [m.get("cost") for m in metas if isinstance(m.get("cost"), (int, float))]
        parts = [f"{tokens} tok", f"slowest {latency:.1f}s"]
        if costs:
            parts.append(f"${sum(costs):.4f}")
        return ", ".join(parts)

    def _log_errors(self, metas: dict[str, dict], what: str) -> None:
        for power, meta in metas.items():
            if meta.get("error"):
                self.recorder.log(f"    ! {power} {what} failed: {meta['error']}")

    def _alive_powers(self) -> list[str]:
        state = self.game.get_state()
        return [p for p in POWERS if state["units"][p] or state["centers"][p]]

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
            self.recorder.log(
                f"  negotiation {rnd}/{total}: prompting {len(alive)} powers...")
            results = dict(zip(alive, await asyncio.gather(*coros)))
            counts = " ".join(f"{p[:3]}={len(r.messages)}" for p, r in results.items())
            self.recorder.log(
                f"  negotiation {rnd}/{total}: "
                f"{sum(len(r.messages) for r in results.values())} messages "
                f"({counts}) [{self._usage_summary([r.meta for r in results.values()])}]"
            )
            self._log_errors({p: r.meta for p, r in results.items()}, "negotiation")
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
        alive = self._alive_powers()
        self.recorder.log(f"=== {phase} === {len(alive)} powers alive: {', '.join(alive)}")
        phase_records: dict = {p: {} for p in POWERS}
        if phase.endswith("M"):
            await self._run_negotiation(phase_records)
        order_powers = [p for p in POWERS if self.game.get_orderable_locations(p)]
        if order_powers:
            views = {p: self.build_view(p) for p in order_powers}
            self.recorder.log(f"  orders: prompting {len(order_powers)} powers...")
            collected = await asyncio.gather(
                *[self.collect_power_orders(p, views[p]) for p in order_powers]
            )
            for power, valid, record in collected:
                self.game.set_orders(power, valid)
                phase_records[power]["orders"] = record
                line = f"    {power}: {'; '.join(valid) or '(none)'}"
                if record["repaired"]:
                    line += " (repaired)"
                if record["dropped"]:
                    line += f" [dropped: {', '.join(record['dropped'])}]"
                self.recorder.log(line)
            self.recorder.log(
                f"  orders: {sum(len(v) for _, v, _ in collected)} accepted "
                f"[{self._usage_summary([r['meta'] for _, _, r in collected])}]"
            )
            self._log_errors({p: r["meta"] for p, _, r in collected}, "orders")
        self.recorder.record_phase(phase, phase_records)
        self.recorder.log(f"  processing {phase}...")
        self.game.process()
        self.recorder.save_game(self.game)
        centers = self.game.get_state()["centers"]
        standings = " ".join(f"{p[:3]}={len(centers[p])}" for p in POWERS)
        self.recorder.log(f"  centers: {standings}")

    async def run(self) -> None:
        self.recorder.log(
            f"Starting game: max_year={self.config.max_year}, "
            f"negotiation_rounds={self.config.n_negotiation_rounds}, "
            f"output={self.recorder.run_dir}"
        )
        for p in POWERS:
            self.recorder.log(f"  {p}: {self.config.model_for(p)}")
        self.recorder.save_game(self.game)
        while not self.game.is_game_done:
            phase = self.game.get_current_phase()
            if not phase[1:5].isdigit():  # e.g. COMPLETED/FORMING — not a playable phase
                break
            year = int(phase[1:5])
            if year > self.config.max_year:
                self.recorder.log(f"Reached max_year {self.config.max_year}; stopping.")
                break
            await self.run_phase()
        self.recorder.log("Game finished.")

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
