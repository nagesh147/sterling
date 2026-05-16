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
    """
    A3: Use the composite health_score (0-100) computed by
    contract_health_engine.assess_contract_health, which already weights
    spread, OI, volume, and quote freshness equally. Scaled to 0-20 here.

    Funding-rate penalty (futures perp impact on options theta) still applied.
    Futures structures get a fixed 18 — they have no option-style health,
    but funding penalty applies via the same hook.
    """
    if structure.structure_type == "futures":
        base = 18.0
    else:
        if not structure.legs:
            return 0.0
        leg = structure.legs[0]
        # Composite health_score is 0-100; scale to 0-20.
        health = float(getattr(leg, "health_score", 0.0))
        base = max(0.0, min(20.0, health / 5.0))

    if funding_rate is not None:
        base -= min(abs(funding_rate) * 300, 5.0)
    return max(0.0, round(base, 2))


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


def _in_funding_window(hour_utc: int, minute_utc: int) -> bool:
    """
    A5: True if within ±15 min of crypto perp funding boundaries (00:00, 08:00,
    16:00 UTC). The funding flip + settlement creates documented mean-reversion
    that hurts trend-followers; we widen the dead-zone around these instants.
    """
    boundaries = (0, 8, 16)
    for b in boundaries:
        prev_hour = (b - 1) % 24
        if hour_utc == b and minute_utc < 15:
            return True
        if hour_utc == prev_hour and minute_utc >= 45:
            return True
    return False


def _score_session_bonus(hour_utc: Optional[int] = None) -> float:
    """
    A4: 0-3 point bonus for high-liquidity crypto sessions (UTC).
      13-16  → +3.0  US/EU overlap (peak crypto liquidity)
      17-20  → +2.0  US extension (tight spreads, strong follow-through)
       7-12  → +1.5  EU morning (reasonable two-way flow)
       0- 2  → +0.5  Asia overlap (thin but trending)
       else  → 0
    """
    h = hour_utc if hour_utc is not None else _dt.datetime.now(_dt.timezone.utc).hour
    if 13 <= h <= 16:
        return 3.0
    if 17 <= h <= 20:
        return 2.0
    if 7 <= h <= 12:
        return 1.5
    if 0 <= h <= 2:
        return 0.5
    return 0.0


def _check_hard_vetoes(
    structure: TradeStructure,
    funding_rate: Optional[float] = None,
    bar_hour_utc: Optional[int] = None,
    bar_minute_utc: Optional[int] = None,
) -> Optional[str]:
    if not structure.legs and structure.structure_type != "futures":
        return "no legs"
    leg = structure.legs[0] if structure.legs else None
    spread_pct = getattr(leg, "spread_pct", 0.0) if leg else 0.0
    oi = getattr(leg, "open_interest", 0.0) if leg else 0.0

    if leg is not None:
        if spread_pct > 0.10:
            return f"spread {spread_pct:.1%} > 10%"
        if oi < 50:
            return f"OI {oi:.0f} < 50"

        # Naked shorts require tighter guardrails: OI > 100 AND spread < 5%
        is_naked_short = structure.structure_type in ("naked_short", "naked_short_call", "naked_short_put")
        if is_naked_short:
            if oi <= 100:
                return f"naked short: OI {oi:.0f} ≤ 100 (requires > 100)"
            if spread_pct >= 0.05:
                return f"naked short: spread {spread_pct:.1%} ≥ 5% (requires < 5%)"

    # Use caller-supplied bar hour (backtest context) or current wall-clock hour (live).
    now = _dt.datetime.now(_dt.timezone.utc)
    hour_utc = bar_hour_utc if bar_hour_utc is not None else now.hour
    minute_utc = bar_minute_utc if bar_minute_utc is not None else now.minute
    if hour_utc in {2, 3, 4, 5}:
        return f"hour {hour_utc}:00 UTC in dead zone"

    # A5: funding-window veto (±15 min of 00/08/16 UTC)
    if _in_funding_window(hour_utc, minute_utc):
        return f"funding window {hour_utc:02d}:{minute_utc:02d} UTC (±15min of 00/08/16)"

    if funding_rate is not None and abs(funding_rate) > 0.025:
        return f"funding_rate {funding_rate:.4f} exceeds 0.025 threshold"

    return None


# ── Hard score threshold gates ────────────────────────────────────────────────

_SCORE_THRESHOLD_NORMAL = 75.0
_SCORE_THRESHOLD_HIGH   = 85.0  # high leverage (≥10×) or naked shorts


def _needs_high_threshold(structure: TradeStructure, leverage: int = 1) -> bool:
    """True if this structure requires the ≥85 score threshold."""
    is_naked_short = structure.structure_type in ("naked_short", "naked_short_call", "naked_short_put")
    is_high_leverage = leverage >= 10
    return is_naked_short or is_high_leverage


def passes_score_threshold(
    structure: TradeStructure,
    leverage: int = 1,
) -> tuple[bool, str]:
    """
    Returns (passes, reason). Enforces hard gates:
      - ≥85 for naked shorts and leverage ≥ 10×
      - ≥75 for everything else
    """
    threshold = _SCORE_THRESHOLD_HIGH if _needs_high_threshold(structure, leverage) else _SCORE_THRESHOLD_NORMAL
    if structure.score < threshold:
        return False, f"score {structure.score:.1f} < threshold {threshold:.0f}"
    return True, ""


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
    bar_hour_utc: Optional[int] = None,
    bar_minute_utc: Optional[int] = None,
) -> TradeStructure:
    direction = structure.direction.value

    veto = _check_hard_vetoes(structure, funding_rate, bar_hour_utc, bar_minute_utc)
    if veto:
        breakdown = {
            "macro_trend": 0.0, "signal": 0.0, "entry": 0.0,
            "contract_health": 0.0, "dte": 0.0, "rr": 0.0,
            "session_bonus": 0.0,
            "total": 0.0, "veto_reason": veto,
        }
        return structure.model_copy(update={"score": 0.0, "score_breakdown": breakdown})

    s_macro = _score_macro_regime(regime)
    s_signal = _score_signal_v2(signal, direction)
    s_exec = _score_exec_timing_v2(exec_timing)
    s_health = _score_contract_health_v2(structure, funding_rate)
    s_dte = _score_dte_v2(structure)
    s_rr = _score_rr_v2(structure)
    s_session = _score_session_bonus(bar_hour_utc)

    # Base = 20+20+15+20+10+15 = 100; session_bonus uplifts up to +3, clamped to 100.
    total = min(round(s_macro + s_signal + s_exec + s_health + s_dte + s_rr + s_session, 1), 100.0)

    breakdown = {
        "macro_trend": round(s_macro, 2),
        "signal": round(s_signal, 2),
        "entry": round(s_exec, 2),
        "contract_health": round(s_health, 2),
        "dte": round(s_dte, 2),
        "rr": round(s_rr, 2),
        "session_bonus": round(s_session, 2),
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
    bar_hour_utc: Optional[int] = None,
    bar_minute_utc: Optional[int] = None,
    leverage: int = 1,
) -> List[TradeStructure]:
    scored = [
        score_structure(s, regime, signal, exec_timing, policy, weights, funding_rate, bar_hour_utc, bar_minute_utc)
        for s in structures
    ]
    # Apply hard score threshold: filter structures that don't meet the ≥75/≥85 gate.
    # Futures structures inherit the leverage from the caller.
    passing = []
    for s in scored:
        s_lev = s.leverage if s.structure_type == "futures" else leverage
        ok, _ = passes_score_threshold(s, s_lev)
        if ok:
            passing.append(s)
    return sorted(passing, key=lambda s: s.score, reverse=True)
