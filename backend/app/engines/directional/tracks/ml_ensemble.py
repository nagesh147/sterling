"""
Sterling v4 Phase 3 — ML ensemble track.

Wraps a per-(asset, profile_key) xgboost model trained via
`engines/ml/walk_forward_train.py` and persisted via
`services/model_store.py`. At compute time:

  1. Build the feature row for the latest bar via `ml.feature_library`.
  2. Run prediction → probability of profitable entry.
  3. Emit a TrackSignal with score = prob × 20 (so it lives on the same
     0..20 scale as the other tracks).

When no model exists for (asset, profile_key) the track returns a neutral
signal — the orchestrator's track-blending picks the next-best signal.

This track is intended to be BLENDED with mean_reversion (highest-score
wins, or weighted average), not to replace it outright. The blending logic
lives in `track_selector.select_tracks` / orchestrator dispatch.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, SignalResult

from app.engines.directional.tracks.base import (
    Track, TrackSignal, NEUTRAL_TRACK_SIGNAL,
)


class MLEnsembleTrack(Track):
    """Loads a per-(asset, profile) xgboost model and emits a TrackSignal.

    Args:
      asset:          underlying asset key, e.g. "BTC" / "ETH"
      profile_key:    TFProfile key, e.g. "scalping_30m"
      direction_hint: +1 for long-side model, -1 for short-side. The model
                      is trained on a specific direction so the loaded
                      booster knows what "profitable" means.
      min_prob:       minimum predicted probability to emit a non-neutral
                      signal. Defaults to 0.6 — calibrated to give roughly
                      the same trade count as the fade-extremes track.
    """

    name = "ml_ensemble"

    def __init__(self, asset: str, profile_key: str,
                 direction_hint: int, *, min_prob: float = 0.6):
        self.asset = asset.upper()
        self.profile_key = profile_key
        self.direction_hint = direction_hint
        self.min_prob = float(min_prob)
        self._loaded = False
        self._booster = None
        self._meta = None

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return self._booster is not None
        from app.services.model_store import load_model
        loaded = load_model(self.asset, self.profile_key)
        if loaded is None:
            self._booster = None
            self._meta = None
        else:
            self._booster, self._meta = loaded
        self._loaded = True
        return self._booster is not None

    def compute(
        self,
        candles_signal: List[Candle],
        regime: RegimeResult,
        *,
        candles_regime: Optional[List[Candle]] = None,
        st_threshold: int = 3,
    ) -> TrackSignal:
        if not self._ensure_loaded():
            return NEUTRAL_TRACK_SIGNAL

        from app.engines.ml.feature_library import build_feature_matrix, FEATURE_NAMES
        import xgboost as xgb

        # Pick a sensible regime_bar_ms — use 4H as a safe default since we
        # don't know the exact profile here. The feature library broadcasts
        # regime values via searchsorted, so a slight TF mismatch only loses
        # alignment in the warmup window.
        regime_bar_ms = 60 * 60_000 * 4
        X, ts = build_feature_matrix(
            candles_signal, candles_regime or [], regime_bar_ms=regime_bar_ms,
        )
        if X.shape[0] == 0:
            return NEUTRAL_TRACK_SIGNAL

        # Predict on the latest bar only — cheap, no DMatrix caching needed.
        last = X[-1:].astype(np.float32)
        d = xgb.DMatrix(last, feature_names=list(FEATURE_NAMES))
        try:
            prob = float(self._booster.predict(d)[0])
        except Exception:
            return NEUTRAL_TRACK_SIGNAL

        cur_close = float(candles_signal[-1].close)
        score = round(prob * 20.0, 2)

        if prob < self.min_prob:
            sig = SignalResult(
                trend=0, all_green=False, all_red=False,
                green_arrow=False, red_arrow=False,
                st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
                close_1h=cur_close, score_long=0.0, score_short=0.0,
                signal_score=score, signal_strength="NONE",
            )
            return TrackSignal(
                track=self.name, trend_dir=0, score=score, strength="NONE",
                reason=f"ml prob={prob:.3f} below min_prob={self.min_prob}",
                signal=sig, features={"prob": prob},
            )

        d_hint = self.direction_hint
        sig = SignalResult(
            trend=d_hint,
            all_green=False, all_red=False,
            green_arrow=False, red_arrow=False,
            st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
            close_1h=cur_close,
            score_long=(score if d_hint == 1 else 0.0),
            score_short=(score if d_hint == -1 else 0.0),
            signal_score=score,
            signal_strength=("STRONG" if prob >= 0.8 else "SIGNAL"),
        )
        return TrackSignal(
            track=self.name, trend_dir=d_hint, score=score,
            strength=sig.signal_strength,
            reason=f"ml prob={prob:.3f} → score={score:.1f}",
            signal=sig,
            features={"prob": prob, "model_oos_sharpe":
                      (self._meta.oos_sharpe if self._meta else None)},
        )
