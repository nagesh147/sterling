"""Pick the option that expresses the bias.

Bullish: buy the first OTM call. Prefer the call wall when that wall *is*
that first resistance (the BSE 3500 CE case). Never buy ATM when
``skip_atm`` is on — ATM premia pay more theta for a worse RR.

Bearish: the mirror, first OTM put / put wall.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .config import OIWallFlowConfig
from .models import BiasReport, ChainRow, InstrumentRef, OptionType, TradePlan, q2


def _row_at(rows: Sequence[ChainRow], strike: float) -> Optional[ChainRow]:
    for r in rows:
        if r.strike == strike:
            return r
    return None


def first_otm_call(spot: float, rows: Sequence[ChainRow], atm: float,
                   *, skip_atm: bool = True) -> Optional[ChainRow]:
    above = [r for r in sorted(rows, key=lambda r: r.strike) if r.strike > spot]
    if skip_atm:
        above = [r for r in above if r.strike != atm]
    return above[0] if above else None


def first_otm_put(spot: float, rows: Sequence[ChainRow], atm: float,
                  *, skip_atm: bool = True) -> Optional[ChainRow]:
    below = [r for r in sorted(rows, key=lambda r: r.strike, reverse=True) if r.strike < spot]
    if skip_atm:
        below = [r for r in below if r.strike != atm]
    return below[0] if below else None


def pick_row(spot: float, rows: Sequence[ChainRow], report: BiasReport,
             cfg: OIWallFlowConfig) -> tuple[Optional[ChainRow], OptionType, str]:
    atm = report.metrics.atm_strike
    walls = report.metrics.walls
    if report.bias == "bullish":
        wall = _row_at(rows, walls.call_wall)
        wall_ok = (
            cfg.prefer_wall_strike and wall is not None and wall.strike > spot
            and (not cfg.skip_atm or wall.strike != atm)
        )
        if wall_ok:
            return wall, "CE", (
                f"call wall {wall.strike:.0f} is the first resistance; "
                f"buy that CE, not ATM {atm:.0f}"
            )
        otm = first_otm_call(spot, rows, atm, skip_atm=cfg.skip_atm)
        if otm is not None:
            return otm, "CE", f"nearest OTM call {otm.strike:.0f}"
        return None, "CE", "no OTM call above spot"
    if report.bias == "bearish":
        wall = _row_at(rows, walls.put_wall)
        wall_ok = (
            cfg.prefer_wall_strike and wall is not None and wall.strike < spot
            and (not cfg.skip_atm or wall.strike != atm)
        )
        if wall_ok:
            return wall, "PE", (
                f"put wall {wall.strike:.0f} is the first support; "
                f"buy that PE, not ATM {atm:.0f}"
            )
        otm = first_otm_put(spot, rows, atm, skip_atm=cfg.skip_atm)
        if otm is not None:
            return otm, "PE", f"nearest OTM put {otm.strike:.0f}"
        return None, "PE", "no OTM put below spot"
    return None, "CE", "bias is neutral"


def premium_of(row: ChainRow, option_type: OptionType) -> float:
    return row.call_ltp if option_type == "CE" else row.put_ltp


def oi_of(row: ChainRow, option_type: OptionType) -> int:
    return row.call_oi if option_type == "CE" else row.put_oi


def make_plan(spot: float, rows: Sequence[ChainRow], report: BiasReport,
              cfg: OIWallFlowConfig, *, lot_size: int, instrument: Optional[InstrumentRef] = None
              ) -> tuple[Optional[TradePlan], Optional[str]]:
    row, option_type, why = pick_row(spot, rows, report, cfg)
    if row is None:
        return None, why
    entry = q2(premium_of(row, option_type))
    if entry < cfg.min_option_premium:
        return None, f"{option_type} {row.strike:.0f} premium {entry} is below {cfg.min_option_premium}"
    if oi_of(row, option_type) < cfg.min_option_oi:
        return None, (
            f"{option_type} {row.strike:.0f} OI {oi_of(row, option_type)} "
            f"is below {cfg.min_option_oi}"
        )
    stop = cfg.stop_price(entry)
    target = cfg.target_price(entry)
    if stop is None or target is None:
        return None, "could not build a stop or target from this premium"
    invalidation = (
        report.metrics.walls.put_wall if option_type == "CE"
        else report.metrics.walls.call_wall
    )
    lots = cfg.lots
    qty = cfg.effective_quantity(lot_size, lots)
    at_risk = (entry - stop) * qty
    if at_risk > cfg.max_premium_at_risk_inr:
        return None, (
            f"Rs {at_risk:,.0f} at risk exceeds the Rs "
            f"{cfg.max_premium_at_risk_inr:,.0f} cap"
        )
    return TradePlan(
        option_type=option_type,
        strike=row.strike,
        entry=entry,
        stop=stop,
        target=target,
        target_2=cfg.target_2_price(entry),
        underlying_invalidation=invalidation,
        lot_size=lot_size,
        quantity=qty,
        lots=lots,
        reason=why,
        instrument=instrument,
    ), None
