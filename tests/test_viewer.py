import json

import pytest

from diplomacy_ai.config import GameConfig, PowerConfig
from diplomacy_ai.recorder import Recorder
from diplomacy_ai.viewer import build_payload, build_viewer, extract_map

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


def _units(**over):
    base = {p: [] for p in POWERS}
    base.update(over)
    return base


def make_run(tmp_path, with_config=True, message="ally?"):
    run = tmp_path / "run"
    (run / "transcript").mkdir(parents=True)
    game = {"phases": [
        {"name": "S1901M",
         "state": {"units": _units(FRANCE=["A PAR", "F BRE"], GERMANY=["A MUN"]),
                   "centers": _units(FRANCE=["PAR", "BRE"], GERMANY=["MUN"])},
         "orders": {"FRANCE": ["A PAR - BUR", "F BRE - MAO"], "GERMANY": ["A MUN H"]},
         "results": {}, "messages": []},
        {"name": "F1901M",
         "state": {"units": _units(FRANCE=["A BUR", "F MAO"], GERMANY=["A MUN"]),
                   "centers": _units(FRANCE=["PAR", "BRE"], GERMANY=["MUN"])},
         "orders": {"FRANCE": ["A BUR - MUN"]}, "results": {}, "messages": []},
    ]}
    (run / "game.json").write_text(json.dumps(game))
    (run / "transcript" / "S1901M.json").write_text(json.dumps({
        "FRANCE": {
            "negotiation_sent": [{"round": 1, "reasoning": "probe Germany",
                                  "messages": [{"to": "GERMANY", "body": message}],
                                  "meta": {"model": "prov:a/m", "prompt_tokens": 10,
                                           "completion_tokens": 5, "latency": 1.0,
                                           "cost": 0.5}}],
            "orders": {"reasoning": "advance", "orders_final": ["A PAR - BUR"],
                       "dropped": ["A PAR - XXX"],
                       "meta": {"model": "prov:a/m", "prompt_tokens": 20,
                                "completion_tokens": 8, "latency": 2.0, "cost": 0.25}},
        },
        "GERMANY": {"orders": {"reasoning": "hold", "orders_final": ["A MUN H"],
                               "dropped": [], "meta": {"error": "boom"}}},
    }))
    if with_config:
        cfg = GameConfig(n_negotiation_rounds=2, max_year=1905, timeout=42,
                         default_model="prov:a/m",
                         powers={"FRANCE": PowerConfig(model="prov:b/n", persona="bold")})
        Recorder(run).save_config(cfg)
    return run


def test_payload_merges_game_and_transcript(tmp_path):
    p = build_payload(make_run(tmp_path))
    assert [x["n"] for x in p["phases"]] == ["S1901M", "F1901M"]
    first = p["phases"][0]
    assert first["o"]["FRANCE"] == ["A PAR - BUR", "F BRE - MAO"]
    assert first["press"]["FRANCE"][0]["m"] == [["GERMANY", "ally?"]]
    assert first["dec"]["FRANCE"]["drop"] == ["A PAR - XXX"]


def test_setup_prefers_config_over_defaults(tmp_path):
    s = build_payload(make_run(tmp_path))["setup"]
    assert s["has_config"] is True
    assert s["settings"]["max_year"] == 1905
    assert s["powers"]["FRANCE"]["model"] == "prov:b/n"      # per-power override
    assert s["powers"]["GERMANY"]["model"] == "prov:a/m"     # falls back to default
    assert s["powers"]["FRANCE"]["persona"] == "bold"
    assert s["powers"]["FRANCE"]["units"] == ["A PAR", "F BRE"]


def test_setup_survives_a_run_with_no_config(tmp_path):
    s = build_payload(make_run(tmp_path, with_config=False))["setup"]
    assert s["has_config"] is False
    assert s["powers"]["FRANCE"]["model"] is None    # viewer falls back to observed model


def test_model_report_counts_calls_tokens_and_errors(tmp_path):
    m = build_payload(make_run(tmp_path))["models"]
    fr = m["FRANCE"]
    assert fr["calls"] == 2 and fr["errors"] == 0
    assert fr["prompt_tokens"] == 30 and fr["completion_tokens"] == 13
    assert fr["models"] == {"prov:a/m": 2}
    assert fr["cost_known"] is True and fr["cost"] == pytest.approx(0.75)
    assert m["GERMANY"]["calls"] == 1 and m["GERMANY"]["errors"] == 1
    assert m["GERMANY"]["models"] == {}               # errored calls report no model


def test_build_viewer_writes_one_self_contained_file(tmp_path):
    out = build_viewer(make_run(tmp_path))
    html = out.read_text()
    assert out.name == "viewer.html"
    assert html.startswith("<!doctype html>")
    # no external fetches: the CSP-free requirement is that nothing is linked out
    assert "<link" not in html and "src=" not in html
    assert "{{DATA}}" not in html and "{{CSS}}" not in html and "{{JS}}" not in html
    assert "A PAR - BUR" in html
    # The page reads DAI_REFRESH either way; only a --watch build declares it,
    # and without a value the reload never arms — a finished run stays put.
    assert "DAI_REFRESH=" not in html


def test_watch_interval_makes_the_page_reload_itself(tmp_path):
    html = build_viewer(make_run(tmp_path), refresh=10).read_text()
    assert "window.DAI_REFRESH=10" in html
    # A <meta refresh> reloads the bare URL and drops the fragment the page keeps
    # the reader's phase and power in, so the reload has to come from the page.
    assert "http-equiv" not in html
    # sub-second intervals would hammer the browser; the interval floors at one
    html = build_viewer(make_run(tmp_path / "b"), refresh=0.2).read_text()
    assert "window.DAI_REFRESH=1" in html


def test_embedded_json_cannot_break_out_of_the_script_tag(tmp_path):
    run = make_run(tmp_path, message="</script><script>alert(1)</script>")
    html = build_viewer(run).read_text()
    assert "</script><script>alert(1)" not in html
    assert "<\\/script>" in html


def test_extract_map_returns_geometry_for_the_standard_board():
    m = extract_map()
    assert len(m["paths"]) > 50
    assert m["units"]["PAR"] and m["sc"]["PAR"]
    assert all(k in m for k in ("vb", "paths", "units", "sc", "labels"))
    # Provinces the source viewBox clips must still be present; the page
    # re-fits the box around them at render time.
    ids = {p["id"] for p in m["paths"]}
    assert {"SYR", "ARM", "SEV", "NAF"} <= ids
