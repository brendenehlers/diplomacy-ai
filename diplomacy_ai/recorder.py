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
