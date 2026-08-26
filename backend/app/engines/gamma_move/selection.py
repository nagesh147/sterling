"""Which contract a level implies: expiry window, strike window, highest OI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Sequence

from .config import GammaMoveConfig
from .models import InstrumentRef, SpotLevel, StrikeCandidate


def days_to_expiry(expiry: str, today: date) -> Optional[int]:
    try:
        return (datetime.strptime(expiry[:10], "%Y-%m-%d").date() - today).days
    except (ValueError, TypeError):
        return None


def expiry_in_window(expiry: str, today: date, cfg: GammaMoveConfig) -> bool:
    """The source's "only the last week or two" rule, as a closed interval.

    NSE stock options are monthly-only -- there is no weekly stock series -- so
    this window is roughly the 15th of the month onward, and outside it the
    engine is meant to find nothing rather than to trade a worse setup.
    """
    dte = days_to_expiry(expiry, today)
    if dte is None:
        return False
    if cfg.avoid_expiry_day and dte == 0:
        # Expiry day itself. The open-interest signal degenerates into settlement
        # mechanics there and the premium is nearly all gamma already — a
        # different trade wearing this one's name.
        return False
    return cfg.expiry_dte_min <= dte <= cfg.expiry_dte_max


def select_expiry(expiries: Sequence[str], today: date,
                  cfg: GammaMoveConfig) -> Optional[str]:
    """The soonest expiry inside the window, or None if none qualifies."""
    ok = sorted({e[:10] for e in expiries if expiry_in_window(e, today, cfg)})
    return ok[0] if ok else None


def strikes_near_level(contracts: Sequence[InstrumentRef], level: SpotLevel,
                       cfg: GammaMoveConfig) -> list[InstrumentRef]:
    """Contracts of the right type whose strike sits near the level.

    The source allows the heaviest strike to be "a couple of strikes up or down"
    from the exact level, which is what ``strike_window_pct`` expresses.
    """
    want = "CE" if level.kind == "resistance" else "PE"
    if level.price <= 0:
        return []
    return [c for c in contracts
            if c.option_type == want
            and abs(c.strike - level.price) / level.price * 100.0 <= cfg.strike_window_pct]


def pick_strike(contracts: Sequence[InstrumentRef], level: SpotLevel, *,
                underlying: str, oi_by_id: dict, premium_by_id: dict, spot: float,
                today: date, cfg: GammaMoveConfig) -> Optional[StrikeCandidate]:
    """The highest-open-interest strike at the level -- the source's R4 pick.

    Ties break toward the strike nearest the level, because at equal open
    interest the nearer strike is the one the break actually threatens.
    """
    best: Optional[StrikeCandidate] = None
    for c in strikes_near_level(contracts, level, cfg):
        oi = int(oi_by_id.get(c.instrument_id) or 0)
        premium = float(premium_by_id.get(c.instrument_id) or 0.0)
        if oi < cfg.min_option_oi or premium < cfg.min_option_premium:
            continue
        dte = days_to_expiry(c.expiry, today)
        if dte is None or not expiry_in_window(c.expiry, today, cfg):
            continue
        cand = StrikeCandidate(underlying=underlying, level=level, instrument=c,
                               oi=oi, days_to_expiry=dte, spot=spot, premium=premium)
        if best is None or (oi, -abs(c.strike - level.price)) > (best.oi, -abs(best.instrument.strike - level.price)):
            best = cand
    return best
