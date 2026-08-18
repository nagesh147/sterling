# NIFTY ORB + VWAP Directional Options

## Contract

The strategy generates direction from the NIFTY 50 underlying and uses a CE/PE only as the execution vehicle.

```text
NIFTY 50 -> ORB + VWAP + ATR + regime -> LONG/SHORT/NONE
                                      -> CE/PE selection
                                      -> risk sizing
                                      -> Kite execution
```

## Default configuration

- Signal interval: 5 minutes
- Opening range: 15 minutes (09:15-09:30 IST)
- Entry window: 09:30-12:00 IST
- Breakout threshold: 0.15 ATR
- Volume confirmation: 1.15x prior-volume baseline
- ATR period: 14
- Initial stop buffer: 0.10 ATR
- Trail: 1.25 ATR
- Target: 2R
- Option: ATM
- Maximum risk: Rs 3,000/trade
- Maximum trades: 2/day
- Data source: **Kite**
- Alternative data source: **TrueData**
- Execution broker: **Kite**
- Live execution: disabled by default (`paper_only=true`)

## Signal rules

LONG requires:

1. Current bar is inside the configured entry window.
2. Close is above the opening-range high by at least the configured ATR threshold.
3. Price is above VWAP.
4. VWAP slope is positive over the configured lookback.
5. Volume meets the configured multiplier.
6. Regime is TREND or EXPANSION.

SHORT mirrors the conditions below the opening-range low.

A RANGE regime produces no trade.

## Option selection

For LONG, select CE. For SHORT, select PE. Contracts are selected from the nearest eligible expiry and configured ATM/ITM moneyness. The option is not used to generate the directional signal.

## Risk

Risk is calculated from the underlying entry/stop distance and the configured INR risk budget. The execution quantity is constrained by lot size and the maximum risk budget.

## Backtest integrity

The baseline signal backtest reports underlying-point/R statistics. It must not be presented as historical option P&L. True option replay requires historical option premiums/contracts and must model spread, slippage, charges, expiry, liquidity and available contracts.

## Provider architecture

Kite and TrueData feed the same canonical bar/option representations. Switching the market-data provider must not change the execution broker. Execution remains routed through the existing Kite safety/protection path.

## Production graduation criteria

Do not enable live execution until the strategy has a sufficiently large out-of-sample option-level sample and demonstrates stable profit factor, expectancy and drawdown after costs and slippage across market regimes.
