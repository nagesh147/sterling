from typing import Dict, List, Optional, Tuple
import numpy as np
from app.schemas.market import OptionSummary, Candle
from app.schemas.execution import CandidateContract
from app.schemas.directional import Direction, PolicyResult, IVRBand
from app.schemas.instruments import InstrumentMeta
from app.engines.directional.contract_health_engine import assess_contract_health


# ── A1: IVR-aware delta-band targeting ────────────────────────────────────────
# Maps the IVR regime to an absolute-delta band on candidate contracts.
# The band is intentionally wide enough that the structure builder can still
# find adjacent strikes for spreads — this is a soft "no garbage" filter, not
# a precision-strike picker.
#
#   LOW       → long premium preferred; want decent moneyness for naked + debit
#   NORMAL    → balanced; moderate band
#   ELEVATED  → debit preferred; allow OTM cheap legs + some ATM
#   HIGH      → naked-short / credit; need wings (low Δ) AND ATM legs available
#
# Contracts with delta == 0.0 (no greeks reported by the adapter) are passed
# through by get_healthy_candidates — preserving back-compat with HV-only
# adapters such as Delta India and Binance.

def default_delta_band(ivr_band: IVRBand) -> Tuple[float, float]:
    """Return (lo, hi) absolute-delta band for the given IVR regime."""
    if ivr_band == IVRBand.LOW:
        return (0.20, 0.70)
    if ivr_band == IVRBand.NORMAL:
        return (0.18, 0.65)
    if ivr_band == IVRBand.ELEVATED:
        return (0.15, 0.55)
    # HIGH: keep wide so credit-spread builder has both wings and ATM available
    return (0.10, 0.55)


# ── B4: DTE term-structure preference ────────────────────────────────────────
# Adapters that expose mark_iv per option allow us to compute an ATM-IV value
# per expiry. Compared to the underlying's realized HV (computed elsewhere),
# this tells us whether the active side has positive carry:
#   long_premium  earns when IV < HV (cheap implied vol vs realized)
#   short_premium earns when IV > HV (rich implied vol)
#
# Adapters without IV (HV-only fallback) report mark_iv = 0; the helpers
# return a neutral 0 bonus, preserving back-compat.

def compute_term_iv(
    option_chain: List[OptionSummary],
    spot_price: float,
    atm_pct: float = 0.05,
) -> Dict[int, float]:
    """ATM-mean mark_iv per DTE bucket. ATM = strike within ±atm_pct of spot."""
    by_dte: Dict[int, List[float]] = {}
    if spot_price <= 0:
        return {}
    for opt in option_chain:
        if opt.mark_iv <= 0 or opt.strike <= 0:
            continue
        if abs(opt.strike - spot_price) / spot_price > atm_pct:
            continue
        by_dte.setdefault(opt.dte, []).append(opt.mark_iv)
    return {d: float(np.mean(v)) for d, v in by_dte.items() if v}


def compute_realized_hv(candles_1h: List[Candle], window_days: int = 30) -> Optional[float]:
    """
    Annualized realized volatility of log-returns over the trailing window_days
    (24 1H bars per day). Returns a fraction (e.g. 0.65 = 65% HV) or None when
    insufficient data. Comparable directly to mark_iv on options.
    """
    if not candles_1h or len(candles_1h) < 24:
        return None
    closes = np.array([c.close for c in candles_1h], dtype=np.float64)
    if len(closes) < 24:
        return None
    log_rets = np.diff(np.log(closes + 1e-10))
    bars = window_days * 24
    seg = log_rets[-bars:] if len(log_rets) > bars else log_rets
    if len(seg) < 12:
        return None
    return float(np.std(seg) * np.sqrt(365 * 24))


def term_structure_bonus(
    dte: int,
    term_iv_by_dte: Optional[Dict[int, float]],
    realized_hv: Optional[float],
    side: str = "neutral",
) -> float:
    """
    Returns 0-3 point bonus on dte_score when the per-expiry IV vs HV favors
    the active side.

      side="long_premium":  IV < HV ⇒ buyers paying less than realized → bonus
      side="short_premium": IV > HV ⇒ sellers receiving more than realized → bonus
      side="neutral":       no preference → 0

    Linear scale: ≥10% spread = full 3 pts; <10% = scaled.
    """
    if not term_iv_by_dte or realized_hv is None or realized_hv <= 0:
        return 0.0
    iv = term_iv_by_dte.get(dte)
    if iv is None or iv <= 0:
        return 0.0
    spread = (iv - realized_hv) / realized_hv
    if side == "long_premium" and spread < -0.05:
        return round(min(3.0, abs(spread) * 30.0), 2)
    if side == "short_premium" and spread > 0.05:
        return round(min(3.0, spread * 30.0), 2)
    return 0.0


def policy_premium_side(policy: PolicyResult) -> str:
    """Map an IVR-band policy decision to the side we are taking on premium."""
    if policy.ivr_band in (IVRBand.LOW, IVRBand.NORMAL):
        return "long_premium"
    if policy.ivr_band == IVRBand.HIGH:
        return "short_premium"
    return "neutral"


def _dte_score_raw(dte: int, preferred_min: int, preferred_max: int) -> float:
    if dte < 5:
        return 0.0
    if preferred_min <= dte <= preferred_max:
        return 100.0
    if dte < preferred_min:
        return 50.0 + (dte - 5) / max(1, preferred_min - 5) * 50.0
    return max(0.0, 100.0 - (dte - preferred_max) * 2.0)


def dte_score(
    dte: int,
    policy: PolicyResult,
    term_iv_by_dte: Optional[Dict[int, float]] = None,
    realized_hv: Optional[float] = None,
    side: Optional[str] = None,
) -> float:
    base = _dte_score_raw(dte, policy.preferred_dte_min, policy.preferred_dte_max)
    if side and term_iv_by_dte and realized_hv:
        base = min(100.0, base + term_structure_bonus(dte, term_iv_by_dte, realized_hv, side))
    return base


def get_healthy_candidates(
    instrument: InstrumentMeta,
    policy: PolicyResult,
    option_chain: List[OptionSummary],
    spot_price: float,
    option_type: str,       # "call" | "put"
    max_candidates: int = 30,
    max_strike_pct: float = 0.25,
    target_delta_band: Optional[Tuple[float, float]] = None,
    term_iv_by_dte: Optional[Dict[int, float]] = None,
    realized_hv: Optional[float] = None,
    side: Optional[str] = None,
) -> List[CandidateContract]:
    """
    Filter + health-check option chain by type.
    Returns healthy candidates sorted by DTE score desc.

    target_delta_band: optional (lo, hi) on |delta|. When supplied, contracts
    whose absolute delta falls outside the band are filtered out. Contracts
    with delta == 0 (no greeks) are passed through to preserve back-compat
    with adapters that don't compute greeks.

    term_iv_by_dte / realized_hv / side: optional B4 inputs that boost dte_score
    on expiries with favorable IV vs HV term-structure for the active side.
    """
    filtered: List[Tuple[float, CandidateContract]] = []
    lo, hi = (target_delta_band if target_delta_band else (0.0, 1.0))

    for opt in option_chain:
        if opt.option_type != option_type:
            continue
        if opt.dte < instrument.min_dte:
            continue
        # Strike within max_strike_pct of spot
        if abs(opt.strike - spot_price) / spot_price > max_strike_pct:
            continue

        # Delta-band filter — skip when delta is zero (greeks unavailable)
        if target_delta_band is not None and opt.delta != 0.0:
            abs_delta = abs(opt.delta)
            if abs_delta < lo or abs_delta > hi:
                continue

        candidate = assess_contract_health(opt, min_dte=instrument.min_dte)
        if not candidate.healthy:
            continue

        filtered.append((dte_score(opt.dte, policy, term_iv_by_dte, realized_hv, side), candidate))

    filtered.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in filtered[:max_candidates]]


def translate_options(
    instrument: InstrumentMeta,
    direction: Direction,
    policy: PolicyResult,
    option_chain: List[OptionSummary],
    spot_price: float,
    max_candidates: int = 20,
    target_delta_band: Optional[Tuple[float, float]] = None,
    candles_1h: Optional[List[Candle]] = None,
) -> Tuple[List[CandidateContract], List[CandidateContract]]:
    """
    Returns (calls, puts) healthy candidate lists.
    Orchestrator passes both to structure_selector.

    target_delta_band overrides the IVR-derived default. When None, the band
    is derived from policy.ivr_band via default_delta_band(). Pass an explicit
    (0.0, 1.0) to disable filtering (used by tests / preview).

    candles_1h: optional 1H candles enabling B4 term-structure preference.
    When provided alongside an option chain that exposes mark_iv, expiries
    with favorable IV/HV carry get a +0-3 dte_score bonus.
    """
    band = target_delta_band if target_delta_band is not None else default_delta_band(policy.ivr_band)

    term_iv = compute_term_iv(option_chain, spot_price)
    realized_hv = compute_realized_hv(candles_1h) if candles_1h else None
    side = policy_premium_side(policy)

    calls = get_healthy_candidates(
        instrument, policy, option_chain, spot_price, "call", max_candidates,
        target_delta_band=band,
        term_iv_by_dte=term_iv, realized_hv=realized_hv, side=side,
    )
    puts = get_healthy_candidates(
        instrument, policy, option_chain, spot_price, "put", max_candidates,
        target_delta_band=band,
        term_iv_by_dte=term_iv, realized_hv=realized_hv, side=side,
    )
    return calls, puts
