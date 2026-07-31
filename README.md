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
| `provider.py` | Async OpenAI-SDK wrapper (ngrok AI Gateway) with retries/backoff and token/cost/latency capture. **Only** module importing `openai` |
| `prompts.py` | System/user prompts + JSON schemas (pure) |
| `models.py` | Shared dataclasses (pure, no I/O) |
| `config.py` | TOML → Pydantic config |
| `recorder.py` | Writes `config.json`, `game.json`, per-phase transcripts, and `events.log` |
| `viewer/` | Builds a standalone `viewer.html` from a finished run |

## Setup

Python **3.11+** (repo runs on 3.14). All Python goes through the venv at `.venv/`.

```bash
just install                 # or: .venv/bin/pip install -e ".[dev]"
cp .env.example .env         # just auto-loads .env
```

Every model call goes through the [ngrok AI Gateway](https://ngrok.com/docs/ai-gateway/overview)
(`https://gateway.ngrok.ai/v1`) — an OpenAI-compatible endpoint fronting many
providers, so **one key** covers all of them.

## Get running

1. **Get a gateway API key** from ngrok's AI Gateway.
2. **Put it in `.env`** (copied from `.env.example`):

   ```bash
   NGROK_API_KEY=ng-...
   ```

   `just` auto-loads `.env`, so nothing else to export. Set `NGROK_BASE_URL` only
   if you run a custom gateway endpoint.
3. **Pick your models** in `game.toml`. Ids use the gateway's
   `provider:author/model` form — `default_model` applies to every power, and a
   `model` under `[powers.<NAME>]` overrides it for that nation:

   ```toml
   default_model = "openai:openai/gpt-4o-mini"

   [powers.FRANCE]
   model = "anthropic:anthropic/claude-sonnet-4"
   ```

   That's the knob for pitting models and providers against each other — give all
   seven different ids if you want a seven-way bake-off.
4. **Run it:**

   ```bash
   just run
   ```

5. **Verify your setup first** (one real phase) before a full game:

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

- **`viewer.html`** — a standalone page for the whole game: interactive board,
  every phase, every message, and each power's private reasoning. See
  [Share a game](#share-a-game) below.
- **`config.json`** — the settings the run started from (models, personas, limits).
- **`game.json`** — saved-game file; load it in the official web UI to watch the
  board and press.
- **`transcript/<phase>.json`** — each power's private reasoning, sent/received
  messages per round, raw + final orders, dropped orders, and call metadata
  (tokens, cost, latency). `cost` is whatever the gateway reports in `usage`;
  it's `null` if the gateway doesn't return one.
- **`events.log`** — running progress log.

Write to a custom directory with `just run-out game.toml <dir>` or
`--out <dir>`.

## Configuration

Edit `game.toml`:

| Key | Meaning |
|-----|---------|
| `n_negotiation_rounds` | Press rounds per movement phase |
| `max_year` | Stop after this game year |
| `default_model` | Gateway model id used for any power without an override |
| `temperature` / `timeout` | Passed to every completion |
| `[powers.<NAME>]` | Per-power `model` and/or `persona` overrides |

Model ids are `provider:author/model`, e.g. `openai:openai/gpt-4o-mini` or
`anthropic:anthropic/claude-sonnet-4`. The string is sent to the gateway verbatim,
so any id the gateway routes works — an unknown one fails on the first call, not at
startup. Personas are free-text and shape how each power negotiates and plays; the
sample config ships 7 aggressive ones.

## Share a game

Every run writes **`runs/<timestamp>/viewer.html`** — one self-contained file with
no external dependencies, so you can email it, drop it in a bucket, or open it
straight off disk.

```bash
just watch-last                      # build for the newest run and open it
just viewer runs/20260730-135318     # or rebuild for a specific run
```

It contains:

- **Setup** — the model and persona behind each power, the run's settings, and
  each power's opening position.
- **The game** — an interactive board for all phases. Provinces fill with the
  owner's colour as centres change hands; orders draw as arrows (move), dashed
  lines (support), dotted (convoy), rings (hold) and crosses (disband). Step with
  the slider, the ← → keys, or play it through.
- **Per-power panel** — for the selected phase, that power's private reasoning,
  every message it sent that round, and its orders, with illegal ones struck out.
- **Standings** and a **model report** — calls, tokens, latency and errors per power.

Runs made before this existed still work — `just viewer <dir>` recovers the model
per power from the metadata recorded on each call. Only the personas and settings
are missing, since those runs predate `config.json`; the page says so where it
would otherwise be guessing.

Pass `--no-viewer` to `diplomacy-ai run` to skip generating it, or `--map <name>`
to `diplomacy-ai viewer` for a non-standard board.

### Follow a game as it plays

The viewer is a snapshot, but a run writes its phases to disk as it finishes
them, so a snapshot rebuilt on a timer is a live one. From a second terminal:

```bash
just follow                          # open the newest run, then rebuild every 10s
just follow 30                       # …or on a slower timer
diplomacy-ai viewer <run_dir> --watch 10
```

`--watch` rebuilds only when the run writes something new, and tells the page to
reload itself on the same interval, so an open tab follows along. The reload
keeps the phase and power you were looking at (they live in the URL, so a
position is also linkable), your scroll offset and your theme — and if you were
sitting on the newest phase, it moves you onto whatever has been played since.
Ctrl-C to stop.

It is still a reload, so the page does blink each time. If that grates while
reading, stop the watcher and step through at your own pace; the run keeps
writing either way.

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
RUN_SMOKE=1 just test-smoke            # opt-in live phase (needs NGROK_API_KEY, costs money)
just test-one tests/test_agent.py      # a single file
```

The fast suite needs no network. The smoke test is skipped unless both
`RUN_SMOKE=1` and `NGROK_API_KEY` are set.

## More

Run `just` to list all recipes. See `AGENTS.md` for contributor notes and
`docs/superpowers/` for the original spec and implementation plan.
