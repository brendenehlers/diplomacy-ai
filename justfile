# Diplomacy AI task runner. Run `just` to list recipes.
# All Python runs through the project venv at .venv.

# Load environment variables from .env (copy .env.example to .env first).
set dotenv-load := true

venv := ".venv/bin"

# Path to the official diplomacy web UI bundled in the installed package.
web_src := `.venv/bin/python -c "import diplomacy,os;print(os.path.join(os.path.dirname(diplomacy.__file__),'web'))"`

# List available recipes
default:
    @just --list

# Install the package + dev dependencies (editable)
install:
    {{venv}}/pip install -e ".[dev]"

# Run the full test suite (fast, no network)
test:
    {{venv}}/pytest -q

# Run a single test file or node, e.g. `just test-one tests/test_agent.py`
test-one target:
    {{venv}}/pytest {{target}} -v

# Run the live smoke test against the ngrok gateway (needs NGROK_API_KEY)
test-smoke:
    RUN_SMOKE=1 {{venv}}/pytest tests/test_smoke.py -v

# Run a full game with the sample config (LM Studio must be running; see .env)
run config="game.toml":
    {{venv}}/diplomacy-ai run --config {{config}}

# Run a game writing output to a custom directory
run-out config="game.toml" out="runs":
    {{venv}}/diplomacy-ai run --config {{config}} --out {{out}}

# Rebuild the standalone HTML viewer for a run (runs also write one automatically)
viewer run_dir:
    {{venv}}/diplomacy-ai viewer {{run_dir}}

# Build the viewer for the most recent run and open it
watch-last:
    {{venv}}/diplomacy-ai viewer "$(ls -td runs/*/ | head -1)"
    open "$(ls -td runs/*/ | head -1)viewer.html"

# Follow the most recent run live: open its viewer, then rebuild while it plays
follow every="10":
    dir="$(ls -td runs/*/ | head -1)" && {{venv}}/diplomacy-ai viewer "$dir" && open "$dir/viewer.html" && {{venv}}/diplomacy-ai viewer "$dir" --watch {{every}}

# Show CLI help
help:
    {{venv}}/diplomacy-ai run --help

# --- Watching a game in the official diplomacy web UI ---
# Flow: `just serve-engine` (one terminal) + `just serve-ui` (another), open
# http://localhost:3000, connect to localhost:8432, register any user/password,
# then "Load a game from disk" and pick runs/<timestamp>/game.json.

# One-time: copy the bundled web UI into ./ui and install its npm deps
ui-setup:
    test -d ui || rsync -a --exclude node_modules --exclude build "{{web_src}}/" ui/
    cd ui && npm install

# Serve the diplomacy websocket server on :8432 (first launch precomputes
# convoy paths and can take several minutes — wait for "Serving forever")
serve-engine port="8432":
    {{venv}}/python -m diplomacy.server.run --port={{port}}

# Serve the web UI dev server (run `just ui-setup` first). Default port 3000;
# pass another if it's taken, e.g. `just serve-ui 3007`. The legacy
# OpenSSL/preflight flags are required for react-scripts 3 on Node 17+.
serve-ui port="3000":
    cd ui && PORT={{port}} BROWSER=none SKIP_PREFLIGHT_CHECK=true NODE_OPTIONS=--openssl-legacy-provider npm start
