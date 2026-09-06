# Kite Sterling Kite Engine — Full Permutation Backtest (real data)

**Date:** 2026-06-20 · **Branch:** KiteEngine · **Scope:** Kite Indian index options.

Every combination of the live Kite strategy's knobs, replayed over **7.5 years of
real 1H index candles** pulled from the Zerodha historical API (read-only). This
report answers: *does any permutation of the existing strategy have a real,
out-of-sample-durable edge?*

Harness: `backend/study/kite_data.py` (fetch+cache), `kite_st_sweep.py` (sweep),
`kite_st_analyze.py` (diagnostics). Reuses the **production** regime core,
Black-Scholes pricer, Indian F&O cost schedule and stats — results match the
`/api/v1/kite/engine/backtest` endpoint.

---

## TL;DR

> **As built — buying index options on the signal — NO permutation survives
> out-of-sample. 0 of 60 configs are OOS net-positive; 0 of 60 have OOS profit
> factor > 1.0.** The eye-popping full-history returns (up to +961%) are an
> artifact of (a) the high-volatility 2019–2023 in-sample regime and (b) a *fixed*
> implied-volatility assumption — the IV-sensitivity sweep shows the entire
> "profit" is the IV input, not the strategy.
>
> **But the underlying signal is not worthless.** Stripping the options wrapper and
> trading the *signal* delta-1 (futures-equivalent) is **net-positive out-of-sample
> on all four indices** (OOS profit factor 1.05–1.15). The trend signal has a
> modest, durable *directional* edge; the *option-buying wrapper* (theta + IV) is
> what destroys it.

**Actionable:** the edge is directional, not in long options. Monetize it with
delta-1 / futures (or deep-ITM with DTE matched to hold), price with **live** IV
(never a fixed assumption), drop `early_lock` (proven inert), and prefer
`trail=fast/mid` over `slow`.

---

## Data

| Underlying | Real 1H bars | Span | Source |
|---|---|---|---|
| NIFTY 50 | 12,903 | 2019-01-01 → 2026-06-19 | Kite historical (token 256265) |
| NIFTY BANK | 12,903 | 2019-01-01 → 2026-06-19 | Kite historical (token 260105) |
| NIFTY FIN SERVICE | 12,903 | 2019-01-01 → 2026-06-19 | Kite historical (token 257801) |
| SENSEX | 12,850 | 2019-01-01 → 2026-06-19 | Kite historical (token 265) |

Underlying candles are **real**. Option premium is **Black-Scholes-modelled** (IV
0.18, theta decay) — the only way to test the signal over full history, since
expired strikes have no fetchable premium. A real-premium anchor on currently-listed
contracts is in §6. **IS** = first 70% (2019→2024, includes the COVID crash + the
2020–21 bull). **OOS** = last 30% (~2024-09 → 2026-06). Each window's regime is
computed only from its own bars (no look-ahead).

## The permutation grid (the "existing strategy" knobs)

| Knob | Values | Count |
|---|---|---|
| underlying | NIFTY 50, NIFTY BANK, NIFTY FIN SERVICE, SENSEX | 4 |
| `trail_target` | fast, mid, slow | 3 |
| `early_lock` | off, on@0.5R, on@1.0R, on@1.5R | 4 |
| moneyness | ITM2, ITM1, ATM, OTM1, OTM2 | 5 |

**240 permutations** × 3 windows (full / IS / OOS). Fixed: monthly expiry
(**DTE 30** — see §5; the signal's median hold is 3.7 days, p90 ~10 days, so a
7-DTE weekly would expire mid-trade), lot qty 50, ₹100k capital, real Indian F&O
costs (STT 0.0625% on sell premium, ₹20/order brokerage, 0.035% exchange, 18% GST,
SEBI, stamp, 1%/side slippage). Full table: `backend/study/kite_st_sweep_results.csv`.

> **`early_lock` is inert — proven, not assumed.** All four lock variants produce
> *byte-identical* results. `early_lock` adds a slow-SuperTrend exit once in profit,
> but the slow ST (widest band) always flips *after* the fast/mid trail has already
> exited — so it never fires (0 early-lock exits across the whole sweep). It can be
> removed from the engine. The grid below collapses to the 60 distinct configs.

---

## 1. Options-buying results (the strategy as deployed)

**Across all 60 distinct configs:**

| Metric | Result |
|---|---|
| Full-history net-positive | **45 / 60** |
| **OOS net-positive** | **0 / 60** |
| **OOS profit factor > 1.0** | **0 / 60** |
| Best full-history return | +975.8% |
| Best OOS return | **−12.0%** (still a loss) |
| IS→OOS rank correlation (Spearman) | 0.354 |

The ranking partially carries from IS to OOS (corr 0.35 > 0), but the *magnitude*
collapses from triple-digit gains to losses. Nothing clears the holdout.

### Best config per index (ranked by OOS return)

| Underlying | trail | moneyness | Full ret | IS ret | **OOS ret** | PF | OOS PF | trades |
|---|---|---|---|---:|---:|---:|---:|---:|
| NIFTY FIN SERVICE | fast | OTM2 | +246.4% | +257.6% | **−12.0%** | 1.186 | 0.975 | 553 |
| NIFTY BANK | mid | OTM2 | +961.4% | +1005.7% | **−46.5%** | 1.396 | 0.951 | 332 |
| NIFTY 50 | fast | OTM2 | +58.4% | +118.0% | **−60.5%** | 1.054 | 0.849 | 547 |
| SENSEX | mid | OTM2 | −86.6% | +87.9% | **−206.7%** | 0.975 | 0.847 | 358 |

Note NIFTY BANK's full-history **+961%** → **OOS −46.5%**: the headline number is
entirely an in-sample (high-vol) phenomenon.

### Effect of the knobs (mean OOS return)

| `trail_target` | fast **−92%** · mid −117% · slow −313% | fast/mid beat slow decisively |
|---|---|---|
| **moneyness** | OTM2 **−165%** · OTM1 −170% · ATM −174% · ITM1 −179% · ITM2 −183% | cheaper OTM bleeds least (all negative) |

---

## 2. Why the full-history numbers are a mirage — IV sensitivity

Same config (FINNIFTY fast OTM2), full history, **only the IV assumption changes:**

| IV assumption | Return | Profit factor |
|---:|---:|---:|
| 0.10 | **+836.7%** | 1.818 |
| 0.14 | +508.6% | 1.426 |
| 0.18 (base) | +246.4% | 1.186 |
| 0.22 | +20.8% | 1.014 |
| 0.28 | **−278.3%** | 0.827 |

The result swings from a 9× gain to a total loss purely on the IV input. **A
backtest whose sign depends on a fixed IV guess is not measuring a tradeable edge** —
real options are bought at *market* IV, which moves against trend-buyers exactly when
realised vol falls. This single table is the strongest reason to distrust any
"long options" P&L here.

## 3. DTE sensitivity (theta)

Same config, varying expiry at entry:

| DTE | Return | PF |
|---:|---:|---:|
| 7 | +422.8% | 1.339 |
| 14 | +340.1% | 1.268 |
| 30 (base) | +246.4% | 1.186 |
| 45 | +186.0% | 1.136 |
| 60 | +137.3% | 1.098 |

Shorter DTE *looks* better (more convexity) but is unusable: the signal holds a
median 3.7 / p90 ~10 / max ~25 days, so a 7-DTE weekly expires inside most winners.
The monthly (30) is the honest baseline.

---

## 4. Signal isolation — does the trend itself have edge?

Strip the options wrapper: trade the **same entries delta-1** on the underlying
(long bull / short bear, exit on trail flip, 3 bps round-trip friction).

| Underlying | best trail | Full ret | PF | Win% | **OOS ret** | **OOS PF** | trades |
|---|---|---:|---:|---:|---:|---:|---:|
| NIFTY FIN SERVICE | fast | +73.4% | 1.244 | 39.2% | **+10.9%** | **1.15** | 553 |
| SENSEX | fast | +60.1% | 1.248 | 37.8% | **+8.9%** | **1.14** | 545 |
| NIFTY 50 | mid | +72.9% | 1.357 | 39.1% | **+6.2%** | **1.10** | 361 |
| NIFTY BANK | mid | +94.7% | 1.372 | 42.2% | **+3.7%** | **1.05** | 332 |

**All four are net-positive out-of-sample** (OOS PF 1.05–1.15). The classic
trend-follower profile — sub-coinflip win rate (~38–42%) carried by winners running
on the trail. This is a *modest* edge (PF ~1.2–1.4, not deflation-grade), but it is
**real and it survives the holdout** — the opposite of the options version.

**Conclusion: the signal has a directional edge; the option-buying wrapper (theta +
IV) is what turns it into a guaranteed OOS loser.**

## 5. Modelling choices & honesty caveats

- **Premium is BS-modelled** over real underlying history (fixed IV 0.18 + theta).
  §2 shows this assumption *is* the result — treat all §1–3 absolute returns as
  illustrative of the *mechanism*, not as achievable P&L.
- **IS regime is favourable to long options** (2020 crash + 2020–21 bull = high
  realised vol). OOS (2024–26, lower vol) is where theta dominates. This is realistic,
  not a flaw — it's why OOS is the metric that matters.
- Costs are the real Indian F&O schedule with 1%/side slippage (heavy, appropriate
  for OTM index spreads).
- `early_lock` modelled faithfully (mirrors `engine.manage`) and shown inert.

## 6. Real-premium anchor (currently-listed contracts)

Replay on *actual* fetched option premium (no BS), nearest ATM monthly:

| Contract | window | trail=fast | mid | slow |
|---|---|---|---|---|
| NIFTY2662324050CE | 2026-05-25→06-19 | −4.0% (n=3) | +1.0% (n=1) | +0.3% (n=1) |
| BANKNIFTY26JUN57700CE | 2026-04-22→06-19 | +8.4% (n=5) | +4.8% (n=3) | +13.4% (n=2) |

**n = 1–5 trades over ~1 month — statistically meaningless** (one expiry cycle is
all the real premium history a listed strike has). Shown only as a sanity anchor;
it neither confirms nor refutes §1.

---

## Recommendations

1. **Do not deploy the long-options strategy on any of these permutations** — 0/60
   survive out-of-sample, and the backtested gains are an IV/regime artifact.
2. **The edge is directional.** To monetize the ST signal, trade **futures / delta-1**
   (OOS PF 1.05–1.15) rather than buying OTM options; if options are required, use
   **deep-ITM (≈delta-1) with DTE matched to the ~10-day p90 hold**, and size for
   the ~38–42% win rate.
3. **Never backtest or trade these with a fixed IV** — the engine must mark premium
   to **live** IV; a fixed assumption flips the sign of the result.
4. **Remove `early_lock`** (inert) and **prefer `trail=fast` or `mid`** (slow is
   far worse on every axis).
5. Treat even the delta-1 edge as *modest* (PF ~1.2–1.4), consistent with the rest
   of this codebase's finding that nothing clears a deflated-Sharpe bar — validate
   on more history / more underlyings before risking real capital.

*Artifacts: `backend/study/kite_st_sweep_results.csv` (all 240 rows),
`kite_st_sweep_meta.json`, `kite_st_analysis.json`.*
