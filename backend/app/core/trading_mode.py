from dataclasses import dataclass
from enum import Enum


class TrailMode(str, Enum):
    ATR = "atr"
    SUPERTREND = "supertrend"
    PERCENTAGE = "percentage"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class TradingModeConfig:
    name: str
    display: str
    macro_tf: str
    signal_tf: str
    execution_tf: str
    st_threshold: int
    macro_filter: str
    dte_min: int
    dte_preferred: tuple
    dte_max: int
    ivr_pct_naked_max: int
    stop_atr_mult: float
    trail_mode: TrailMode
    trail_atr_mult: float
    trail_pct: float
    rr_target: float
    partial_25_pct: float
    partial_50_pct: float
    # IST equity-market session timestamp ("15:25" = 3:25pm). Used by
    # Zerodha-shaped (NSE) adapters to force-close intraday positions
    # before market close. KEEP for those flows. Crypto options on Delta
    # India do not use this — use `force_close_minutes_before_expiry`
    # below for the DTE-based force-close that the derivatives selector
    # and background monitor consume.
    force_close_time: str | None
    max_hold_bars: int
    position_pct: float
    max_concurrent: int
    poll_interval_s: int
    # Force-close any open options position N minutes before its expiry.
    # The background monitor tiers this further by notional (positions
    # with notional > $1k use the full window, smaller ones use a tighter
    # 30-min default). Selector profiles may also override per-strategy.
    # 120 default matches Delta India weekly options settlement at
    # Friday 12:30 UTC — gives 2h cushion for settlement-period spread
    # widening before the cash-settle mark is locked.
    force_close_minutes_before_expiry: int = 120
    hybrid_st_weight: float = 0.5  # weight for ST in hybrid trail (0=ATR, 1=ST)


MODES: dict[str, TradingModeConfig] = {
    "scalping": TradingModeConfig(
        name="scalping", display="Scalping",
        macro_tf="15m", signal_tf="5m", execution_tf="1m",
        st_threshold=1, macro_filter="off",
        dte_min=0, dte_preferred=(0, 1), dte_max=3,
        ivr_pct_naked_max=85,
        stop_atr_mult=1.0, trail_mode=TrailMode.PERCENTAGE,
        trail_atr_mult=0.5, trail_pct=0.5,
        rr_target=1.0, partial_25_pct=0.05, partial_50_pct=0.10,
        force_close_time="15:25", max_hold_bars=15,
        position_pct=0.01, max_concurrent=3, poll_interval_s=5,
        hybrid_st_weight=0.5,
    ),
    "intraday": TradingModeConfig(
        name="intraday", display="Intraday",
        macro_tf="1H", signal_tf="15m", execution_tf="5m",
        st_threshold=2, macro_filter="adx_1h",
        dte_min=0, dte_preferred=(0, 3), dte_max=7,
        ivr_pct_naked_max=60,
        stop_atr_mult=1.5, trail_mode=TrailMode.SUPERTREND,
        trail_atr_mult=1.0, trail_pct=1.0,
        rr_target=1.5, partial_25_pct=0.08, partial_50_pct=0.15,
        force_close_time="15:20", max_hold_bars=48,
        position_pct=0.025, max_concurrent=4, poll_interval_s=30,
        hybrid_st_weight=0.5,
    ),
    "swing": TradingModeConfig(
        name="swing", display="Swing",
        macro_tf="4H", signal_tf="1H", execution_tf="15m",
        st_threshold=3, macro_filter="adx_4h",
        dte_min=7, dte_preferred=(10, 21), dte_max=30,
        ivr_pct_naked_max=40,
        stop_atr_mult=2.0, trail_mode=TrailMode.HYBRID,
        trail_atr_mult=2.0, trail_pct=2.5,
        rr_target=2.0, partial_25_pct=0.10, partial_50_pct=0.20,
        force_close_time=None, max_hold_bars=42,
        position_pct=0.04, max_concurrent=5, poll_interval_s=300,
        hybrid_st_weight=0.5,
    ),
    "positional": TradingModeConfig(
        name="positional", display="Positional",
        macro_tf="D", signal_tf="4H", execution_tf="1H",
        st_threshold=3, macro_filter="adx_4h",
        dte_min=21, dte_preferred=(30, 60), dte_max=90,
        ivr_pct_naked_max=30,
        stop_atr_mult=3.0, trail_mode=TrailMode.HYBRID,
        trail_atr_mult=3.0, trail_pct=5.0,
        rr_target=3.0, partial_25_pct=0.15, partial_50_pct=0.30,
        force_close_time=None, max_hold_bars=90,
        position_pct=0.07, max_concurrent=6, poll_interval_s=900,
        hybrid_st_weight=0.5,
    ),
}

MODES["all"] = TradingModeConfig(
    name="all", display="All Modes",
    macro_tf="1H", signal_tf="5m", execution_tf="1m",
    st_threshold=1, macro_filter="off",
    dte_min=0, dte_preferred=(0, 30), dte_max=90,
    ivr_pct_naked_max=85,
    stop_atr_mult=2.0, trail_mode=TrailMode.HYBRID,
    trail_atr_mult=2.0, trail_pct=2.5,
    rr_target=2.0, partial_25_pct=0.10, partial_50_pct=0.20,
    force_close_time=None, max_hold_bars=90,
    position_pct=0.04, max_concurrent=6, poll_interval_s=30,
    hybrid_st_weight=0.5,
)

DEFAULT_MODE = "swing"
