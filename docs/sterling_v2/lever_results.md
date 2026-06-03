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

## Lever 2 -- Conviction/regime gate (gated vs ungated long-only), TEST slice @ 4h

adx_min selected on the VALIDATION slice (never the test set); EMA(50)-slope + ADX(14) gate, side=1. KEEP = improves test Sharpe. Gating thins the ~25-trade test slice substantially, so per-cell verdicts are indicative; the decisive test is the full combined stack (>=100 trades) in Task 15.

| Symbol | Strategy | adx* | Ungated Sh | Ungated PF | Ungated n | Gated Sh | Gated PF | Gated Net% | Gated DD% | Gated n | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD | ma_crossover | 18 | -0.69 | 0.84 | 34 | +0.51 | 1.14 | +5 | -12 | 29 | **KEEP** |
| BTCUSD | breakout | 22 | -1.99 | 0.54 | 20 | -1.86 | 0.46 | -11 | -13 | 9 | **KEEP** |
| BTCUSD | smc | 0 | -1.36 | 0.68 | 29 | -0.95 | 0.74 | -9 | -17 | 17 | **KEEP** |
| BTCUSD | price_action | 15 | -1.28 | 0.69 | 25 | +0.69 | 1.26 | +5 | -10 | 14 | **KEEP** |
| ETHUSD | ma_crossover | 25 | -0.50 | 0.86 | 22 | -1.02 | 0.71 | -12 | -17 | 15 | reject |
| ETHUSD | breakout | 22 | -2.04 | 0.53 | 20 | +0.02 | 1.01 | -0 | -7 | 6 | **KEEP** |
| ETHUSD | smc | 25 | -0.22 | 0.94 | 26 | +3.15 | 4.52 | +18 | -5 | 5 | **KEEP** |
| ETHUSD | price_action | 15 | -2.06 | 0.55 | 24 | -2.90 | 0.33 | -21 | -24 | 11 | reject |
| SOLUSD | ma_crossover | 22 | +0.23 | 1.07 | 25 | -2.28 | 0.51 | -28 | -31 | 19 | reject |
| SOLUSD | breakout | 22 | -3.33 | 0.39 | 22 | -2.56 | 0.36 | -18 | -23 | 9 | **KEEP** |
| SOLUSD | smc | 22 | -1.09 | 0.73 | 24 | -3.87 | 0.25 | -25 | -30 | 11 | reject |
| SOLUSD | price_action | 22 | -2.95 | 0.43 | 24 | -1.78 | 0.46 | -14 | -14 | 8 | **KEEP** |

**Verdict:** gate improves test Sharpe in 8/12 cells overall, but 7/12 cells fell below 12 test trades after gating -- too thin to trust (e.g. ETH smc n=5 Sharpe +3.15 is noise). Among the 5 adequately-sampled cells (>= 12 trades), the gate helps 3: it lifts the BTC long book (ma_crossover -0.69->+0.51 n29, smc -1.36->-0.95 n17, price_action -1.28->+0.69 n14) -- consistent with the grounding's BTC-only long edge -- but does NOT rescue ETH/SOL long (those are fixed by the SHORT side, lever 1, not a long gate). **Provisional KEEP for the long side (esp. BTC); firm decision on the combined stack (>=100 trades) in Task 15.**

