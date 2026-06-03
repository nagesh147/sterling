# Sterling 2.0 Trading Engine Architecture
**Document Version:** 1.0.0
**Target:** Sterling Backend Engine / V2 Backtester

---

## 1. Executive Summary
The Sterling trading engine is a highly modular, quantitative trading architecture designed to separate **signal generation** from **execution risk management**. Instead of relying on monolithic trading scripts, the engine pieces together three distinct components to form a fully-qualified trade:

1. **Timeframe** (The Lens)
2. **Strategy** (The Trigger)
3. **Risk Profile** (The Exit Plan)

By decoupling these components, the engine is able to systematically cross-validate hundreds of permutations across Spot, Futures, and Options markets to find statistically significant, mathematically sound trading edges.

---

## 2. Component Breakdown

### 2.1 The Timeframe (The Lens)
Before applying any technical indicators, raw 1-minute OHLCV (Open, High, Low, Close, Volume) market data is grouped into higher timeframes. The engine evaluates 4 primary timeframes:
- **15-minute** (`15m`)
- **30-minute** (`30m`)
- **1-hour** (`1h`)
- **4-hour** (`4h`)

*Technical Aspect:* 
The resampling logic guarantees that indicators (like the ATR) adapt accurately to the timeframe being evaluated.

```python
def resample(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1-minute OHLCV to `rule` and recompute ATR(14) on the new bars."""
    if rule == "1min":
        return df_1m
    agg = df_1m.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["close"])
    agg["atr"] = atr14(agg)  # Recalculate Volatility per timeframe
    return agg
```

### 2.2 The Strategy (The Trigger)
The engine maintains a repository of pure, mathematical formulas designed to identify structural market anomalies. These are evaluated across the resampled data. The engine uses 5 core strategies, returning a vectorized boolean array (`True` for a buy signal, `False` for no action).

**Example 1: MA Crossover (Trend Following)**
Fires when the short-term moving average (9 EMA) crosses above the longer-term moving average (21 EMA).
```python
def signals_ma_crossover(df: pd.DataFrame) -> np.ndarray:
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bull = fast > slow
    # Only fire on the exact candle the cross occurs
    return (bull & ~bull.shift(1).fillna(False)).to_numpy()
```

**Example 2: Smart Money Concepts (SMC) Fair Value Gap**
Identifies institutional buying pressure by locating bullish Fair Value Gaps (where the current low is higher than the high of two bars ago).
```python
def signals_smc(df: pd.DataFrame) -> np.ndarray:
    # Bullish fair-value-gap: low of bar > high of bar two back
    gap = df["low"] - df["high"].shift(2)
    curr_bull = df["close"] > df["open"]
    return ((gap > 0) & curr_bull).fillna(False).to_numpy()
```

### 2.3 The Risk Profile (The Exit Plan)
A signal tells the engine *when* to buy, but a **Risk Profile** tells it *when* to sell. Sterling uses dynamic, volatility-adjusted Stop Loss (SL) and Take Profit (TP) parameters based on the Average True Range (ATR). 

The Engine supports three configurations:
1. **Scalping:** SL = `1.0 × ATR` | TP = `2.0 × ATR` (Fast in and out, high win rate)
2. **Intraday:** SL = `2.0 × ATR` | TP = `3.5 × ATR` (Standard trend catching)
3. **Aggressive:** SL = `1.5 × ATR` | TP = `4.5 × ATR` (Wide targets, seeking massive runners)

```python
def atr14(df: pd.DataFrame) -> pd.Series:
    """True-range ATR(14) calculation for dynamic risk mapping."""
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(14).mean()
```

---

## 3. The Engine Process Flow (End-to-End)

Once the engine selects a specific combination (e.g., `1h + SMC + Intraday`), it executes the trade through a highly-optimized, bar-by-bar simulation process.

### Step-by-Step Simulation Lifecycle:
1. **Locate Signal**: The engine identifies a `True` value in the signal array.
2. **Calculate Risk**: It captures the entry price and immediately calculates the exact dollar price for the Stop Loss and Take Profit using the current candle's ATR.
3. **Step Forward (First-Touch Scan)**: The engine moves forward in time, bar by bar. For every future bar, it checks the absolute `High` and `Low`.
    - If the `Low` touches the Stop Loss first → Trade is closed as a Loss.
    - If the `High` touches the Take Profit first → Trade is closed as a Win.
4. **Time Stop**: To prevent holding "dead" trades infinitely, the engine enforces a strict 200-bar maximum hold limit (`MAX_HOLD_BARS`). If neither SL nor TP is hit by bar 200, the trade is force-closed at market price.

*Technical Aspect: The Simulator Block*
```python
def simulate(df: pd.DataFrame, signals: np.ndarray,
             sl_mult: float, tp_mult: float) -> np.ndarray:
    
    close, high, low, atr = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["atr"].to_numpy()
    n = len(close)
    trades = []
    
    sig_idx = np.flatnonzero(signals) # Find all triggers
    sp = 0
    
    while sp < len(sig_idx):
        i = sig_idx[sp]
        sp += 1
        
        entry = close[i]
        sl = entry - sl_mult * atr[i]
        tp = entry + tp_mult * atr[i]
        end = min(i + 200, n - 1) # 200 Bar Time-Stop
        
        exit_price, exit_idx = close[end], end
        
        # Forward First-Touch Scan
        for j in range(i + 1, end + 1):
            if low[j] <= sl:
                exit_price, exit_idx = sl, j
                break
            if high[j] >= tp:
                exit_price, exit_idx = tp, j
                break
                
        # Calculate final PnL (accounting for trading fees)
        ret = (exit_price / entry) - 1.0 - 0.001 
        trades.append(ret)
        
        # Prevents overlapping positions - skips any signals that fired while in a trade
        while sp < len(sig_idx) and sig_idx[sp] <= exit_idx:
            sp += 1
            
    return np.asarray(trades)
```

## 4. Final Processing & Route Generation
Once the `simulate()` function has swept the entire history, it returns an array of pure percentage returns (e.g., `[-0.015, +0.035, -0.012, ...]`). 

The engine then runs a **Metrics Pipeline** on these returns to calculate:
- **Win Rate & Profit Factor**
- **Expectancy** (Statistical probability of making money on any given trade)
- **Sharpe Ratio** (Risk-adjusted edge)
- **Max Drawdown**

This data is finally passed out to the higher-order backtesting orchestrator (like `deriv_fut_opt_metrics.py`), which uses the trade entry/exit timestamps to mathematically model how those exact same timestamps would have performed in **Futures** (with leverage) and **Options** (applying Black-Scholes pricing models and Realism Constraints).

---
*Generated by Sterling V2 Auto-Documentation*
