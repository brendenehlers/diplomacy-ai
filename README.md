# Diplomacy AI

Runs a full game of Diplomacy between 7 LLM-controlled powers on the
[`diplomacy`](https://github.com/diplomacy/diplomacy) engine. Powers negotiate
over a fixed number of rounds (private + global press) each movement phase, then
submit orders. All reasoning, messages, and orders are recorded for review.

## Setup

```bash
.venv/bin/pip install -e ".[dev]"
export GEMINI_API_KEY=...   # or any LiteLLM-supported provider key
```

## Run a game

```bash
.venv/bin/diplomacy-ai run --config game.toml
```

Output lands in `runs/<timestamp>/`:
- `game.json` — load in the official diplomacy web UI to watch the board + press.
- `transcript/<phase>.json` — each power's private reasoning, messages, and orders.
- `events.log` — running log.

## Configuration

Edit `game.toml`: set `n_negotiation_rounds`, `max_year`, `default_model`, and
optional per-power `model` / `persona` overrides. Switch models by changing the
model string (any LiteLLM-supported model, e.g. `gemini/gemini-2.5-pro`,
`openai/gpt-4o`, `anthropic/claude-...`).

## Tests

```bash
.venv/bin/pytest -q                       # fast, no network
RUN_SMOKE=1 .venv/bin/pytest tests/test_smoke.py   # live Gemini phase
```
