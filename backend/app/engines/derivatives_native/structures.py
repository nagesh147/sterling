"""Defined-risk options structure construction + payoff economics.

`compute_economics` derives net premium, max loss, max profit, and breakevens
from any set of legs by evaluating the piecewise-linear expiry payoff on the
grid {0, strikes, far}. The builders pick strikes from a live chain and size
contracts to a max-loss budget. Pure functions — no I/O, fully unit-testable.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from app.engines.derivatives.schemas import DerivativesStructure, StructureLeg
from app.schemas.market import OptionSummary


def _leg_intrinsic(leg: StructureLeg, s: float) -> float:
    if leg.option_type == "call":
        intr = max(s - leg.strike, 0.0)
    else:
        intr = max(leg.strike - s, 0.0)
    sign = 1.0 if leg.side == "buy" else -1.0
    return sign * intr * leg.ratio


def _net_debit(legs: Sequence[StructureLeg]) -> float:
    """+ = debit paid at entry, - = credit received."""
    return sum((leg.premium if leg.side == "buy" else -leg.premium) * leg.ratio
               for leg in legs)


def compute_economics(legs: Sequence[StructureLeg], contracts: float):
    """Return (net_premium_usd, max_loss_usd, max_profit_usd, breakevens).

    net_premium_usd: + debit / - credit (× contracts).
    max_loss_usd / max_profit_usd: positive magnitudes (× contracts).
    """
    if not legs:
        return 0.0, 0.0, 0.0, []
    net = _net_debit(legs)
    strikes = sorted({leg.strike for leg in legs})
    grid = [0.0] + strikes + [strikes[-1] * 2.0 + 1.0]

    def pnl(s: float) -> float:
        return sum(_leg_intrinsic(leg, s) for leg in legs) - net

    vals = [(s, pnl(s)) for s in grid]
    max_profit = max(v for _, v in vals)
    max_loss = min(v for _, v in vals)            # <= 0 for defined-risk

    breakevens: list[float] = []
    for (s0, p0), (s1, p1) in zip(vals, vals[1:]):
        if p0 == 0.0:
            breakevens.append(round(s0, 2))
        if (p0 < 0.0 < p1) or (p1 < 0.0 < p0):
            be = s0 + (0.0 - p0) * (s1 - s0) / (p1 - p0)
            breakevens.append(round(be, 2))

    return (
        round(net * contracts, 2),
        round(max(0.0, -max_loss) * contracts, 2),
        round(max(0.0, max_profit) * contracts, 2),
        sorted(set(breakevens)),
    )


def _nearest(chain: Sequence[OptionSummary], opt_type: str, target: float) -> Optional[OptionSummary]:
    cands = [o for o in chain if o.option_type == opt_type and o.strike > 0]
    if not cands:
        return None
    return min(cands, key=lambda o: abs(o.strike - target))


def _prem(o: OptionSummary) -> float:
    return o.mark_price if o.mark_price > 0 else o.mid_price


def _size_to_budget(per_contract_max_loss: float, nav_usd: float, max_loss_pct: float) -> float:
    if per_contract_max_loss <= 0:
        return 0.0
    budget = nav_usd * max_loss_pct
    return max(0.01, math.floor((budget / per_contract_max_loss) * 100) / 100)


def _leg_from_option(o: OptionSummary, side: str) -> StructureLeg:
    return StructureLeg(
        option_symbol=o.instrument_name, option_type=o.option_type, side=side,
        strike=o.strike, expiry=o.expiry_date, dte=o.dte, ratio=1, premium=_prem(o),
        delta=o.delta, gamma=o.gamma, vega=o.vega, theta=o.theta)


def build_debit_vertical(
    *, chain: Sequence[OptionSummary], spot: float, direction: str,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Bullish → call debit spread (buy ATM, sell OTM higher).
    Bearish → put debit spread (buy ATM, sell OTM lower)."""
    if direction == "long":
        opt_type, long_target, short_target = "call", spot, spot * (1.0 + width_pct)
    else:
        opt_type, long_target, short_target = "put", spot, spot * (1.0 - width_pct)
    long_o = _nearest(chain, opt_type, long_target)
    short_o = _nearest(chain, opt_type, short_target)
    if not long_o or not short_o or long_o.strike == short_o.strike:
        return None
    legs = [_leg_from_option(long_o, "buy"), _leg_from_option(short_o, "sell")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="debit_vertical", underlying=long_o.underlying,
        direction=direction, legs=legs, contracts=contracts,
        net_premium_usd=net, max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)


def build_credit_vertical(
    *, chain: Sequence[OptionSummary], spot: float, direction: str,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Bullish → put credit spread (sell OTM put, buy further-OTM put)."""
    if direction == "long":
        opt_type, short_target, long_target = "put", spot * (1.0 - width_pct), spot * (1.0 - 2 * width_pct)
    else:
        opt_type, short_target, long_target = "call", spot * (1.0 + width_pct), spot * (1.0 + 2 * width_pct)
    short_o = _nearest(chain, opt_type, short_target)
    long_o = _nearest(chain, opt_type, long_target)
    if not short_o or not long_o or short_o.strike == long_o.strike:
        return None
    legs = [_leg_from_option(short_o, "sell"), _leg_from_option(long_o, "buy")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="credit_vertical", underlying=short_o.underlying,
        direction=direction, legs=legs, contracts=contracts,
        net_premium_usd=net, max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)


def build_short_strangle(
    *, chain: Sequence[OptionSummary], spot: float,
    width_pct: float, nav_usd: float, premium_pct: float,
) -> Optional[DerivativesStructure]:
    """NAKED short strangle: sell OTM put + sell OTM call. UNCAPPED tail risk —
    `defined=False`. Sized to a PREMIUM budget (not max-loss, which is unbounded):
    contracts so collected credit ≈ premium_pct × NAV. Opt-in + regime-gated by
    the caller; never auto-executed."""
    sp = _nearest(chain, "put", spot * (1.0 - width_pct))
    sc = _nearest(chain, "call", spot * (1.0 + width_pct))
    if sp is None or sc is None or sp.strike == sc.strike:
        return None
    legs = [_leg_from_option(sp, "sell"), _leg_from_option(sc, "sell")]
    credit_per_contract = abs(_net_debit(legs))   # net credit (debit is negative)
    if credit_per_contract <= 0:
        return None
    budget = nav_usd * premium_pct
    contracts = max(0.01, math.floor((budget / credit_per_contract) * 100) / 100)
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="short_strangle", underlying=sp.underlying, direction="neutral",
        legs=legs, contracts=contracts, defined=False,
        net_premium_usd=net, max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)


def build_iron_condor(
    *, chain: Sequence[OptionSummary], spot: float,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Neutral: sell OTM put + call, buy further-OTM wings."""
    sp = _nearest(chain, "put", spot * (1.0 - width_pct))
    lp = _nearest(chain, "put", spot * (1.0 - 2 * width_pct))
    sc = _nearest(chain, "call", spot * (1.0 + width_pct))
    lc = _nearest(chain, "call", spot * (1.0 + 2 * width_pct))
    legs_o = [sp, lp, sc, lc]
    if any(o is None for o in legs_o):
        return None
    if len({o.strike for o in legs_o}) < 4:
        return None
    legs = [_leg_from_option(sp, "sell"), _leg_from_option(lp, "buy"),
            _leg_from_option(sc, "sell"), _leg_from_option(lc, "buy")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="iron_condor", underlying=sp.underlying, direction="neutral",
        legs=legs, contracts=contracts, net_premium_usd=net,
        max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)
