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
