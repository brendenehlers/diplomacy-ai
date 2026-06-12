from diplomacy_ai.config import GameConfig, load_config


def test_defaults_apply_when_power_omitted():
    cfg = GameConfig(default_model="gemini/x")
    assert cfg.model_for("FRANCE") == "gemini/x"
    assert cfg.persona_for("FRANCE") == ""
    assert cfg.n_negotiation_rounds == 3


def test_per_power_overrides():
    cfg = GameConfig(
        default_model="gemini/x",
        powers={"FRANCE": {"model": "gemini/pro", "persona": "bold"}},
    )
    assert cfg.model_for("FRANCE") == "gemini/pro"
    assert cfg.persona_for("FRANCE") == "bold"
    cfg2 = GameConfig(default_model="gemini/x", powers={"ITALY": {"persona": "shy"}})
    assert cfg2.model_for("ITALY") == "gemini/x"
    assert cfg2.persona_for("ITALY") == "shy"


def test_load_config_reads_toml_and_uppercases_powers(tmp_path):
    p = tmp_path / "game.toml"
    p.write_text(
        'n_negotiation_rounds = 2\n'
        'default_model = "gemini/flash"\n'
        '[powers.france]\n'
        'persona = "cautious"\n'
    )
    cfg = load_config(p)
    assert cfg.n_negotiation_rounds == 2
    assert cfg.persona_for("FRANCE") == "cautious"
