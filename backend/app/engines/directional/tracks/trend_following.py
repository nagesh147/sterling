"""
Sterling v4 — Trend-following track.

Thin wrapper around the legacy `signal_engine.compute_signal` so it speaks
the Track interface. Zero behaviour change: ETH paths route here and produce
the byte-identical SignalResult / signal_score / signal_strength they would
without the track layer. The wrapper exists purely so `mean_reversion` can
share an orchestration surface.
"""
from __future__ import annotations

from typing import List, Optional

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult

from app.engines.directional.tracks.base import Track, TrackSignal, NEUTRAL_TRACK_SIGNAL
from app.engines.directional.signal_engine import compute_signal


class TrendFollowingTrack(Track):
    """Trend-following confluence strategy. Legacy v4 default."""

    name = "trend_following"

    def compute(
        self,
        candles_signal: List[Candle],
        regime: RegimeResult,
        *,
        candles_regime: Optional[List[Candle]] = None,
        st_threshold: int = 3,
    ) -> TrackSignal:
        regime_label = regime.macro_regime.value if regime else ""
        sig = compute_signal(
            candles_signal,
            st_threshold=st_threshold,
            regime_label=regime_label,
        )
        return TrackSignal(
            track=self.name,
            trend_dir=sig.trend,
            score=sig.signal_score,
            strength=sig.signal_strength,
            reason=f"trend_following score={sig.signal_score:.1f} strength={sig.signal_strength}",
            signal=sig,
            features={
                "rsi": sig.rsi,
                "squeezed": sig.squeezed,
                "vol_confirm": sig.vol_confirm,
                "bars_since_flip": sig.bars_since_flip,
                "cvd_proxy": sig.cvd_proxy,
                "ha_real_divergence_pct": sig.ha_real_divergence_pct,
            },
        )
