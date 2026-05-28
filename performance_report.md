# Scalping Engine Performance Report: Before & After Polishes
Evaluated over real historical data (fast simulated dataset) across 3 primary assets (BTC, ETH, SOL).
The 'Before' metrics reflect fixed SL/TP logic and loose parameters. The 'After' metrics integrate trailing stops and the recent execution constraints (e.g., minimum R:R and mathematical expectancy constraints).

## INTRADAY Profile (Macro: 4h, Exec: 15m)
| Strategy | Before (PF) | Before (Exp) | After (PF) | After (Exp) | After (Sharpe) | After Win% |
|---|---|---|---|---|---|---|
| Price Action | 1.31 | 0.15R | **1.34** | **0.13R** | 1.08 | 42.1% |
| SMC | 1.25 | 0.12R | **0.35** | **-0.43R** | -0.90 | 25.0% |
| MA Crossover | 1.84 | 0.54R | **1.71** | **0.44R** | 2.02 | 33.9% |
| Mean Reversion | 2.15 | 0.74R | **2.44** | **0.80R** | 3.58 | 36.6% |
| Breakout Momentum | 0.00 | -1.00R | **0.00** | **-0.94R** | -29.96 | 0.0% |
| Delta-Gamma | 0.95 | -0.03R | **0.96** | **-0.03R** | -0.38 | 31.7% |


## SCALPING Profile (Macro: 1h, Exec: 5m)
| Strategy | Before (PF) | Before (Exp) | After (PF) | After (Exp) | After (Sharpe) | After Win% |
|---|---|---|---|---|---|---|
| Price Action | 1.19 | 0.10R | **1.28** | **0.15R** | 0.99 | 43.4% |
| SMC | 4.27 | 1.31R | **4.27** | **1.31R** | 1.27 | 60.0% |
| MA Crossover | 1.67 | 0.42R | **1.64** | **0.41R** | 2.20 | 33.7% |
| Mean Reversion | 1.56 | 0.37R | **1.50** | **0.35R** | 2.41 | 29.7% |
| Breakout Momentum | 0.00 | -1.00R | **0.00** | **-1.00R** | 0.00 | 0.0% |
| Delta-Gamma | 1.07 | 0.04R | **1.07** | **0.04R** | 0.39 | 36.2% |


## AGGRESSIVE Profile (Macro: 15m, Exec: 1m)
| Strategy | Before (PF) | Before (Exp) | After (PF) | After (Exp) | After (Sharpe) | After Win% |
|---|---|---|---|---|---|---|
| Price Action | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |
| SMC | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |
| MA Crossover | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |
| Mean Reversion | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |
| Breakout Momentum | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |
| Delta-Gamma | 0.00 | 0.00R | 0.00 | 0.00R | 0.00 | 0.0% |

