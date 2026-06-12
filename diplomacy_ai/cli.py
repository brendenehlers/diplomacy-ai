"""Command-line entry point: `diplomacy-ai run --config game.toml`."""
from __future__ import annotations

import argparse
import asyncio
import datetime
from pathlib import Path

from diplomacy import Game

from .agent import PowerAgent
from .config import GameConfig, load_config
from .orchestrator import POWERS, Orchestrator
from .provider import LiteLLMProvider
from .recorder import Recorder


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
    args = parser.parse_args(argv)

    config = load_config(args.config)
    provider = LiteLLMProvider()
    game = Game()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    recorder = Recorder(Path(args.out) / ts)
    agents = build_agents(config, provider)
    orch = Orchestrator(game, agents, config, recorder)

    asyncio.run(orch.run())
    print(f"Done. Run saved to {recorder.run_dir}")
