"""
Sterling v4 — VCP Track.

Implements the Track interface for the Hybrid VCP-Momentum Scalper strategy.
Consumes signal+regime candles from the orchestrator and emits a TrackSignal
with the direction, score, and reason.

This lets VCP participate in the same track-ranking pipeline as
trend_following and mean_reversion — same risk budgeting, same orchestrator
dispatch, same order-routing pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, SignalResult

from app.engines.hybrid_vcp.profiles import PROFILES, VCPProfile
from app.engines.hybrid_vcp.indicators import compute_bundle, VCPConfig, MomentumConfig
from app.engines.hybrid_vcp.microstructure import (
    obi_proxy, cvd_proxy_bar, detect_divergence,
)
from app.engines.hybrid_vcp.signals import (
    detect_mode, signal_compression, signal_breakout, Direction,
)
from app.engines.hybrid_vcp.entries import EntryConfig, evaluate_gate

from .base import Track, TrackSignal, NEUTRAL_TRACK_SIGNAL


@dataclass(frozen=True)
class VCPTrackConfig:
    """VCP track parameters — driven by the profile."""
    profile_key: str = "btc_scalping_15m"
    vol_filter_pct: float = 35.0
    flow_threshold: float = 0.35
    max_ibs_long: float = 0.35
    min_ibs_short: float = 0.65
    max_rsi_long: float = 40.0
    min_rsi_short: float = 60.0


class VCPTrack(Track):
    """
    VCP-Momentum Scalper as a Track.

    Evaluated per (asset, profile) by the orchestrator via `select_tracks`.
    The orchestrator calls `compute` on each selected track and keeps the
    highest-scoring TrackSignal (subject to track budget rules).

    The track delegates to the same `evaluate_gate` used by the backtest engine,
    ensuring bit-exact signal agreement between backtest and live evaluation.
    """

    name = "vcp"

    def __init__(self, config: Optional[VCPTrackConfig] = None):
        self._cfg = config or VCPTrackConfig()
        profile = PROFILES.get(self._cfg.profile_key)
        if profile:
            self._profile = profile
            self._entry_cfg = EntryConfig(
                vol_filter_pct=profile.vol_filter_pct,
                flow_threshold=profile.flow_threshold,
                max_ibs_long=profile.max_ibs_long,
                min_ibs_short=profile.min_ibs_short,
                max_rsi_long=profile.max_rsi_long,
                min_rsi_short=profile.min_rsi_short,
            )
        else:
            self._profile = PROFILES["btc_scalping_15m"]
            self._entry_cfg = EntryConfig()

    @property
    def profile_key(self) -> str:
        return self._cfg.profile_key

    def compute(
        self,
        candles_signal: List[Candle],
        regime: RegimeResult,
        *,
        candles_regime: Optional[List[Candle]] = None,
        st_threshold: int = 3,
    ) -> TrackSignal:
        """
        Evaluate VCP entry gate on the latest signal bar.

        Parameters
        ----------
        candles_signal : List[Candle]
            Signal-timeframe candles (e.g. 15m or 30m). Must have at least
            30 bars for EMA warmup. The last candle is the bar being evaluated.
        regime : RegimeResult
            Pre-computed macro regime (from regime_engine). Used as a filter —
            VCP entries are only taken in non-chop regimes (score > threshold).
        candles_regime : Optional[List[Candle]]
            Regime candles (e.g. 1H or 2H) — passed for completeness but VCP
            computes its own regime internally via `detect_mode`. Currently unused
            but reserved for future confluence with the orchestrator's regime.
        st_threshold : int
            SuperTrend threshold passed to satisfy the base Track signature.
            Not used by VCP (its own ATR-based thresholds are in the profile).

        Returns
        -------
        TrackSignal
            VCP signal or NEUTRAL_TRACK_SIGNAL if no entry qualifies.
        """
        n = len(candles_signal)
        if n < 30:
            return NEUTRAL_TRACK_SIGNAL

        # Chop filter — skip VCP in sideways / low-volume regimes
        regime_score = getattr(regime, "score", None) or 0.0
        if regime_score < 30.0:
            return NEUTRAL_TRACK_SIGNAL

        opn = _arr([c.open for c in candles_signal])
        hig = _arr([c.high for c in candles_signal])
        low = _arr([c.low  for c in candles_signal])
        cls = _arr([c.close for c in candles_signal])
        vol = _arr([c.volume for c in candles_signal])

        idx = n - 1
        bundle = compute_bundle(opn, hig, low, cls, vol)

        mode = detect_mode(cls, hig, low, bundle.atr, VCPConfig())
        comp = signal_compression(bundle.ibs, bundle.rsi, VCPConfig())
        brk  = signal_breakout(cls, hig, low, bundle.rsi, bundle.ema8, bundle.ema21,
                              bundle.pivot_high, bundle.pivot_low,
                              vol, bundle.vol_sma20, MomentumConfig())

        obi_val = float(obi_proxy(hig, low, cls, vol, bundle.vol_sma20)[idx])
        cvd_val = float(cvd_proxy_bar(opn, hig, low, cls, vol)[idx])

        gate = evaluate_gate(idx, cls, hig, low, opn, vol, bundle, config=self._entry_cfg)

        if not gate.triggered or gate.direction == Direction.NONE:
            return NEUTRAL_TRACK_SIGNAL

        # Map VCP direction to trend_dir
        trend_dir = +1 if gate.direction == Direction.LONG else -1

        # Score: use gate's entry_score (already combines flow, IBS, RSI)
        score = min(20.0, max(0.0, float(gate.entry_score)))

        strength = (
            "STRONG" if score >= 14.0
            else "SIGNAL" if score >= 6.0
            else "NONE"
        )

        # Divergence confirmation
        div = detect_divergence(cls, bundle.rsi)
        div_bonus = 2.0 if div else 0.0

        obi_val  = float(obi_proxy(hig, low, cls, vol, bundle.vol_sma20)[idx])
        cvd_val  = float(cvd_proxy_bar(opn, hig, low, cls, vol)[idx])
        rsi_val  = float(bundle.rsi[idx]) if n > 0 else 50.0

        # score_long/short for back-compat SignalResult
        long_score  = float(comp.long_score)  if comp and hasattr(comp, 'long_score')  else 0.0
        short_score = float(comp.short_score) if comp and hasattr(comp, 'short_score') else 0.0

        reason = (
            f"VCP {'LONG' if trend_dir == +1 else 'SHORT'} | "
            f"ibs={gate.ibs:.2f} rsi={rsi_val:.1f} "
            f"flow={gate.entry_score:.3f} div={'Y' if div else 'N'} | "
            f"mode={getattr(mode, 'value', '?')}"
        )

        fake_signal = SignalResult(
            trend=trend_dir,
            all_green=(trend_dir == +1),
            all_red=(trend_dir == -1),
            green_arrow=(trend_dir == +1),
            red_arrow=(trend_dir == -1),
            st_trends=[0, 0, 0],
            st_values=[0.0, 0.0, 0.0],
            close_1h=cls[idx] if n > 0 else 0.0,
            score_long=long_score,
            score_short=short_score,
        )

        return TrackSignal(
            track="vcp",
            trend_dir=trend_dir,
            score=round(score + div_bonus, 2),
            strength=strength,
            reason=reason,
            signal=fake_signal,
            features={
                "profile": self._cfg.profile_key,
                "ibs": round(gate.ibs, 4),
                "rsi": round(rsi_val, 2),
                "flow": round(gate.entry_score, 4),
                "obi": round(obi_val, 4),
                "divergence": div,
                "vcp_mode": getattr(mode, "value", "unknown"),
            },
        )


def _arr(values: list) -> "np.ndarray":
    import numpy as np
    return np.array(values, dtype=np.float64)