# SterlingV2 — Before / After (test slice, leak-free harness)

All numbers are on the **untouched test slice** (last 20% of each parquet), through the leak-free harness (next-bar fills, 0.10% fee, 5bps slippage, realized-frequency Sharpe). Baseline = long-only ma_crossover. V2 = long+short + vol-targeted sizing + correlation-aware portfolio with a hard -20% drawdown breaker. Same `research.run_v2_book` the live endpoint trades.

## Levers kept / rejected
- **Lever 1 short side — KEPT.** Improves test Sharpe in 11/12 cells; biggest gains on the down-trending ETH/SOL.
- **Lever 2 conviction gate — KEPT (long-only) / OFF for combined book.** Redundant with the short side; hurts the combined book on all 3 symbols.
- **Lever 3 trailing exit — REJECTED.** Improves Sharpe in only 3/12; trims winners; val-selected param generalizes poorly. Static SL/TP kept.
- **Lever 4 vol-targeted sizing — KEPT.** Improves test Sharpe in 10/12 at equal exposure.
- **Lever 5 correlation-aware portfolio + DD breaker — KEPT.** Caps portfolio drawdown.

## Per-symbol (test slice)

### Baseline (long-only ma_crossover)
| Symbol | Trades | Win% | PF | Sharpe | Net% | MaxDD% |
|---|---|---|---|---|---|---|
| BTCUSD | 34 | 32.4 | 0.84 | -0.69 | -12.7 | -22.0 |
| ETHUSD | 22 | 31.8 | 0.86 | -0.50 | -10.9 | -23.6 |
| SOLUSD | 25 | 40.0 | 1.07 | +0.23 | +0.5 | -24.3 |

### V2 stack (long+short + vol-sizing)
| Symbol | Trades | Win% | PF | Sharpe | Net% | MaxDD% |
|---|---|---|---|---|---|---|
| BTCUSD | 33 | 39.4 | 1.38 | +1.13 | +18.4 | -19.7 |
| ETHUSD | 23 | 34.8 | 1.09 | +0.24 | +0.5 | -18.9 |
| SOLUSD | 26 | 38.5 | 1.45 | +1.26 | +21.5 | -20.0 |

## Portfolio (combined, test slice)

| Portfolio | Net% | Sharpe | MaxDD% |
|---|---|---|---|
| Baseline (inverse-vol, no breaker) | -5.6 | -0.37 | -21.7 |
| **V2 (corr-weighted, -20% breaker)** | **+12.5** | **+1.12** | **-17.5** |

V2 portfolio weights: BTCUSD 37% · ETHUSD 30% · SOLUSD 32%.

## Robustness (combined V2 trade stream)

- Combined trades: **82**  (median hold 12 bars)
- **PBO** (prob. of backtest overfitting): **0.47**  (mean OOS path Sharpe +6.88, 15 CPCV paths)
- **Monte-Carlo p-loss** (bootstrap, 10k): **0.22**  (median path net +43.6%, p05 net -33.0%, p05 maxDD -52.0%)
- **Deflated Sharpe** (annualized Sh +1.12, n=82 trades): 5 trials → 0.30, 20 trials → 0.00, 144 trials → 0.00.  Probability the Sharpe survives multiple-testing (>0.5 = more likely than not). It clears >0 only at low trial counts and approaches 0 under aggressive correction — borderline, a direct consequence of the thin 82-trade OOS sample.

## Pre-registered gates (fixed before seeing the test set)

| Gate | Threshold | Observed | Status |
|---|---|---|---|
| Max drawdown | ≤ 20% | -17.5% | ✅ |
| OOS Sharpe | > 0 | +1.12 | ✅ |
| PBO | < 0.5 | 0.47 | ⚠️ |
| Monte-Carlo p-loss | ≤ 0.35 | 0.22 | ✅ |
| Deflated Sharpe (20 trials) | > 0 | 1.6e-08 | ⚠️ |
| Test trades | ≥ 100 | 82 | ❌ |

✅ clean · ⚠️ marginal (passes but near the threshold) · ❌ not met

**Overall: GATES NOT ALL MET.** Clean passes: max-drawdown (within the -20% cap), OOS Sharpe (+1.12), p-loss (0.22).

**Caveats / marginal gates.** PBO 0.47 sits just under the 0.50 ceiling, and the deflated Sharpe is positive only at low assumed trial counts (≈0 under aggressive multiple-testing). Both are marginal for the SAME reason as the one clear miss — the single-strategy ma_crossover test slice yields only ~82 combined trades, below the 100-trade floor. The economic before/after is strong and the drawdown is contained, but the statistical power on this thin OOS sample is limited.

**Disciplined remedy (next step, not a gate relaxation):** add the other validated edge strategies (breakout / smc) as additional per-symbol books. That ~3x's the trade count past 100, adds genuine diversification (lowering PBO and lifting DSR), and is preferable to borrowing validation data or loosening the pre-registered gates.

_Gate engine unmet list: trades 82 < 100._
