"""
Sterling v4 — Ensemble track scorer (TF + VCP + MR combined).

Supports pluggable scoring strategies:
  - by_edge_max_linear_agree  (default, best from search May 2024)
  - unweighted_mean            (legacy, pre-search)

Usage:
  # Default (current best)
  python -c "from app.engines.directional.track_scoring import compute_ensemble_signal"

  # Override via env
  STERLING_SCORING_STRATEGY=unweighted_mean python -c "from app.engines.directional.track_scoring; print(get_active_strategy())"

  # Runtime switch (sets module-global)
  from app.engines.directional.track_scoring import set_strategy
  set_strategy("unweighted_mean")
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable

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

_REGIME_WEIGHT: Dict[str, Dict[str, float]] = {
    "bull_trend":   {"trend_following": 1.00, "vcp": 0.85, "mean_reversion": 0.50},
    "bear_trend":   {"trend_following": 0.90, "vcp": 1.00, "mean_reversion": 0.55},
    "bull_ranging": {"trend_following": 0.75, "vcp": 1.00, "mean_reversion": 0.80},
    "bear_ranging": {"trend_following": 0.80, "vcp": 1.00, "mean_reversion": 0.75},
    "neutral":      {"trend_following": 0.90, "vcp": 0.95, "mean_reversion": 0.90},
}


# ── Strategy registry ────────────────────────────────────────────────────────

@dataclass
class EnsembleTrackState:
    track_name: str
    raw_score: float
    norm_score: float
    weight: float
    trend_dir: int
    strength: str
    wr_long: float
    wr_short: float
    sharpe: float
    agreement_count: int


@dataclass
class EnsembleSignal:
    ensemble_score: float
    direction: int
    strength: str
    tracks: List[EnsembleTrackState]
    agreement_count: int
    regime_label: str
    composite_score: float
    cross_regime_corr: float
    strategy: str = "ensemble"
    edge_per_trade: float = 0.0


# ── Rolling score windows ─────────────────────────────────────────────────────
_TRACK_WINDOWS: Dict[str, List[float]] = {
    "trend_following": [],
    "vcp": [],
    "mean_reversion": [],
}
_WINDOW_SIZE = 200

# ── Module-global strategy ───────────────────────────────────────────────────
_ACTIVE_STRATEGY: str = os.environ.get("STERLING_SCORING_STRATEGY", "by_edge_max_linear_agree")


def get_active_strategy() -> str:
    return _ACTIVE_STRATEGY


def set_strategy(name: str) -> None:
    global _ACTIVE_STRATEGY
    if name not in AVAILABLE_STRATEGIES:
        raise ValueError(f"Unknown strategy {name!r}. Available: {list(AVAILABLE_STRATEGIES)}")
    _ACTIVE_STRATEGY = name


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


def _track_edge(track: str, regime: str, direction: int) -> float:
    reg_key = (track.lower(), regime)
    wr_entry = _WIN_REGISTRY.get(reg_key, _WIN_REGISTRY.get(
        (track.lower(), "neutral"), {"long_wr": 0.5, "short_wr": 0.5, "sharpe": 0.4}
    ))
    wr = wr_entry["long_wr"] if direction == 1 else wr_entry["short_wr"]
    return wr_entry["sharpe"] * wr


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


# ── Strategy implementations ───────────────────────────────────────────────────

def _compute_by_edge_max_linear_agree(
    track_states: List[EnsembleTrackState],
    regime: str,
) -> Tuple[int, float, str, float]:
    """
    by_edge_max_linear_agree — current best from search.

    Direction  : sign(Σ edge_i × trend_dir_i)  — edge-weighted vote
    Score      : max(active scores) × (1 + boost)
    Boost      : +30% if 3 agreeing, +15% if 2 agreeing
    Strength   : max_score ≥ 14 + agree_count ≥ 2 + top track agrees → STRONG
    """
    active_states = [st for st in track_states if st.trend_dir != 0]

    direction_raw = sum(
        _track_edge(st.track_name, regime, st.trend_dir) * st.trend_dir
        for st in active_states
    )
    direction = int(np.sign(direction_raw)) if direction_raw != 0 else 0

    agreeing_states = [st for st in active_states if st.trend_dir == direction and direction != 0]
    n_agreeing = len(agreeing_states)
    boost = 0.30 if n_agreeing >= 3 else (0.15 if n_agreeing == 2 else 0.0)

    if active_states:
        composite_raw = max(st.raw_score for st in active_states) * (1.0 + boost)
    else:
        composite_raw = 0.0

    ensemble_score = min(20.0, composite_raw)

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

    if agreeing_states:
        avg_edge = np.mean([_track_edge(st.track_name, regime, direction) for st in agreeing_states])
    elif active_states:
        avg_edge = np.mean([_track_edge(st.track_name, regime, st.trend_dir) for st in active_states])
    else:
        avg_edge = 0.0

    return direction, round(ensemble_score, 2), final_strength, round(avg_edge, 4)


def _compute_unweighted_mean(
    track_states: List[EnsembleTrackState],
    regime: str,
) -> Tuple[int, float, str, float]:
    """
    unweighted_mean — legacy scoring from pre-search.

    Direction  : sign(Σ weight_i × trend_dir_i) for active tracks
    Score      : (Σ norm_score / n_active) × 20
    Boost      : none
    Strength   : max_raw_score ≥ 14 → STRONG, ≥ 6 → SIGNAL
                 (no agreement requirement)
    """
    active_states = [st for st in track_states if st.trend_dir != 0]
    n_active = len(active_states)

    if n_active > 0:
        direction = int(np.sign(sum(st.weight * st.trend_dir for st in active_states)))
        ensemble_score = (sum(st.norm_score for st in active_states) / n_active) * 20.0
    else:
        direction = 0
        ensemble_score = 0.0

    max_score_state = max(track_states, key=lambda st: st.raw_score, default=None)
    max_score = max_score_state.raw_score if max_score_state else 0.0

    if max_score >= 14.0:
        final_strength = "STRONG"
    elif max_score >= 6.0:
        final_strength = "SIGNAL"
    else:
        final_strength = "NONE"

    if active_states:
        avg_edge = np.mean([
            st.sharpe * (st.wr_long if st.trend_dir == 1 else st.wr_short)
            for st in active_states
        ])
    else:
        avg_edge = 0.0

    return direction, min(20.0, round(ensemble_score, 2)), final_strength, round(avg_edge, 4)


# ── Strategy registry ──────────────────────────────────────────────────────────

StrategyCompute = Callable[[List[EnsembleTrackState], str], Tuple[int, float, str, float]]

AVAILABLE_STRATEGIES: Dict[str, StrategyCompute] = {
    "by_edge_max_linear_agree": _compute_by_edge_max_linear_agree,
    "unweighted_mean": _compute_unweighted_mean,
}


# ── Main dispatcher ───────────────────────────────────────────────────────────

def compute_ensemble_signal(
    candidates: List[TrackSignal],
    regime_label: str,
    track_score_history: Optional[Dict[str, List[float]]] = None,
) -> EnsembleSignal:
    """
    Combine TF + VCP + MR into a single composite signal.

    Delegates to the currently active strategy compute function.
    Default: by_edge_max_linear_agree (set via STERLING_SCORING_STRATEGY env
    or call set_strategy("unweighted_mean") at runtime).

    Returns EnsembleSignal with direction, score, strength, per-track states,
    and the active strategy name.
    """
    if not candidates:
        return _neutral_ensemble()

    regime = regime_label.lower().replace(" ", "_").replace("__", "_")
    history = track_score_history or {}
    rw = _REGIME_WEIGHT.get(regime, _REGIME_WEIGHT["neutral"])

    # Build per-track states (shared by all strategies)
    track_states: List[EnsembleTrackState] = []
    for ts in candidates:
        warmup = history.get(ts.track) if history else None
        if warmup is None:
            warmup = _TRACK_WINDOWS.get(ts.track, [])

        norm = _normalise_score(ts.score, warmup)

        reg_key = (ts.track.lower(), regime)
        wr = _WIN_REGISTRY.get(reg_key, _WIN_REGISTRY.get(
            (ts.track.lower(), "neutral"),
            {"long_wr": 0.5, "short_wr": 0.5, "sharpe": 0.5}
        ))

        track_states.append(EnsembleTrackState(
            track_name=ts.track,
            raw_score=ts.score,
            norm_score=norm,
            weight=norm * rw.get(ts.track, 0.7),
            trend_dir=ts.trend_dir,
            strength=ts.strength,
            wr_long=wr["long_wr"],
            wr_short=wr["short_wr"],
            sharpe=wr["sharpe"],
            agreement_count=1,
        ))

    # Direction agreement count (used by both strategies)
    dir_groups: Dict[int, List[EnsembleTrackState]] = {}
    for st in track_states:
        if st.trend_dir == 0:
            continue
        dir_groups.setdefault(st.trend_dir, []).append(st)
    for st in track_states:
        if st.trend_dir != 0:
            st.agreement_count = len(dir_groups.get(st.trend_dir, []))

    # Dispatch to active strategy
    compute_fn = AVAILABLE_STRATEGIES.get(_ACTIVE_STRATEGY, _compute_by_edge_max_linear_agree)
    direction, ensemble_score, final_strength, avg_edge = compute_fn(track_states, regime)

    n_agreeing = sum(1 for st in track_states if st.trend_dir == direction and direction != 0)
    cross_corr = _dir_correlation(track_states)

    return EnsembleSignal(
        ensemble_score=ensemble_score,
        direction=direction,
        strength=final_strength,
        tracks=track_states,
        agreement_count=n_agreeing if direction != 0 else 0,
        regime_label=regime,
        composite_score=ensemble_score,
        cross_regime_corr=cross_corr,
        strategy=_ACTIVE_STRATEGY,
        edge_per_trade=avg_edge,
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