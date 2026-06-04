# Sterling Trading Report — Before / After Kronos

**Report 3 of 3** · _Canonical_ · Date: 2026-06-03 · Branch: `main` @ `7a6b2ab`
Companion reports: [Report 1 — Baseline](./STERLING_TRADING_REPORT_BASELINE.md) · [Report 2 — With Kronos](./STERLING_TRADING_REPORT_KRONOS.md)

> This report supersedes and consolidates `docs/superpowers/specs/2026-06-03-kronos-integration-before-after.md`. That file is retained for provenance only and carries a deprecation banner pointing here.

---

## 0. Provenance & framing — read this first

| Field | Value |
|---|---|
| **Capital** | $500 per combo · $5,000 across 10 combos |
| **Data** | REAL BTC/ETH/SOL 1-minute parquet, Dec 2023 → May 2026 (3.56M bars) |
| **Engine** | Bar-by-bar first-touch SL/TP, ATR sizing, 0.10% round-trip fees |
| **"Before"** | 10 validated combos, **every signal executed** (no gate) — **out-of-sample forward replay** |
| **"After"** | Same combos, **Kronos gate** applied (mini, 4.1M) — REAL for futures/spot |
| **Options** | **Not included in the $ comparison** — modeled-only, no options×Kronos run (see §7) |
| **Integration** | **Kronos is not wired yet.** This is a backtest-validated proposal. |

> **Critical reconciliation for reviewers:** the "before" numbers here are *worse* than the in-sample selection metrics in [Report 1 §4.2]. That is the whole point. The 10 combos were *selected* on full-history in-sample stats (e.g. BTC 4h MA Cross **+95.3%** in-sample), but on an **out-of-sample forward replay they bleed** (that same combo → **−$75**). Sharpe regresses from +0.39…1.83 in-sample to −1.22…0.79 out-of-sample. **Validated ≠ profitable live.** Kronos is the layer that closes that gap.

---

## 1. Executive summary

| Metric | Before (Sterling) | After (+ Kronos) | Delta |
|---|---|---|---|
| **Total PnL** | −$674 | **+$573** | **+$1,247** |
| **Return on capital** | −13.5% | **+11.5%** | **+25.0pp** |
| **Sharpe** | −0.305 | **2.967** | **+3.27** |
| **Profit factor** | 0.96 | **1.54** | +0.58 |
| **Win rate** | 33.2% | **43.0%** | **+9.8pp** |
| **Max drawdown** | 65.8% | **13.3%** | **−52.5pp** |
| **Total trades** | 2,075 | 237 | −88.6% |
| **Trades / month** | ~70 | ~8 | −88.6% |
| **Profitable combos** | 4 / 10 | **10 / 10** | all win |

> Kronos turns the validated-combo book from **losing −$674 to making +$573** by filtering **88.6%** of low-conviction signals while preserving the high-conviction ones. The system trades **less** but wins **more** — 43% vs 33% win rate at **1/5th the drawdown.**

---

## 2. Before / After by instrument

All three instruments share the same gated signal set; they differ only in the P&L transform (Report 1 §0).

| Instrument | Before | After | Evidence |
|---|---|---|---|
| **Spot / Index** (1×, no funding) | −13.5% net, 33.2% win, DD 65.8% | **+11.5% net, 43.0% win, DD 13.3%** | REAL — directional edge turns positive on the gate alone, not on leverage |
| **Futures** (leveraged + funding + fees) | −$674, PF 0.96, Sharpe −0.31 | **+$573, PF 1.54, Sharpe 2.97** | REAL — the headline result; §3–§5 |
| **Options** (convex, modeled) | win% = futures; median PF ~0.91–1.47 | **win% +9.8pp ⇒ PF expected higher** | **INFERENCE ONLY** — no options×Kronos run; see §7 |

**Instrument takeaway:** the improvement is driven entirely by the **signal-selection layer**, which is instrument-agnostic. Futures realize it linearly (measured). Options *should* realize it with amplification via convexity (unmeasured). Spot/Index shows the pure effect at 1×.

---

## 3. Per-combo PnL: before → after

| Combo | Before PnL | After PnL | Delta |
|---|---|---|---|
| BTC 4h MA Cross Intraday | −$75 | +$2 | **+$76** |
| BTC 4h Breakout Intraday | +$71 | +$88 | +$17 |
| ETH 4h SMC Scalping | +$100 | +$29 | −$71 |
| SOL 4h SMC Aggressive | −$53 | +$128 | **+$181** ✦ |
| BTC 4h SMC Intraday | +$64 | +$88 | +$24 |
| BTC 4h MA Cross Aggressive | −$24 | +$48 | **+$72** ✦ |
| BTC 1h Price Action Intraday | −$267 | +$46 | **+$313** ✦ |
| BTC 4h SMC Aggressive | −$85 | +$36 | **+$121** ✦ |
| SOL 4h SMC Scalping | −$151 | +$64 | **+$214** ✦ |
| BTC 1h Price Action Aggressive | −$255 | +$46 | **+$301** ✦ |
| **Total** | **−$674** | **+$573** | **+$1,247** |

✦ = flipped from losing to winning (6 of 10). The single regression — **ETH 4h SMC Scalping (−$71)** — stayed profitable (+$29). Every other combo improved.

---

## 4. Per-combo drawdown: before → after

| Combo | Before max DD | After max DD | Reduction |
|---|---|---|---|
| BTC 1h Price Action Intraday | 65.8% | 10.1% | **−55.6pp** |
| BTC 1h Price Action Aggressive | 65.0% | 13.3% | **−51.7pp** |
| SOL 4h SMC Scalping | 51.5% | 6.3% | **−45.2pp** |
| BTC 4h SMC Aggressive | 37.8% | 9.2% | −28.6pp |
| ETH 4h SMC Scalping | 32.0% | 6.0% | −26.0pp |
| SOL 4h SMC Aggressive | 29.7% | 6.3% | −23.5pp |
| BTC 4h MA Cross Intraday | 36.2% | 12.8% | −23.3pp |
| BTC 4h MA Cross Aggressive | 33.5% | 11.9% | −21.6pp |
| BTC 4h Breakout Intraday | 20.6% | 4.2% | −16.3pp |
| BTC 4h SMC Intraday | 21.7% | 8.1% | −13.6pp |

Worst-case drawdown falls from **65.8% → 13.3%**. Combos with DD > 30% go from **6/10 → 0/10**; DD > 50% from **3/10 → 0/10**.

---

## 5. Why the filter works (and what it removes)

| Symbol/TF | Raw signals | After Kronos | Filtered |
|---|---|---|---|
| BTCUSD 4h | 1,076 | 192 | 82.2% |
| ETHUSD 4h | 207 | 23 | 88.9% |
| SOLUSD 4h | 313 | 32 | 89.8% |
| BTCUSD 1h | 879 | 49 | 94.4% |
| **Total** | **2,075** | **237** | **88.6%** |

Kronos removes 1,838 signals; the removed set accounts for **more than 100% of the losses** (the book swings +$1,247 on only 237 remaining trades). It isn't predicting trade outcomes — it forecasts the next 12 candles and blocks entries into bearish/uncertain regimes, which is exactly where the no-gate system bled.

---

## 6. Risk & capital efficiency

| Metric | Before | After |
|---|---|---|
| Final equity ($5k start) | $4,326 | **$5,573** |
| Avg PnL per trade | −$0.32 | **+$2.42** |
| Avg PnL / winning trade | — | +$18.91 |
| Avg PnL / losing trade | — | −$10.03 |
| Return per unit risk (PnL / \|maxDD\|) | 0.20 | **0.86** |
| Capital at risk (maxDD × capital) | −$3,290 | −$665 |
| Avg combo drawdown | 36.0% | 8.8% |
| Expected monthly PnL | −$22 | **+$19** |
| Expected trades / month | ~70 | ~8 |

---

## 7. Honest caveats (the reviewer's red-team list)

1. **Kronos is not wired.** No `backend/app/engines/kronos/` exists. This is a validated *proposal*, not a deployed result. (Report 2 §7 lists the build.)
2. **Small sample.** 237 gated trades (~8/month) is statistically thin. Confidence intervals on Sharpe 2.97 are wide. Treat as promising, not proven.
3. **Options are excluded from the $ comparison.** They are modeled-only (constant-IV BSM, no historical IV), and **no options×Kronos backtest exists.** §2's options row is *inference* from the +9.8pp win-rate lift, not a measurement.
4. **In-sample selection bias upstream.** The 10 combos were chosen on in-sample stats; the "before" is their OOS bleed. Kronos is tested *on the same data window* — its own out-of-sample robustness still needs shadow-mode confirmation.
5. **Model staleness risk.** Pre-trained weights don't adapt to regime shifts; quarterly re-fine-tune + decay tracking required.
6. **Permissive thresholds.** The gate (pred_return 0.05%, confidence 0.2) already filters 86%; the result is sensitive to these — re-tune on more data.

---

## 8. Recommendation

**Adopt Kronos as a signal gate via shadow → paper → live.**

| Phase | Timeline | Scope | Capital risk | Gate to advance |
|---|---|---|---|---|
| 1 — Shadow | Wk 1–2 | Log predictions, no trade impact | None | Predictions logged; lookahead-clean |
| 2 — Paper | Wk 3–4 | Gate on paper only | Paper only | Paper Sharpe > 2.0, DD < 15% |
| 3 — Live | Month 2 | Top 3 combos (BTC Breakout, SOL SMC Aggr, BTC SMC Intraday), 0.5% risk/trade | Small | Live tracks backtest within tolerance |
| 4 — Optimize | Month 3 | Fine-tune on Sterling parquet; begin options measurement post forward-IV | Model risk | Measured options uplift |

**Bottom line:** measured on futures/spot, Kronos converts a losing validated-combo book into a profitable one (−$674 → +$573) with a 5× drawdown reduction, by trading far less and far better. The result is **real but thin and not yet wired**, and the **options uplift is expected but unmeasured.** The architecture is ready; the next step is shadow mode — not capital.

---

### Cross-references
- Baseline metrics & full config matrix → [Report 1](./STERLING_TRADING_REPORT_BASELINE.md)
- Kronos mechanics, model card, gate knobs, build plan → [Report 2](./STERLING_TRADING_REPORT_KRONOS.md)
