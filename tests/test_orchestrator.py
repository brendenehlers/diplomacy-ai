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
    assert "PAR" in view.legal_orders


async def test_collect_orders_keeps_valid_drops_invalid(tmp_path):
    agents = {p: FakeAgent(p) for p in POWERS}
    agents["FRANCE"] = FakeAgent("FRANCE", order_scripts=[["A PAR H", "A PAR - MARS"]])
    orch = _orch(tmp_path, agents)
    view = orch.build_view("FRANCE")
    power, final, record = await orch.collect_power_orders("FRANCE", view)
    assert "A PAR H" in final
    assert "A PAR - MARS" in record["dropped"]


async def test_collect_orders_repairs_then_drops(tmp_path):
    agents = {p: FakeAgent(p) for p in POWERS}
    agents["FRANCE"] = FakeAgent(
        "FRANCE", order_scripts=[["A PAR - MARS"], ["A PAR H"]])
    orch = _orch(tmp_path, agents)
    view = orch.build_view("FRANCE")
    power, final, record = await orch.collect_power_orders("FRANCE", view)
    assert final == ["A PAR H"]
    assert record["repaired"] is True
    assert agents["FRANCE"].order_calls == [None, ["A PAR - MARS"]]


from diplomacy_ai.models import NegotiationResult, OutMessage


def test_route_delivers_private_and_global(tmp_path):
    orch = _orch(tmp_path, {p: FakeAgent(p) for p in POWERS})
    results = {
        "FRANCE": NegotiationResult("r", [
            OutMessage("ENGLAND", "secret"), OutMessage("GLOBAL", "hi all")]),
        "ENGLAND": NegotiationResult("r", []),
    }
    inboxes = orch.route(results)
    eng = [m for m in inboxes["ENGLAND"] if m.body == "secret"]
    assert len(eng) == 1 and eng[0].scope == "private"
    assert all(m.body != "secret" for m in inboxes["GERMANY"])
    assert any(m.body == "hi all" for m in inboxes["GERMANY"])
    assert all(m.body != "hi all" for m in inboxes["FRANCE"])
    assert len(orch.game.messages) == 2


def test_route_returns_inbox_for_every_power(tmp_path):
    orch = _orch(tmp_path, {p: FakeAgent(p) for p in POWERS})
    inboxes = orch.route({"FRANCE": NegotiationResult("r", [])})
    assert set(inboxes.keys()) == set(POWERS)


async def test_run_terminates_at_max_year_and_records(tmp_path):
    agents = {p: FakeAgent(p, order_scripts=[[]] * 50) for p in POWERS}
    orch = _orch(tmp_path, agents, n_negotiation_rounds=1, max_year=1901)
    await orch.run()
    assert int(orch.game.get_current_phase()[1:5]) >= 1902
    assert (tmp_path / "run" / "game.json").exists()
    assert (tmp_path / "run" / "transcript" / "S1901M.json").exists()
    assert "max_year" in (tmp_path / "run" / "events.log").read_text()


async def test_run_phase_sets_valid_orders(tmp_path):
    agents = {p: FakeAgent(p, order_scripts=[[]]) for p in POWERS}
    agents["FRANCE"] = FakeAgent("FRANCE", order_scripts=[["A PAR H"]])
    orch = _orch(tmp_path, agents, n_negotiation_rounds=1, max_year=1920)
    await orch.run_phase()
    assert orch.game.get_current_phase() != "S1901M"
