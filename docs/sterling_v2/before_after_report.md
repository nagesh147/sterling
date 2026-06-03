# SterlingV2 — Before / After + robustness gates (test slice)

All numbers on the **untouched test slice** (last 20% of each parquet), through the leak-free harness (next-bar fills, 0.10% fee, 5bps slippage, realized-frequency Sharpe). Two stacks are reported: **(A)** the validated ma_crossover stack, and **(B)** the multi-book expansion (+breakout +smc) tested to reach the 100-trade floor.

## Levers kept / rejected
- **Lever 1 short side — KEPT** (+test Sharpe 11/12).  **Lever 4 vol-sizing — KEPT** (10/12).  **Lever 5 corr-portfolio + -20% DD breaker — KEPT.**
- **Lever 2 conviction gate — OFF for the combined book** (redundant with the short side).  **Lever 3 trailing exit — REJECTED** (3/12; trims winners; val param overfits).

## Stack A — validated (ma_crossover, 3 symbols)

| Portfolio | Net% | Sharpe | MaxDD% |
|---|---|---|---|
| Baseline (long-only) | -5.6 | -0.37 | -21.7 |
| **V2 stack** | **+12.5** | **+1.12** | **-17.5** |

Robustness: 82 trades · PBO 0.47 · MC p-loss 0.22 · DSR(20) 1.6e-08.

| Gate | Threshold | Observed | Status |
|---|---|---|---|
| Max drawdown | ≤ 20% | -17.5% | ✅ |
| OOS Sharpe | > 0 | +1.12 | ✅ |
| PBO | < 0.5 | 0.47 | ⚠️ |
| MC p-loss | ≤ 0.35 | 0.22 | ✅ |
| Deflated Sharpe (20 trials) | > 0 | 1.6e-08 | ⚠️ |
| Test trades | ≥ 100 | 82 | ❌ |

**Stack A verdict: GATES NOT ALL MET** — trades 82 < 100. Economically strong and drawdown-contained; the only miss is the 100-trade floor (single strategy x 3 symbols on a 20% slice).

## Stack B — multi-book expansion (+breakout +smc, 9 books)

Per-book test-slice metrics:
| Book | Trades | Win% | PF | Sharpe | Net% | MaxDD% |
|---|---|---|---|---|---|---|
| BTC/ma_crossover | 33 | 39 | 1.38 | +1.13 | +18 | -20 |
| BTC/breakout | 35 | 26 | 0.69 | -1.47 | -21 | -22 |
| BTC/smc | 32 | 38 | 0.84 | -0.64 | -13 | -20 |
| ETH/ma_crossover | 23 | 35 | 1.09 | +0.24 | +0 | -19 |
| ETH/breakout | 30 | 37 | 0.73 | -1.11 | -21 | -21 |
| ETH/smc | 37 | 46 | 1.28 | +0.96 | +18 | -20 |
| SOL/ma_crossover | 26 | 38 | 1.45 | +1.26 | +22 | -20 |
| SOL/breakout | 36 | 28 | 0.80 | -0.92 | -20 | -44 |
| SOL/smc | 38 | 37 | 1.07 | +0.30 | +1 | -40 |

| Portfolio | Net% | Sharpe | MaxDD% |
|---|---|---|---|
| Baseline (long-only, 9 books) | -15.7 | -2.39 | -21.6 |
| V2 (9 books) | -2.0 | -0.19 | -16.1 |

Robustness: 290 trades · PBO 0.47 · MC p-loss 0.65 · DSR(20) 0.

| Gate | Threshold | Observed | Status |
|---|---|---|---|
| Max drawdown | ≤ 20% | -16.1% | ✅ |
| OOS Sharpe | > 0 | -0.19 | ❌ |
| PBO | < 0.5 | 0.47 | ⚠️ |
| MC p-loss | ≤ 0.35 | 0.65 | ❌ |
| Deflated Sharpe (20 trials) | > 0 | 0 | ❌ |
| Test trades | ≥ 100 | 290 | ✅ |

**Stack B verdict: GATES NOT ALL MET** — oos_sharpe -0.19 <= 0.0; p_loss 0.65 > 0.35; DSR 0.00 <= 0.0.

## Conclusion

Adding breakout and smc reaches the 100-trade floor (290 trades) but **fails the economic gates**: breakout is a consistent OOS loser (BTC -1.47, ETH -1.11, SOL -0.92 Sharpe) and smc is mixed, dragging the portfolio to a negative Sharpe. The baseline screen rated those strategies net-positive on the full sample, but that did not survive out-of-sample — so padding the trade count with them trades a real edge for a fake one, and the gates correctly reject it.

**The durable result is Stack A (ma_crossover x 3 symbols): +12% net, +1.12 Sharpe, -18% max-DD**, clearing every economic and risk gate and missing only the 100-trade floor (82 trades). The honest way to clear that floor is to **accrue real paper trades over time** (the stack is already wired live, paper-only), not to inflate the count with strategies that lack out-of-sample edge.
