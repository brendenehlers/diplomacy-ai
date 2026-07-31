"""Persistence: saved-game JSON, per-phase transcripts, event log."""
from __future__ import annotations

import datetime
import json
import shutil
import sys
from pathlib import Path

from diplomacy.utils.export import to_saved_game_format


class Recorder:
    def __init__(self, run_dir: str | Path):
        self.run_dir = Path(run_dir)
        (self.run_dir / "transcript").mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.log"

    def save_config(self, config) -> None:
        """Snapshot the run's settings so the viewer can show what was configured."""
        (self.run_dir / "config.json").write_text(
            json.dumps(config.model_dump(), indent=2, default=str))

    def save_config_file(self, config_path: str | Path) -> None:
        """Copy the config file verbatim so the run's setup can be audited later."""
        src = Path(config_path)
        shutil.copyfile(src, self.run_dir / src.name)

    def save_game(self, game) -> None:
        data = to_saved_game_format(game)
        (self.run_dir / "game.json").write_text(json.dumps(data, indent=2))

    def record_phase(self, phase: str, phase_records: dict) -> None:
        path = self.run_dir / "transcript" / f"{phase}.json"
        path.write_text(json.dumps(phase_records, indent=2, default=str))

    def log(self, message: str, echo: bool = True) -> None:
        """Append to events.log and (by default) mirror it to the console.

        The file keeps the bare message; only the console gets a timestamp, so
        a long run is watchable live without changing the on-disk format.
        """
        with self.events_path.open("a") as f:
            f.write(message + "\n")
        if echo:
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] {message}", file=sys.stderr, flush=True)
