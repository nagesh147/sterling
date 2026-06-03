# Sterling Trading Report — With Kronos AI Gatekeeper

**Report 2 of 3** · _Canonical_ · Date: 2026-06-03 · Branch: `main` @ `7a6b2ab`
Companion reports: [Report 1 — Baseline](./STERLING_TRADING_REPORT_BASELINE.md) · [Report 3 — Before/After](./STERLING_TRADING_REPORT_BEFORE_AFTER.md)

> This report supersedes and consolidates `KRONOS_ANALYSIS_REPORT.md` and `VALIDATED_KRONOS_FINAL_REPORT.md`. Those files are retained for provenance only and carry a deprecation banner pointing here.

---

## 0. Status & provenance — read this first

| Fact | Detail |
|---|---|
| **Integration status** | **PROPOSED. Not wired.** There is no `backend/app/engines/kronos/` in the codebase today. The components in §7 are "to build." |
| **Futures evidence** | **REAL** — the gated results are a bar-by-bar replay of the 10 validated combos through the Kronos gate on actual 1m parquet (Dec 2023 → May 2026). |
| **Spot/Index evidence** | **REAL** — the same gated replay at 1×, no funding. |
| **Options + Kronos** | **INFERENCE, NOT MEASURED.** No options×Kronos backtest exists. §6 reasons from the measured signal-level win-rate lift; it is explicitly *not* a result. |
| **Sample size** | **237 gated trades.** Statistically thin — see §8. |
| **Model used** | Kronos-mini (4.1M params, context 2048). |

> Everything here describes **what the backtest shows if the gate were added** with zero changes to signal generation or order execution. The numbers are real for futures/spot; the integration is a design.

---

## 1. What Kronos is

Kronos is a **decoder-only autoregressive Transformer foundation model for candlesticks** (Tsinghua / AAAI 2026), trained on **12B+ candles from 45 exchanges**. It makes **zero-shot directional forecasts** of future OHLCV — no fine-tuning on Sterling's data required.

| Property | Value |
|---|---|
| Parameters | 4.1M (mini) / 24.7M (small) / 103M (base) |
| Context window | 2,048 bars |
| Tokenizer | Binary Spherical Quantization (BSQ), dual 10-bit heads |
| Prediction horizon | 1–24 bars (configurable) |
| Inference (CPU) | ~70s/prediction (this study averaged ~1.1s on cached batches) |
| Inference (GPU) | <5s/prediction |
| Memory | ~100MB (mini) / ~400MB (small) |

Kronos is **not** a trade-outcome predictor. It predicts the **next 12 candles**, and Sterling converts that into a **gate** (allow / block) on each signal.

---

## 2. How the gate works (the only new logic)

Kronos sits **between signal generation and the order router**. Signal generation, sizing, strikes, and execution are unchanged.

```
Edge signal fires (§ Report 1 strategies)
        │
        ▼
Kronos gate at bar i:
  1. nearest Kronos prediction (within `step` bars)
  2. predicted_return = mean(predicted_closes) − current_close
  3. confidence       = 1 / (1 + prediction_spread × 100)
  4. ALLOW iff  predicted_return > 0.05%  AND  confidence > 0.2
        │
   ┌────┴────┐
 ALLOW     BLOCK            (≈14% pass, ≈86% filtered)
   │
   ▼
Order Router (paper/shadow/live) — unchanged
```

- **Bullish & confident → allow** the long entry.
- **Bearish or uncertain → block.** Skipping uncertain regimes preserves capital.

---

## 3. New configuration knobs Kronos adds

These stack **on top of** every Report 1 config (symbol/TF/strategy/profile/risk/derivatives all still apply). Defaults from the validated run:

| Knob | Default | Effect |
|---|---|---|
| `predicted_return_threshold` | **0.0005** (0.05%) | Minimum forecast move to allow a trade. Higher → fewer, higher-conviction trades |
| `confidence_threshold` | **0.2** | Minimum ensemble agreement. Higher → blocks noisy regimes harder |
| `lookback_bars` | **200** | Candles fed to Kronos |
| `prediction_length` | **12** | Future bars forecast |
| `sample_count` | **3** | Ensemble members averaged |
| `step_4h` | **24** | Re-predict every 24 bars on 4H |
| `step_1h` | **48** | Re-predict every 48 bars on 1H |
| `model` | **kronos-mini** | mini / small / base trade accuracy vs latency |

> **Tuning intuition for reviewers:** raising either threshold trades *fewer* signals at *higher* average conviction. The validated config is deliberately permissive (0.05% / 0.2) and still filters **86%** of signals — i.e. the raw signal set is mostly low-conviction.

---

## 4. SPOT / INDEX + Kronos (REAL, 1×)

Win% and PnL shape are identical to futures (same gated entries, 1×, no funding). The aggregate gated set:

| Metric | Baseline (no gate) | **+ Kronos** | Δ |
|---|---|---|---|
| Trades | 2,075 | **237** | −88.6% |
| Win rate | 33.2% | **43.0%** | **+9.8pp** |
| Avg Sharpe | −0.305 | **2.967** | **+3.27** |
| Profit factor | 0.96 | **1.54** | +0.58 |
| Net (1× on $5k) | −13.5% | **+11.5%** | +25.0pp |
| Worst max DD | 65.8% | **13.3%** | −52.5pp |

The directional edge becomes positive at 1× — meaning the gate, not leverage, is what turns the system profitable.

---

## 5. FUTURES + Kronos — REAL (the headline result)

The 10 validated combos, replayed bar-by-bar with the gate, $500 each ($5,000 total), 0.10% round-trip:

| Combo | Trades | Win% | Sharpe | PF | PnL | Return | Max DD |
|---|---|---|---|---|---|---|---|
| BTC 4h MA Cross Intraday | 35 | 40.0% | 0.06 | 1.01 | +$2 | +0.3% | 12.8% |
| BTC 4h Breakout Intraday | 17 | **58.8%** | **6.03** | **2.14** | +$88 | +17.5% | **4.2%** |
| ETH 4h SMC Scalping | 23 | 39.1% | 1.57 | 1.23 | +$29 | +5.9% | 6.0% |
| SOL 4h SMC Aggressive | 15 | 46.7% | **6.27** | **2.39** | +$128 | +25.5% | 6.3% |
| BTC 4h SMC Intraday | 25 | 52.0% | 4.03 | 1.68 | +$88 | +17.6% | 8.1% |
| BTC 4h MA Cross Aggressive | 34 | 32.4% | 1.28 | 1.20 | +$48 | +9.6% | 11.9% |
| BTC 1h Price Action Intraday | 26 | 50.0% | 2.43 | 1.38 | +$46 | +9.2% | 10.1% |
| BTC 4h SMC Aggressive | 22 | 31.8% | 1.60 | 1.26 | +$36 | +7.1% | 9.2% |
| SOL 4h SMC Scalping | 17 | 52.9% | 4.08 | 1.69 | +$64 | +12.7% | 6.3% |
| BTC 1h Price Action Aggressive | 23 | 39.1% | 2.33 | 1.40 | +$46 | +9.2% | 13.3% |
| **Aggregate** | **237** | **43.0%** | **2.97** | **1.54** | **+$573** | **+11.5%** | **13.3%** |

**Every combo is profitable after the gate (10/10).** Top performers: SOL 4h SMC Aggressive (Sharpe 6.27, PF 2.39) and BTC 4h Breakout Intraday (Sharpe 6.03, 58.8% win, PF 2.14).

### 5.1 What the gate filters

| Symbol/TF | Raw signals | After Kronos | Filtered |
|---|---|---|---|
| BTCUSD 4h | 1,076 | 192 | 82.2% |
| ETHUSD 4h | 207 | 23 | 88.9% |
| SOLUSD 4h | 313 | 32 | 89.8% |
| BTCUSD 1h | 879 | 49 | 94.4% |
| **Total** | **2,075** | **237** | **88.6%** |

1H signals are filtered harder (94.4%) than 4H (82–90%) — shorter horizons are noisier, so a 12-bar forecast carries less conviction there. **Leverage/funding/contract caps from Report 1 still apply on top** — the gate changes *which* trades fire, not how they're sized.

---

## 6. OPTIONS + Kronos — INFERENCE ONLY (not measured)

> ⚠️ **No options×Kronos backtest exists.** This section is reasoning, clearly separated from the measured futures result above. Do not quote it as a result.

What we **can** say from measured data:
1. The gate lifts the **shared signal win-rate from 33.2% → 43.0% (+9.8pp)** and lifts directional PF from 0.96 → 1.54 (Report 5 = futures, measured).
2. Options PF (Report 1 §6) is **higher than futures PF wherever the signal already wins** because the payoff is convex (4h modeled options PF 1.47 vs futures 0.94; headline config 1.68–1.76 vs 1.29–1.33).

**The inference:** applying the same +9.8pp win-rate gate to the convex option payoff would push modeled option PF **above** the gated-futures PF, because convexity amplifies a higher-quality (higher win-rate) signal more than a linear one. Directionally: gated options ≳ gated futures on PF.

**Why this is not a number:** (a) no historical IV → theta path is modeled and optimistic; (b) the gate's *timing* interacts with theta (a blocked-then-allowed entry shifts DTE) in ways the futures replay doesn't capture; (c) Delta India option liquidity (thin OI, spread-gated) caps realizable convexity. **The honest position: options remain a convexity overlay; the gate should improve them, but this must be measured once the forward-IV recorder accrues data — it is not validated.**

---

## 7. What it takes to wire Kronos (currently absent)

| Component | File (to create) | Purpose |
|---|---|---|
| Gate engine | `backend/app/engines/kronos/gate.py` | Load model, predict, gate signals |
| Prediction cache | `backend/app/engines/kronos/cache.py` | Avoid recompute (predict every 24/48 bars) |
| Decision log | `backend/app/services/kronos_log.py` | Log gate decisions to SQLite for audit |
| Config | `backend/config/tracks.yaml` (Kronos block) | Thresholds, step intervals, model size |
| Deps | `torch`, `einops`, `huggingface_hub`, `safetensors` | CPU inference works; GPU optional |

**Phased rollout (proposed):**

| Phase | Timeline | Scope | Capital risk |
|---|---|---|---|
| 1 — Shadow | Wk 1–2 | Log predictions, no trade impact | None |
| 2 — Paper | Wk 3–4 | Gate enabled for paper only | Paper only |
| 3 — Live | Month 2 | Top 3 combos, 0.5% risk/trade | Small |
| 4 — Optimize | Month 3 | Fine-tune on Sterling parquet; tune thresholds | Model risk |

---

## 8. Risks (the reviewer's checklist)

| Risk | Severity | Mitigation |
|---|---|---|
| **Small sample** — 237 trades, ~8/month | High | Extend backtest history; validate in shadow before live |
| **Over-filtering** — 86% cut may drop valid trades | Medium | Track opportunity cost vs no-gate; tune thresholds |
| **Model staleness** — pre-trained weights don't adapt to regime shift | High | Decay tracker (rolling 90-day Sharpe); re-fine-tune quarterly |
| **Lookahead hygiene** — gate must use only bars ≤ entry | High | Predictions computed at bar i from bars ≤ i; verify in shadow logs |
| **Options unmeasured** — §6 is inference | High | Do not deploy options-on-Kronos until measured post forward-IV |
| **Latency** — 70s CPU/prediction | Low | GPU, or predict every 24 bars = minutes of slack |
| **New dependency** — torch + HF in prod | Low | Containerize, pin versions |

---

## 9. Verdict

**Kronos is a regime-aware conviction filter, not an alpha source.** Measured on futures/spot, adding a single gate layer (zero changes to signals or execution) turns the validated-combo book from **−$674 → +$573**, cuts worst-case drawdown **66% → 13%**, and lifts Sharpe **−0.31 → 2.97** — by trading **8×/month instead of 70×**. The futures/spot result is real but **thin (237 trades) and not yet wired**; the options uplift is **expected but unmeasured.** Path: shadow → paper → live, exactly as Report 3 lays out.

→ Side-by-side detail in [Report 3 — Before/After](./STERLING_TRADING_REPORT_BEFORE_AFTER.md).
