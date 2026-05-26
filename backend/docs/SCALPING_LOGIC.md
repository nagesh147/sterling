# Scalping Strategy Engine

The Sterling scalping engine evaluates price action on the **15-minute timeframe** strictly around **4-Hour key levels** (support and resistance). It operates three independent strategy modules concurrently. If any of the strategies detect a confirmed setup near a 4H level, a `ScalpingSignal` is emitted.

This document details the logic and provides core code snippets for each strategy.

---

## Strategy 1: Price Action (`price_action.py`)

This strategy looks for classic chart patterns forming directly at or near 4H levels. The detection logic is intentionally relaxed to accommodate cryptocurrency market noise (e.g., allowing slight deviations in "flat" tops or bottoms).

### Bullish Patterns (at 4H Support)
- **Ascending Triangle**: Flat top, rising lows. Breakout above the flat top.
- **Double Bottom**: Two dips near the same price. Breakout above the valley high (neckline).
- **Bullish Consolidation**: Tight range above support with the close near the top of the range.

### Bearish Patterns (at 4H Resistance)
- **Descending Triangle**: Flat bottom, declining highs. Breakout below the flat bottom.
- **Double Top**: Two peaks near the same price. Breakout below the valley low (neckline).
- **Bearish Consolidation**: Tight range below resistance with the close near the bottom of the range.

### Code Snippet: Double Bottom Detection
```python
def detect_double_bottom(
    highs: NDArray, lows: NDArray, closes: NDArray, lookback: int
) -> Optional[dict]:
    # Find the lowest point
    sorted_indices = np.argsort(lows[-lookback:])
    bottom_idx = int(sorted_indices[0])
    bottom_val = float(lows[-lookback:][bottom_idx])
    
    # Find the second bottom: must be >= 3 bars away and within 2% of the first
    second_idx = None
    for idx in sorted_indices[1:]:
        idx = int(idx)
        if abs(idx - bottom_idx) < 3:
            continue
        if abs(float(lows[-lookback:][idx]) - bottom_val) / max(bottom_val, 1e-6) < 0.02:
            second_idx = idx
            break
            
    if second_idx is None:
        return None
        
    # Neckline = highest point between the two bottoms
    lo_idx, hi_idx = min(bottom_idx, second_idx), max(bottom_idx, second_idx)
    neckline = round(float(np.max(highs[-lookback:][lo_idx:hi_idx + 1])), 4)
    
    # Current close must be at or above neckline (breakout confirmation)
    if closes[-1] < neckline * 0.998:
        return None
        
    return {
        "pattern": "double_bottom",
        "direction": "long",
        "neckline": neckline,
        "stop_below": bottom_val,
    }
```

---

## Strategy 2: Smart Money Concepts / SMC (`smc.py`)

This strategy focuses on liquidity sweeps (stop hunts) followed by immediate momentum shifts, commonly known as **Inducement + Imbalance**.

### Bullish Setup (at 4H Support)
1. **Inducement (Sweep)**: Price wicks below the 4H support level, sweeping liquidity (false breakdown).
2. **Imbalance (Displacement)**: A subsequent strong bullish candle where the body engulfs the entire range of the previous candle.

### Bearish Setup (at 4H Resistance)
1. **Inducement (Sweep)**: Price wicks above the 4H resistance level, sweeping liquidity (false breakout).
2. **Imbalance (Displacement)**: A subsequent strong bearish candle where the body engulfs the entire range of the previous candle.

### Code Snippet: Bullish SMC Logic
```python
# Look for an inducement bar, followed by a bullish imbalance candle
for i in range(n - lookback, n):
    if closes[i] <= opens[i]:
        continue  # skip bearish candles — we need a bullish imbalance
        
    body = closes[i] - opens[i]
    prev_range = highs[i - 1] - lows[i - 1]
    
    # Imbalance check: current bullish body > previous candle's range * ratio
    if body < prev_range * cfg.smc_imbalance_ratio * 0.5:
        continue
        
    # Inducement check: look for a wick below support in the window before this candle
    inducement_found = False
    for j in range(max(n - lookback, 0), i):
        if lows[j] < level_price * (1 - tol * 0.5):
            inducement_found = True
            break
            
    if inducement_found:
        # Valid bullish SMC signal
        direction = "long"
        pattern = "bullish_imbalance"
        entry = round(float(closes[i]), 4)
        stop_loss = round(float(lows[i]) * 0.999, 4)
        break
```

---

## Strategy 3: Moving Average Crossover (`ma_crossover.py`)

A classic trend-following trigger applied contextually at key support/resistance zones. It uses a Fast Simple Moving Average (SMA, default 5) and a Slow Exponential Moving Average (EMA, default 9).

### Bullish Crossover (at 4H Support)
- **Condition**: SMA(5) crosses above EMA(9) within the last 3 bars while near a 4H support zone.
- **Entry**: Immediate on confirmation.
- **Stop Loss**: Placed below the lowest point of the 4H support zone (last 20 4H bars).

### Bearish Crossover (at 4H Resistance)
- **Condition**: SMA(5) crosses below EMA(9) within the last 3 bars while near a 4H resistance zone.
- **Entry**: Immediate on confirmation.
- **Stop Loss**: Placed above the highest point of the 4H resistance zone (last 20 4H bars).

### Code Snippet: Crossover Evaluation
```python
sma = rolling_sma(closes, fast)
ema = rolling_ema(closes, slow)

# Check for recent crossover (within last 3 bars) — more practical than exact bar
recent_cross_bull = False
recent_cross_bear = False

for j in range(i - cross_bars + 1, i + 1):
    if sma[j] > ema[j] and sma[j - 1] <= ema[j - 1]:
        recent_cross_bull = True
    if sma[j] < ema[j] and sma[j - 1] >= ema[j - 1]:
        recent_cross_bear = True

if nearby.level_type == "support" and cfg.allow_long:
    if recent_cross_bull:
        # Fresh bullish crossover near support — ARMED, can execute
        direction = "long"
        pattern = "sma_cross_above_ema"
        entry = round(current_price, 4)
        support_zone_low = round(float(np.min([c.low for c in candles_4h[-20:]])), 4) 
        stop_loss = round(support_zone_low * 0.999, 4)
```

---

## Execution Routing
If any strategy produces a valid signal (`entry_ok = True`), the engine formulates a complete Trade Plan (Entry, Stop Loss, Take Profit) and pushes it to the execution router (`OrderRouter`). Depending on the system's active `algo_router_mode`, the trade will be simulated (Paper), logged via exchange validation (Shadow), or executed directly on the live exchange.
