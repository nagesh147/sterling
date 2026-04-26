from pydantic import BaseModel
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
