"""Sell volatility when the tape is already moving — defined risk only.

The long side does not work. A long straddle needs implied below realised, and
index options carry the variance risk premium the other way, so that gate
refuses almost always (see VOLATILITY_EDGE.md). The short side is where the
premium is. This module is that side, and it is deliberately narrow about how.

**Three findings shape it, and two of them invert the usual intuition.**

*Sell into movement, not into calm.* Sorting decisions by forecast volatility
and selling only the top 40% roughly doubles the expectancy against selling
everything (+13.8 bps against +6.0), while selling only the quietest 40% earns
+0.18 bps — nothing. The reason is that the collected premium scales with
volatility but the tail barely does: measured by forecast quintile, a 1-in-100
move costs 7.1 times the premium in the quietest quintile and 1.8 times in the
most active. Selling into calm is *more* dangerous per rupee earned, which is
the opposite of how it is usually described.

*The forecaster predicts the body, not the tail.* Median forward excursion rises
2.4x from the lowest forecast quintile to the highest; the maximum does not move
at all, and the single largest excursion in the sample came from the quietest
quintile. So the forecast may size the premium. It may never be used to argue
that a tail will not arrive.

*Which is why nothing here sells naked.* A 6% intraday move costs a naked seller
18.8 times the credit and a 13% move costs 42 times — and a stop does not help,
because a gap opens through it. Wings at 1.5 standard deviations keep 89% of the
expectancy and cap that same 6% move at 1.0 times the credit. Every structure
this module produces is defined-risk. There is no flag to turn that off.

Evidence, all of it out of sample: non-overlapping t-statistic 10.9, a
session-block bootstrap over 118 sessions giving a 95% interval of [+12.0,
+16.0] bps with none of 2000 draws below zero, and 37 of 37 NSE indices
profitable on the same rule.

**What is assumed and not measured:** the implied-to-realised ratio. There is no
option price history in any store here, so the expectancy above assumes the
market charges 1.2x realised. If the real premium is thinner the edge scales
down with it. The engine computes the ratio from live quotes at decision time,
so this assumption never reaches a trading decision — it only sizes the research.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .volatility_forecast import VolatilityForecast, forecast

#: Sell only when the forecast sits in the top of its own distribution. Below
#: this the premium does not cover the tail: measured tail-to-premium is 7.1x in
#: the quietest quintile against 1.8x in the most active.
MIN_FORECAST_PERCENTILE = 0.60

#: Wing distance in standard deviations of the terminal move. 1.5 keeps 89% of
#: the naked expectancy and caps a 6% shock at one credit instead of 18.8.
WING_DISTANCE_SD = 1.5

#: Black-Scholes at the money: a straddle is worth about this times sigma*sqrt(T)*S.
ATM_STRADDLE_COEFFICIENT = 0.7979


class VolatilityHarvestError(ValueError):
    pass


def _phi(x: float) -> float:
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def strangle_value(sd_bps: float, wing_bps: float) -> float:
    """What the protective wings cost, in basis points.

    Under a normal terminal distribution, a call struck `wing_bps` away is worth
    `sd*phi(w) - wing*(1-Phi(w))`. Both wings together is twice that. This is
    what an earlier version of the study left out, and leaving it out made a
    defined-risk structure look like it could never lose — which is impossible
    and was the tell.
    """
    if sd_bps <= 0:
        return 0.0
    w = wing_bps / sd_bps
    return 2.0 * (sd_bps * _phi(w) - wing_bps * (1.0 - _cdf(w)))


@dataclass(frozen=True)
class HarvestStructure:
    """A defined-risk short-volatility position, priced in basis points of spot.

    `max_loss_bps` is finite by construction. If it ever is not, the structure is
    not one this module produced.
    """

    net_credit_bps: float
    wing_bps: float
    max_loss_bps: float
    breakeven_bps: float
    forecast_bps: float
    realised_vol_bps: float
    forecast_percentile: float
    eligible: bool
    reason: str

    @property
    def credit_to_risk(self) -> float:
        return self.net_credit_bps / self.max_loss_bps if self.max_loss_bps > 0 else 0.0

    @property
    def shock_loss_multiple(self) -> float:
        """How many credits the worst case costs. Bounded, by construction."""
        return self.max_loss_bps / self.net_credit_bps if self.net_credit_bps > 0 else 0.0


def evaluate(
    closes: Sequence[float],
    *,
    implied_vol_ratio: float,
    horizon_bars: int = 30,
    wing_sd: float = WING_DISTANCE_SD,
    min_percentile: float = MIN_FORECAST_PERCENTILE,
    multiple: float | None = None,
) -> HarvestStructure | None:
    """Price a defined-risk short-volatility structure, or decline.

    `implied_vol_ratio` is implied divided by realised, taken from live quotes.
    It is required rather than defaulted: the entire expectancy is proportional
    to it, and a default would let a research assumption reach a trade.

    Returns None when there is not enough history to forecast — that is the
    engine unable to ask, which is different from declining.
    """
    if implied_vol_ratio <= 0:
        raise VolatilityHarvestError("implied_vol_ratio must be positive and measured from live quotes")
    if wing_sd <= 0:
        raise VolatilityHarvestError("wing distance must be positive — this module does not sell naked")

    view: VolatilityForecast | None = (
        forecast(closes, horizon_bars=horizon_bars, multiple=multiple)
        if multiple is not None
        else forecast(closes, horizon_bars=horizon_bars)
    )
    if view is None:
        return None

    # Standard deviation of the terminal move the market is charging for.
    sd_bps = implied_vol_ratio * view.realised_vol_bps * math.sqrt(max(1, horizon_bars))
    if sd_bps <= 0:
        return None

    gross_credit = ATM_STRADDLE_COEFFICIENT * sd_bps
    wing_bps = wing_sd * sd_bps
    net_credit = gross_credit - strangle_value(sd_bps, wing_bps)
    max_loss = wing_bps - net_credit

    if net_credit <= 0 or max_loss <= 0:
        return HarvestStructure(
            net_credit, wing_bps, max(max_loss, 0.0), net_credit,
            view.excursion_bps, view.realised_vol_bps, view.percentile,
            False, "wings cost more than the body collects at this width")

    structure = HarvestStructure(
        net_credit_bps=net_credit,
        wing_bps=wing_bps,
        max_loss_bps=max_loss,
        breakeven_bps=net_credit,
        forecast_bps=view.excursion_bps,
        realised_vol_bps=view.realised_vol_bps,
        forecast_percentile=view.percentile,
        eligible=False,
        reason="",
    )

    if view.percentile < min_percentile:
        return _with(structure, False,
                     f"forecast in the {view.percentile:.0%} percentile, below the "
                     f"{min_percentile:.0%} floor — the premium does not cover the tail "
                     f"in quiet tape")
    return _with(structure, True,
                 f"selling into the {view.percentile:.0%} percentile of forecast movement, "
                 f"risk capped at {max_loss:.1f}bps for {net_credit:.1f}bps of credit")


def _with(s: HarvestStructure, eligible: bool, reason: str) -> HarvestStructure:
    return HarvestStructure(
        s.net_credit_bps, s.wing_bps, s.max_loss_bps, s.breakeven_bps,
        s.forecast_bps, s.realised_vol_bps, s.forecast_percentile, eligible, reason)
