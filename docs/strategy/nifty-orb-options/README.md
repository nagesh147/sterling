# NIFTY ORB + VWAP Options Strategy

## Scope

NIFTY 50 directional option buying strategy implemented alongside SuperTrend and Adaptive Edge. The signal is generated from the NIFTY underlying; CE/PE is the execution vehicle.

```text
NIFTY 5m bars
    |
    +-- 09:15-09:30 opening range
    |
    +-- VWAP alignment
    |
    +-- ATR-normalized breakout
    |
    +-- volume confirmation
    |
    +-- trend/expansion regime
    v
LONG / SHORT / NO TRADE
    |
    +-- ATM CE / PE (optional ITM)
    |
    +-- underlying-derived stop
    |
    +-- R target + trailing protection
    v
existing Kite safety + protection path
```

## Data sources

The strategy supports:

- `kite` — default. Uses the existing Sterling Kite account/session and instrument/quote services.
- `truedata` — uses the existing TrueData historical client and option-chain API.

The data source controls market data only. Execution is fixed to Zerodha Kite so changing the market-data provider cannot change the broker order path.

Kite's official API supplies historical candles, quotes, instruments and orders, but does not expose a native option-chain endpoint; Sterling therefore builds the live NFO chain from the instrument master and quote endpoints. citeturn2search0turn2search5

TrueData provides option-chain fields including strike, CE/PE type, LTP, volume, OI, bid and ask. citeturn2search12

## Default configuration

- Interval: 5 minutes
- Opening range: 15 minutes
- Entry window: 09:30-12:00 IST
- Breakout threshold: 0.15 ATR
- Volume confirmation: 1.15x recent average
- Option: ATM
- Max risk: ₹3,000/trade
- Max trades: 2/day
- Execution: Kite
- Paper-only: enabled
- Data source: Kite

## API

```text
GET  /api/v1/config/nifty-orb-options
PUT  /api/v1/config/nifty-orb-options
POST /api/v1/config/nifty-orb-options/snapshot
POST /api/v1/config/nifty-orb-options/backtest
POST /api/v1/config/nifty-orb-options/execute
```

`execute` is blocked while `paper_only=true`.

## Backtest integrity

The included deterministic backtest is the **underlying signal-validation layer**. It must not be presented as an options P&L backtest.

A production-grade options backtest must replay historical option contracts and premiums for the selected expiry/strike, including:

- brokerage and statutory charges
- bid/ask slippage
- option liquidity
- IV changes
- expiry-day behavior
- contract roll/selection
- partial fills
- actual lot sizes

No fabricated option P&L is generated when those data are unavailable.

## Metrics

The engine reports:

- trades
- wins/losses
- win rate
- gross profit/loss
- profit factor
- expectancy
- average win/loss
- maximum drawdown
- net P&L

The acceptance target is not a specific win rate. The strategy should only graduate to live execution after out-of-sample and walk-forward tests demonstrate positive expectancy after costs and stable drawdown.
