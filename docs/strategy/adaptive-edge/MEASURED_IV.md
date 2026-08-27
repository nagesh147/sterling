# The number that was missing — measured, 2026-08-27

Every offline conclusion in this engine's research turned on the
implied-to-realised volatility ratio, and none of them could measure it: no
store here holds option price history. With a live Kite session it took minutes.

Data: 25 NIFTY option contracts around the money, expiry 2026-09-01, minute bars
over four sessions, plus 1,500 spot bars. 738 paired observations.

## Real NIFTY ATM implied / realised

| | |
|---|---|
| p10 | 1.029 |
| p25 | 1.334 |
| **median** | **1.912** |
| p75 | 2.340 |
| p90 | 2.767 |
| mean | 1.876 |
| **above 1.0** | **91.1%** |

Mean implied 0.090 against mean realised 0.064. The variance risk premium is not
just present, it is large — implied runs about 1.9 times realised, and even the
cheapest decile sits above parity.

## What that does to each gate

**Long straddle** needs IV/RV below 0.856. Measured, it clears **7.6%** of the
time. The engine will decline roughly nineteen decisions in twenty, which is the
gate correctly refusing to buy movement that is already dearer than the tape
delivers.

**Short volatility** is where the measurement changes the design.

The strategy as studied filters on the forecast percentile — sell into the top
40% of expected movement. Against real prices those two conditions are strongly
anti-correlated, and mechanically so: the forecast scales with trailing realised
volatility, which is the denominator of the ratio.

| Subset | median IV/RV |
|---|---|
| forecast percentile ≥ 0.60 | **0.325** |
| forecast percentile < 0.60 | **1.967** |

So "sell into movement" selects the moments when premium is *cheapest* relative
to the tape, and "sell rich premium" selects quiet tape — which is exactly where
the earlier study showed selling loses. **The two filters the design depends on
are in tension, and only real prices could show it.**

## The actual trade, with actual prices

Sell the ATM straddle, buy it back thirty minutes later. No model, no assumed
volatility — entry and exit are quoted prices.

| Subset | n | mean (pts) | win | t |
|---|---|---|---|---|
| all observations | 658 | +0.07 | 0.629 | 0.43 |
| IV/RV above median | 329 | +0.09 | 0.629 | 0.46 |
| **IV/RV > 2.0 (richest premium)** | 288 | **−0.20** | 0.587 | −0.94 |
| forecast percentile ≥ 0.60 | 52 | +2.65 | 0.904 | 3.26 |

Selling the richest premium **loses**. The only positive subset is the one where
premium looks cheap.

### And that subset does not survive either

Those 658 round trips step every minute across a thirty-minute hold — thirty-fold
overlap. Non-overlapping:

| sampling | selected n |
|---|---|
| every minute | 52 |
| every 15 min | 3 |
| **non-overlapping** | **2** |

Two independent observations, across three sessions, one of which averaged
−19.27. The t-statistic of 3.26 is an artifact of counting the same trade thirty
times.

## The conclusion

Nothing here establishes a tradeable edge, and the evidence gate is refusing for
exactly the right reason: it wants 400 observations across 20 sessions, and four
sessions of data yields about two independent ones.

What *is* established, and is worth having:

* **NIFTY ATM implied runs ~1.9x realised**, above parity 91% of the time. That
  is a measured fact about this market, not an assumption.
* **The long gate clears 7.6% of the time** — a real number, not a sweep.
* **The design's two filters conflict**, which no amount of offline work could
  have shown.

Four sessions is a beginning. The engine now records this every scan.
