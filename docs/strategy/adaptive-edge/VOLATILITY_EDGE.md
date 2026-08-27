# The edge, and what it is not — 2026-08-27

Measured on 50,244 real NIFTY-I one-minute bars, 2026-02-02 to 2026-08-18, 134
sessions, plus 53,884 tick quotes over 9 of them. Every number below is
out-of-sample unless it says otherwise.

## Direction does not work

Tested at 30, 60 and 120-bar horizons, entering at the **next bar's open**
because the signal is computed from a bar's close and you cannot fill there.
Explore = first 60% of the series, confirm = last 40%, never fitted on.

| Signal | Hold | Explore hit | Confirm hit | Confirm bps |
|---|---|---|---|---|
| fade 30-bar move | 30 | 0.5007 | 0.5136 | +0.115 |
| fade 60-bar move | 30 | 0.4912 | 0.5151 | +0.321 |
| momentum 60-bar | 30 | 0.5042 | 0.4784 | −0.321 |
| fade sma100 deviation | 30 | 0.4862 | 0.5113 | +0.103 |
| opening-range breakout | 30 | 0.4949 | 0.4942 | −0.792 |
| opening-range breakout | 120 | 0.5505 | 0.5358 | **−1.785** |

Nothing holds. The breakout row at 120 bars is worth keeping in mind: a 53.6%
hit rate with a negative expectancy, because the losers are far larger than the
winners. Hit rate on its own says nothing.

### The one that looked real

Fading an outsized one-minute move in quiet tape looked strong — 58.3% hit,
+0.572 bps, and **all five walk-forward blocks positive**. Then entry moved from
the signal bar's close to the next bar's open:

| Entry | Hit | Mean |
|---|---|---|
| signal bar close (lookahead) | 0.5801 | +0.545 bps |
| next bar open (realistic) | 0.5207 | **+0.141 bps** |

Three quarters of the edge happens before anyone can act. At 0.14 bps — about
0.35 NIFTY points, roughly 0.17 on an at-the-money option — the spread alone
eats it. The effect is real and it is not tradeable on one-minute bars.

### Tick data does not rescue it

Quote imbalance does predict the next few ticks (rank correlation +0.067 at 3
ticks, top-quintile +0.188 bps against bottom-quintile −0.219). But the recorded
futures spread has a median of 3.80 points — 1.5 bps, nearly four times the
entire quintile spread — and `ltp` sits inside the quoted band only 89.6% of the
time. These are two-second snapshots, not a book. The signal may be real; this
data cannot show it is executable.

## Magnitude does work

How far the tape travels is predictable, and by enough to matter.

Forecast = `4.6775 x realised_vol`, one predictor, fitted on the prior block only.

| Block | k | OOS rank corr | Top decile | Bottom decile | Ratio |
|---|---|---|---|---|---|
| 1 | 4.837 | +0.3509 | 34.93 | 19.28 | 1.81 |
| 2 | 5.055 | +0.2854 | 27.36 | 14.97 | 1.83 |
| 3 | 4.774 | +0.2123 | 23.10 | 16.97 | 1.36 |
| 4 | 4.805 | +0.3223 | 20.82 | 10.19 | 2.04 |
| 5 | 4.352 | +0.2822 | 14.23 | 8.91 | 1.60 |

**Mean out-of-sample rank correlation +0.2906**, every block positive, `k` stable
between 4.35 and 5.06. The top forecast decile travels about 1.7 times as far as
the bottom.

A three-predictor least-squares fit on realised volatility, range and relative
volume scored **worse** (+0.2275) and gave realised volatility a negative
coefficient, because range and realised volatility measure the same thing and
the fit split them between the two. One interpretable term beat it, and that is
what ships.

`k = 4.68` sits below `sqrt(30) = 5.477`, the random-walk value. That gap is the
damping a mean-reverting tape produces, and it is why the multiple is measured
rather than assumed.

## What the strategy therefore is

Long gamma, no direction.

```text
realised volatility  ->  forecast excursion over the horizon
quoted ATM straddle  ->  breakeven move, including round-trip costs
trade only when      forecast > breakeven x margin
```

An option buyer needs the underlying to travel further than the premium already
charges for. The forecast is measured offline; the premium is quoted now. **The
edge is decided live**, which is why nothing in `volatility_forecast.py` carries
a hardcoded implied volatility — a fitted IV would be answering with history a
question that is about the current quote.

The margin defaults to 1.25. It is a judgement, not a fitted value: the forecast
ranks at 0.29, not 1.0, so trading at exactly breakeven means trading a coin
flip on an estimate.

## Limits worth stating

* One instrument, one regime, 6.5 months. NIFTY between February and August 2026.
* The excursion multiple is measured at a 30-bar horizon. Other horizons are
  extrapolated by `sqrt(t)` and have not been re-measured.
* **Realised versus implied has not been tested.** There is no option price
  history in this dataset, so whether the straddle is systematically cheap
  enough is unknown. The gate makes the comparison correctly; whether it clears
  often enough to be a business is an open question that live paper sessions
  answer.
* The forecast predicts *maximum excursion within* the horizon, not the move at
  the end of it. That is what a target captures, and it is what the multiple was
  fitted against — using it as an end-of-horizon estimate would overstate it.

---

# Cross-validation and the paper run — 2026-08-27

## The forecaster holds across 120 instruments

Re-run against the offline lake on the pendrive (`SterlingLake`, 12,250 parquet
files, 1.9 GB) — 130 NSE indices and 4,354 cash names, minute bars, Feb to Aug
2026. 120 instruments sampled at random, **none of them fitted on**.

| | |
|---|---|
| Positive rank correlation | **119 / 120 (99.2%)** |
| Mean / median rank corr | +0.343 / +0.365 |
| Per-instrument multiple | 2.96 – 5.03 (p10–p90), NIFTY's 4.68 inside |
| Top/bottom decile ratio | **2.22x** median |

The single negative is an illiquid SME with 267 observations. The median rank
correlation is *higher* than the NIFTY-only figure it was fitted from, which is
the opposite of what an overfitted signal does out of sample.

The multiple varies enough by instrument to be worth measuring per name;
`forecast(..., multiple=)` takes one.

## The paper run, and what it found

The gate was run over 8,772 decision points on NIFTY 50. The result is a step
function — the gate clears 100% of the time below a threshold and 0% above it —
and the reason is worth stating, because it turns the whole strategy into one
number.

The forecast is `multiple * realised_vol`. An at-the-money straddle costs about
`0.7979 * implied_vol * sqrt(horizon)`. Both sides scale with volatility, so
realised volatility cancels:

```text
clears  <=>  multiple  >  0.7979 * sqrt(horizon) * margin * (IV / RV)
```

| Margin | Gate refuses above IV/RV |
|---|---|
| 1.00 | 1.070 |
| **1.25** | **0.856** |
| 1.50 | 0.714 |

**A long straddle needs implied volatility below realised.** Index options
normally carry the opposite — the variance risk premium — so at the shipped
margin this gate will refuse most of the time.

That is the gate working. Buying volatility that is already dearer than the tape
delivers is a structurally losing trade, and an engine that declines it is doing
its job. The 100%-clearing rows in the sweep sit at IV/RV of 0.7 and 0.8, and in
those the forecast beat realised movement 84% and 77% of the time — so when
options *are* that cheap the trade is good. They are rarely that cheap.

## What this means to run

* Run it. It will decline most sessions, and the reason it gives is now the
  volatility ratio rather than two rupee figures, so "declining" is legible.
* The regimes to watch for are the ones where implied collapses below realised:
  after an event passes, or into a post-shock volatility crush.
* **The obvious inversion is deliberately not implemented.** If IV exceeds RV
  systematically, the profitable side is selling volatility — and that carries
  unbounded risk on a strategy whose directional model has no edge to hedge
  with. That is a different product and a different risk conversation, not a
  sign flip.

## Still not answered

Whether NIFTY options actually trade below 0.856 IV/RV often enough to be a
business. That needs an option price history, and neither the local stores nor
the pendrive lake has one — the lake holds index and cash-equity bars only. Live
paper sessions record it, which is what the observation recorder is for.
