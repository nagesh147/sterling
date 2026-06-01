# Sterling Derivatives Engine: Architecture & Logic

## 1. How are strike prices selected? (Strictly Option Buying)
The `strike_picker.py` engine is exclusively designed for **Option Buying (Long Calls / Long Puts)**. Selling options is strictly vetoed at the architectural level to eliminate unlimited risk.
Strike prices are selected through a multi-factor scoring system (0-100) applied to the option chain:
*   **Moneyness (Delta) [30%]**: Targets a "sweet spot" Delta (typically 0.35 to 0.65). It avoids deep out-of-the-money (OTM) lottery tickets which have too low delta, and deep in-the-money (ITM) strikes which are too expensive.
*   **Time to Expiry (DTE) [20%]**: Filters out options expiring too soon (theta decay cliff) or too late (low leverage).
*   **Liquidity & Spread [15%]**: Penalizes strikes with wide bid-ask spreads or low open interest.
*   **Gamma & Theta [15%]**: Optimizes for high gamma (explosiveness) while penalizing excessive theta decay (for longer holds).
*   **GEX Influence [20%]**: Uses Gamma Exposure (GEX) to identify high-interest zones. Strikes near positive Gamma walls receive a score boost, while those near toxic/pinning strikes are penalized.

## 2. How are Greek values considered when selecting a strike price?
Greeks are dynamically weighted based on the strategy's expected holding timeframe:
*   **Scalping (1-5m)**: High weight on **Gamma** (needs explosive moves) and **Delta** (needs price responsiveness). Theta is largely ignored since the hold time is minutes.
*   **Intraday (15m-1h)**: Balanced Delta and Gamma. Theta starts to carry a slight penalty.
*   **Swing (4h-1d+)**: High penalty for **Theta** (time decay). Moderate Delta is preferred to avoid premium destruction.
*   **Vega**: If the IV is extremely high compared to the ATM IV (Volatility Skew > 15%), the strike is heavily penalized to avoid entering a trade prone to sudden IV Crush.

## 3. Is a Trailing Stop-Loss (SL) used? How?
Yes, the `TrailingStopEngine` (in `trailing_stop.py`) employs a monotonic ratchet trailing stop, meaning the stop-loss only ever moves in the trade's favor.
*   **Base Trail**: Uses a multiplier of ATR (Average True Range) or a percentage offset.
*   **Progressive Squeeze (Timeframe-Adaptive)**: As the trade achieves higher Risk-to-Reward (R) multiples (e.g., 1R, 2R, 3R), the trailing distance tightly squeezes. Scalping squeezes much faster than Swing trading.
*   **Options-Specific Adjustments**:
    *   **GEX Awareness**: If the market is in a Positive GEX regime (pinning/mean-reversion likely), the trailing stop is squeezed by 20% to lock in profits before the reversal. If Negative GEX (momentum/trend likely), the trail widens by 25% to let the runner go.
    *   **IV Crush / Theta Guard**: If IV drops violently (>15%), or if theta burn is high, the trail tightens by 25-40% to protect the remaining premium.

## 4. How does the system determine whether to trade Options vs Futures?
The `instrument_chooser.py` engine calculates a **Composite Routing Score** (0-100). If the score is > 55, it routes to Options; otherwise, it routes to Futures.
*   **Volatility Regime**: High IV Rank (>60%) or expected Volatility Expansion favors Options. Low IVR favors Futures.
*   **Time Horizon**: Ultra-short scalps often route to Futures (no theta decay, instant execution). Overnight holds favor Options (defined risk).
*   **Gamma Exposure (GEX)**: Positive GEX (choppy/pinning) favors Options (if buying at boundaries) or Futures (for tight scalps). Negative GEX (trending) heavily favors Options (convexity).

## 5. How does Gamma Exposure (GEX) influence trading decisions?
The `gex_engine.py` aggregates total market open interest and gamma to identify:
*   **Total GEX**: Measures overall market dealer positioning.
*   **Zero Gamma Flip**: The level where dealer hedging flips from stabilizing (mean-reverting) to destabilizing (momentum-amplifying).
*   **Call/Put Walls**: Massive OI concentrations that act as price magnets or heavy resistance/support.
*   **Pinning Gate**: If the asset is near expiry (≤ 2 days) and the spot price is within 1.5% of a Call/Put Wall with high GEX, the system **vetoes** the option entry to prevent "pinning risk" (where the option expires worthless near the wall).

## 6. How does the Leverage Engine adapt to different timeframes?
The `leverage_engine.py` limits maximum leverage based on the expected holding duration to balance capital efficiency against liquidation risk:
*   **Scalping**: Up to 50x (tight stops, requires purchasing power).
*   **Intraday**: Up to 35x.
*   **Swing/Positional**: Capped strictly at 15x-20x to survive larger wicks and overnight funding rate fluctuations.

## 7. What happens to the SL/TP when the Option Premium falls but the Spot Price hasn't hit SL?
The `sl_tp_solver.py` uses a **Hybrid Invalidation Framework**:
*   The system continually evaluates both the **Underlying Asset Spot Price** and the **Option Premium Mark**.
*   A **BSM (Black-Scholes-Merton) projection** determines what the option premium *should* be at the spot Stop-Loss level.
*   If the Option Premium falls below this projected BSM Stop-Loss (e.g., due to sudden IV crush or severe theta decay), the position is exited, *even if the Spot Price hasn't formally hit the spot stop loss*.
*   However, a `premium_floor_pct` (e.g., 50%) is enforced to prevent premature exits due to mere bid-ask spread noise.

## 8. How is volatility (IV) crush risk mitigated?
*   **Entry Vetoes**: The system measures Current IV against a rolling IV Rank (IVR). If IVR > 85%, long options are vetoed entirely because they are statistically overpriced.
*   **Skew Correction**: Individual strikes are penalized if their local IV is excessively higher than the At-The-Money (ATM) IV.
*   **Dynamic SL Buffering**: In high-volatility regimes (IV > 60%), the calculated BSM Stop-Loss is padded (widened by an extra 10-20%) because standard BSM underestimates the sudden harshness of IV crush.
