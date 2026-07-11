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
    win_rate: float = 0.52  # for Kelly sizing — used only when win_rate_known
    # TTACE Phase 3: callers must explicitly affirm the edge is calibrated.
    # Cold-start callers (calibration sample < MIN_TRADES_FOR_WIN_RATE) set
    # this to False, which causes size_trade to fail closed.
    win_rate_known: bool = True
    # Issue 12 — operator opt-in to size during cold start (paper mode only).
    # When set AND trading_mode == "paper" AND win_rate_known is False, the
    # sizer uses this value for Kelly with a hard 0.25× multiplier. In any
    # other context the field is ignored (fail-closed).
    cold_start_default_win_rate: Optional[float] = None
    # Issue 5 — operator opt-in to allow EARLY_SETUP_ACTIVE entries with a
    # 0.5× sizing haircut when signal_score lands in the 11–14 band.
    enable_early_entry: bool = False
    # Honored by callers that read `app.state.trading_mode` to decide whether
    # an opt-in flag like cold_start_default_win_rate is actually safe to use.
    trading_mode: Optional[str] = None
    # Unified hybrid trail weight from risk config (0-1 for ATR+ST blend)
    hybrid_st_weight: float = 0.5

    @field_validator("hybrid_st_weight", mode="before")
    @classmethod
    def _clamp_hybrid(cls, v: float) -> float:
        return round(max(0.0, min(1.0, float(v))), 2)


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
    dte: float = 0.10        # 10 pts max — matches scoring code (20+20+15+20+10+15=100)
    health: float = 0.20
    risk_reward: float = 0.15  # 15 pts max — matches scoring code

    @field_validator("regime", "signal", "execution", "dte", "health", "risk_reward", mode="before")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return round(max(0.0, min(1.0, float(v))), 4)
