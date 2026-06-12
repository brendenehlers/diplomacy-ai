# Diplomacy AI — Design Spec

**Date:** 2026-06-11
**Status:** Approved (brainstorm), pending implementation plan

## Goal

A self-contained Python application that runs a full game of Diplomacy between
7 LLM-controlled powers. The user watches the game unfold and reviews what each
model said, decided, and why. We build **only the AI layer**; the
[`diplomacy`](https://github.com/diplomacy/diplomacy) package (v1.1.2, installed
in `.venv`) is the game engine and is treated as a black box that owns all rules
and adjudication.

## Requirements

1. **Backend-agnostic LLM provider**, Gemini first. Swapping models must touch
   one place. → LiteLLM.
2. **Reviewable play.** The user can look through the board, press, and turns to
   understand what the LLMs are doing — including each power's private reasoning.
3. **Fixed turn structure.** Each movement phase gives powers a fixed number of
   negotiation rounds before orders are due (deterministic, not wall-clock).

## Key decisions

| Decision | Choice |
|---|---|
| Turn timing | Fixed **N negotiation rounds** per movement phase (default 3) |
| Primary viewer | Official `diplomacy` React web UI, fed the standard saved-game JSON |
| Reasoning capture | Yes — separate structured per-phase transcript on disk |
| Provider abstraction | LiteLLM (unified async interface, swap via model string) |
| Per-power model | Configurable per power (model + persona); defaults to one shared model |
| Press style | Full press: private peer-to-peer **and** global broadcasts |
| Orchestration | Synchronous round-based loop; powers queried in parallel via asyncio |

## Architecture

Single Python package `diplomacy_ai/`. Two hard seams:
`orchestrator` is the only module importing the engine's game logic;
`provider` is the only module importing LiteLLM. Swapping either backend touches
exactly one file.

| Module | Responsibility | Depends on |
|---|---|---|
| `config.py` | Load/validate game config (per-power model + persona, N rounds, max year, temperature, timeout). Pydantic. | — |
| `provider.py` | Async wrapper over LiteLLM: `complete(model, system, messages, schema) -> parsed JSON`. Retries/timeouts. Only LLM-aware module. | LiteLLM |
| `agent.py` | One `PowerAgent` per power. Builds prompts, calls provider, exposes `negotiate()` and `decide_orders()`. Holds persona + model. | provider, prompts |
| `prompts.py` | Pure functions: game state → prompt text (rules primer, board, own units, legal orders, message inbox). No I/O. | — |
| `orchestrator.py` | Owns the `Game`. Runs the phase loop. Stops on solo win or max year. | diplomacy, agent, recorder |
| `recorder.py` | Persists after every phase: saved-game JSON + per-power transcript + event log. | diplomacy export |
| `cli.py` | Entry point: `diplomacy-ai run --config game.toml`. | orchestrator, config |

## Turn loop (orchestrator)

For each phase the engine yields:

1. **Branch on phase type.** Movement (`*M`): full negotiation. Retreat (`*R`)
   and adjustment/build (`*A`): order-only, no press (configurable later).
2. **Negotiation — N rounds** (movement only). Each round:
   - Build each power's prompt: board state, own units/centers, legal-order list,
     messages received in the previous round.
   - Query all 7 powers in parallel (`asyncio.gather`). Each returns outgoing
     messages (each tagged `to`: a power or `GLOBAL`) plus private `reasoning`.
   - Route: privates → recipient's next-round inbox; globals → everyone. Record
     all. Push press into the engine via `add_message` so it lands in the saved
     game.
3. **Orders.** After round N (immediately for R/A), query all powers in parallel.
   Prompt includes the legal-order list for their locations.
4. **Validate & process.** Check each order against `get_all_possible_orders()`.
   Invalid → one repair re-prompt naming the rejected orders. Still invalid →
   drop the order (engine treats the unit as a hold). `set_orders` all, then
   `game.process()`.
5. **Record & loop.** `recorder` saves. Repeat until a power reaches 18 centers
   (engine flags solo win) or `max_year` is reached.

## LLM contract

Every call returns strict JSON via LiteLLM structured output:

- **Negotiate:** `{ "reasoning": str, "messages": [ { "to": "FRANCE"|"GLOBAL", "body": str } ] }`
- **Orders:** `{ "reasoning": str, "orders": [ "A PAR - BUR", ... ] }` — strings
  in the engine's order syntax, chosen from the supplied legal list.

Supplying the legal-order list in the prompt plus schema-validated responses
keeps hallucinated orders rare; the validate → repair → drop ladder guarantees
the engine never receives an illegal order.

## Config

`game.toml`, validated by Pydantic:

```toml
n_negotiation_rounds = 3
max_year = 1920
default_model = "gemini/gemini-2.5-pro"
temperature = 0.7
timeout = 60

[powers.FRANCE]
model = "gemini/gemini-2.5-pro"
persona = "Cautious, builds long-term alliances."
# any power omitted → default_model, neutral persona
```

API keys come from environment variables (e.g. `GEMINI_API_KEY`), never the
config file.

## Persistence

Under `runs/<timestamp>/`:

- `game.json` — rewritten each phase via `to_saved_game_format`; loadable in the
  official web UI for board + press playback.
- `transcript/<phase>.json` — per power: reasoning, messages sent/received, raw +
  repaired orders, model, token counts, cost, latency. The "why" record.
- `events.log` — human-readable running log.

Saving every phase bounds crash loss to one phase and allows mid-game inspection.

## Error handling

- Provider call fails (network/rate-limit) → LiteLLM retry with backoff; after
  retries, the power sends no messages this round / holds for orders. No deadlock
  on a single slow or failing model.
- Malformed JSON → treated as a failed call, same fallback.
- Every fallback is recorded in the transcript.

## Testing (TDD)

A fake provider makes tests free and deterministic.

- `provider`: schema parsing, retry/timeout, malformed-JSON handling (mock LiteLLM).
- `orchestrator`: full phase loop with a scripted fake agent — message routing
  (private vs global), validate → repair → drop ladder, termination on solo win /
  max year.
- `prompts`: snapshot tests for legal-order list and inbox rendering.
- One opt-in smoke test running a couple of real phases against Gemini (skipped
  unless an env flag + key are set).

## Out of scope (v1)

- Draw voting / negotiated draws (engine supports it; defer).
- Custom board renderer (reuse engine SVG + official UI).
- Resume-from-saved-game (save format supports it; defer).
- Network/multi-client play (engine's client/server framework unused).
