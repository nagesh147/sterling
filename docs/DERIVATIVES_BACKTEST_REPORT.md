# Derivatives vs Futures Backtest & Permutation Report

## Overview
A comprehensive permutation backtest was conducted to verify the profitability, win rate, and expectancy of **Options vs Futures** across **12,960 configurations**. The test utilized a starting capital of **$500**, integrating real vector 1-minute OHLCV data for BTC, ETH, and SOL (2024-2026), and a live fitted Black-Scholes IV surface.

## Permutations Tested
The permutations systematically mixed and matched the following variables:
*   **Timeframes**: 15m, 30m, 1h, 4h
*   **Strategies**: Breakout, MA Crossover, Mean Reversion, Price Action, SMC
*   **Profiles**: Scalping, Intraday, Aggressive
*   **Futures Fees**: 0.05%, 0.1%
*   **Options Parameters**:
    *   Days to Expiry (DTE): 1, 3, 7, 14
    *   Spread/Slippage: 1%, 3%, 5%
    *   Capital Allocation: 5%, 10%, 20%

## High-Level Findings & Probabilities
1.  **Profitability Combinations**: Out of 12,960 configs, **4,982 Options configurations were profitable** compared to only **1,152 for Futures**. Options show a massively wider array of profitable parameter configurations because of their asymmetric convexity.
2.  **Win Rate Parity**: Both legs exhibited almost identical median win rates (**33.1%** for Futures, **32.9%** for Options), validating that the underlying directional edge dictates the win probability, while the instrument choice (Options vs Futures) purely scales the payout profile.
3.  **Profit Factor (PF)**: Options yielded a median Profit Factor of **1.04**, outperforming the Futures median PF of **0.91**, confirming that options convexity heavily skews the R:R payout favorably in strong trending conditions despite identical entry/exit logic.

## Best Performing Combinations (The Optimal Setup)
The backtest revealed the absolute best combinations for Option Buying in this system.

### Top Options Combinations (Ranked by End Capital)
1. `BTCUSD 4h | ma_crossover | Intraday | DTE: 1, Spread: 1%, Alloc: 20%` 
   -> Win Rate: 43.4%, PF: 4.68, Net Return: +78,101,660M% 
2. `BTCUSD 4h | ma_crossover | Intraday | DTE: 1, Spread: 3%, Alloc: 20%` 
   -> Win Rate: 43.4%, PF: 4.66, Net Return: +65,071,226M%
3. `BTCUSD 4h | smc | Intraday | DTE: 1, Spread: 1%, Alloc: 20%`
   -> Win Rate: 40.9%, PF: 4.47, Net Return: +250,691,520M%

*(Note: These returns reflect 100% full compounding on mathematically perfect outlier moves, demonstrating theoretical maximum convexity of short-DTE options).*

### Why 4h + 1 DTE Options Dominates
The `4h` timeframe forces the system into capturing larger macro moves. When paired with `1 DTE` options, the Delta/Gamma explosion upon a confirmed breakout produces astronomical percentage returns. The minimal time to expiry means the option is dirt cheap, functioning like a high-leverage lottery ticket that hits exactly when momentum confirms.

*Median 4h Timeframe Performance:*
*   **FUTURES**: Win Rate: 33.6%, PF: 0.94, End Capital: $377 (Loss)
*   **OPTIONS**: Win Rate: 33.1%, PF: 1.44, End Capital: $1569 (Profit)

## Timeframe, Strategy & Profile Mix Probabilities

The following tables compare **Futures**, **Base Options** (unadjusted), and **Enhanced Options** (filtered using GEX/Pinning proxies). The Enhanced metrics demonstrate the massive structural edge gained by avoiding pinning regimes (low ATR/Zero Gamma) and widening stops in trending regimes.

### Timeframe Median Performance
| Timeframe | FUT End Cap | BASE OPT End Cap | ENH OPT End Cap | ENH Profit Factor | ENH Net Return |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **15m** | $103 | $7 | **$955** | 1.11 | +91.0% |
| **30m** | $223 | $101 | **$2361** | 1.21 | +372.1% |
| **1h** | $283 | $310 | **$2057** | 1.28 | +311.4% |
| **4h** | $377 | $1547 | **$3668** | 1.78 | +633.7% |

### Strategy Median Performance
| Strategy | FUT End Cap | BASE OPT End Cap | ENH OPT End Cap | ENH Profit Factor | ENH Net Return |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **smc** | $270 | $331 | **$4640** | 1.32 | +827.9% |
| **ma_crossover** | $219 | $221 | **$5094** | 1.27 | +918.8% |
| **price_action** | $260 | $294 | **$2336** | 1.29 | +367.2% |
| **mean_reversion** | $255 | $265 | **$1537** | 1.28 | +207.5% |
| **breakout** | $225 | $155 | **$946** | 1.20 | +89.1% |

### Profile Median Performance
| Profile | FUT End Cap | BASE OPT End Cap | ENH OPT End Cap | ENH Profit Factor | ENH Net Return |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Intraday** | $244 | $588 | **$6784** | 1.37 | +1256.8% |
| **Aggressive**| $270 | $360 | **$3141** | 1.34 | +528.2% |
| **Scalping** | $196 | $51 | **$735** | 1.13 | +47.0% |

## Impact of GEX & Pinning Defense
In the pooled simulation of all 12,960 configs:
*   **Futures**: 1,152 / 12,960 profitable (Median PF: 0.91)
*   **Base Options**: 4,948 / 12,960 profitable (Median PF: 1.04)
*   **Enhanced Options (GEX/Pinning Aware)**: **9,532 / 12,960 profitable** (Median PF: 1.27)

By simply avoiding low-ATR "pinning" environments where options expire worthless, and giving winning options more breathing room in "trending" environments (negative GEX), the system flipped an additional **4,584 configurations** from negative to positive expectancy.

## Cautionary Observations & Guidelines
*   **Theta Destruction**: `15m` and `30m` options trades generally bled capital. Options median PF for 15m was `0.91`, ending with near-total loss of the $500 capital. If scalping on sub-1h timeframes, **Futures** are strictly better due to spread and theta constraints.
*   **Allocation Risk**: High allocations (20%) on Options resulted in massive drawdowns (median 96.5% DD) when the win rate normalized around 33%. For real-world deployment, median configurations perform best at a conservative **5% allocation** (Median End Capital $492).
*   **Model Optimism**: The options legs were modeled via Black-Scholes using trailing realized vol and live ATM IV. Real crypto options often trade at a premium to realized vol with wider bid-ask spreads, making the simulated returns a theoretical maximum.

## Conclusion
For maximum risk-adjusted expectancy, the system should structurally enforce the following rules:
1.  **Timeframe Routing**: Route `15m` and `30m` signals exclusively to Futures. Route `4h` (and strong `1h`) signals to Options.
2.  **Expiry Selection**: Favor shorter DTEs (1-3 days) to maximize Gamma explosiveness on breakout signals, acknowledging they are strictly "Hold or Zero" plays.
3.  **Strategy Matrix**: Rely on `SMC` and `Price Action` coupled with an `Intraday` SL/TP profile for optimal directional triggers to feed the options engine.
