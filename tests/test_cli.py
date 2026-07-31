import json
from pathlib import Path

import pytest

from diplomacy_ai import cli
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
    assert agents["ITALY"].model == "gemini/x"


def test_watch_rebuilds_only_when_the_run_writes(tmp_path, monkeypatch):
    run = tmp_path / "run"
    (run / "transcript").mkdir(parents=True)
    (run / "game.json").write_text(json.dumps({"phases": []}))

    built = []
    monkeypatch.setattr(cli, "build_viewer",
                        lambda *a, **kw: built.append(kw) or Path("viewer.html"))

    ticks = []
    def fake_sleep(_):
        ticks.append(1)
        if len(ticks) == 1:                       # the run finishes a phase
            (run / "transcript" / "S1901M.json").write_text("{}")
        if len(ticks) == 3:                       # the reader hits Ctrl-C
            raise KeyboardInterrupt
    monkeypatch.setattr(cli.time, "sleep", fake_sleep)

    with pytest.raises(KeyboardInterrupt):
        cli.watch(run, None, "standard", 0.01)

    assert len(built) == 2                        # first build + the new phase; idle tick skipped
    assert built[0]["refresh"] == 0.01            # the page reloads on the watch interval


def test_watch_retries_when_it_catches_a_half_written_file(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    (run / "game.json").write_text("{")           # mid-write by the recorder

    monkeypatch.setattr(cli, "build_viewer",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            json.JSONDecodeError("boom", "{", 1)))
    calls = []
    def fake_sleep(_):
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
    monkeypatch.setattr(cli.time, "sleep", fake_sleep)

    with pytest.raises(KeyboardInterrupt):
        cli.watch(run, None, "standard", 0.01)
    assert len(calls) == 2                        # kept going instead of dying
