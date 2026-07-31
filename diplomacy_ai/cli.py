"""Command-line entry point: `diplomacy-ai run --config game.toml`."""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import time
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


def _stamp(run_dir: Path):
    """Cheap fingerprint of everything the viewer reads, to skip idle rebuilds."""
    out = []
    for p in sorted(run_dir.glob("**/*.json")):
        try:
            out.append((str(p), p.stat().st_mtime_ns))
        except FileNotFoundError:
            pass
    return out


def watch(run_dir: str | Path, out: str | None, map_name: str, every: float) -> None:
    """Rebuild viewer.html as the run writes phases, until interrupted.

    The page reloads itself on the same interval, so an open tab follows the
    game. A run in progress is rewriting these files underneath us; a rebuild
    that catches a half-written file is simply retried on the next tick.
    """
    run_dir = Path(run_dir)
    print(f"Watching {run_dir} every {every:g}s — the page reloads itself. Ctrl-C to stop.")
    last = None
    while True:
        stamp = _stamp(run_dir)
        if stamp != last:
            try:
                path = build_viewer(run_dir, out, map_name=map_name, refresh=every)
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as exc:
                print(f"{time.strftime('%H:%M:%S')} run still writing ({exc.__class__.__name__});"
                      " retrying")
            else:
                last = stamp
                print(f"{time.strftime('%H:%M:%S')} rebuilt {path}")
        time.sleep(every)


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
    view_p.add_argument("--watch", nargs="?", type=float, const=10.0, default=None,
                        metavar="SECONDS",
                        help="Keep rebuilding while the run plays, and make the page "
                             "reload itself on the same interval (default 10s)")
    args = parser.parse_args(argv)

    # Provider failures log here; without this they'd only reach the transcript.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "viewer":
        if args.watch:
            try:
                watch(args.run_dir, args.out, args.map, args.watch)
            except KeyboardInterrupt:
                print("\nStopped watching.")
            return
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
