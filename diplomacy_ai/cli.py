"""Command-line entry point: `diplomacy-ai run --config game.toml`."""
from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
from pathlib import Path

from diplomacy import Game

from .agent import PowerAgent
from .config import GameConfig, load_config
from .orchestrator import POWERS, Orchestrator
from .provider import OpenAIProvider
from .recorder import Recorder
from .viewer import build_viewer


def build_agents(config: GameConfig, provider) -> dict[str, PowerAgent]:
    return {
        p: PowerAgent(
            power_name=p, model=config.model_for(p), persona=config.persona_for(p),
            provider=provider, temperature=config.temperature, timeout=config.timeout,
            end_year=config.max_year,
        )
        for p in POWERS
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="diplomacy-ai")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run a full game")
    run_p.add_argument("--config", required=True, help="Path to game.toml")
    run_p.add_argument("--out", default="runs", help="Output directory for runs")
    run_p.add_argument("--no-viewer", action="store_true",
                       help="Skip writing viewer.html at the end of the run")
    view_p = sub.add_parser("viewer", help="Build viewer.html for an existing run")
    view_p.add_argument("run_dir", help="Path to a runs/<timestamp> directory")
    view_p.add_argument("--out", default=None, help="Output file (default: <run_dir>/viewer.html)")
    view_p.add_argument("--map", default="standard", help="Map variant to render")
    args = parser.parse_args(argv)

    # Provider failures log here; without this they'd only reach the transcript.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "viewer":
        path = build_viewer(args.run_dir, args.out, map_name=args.map)
        print(f"Viewer written to {path}")
        return

    config = load_config(args.config)
    provider = OpenAIProvider()
    game = Game()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    recorder = Recorder(Path(args.out) / ts)
    recorder.save_config(config)
    recorder.save_config_file(args.config)
    agents = build_agents(config, provider)
    orch = Orchestrator(game, agents, config, recorder)

    asyncio.run(orch.run())
    print(f"Done. Run saved to {recorder.run_dir}")
    if not args.no_viewer:
        print(f"Viewer written to {build_viewer(recorder.run_dir)}")
