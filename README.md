# Diplomacy AI

Runs a full game of Diplomacy between 7 LLM-controlled powers on the
[`diplomacy`](https://github.com/diplomacy/diplomacy) engine. Powers negotiate
over a fixed number of rounds (private + global press) each movement phase, then
submit orders. All reasoning, messages, and orders are recorded for review.

## Setup

```bash
.venv/bin/pip install -e ".[dev]"

# Default model runs locally via LM Studio (start it with the model loaded):
export LM_STUDIO_API_BASE=http://localhost:1234/v1
export LM_STUDIO_API_KEY=lm-studio   # any non-empty string

# Or use a hosted provider by changing the model in game.toml, e.g.:
# export GEMINI_API_KEY=...
```

## Run a game

```bash
.venv/bin/diplomacy-ai run --config game.toml
```

Output lands in `runs/<timestamp>/`:
- `game.json` — load in the official diplomacy web UI to watch the board + press.
- `transcript/<phase>.json` — each power's private reasoning, messages, and orders.
- `events.log` — running log.

## Watch a game in the official web UI

The `diplomacy` package bundles its React web UI. To replay a finished game:

```bash
just ui-setup        # one-time: copy the UI into ./ui and npm install

just serve-engine    # terminal 1 — websocket server on :8432
                     # (first launch precomputes convoy paths; wait a few minutes)
just serve-ui        # terminal 2 — web UI on :3000 (pass a port if 3000 is taken,
                     #   e.g. `just serve-ui 3007`)
```

Then open the UI, **Connect** to `localhost:8432`, register any username/password,
log in, and choose **"Load a game from disk"** → `runs/<timestamp>/game.json`.

Notes:
- This shows the board + press only; private per-power reasoning lives in
  `transcript/<phase>.json`.
- The UI is an old react-scripts 3 app; the `serve-ui` recipe sets the legacy
  OpenSSL flag it needs on modern Node. `ui/` is gitignored.

## Configuration

Edit `game.toml`: set `n_negotiation_rounds`, `max_year`, `default_model`, and
optional per-power `model` / `persona` overrides. Switch models by changing the
model string (any LiteLLM-supported model, e.g.
`lm_studio/qwen/qwen3-4b-thinking-2507` (local), `gemini/gemini-2.5-pro`,
`openai/gpt-4o`, `anthropic/claude-...`).

## Tests

```bash
.venv/bin/pytest -q                       # fast, no network
RUN_SMOKE=1 .venv/bin/pytest tests/test_smoke.py   # live Gemini phase
```
