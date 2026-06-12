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
- **Default model is local:** `lm_studio/qwen/qwen3-4b-thinking-2507`, served by
  LM Studio's OpenAI-compatible endpoint. Before a real run, start LM Studio with
  the model loaded and export `LM_STUDIO_API_BASE=http://localhost:1234/v1` and
  `LM_STUDIO_API_KEY=lm-studio` (any non-empty string). To use a hosted provider
  instead, change the model in `game.toml` and set its key (e.g. `GEMINI_API_KEY`).
  The fast test suite uses a fake provider and needs **no network or LM Studio**.
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
- **Watching a game:** output lands in `runs/<timestamp>/`. `transcript/<phase>.json`
  holds each power's private reasoning, messages, and orders (`runs/` is gitignored).
  To use the official web UI: `just ui-setup` once, then `just serve-engine`
  (websocket server on :8432 — first launch precomputes convoy paths and takes a
  few minutes) and `just serve-ui` (react-scripts dev server on :3000; pass a port
  arg if 3000 is taken). In the UI: Connect to localhost:8432 → register/login →
  "Load a game from disk" → `game.json`. The UI shows board + press only, not the
  private reasoning. The `ui/` dir is a gitignored local copy of the package's web
  app; `serve-ui` sets `NODE_OPTIONS=--openssl-legacy-provider` (required for
  react-scripts 3 on Node 17+).
- **Tests:** pytest runs with `asyncio_mode = "auto"` — async tests need no
  decorator. `tests/` is a package, so `from tests.conftest import ...` works.
- A `DeprecationWarning` about `datetime.utcfromtimestamp` originates **inside the
  `diplomacy` package**, not our code — ignore it.

## Spec & plan

Design and implementation history live in `docs/superpowers/specs/` and
`docs/superpowers/plans/`.
