> **⚠️ DEPRECATED — superseded 2026-06-03.** Canonical metrics now live in **[Report 1 — Baseline](./STERLING_TRADING_REPORT_BASELINE.md)** (§4 spot, §5 futures, §6 options). Kept for provenance/audit only.

# Real-Data Performance — Futures vs Options (separated)

_2026-06-02 · Futures = REAL bar-by-bar on `vector_store_1m_{BTC,ETH,SOL}USD.parquet` (~2024→2026). Options = Black-Scholes MODELED off realized vol, calibrated to the live Delta surface (no historical chain). $500 start, 0.1% futures round-trip._

## ⚠️ Read this first

- **Win-rate and Profit Factor (PF) are the trustworthy, sizing-independent metrics.** Use them to compare.
- **The modeled-options $ / % returns are unreliable artifacts** — short-DTE options under fractional compounding explode to absurd values (e.g. "+5,219,805,847,186%", "$26T"). Ignore every options *dollar/return* figure. There is **no historical IV**, so options P&L is optimistic and the magnitudes are meaningless.
- **Most configurations lose.** Across the full 12,960-config grid, **futures median PF ≈ 0.88–0.94 (<1.0)**. Edge is concentrated in a handful of 2h–4h configs; sub-hour dies to fees/theta.

---

## A. FUTURES — REAL, trustworthy

OOS-robustness survivors (225 configs → **8**; CPCV OOS retention + Monte-Carlo p-loss; fee 0.10%):

| # | config | trades | **win%** | **PF** | net return | p(loss) | max-DD |
|---|--------|-------:|---------:|-------:|-----------:|--------:|-------:|
| 1 | **ma_crossover 4h BTC** | 166 | **43.4%** | **1.29** | **+95.3%** | **11%** | −27.2% |
| 2 | breakout 4h BTC | 100 | 42.0% | 1.20 | +27.7% | 28% | −28.1% |
| 3 | smc 4h ETH | 220 | 39.6% | 1.15 | +38.6% | 25% | −33.1% |
| 4 | smc 2h ETH (Aggr) | 240 | 30.0% | 1.15 | +46.4% | 27% | −45.0% |
| 5 | smc 2h ETH (Intr) | 237 | 40.9% | 1.12 | +37.5% | 32% | −46.9% |
| 6 | smc 4h BTC | 149 | 40.9% | 1.14 | +26.3% | 34% | −44.4% |
| 7 | price_action 1h BTC | 434 | 41.7% | 1.11 | +39.2% | 24% | −38.5% |
| 8 | ma_crossover 2h BTC (Aggr) | 322 | 29.2% | 1.10 | +27.6% | 34% | −39.0% |

**Full-grid median (12,960 configs)** — the sobering baseline:

| TF | futures win% | futures PF | futures median net |
|----|-------------:|-----------:|-------------------:|
| 15m | 33.1% | 0.87 | −79.5% |
| 30m | 32.9% | 0.92 | −55.4% |
| 1h | 32.8% | 0.93 | −43.5% |
| **4h** | **33.6%** | **0.94** | **−24.6%** |

→ **Only `ma_crossover 4h BTC` is a clean edge** (high net, OOS-retentive, p-loss 11%). The rest are real but carry 24–34% probability of ending underwater and 33–47% max-DD. **Win rates are ~33–43%** — these are trend/tail strategies (you lose more often than you win; PF>1 comes from a few large winners).

## B. OPTIONS — MODELED (win%/PF only; $ figures discarded)

Same entries/exits as futures, repriced as a long ATM option. **Win-rate ≈ the futures win-rate** (same signals). PF differs because options are convex:

| TF | options win% | options PF | vs futures PF |
|----|-------------:|-----------:|--------------:|
| 15m | 33.1% | 0.92 | 0.87 (both lose) |
| 30m | 32.9% | 1.01 | 0.92 |
| 1h | 32.8% | 1.08 | 0.93 |
| **4h** | **33.1%** | **1.47** | **0.94** |

By DTE (modeled): 7–14 DTE options median PF ≈ 0.91–0.99 (≈breakeven/lose on theta); only the standout configs + short DTE show high PF (and those $ are the artifacts).

**Headline config, `ma_crossover 4h BTC` (14-DTE, 1% spread):** options win% 43.4%, **PF ≈ 1.68–1.76** vs futures PF 1.29–1.33 — i.e. options *amplify the PF of a signal that already has edge*, because winners pay convex multiples. **But this is modeled and optimistic.**

## C. Honest conclusions

1. **The validated edge is FUTURES on a few 2h–4h configs** — chiefly `ma_crossover 4h BTC`. That's the only thing real data supports trading.
2. **Options are a convexity overlay, not a standalone edge.** They raise PF *where the underlying signal already wins* (4h), and bleed to losses on the median config (theta). No standalone options edge is demonstrated, and the figures are modeled — **not validatable until forward IV accrues**.
3. **No config is a "free money" machine.** ~33–43% win rates + 27–47% drawdowns mean long losing streaks are normal. Size for the p-loss, not the headline return.
