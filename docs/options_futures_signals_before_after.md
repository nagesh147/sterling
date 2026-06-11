# Options/Futures Signals — Before / After (with $500 framing)

What the engine-level changes did to the **options/futures candidate signals** for
both engines (Sterling + Grok-directional). Date: 2026-06-11.

## The honesty caveat you must read first

**These candidate signals have no backtested P&L.** They are an *advisory* feed —
nothing was traded, auto-execution is default-OFF, and (unlike the conviction
book) the signals were never run through the deflated-Sharpe / walk-forward
harness as a tradeable strategy. So there is **no honest "$500 → $X" return for
the signals themselves.** This report compares their **quality, visibility, and
$500 risk-sizing** before vs after — not a realized P&L, which would be fabricated.

The only $500-*validated* number in this project is the conviction book (the
directional **alpha** these futures signals now reflect) — see §4.

## 1. Signal quality

| | BEFORE | AFTER |
|---|---|---|
| Signal source | Fabricated stub: `score=85 / "STRONG"` on **every** output, from a trivial EMA20 cross | Real ADX(14)+SMA(50)-slope regime → momentum (trend) / mean-reversion (range) |
| Regime | Faked: `adx = 10 + int(close) % 30` | Real Wilder ADX + SMA slope → BULL/BEAR_TREND / RANGING |
| Score | Constant 85 (meaningless) | Varies with real conviction (ADX strength / RSI extremity); STRONG≥75 / SIGNAL≥55 / NONE |
| Arming | Required 1h to independently re-confirm 4h → never armed in practice | 4h sets direction + 1h timing; arms in trend, and mean-reversion at RSI extremes in range; WATCHING when 1h opposes |

## 2. Candidate tables (what actually shows up)

| | BEFORE | AFTER |
|---|---|---|
| Futures table | **Empty** — every leg DEFERed ("sl_tp_reject" / "cramped target") | **Populates** — real defined-risk rows for armed signals (live-verified) |
| Options table | Rarely/never (Phase-2a incomplete; strike-based ATM heuristic) | Delta-targeted debit spreads built from each engine's profile **when the live chain supports it**; honest DEFER on thin chains |
| Honesty | Fake "STRONG" rows shown constantly | Real rows when a tradeable structure exists; empty when there isn't (the selector's honest judgment) |

## 3. The live example, scaled to $500

A real candidate the live engine is emitting right now:

> **BTC · directional · futures · LONG** — entry ≈ **$62,889**, stop **$61,924**
> (−1.53%), target **$64,817** (+3.07%), **2R**, 2× leverage.

- **Sizing is risk-based: 2% of account NAV per R.**
- The row's displayed notional (~$130k) is sized to the engine's `portfolio_value`
  (the drawdown-breaker peak, ~$100k) — **not** $500.
- **On a true $500 account:** 2% = **$10 risked** to make **~$20 (2R)** if the
  target hits — ≈ 0.0104 BTC, ~$650 notional at 2× (≈$325 margin).

BEFORE, on $500: there was either **nothing** (empty table) or a fabricated
all-in "STRONG" signal — acting on which would have risked the $500 on noise.
AFTER: $500 sees a **real, defined-risk** candidate ($10 risk → $20 target) with
an honest score — but an **unproven win-rate** (no backtest).

## 4. The only validated $500 number (the underlying alpha)

The directional futures signals now reflect the regime logic of the **conviction
book**, which IS $500-validated (it's the futures-direction strategy, paper-traded):

| | $500 result |
|---|--:|
| Live paper (real Binance, since 2025-09-07) | $500 → **$857 realized / +71.6%**, Sharpe 2.35, −30% maxDD |
| Backtest OOS (full 2020→now cycle) | +150.7%, **DSR 0.394** (still < 0.5 — not deflation-provable) |

That is the *strategy's* record. The candidate-signal feed's *own* trading P&L
remains untested — which is why it stays advisory (auto-exec OFF).

## Bottom line

The changes turned the options/futures signals from **fabricated-and-empty** into
**real-and-visible**: honest regime scores, futures candidates that actually render
($10-risk/$20-target defined-risk trades on $500), and delta-targeted options when
the chain supports them. What did **not** change: there is still no validated P&L
for trading these signals — they reflect a real edge (DSR 0.394) but are not
themselves proven, so they remain advisory, not auto-traded.
