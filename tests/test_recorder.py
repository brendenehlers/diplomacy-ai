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


def test_save_config_file_copies_source_toml(tmp_path):
    src = tmp_path / "game.toml"
    src.write_text('max_year = 1905\n')
    rec = Recorder(tmp_path / "run")
    rec.save_config_file(src)
    assert (tmp_path / "run" / "game.toml").read_text() == 'max_year = 1905\n'


def test_log_appends_lines(tmp_path):
    rec = Recorder(tmp_path / "run")
    rec.log("first")
    rec.log("second")
    assert (tmp_path / "run" / "events.log").read_text() == "first\nsecond\n"
