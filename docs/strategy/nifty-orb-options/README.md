# NIFTY ORB + VWAP Options Strategy

## Scope

NIFTY 50 directional option buying strategy implemented alongside SuperTrend and Adaptive Edge. The signal is generated from the NIFTY underlying; CE/PE is the execution vehicle.

```text
NIFTY 5m bars
    |
    +-- 09:15-09:30 opening range
    +-- VWAP alignment + VWAP slope
    +-- ATR-normalized breakout
    +-- volume confirmation
    +-- trend/expansion regime
    v
LONG / SHORT / NO TRADE
    |
    +-- ATM CE / PE (optional ITM)
    +-- liquidity gates
    +-- risk sizing
    +-- premium-domain protection
    v
universal Trading Mode -> Kite safety + protection path
```

## Execution ownership

NIFTY ORB does not define its own Paper/Live switch. The active Kite account's universal Trading Mode controls Paper/Live, and the universal Manual/Auto setting controls who places orders. The ORB-specific `enabled` flag controls only whether this signal engine generates signals.

A strategy-local `paper_only` field is intentionally rejected.

## Default configuration

- Strategy: disabled on fresh installation
- Interval: 5 minutes
- Opening range: 15 minutes
- Entry window: 09:30-12:00 IST
- Breakout threshold: 0.15 ATR
- Volume confirmation: 1.15x recent average
- VWAP slope: required in the signal direction
- Option: ATM
- Max risk: ₹3,000/trade
- Max trades: 2/day
- Max spread: 1.5% of mid
- Minimum option volume: 1,000
- Minimum open interest: 10,000
- Execution: Kite
- Execution mode: universal Paper/Live + Manual/Auto
- Data source: Kite

## Automatic lifecycle

When universal Auto is enabled, the ORB runner evaluates active connected Kite accounts during market hours. It reuses the same live-safety/idempotency and position-protection infrastructure as SuperTrend. Daily trade count and the last executed signal are persisted, and an active NIFTY ORB position blocks another concurrent ORB entry.

## API

```text
GET  /api/v1/config/nifty-orb-options
PUT  /api/v1/config/nifty-orb-options
POST /api/v1/config/nifty-orb-options/snapshot
POST /api/v1/config/nifty-orb-options/backtest
POST /api/v1/config/nifty-orb-options/execute
```

`execute` uses the active account's universal Paper/Live mode. It does not have a strategy-local paper flag.

## Backtest integrity

The deterministic backtest is the **underlying signal-validation layer**. It must not be presented as historical options P&L. Production-grade option replay requires historical option contracts and premiums, brokerage, statutory charges, bid/ask slippage, option liquidity, IV changes, expiry-day behavior, contract roll/selection, partial fills and actual lot sizes.

No fabricated option P&L is generated when those data are unavailable.

## Graduation criteria

The strategy should only graduate to automatic/live execution after out-of-sample and walk-forward tests demonstrate positive expectancy after costs and stable drawdown across market regimes.
