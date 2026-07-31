"""Build a self-contained HTML viewer for a finished run.

One public entry point, `build_viewer(run_dir)`. It reads only what a run wrote
to disk, so it works on any run directory — including ones made before the
viewer existed (model details are recovered from per-call metadata when no
`config.json` was saved).
"""
from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


# --------------------------------------------------------------------------
# map geometry
# --------------------------------------------------------------------------

def extract_map(map_name: str = "standard", svg_path: str | Path | None = None) -> dict:
    """Pull province shapes, unit anchor points and labels out of a jDip map SVG.

    The engine ships these maps; we read the installed copy rather than
    vendoring one, so the board always matches the engine in use.
    """
    if svg_path is None:
        # Static asset lookup, not engine logic — no game classes are touched.
        svg_path = resources.files("diplomacy") / "maps" / "svg" / f"{map_name}.svg"
    raw = Path(svg_path).read_text()

    # The DOCTYPE points at a local DTD that ElementTree would try to resolve.
    import xml.etree.ElementTree as ET
    cleaned = re.sub(r"<!DOCTYPE.*?>", "", raw, flags=re.S).replace(
        'xmlns:jdipNS="svg.dtd"', 'xmlns:jdipNS="http://jdip"')
    root = ET.fromstring(cleaned)
    NS = "{http://www.w3.org/2000/svg}"

    def layer(name):
        for g in root:
            if g.get("id") == name:
                return g
        return []

    paths = []
    for p in layer("MapLayer"):
        if p.tag != NS + "path":
            continue
        pid = (p.get("id") or "").lstrip("_")
        if pid:
            paths.append({"id": pid.upper(), "c": p.get("class") or "", "d": p.get("d")})

    units = {}
    for m in re.finditer(
        r'<jdipNS:PROVINCE name="([^"]+)">\s*<jdipNS:UNIT x="([\d.]+)" y="([\d.]+)"', raw
    ):
        key = m.group(1).upper().replace("-", "/")
        units[key] = [round(float(m.group(2)), 1), round(float(m.group(3)), 1)]

    sc = {}
    for u in layer("SupplyCenterLayer"):
        i = u.get("id") or ""
        if i.startswith("sc_"):
            sc[i[3:].upper()] = [round(float(u.get("x")) + 10, 1),
                                 round(float(u.get("y")) + 10, 1)]

    # Angled labels (POR, ROM, SKA on the standard map) carry x="0" y="0" and
    # place themselves with a transform; keep it or they all stack at the origin.
    labels = []
    for t in layer("BriefLabelLayer"):
        if t.tag != NS + "text" or not (t.text or "").strip():
            continue
        lab = {"x": round(float(t.get("x") or 0), 1),
               "y": round(float(t.get("y") or 0), 1),
               "t": t.text.strip()}
        if t.get("transform"):
            lab["tr"] = t.get("transform")
        labels.append(lab)

    # Starting viewBox only. It is not trustworthy — on the standard map the
    # source box is both padded and too small (Syria and Armenia fall outside
    # it) — so the page re-fits it by measuring the rendered paths.
    return {"vb": root.get("viewBox"),
            "paths": paths, "units": units, "sc": sc, "labels": labels}


# --------------------------------------------------------------------------
# run data
# --------------------------------------------------------------------------

def _phase_sort_key(name: str):
    return (int(name[1:5]), {"S": 0, "F": 1, "W": 2}.get(name[0], 3), name)


def build_payload(run_dir: str | Path) -> dict:
    """Fold game.json, the per-phase transcripts and config.json into one blob."""
    run_dir = Path(run_dir)
    game = json.loads((run_dir / "game.json").read_text())

    transcripts = {}
    tdir = run_dir / "transcript"
    if tdir.is_dir():
        for f in tdir.glob("*.json"):
            transcripts[f.stem] = json.loads(f.read_text())

    powers = list(game["phases"][0]["state"]["units"]) if game["phases"] else POWERS

    phases = []
    for ph in game["phases"]:
        name = ph["name"]
        t = transcripts.get(name, {})
        press, dec = {}, {}
        for p in powers:
            rec = t.get(p) or {}
            rounds = [{"r": x.get("round"), "why": x.get("reasoning", ""),
                       "m": [[m["to"], m["body"]] for m in x.get("messages", [])]}
                      for x in rec.get("negotiation_sent", [])]
            if rounds:
                press[p] = rounds
            o = rec.get("orders")
            if o:
                dec[p] = {"why": o.get("reasoning", ""), "drop": o.get("dropped", [])}
        phases.append({
            "n": name,
            "u": {p: ph["state"]["units"].get(p, []) for p in powers},
            "c": {p: ph["state"]["centers"].get(p, []) for p in powers},
            "o": ph.get("orders") or {},
            "press": press, "dec": dec,
        })

    return {"powers": powers, "phases": phases,
            "setup": _setup(run_dir, game, powers),
            "models": _model_report(transcripts, powers)}


def _setup(run_dir: Path, game: dict, powers: list[str]) -> dict:
    """Starting position plus whatever configuration the run recorded."""
    cfg_path = run_dir / "config.json"
    cfg = json.loads(cfg_path.read_text()) if cfg_path.is_file() else {}
    first = game["phases"][0] if game["phases"] else {"state": {"units": {}, "centers": {}}}
    pcfg = cfg.get("powers", {})
    return {
        "run": run_dir.name,
        "settings": {k: cfg.get(k) for k in
                     ("n_negotiation_rounds", "max_year", "temperature", "timeout")},
        "default_model": cfg.get("default_model"),
        "start_phase": first.get("name"),
        "powers": {p: {
            "model": (pcfg.get(p) or {}).get("model") or cfg.get("default_model"),
            "persona": (pcfg.get(p) or {}).get("persona", ""),
            "units": first["state"]["units"].get(p, []),
            "centers": first["state"]["centers"].get(p, []),
        } for p in powers},
        "has_config": bool(cfg),
    }


def _model_report(transcripts: dict, powers: list[str]) -> dict:
    """Per-power call tally recovered from the metadata on every completion."""
    out = {p: {"calls": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0,
               "cost": 0.0, "cost_known": False, "latency": 0.0, "models": {}}
           for p in powers}
    for name in sorted(transcripts, key=_phase_sort_key):
        for p, rec in transcripts[name].items():
            if p not in out:
                continue
            metas = [x.get("meta") or {} for x in rec.get("negotiation_sent", [])]
            if rec.get("orders"):
                metas.append(rec["orders"].get("meta") or {})
            for m in metas:
                if not m:
                    continue
                s = out[p]
                s["calls"] += 1
                if m.get("error"):
                    s["errors"] += 1
                    continue
                if m.get("model"):
                    s["models"][m["model"]] = s["models"].get(m["model"], 0) + 1
                s["prompt_tokens"] += m.get("prompt_tokens") or 0
                s["completion_tokens"] += m.get("completion_tokens") or 0
                s["latency"] += m.get("latency") or 0
                if isinstance(m.get("cost"), (int, float)):
                    s["cost"] += m["cost"]
                    s["cost_known"] = True
    return out


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def _asset(name: str) -> str:
    return (resources.files(__package__) / "assets" / name).read_text()


def build_viewer(run_dir: str | Path, out_path: str | Path | None = None,
                 map_name: str = "standard", title: str | None = None) -> Path:
    """Write a single self-contained HTML file for `run_dir`. Returns its path."""
    run_dir = Path(run_dir)
    out_path = Path(out_path) if out_path else run_dir / "viewer.html"
    payload = build_payload(run_dir)
    title = title or f"Diplomacy AI — run {run_dir.name}"

    html = _asset("shell.html")
    html = html.replace("{{TITLE}}", title)
    html = html.replace("/*{{CSS}}*/", _asset("app.css"))
    html = html.replace("/*{{JS}}*/", _asset("app.js"))
    html = html.replace('"{{DATA}}"', _embed(payload))
    html = html.replace('"{{MAP}}"', _embed(extract_map(map_name)))
    out_path.write_text(html)
    return out_path


def _embed(obj) -> str:
    """JSON for a <script type="application/json"> block.

    A message body containing "</script>" would otherwise close the tag early,
    so the slash is escaped — JSON parses "<\\/" and "</" identically.
    """
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")
