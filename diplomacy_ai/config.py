"""Game configuration: Pydantic models + tomllib loader."""
from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class PowerConfig(BaseModel):
    model: str | None = None
    persona: str = ""


class GameConfig(BaseModel):
    n_negotiation_rounds: int = 3
    max_year: int = 1920
    default_model: str = "openai:openai/gpt-4o-mini"
    temperature: float = 0.7
    timeout: int = 60
    powers: dict[str, PowerConfig] = Field(default_factory=dict)

    def model_for(self, power: str) -> str:
        pc = self.powers.get(power)
        return pc.model if pc and pc.model else self.default_model

    def persona_for(self, power: str) -> str:
        pc = self.powers.get(power)
        return pc.persona if pc else ""


def load_config(path: str | Path) -> GameConfig:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    powers = data.pop("powers", {})
    data["powers"] = {name.upper(): PowerConfig(**pc) for name, pc in powers.items()}
    return GameConfig(**data)
