import datetime as _dt
from typing import List, Optional
from app.schemas.execution import TradeStructure, CandidateContract
from app.schemas.risk import ScoringWeights
from app.schemas.directional import (
    RegimeResult, SignalResult, ExecTimingResult,
    PolicyResult, ExecMode, IVRBand,
)


def _score_macro_regime(regime: RegimeResult) -> float:
    """Returns 0-20 points."""
    return min(20.0, max(0.0, float(regime.score)))


def _score_signal_v2(signal: SignalResult, direction: str) -> float:
    """Returns 0-20 points based on confluence signal_score."""
    return min(20.0, max(0.0, float(signal.signal_score)))


def _score_exec_timing_v2(exec_timing: ExecTimingResult) -> float:
    """Returns 0-15 points."""
    return min(15.0, max(0.0, float(exec_timing.exec_score)))


def _score_contract_health_v2(
    structure: TradeStructure,
    funding_rate: Optional[float] = None,
) -> float:
    """Returns 0-20 points."""
    if not structure.legs:
        return 0.0
    leg = structure.legs[0]
    spread_pct = getattr(leg, "spread_pct", 0.0)
    oi = getattr(leg, "open_interest", 0.0)

    score = 20.0
    score -= min(spread_pct * 120, 10.0)
    if oi < 200:
        score -= 5.0
    if oi < 100:
        score -= 5.0
    if funding_rate is not None:
        score -= min(abs(funding_rate) * 300, 5.0)
    return max(0.0, round(score, 2))


def _score_dte_v2(structure: TradeStructure) -> float:
    """Returns 0-10 points using DTE curve."""
    if not structure.legs:
        return 0.0
    if structure.structure_type == "futures":
        return 10.0
    dte = structure.legs[0].dte
    if dte < 7:
        return 0.0
    if dte < 14:
        return 3.0
    if dte <= 45:
        return 10.0
    if dte <= 60:
        return 7.0
    return 5.0


def _score_rr_v2(structure: TradeStructure) -> float:
    """Returns 0-15 points based on risk:reward."""
    if structure.risk_reward is None:
        return 0.0
    rr = structure.risk_reward
    if rr < 1.5:
        return 0.0
    if rr < 2.0:
        return 7.0
    if rr < 2.5:
        return 11.0
    return 15.0


def _check_hard_vetoes(
    structure: TradeStructure,
    funding_rate: Optional[float] = None,
) -> Optional[str]:
    if not structure.legs:
        return "no legs"
    leg = structure.legs[0]
    spread_pct = getattr(leg, "spread_pct", 0.0)
    oi = getattr(leg, "open_interest", 0.0)

    if spread_pct > 0.10:
        return f"spread {spread_pct:.1%} > 10%"
    if oi < 50:
        return f"OI {oi:.0f} < 50"

    hour_utc = _dt.datetime.now(_dt.timezone.utc).hour
    if hour_utc in {2, 3, 4, 5}:
        return f"hour {hour_utc}:00 UTC in dead zone"

    if funding_rate is not None and abs(funding_rate) > 0.025:
        return f"funding_rate {funding_rate:.4f} exceeds 0.025 threshold"

    return None


# ── Backward-compat aliases used by existing tests / endpoints ─────────────

def score_macro_regime(regime: RegimeResult) -> float:
    return _score_macro_regime(regime)


def score_signal(signal: SignalResult, direction: str) -> float:
    return _score_signal_v2(signal, direction)


def score_exec_timing(exec_timing: ExecTimingResult) -> float:
    return _score_exec_timing_v2(exec_timing)


def score_structure_rr(structure: TradeStructure) -> float:
    return _score_rr_v2(structure)


def score_structure(
    structure: TradeStructure,
    regime: RegimeResult,
    signal: SignalResult,
    exec_timing: ExecTimingResult,
    policy: PolicyResult,
    weights: Optional[ScoringWeights] = None,
    funding_rate: Optional[float] = None,
) -> TradeStructure:
    direction = structure.direction.value

    veto = _check_hard_vetoes(structure, funding_rate)
    if veto:
        breakdown = {
            "macro_trend": 0.0, "signal": 0.0, "entry": 0.0,
            "contract_health": 0.0, "dte": 0.0, "rr": 0.0,
            "total": 0.0, "veto_reason": veto,
        }
        return structure.model_copy(update={"score": 0.0, "score_breakdown": breakdown})

    s_macro = _score_macro_regime(regime)
    s_signal = _score_signal_v2(signal, direction)
    s_exec = _score_exec_timing_v2(exec_timing)
    s_health = _score_contract_health_v2(structure, funding_rate)
    s_dte = _score_dte_v2(structure)
    s_rr = _score_rr_v2(structure)

    # Max = 20+20+15+20+10+15 = 100
    total = min(round(s_macro + s_signal + s_exec + s_health + s_dte + s_rr, 1), 100.0)

    breakdown = {
        "macro_trend": round(s_macro, 2),
        "signal": round(s_signal, 2),
        "entry": round(s_exec, 2),
        "contract_health": round(s_health, 2),
        "dte": round(s_dte, 2),
        "rr": round(s_rr, 2),
        "total": round(total, 2),
    }

    return structure.model_copy(update={"score": total, "score_breakdown": breakdown})


def score_no_trade(regime: RegimeResult, signal: SignalResult, policy: PolicyResult) -> float:
    base = 20.0
    if policy.avoid_long_premium:
        base += 40.0
    if signal.trend == 0:
        base += 20.0
    if regime.score < 5.0:
        base += 20.0
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
    funding_rate: Optional[float] = None,
) -> List[TradeStructure]:
    scored = [
        score_structure(s, regime, signal, exec_timing, policy, weights, funding_rate)
        for s in structures
    ]
    return sorted(scored, key=lambda s: s.score, reverse=True)
