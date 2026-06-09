# Backtest — Full Trading Metrics, Real Data, Before vs After

Complete performance-metrics report on real parquet data, for the two headline
BTC 4h configs. Each metric is shown for the **FULL** period, the **IN-SAMPLE**
window (the "before" view the old pipeline trusted), and the **OUT-OF-SAMPLE /
forward** window (the honest "after" view the changes exposed).

## Method

- **Data:** real 1-min OHLCV → BTC 4h, 2023-12-29 → 2026-05-30 (5,128 bars).
- **Sim:** `study.sim.simulate_idx` — long-only, enter at signal-bar close,
  first-touch intrabar ATR SL/TP, max hold 200 bars, **0.10% round-trip fee**.
- **Capital:** $500. **IS/OOS boundary:** 70% of calendar time = 2025-09-07
  (BTC fell ~−34% over the OOS span).
- Sharpe/Sortino annualised by actual trade frequency; Calmar = CAGR/|maxDD|.
- Robustness (OOS Sharpe via CPCV, P(loss) via Monte-Carlo, DSR) from the live
  `robustness_scan_results.csv`; "DSR before-fix" = what the saturated formula
  returned for every config (0.0000).

---

## Config A — `ma_crossover` Intraday (momentum), SL 2.0·ATR / TP 3.5·ATR

| Metric | FULL | IN-SAMPLE (before) | OUT-OF-SAMPLE (after) |
|---|--:|--:|--:|
| Final equity | $976 | $1,098 | $445 |
| Net return % | +95.3% | +119.5% | −11.0% |
| Net P&L ($) | +$476 | +$598 | −$55 |
| CAGR % | +33.4% | +62.7% | −15.3% |
| Trades | 166 | 115 | 51 |
| Trades / yr | 71 | 71 | 72 |
| Win rate % | 43.4% | 47.0% | 35.3% |
| Wins / Losses | 72 / 94 | 54 / 61 | 18 / 33 |
| Profit factor | 1.29 | 1.48 | 0.91 |
| Expectancy %/tr | +0.49% | +0.78% | −0.16% |
| Expectancy $/tr | +$2.46 | +$3.91 | −$0.80 |
| Avg win % | +5.02% | +5.14% | +4.66% |
| Avg loss % | −2.98% | −3.08% | −2.79% |
| Payoff (win/loss) | 1.69 | 1.67 | 1.67 |
| Biggest win % | +11.3% | +11.3% | +7.2% |
| Biggest loss % | −6.3% | −6.3% | −5.1% |
| Median trade % | −1.85% | −1.80% | −2.14% |
| **Sharpe (ann.)** | **0.98** | **1.49** | **−0.36** |
| Sortino (ann.) | 1.32 | 2.02 | −0.46 |
| Calmar | 1.23 | 2.68 | −0.56 |
| Max drawdown % | −27.2% | −23.4% | −27.2% |
| Max drawdown ($) | −$329 | −$268 | −$150 |
| Ulcer index | 10.94 | 8.85 | 14.54 |
| Recovery factor | 1.45 | 2.23 | −0.37 |
| Max win streak | 9 | 9 | 3 |
| Max loss streak | 7 | 5 | 7 |
| Avg / median hold (bars) | 20 / 12 | 22 / 12 | 18 / 12 |
| Exposure % | 66% | 48% | 18% |
| Skew | +0.48 | +0.37 | +0.68 |
| Kurtosis | 1.9 | 1.8 | 1.8 |
| Tail ratio p95/\|p5\| | 1.71 | 1.76 | 1.61 |
| Exits TP / SL / time | 72 / 94 / 0 | 54 / 61 / 0 | 18 / 33 / 0 |
| Fee drag ($) | $176 | $133 | $23 |

**Robustness:** OOS Sharpe (CPCV) +10.52 · P(loss) 0.11 · DSR(525-grid) **0.0620**
· DSR before-fix 0.0000 · beats buy-and-hold ✅ (HODL full $861, HODL OOS $331).

**Read:** profitable and significant-looking in-sample (Sharpe 1.49, PF 1.48),
but **forward it flips negative** (Sharpe −0.36, PF 0.91, −11%). Win rate drops
47%→35%, profit factor falls below 1. The momentum edge is regime-dependent.

---

## Config B — `bb_rsi_reversion` Aggressive (mean-reversion), SL 1.5·ATR / TP 4.5·ATR

| Metric | FULL | IN-SAMPLE (before) | OUT-OF-SAMPLE (after) |
|---|--:|--:|--:|
| Final equity | $997 | $949 | $525 |
| Net return % | +99.3% | +89.8% | +5.0% |
| Net P&L ($) | +$497 | +$449 | +$25 |
| CAGR % | +35.4% | +50.8% | +7.4% |
| Trades | 92 | 64 | 28 |
| Trades / yr | 40 | 41 | 41 |
| Win rate % | 32.6% | 32.8% | 32.1% |
| Wins / Losses | 30 / 62 | 21 / 43 | 9 / 19 |
| Profit factor | 1.53 | 1.71 | 1.16 |
| Expectancy %/tr | +0.89% | +1.16% | +0.28% |
| Expectancy $/tr | +$4.44 | +$5.78 | +$1.39 |
| Avg win % | +7.82% | +8.52% | +6.20% |
| Avg loss % | −2.47% | −2.44% | −2.53% |
| Payoff (win/loss) | 3.17 | 3.49 | 2.45 |
| Biggest win % | +19.1% | +19.1% | +13.7% |
| Biggest loss % | −4.5% | −4.5% | −4.2% |
| Median trade % | −1.82% | −1.82% | −1.84% |
| **Sharpe (ann.)** | **1.05** | **1.30** | **0.38** |
| Sortino (ann.) | 2.16 | 2.87 | 0.66 |
| Calmar | 1.88 | 2.70 | 0.42 |
| Max drawdown % | −18.8% | −18.8% | −17.6% |
| Max drawdown ($) | −$180 | −$144 | −$95 |
| Ulcer index | 7.00 | 6.92 | 7.14 |
| Recovery factor | 2.76 | 3.12 | 0.26 |
| Max win streak | 2 | 2 | 2 |
| Max loss streak | 7 | 7 | 7 |
| Avg / median hold (bars) | 25 / 12 | 23 / 12 | 29 / 12 |
| Exposure % | 44% | 28% | 16% |
| Skew | +1.25 | +1.19 | +1.22 |
| Kurtosis | 3.6 | 3.3 | 3.4 |
| Tail ratio p95/\|p5\| | 3.05 | 3.16 | 2.04 |
| Exits TP / SL / time | 28 / 62 / 2 | 21 / 43 / 0 | 7 / 19 / 2 |
| Fee drag ($) | $95 | $62 | $15 |

**Robustness:** OOS Sharpe (CPCV) +15.55 · P(loss) 0.08 · DSR(525-grid) **0.0959**
· DSR before-fix 0.0000 · beats buy-and-hold ✅.

**Read:** low win rate (32.6%) but high payoff (3.17×) and positive skew (+1.25)
— a convexity profile. Decays forward (Sharpe 1.30→0.38) but **stays positive**
(+5%) where BTC fell −34% and momentum went negative. The one real lead.

---

## Study-level — what the gate admits, before vs after

Live CSV `robustness_scan_results.csv`: **525 configs**, real data.

| | BEFORE gate | AFTER gate |
|---|---|---|
| Rule | net>0, OOS Sharpe>0, P(loss)≤35% | + DSR≥0.5 + beats buy-and-hold |
| Configs admitted live | **23** | **0** |
| $500/config (median) | $696 | — (cash) |
| Beat buy-and-hold | 11 / 23 | n/a |
| Mean DSR of admitted | 0.027 (max 0.096) | — |

Full-grid DSR spans **0.000–0.096** — *no* config is within 5× of the 0.5 bar.
39 configs are net-positive and 99 beat hold, but none survive deflation.

## Forward proof — anchored walk-forward ($500, params chosen on past only)

| TF | WF $500 | Sharpe | n | DSR | BTC HODL (span) |
|---|--:|--:|--:|--:|--:|
| 1h | $497 (−0.6%) | 0.11 | 59 | 0.003 | $436 (−12.7%) |
| 2h | $579 (+15.8%) | 4.14 | 19 | 0.040 | $439 (−12.3%) |
| 4h | $554 (+10.7%) | 1.83 | 23 | 0.012 | $439 (−12.3%) |

Cross-symbol (final BTC-selected params, OOS spans never used in selection):
ETH +19.6%, SOL +20.1% (SOL −38%). Real but n too small → DSR ≪ 0.5.

## Verdict

Every full-period and in-sample number looks deployable (Sharpe ~1, PF >1.3,
Calmar >1.8). The **out-of-sample columns are the truth**: momentum goes Sharpe
−0.36 / PF 0.91; mean-reversion holds at Sharpe 0.38 / PF 1.16 but at a return
too small, with too few trades, to clear deflation. Before the changes the
system would have sent 23 such configs live on the in-sample mirage; after, it
sends **0** and preserves the $500.
