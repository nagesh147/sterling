"""Pydantic request/response shapes for the scalping strategies API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.engines.scalping.config import ScalpingConfig


class SupportResistanceLevel(BaseModel):
    underlying: str = ""
    price: float
    touches: int
    first_touch_ts: int
    last_touch_ts: int
    level_type: str = "support"  # "support" or "resistance"


class ScalpingSignal(BaseModel):
    underlying: str
    close: float
    strategy: str                  # "price_action" | "smc" | "ma_crossover"
    profile: str = ""              # e.g. "intraday", "scalping", "aggressive"
    direction: str                 # "long" | "short" | "none"

    # 4H context
    near_level: Optional[float] = None
    level_type: str = ""           # "support" | "resistance"

    # Strategy-specific detail
    pattern: str = ""              # e.g. "ascending_triangle", "bullish_imbalance", "sma_cross_above_ema"
    reason: str = ""

    # Trade plan
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    tp_source: str = ""
    risk_pct: Optional[float] = None
    leverage: Optional[float] = None
    size_units: Optional[float] = None
    notional_usd: Optional[float] = None

    # Readiness
    entry_ok: bool = False
    executable: bool = False
    timestamp_ms: int = 0
    error: Optional[str] = None


class ScalpingScanResponse(BaseModel):
    signals: List[ScalpingSignal]
    levels: List[SupportResistanceLevel]
    count: int
    armed_count: int
    timestamp_ms: int


class ScalpingConfigResponse(BaseModel):
    config: ScalpingConfig


class ScalpingUniverseResponse(BaseModel):
    symbols: List[str]


class ScalpingBacktestTrade(BaseModel):
    direction: str
    strategy: str
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    bars_held: int
    pnl_r: float           # NET R after costs (the honest per-trade outcome)
    gross_pnl_r: float = 0.0
    exit_reason: str
    regime: str = ""       # macro regime at entry: bull | bear | chop


class SampleQuality(BaseModel):
    """Adequacy of the trade sample. Under ~100 trades a backtest is unreliable;
    500+ is robust."""
    label: str             # robust | adequate | thin | unreliable | no_trades
    note: str
    min_reliable: int = 100
    adequate: bool = False


class RegimeStats(BaseModel):
    trade_count: int = 0
    win_rate: float = 0.0
    avg_r: float = 0.0


class RegimeCoverage(BaseModel):
    """Did the lookback span both a bull and a bear leg, and how did the edge
    perform in each regime?"""
    covers_bull_and_bear: bool = False
    bull_pct: float = 0.0
    bear_pct: float = 0.0
    chop_pct: float = 0.0
    by_regime: dict = Field(default_factory=dict)  # regime -> RegimeStats-shaped


class OOSSplit(BaseModel):
    """70/30 in-sample vs out-of-sample split — does the edge generalise or is
    it curve-fit to this window?"""
    n_is: int = 0
    n_oos: int = 0
    is_pf: Optional[float] = None
    is_exp: float = 0.0
    oos_pf: Optional[float] = None
    oos_exp: float = 0.0
    generalises: bool = False
    note: str = ""


class ScalpingBacktestResult(BaseModel):
    underlying: str
    lookback_days: int
    bars_evaluated: int
    config: ScalpingConfig
    trades: List[ScalpingBacktestTrade]
    total_trades: int
    win_rate: float
    total_return_pct: float          # net of costs (kept for UI back-compat)
    max_drawdown_pct: float
    timestamp_ms: int
    # ── honest-replay additions ──
    expectancy_r: float = 0.0        # mean NET R per trade
    profit_factor: Optional[float] = None
    avg_cost_r: float = 0.0          # avg fee+slippage+funding per trade, in R
    cost_modeled: bool = True
    equity_curve: List[float] = Field(default_factory=list)
    sample_quality: Optional[SampleQuality] = None
    regime_coverage: Optional[RegimeCoverage] = None
    oos: Optional[OOSSplit] = None


class ScalpingBacktestRequest(BaseModel):
    underlying: str = "BTC"
    lookback_days: int = Field(default=90, ge=14, le=365)
    strategies: Optional[List[str]] = None  # None = all enabled
    config: Optional[ScalpingConfig] = None


class ScalpingExecuteRequest(BaseModel):
    underlying: str
    strategy: str  # "price_action" | "smc" | "ma_crossover"
    confirm: bool = True
    auto: bool = False  # True when fired by the algo auto-exec loop (vs a manual click)


class ScalpingExecuteResponse(BaseModel):
    accepted: bool
    mode: str
    underlying: str
    strategy: str
    direction: str
    size_units: float
    notional_usd: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    tp_source: str = ""
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    status: str
    reason: str
    timestamp_ms: int
    telegram_alert_sent: bool = False