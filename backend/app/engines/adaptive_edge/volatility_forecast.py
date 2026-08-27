"""F-104: forecast how far the underlying will move, not which way.

This is the signal the engine trades on, and it exists because the directional
one does not work. Measured on 50,244 real NIFTY one-minute bars, February to
August 2026:

* **Direction is not tradeable.** Momentum, mean reversion, SMA deviation and
  opening-range breakout were all tested at 30, 60 and 120-bar horizons with
  next-bar-open fills. Nothing held from the explore half to the confirm half.
  The one signal that looked real — fading an outsized one-minute move in quiet
  tape, 58% hit — collapsed to 52% and +0.14 bps once entry moved from the
  signal bar's close to the next bar's open. Three quarters of it happened
  before anyone could act.
* **Magnitude is predictable, and by a lot.** Forecast excursion ranks against
  realised excursion with an out-of-sample rank correlation of +0.29 across five
  walk-forward blocks, every one positive. The top forecast decile moves roughly
  1.7 times as far as the bottom.

For an option buyer that is the useful half. A long option profits from
movement; being right about the direction of a coin flip is not a strategy, and
knowing when the tape is about to travel is.

The forecast is deliberately one predictor. A three-predictor least-squares fit
on realised volatility, range and relative volume scored *worse* out of sample
(+0.2275) and gave realised volatility a negative coefficient, because range and
realised volatility measure the same thing and the fit split them. One
interpretable term beat it.

Full working: docs/strategy/adaptive-edge/VOLATILITY_EDGE.md
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

#: Excursion per unit of realised volatility over a 30-bar horizon, the median
#: ratio across 48,174 observations. A pure random walk would give sqrt(30) =
#: 5.477; the measured 4.68 is below that, which is the damping a mean-reverting
#: tape produces and is the reason this is fitted rather than assumed.
EXCURSION_MULTIPLE = 4.6775

#: The horizon the multiple was measured over. Changing one without re-measuring
#: the other silently rescales every forecast.
HORIZON_BARS = 30

#: Bars of history the realised-volatility estimate needs. Below this the
#: estimate is noise and the forecast inherits it.
MIN_HISTORY_BARS = 30

#: Measured on the fitted window, for turning a forecast into a percentile
#: without recomputing the distribution live.
FORECAST_DECILES_BPS = (8.4, 11.0, 13.2, 15.4, 17.7, 20.4, 23.8, 28.5, 36.6)


@dataclass(frozen=True)
class VolatilityForecast:
    """Expected maximum excursion over the horizon, in basis points of spot.

    `excursion_bps` is the *maximum* absolute move expected within the horizon,
    not the move at the end of it. That is deliberate: it is what a target
    captures and what a long option needs in order to pay, and it is what the
    multiple above was fitted against.
    """

    excursion_bps: float
    realised_vol_bps: float
    horizon_bars: int
    bars_used: int
    percentile: float

    @property
    def is_quiet(self) -> bool:
        return self.percentile <= 0.30

    @property
    def is_active(self) -> bool:
        return self.percentile >= 0.70


def realised_vol_bps(closes: Sequence[float], bars: int = MIN_HISTORY_BARS) -> float | None:
    """Standard deviation of one-bar returns, in basis points.

    Returns None rather than zero when there is not enough history. Zero is a
    real reading — a tape that did not move — and collapsing "no data" into it
    would make the forecast say "nothing will happen" when it means "I cannot
    tell".
    """
    window = [c for c in closes[-(bars + 1):] if c and c > 0]
    if len(window) < bars:
        return None
    returns = [(window[i] / window[i - 1] - 1.0) for i in range(1, len(window))]
    if len(returns) < 2:
        return None
    return statistics.pstdev(returns) * 10_000.0


def _percentile(value: float) -> float:
    for index, edge in enumerate(FORECAST_DECILES_BPS):
        if value < edge:
            return (index + 1) / 10.0
    return 1.0


def forecast(closes: Sequence[float], *, horizon_bars: int = HORIZON_BARS) -> VolatilityForecast | None:
    """Forecast the maximum excursion over `horizon_bars`.

    Scaled by sqrt(horizon / fitted horizon) when asked for a different window,
    because excursion grows with the square root of time. That is an
    extrapolation away from the measured point, so a caller who cares about
    accuracy at another horizon should re-measure the multiple there rather than
    trust this to hold far from 30 bars.
    """
    vol = realised_vol_bps(closes)
    if vol is None:
        return None
    scale = math.sqrt(max(1, horizon_bars) / HORIZON_BARS)
    excursion = EXCURSION_MULTIPLE * vol * scale
    return VolatilityForecast(
        excursion_bps=excursion,
        realised_vol_bps=vol,
        horizon_bars=horizon_bars,
        bars_used=min(len(closes), MIN_HISTORY_BARS + 1),
        percentile=_percentile(excursion),
    )


@dataclass(frozen=True)
class StraddleGate:
    """Whether a long straddle is worth buying at the quoted price.

    The whole strategy in one comparison: an option buyer needs the underlying
    to travel further than the premium already charges for. `breakeven_bps` is
    what the market is asking; `forecast_bps` is what the tape is expected to
    deliver.

    This is where the edge either exists or does not, and it can only be decided
    live — the forecast is measured offline, the premium is quoted now. No
    amount of historical fitting settles it, which is why nothing here carries a
    hardcoded implied volatility.
    """

    forecast_bps: float
    breakeven_bps: float
    margin: float
    eligible: bool
    reason: str

    @property
    def edge_ratio(self) -> float:
        return self.forecast_bps / self.breakeven_bps if self.breakeven_bps > 0 else 0.0


def evaluate_straddle(
    *,
    forecast_bps: float,
    call_premium: float,
    put_premium: float,
    spot: float,
    round_trip_cost_pct: float = 1.0,
    margin: float = 1.25,
) -> StraddleGate:
    """Compare the forecast move against what the straddle costs.

    `margin` is the multiple of breakeven the forecast must clear. It is a
    safety factor, not a fitted parameter: the forecast has a rank correlation
    of 0.29, not 1.0, so trading at exactly breakeven means trading a coin flip
    on an estimate. 1.25 is a judgement and is exposed so it can be argued with.

    Costs are added to the premium rather than netted afterwards, because the
    spread is paid on the way in and the way out and a breakeven that ignores it
    is not a breakeven.
    """
    if spot <= 0:
        return StraddleGate(forecast_bps, 0.0, margin, False, "no spot price")
    if call_premium <= 0 or put_premium <= 0:
        return StraddleGate(forecast_bps, 0.0, margin, False, "straddle not priced")

    premium = call_premium + put_premium
    with_costs = premium * (1.0 + max(0.0, round_trip_cost_pct) / 100.0)
    breakeven_bps = (with_costs / spot) * 10_000.0

    if forecast_bps <= 0:
        return StraddleGate(forecast_bps, breakeven_bps, margin, False, "no forecast")
    if forecast_bps < breakeven_bps * margin:
        return StraddleGate(
            forecast_bps, breakeven_bps, margin, False,
            f"forecast {forecast_bps:.1f}bps below {margin:.2f}x breakeven "
            f"{breakeven_bps:.1f}bps — the premium already prices more movement than expected")
    return StraddleGate(forecast_bps, breakeven_bps, margin, True, "forecast clears breakeven")
