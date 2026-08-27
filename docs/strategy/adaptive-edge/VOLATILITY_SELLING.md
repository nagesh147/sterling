# Selling volatility — the study, artifact by artifact

Long volatility does not work here: a long straddle needs implied below
realised, and index options carry the variance risk premium the other way
(`VOLATILITY_EDGE.md`). This is the short side, examined properly.

Data: the pendrive lake, NIFTY 50 minute bars, 2026-02-13 to 2026-08-13, 122
sessions, plus 37 NSE indices for cross-checks. Every figure out of sample.

---

## Artifact 1 — the tail

A seller's entire risk lives here.

| Horizon | n | median | p90 | p99 | max | p99/median |
|---|---|---|---|---|---|---|
| 30-minute | 1,464 | 16.0 | 35.9 | 65.0 | 117.0 | 4.1x |
| 75-minute | 610 | 27.6 | 57.1 | 100.6 | 140.1 | 3.6x |
| full session | 122 | 68.7 | 135.3 | 200.8 | 246.7 | 2.9x |

All in basis points.

## Artifact 2 — the forecaster predicts the body, not the tail

Forward 30-minute excursion by quintile of prior realised volatility:

| Quintile | median | p95 | p99 | **max** |
|---|---|---|---|---|
| 1 (quietest) | 9.8 | 26.7 | 56.2 | **130.2** |
| 5 (most active) | 23.5 | 54.8 | 75.1 | **122.6** |

The median rises 2.4x across quintiles. The maximum does not move — and the
single largest excursion in the sample came from the *quietest* quintile.

**The forecast may size the premium. It may never be used to argue that a tail
will not arrive.** That is the discipline the rest of this rests on.

## Artifacts 3 and 4 — the inversion

Premium collected against tail faced, by forecast quintile, at IV/RV 1.2:

| Quintile | premium | median move | p99 move | **tail/premium** | **mean P&L** |
|---|---|---|---|---|---|
| 1 (quietest) | 7.9 | 6.1 | 56.2 | **7.11x** | **−0.83** |
| 2 | 11.0 | 7.4 | 51.2 | 4.64x | +1.18 |
| 3 | 14.1 | 9.6 | 52.0 | 3.68x | +1.90 |
| 4 | 18.6 | 11.4 | 68.5 | 3.68x | +3.80 |
| 5 (most active) | 41.6 | 14.9 | 75.1 | **1.80x** | **+23.50** |

**Selling into calm loses money and carries the worst tail ratio.** Premium
scales with volatility; the tail barely does. This is the opposite of how
volatility selling is usually described, and it is the single most useful thing
in this study.

## Artifact 5 — the window is benign

| | |
|---|---|
| worst intraday range in sample | **2.63%** (2026-04-02) |
| NIFTY, 4 Jun 2024 | ~6% |
| NIFTY, Mar 2020 | ~13% |

There is no shock in this data. **Every tail number above is a lower bound.**

## Artifact 6 — conditioning on the forecast

Non-overlapping, IV/RV 1.2:

| Rule | mean | win | worst |
|---|---|---|---|
| sell everything | +5.97 | 0.697 | −122.2 |
| **sell top-40% forecast vol** | **+13.80** | 0.772 | −97.7 |
| sell bottom-40% (the naive way) | +0.18 | 0.635 | −122.2 |

Conditioning more than doubles the expectancy and improves the worst case. The
naive version earns nothing.

## Artifact 7 — significance, honestly

| | |
|---|---|
| overlapping (5-bar step) t-statistic | 26.9 — **inflated** |
| non-overlapping (30-bar step) | **10.9** |
| session block bootstrap, 118 sessions | mean +14.03, 95% CI [+12.05, +16.01] |
| bootstrap draws at or below zero | **0 / 2000** |

A 5-bar step over a 30-bar horizon reuses each move six times. The corrected
figure is the one that counts.

## Artifact 8 — what a shock costs a naked seller

Credit ~30 bps on a 30-minute straddle at IV/RV 1.2:

| Event | loss | multiple of credit |
|---|---|---|
| worst in sample (2.63%) | 233 bps | 7.7x |
| 4 Jun 2024 (~6%) | 570 bps | **18.8x** |
| Mar 2020 (~13%) | 1,270 bps | **42.0x** |

One 6% day erases 41 winning trades. A stop does not save you: a gap opens
through it.

## Artifact 9 — defined risk

Iron condor, wings at a multiple of the terminal standard deviation. Net credit
is the straddle *minus what the wings cost* — omitting that made an earlier run
show a structure that could never lose, which is impossible and was the tell.

| Structure | credit | max loss | mean | win | worst | 6% shock | t |
|---|---|---|---|---|---|---|---|
| naked straddle | 30.2 | unbounded | +14.05 | 0.757 | −95.9 | 18.8x | 10.9 |
| condor, wings 1.0 sd | 23.9 | 14.0 | +9.64 | 0.680 | −17.0 | 0.6x | 9.9 |
| **condor, wings 1.5 sd** | **28.0** | **28.8** | **+12.54** | 0.740 | −31.5 | **1.0x** | 10.8 |
| condor, wings 2.0 sd | 29.6 | 46.2 | +13.74 | 0.756 | −43.2 | 1.6x | 11.1 |

**1.5 sd keeps 89% of the expectancy and turns an unbounded 18.8x shock into a
capped 1.0x.** That is the shipped default, and `volatility_harvest.py` has no
path to a naked position — `wing_sd <= 0` raises.

## Artifact 10 — it is not a NIFTY artifact

Same rule across 37 NSE indices: **37 of 37 profitable**, median +13.20 bps,
median win rate 0.733.

---

## What is assumed, and what that means

**The implied-to-realised ratio.** There is no option price history in any store
here — not the local SQLite, not the pendrive lake, which holds index and cash
bars only. Every expectancy above assumes the market charges 1.2x realised. If
the real premium is thinner the edge scales down proportionally; at 0.9x the
naked mean falls from +14.0 to +1.3.

The engine does not inherit that assumption. `evaluate()` **requires**
`implied_vol_ratio` with no default, computed from live quotes at decision time,
so the research number can never reach a trade.

**And the window has no shock.** The defined-risk structure is what makes this
shippable in spite of that: the cap holds whatever the move, which is precisely
the property a benign sample cannot verify and a bounded payoff does not need to.
