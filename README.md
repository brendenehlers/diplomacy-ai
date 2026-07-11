# Diplomacy AI

Runs a complete game of [Diplomacy](https://en.wikipedia.org/wiki/Diplomacy_(game))
between **7 LLM-controlled powers** on the official
[`diplomacy`](https://github.com/diplomacy/diplomacy) engine.

Each movement phase, the powers **negotiate** over a fixed number of press rounds
(private and global messages), then submit **orders**. Every power's private
reasoning, messages, and orders are recorded so you can review the whole game
afterward — including the plotting that never becomes public.

## What it does

For each phase the engine reports:

1. **Negotiation** (movement phases only) — over `n_negotiation_rounds`, all
   living powers concurrently read their inbox and send new messages, addressed
   to another power (private) or `GLOBAL` (broadcast). Messages are routed and
   delivered to the next round's inboxes.
2. **Orders** — each power with orderable units returns orders as structured
   JSON. Orders are validated against the engine's legal-order list. Illegal
   orders trigger **one repair re-prompt**; anything still illegal is dropped
   (the unit holds). The engine never receives an illegal order.
3. **Process & record** — the engine adjudicates the phase, and the full
   transcript plus the updated saved-game file are written to disk.

The loop continues until the game ends or `max_year` is reached.

## Architecture

Module boundaries are deliberate — swapping the engine or LLM backend touches
exactly one file.

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Entry point (`diplomacy-ai run`); wires everything together |
| `orchestrator.py` | Owns the `Game`, runs the phase loop, routes press. **Only** module importing the `diplomacy` engine |
| `agent.py` | `PowerAgent` — turns a board view into messages and orders |
| `provider.py` | Async LiteLLM wrapper with retries/backoff and token/cost/latency capture. **Only** module importing `litellm` |
| `prompts.py` | System/user prompts + JSON schemas (pure) |
| `models.py` | Shared dataclasses (pure, no I/O) |
| `config.py` | TOML → Pydantic config |
| `recorder.py` | Writes `game.json`, per-phase transcripts, and `events.log` |

## Setup

Python **3.11+** (repo runs on 3.14). All Python goes through the venv at `.venv/`.

```bash
just install                 # or: .venv/bin/pip install -e ".[dev]"
cp .env.example .env         # just auto-loads .env
```

The sample `game.toml` uses Google **Gemini** (`gemini/gemini-3.5-flash`). See
[Play with Gemini](#play-with-gemini) below to get set up.

To run a model **locally** instead (no API key, no cost), use
[LM Studio](https://lmstudio.ai/)'s OpenAI-compatible server: set
`default_model` in `game.toml` to `lm_studio/qwen/qwen3-4b-thinking-2507`, start
LM Studio with that model loaded, and set `LM_STUDIO_API_BASE` /
`LM_STUDIO_API_KEY` in `.env`. Any [LiteLLM-supported](https://docs.litellm.ai/docs/providers)
provider works the same way — change the model and set the matching key.

## Play with Gemini

The quickest way to run your own game. Gemini's free tier is enough to
experiment with.

1. **Get an API key** from [Google AI Studio](https://aistudio.google.com/apikey).
2. **Put it in `.env`** (copied from `.env.example`):

   ```bash
   GEMINI_API_KEY=your-key-here
   ```

   `just` auto-loads `.env`, so nothing else to export.
3. **Pick your model** in `game.toml` — the default is `gemini/gemini-3.5-flash`
   (fast and cheap). Swap in `gemini/gemini-2.5-pro` for stronger play. Any
   `gemini/...` id LiteLLM knows works. You can also set a different `model`
   per power under `[powers.<NAME>]` to pit models against each other.
4. **Run it:**

   ```bash
   just run
   ```

5. **Verify your setup first** (one real Gemini phase) before a full game:

   ```bash
   RUN_SMOKE=1 just test-smoke
   ```

Full games make many calls across all phases — watch your quota/costs if you
raise `n_negotiation_rounds` or `max_year`.

## Run a game

```bash
just run                     # or: .venv/bin/diplomacy-ai run --config game.toml
```

Output lands in `runs/<timestamp>/` (gitignored):

- **`game.json`** — saved-game file; load it in the official web UI to watch the
  board and press.
- **`transcript/<phase>.json`** — each power's private reasoning, sent/received
  messages per round, raw + final orders, dropped orders, and call metadata
  (tokens, cost, latency).
- **`events.log`** — running progress log.

Write to a custom directory with `just run-out game.toml <dir>` or
`--out <dir>`.

## Configuration

Edit `game.toml`:

| Key | Meaning |
|-----|---------|
| `n_negotiation_rounds` | Press rounds per movement phase |
| `max_year` | Stop after this game year |
| `default_model` | LiteLLM model id used for any power without an override |
| `temperature` / `timeout` | Passed to every completion |
| `[powers.<NAME>]` | Per-power `model` and/or `persona` overrides |

Any LiteLLM-supported model id works, e.g. `gemini/gemini-3.5-flash`,
`gemini/gemini-2.5-pro`, `openai/gpt-4o`, `anthropic/claude-...`, or
`lm_studio/qwen/qwen3-4b-thinking-2507` (local). Personas are free-text and shape how
each power negotiates and plays; the sample config ships 7 aggressive ones.

## Watch a game in the official web UI

The `diplomacy` package bundles a React web UI. To replay a finished game:

```bash
just ui-setup        # one-time: copy the UI into ./ui and npm install
just serve-engine    # terminal 1 — websocket server on :8432
                     #   (first launch precomputes convoy paths; wait a few minutes)
just serve-ui        # terminal 2 — web UI on :3000 (pass a port if 3000 is taken,
                     #   e.g. `just serve-ui 3007`)
```

Then open the UI → **Connect** to `localhost:8432` → register any
username/password → log in → **"Load a game from disk"** → pick
`runs/<timestamp>/game.json`.

Notes:
- The UI shows the board and press only; private per-power reasoning lives in
  `transcript/<phase>.json`.
- It's an old react-scripts 3 app; `serve-ui` sets the legacy OpenSSL flag it
  needs on modern Node. `ui/` is gitignored.

## Tests

```bash
just test                              # fast suite, no network (fake provider)
RUN_SMOKE=1 just test-smoke            # opt-in live phase (needs GEMINI_API_KEY, costs money)
just test-one tests/test_agent.py      # a single file
```

The fast suite needs no network or LM Studio. The smoke test is skipped unless
both `RUN_SMOKE=1` and `GEMINI_API_KEY` are set.

## More

Run `just` to list all recipes. See `AGENTS.md` for contributor notes and
`docs/superpowers/` for the original spec and implementation plan.
