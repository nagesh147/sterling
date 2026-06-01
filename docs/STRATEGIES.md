# Sterling Trading Strategies

This document outlines the underlying logic, configuration, and execution flows for the primary trading strategies deployed within the Sterling trading engine.

## 1. Price Action (VCP & Momentum)
**Type:** Directional & Breakout
**Engine:** `DirectionalOrchestrator` / `VCPExecutor`

### Logic
The Price Action strategy primarily focuses on Volatility Contraction Patterns (VCP) and pure momentum breakouts. 
- **VCP:** Identifies periods of contracting volatility (tighter consolidation ranges and lower volume) followed by an expansion (breakout with volume). It uses ATR (Average True Range) compression as a proxy for the contraction phase.
- **Momentum:** Monitors fast-moving price action against VWAP and EMA bands. 

### Signal Generation
- A signal is armed when price breaks a local resistance/support level with a predefined volume multiplier.
- Validated by the `snapshot_cache` to ensure the macro regime (`macro_regime`) is not `RANGING` or `VOLATILE` (unless playing a mean reversion setup).
- Requires a strong ADX (Average Directional Index) reading (e.g., ADX > 25) to confirm trend presence before taking directional breakout trades.

---

## 2. Smart Money Concepts (SMC)
**Type:** Liquidity & Order Block
**Engine:** `DirectionalOrchestrator` / `SMCScanner`

### Logic
SMC focuses on institutional footprints left on the chart, such as Fair Value Gaps (FVG), Order Blocks (OB), and liquidity sweeps. 
- **Fair Value Gaps (FVG):** Detects 3-candle patterns where a significant price imbalance occurs. The strategy sets limit orders at the FVG zone for a retracement entry.
- **Liquidity Sweeps:** Identifies swing highs/lows that are breached briefly (stop hunts) before the price reverses, signaling a liquidity grab.

### Signal Generation
- A "Sweep" event is recorded when price takes out a previous high/low but fails to close beyond it.
- An "Order Block" is formed at the origin of a strong displacement move.
- Signals are generated when price retraces into an unmitigated OB or FVG. The signal strength is amplified if it aligns with the higher timeframe trend (`st_trends` - SuperTrend alignment).

---

## 3. Moving Average (MA) Crossover
**Type:** Trend Following
**Engine:** `DirectionalOrchestrator` / `MACrossExecutor`

### Logic
A classic trend-following model utilizing multiple moving averages (typically EMAs) to detect trend shifts and continuations.
- Usually configured as a fast/slow EMA pair (e.g., 9 EMA and 21 EMA).
- Often combined with a baseline macro filter (e.g., 200 SMA) to ensure trades are only taken in the direction of the long-term trend.

### Signal Generation
- **Golden/Death Cross:** A signal triggers when the fast EMA crosses the slow EMA.
- **Pullback Continuation:** Instead of buying the initial cross (which can be prone to whipsaws), the strategy often arms on the cross and triggers when price pulls back to the fast EMA and rejects, providing a better Risk/Reward entry.
- Signals are vetoed if the ADX indicates a weak or non-existent trend (ADX < 20).

---

## Strategy Orchestration & Routing

All generated signals from these models are aggregated into the `DirectionalOrchestrator`. 
1. **Scoring:** The orchestrator scores the signals based on confluence (e.g., if SMC and MA Cross both point Long, the score increases).
2. **Veto Checks:** Evaluates `snapshot_cache` for systemic vetoes (e.g., high funding rates, extreme RSI).
3. **Execution Routing:** The signal is passed to the `OrderRouter`, which checks the `algo_router_mode` (`paper`, `shadow`, or `live`) and submits the order to the respective exchange client (e.g., `DeltaIndiaClient`).

---

## Derivatives Verification & Live IV Modeling

Behind the scenes, Sterling supports an advanced derivatives pricing matrix that evaluates routing signals to linear (Futures) or convex (Options) execution depending on mathematical expectancy derived from real-time Implied Volatility (IV) surface fits.

### 1. Live IV Streaming & Persistence
- **Socket Ingestion:** Instead of relying on static Black-Scholes approximations or lagging historical volatility, Sterling ingests live options chains via WebSockets (e.g., `DeltaIVManager`).
- **Surface Modeling:** The engine continuously calculates and fits a mathematical surface (`iv_surface_fit.py`) accounting for both **term-structure** and **skew** across strikes and expirations. 
- **Backtest Replayability:** These 5-coefficient surface variables are archived to SQLite (`iv_surface_params`). When simulating, the engine queries this preserved IV surface to highly accurately price historical options scenarios.

### 2. Futures vs. Options Routing Logic
By default, strategies are optimized for linear Futures logic. However, the system runs side-by-side models for options routing:
- **The Options Leg:** Modeled dynamically (e.g., long ATM calls for long-only momentum setups). Downside risk is strictly capped to the initial premium allocation (e.g., 5-10% of portfolio), insulating the account from catastrophic flash-crashes.
- **Timeframe Convexity (The 4H Edge):** Backtesting over 12,000 permutations reveals that options drastically outperform futures exclusively on **high timeframes (4h+)** within strategies like `ma_crossover`. On smaller intraday frames (15m/30m), options underperform due to severe theta decay and bid-ask spread drag. On the 4h, directional price moves are large enough to break even on premium decay and drive exponential returns.
- **Config Sweet-Spots:** Extensive vector simulations show that targeting **7 DTE** options with a **10% premium allocation** offers the highest balanced Profit Factor (PF > 1.9) and win rate retention for these trending structures.
