# Cross-Market Test — Indian Indices (Honest Negative)

Goal: the honest path to a deflation-provable (DSR ≥ 0.5) edge is *independent*
information. Crypto-coin breadth failed (coins ~0.8 correlated). Indian equity
indices (NIFTY, BANKNIFTY) are genuinely uncorrelated to crypto, so this tested two
things: (1) is the conviction-book *architecture* market-agnostic, and (2) does
pooling crypto + Indian lift the combined DSR past 0.5?

Data: real Yahoo Finance daily, NIFTY (`^NSEI`) + BANKNIFTY (`^NSEBANK`), 2016→2026
(~2,460 bars each); crypto = BTC/ETH/SOL 4h 2020→now. The **exact**
`study.regime_book.select_conviction_book` was run on each, unchanged. Reproduce:
`cd backend && .venv/bin/python -m study.crossmarket_probe`.

## Pre-registered criteria (frozen before the run)

- **Market-agnostic** if NIFTY/BANKNIFTY standalone OOS Sharpe > 0 and IS→OOS corr ≥ 0.
- **Provability breakthrough** if pooled (crypto + Indian) combined DSR ≥ 0.5.
- **Honest negative** if the engine loses on Indian indices → edge is crypto-specific.

## Result — NEGATIVE on both questions

| Market (same engine) | OOS return | Sharpe | n | DSR | IS→OOS corr |
|---|--:|--:|--:|--:|--:|
| **Crypto** (BTC/ETH/SOL) | +150.7% | **1.16** | 570 | **0.394** | **+0.82** |
| **NIFTY** | **−13.5%** | **−1.71** | 52 | 0.002 | **−0.87** |
| **BANKNIFTY** | +2.5% | 0.64 | 38 | 0.029 | +0.32 |
| Indian (NIFTY+BANK) | +1.3% | 0.29 | 83 | 0.024 | −0.40 |

**The engine is NOT market-agnostic.** It loses on NIFTY with a strongly *negative*
IS→OOS correlation (−0.87 = the overfit signature), and is only marginally positive
on BANKNIFTY on a tiny sample (38 trades). The regime book is a **crypto-specific**
edge, not a universal regime-follower.

### Independence held — but it didn't help

Daily OOS-return correlations are essentially zero, exactly as hypothesised:

|  | crypto | nifty | banknifty |
|---|--:|--:|--:|
| crypto | 1.00 | −0.01 | −0.03 |
| nifty | −0.01 | 1.00 | 0.03 |
| banknifty | −0.03 | 0.03 | 1.00 |

But diversification only helps when you combine *positive-edge* uncorrelated streams.
Pooling a losing book (NIFTY) and a barely-positive one (BANKNIFTY) **dilutes**:

| Book (per-day basis) | daily Sharpe | DSR |
|---|--:|--:|
| crypto alone | 0.51 | 0.071 (36 trials) |
| crypto + NIFTY + BANKNIFTY | **0.39** | **0.023** (108 trials) |

Pooling *lowered* both Sharpe and DSR. **The 0.5 bar was NOT cleared — it moved
the wrong way.** (Per-day basis differs from the per-trade headline DSR 0.394; the
point is the *direction*: adding edgeless uncorrelated markets hurts.)

## Why it failed (honest diagnosis)

- **Indian indices are long-biased trenders** (NIFTY/BANKNIFTY rose for most of
  2016-2026); the book's short + mean-reversion sleeves fight that, and the regime
  thresholds were shaped by crypto's volatility structure, not equity index dynamics.
- **Daily bars → tiny samples** (38-52 OOS trades) after the deep-RSI conviction
  filter; not enough to support an edge or a DSR.
- Equity microstructure (gaps, no 24/7, different vol regimes) doesn't match the
  ATR first-touch / 4h assumptions the book was built on.

## Verdict

Uncorrelated data was necessary but not sufficient — you also need an *edge* in that
market, and naively transferring the crypto book to Indian indices does not produce
one. This is a documented **negative**, joining breadth / cross-sectional / leverage
/ trailing / funding-sleeve. The honest standing conclusion is unchanged and sharper:

> The conviction book is a **real, validated, regime-robust *crypto* edge** (survives
> a full cycle, DSR 0.394) — **not** a universal multi-market engine. Making it work
> on Indian markets would require a *separate strategy re-fit* for equity dynamics
> (its own research program, with its own honest chance of failing), not a config
> change. DSR ≥ 0.5 remains uncleared.
