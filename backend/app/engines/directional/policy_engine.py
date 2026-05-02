from typing import Optional, List
from app.schemas.directional import PolicyResult, IVRBand, Direction
from app.schemas.instruments import InstrumentMeta


def _ivr_band(ivr: Optional[float], underlying: Optional[str] = None) -> IVRBand:
    if ivr is None:
        return IVRBand.ELEVATED

    # Try IV percentile first when underlying is known
    if underlying:
        try:
            from app.services.eval_history import get_ivr_percentile
            pct = get_ivr_percentile(underlying, ivr)
            rank = pct if pct is not None else ivr
        except Exception:
            rank = ivr
    else:
        rank = ivr

    if rank < 30:
        return IVRBand.LOW
    if rank < 55:
        return IVRBand.NORMAL
    if rank < 75:
        return IVRBand.ELEVATED
    return IVRBand.HIGH


def _allowed_structures(
    direction: Direction,
    ivr: Optional[float],
    ivr_band: IVRBand,
) -> List[str]:
    if direction == Direction.LONG:
        if ivr_band == IVRBand.HIGH:
            # >80 IVR: avoid long premium — credit spread only
            return ["bull_put_spread"]
        return ["naked_call", "bull_call_spread", "bull_put_spread"]
    elif direction == Direction.SHORT:
        if ivr_band == IVRBand.HIGH:
            # >80 IVR: avoid long premium — credit spread only
            return ["bear_call_spread"]
        return ["naked_put", "bear_put_spread", "bear_call_spread"]
    else:
        return ["no_trade"]


def apply_policy(
    direction: Direction,
    instrument: InstrumentMeta,
    ivr: Optional[float],
) -> PolicyResult:
    band = _ivr_band(ivr, underlying=instrument.underlying if instrument else None)
    naked_allowed = band in (IVRBand.LOW, IVRBand.NORMAL)
    debit_preferred = band == IVRBand.ELEVATED
    avoid_long_premium = band == IVRBand.HIGH

    structures = _allowed_structures(direction, ivr, band)

    return PolicyResult(
        allowed_structures=structures,
        ivr=ivr,
        ivr_band=band,
        preferred_dte_min=instrument.preferred_dte_min,
        preferred_dte_max=instrument.preferred_dte_max,
        naked_allowed=naked_allowed,
        debit_preferred=debit_preferred,
        avoid_long_premium=avoid_long_premium,
    )
