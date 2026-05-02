from typing import Optional, List
from app.schemas.directional import PolicyResult, IVRBand, Direction
from app.schemas.instruments import InstrumentMeta


def _ivr_band(ivr: Optional[float]) -> IVRBand:
    if ivr is None:
        # Unknown IV — fail closed: treat as elevated so naked options are excluded
        # and debit spreads are preferred over naked long premium.
        return IVRBand.ELEVATED
    if ivr < 40:
        return IVRBand.LOW
    if ivr < 60:
        return IVRBand.NORMAL
    if ivr <= 80:
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
    band = _ivr_band(ivr)
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
