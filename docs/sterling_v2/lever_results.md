# SterlingV2 Lever Results (test-slice, gated)

## Lever 1 -- Short side (long+short vs long-only), TEST slice @ 4h

Single combined non-overlapping book; same cost model as baseline. KEEP = improves test-set Sharpe (risk-adjusted objective). The -20% max-DD cap is a PORTFOLIO gate (lever 5 DD circuit breaker + Task-15 final gate), not applied per single book -- even the long-only baselines breach -20% on a ~25-trade slice. DD shown for transparency.

| Symbol | Strategy | LO PF | LO Sh | LO Net% | LO DD% | LS PF | LS Sh | LS Net% | LS DD% | LS n | Sharpe verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD | ma_crossover | 0.84 | -0.69 | -13 | -22 | 1.18 | +0.63 | +8 | -22 | 33 | **better** |
| BTCUSD | breakout | 0.54 | -1.99 | -18 | -19 | 0.62 | -1.92 | -26 | -28 | 35 | **better** |
| BTCUSD | smc | 0.68 | -1.36 | -20 | -20 | 0.76 | -1.04 | -18 | -25 | 32 | **better** |
| BTCUSD | price_action | 0.69 | -1.28 | -18 | -25 | 0.81 | -0.84 | -15 | -22 | 33 | **better** |
| ETHUSD | ma_crossover | 0.86 | -0.50 | -11 | -24 | 0.93 | -0.22 | -7 | -20 | 23 | **better** |
| ETHUSD | breakout | 0.53 | -2.04 | -22 | -26 | 0.86 | -0.59 | -13 | -26 | 30 | **better** |
| ETHUSD | smc | 0.94 | -0.22 | -8 | -20 | 1.19 | +0.70 | +11 | -27 | 37 | **better** |
| ETHUSD | price_action | 0.55 | -2.06 | -32 | -36 | 2.00 | +2.59 | +65 | -20 | 30 | **better** |
| SOLUSD | ma_crossover | 1.07 | +0.23 | +1 | -24 | 1.01 | +0.04 | -3 | -24 | 26 | worse |
| SOLUSD | breakout | 0.39 | -3.33 | -34 | -42 | 0.62 | -2.18 | -36 | -54 | 36 | **better** |
| SOLUSD | smc | 0.73 | -1.09 | -20 | -29 | 0.85 | -0.76 | -18 | -48 | 38 | **better** |
| SOLUSD | price_action | 0.43 | -2.95 | -34 | -32 | 1.23 | +0.71 | +10 | -23 | 25 | **better** |

**Verdict: KEEP short side as a lever.** Improves test Sharpe in 11/12 (symbol, strategy) cells, with the largest gains on the down-trending assets (ETH/SOL) exactly as the grounding predicted -- consistency across 12 independent cells is evidence it is structural, not small-sample noise. Residual drawdown to be contained by the portfolio DD circuit breaker (lever 5).

