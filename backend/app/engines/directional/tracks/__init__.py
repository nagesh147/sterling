"""Sterling v4 — strategy tracks.

The `Track` abstraction lets multiple strategies coexist behind one
orchestrator. Each track consumes the shared signal primitives in
`signal_features` / `signal_weights` and emits a `TrackSignal`.

Built-in tracks (v4):
  * trend_following — wraps legacy compute_signal; default for ETH + intraday.
  * mean_reversion  — fade-extremes specialist (FadeExtremesTrack); BTC short-TF.
  * vcp             — Hybrid VCP-Momentum Scalper; BTC/ETH short-TF primary signal.
  * microstructure  — Phase 2; OHLCV-proxy microstructure scoring (blended).
  * ml_ensemble     — Phase 3; xgboost classifier wrapper.

Routing is config-driven via `track_selector.select_tracks(asset, profile)`.
Legacy `mean_reversion.py` is preserved as a research-only scaffold for the
older squeeze-based MR experiment; it is NOT wired into the v4 track router.
"""
from app.engines.directional.tracks.base import (
    Track, TrackSignal, NEUTRAL_TRACK_SIGNAL,
)
from app.engines.directional.tracks.trend_following import TrendFollowingTrack
from app.engines.directional.tracks.fade_extremes import (
    FadeExtremesTrack, FadeExtremesConfig,
)
from app.engines.directional.tracks.vcp_track import VCPTrack, VCPTrackConfig

__all__ = [
    "Track", "TrackSignal", "NEUTRAL_TRACK_SIGNAL",
    "TrendFollowingTrack", "FadeExtremesTrack", "FadeExtremesConfig",
    "VCPTrack", "VCPTrackConfig",
]
