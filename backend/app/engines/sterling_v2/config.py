from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SimConfig:
    """Backtest cost/exit model. All costs are fractions of notional."""
    sl_mult: float = 2.0          # stop = entry - sl_mult * ATR (long)
    tp_mult: float = 3.5          # target = entry + tp_mult * ATR (long)
    fee_round_trip: float = 0.001  # 0.10%
    slippage: float = 0.0005       # 5 bps per fill (entry + each exit)
    funding_per_bar: float = 0.0   # perp funding drag per bar held
    max_hold_bars: int = 200
    allow_short: bool = False


# Pre-registered acceptance gates (fixed BEFORE the test set is evaluated).
MAX_DD_CAP = 0.20         # hard guardrail: test-set max drawdown <= 20%
MIN_TEST_TRADES = 100
MAX_PBO = 0.5
MAX_P_LOSS = 0.35
MIN_OOS_SHARPE = 0.0
MIN_DSR = 0.0

# Train/validation/test chronological split (fractions of bars).
SPLIT = (0.60, 0.20, 0.20)

# Toggle/runtime defaults.
V2_ENABLED_DEFAULT = False
V2_PAPER_ONLY = True
V2_AUTO_EXECUTE = False
