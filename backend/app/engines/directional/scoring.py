from typing import List, Optional
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult,
    PolicyResult, ExecMode, IVRBand,
)
from app.engines.directional.option_translation_engine import dte_score

# Deterministic weights
_W_REGIME = 0.20
_W_SIGNAL = 0.20
_W_EXEC = 0.15
_W_DTE = 0.15
_W_HEALTH = 0.20
_W_RR = 0.10


def score_macro_regime(regime: RegimeResult) -> float:
    return regime.score


def score_signal(signal: SignalResult, direction: str) -> float:
    if direction == "long":
        return signal.score_long
    if direction == "short":
        return signal.score_short
    return 0.0


def score_exec_timing(exec_timing: ExecTimingResult) -> float:
    if exec_timing.mode == ExecMode.PULLBACK:
        return 60.0 + exec_timing.confidence * 40.0
    if exec_timing.mode == ExecMode.CONTINUATION:
        return 50.0 + exec_timing.confidence * 40.0
    return 20.0


def score_structure_rr(structure: TradeStructure) -> float:
    if structure.risk_reward is None:
        return 40.0  # naked: unlimited upside, moderate score
    rr = structure.risk_reward
    if rr >= 3.0:
        return 100.0
    if rr >= 2.0:
        return 80.0
    if rr >= 1.5:
        return 65.0
    if rr >= 1.0:
        return 50.0
    return max(0.0, rr * 50.0)


def score_structure(
    structure: TradeStructure,
    regime: RegimeResult,
    signal: SignalResult,
    exec_timing: ExecTimingResult,
    policy: PolicyResult,
) -> TradeStructure:
    direction = structure.direction.value

    s_regime = score_macro_regime(regime)
    s_signal = score_signal(signal, direction)
    s_exec = score_exec_timing(exec_timing)
    s_health = float(
        sum(l.health_score for l in structure.legs) / max(1, len(structure.legs))
    )
    s_dte = float(
        sum(dte_score(l.dte, policy) for l in structure.legs) / max(1, len(structure.legs))
    )
    s_rr = score_structure_rr(structure)

    total = (
        s_regime * _W_REGIME
        + s_signal * _W_SIGNAL
        + s_exec * _W_EXEC
        + s_health * _W_HEALTH
        + s_dte * _W_DTE
        + s_rr * _W_RR
    )

    breakdown = {
        "regime": round(s_regime, 2),
        "signal": round(s_signal, 2),
        "exec_timing": round(s_exec, 2),
        "health": round(s_health, 2),
        "dte": round(s_dte, 2),
        "rr": round(s_rr, 2),
        "total": round(total, 2),
    }

    return structure.model_copy(update={"score": round(total, 2), "score_breakdown": breakdown})


def score_no_trade(regime: RegimeResult, signal: SignalResult, policy: PolicyResult) -> float:
    """Higher = stronger reason to not trade."""
    base = 20.0
    if policy.avoid_long_premium:
        base += 40.0
    if signal.trend == 0:
        base += 20.0
    if regime.score < 40.0:
        base += 20.0
    return min(100.0, base)


def rank_structures(
    structures: List[TradeStructure],
    regime: RegimeResult,
    signal: SignalResult,
    exec_timing: ExecTimingResult,
    policy: PolicyResult,
) -> List[TradeStructure]:
    scored = [
        score_structure(s, regime, signal, exec_timing, policy)
        for s in structures
    ]
    return sorted(scored, key=lambda s: s.score, reverse=True)
