# Conviction Book — P&L Report on $500

Bottom-line performance of the regime-gated conviction book on **real $500**, as of
**2026-06-10**. Honest framing first, because it changes how every number below
should be read:

- This is **paper trading** — *no real capital is deployed*.
- The edge is real *out-of-sample* but **DSR = 0.327 < 0.5 — NOT deflation-provable.**
- 2025–26 is essentially **one macro regime** (a crypto downturn the short sleeves
  exploited). The Sharpe reflects that regime, not a full bull+bear cycle.

Source: `study.paper_trader` (live state), `study.regime_book` /
`study.funding_sleeve` (validation). Reproduce: `cd backend && .venv/bin/python -m
study.paper_trader`.

## 1. Live paper book — real Binance 4h, since inception 2025-09-07

As of bar 2026-06-10 12:00:

| | $ | Profit on $500 | Return |
|---|--:|--:|--:|
| **Realized** (closed trades only) | **$857.76** | **+$357.76** | **+71.6%** |
| **Total** (incl. 3 open shorts) | **$872.32** | **+$372.32** | **+74.5%** |

- **Sharpe 2.35** · **max drawdown −29.9%** · **146 closed trades.**
- Kill-switch **ARMED** (~27% drawdown buffer before it trips the book flat).
- Open positions: short BTC / ETH / SOL (regime gate → momentum-short in a
  downtrend), all modestly in profit.

## 2. Backtest validation (out-of-sample, $500)

Held-out last 50% of history the book never trained on:

| Dataset | $500 → | Return | Sharpe | DSR |
|---|--:|--:|--:|--:|
| **Native Binance 4h** (current) | **~$879** | **+75.8%** | 1.57 | **0.327** |
| Legacy 1m-derived | $716 | +43.2% | 1.15 | 0.166 |

Beats an equal-weight BTC/ETH/SOL buy-and-hold (−18.7% over the same OOS span) by
~60–94 points, at roughly half the drawdown. IS→OOS rank correlation **+0.38**
(in-sample quality *predicts* out-of-sample — the opposite of the project's earlier
overfit strategies, which were −0.65 to −0.73).

## 3. Robustness across start dates ($500, 1×, real Binance)

Every inception is solidly positive (as-validated snapshot — the repaint-bug fix
later trimmed the 2025-09-07 headline from +85.4% to the +71.6% live figure):

| Start | $500 → | Return | Sharpe |
|---|--:|--:|--:|
| 2025-01-01 | $879 | +75.8% | 1.46 |
| 2025-03-01 | $810 | +62.0% | 1.39 |
| 2025-06-01 | $872 | +74.4% | 1.78 |
| 2025-09-07 | $857* | +71.6%* | 2.35 |
| 2026-01-01 | $817 | +63.3% | 3.52 |
| 2026-03-01 (~3mo) | $573 | +14.5% | 1.65 |

\*current live figure.

## 4. Leverage dial ($500, OOS) — diminishing, then ruin

Sharpe is invariant to leverage; only return and drawdown move, and past ~2× the
compound return *falls* while drawdown explodes (volatility drag):

| Leverage | $500 → | Return | maxDD | note |
|--:|--:|--:|--:|---|
| 1.0× | $716 | +43.2% | −29% | conservative (live runs here) |
| **1.5×** | **$811** | **+62.3%** | −40% | **~half-Kelly (recommended ceiling)** |
| 2.0× | $889 | +77.8% | −50% | aggressive |
| 3.0× | $970 | +94.0% | −65% | return stalls |
| 4.0× | $939 | +87.9% | −76% | **ruin zone — return falls** |

## 5. What LOST money / was cut (the honest other half)

| Idea | Result on $500 | Disposition |
|---|--:|---|
| **Funding-tilt sleeve** | standalone −28.8% (→ ~$356), 0/8 OOS-positive, dragged book DSR 0.327→0.065 | **KILL** |
| **Breadth (24 coins)** | Sharpe *fell* vs 3-coin; XS factors −73% to −81% | cut |
| **Naive leverage > 2×** | return falls, drawdown to −76% | cut |
| **Uniform trailing stops** | every variant negative vs fixed bracket | cut |

## Bottom line

On $500 real Binance paper data: **+$357 realized / +$372 total (+71.6% / +74.5%),
Sharpe 2.35, −30% worst drawdown** — the strongest, most honest result this project
has produced. But it is **paper-only**, **not deflation-provable (DSR 0.327 < 0.5)**,
and earned in **one short-friendly regime**. **Update:** the full bull+bear+bull+bear
cycle (2020→now) has since been stress-tested — see `docs/fullcycle_stress_test.md`:
the book **survives and beats HODL on both axes** (OOS +150.7% vs +92.8%, −30% vs
−68% drawdown), DSR rises to **0.394**, and it is positive in every bull year (one
losing year, 2025). Still DSR < 0.5 (not provable). No real capital is deployed.
