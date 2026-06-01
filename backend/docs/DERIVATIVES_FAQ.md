# Derivatives Engine FAQ & Behind-the-Scenes

This document explains the inner workings, rules, and mathematical frameworks driving the **Sterling Universal Derivatives Engine** for Delta Exchange India (BTC & ETH).

## Core Philosophy
- Strictly **long options only** (no naked selling or credit spreads).
- All decisions are driven by **underlying index spot price** as the primary reference.
- The engine is fully adaptive across timeframes: Scalping → Intraday → Overnight → Positional → Swing.
- Combines Greeks (via adjusted Black-Scholes), Liquidity Defense, Dealer Hedging Flow (GEX), Gamma Flip, and Max Pain.

---

## 1. How are strike prices selected?
The `Universal Strike Picker` (`strike_picker.py`) evaluates all valid strikes across allowed DTE bands using a **composite multi-factor score**. 

It always uses the **live underlying crypto index price** (not option premium) as the anchor for moneyness, delta, and Greeks. This prevents distortion from wide spreads or temporary premium spikes.

The picker simulates expected R-multiple by running a **time-shifted Black-Scholes revaluation** at the `expected_hold_minutes` horizon to account for theta decay realistically.

**Option Selling**: Strictly forbidden. Only long calls (bullish) or long puts (bearish).

---

## 2. How are Greek values considered when selecting a strike price?
Greeks are calculated via **Black-Scholes Model** (with crypto adjustments for volatility skew and jumps) and weighted dynamically by timeframe:

- **Delta Proximity** (core anchor): Targets 0.40–0.60 range. Avoids deep OTM (low gamma) and deep ITM (high premium cost).
- **Gamma**: Heavily weighted in short-term profiles (scalping/intraday) for explosive convexity on fast moves.
- **Theta**: Strong penalty in longer holds (positional/swing) to minimize time decay bleed.
- **Vega / IVR**: Defensive gate. Penalizes high IVR strikes (>70th percentile) to avoid immediate IV crush.
- **Skew Edge**: Adjusts scoring to exploit crypto’s typical put-skew (downside options often richer).

---

## 3. How is the trailing stop-loss used?
The `TrailingStopEngine` (`trailing_stop.py`) uses a **non-linear monotonic ratchet** (never moves backward).

- **Base Trail**: Hybrid of ATR, Supertrend, and volatility-adjusted percentage.
- **Progressive Tightening**: Trail distance squeezes as profit increases (e.g., 0.75× at +1R, 0.5× at +2R).
- **Stepped Profit Locking**: Breakeven at +1R, +1R locked at +2R, partial scale-out at +2R+.
- **Options Guards**: Rapid IV crush or high theta burn triggers aggressive tightening (e.g., ×0.6 multiplier).

**GEX Influence**: Tighter trail in Positive GEX (pinning likely). Wider trail in Negative GEX (momentum potential).

---

## 4. How does the underlying spot price improve derivative selection?
Using the **underlying index price** ensures objective moneyness and Greek calculations. Option mark prices on Delta can be noisy due to low liquidity and sudden premium jumps. This approach keeps all theoretical pricing and risk metrics grounded in the true market structure.

---

## 5. What happens during sudden IV Crush?
The engine continuously monitors IV change. Upon detecting significant IV contraction, the `TrailingStopEngine` immediately applies a squeeze factor (e.g., 0.6×) to protect remaining extrinsic value, often exiting faster than a pure price-based stop would allow.

---

## 6. How does execution timeframe impact Greek weighting?
The `Universal Strike Picker` uses **timeframe-adaptive weights**. Short-term trades prioritize Gamma and short-term momentum. Longer-term trades penalize Theta heavily and favor strikes with better vega-to-theta ratios.

---

## 7. How is liquidity accounted for?
Hard filters via `LiquidityScore` run **before** Greek scoring:
- Bid-Ask spread, 1h/24h volume, and Open Interest must meet minimum thresholds.
- Illiquid contracts are immediately vetoed to prevent massive slippage on Delta Exchange.

---

## 8. Why is Time-Shifted BSM Revaluation necessary?
It projects the option’s value at the planned exit time using Black-Scholes. This bakes realistic theta decay into the Expected R-Multiple, preventing selection of options that look attractive now but will decay heavily by exit.

---

## 9. How does Gamma Exposure (GEX) & Dealer Hedging Flow influence the system?
Dealer hedging flow is the mechanical buying/selling of underlying futures by market makers to stay delta-neutral.

**GEX Formula**:
```python
GEX = Gamma × OI × Contract_Multiplier × (Underlying_Price²) × 0.01
```
- **Positive Net GEX**: Stabilizing flow → favors Options + tighter trailing stops.
- **Negative Net GEX**: Amplifying flow → favors strong momentum Options + wider trailing stops.

---

## 10. What is the Gamma Flip Level and how is it used?
The Gamma Flip is the underlying price where cumulative GEX crosses zero — the transition point between negative gamma (trending) and positive gamma (pinning) regimes.
The engine tracks this level dynamically from the option chain and uses it as:
- Dynamic support/resistance.
- Signal to adjust trailing stops or route instruments.
- Early warning for volatility regime shifts.

---

## 11. How does the system defend against Pinning Risk at Expiry?
The `pinning_gate.py` combines Max Pain and high GEX walls:

- **Max Pain**: Strike where maximum option value expires worthless.
If <48 hours to expiry and underlying is within 1.5% of Max Pain (or major Call/Put Wall), the system activates defense:
- Veto new entries.
- Tighten stops aggressively.
- Suggest early roll to next expiry.

This significantly reduces expiry-related losses common in crypto options.
