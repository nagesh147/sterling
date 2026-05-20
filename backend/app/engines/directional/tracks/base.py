"""
Sterling v4 — Track abstraction.

A Track is a strategy specialisation that consumes the unified signal
primitives (`signal_features.*_state_at`) and emits a `TrackSignal`.

Two tracks coexist after v4:
  - `trend_following`: the legacy compute_signal logic, wrapped so it speaks
                       the Track interface. Used for ETH 30m + intraday paths.
  - `mean_reversion`:  fades extremes in trending regimes. Used for BTC
                       short-TF where the data shows BULL_TREND longs win
                       only 32% but BEAR_TREND shorts win 62-67%, so the
                       counter-trend trade is the actual edge.

The orchestrator dispatches to one track per (asset, profile) via
`track_selector.select_tracks`. The signature is intentionally narrow so a
track only sees what it needs and tracks remain easily testable in isolation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, SignalResult


@dataclass(frozen=True)
class TrackSignal:
    """
    Output of a Track. Shape mirrors the legacy SignalResult on the fields the
    setup_engine + backtest entry gate consume, plus track metadata so
    downstream code can route on which strategy fired.

    `trend_dir` is the TRADE direction (+1 long, -1 short, 0 no trade) — for
    a counter-trend mean-reversion track this is OPPOSITE to the macro regime
    direction. The legacy MTF agreement filter in setup_engine must be
    track-aware so MR signals don't get auto-filtered.

    Score is on the same 0..20 scale as legacy signal_score so the cost-aware
    entry gate in `_replay_profile` works without modification.
    """
    track:        str                            # "trend_following" | "mean_reversion" | ...
    trend_dir:    int                            # 1 / -1 / 0 — desired trade direction
    score:        float                          # 0..20
    strength:     str                            # "STRONG" | "SIGNAL" | "NONE"
    reason:       str                            # human-readable
    signal:       SignalResult                   # raw SignalResult for back-compat
    features:     Dict[str, Any] = field(default_factory=dict)


NEUTRAL_TRACK_SIGNAL = TrackSignal(
    track="none", trend_dir=0, score=0.0, strength="NONE",
    reason="warmup_or_no_signal",
    signal=SignalResult(
        trend=0, all_green=False, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
        close_1h=0.0, score_long=0.0, score_short=0.0,
    ),
)


class Track(ABC):
    """ABC for strategy tracks. Subclasses implement compute()."""

    name: str = "base"

    @abstractmethod
    def compute(
        self,
        candles_signal: List[Candle],
        regime: RegimeResult,
        *,
        candles_regime: Optional[List[Candle]] = None,
        st_threshold: int = 3,
    ) -> TrackSignal:
        """Compute a TrackSignal at the latest bar of candles_signal."""
        raise NotImplementedError
