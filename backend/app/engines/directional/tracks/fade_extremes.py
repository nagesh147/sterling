"""
Sterling v4 — Fade-extremes mean-reversion track.

Designed for BTC sub-1H profiles where the historical regime breakdown shows:

  Regime       Long-signal WR    Short-signal WR
  BULL_TREND   32% (loses)       (filtered today)
  BEAR_TREND   (filtered today)  62-67% (wins)
  RANGING/IDLE ~50% (chops)      ~50% (chops)

The 32% long-WR in BULL_TREND is NOT random — it's a systematic loss on the
trend-following side. The matching profitable side is to FADE the rally
(short in BULL_TREND on extreme overbought + climax). The legacy MTF filter
in setup_engine blocks this directly; this track exists to bypass that
filter for the (asset, profile) combos where data shows the counter-trend
edge dominates.

Entry rules (counter-trend, asymmetric long/short):

  Short entry (the bread-and-butter on BTC):
    HTF regime  ∈ {BULL_TREND, BULLISH, BULL_TRENDING, BULL_RANGING}
    AND signal-TF RSI(14)         > rsi_extreme_high
    AND signal-TF close            > upper_bollinger
    AND signal-TF volume_climax   (vol > vol_climax_pct of last 100 bars)
    AND CVD-10 sign                negative (selling pressure absorbing the rip)

  Long entry (rare on BTC, exists for symmetry):
    HTF regime  ∈ {BEAR_TREND, BEARISH, BEAR_TRENDING, BEAR_RANGING}
    AND signal-TF RSI(14)         < rsi_extreme_low
    AND signal-TF close            < lower_bollinger
    AND signal-TF volume_climax
    AND CVD-10 sign                positive

Scoring (0..20 scale, same as legacy):
  +6  base regime alignment for fading the trend
  +4  RSI extreme magnitude (linear from threshold to threshold±10)
  +4  Bollinger distance: (price - band) / band_width
  +3  volume climax fired
  +3  CVD direction matches expected absorption

If `short_bias_boost > 0` the short side gets a flat boost (default 2 points)
because BTC's historical short-side edge is roughly 30% stronger.

Exits (handled in `_replay_profile` via the v4 v4_*_mult fields):
  Tight stop / quick TP / short hold_bars — handled by the BTC override
  TFProfile in `PROFILES_BY_ASSET["BTC"]`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, SignalResult

from app.engines.directional.tracks.base import Track, TrackSignal, NEUTRAL_TRACK_SIGNAL
from app.engines.indicators.rsi import rsi as compute_rsi
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.directional.signal_features import cvd_state_at, rsi_extreme_at
from app.engines.directional.signal_weights import DEFAULT_THRESHOLDS, SignalThresholds


_BULL_REGIMES = {"BULL_TREND", "BULLISH", "BULL_TRENDING", "BULL_RANGING", "BULL_WEAK"}
_BEAR_REGIMES = {"BEAR_TREND", "BEARISH", "BEAR_TRENDING", "BEAR_RANGING", "BEAR_WEAK"}


@dataclass(frozen=True)
class FadeExtremesConfig:
    """Tunable knobs. Search driver (`scripts/btc_mr_search.py`) sweeps these.

    Defaults are starting points; the search confirms or supersedes them via
    walk-forward + deflated_sharpe + bootstrap + permutation gates.
    """
    rsi_extreme_high:     float = 75.0
    rsi_extreme_low:      float = 25.0
    rsi_extreme_pct:      float = 0.10   # top/bottom 10% percentile for adaptive gate
    rsi_extreme_lookback: int   = 100    # trailing window for RSI percentile
    bb_period:            int   = 20
    bb_std:               float = 2.0
    vol_climax_window:    int   = 100
    vol_climax_pct:       float = 0.95   # top 5% volume bar
    cvd_window:           int   = 10
    cvd_min_ratio:        float = 0.3    # min |cvd|/sum(|delta|) for confirmation
    short_bias_boost:     float = 2.0    # extra score on the short side (BTC asymmetry)
    score_w_regime:       float = 6.0
    score_w_rsi:          float = 4.0
    score_w_bb:           float = 4.0
    score_w_vol:          float = 3.0
    score_w_cvd:          float = 3.0
    min_warmup_bars:      int   = 30
    max_consecutive_fade: int   = 5     # avoid re-entering same extreme bar-after-bar


def _rsi_extremity_score(rsi: float, threshold: float, direction: int,
                         cfg: FadeExtremesConfig) -> float:
    """Linear 0..1 score for how far past the extreme threshold the RSI is.
    Saturates at threshold ± 10 (so RSI=85 with thresh=75 → 1.0; RSI=75 → 0.0)."""
    if direction == 1:  # long entry — need oversold
        gap = max(0.0, threshold - rsi)
    else:                # short entry — need overbought
        gap = max(0.0, rsi - threshold)
    return min(1.0, gap / 10.0)


def _bb_extremity_score(close: float, lo: float, hi: float, direction: int) -> float:
    """0..1 score for how far the close is beyond the relevant Bollinger band."""
    width = hi - lo
    if width <= 0:
        return 0.0
    if direction == 1:  # long entry — need close BELOW lower band
        if close >= lo:
            return 0.0
        return min(1.0, (lo - close) / (width * 0.5))
    else:                # short entry — need close ABOVE upper band
        if close <= hi:
            return 0.0
        return min(1.0, (close - hi) / (width * 0.5))


def _cvd_confirmation_score(cvd_sum: float, cvd_abs_sum: float,
                            direction: int, cfg: FadeExtremesConfig) -> float:
    """0..1 score for CVD absorbing the move in the right direction.

    For a SHORT entry, we want CVD-10 negative (sellers absorbing the rally).
    For a LONG entry, we want CVD-10 positive (buyers absorbing the dip).
    Returns 0 when CVD ratio is below the configured floor or sign is wrong.
    """
    if cvd_abs_sum <= 0:
        return 0.0
    ratio = abs(cvd_sum) / cvd_abs_sum
    if ratio < cfg.cvd_min_ratio:
        return 0.0
    sign_ok = (direction == 1 and cvd_sum > 0) or (direction == -1 and cvd_sum < 0)
    if not sign_ok:
        return 0.0
    return min(1.0, ratio)  # saturates at 1.0 even though ratio can be ≤ 1


class FadeExtremesTrack(Track):
    """Counter-trend mean-reversion track. Designed for BTC short-TF."""

    name = "mean_reversion"   # public track name (the user-facing canonical track id)

    def __init__(self, config: Optional[FadeExtremesConfig] = None):
        self.config = config or FadeExtremesConfig()
        self._fade_count: int = 0  # consecutive bars with an active fade signal

    def compute(
        self,
        candles_signal: List[Candle],
        regime: RegimeResult,
        *,
        candles_regime: Optional[List[Candle]] = None,
        st_threshold: int = 3,
    ) -> TrackSignal:
        cfg = self.config
        n = len(candles_signal)
        if n < cfg.min_warmup_bars or regime is None:
            return NEUTRAL_TRACK_SIGNAL

        # Staleness guard: if the same fade direction has been active for
        # max_consecutive_fade bars, return neutral until the signal resets.
        maulim = cfg.max_consecutive_fade
        if maulim > 0 and self._fade_count >= maulim:
            return self._emit_neutral(candles_signal, f"stale_fade count={self._fade_count}/{maulim}")

        # Determine candidate direction from HTF regime — counter-trend.
        macro = regime.macro_regime.value if regime.macro_regime else ""
        if macro in _BULL_REGIMES:
            entry_dir = -1   # fade the rally
        elif macro in _BEAR_REGIMES:
            entry_dir = 1    # fade the puke
        else:
            return self._emit_neutral(candles_signal, "not_trending")

        # Arrays.
        o = np.array([c.open  for c in candles_signal], dtype=np.float64)
        h = np.array([c.high  for c in candles_signal], dtype=np.float64)
        l = np.array([c.low   for c in candles_signal], dtype=np.float64)
        c = np.array([c.close for c in candles_signal], dtype=np.float64)
        v = np.array([c.volume for c in candles_signal], dtype=np.float64)

        # Indicators.
        rsi_arr = compute_rsi(c, 14)
        cur_rsi = float(rsi_arr[-1])
        bb_lo, _bb_mid, bb_hi = bollinger_bands(c, cfg.bb_period, cfg.bb_std)
        cur_close = float(c[-1])
        cur_bb_lo = float(bb_lo[-1])
        cur_bb_hi = float(bb_hi[-1])

        # Volume climax: percentile rank against rolling window.
        v_window = v[-cfg.vol_climax_window:]
        if v_window.size > 5:
            pct_rank = float(np.sum(v[-1] >= v_window) / v_window.size)
        else:
            pct_rank = 0.0
        vol_climax = pct_rank >= cfg.vol_climax_pct

        # CVD-window state.
        cvd_s = cvd_state_at(o, h, l, c, v, entry_dir,
                              SignalThresholds(cvd_window=cfg.cvd_window))
        # Note: cvd_state_at returns divergent=True when CVD-sign is opposite
        # to trend. For a fade-extremes entry we WANT CVD to align with the
        # fade direction (i.e. absorbing the move). So we read the raw sum.

        # ── RSI extreme gate (adaptive percentile + fixed floor) ─────────
        # Primary: percentile-based (e.g. top 10% of last 100 bars).
        # Fallback: fixed thresholds when the window is too small.
        if entry_dir == -1:
            rsi_threshold = cfg.rsi_extreme_high
            adaptive, _ = rsi_extreme_at(
                rsi_arr, cur_rsi, -1,
                lookback=cfg.rsi_extreme_lookback,
                percentile=cfg.rsi_extreme_pct,
            )
            rsi_extreme = adaptive or cur_rsi > rsi_threshold
        else:
            rsi_threshold = cfg.rsi_extreme_low
            adaptive, _ = rsi_extreme_at(
                rsi_arr, cur_rsi, 1,
                lookback=cfg.rsi_extreme_lookback,
                percentile=cfg.rsi_extreme_pct,
            )
            rsi_extreme = adaptive or cur_rsi < rsi_threshold

        if not rsi_extreme:
            return self._emit_neutral(candles_signal, f"rsi_not_extreme rsi={cur_rsi:.1f}")

        # ── BB breach gate ────────────────────────────────────────────────
        bb_score = _bb_extremity_score(cur_close, cur_bb_lo, cur_bb_hi, entry_dir)
        if bb_score <= 0:
            return self._emit_neutral(
                candles_signal,
                f"bb_no_breach close={cur_close:.2f} bb_lo={cur_bb_lo:.2f} bb_hi={cur_bb_hi:.2f}",
            )

        # ── Score assembly ────────────────────────────────────────────────
        rsi_score = _rsi_extremity_score(cur_rsi, rsi_threshold, entry_dir, cfg)
        vol_score = 1.0 if vol_climax else 0.0
        cvd_score = _cvd_confirmation_score(cvd_s.cvd_sum, cvd_s.cvd_abs_sum,
                                            entry_dir, cfg)
        earned = (
            cfg.score_w_regime * 1.0          # we already passed regime gate
            + cfg.score_w_rsi    * rsi_score
            + cfg.score_w_bb     * bb_score
            + cfg.score_w_vol    * vol_score
            + cfg.score_w_cvd    * cvd_score
        )
        total = (cfg.score_w_regime + cfg.score_w_rsi + cfg.score_w_bb
                 + cfg.score_w_vol + cfg.score_w_cvd)
        pct = earned / total if total > 0 else 0.0
        score = round(pct * 20.0, 2)

        # BTC asymmetry: short side gets a flat boost.
        if entry_dir == -1 and cfg.short_bias_boost > 0:
            score = min(20.0, score + cfg.short_bias_boost)

        if pct >= 0.75:
            strength = "STRONG"
        elif pct >= 0.35:
            strength = "SIGNAL"
        else:
            strength = "NONE"

        # Build a SignalResult shim so existing entry-gate code reading the
        # SignalResult interface still works.
        # Note: trend on SignalResult points to the MACRO direction; for MR
        # we set the SignalResult.trend to entry_dir so cost-uplift logic
        # still works downstream.
        sig = SignalResult(
            trend=entry_dir,
            all_green=False,
            all_red=False,
            green_arrow=False,
            red_arrow=False,
            st_trends=[0, 0, 0],
            st_values=[0.0, 0.0, 0.0],
            close_1h=cur_close,
            score_long=(score if entry_dir == 1 else 0.0),
            score_short=(score if entry_dir == -1 else 0.0),
            signal_strength=strength,
            signal_score=score,
            rsi=round(cur_rsi, 2),
            squeezed=False,
            vol_confirm=vol_climax,
            bars_since_flip=0,
            cvd_proxy=round(cvd_s.cvd_sum, 4),
            ha_real_divergence_pct=0.0,
        )

        reason = (
            f"fade_extremes dir={'short' if entry_dir==-1 else 'long'} "
            f"rsi={cur_rsi:.1f} bb_score={bb_score:.2f} vol_climax={vol_climax} "
            f"cvd_score={cvd_score:.2f} score={score:.1f} regime={macro}"
        )
        # Increment staleness counter — reset when signal flips or goes neutral.
        self._fade_count += 1

        return TrackSignal(
            track=self.name,
            trend_dir=entry_dir,
            score=score,
            strength=strength,
            reason=reason,
            signal=sig,
            features={
                "rsi": cur_rsi,
                "rsi_extreme": rsi_extreme,
                "bb_score": bb_score,
                "rsi_score": rsi_score,
                "vol_climax_pct_rank": pct_rank,
                "cvd_score": cvd_score,
                "cvd_sum": cvd_s.cvd_sum,
                "macro_regime": macro,
                "fade_count": self._fade_count,
            },
        )

    def _emit_neutral(self, candles_signal: List[Candle], reason: str) -> TrackSignal:
        """Build a neutral TrackSignal that still carries the latest close for UI."""
        self._fade_count = 0  # reset staleness counter on any neutral bar
        close = float(candles_signal[-1].close) if candles_signal else 0.0
        sig = SignalResult(
            trend=0, all_green=False, all_red=False,
            green_arrow=False, red_arrow=False,
            st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
            close_1h=close, score_long=0.0, score_short=0.0,
        )
        return TrackSignal(
            track=self.name, trend_dir=0, score=0.0, strength="NONE",
            reason=reason, signal=sig, features={},
        )
