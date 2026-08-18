# NIFTY ORB + VWAP Directional Options

## Contract

The strategy generates direction from the NIFTY 50 underlying and uses a CE/PE only as the execution vehicle.

```text
NIFTY 50 -> ORB + VWAP + ATR + regime -> LONG/SHORT/NONE
                                      -> CE/PE selection
                                      -> risk sizing
                                      -> universal Kite execution mode
```

## Default configuration

- Strategy: **disabled** on fresh installation
- Signal interval: 5 minutes
- Opening range: 15 minutes (09:15-09:30 IST)
- Entry window: 09:30-12:00 IST
- Breakout threshold: 0.15 ATR
- Volume confirmation: 1.15x prior-volume baseline
- VWAP slope: required in the signal direction
- ATR period: 14
- Initial stop buffer: 0.10 ATR
- Trail: 1.25 ATR
- Target: 2R
- Option: ATM
- Maximum risk: Rs 3,000/trade
- Maximum trades: 2/day
- Maximum spread: 1.5% of mid
- Minimum option volume: 1,000
- Minimum open interest: 10,000
- Data source: **Kite**
- Alternative: **TrueData**
- Execution broker: **Kite**
- Execution mode: **universal Trading Mode** (Paper/Live + Manual/Auto)

## Execution ownership

NIFTY ORB does **not** own a paper/live switch. The active Kite account owns Paper/Live, and the universal Trading Mode owns Manual/Auto. This prevents contradictory execution controls between signal engines.

The strategy's own `enabled` flag answers only whether NIFTY ORB may generate signals.

```text
Strategy enabled?  -> ORB signal engine ON/OFF
Paper / Live?      -> universal account mode
Manual / Auto?     -> universal execution mode
```

Automatic execution runs through the same live-safety, idempotency, Kite order and position-protection infrastructure used by SuperTrend. A strategy-local `paper_only` setting is intentionally forbidden.

## Signal rules

LONG requires:

1. Current bar is inside the configured entry window.
2. Close is above the opening-range high by at least the configured ATR threshold.
3. Price is above VWAP.
4. VWAP slope is positive over the configured lookback.
5. Volume meets the configured multiplier.
6. Regime is TREND or EXPANSION.

SHORT mirrors these conditions below the opening-range low, including a negative VWAP slope.

A RANGE regime produces no trade.

## Option selection and liquidity

For LONG, select CE. For SHORT, select PE. Contracts are selected from the nearest eligible expiry and configured ATM/ITM moneyness. The option is not used to generate the directional signal.

Before a contract can be selected for execution it must have a valid bid/ask, acceptable spread, minimum volume and minimum open interest. The quantity is lot-aligned and constrained by the INR risk budget.

## Protection and lifecycle

The generated plan contains both underlying risk levels and premium-domain protection levels. Automatic execution registers the position through the existing protection subsystem so broker GTT and/or server-side monitoring follow the universal `stop_mode` configuration. Existing reconciliation, expiry square-off and position monitoring remain responsible for the resulting open position.

The ORB background runner is multi-tenant, processes only active connected Kite accounts, is market-hours gated, and isolates failures per account. Daily trade count and the last executed signal are persisted so a process restart cannot reset the daily limit.

## Backtest integrity

The baseline signal backtest reports underlying-point/R statistics. It must not be presented as historical option P&L. True option replay requires historical option premiums/contracts and must model spread, slippage, charges, expiry, liquidity and available contracts.

## Provider architecture

Kite and TrueData feed the same canonical bar/option representations. Switching the market-data provider must not change the execution broker. Execution remains routed through the existing Kite safety/protection path.

## Production graduation criteria

Do not enable automatic/live execution merely because the signal engine is enabled. Require a sufficiently large out-of-sample option-level sample and demonstrate stable profit factor, expectancy and drawdown after costs and slippage across market regimes.
