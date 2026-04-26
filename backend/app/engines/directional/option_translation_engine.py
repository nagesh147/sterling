from typing import List, Tuple
from app.schemas.market import OptionSummary
from app.schemas.execution import CandidateContract
from app.schemas.directional import Direction, PolicyResult
from app.schemas.instruments import InstrumentMeta
from app.engines.directional.contract_health_engine import assess_contract_health


def _dte_score_raw(dte: int, preferred_min: int, preferred_max: int) -> float:
    if dte < 5:
        return 0.0
    if preferred_min <= dte <= preferred_max:
        return 100.0
    if dte < preferred_min:
        return 50.0 + (dte - 5) / max(1, preferred_min - 5) * 50.0
    return max(0.0, 100.0 - (dte - preferred_max) * 2.0)


def dte_score(dte: int, policy: PolicyResult) -> float:
    return _dte_score_raw(dte, policy.preferred_dte_min, policy.preferred_dte_max)


def get_healthy_candidates(
    instrument: InstrumentMeta,
    policy: PolicyResult,
    option_chain: List[OptionSummary],
    spot_price: float,
    option_type: str,       # "call" | "put"
    max_candidates: int = 30,
    max_strike_pct: float = 0.25,
) -> List[CandidateContract]:
    """
    Filter + health-check option chain by type.
    Returns healthy candidates sorted by DTE score desc.
    """
    filtered: List[Tuple[float, CandidateContract]] = []

    for opt in option_chain:
        if opt.option_type != option_type:
            continue
        if opt.dte < instrument.min_dte:
            continue
        # Strike within max_strike_pct of spot
        if abs(opt.strike - spot_price) / spot_price > max_strike_pct:
            continue

        candidate = assess_contract_health(opt, min_dte=instrument.min_dte)
        if not candidate.healthy:
            continue

        filtered.append((dte_score(opt.dte, policy), candidate))

    filtered.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in filtered[:max_candidates]]


def translate_options(
    instrument: InstrumentMeta,
    direction: Direction,
    policy: PolicyResult,
    option_chain: List[OptionSummary],
    spot_price: float,
    max_candidates: int = 20,
) -> Tuple[List[CandidateContract], List[CandidateContract]]:
    """
    Returns (calls, puts) healthy candidate lists.
    Orchestrator passes both to structure_selector.
    """
    calls = get_healthy_candidates(
        instrument, policy, option_chain, spot_price, "call", max_candidates
    )
    puts = get_healthy_candidates(
        instrument, policy, option_chain, spot_price, "put", max_candidates
    )
    return calls, puts
