"""Live gateway smoke test. Skipped unless RUN_SMOKE=1 and NGROK_API_KEY are set."""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SMOKE") != "1" or not os.environ.get("NGROK_API_KEY"),
    reason="Set RUN_SMOKE=1 and NGROK_API_KEY to run the live smoke test",
)


async def test_one_movement_phase_against_gateway(tmp_path):
    from diplomacy import Game
    from diplomacy_ai.cli import build_agents
    from diplomacy_ai.config import GameConfig
    from diplomacy_ai.orchestrator import Orchestrator
    from diplomacy_ai.provider import OpenAIProvider
    from diplomacy_ai.recorder import Recorder

    config = GameConfig(n_negotiation_rounds=1, max_year=1901,
                        default_model="openai:openai/gpt-4o-mini", timeout=60)
    game = Game()
    rec = Recorder(tmp_path / "run")
    agents = build_agents(config, OpenAIProvider())
    orch = Orchestrator(game, agents, config, rec)
    await orch.run_phase()

    assert game.get_current_phase() != "S1901M"
    transcript = (tmp_path / "run" / "transcript" / "S1901M.json").read_text()
    assert "negotiation_sent" in transcript
