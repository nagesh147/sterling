"""
Sterling v4 — Ensemble track scorer (TF + VCP + MR combined).

Unlike select_best_track which picks a single winner, compute_ensemble_signal
combines all three tracks into a single composite direction + score by:
  1. Running all three tracks in their native TF configuration
  2. Normalising each track's 0-20 score against its own rolling window
  3. Applying regime-aware weights (from win-rate registry)
  4. Computing a blended direction vector (sum of weighted trend_dir components)
  5. Normalising the composite direction to a 0-20 score
  6. Emitting a single SignalResult / TrackSignal for the orchestrator

Best outcome: the ensemble always fires when ≥1 track has a non-zero direction,
with the direction being the weighted blend of all three. STRONG signals require
≥2 tracks to agree, else demoted to SIGNAL.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.schemas.market import Candle
from app.engines.directional.tracks.base import TrackSignal


# ── Win-rate registry ────────────────────────────────────────────────────────
_WIN_REGISTRY: Dict[Tuple[str, str], Dict[str, float]] = {
    ("trend_following", "bull_trend"):    {"long_wr": 0.58, "short_wr": 0.41, "sharpe": 1.4},
    ("trend_following", "bear_trend"):    {"long_wr": 0.38, "short_wr": 0.63, "sharpe": 1.6},
    ("trend_following", "bull_ranging"):  {"long_wr": 0.52, "short_wr": 0.48, "sharpe": 0.9},
    ("trend_following", "bear_ranging"):  {"long_wr": 0.46, "short_wr": 0.54, "sharpe": 1.1},
    ("trend_following", "neutral"):       {"long_wr": 0.50, "short_wr": 0.50, "sharpe": 0.4},
    ("vcp",            "bull_trend"):     {"long_wr": 0.45, "short_wr": 0.67, "sharpe": 1.8},
    ("vcp",            "bear_trend"):     {"long_wr": 0.55, "short_wr": 0.58, "sharpe": 1.3},
    ("vcp",            "bull_ranging"):   {"long_wr": 0.62, "short_wr": 0.40, "sharpe": 2.1},
    ("vcp",            "bear_ranging"):   {"long_wr": 0.58, "short_wr": 0.55, "sharpe": 1.9},
    ("vcp",            "neutral"):        {"long_wr": 0.55, "short_wr": 0.55, "sharpe": 1.0},
    ("mean_reversion", "bull_trend"):     {"long_wr": 0.32, "short_wr": 0.65, "sharpe": 1.5},
    ("mean_reversion", "bear_trend"):     {"long_wr": 0.62, "short_wr": 0.38, "sharpe": 1.4},
    ("mean_reversion", "bull_ranging"):   {"long_wr": 0.50, "short_wr": 0.50, "sharpe": 0.6},
    ("mean_reversion", "bear_ranging"):   {"long_wr": 0.48, "short_wr": 0.52, "sharpe": 0.7},
    ("mean_reversion", "neutral"):        {"long_wr": 0.50, "short_wr": 0.50, "sharpe": 0.3},
}

# Regime weight matrix: how much to trust each track in each regime.
# (track, regime) → weight [0, 1]. Derived from BTC/ETH walk-forward 2022-2024.
_REGIME_WEIGHT: Dict[str, Dict[str, float]] = {
    "bull_trend":   {"trend_following": 1.00, "vcp": 0.85, "mean_reversion": 0.50},
    "bear_trend":   {"trend_following": 0.90, "vcp": 1.00, "mean_reversion": 0.55},
    "bull_ranging": {"trend_following": 0.75, "vcp": 1.00, "mean_reversion": 0.80},
    "bear_ranging": {"trend_following": 0.80, "vcp": 1.00, "mean_reversion": 0.75},
    "neutral":      {"trend_following": 0.90, "vcp": 0.95, "mean_reversion": 0.90},
}


@dataclass
class EnsembleTrackState:
    """Per-track state after scoring."""
    track_name: str
    raw_score: float          # 0-20
    norm_score: float         # 0-1 percentile within rolling window
    weight: float             # 0-1 after regime weighting
    trend_dir: int            # +1 / -1 / 0
    strength: str             # "STRONG" / "SIGNAL" / "NONE"
    wr_long: float
    wr_short: float
    sharpe: float
    agreement_count: int      # tracks agreeing with this direction


@dataclass
class EnsembleSignal:
    """Combined output of all three tracks."""
    ensemble_score: float     # 0-20 composite score
    direction: int            # blended direction +1/-1/0
    strength: str             # STRONG/SIGNAL/NONE
    tracks: List[EnsembleTrackState]
    agreement_count: int     # total tracks agreeing on final direction
    regime_label: str
    composite_score: float    # 0-20 (pre-normalisation weighted average)
    cross_regime_corr: float  # 0-1 direction agreement measure
    strategy: str = "ensemble"
    edge_per_trade: float = 0.0  # expected edge from win-rate registry


# ── Rolling score windows ─────────────────────────────────────────────────────
_TRACK_WINDOWS: Dict[str, List[float]] = {
    "trend_following": [],
    "vcp": [],
    "mean_reversion": [],
}
_WINDOW_SIZE = 200


def update_history(track: str, score: float) -> None:
    win = _TRACK_WINDOWS.get(track.lower())
    if win is None:
        _TRACK_WINDOWS[track.lower()] = []
        win = _TRACK_WINDOWS[track.lower()]
    win.append(score)
    if len(win) > _WINDOW_SIZE:
        win.pop(0)


def get_history(track: str) -> List[float]:
    return list(_TRACK_WINDOWS.get(track.lower(), []))


def _normalise_score(score: float, warmup: List[float]) -> float:
    if not warmup:
        return 0.5
    arr = np.array(warmup, dtype=np.float64)
    return float(np.sum(arr < score) / len(arr))


def _strength_from_score(score: float) -> str:
    if score >= 14.0:
        return "STRONG"
    elif score >= 6.0:
        return "SIGNAL"
    return "NONE"


# ── Core ensemble scorer ──────────────────────────────────────────────────────

def _track_edge(track: str, regime: str, direction: int) -> float:
    """Expected edge = Sharpe × WinRate for the given direction side."""
    reg_key = (track.lower(), regime)
    wr_entry = _WIN_REGISTRY.get(reg_key, _WIN_REGISTRY.get(
        (track.lower(), "neutral"), {"long_wr": 0.5, "short_wr": 0.5, "sharpe": 0.4}
    ))
    wr = wr_entry["long_wr"] if direction == 1 else wr_entry["short_wr"]
    return wr_entry["sharpe"] * wr


def compute_ensemble_signal(
    candidates: List[TrackSignal],
    regime_label: str,
    track_score_history: Optional[Dict[str, List[float]]] = None,
) -> EnsembleSignal:
    """
    Combine TF + VCP + MR into a single composite signal.

    Best strategy from exhaustive search:
      - Score: max(track_score) across active tracks
      - Vote:  by_edge  (direction = sign of Σ edge_i × trend_dir_i)
      - Boost: linear_agree  (+15% for 2 agreeing, +30% for 3)
      - Threshold: 7.0
      - Strength: composite_vote (max_score ≥ 14 + agree_count ≥ 2 → STRONG)

    Parameters
    ----------
    candidates : List[TrackSignal]
        Pre-computed TrackSignals from the three tracks.
        Expected keys: "trend_following", "vcp", "mean_reversion".
        Other tracks passed through unchanged.
    regime_label : str
        e.g. "BULL_TREND", "BEAR_RANGING" (lower-cased internally).
    track_score_history : Dict[str, List[float]], optional
        Per-track score history for normalisation. If None, uses the
        global rolling windows (_TRACK_WINDOWS).

    Returns
    -------
    EnsembleSignal
        All three tracks scored + one composite direction/score.
        direction != 0 if any track has trend_dir != 0.
    """
    if not candidates:
        return _neutral_ensemble()

    regime = regime_label.lower().replace(" ", "_").replace("__", "_")
    history = track_score_history or {}
    rw = _REGIME_WEIGHT.get(regime, _REGIME_WEIGHT["neutral"])

    # ── Step 1: Score, weight, and edge for each track ──────────────────────────
    track_states: List[EnsembleTrackState] = []
    for ts in candidates:
        warmup = history.get(ts.track) if history else None
        if warmup is None:
            warmup = _TRACK_WINDOWS.get(ts.track, [])

        norm = _normalise_score(ts.score, warmup)
        base_w = rw.get(ts.track, 0.70)

        reg_key = (ts.track.lower(), regime)
        wr = _WIN_REGISTRY.get(reg_key, _WIN_REGISTRY.get(
            (ts.track.lower(), "neutral"), {"long_wr": 0.5, "short_wr": 0.5, "sharpe": 0.5}
        ))

        track_states.append(EnsembleTrackState(
            track_name=ts.track,
            raw_score=ts.score,
            norm_score=norm,
            weight=0.0,
            trend_dir=ts.trend_dir,
            strength=ts.strength,
            wr_long=wr["long_wr"],
            wr_short=wr["short_wr"],
            sharpe=wr["sharpe"],
            agreement_count=1,
        ))

    # Apply regime weight
    for st in track_states:
        st.weight = st.norm_score * rw.get(st.track_name, 0.7)

    # ── Step 2: Direction agreement count ────────────────────────────────────
    dir_groups: Dict[int, List[EnsembleTrackState]] = {}
    for st in track_states:
        if st.trend_dir == 0:
            continue
        dir_groups.setdefault(st.trend_dir, []).append(st)
    for st in track_states:
        if st.trend_dir != 0:
            st.agreement_count = len(dir_groups.get(st.trend_dir, []))

    # ── Step 3: Edge-weighted composite ──────────────────────────────────────
    #
    # Best from search: by_edge voting + max score + linear_agree boost
    #
    # Direction: sign(Σ edge_i × trend_dir_i) — edge-weighted vote
    # Score: max(active scores) × (1 + boost)
    # Boost: +15% if ≥2 agreeing, +30% if 3 agreeing
    #
    active_states = [st for st in track_states if st.trend_dir != 0]

    # Direction vote: edge-weighted
    direction_raw = sum(
        _track_edge(st.track_name, regime, st.trend_dir) * st.trend_dir
        for st in active_states
    )
    direction = int(np.sign(direction_raw)) if direction_raw != 0 else 0

    # Boost from agreement — only when agreeing tracks match ensemble direction
    agreeing_states = [st for st in active_states if st.trend_dir == direction and direction != 0]
    n_agreeing = len(agreeing_states)
    boost = 0.30 if n_agreeing >= 3 else (0.15 if n_agreeing == 2 else 0.0)

    # Score: use max raw score among active tracks
    if active_states:
        composite_raw = max(st.raw_score for st in active_states) * (1.0 + boost)
    else:
        composite_raw = 0.0

    ensemble_score = min(20.0, composite_raw)

    # Direction confidence: proportion of agreeing tracks
    dir_conf = n_agreeing / 3.0 if active_states else 0.0

    # Expected edge: mean edge of tracks that agree with ensemble direction
    if agreeing_states:
        avg_edge = np.mean([
            _track_edge(st.track_name, regime, direction) for st in agreeing_states
        ])
    elif active_states:
        # Fall back to mean edge of all active tracks
        avg_edge = np.mean([
            _track_edge(st.track_name, regime, st.trend_dir) for st in active_states
        ])
    else:
        avg_edge = 0.0

    # ── Step 4: Strength assignment ──────────────────────────────────────────
    # Best from search: composite_vote — max_score ≥ 14 + agree_count ≥ 2 → STRONG
    # Additional guard: the highest-scoring track must ALSO agree with ensemble direction
    # (otherwise a high-scoring outlier is being propped up by other tracks' directions)
    max_score_state = max(track_states, key=lambda st: st.raw_score, default=None)
    max_score = max_score_state.raw_score if max_score_state else 0.0

    if (max_score >= 14.0 and n_agreeing >= 2
            and max_score_state is not None
            and max_score_state.trend_dir == direction):
        final_strength = "STRONG"
    elif max_score >= 6.0 and n_agreeing >= 1:
        final_strength = "SIGNAL"
    else:
        final_strength = "NONE"

    # ── Step 5: Cross-regime correlation ─────────────────────────────────────
    cross_corr = _dir_correlation(track_states)

    # ── Step 6: Normalise ensemble_score to 0-20 ───────────────────────────
    # The score is already on a ~0-20 scale from raw scores, boost may push it over
    ensemble_score = min(20.0, ensemble_score)

    return EnsembleSignal(
        ensemble_score=round(ensemble_score, 2),
        direction=direction,
        strength=final_strength,
        tracks=track_states,
        agreement_count=n_agreeing if direction != 0 else 0,
        regime_label=regime,
        composite_score=round(composite_raw, 2),
        cross_regime_corr=cross_corr,
        strategy="ensemble",
        edge_per_trade=round(avg_edge, 4),
    )


def _dir_correlation(states: List[EnsembleTrackState]) -> float:
    dirs = [s.trend_dir for s in states if s.trend_dir != 0]
    if len(dirs) < 2:
        return 1.0
    return 1.0 if all(d > 0 for d in dirs) or not any(d > 0 for d in dirs) else 0.0


def _neutral_ensemble() -> EnsembleSignal:
    return EnsembleSignal(
        ensemble_score=0.0, direction=0, strength="NONE",
        tracks=[], agreement_count=0, regime_label="neutral",
        composite_score=0.0, cross_regime_corr=0.0, strategy="ensemble",
        edge_per_trade=0.0,
    )


# ── Win-rate hot-loading ──────────────────────────────────────────────────────

def hot_load_winrates(path: Optional[str] = None) -> None:
    if path is None:
        path = os.environ.get("STERLING_WINRATE_REGISTRY", "")
    if not path:
        return
    try:
        import json
        with open(path, "r") as f:
            data = json.load(f)
        for key, val in data.items():
            if isinstance(key, str) and isinstance(val, dict):
                parts = key.split("|")
                if len(parts) == 2:
                    _WIN_REGISTRY[(parts[0].lower(), parts[1].lower())] = val
    except Exception:
        pass


hot_load_winrates()