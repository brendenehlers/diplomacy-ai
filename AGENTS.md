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
| Rebuild a run's viewer | `just viewer <run_dir>` | `.venv/bin/diplomacy-ai viewer <run_dir>` |
| Follow a live run | `just follow` | `.venv/bin/diplomacy-ai viewer <run_dir> --watch 10` |
| CLI help | `just help` | `.venv/bin/diplomacy-ai run --help` |

## Caveats

- **Always use the venv** at `.venv/` (`.venv/bin/...`). Python is **3.14**, so
  `tomllib` is stdlib (no `tomli` dependency).
- **All LLM calls go through the ngrok AI Gateway** (`https://gateway.ngrok.ai/v1`),
  an OpenAI-compatible endpoint fronting many providers behind one credential.
  Set `NGROK_API_KEY` in `.env`; override the host with `NGROK_BASE_URL` only for a
  custom gateway. The fast test suite uses a fake provider and needs **no network**.
- **The smoke test is opt-in:** skipped unless both `RUN_SMOKE=1` and
  `NGROK_API_KEY` are set. It makes real API calls (costs money).
- **Module boundaries are deliberate — keep them:**
  - `orchestrator.py` is the **only** module that imports `diplomacy` game logic.
    (`viewer/` reads a map SVG out of the installed `diplomacy` package, but
    touches no game classes.)
  - `provider.py` is the **only** module that imports the `openai` SDK.
  - `models.py` and `prompts.py` are pure (no I/O, no engine/LLM imports).
  Swapping the engine or LLM backend should touch exactly one file.
- **Switching models:** change the `model` string in `game.toml` (per-power) or
  `default_model`. Ids use the gateway's `provider:author/model` form, e.g.
  `openai:openai/gpt-4o-mini`, `anthropic:anthropic/claude-sonnet-4`. The string is
  passed through verbatim — bad ids fail at call time, not at config load.
- **Order handling:** LLM orders are validated against the engine's legal-order
  list, with one repair re-prompt, then illegal orders are dropped (unit holds).
  The engine never receives an illegal order.
- **Watching a game:** output lands in `runs/<timestamp>/`. `transcript/<phase>.json`
  holds each power's private reasoning, messages, and orders (`runs/` is gitignored).
  Each run also writes a standalone `viewer.html` (board + all phases + model report);
  `diplomacy_ai/viewer/` builds it from disk alone, so it works on any run directory,
  including ones made before `config.json` was recorded.
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
