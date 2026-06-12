# Diplomacy AI task runner. Run `just` to list recipes.
# All Python runs through the project venv at .venv.

# Load environment variables from .env (copy .env.example to .env first).
set dotenv-load := true

venv := ".venv/bin"

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

# Run the live smoke test against Gemini (needs GEMINI_API_KEY)
test-smoke:
    RUN_SMOKE=1 {{venv}}/pytest tests/test_smoke.py -v

# Run a full game with the sample config (needs GEMINI_API_KEY)
run config="game.toml":
    {{venv}}/diplomacy-ai run --config {{config}}

# Run a game writing output to a custom directory
run-out config="game.toml" out="runs":
    {{venv}}/diplomacy-ai run --config {{config}} --out {{out}}

# Show CLI help
help:
    {{venv}}/diplomacy-ai run --help
