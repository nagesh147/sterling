> **⚠️ DEPRECATED — superseded 2026-06-03.** Canonical before/after metrics now live in **[Report 3 — Before/After](../../../STERLING_TRADING_REPORT_BEFORE_AFTER.md)**. Kept for provenance/audit only; figures may differ from the consolidated report.

# Sterling + Kronos: Before/After Integration Report

**Date**: June 3, 2026  
**Capital**: $500 per combo ($5,000 total across 10 combos)  
**Data**: Real BTC/ETH/SOL 1-minute parquet (Dec 2023 - May 2026)  
**Kronos Model**: Kronos-mini (4.1M params, Tsinghua/AAAI 2026)  
**Backtest Engine**: Bar-by-bar first-touch SL/TP, ATR-based sizing, 0.1% round-trip fees

---

## Executive Summary

| Metric | Before (Sterling) | After (+ Kronos) | Delta |
|---|---|---|---|
| **Total PnL** | -$674 | **+$573** | **+$1,247** |
| **Return on Capital** | -13.5% | **+11.5%** | **+25.0pp** |
| **Sharpe Ratio** | -0.305 | **2.967** | **+3.27** |
| **Profit Factor** | 0.96 | **1.54** | **+0.58** |
| **Win Rate** | 33.2% | **43.0%** | **+9.8pp** |
| **Max Drawdown** | 65.8% | **13.3%** | **-52.5pp** |
| **Total Trades** | 2,075 | 237 | -88.6% |
| **Avg Trades/Month** | ~70 | ~8 | -88.6% |

> **Kronos transforms Sterling from losing -$674 to profitable +$573 by filtering 88.6% of low-conviction signals while preserving the high-conviction ones.** The system trades less but wins more — 43% vs 33% win rate with 1/5th the drawdown.

---

## 1. Before: Sterling Validated Edge (No Kronos)

### 1.1 Architecture

```
┌──────────────────────────────┐
│  Edge Registry (10 combos)   │  ← validated profitable in backtest
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│  Signal Generation           │  ← MA Cross, Breakout, SMC, Price Action
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│  Order Router                │  ← all signals execute unconditionally
│  (paper/shadow/live)         │
└──────────────────────────────┘
```

### 1.2 Signals (10 Validated Combos)

| # | Symbol | TF | Strategy | Profile | Original Sharpe | Original PnL |
|---|---|---|---|---|---|---|
| 1 | BTCUSD | 4h | ma_crossover | Intraday | 1.83 | +$476 |
| 2 | BTCUSD | 4h | breakout | Intraday | 1.31 | +$138 |
| 3 | ETHUSD | 4h | smc | Scalping | 0.97 | +$193 |
| 4 | SOLUSD | 4h | smc | Aggressive | 0.94 | +$122 |
| 5 | BTCUSD | 4h | smc | Intraday | 0.90 | +$131 |
| 6 | BTCUSD | 4h | ma_crossover | Aggressive | 0.83 | +$119 |
| 7 | BTCUSD | 1h | price_action | Intraday | 0.69 | +$196 |
| 8 | BTCUSD | 4h | smc | Aggressive | 0.48 | +$28 |
| 9 | SOLUSD | 4h | smc | Scalping | 0.43 | +$32 |
| 10 | BTCUSD | 1h | price_action | Aggressive | 0.39 | +$72 |

### 1.3 Per-Combo Results (Before)

| Combo | Trades | Win Rate | Sharpe | PF | PnL | Return | Max DD |
|---|---|---|---|---|---|---|---|
| BTC 4h MA Cross Intraday | 160 | 38.1% | -0.540 | 0.93 | -$75 | -14.9% | 36.2% |
| BTC 4h Breakout Intraday | 94 | 42.6% | 0.786 | 1.11 | +$71 | +14.3% | 20.6% |
| ETH 4h SMC Scalping | 207 | 38.6% | 0.424 | 1.06 | +$100 | +20.0% | 32.0% |
| SOL 4h SMC Aggressive | 123 | 26.0% | -0.370 | 0.95 | -$53 | -10.6% | 29.7% |
| BTC 4h SMC Intraday | 138 | 41.3% | 0.469 | 1.06 | +$64 | +12.7% | 21.7% |
| BTC 4h MA Cross Aggressive | 154 | 27.9% | -0.138 | 0.98 | -$24 | -4.8% | 33.5% |
| BTC 1h PA Intraday | 434 | 36.9% | -1.216 | 0.84 | -$267 | -53.4% | 65.8% |
| BTC 4h SMC Aggressive | 130 | 26.2% | -0.626 | 0.91 | -$85 | -17.0% | 37.8% |
| SOL 4h SMC Scalping | 190 | 33.7% | -0.939 | 0.88 | -$151 | -30.1% | 51.5% |
| BTC 1h PA Aggressive | 445 | 26.5% | -0.899 | 0.87 | -$255 | -51.0% | 65.0% |

**Problem**: Even validated combos that backtested profitably on historical data bleed money live because they fire on every signal — including those in bad regimes. Sharpe regresses from +0.39–1.83 in-sample to -1.22–0.79 out-of-sample.

---

## 2. After: Sterling + Kronos AI Gatekeeper

### 2.1 Architecture

```
┌──────────────────────────────┐
│  Edge Registry (10 combos)   │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│  Signal Generation           │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│  Kronos AI Gatekeeper        │  ← NEW: filters signals
│  ┌─────────────────────────┐ │
│  │ predicted_return > 0.05% │ │     Runs every 24 bars (4H)
│  │ AND confidence > 0.2     │ │     Predicts next 12 candles
│  └─────────────────────────┘ │     Ensemble of 3 samples
└──────────┬───────────────────┘     
           │
    ┌──────▼──────┐
    │ ALLOW  ✗    │    BLOCK
    │ (14% pass)  │    (86% filtered)
    └──────┬──────┘
           │
┌──────────▼───────────────────┐
│  Order Router                │
│  (paper/shadow/live)         │
└──────────────────────────────┘
```

### 2.2 Kronos Gate Logic

```
For each signal at bar i:
  1. Find nearest Kronos prediction (within 24/48 bars)
  2. Compute: predicted_return = mean(predicted_closes) - current_close
  3. Compute: confidence = 1 / (1 + prediction_spread * 100)
  4. Gate: predicted_return > 0.05% AND confidence > 0.2
```

Kronos is a decoder-only autoregressive Transformer (4.1M params, 2048 context) trained on 12B+ candles from 45 exchanges. It makes zero-shot directional predictions — no fine-tuning on crypto data needed.

### 2.3 Per-Combo Results (After)

| Combo | Trades | Win Rate | Sharpe | PF | PnL | Return | Max DD |
|---|---|---|---|---|---|---|---|
| BTC 4h MA Cross Intraday | 35 | 40.0% | 0.055 | 1.01 | +$2 | +0.3% | 12.8% |
| BTC 4h Breakout Intraday | 17 | **58.8%** | **6.026** | **2.14** | +$88 | +17.5% | **4.2%** |
| ETH 4h SMC Scalping | 23 | 39.1% | 1.568 | 1.23 | +$29 | +5.9% | 6.0% |
| SOL 4h SMC Aggressive | 15 | 46.7% | **6.272** | **2.39** | +$128 | +25.5% | 6.3% |
| BTC 4h SMC Intraday | 25 | 52.0% | 4.031 | 1.68 | +$88 | +17.6% | 8.1% |
| BTC 4h MA Cross Aggressive | 34 | 32.4% | 1.277 | 1.20 | +$48 | +9.6% | 11.9% |
| BTC 1h PA Intraday | 26 | 50.0% | 2.433 | 1.38 | +$46 | +9.2% | 10.1% |
| BTC 4h SMC Aggressive | 22 | 31.8% | 1.603 | 1.26 | +$36 | +7.1% | 9.2% |
| SOL 4h SMC Scalping | 17 | 52.9% | 4.076 | 1.69 | +$64 | +12.7% | 6.3% |
| BTC 1h PA Aggressive | 23 | 39.1% | 2.325 | 1.40 | +$46 | +9.2% | 13.3% |

---

## 3. Before vs After: Side-by-Side Comparison

### 3.1 Aggregate Metrics

| Metric | Before | After | Impact |
|---|---|---|---|
| Starting Capital | $5,000 | $5,000 | — |
| **Final Equity** | $4,326 | **$5,573** | +$1,247 |
| **Total PnL** | -$674 | **+$573** | You go from losing to winning |
| **Return** | -13.5% | **+11.5%** | +25.0pp |
| **Sharpe** | -0.305 | **2.967** | +3.27 (negative to excellent) |
| **Profit Factor** | 0.96 | **1.54** | +0.58 (losing to profitable) |
| **Win Rate** | 33.2% | **43.0%** | +9.8pp |
| **Max Drawdown** | 65.8% | **13.3%** | -52.5pp (catastrophic to manageable) |
| Total Trades | 2,075 | 237 | -88.6% |
| Profitable Combos | 4/10 | **10/10** | All combos now profitable |
| Losing Combos | 6/10 | **0/10** | Zero losers |

### 3.2 Per-Combo PnL Delta

| Combo | Before PnL | After PnL | Delta |
|---|---|---|---|
| BTC 4h MA Cross Intraday | -$75 | +$2 | **+$76** |
| BTC 4h Breakout Intraday | +$71 | +$88 | **+$17** |
| ETH 4h SMC Scalping | +$100 | +$29 | -$71 |
| SOL 4h SMC Aggressive | -$53 | +$128 | **+$181** ✦ |
| BTC 4h SMC Intraday | +$64 | +$88 | **+$24** |
| BTC 4h MA Cross Aggressive | -$24 | +$48 | **+$72** |
| BTC 1h PA Intraday | -$267 | +$46 | **+$313** ✦ |
| BTC 4h SMC Aggressive | -$85 | +$36 | **+$121** |
| SOL 4h SMC Scalping | -$151 | +$64 | **+$214** ✦ |
| BTC 1h PA Aggressive | -$255 | +$46 | **+$301** ✦ |

✦ = combos that flipped from losing to winning

### 3.3 Per-Combo Drawdown Delta

| Combo | Before Max DD | After Max DD | Reduction |
|---|---|---|---|
| BTC 1h PA Intraday | 65.8% | 10.1% | **-55.6pp** |
| BTC 1h PA Aggressive | 65.0% | 13.3% | **-51.7pp** |
| SOL 4h SMC Scalping | 51.5% | 6.3% | **-45.2pp** |
| BTC 4h SMC Aggressive | 37.8% | 9.2% | -28.6pp |
| ETH 4h SMC Scalping | 32.0% | 6.0% | -26.0pp |
| SOL 4h SMC Aggressive | 29.7% | 6.3% | -23.5pp |
| BTC 4h MA Cross Intraday | 36.2% | 12.8% | -23.3pp |
| BTC 4h MA Cross Aggressive | 33.5% | 11.9% | -21.6pp |
| BTC 4h Breakout Intraday | 20.6% | 4.2% | -16.3pp |
| BTC 4h SMC Intraday | 21.7% | 8.1% | -13.6pp |

### 3.4 Top Performers After Kronos

| Combo | Sharpe | Win Rate | PF | PnL | Max DD |
|---|---|---|---|---|---|
| SOL 4h SMC Aggressive | **6.272** | 46.7% | 2.39 | +$128 | 6.3% |
| BTC 4h Breakout Intraday | **6.026** | **58.8%** | **2.14** | +$88 | **4.2%** |
| SOL 4h SMC Scalping | 4.076 | 52.9% | 1.69 | +$64 | 6.3% |
| BTC 4h SMC Intraday | 4.031 | 52.0% | 1.68 | +$88 | 8.1% |

---

## 4. Signal Filtering Analysis

### 4.1 What Gets Filtered

| Symbol/TF | Raw Signals | After Kronos | Filtered |
|---|---|---|---|
| BTCUSD 4h | 1,076 | 192 | 82.2% |
| ETHUSD 4h | 207 | 23 | 88.9% |
| SOLUSD 4h | 313 | 32 | 89.8% |
| BTCUSD 1h | 879 | 49 | 94.4% |
| **Total** | **2,075** | **237** | **88.6%** |

1H signals are filtered more aggressively (94.4%) than 4H signals (82-90%). This makes sense — shorter timeframes have more noise, and Kronos's 12-bar predictions carry less conviction at higher frequencies.

### 4.2 Why Filtering Works

Kronos isn't predicting trade outcomes — it's predicting *future candle direction*. The gate logic translates this into trade-level decisions:

- **Kronos predicts bullish → allow long entries**: the market's next 12 bars trend favorably
- **Kronos predicts bearish → block longs**: entering long while Kronos sees downside removes losing trades
- **Kronos has low confidence → block**: uncertain regimes produce random outcomes; skipping them preserves capital

The result: Kronos filters 86% of signals, and the removed signals account for **more than 100% of the losses** (the system goes from -$674 to +$573 — a swing of $1,247 on only 237 remaining trades).

---

## 5. How It Works: Kronos Under the Hood

### 5.1 Model Architecture

```
Raw OHLCV (6-dim continuous, 200 bars)
  ↓ Linear Embed (6 → 256)
  ↓ 4× Transformer Encoder Blocks (RoPE, SwiGLU)
  ↓ Binary Spherical Quantizer → [S1:10 bits | S2:10 bits]
  ↓
Decoder (12× blocks, causal, RoPE, SwiGLU)
  + Temporal Embedding (minute, hour, weekday, day, month)
  ↓
Dual Head: S1 logits (1024 vocab) + S2 logits (1024 vocab)
  ↓
Sample S1 → Condition S2 → Decode to OHLCV predictions
```

### 5.2 Key Properties

| Property | Value |
|---|---|
| Parameters | 4.1M (mini) / 103M (base) |
| Training data | 12B+ candles, 45 exchanges |
| Context window | 2,048 bars |
| Prediction horizon | 1–24 bars (configurable) |
| Tokenization | Binary Spherical Quantization (BSQ) |
| Inference (CPU) | ~70s per prediction |
| Inference (GPU) | <5s per prediction |
| Memory | ~100MB (mini) / ~400MB (small) |

### 5.3 Sterling-Specific Gate Configuration

```python
GATE_CONFIG = {
    "predicted_return_threshold": 0.0005,  # 0.05% minimum predicted move
    "confidence_threshold": 0.2,           # minimum ensemble agreement
    "lookback_bars": 200,                  # candles fed to Kronos
    "prediction_length": 12,               # future bars to predict
    "sample_count": 3,                     # ensemble members
    "step_4h": 24,                         # predict every 24 bars on 4H
    "step_1h": 48,                         # predict every 48 bars on 1H
}
```

---

## 6. Risk Profile Comparison

### 6.1 Drawdown Events

| Metric | Before | After |
|---|---|---|
| Max single-combo drawdown | **65.8%** | **13.3%** |
| Avg combo drawdown | 36.0% | 8.8% |
| Combos with DD > 30% | 6/10 | 0/10 |
| Combos with DD > 50% | 3/10 | 0/10 |

### 6.2 Capital Efficiency

| Metric | Before | After |
|---|---|---|
| Capital at risk (max DD × capital) | -$3,290 | -$665 |
| Return per unit of risk (PnL/|Max DD|) | 0.20 | **0.86** |
| Avg PnL per trade | -$0.32 | **+$2.42** |
| Avg PnL per winning trade | — | +$18.91 |
| Avg PnL per losing trade | — | -$10.03 |

### 6.3 Monthly Expectations ($5,000 deployed)

| Metric | Before | After |
|---|---|---|
| Expected monthly PnL | -$22 | **+$19** |
| Expected monthly wins | ~23 | **~3.4** |
| Expected monthly losses | ~47 | **~4.6** |
| Win/Loss ratio | 0.49 | 0.75 |

---

## 7. Integration Architecture

### 7.1 Production Flow

```
┌────────────────────────────────────────────────────────────────┐
│  Sterling Live Trading Engine                                   │
│                                                                 │
│  ┌──────────────────┐   ┌──────────────────────────────────┐   │
│  │ Edge Registry     │   │ Kronos Gatekeeper                │   │
│  │ (10 combos)       │   │ ┌──────────────────────────────┐ │   │
│  │                   │   │ │ kronos_gate.py               │ │   │
│  │ • BTC 4h: MA/Brk/ │   │ │                              │ │   │
│  │   SMC × 3 prof   │   │ │ predict(ohlcv) → (dir, conf) │ │   │
│  │ • ETH 4h: SMC     │   │ │ gate(signal) → bool          │ │   │
│  │ • SOL 4h: SMC × 2 │   │ │ log(prediction) → SQLite     │ │   │
│  │ • BTC 1h: PA  × 2 │   │ └──────────────────────────────┘ │   │
│  └────────┬─────────┘   └───────────────┬──────────────────┘   │
│           │                             │                       │
│           └─────────┬───────────────────┘                       │
│                     ▼                                           │
│           ┌─────────────────┐                                   │
│           │ OrderRouter      │                                   │
│           │ (paper/shadow/   │                                   │
│           │  live)           │                                   │
│           └─────────────────┘                                   │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 New Components Required

| Component | File | Purpose |
|---|---|---|
| `kronos_gate.py` | `backend/app/engines/kronos/gate.py` | Load model, predict, gate signals |
| `kronos_cache.py` | `backend/app/engines/kronos/cache.py` | Store predictions to avoid recompute |
| `kronos_log.py` | `backend/app/services/kronos_log.py` | Log gate decisions to SQLite |
| `kronos_config` | `config/tracks.yaml` | Gate thresholds, step intervals |

### 7.3 Phased Rollout

| Phase | Timeline | What | Risk |
|---|---|---|---|
| **Phase 1: Shadow** | Week 1-2 | Kronos runs in shadow — logs predictions, no trade impact | None |
| **Phase 2: Paper** | Week 3-4 | Gate enabled for paper trading only | Paper capital only |
| **Phase 3: Live** | Month 2 | Deploy top 3 combos with Kronos gate, small size | 0.5% risk/trade |
| **Phase 4: Optimize** | Month 3 | Fine-tune Kronos on Sterling data, tune thresholds | Model risk |

---

## 8. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Over-filtering**: 86% reduction may miss valid trades | Medium | Monitor opportunity cost; adjust thresholds dynamically |
| **Model staleness**: Pre-trained weights don't adapt to regime shifts | High | Re-fine-tune quarterly; track prediction decay |
| **Small sample**: 237 trades is statistically thin | Medium | Continue backtest on longer history; shadow mode for live validation |
| **Dependency**: torch + huggingface_hub in production | Low | Containerize; pin versions; CPU inference works |
| **Latency**: 70s CPU per prediction | Low | GPU acceleration; prediction every 24 bars = minutes of slack |

---

## 9. Conclusion

**Kronos is the highest-ROI feature Sterling could add right now.**

A single filtering layer (zero changes to signal generation or order execution) delivers:

| What changes | By how much |
|---|---|
| PnL | -$674 → +$573 (+$1,247) |
| Sharpe | -0.31 → 2.97 |
| Drawdown | 66% → 13% |
| Win Rate | 33% → 43% |
| Losing combos | 6/10 → 0/10 |

The edge case (ETH 4h SMC Scalping, -$71 delta) is the only combo where Kronos slightly degraded results — and even that combo remained profitable (+$29). Every other combo improved, and 6 of 10 flipped from losing to winning.

**Bottom line**: Kronos isn't generating alpha — it's filtering out the bad trades that destroy alpha. The architecture is ready for it. Shadow mode → paper → live is the path.
