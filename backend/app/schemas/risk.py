from pydantic import BaseModel, field_validator
from typing import Optional


class RiskParams(BaseModel):
    capital: float = 100_000.0
    max_position_pct: float = 0.05
    max_contracts: int = 10
    partial_profit_r1: float = 1.5
    partial_profit_r2: float = 2.0
    time_stop_dte: int = 3
    financial_stop_pct: float = 0.50


class ExitSignal(BaseModel):
    should_exit: bool
    reason: str
    exit_type: Optional[str] = None  # "thesis","time","financial","partial","expiry"
    partial: bool = False
    partial_ratio: float = 0.0


class ScoringWeights(BaseModel):
    regime: float = 0.20
    signal: float = 0.20
    execution: float = 0.15
    dte: float = 0.15
    health: float = 0.20
    risk_reward: float = 0.10

    @field_validator("regime", "signal", "execution", "dte", "health", "risk_reward", mode="before")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return round(max(0.0, min(1.0, float(v))), 4)
