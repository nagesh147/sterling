from typing import List, Optional
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.risk import ScoringWeights
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult,
    PolicyResult, ExecMode, IVRBand,
)
from app.engines.directional.option_translation_engine import dte_score

_DEFAULT_WEIGHTS = ScoringWeights()


def _weights() -> ScoringWeights:
    """Return runtime scoring weights (set via config API)."""
    try:
        from app.api.v1.endpoints.config import get_scoring_weights
        return get_scoring_weights()
    except Exception:
        return _DEFAULT_WEIGHTS


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
        return 40.0
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
    weights: Optional[ScoringWeights] = None,
) -> TradeStructure:
    w = weights or _weights()
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

    # Normalize weights so scores stay in [0, 100] regardless of user customization
    w_sum = (w.regime + w.signal + w.execution + w.health + w.dte + w.risk_reward) or 1.0

    total = (
        s_regime * w.regime
        + s_signal * w.signal
        + s_exec * w.execution
        + s_health * w.health
        + s_dte * w.dte
        + s_rr * w.risk_reward
    ) / w_sum

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
    base = 20.0
    if policy.avoid_long_premium:
        base += 40.0
    if signal.trend == 0:
        base += 20.0
    if regime.score < 40.0:
        base += 20.0
    # Penalise unknown IV — we can't reliably price premium without IV data
    if policy.ivr is None:
        base += 15.0
    return min(100.0, base)


def rank_structures(
    structures: List[TradeStructure],
    regime: RegimeResult,
    signal: SignalResult,
    exec_timing: ExecTimingResult,
    policy: PolicyResult,
    weights: Optional[ScoringWeights] = None,
) -> List[TradeStructure]:
    w = weights or _weights()
    scored = [
        score_structure(s, regime, signal, exec_timing, policy, w)
        for s in structures
    ]
    return sorted(scored, key=lambda s: s.score, reverse=True)
