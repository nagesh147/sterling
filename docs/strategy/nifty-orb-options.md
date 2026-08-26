# NIFTY ORB + VWAP Directional Options

## Contract

NIFTY ORB is an independent directional **option-buying** strategy. It generates direction from the NIFTY 50 underlying and uses the option only as the execution vehicle.

```text
NIFTY 5m completed bars
        |
        +--> 09:15-09:30 opening range
        +--> VWAP + VWAP slope
        +--> ATR-normalized breakout
        +--> volume confirmation
        +--> TREND / EXPANSION regime
        |
        v
   LONG / SHORT / NONE
        |
        +--> LONG  -> BUY CE
        +--> SHORT -> BUY PE
        +--> NONE  -> NO ORDER
        |
        v
liquidity -> expiry -> lot sizing -> protection -> universal execution
```

There is no option selling and no cross-strategy signal input.

## Default configuration

- Strategy: **disabled** on fresh installation
- Signal interval: 5 minutes
- Opening range: 15 minutes (09:15-09:30 IST)
- Entry window: 09:30-12:00 IST
- Breakout threshold: 0.15 ATR
- Volume confirmation: 1.15x recent baseline
- VWAP slope lookback: 3 bars
- ATR period: 14
- Initial stop buffer: 0.10 ATR
- Trailing: owned by the universal Trading Mode, not by ORB
- Target: 2R
- Option: ATM
- ITM/OTM steps: 1
- Maximum risk: ₹3,000/trade
- Maximum trades: 2/day
- Expiry DTE: 0-7 days
- Maximum spread: 1.5% of mid
- Minimum option volume: 1,000
- Minimum open interest: 10,000
- Quote freshness: 15 seconds when enabled
- Primary/default data source: Kite
- Advanced alternative: TrueData
- Execution broker: Kite
- Execution mode: universal Trading Mode

## Implemented logic

### Signal

A LONG requires all of the following:

1. A completed bar is available.
2. The current bar is inside the configured entry window.
3. Close exceeds the 09:15 opening-range high by at least `min_breakout_atr * ATR`.
4. Close is above VWAP.
5. VWAP slope is positive.
6. Volume ratio meets the configured threshold.
7. Regime is `TREND` or `EXPANSION`.

SHORT mirrors the logic below the opening-range low with negative VWAP slope.

`RANGE`, `UNKNOWN`, unavailable ATR, missing opening-range bars, or failed filters produce no directional trade.

### Option selection

- LONG -> CE only.
- SHORT -> PE only.
- ATM/ITM/OTM supported.
- Configurable strike steps.
- DTE bounds enforced.
- Expiry-day avoidance supported.
- `expiry_selection` is one of `nearest`, `weekly`, `monthly`, `any`.
- Weekly/monthly are separated by an explicit calendar rule: the monthly
  contract is the last occurrence of that expiry's weekday in its calendar
  month, overridable by passing the venue's real monthly-expiry set. An expiry
  preference that matches nothing raises instead of falling back to another
  bucket.
- All DTE decisions take an explicit reference date, so replay and live agree.
- Lot size must be positive.
- Premium must be positive.
- Bid/ask, spread, OI, volume, and quote-freshness gates are configurable.

### Risk

- Quantity is whole-lot aligned.
- Risk is constrained by the INR risk budget.
- Underlying stop/target levels are represented separately from premium-domain protection.
- Direction and selected option type must agree.

## TrueData policy

TrueData advanced data is used where it improves **data quality and execution-vehicle selection**, not as a replacement directional strategy.

```text
Underlying bars
    -> ORB/VWAP/ATR/regime signal

TrueData advanced option observations
    -> bid/ask
    -> spread
    -> OI
    -> volume
    -> quote freshness
    -> contract quality

Both
    -> risk sizing
    -> execution admission
```

This keeps ORB independent from Adaptive Edge while still exploiting TrueData where the additional observations are causally relevant.

## Execution ownership

ORB does not own Paper/Live or Manual/Auto controls.

```text
ORB enabled   -> signal generation ON/OFF
Paper / Live  -> universal account mode
Manual / Auto -> universal execution mode
```

Automatic execution uses the shared safety, idempotency, order, reconciliation, and position-protection infrastructure. A strategy-local `paper_only` control is intentionally forbidden.

## Current implementation status

The ORB targeted suite is **green: 178 passing, 0 failing**. No production filter
was weakened to get there.

Closed since the previous revision:

| Area | What changed |
| --- | --- |
| Configuration | `StrategyConfig.validate()` rejects every out-of-range value, including the `volume_multiplier=0` that both disabled volume confirmation and divided by zero. It runs at `generate_signal`, `select_option`, `build_trade_plan`, `filter_chain` and the config PUT, and `set_config` delegates its shared rules to it so the API and the engine cannot drift. |
| Signal diagnosis | A rejected bar named "filters not aligned". It now names the first unmet gate, and each gate has an isolating test. |
| Expiry semantics | `nearest`/`weekly`/`monthly`/`any` are defined against an explicit calendar rule shared by the engine and the TrueData provider. Weekly no longer falls back to a monthly contract. |
| Determinism | DTE takes an explicit reference date instead of the wall clock, so the expiry suite is pinned to fixed dates. |
| Provider boundary | Every required TrueData data-quality check raises rather than returning a sentinel a caller could mistake for a valid empty result. |
| Costed validation | `validate_option_trades` reported net figures under `gross_profit` and built `profit_factor` from them. Gross and net are now separate and every decision metric is net. |
| Option replay | Next-bar fills, half-spread on each side, `lots * lot_size` sizing, live-mirroring liquidity admission, volume-capped partial fills, expiry square-off, statutory charges on turnover, and refusals returned as data. |

Still open, and still blocking:

```text
Implemented and unit-green
    !=
Production-ready automated trading
```

### 1. Execution truth (open)

Signal-to-order idempotency, duplicate execution attempts, broker rejection,
partial fill and remaining quantity, position reconciliation, restart recovery,
protection arming and disarming, expiry square-off at the broker, and daily
trade-limit persistence. Partial fills and expiry are modelled in *replay*; the
live order path still needs its own end-to-end coverage.

### 2. Research validation (open)

Walk-forward and out-of-sample runs across distinct regimes on real historical
option data. The replay engine can now produce honest numbers -- expectancy,
net and gross profit factor, drawdown, MAE, MFE, consecutive losses, exit-reason
mix, partial-fill count -- but no historical option dataset has been replayed
through it yet. Until it has, there is **no evidence of edge**, only evidence
that the measurement is sound.

### 3. Graduation gate (open)

Do not enable unattended live execution until:

```text
ORB tests green
      |
      v
TrueData tests green
      |
      v
risk/execution replay green
      |
      v
historical option replay green
      |
      v
walk-forward + OOS stable
      |
      v
cost/slippage validated
      |
      v
production safety review
      |
      v
LIVE AUTOMATION ELIGIBLE
```

## Backtest integrity

The underlying ORB backtest is a signal-validation layer. It must not be represented as historical option P&L.

Option-level performance requires actual historical option contracts/premiums and realistic transaction costs, spread, slippage, liquidity, expiry, contract availability, and execution timing.

## Production graduation criteria

Do not enable automatic/live execution merely because the signal engine is enabled. Require deterministic replay, a sufficiently large out-of-sample option-level sample, positive expectancy after realistic costs, stable drawdown, and robustness across market regimes.

See `docs/strategy/nifty-orb-options/README.md` for the implementation audit and exact next-step program.
