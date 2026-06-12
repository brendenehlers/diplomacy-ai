# AGENTS.md

Guidance for AI agents working in this repo. The app is the **AI layer** for an
LLM-driven Diplomacy game; the [`diplomacy`](https://github.com/diplomacy/diplomacy)
package is the game engine and is treated as a black box.

## Commands

A `justfile` wraps everything. Prefer it; the raw equivalents are shown for clarity.

| Task | Just recipe | Raw command |
|------|-------------|-------------|
| Install deps | `just install` | `.venv/bin/pip install -e ".[dev]"` |
| Run tests (fast) | `just test` | `.venv/bin/pytest -q` |
| One test file | `just test-one tests/test_x.py` | `.venv/bin/pytest <path> -v` |
| Live smoke test | `just test-smoke` | `RUN_SMOKE=1 .venv/bin/pytest tests/test_smoke.py` |
| Run a game | `just run` | `.venv/bin/diplomacy-ai run --config game.toml` |
| CLI help | `just help` | `.venv/bin/diplomacy-ai run --help` |

## Caveats

- **Always use the venv** at `.venv/` (`.venv/bin/...`). Python is **3.14**, so
  `tomllib` is stdlib (no `tomli` dependency).
- **API key:** real games and the smoke test need `GEMINI_API_KEY` (or another
  LiteLLM-supported provider key matching the configured model). The default
  model is `gemini/gemini-2.5-pro`. The fast test suite uses a fake provider and
  needs **no network**.
- **The smoke test is opt-in:** skipped unless both `RUN_SMOKE=1` and
  `GEMINI_API_KEY` are set. It makes real API calls (costs money).
- **Module boundaries are deliberate — keep them:**
  - `orchestrator.py` is the **only** module that imports `diplomacy` game logic.
  - `provider.py` is the **only** module that imports `litellm`.
  - `models.py` and `prompts.py` are pure (no I/O, no engine/LLM imports).
  Swapping the engine or LLM backend should touch exactly one file.
- **Switching models:** change the `model` string in `game.toml` (per-power) or
  `default_model`. Any LiteLLM model id works (`gemini/...`, `openai/...`,
  `anthropic/...`).
- **Order handling:** LLM orders are validated against the engine's legal-order
  list, with one repair re-prompt, then illegal orders are dropped (unit holds).
  The engine never receives an illegal order.
- **Watching a game:** output lands in `runs/<timestamp>/`. Load `game.json` in
  the official `diplomacy` web UI for the board + press; `transcript/<phase>.json`
  holds each power's private reasoning, messages, and orders. `runs/` is gitignored.
- **Tests:** pytest runs with `asyncio_mode = "auto"` — async tests need no
  decorator. `tests/` is a package, so `from tests.conftest import ...` works.
- A `DeprecationWarning` about `datetime.utcfromtimestamp` originates **inside the
  `diplomacy` package**, not our code — ignore it.

## Spec & plan

Design and implementation history live in `docs/superpowers/specs/` and
`docs/superpowers/plans/`.
