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
- Trail: 1.25 ATR
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
- Nearest/weekly selection supported by the current implementation.
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

The core strategy implementation and the surrounding TrueData/liquidity controls are substantially implemented. The Adaptive Edge reconciliation is green with **141 tests passing**.

The ORB targeted suite is **not yet green**. The latest local verification had **15 passing and 5 failing tests**. The remaining failures are concentrated in ORB fixture/semantic alignment; the production liquidity and freshness gates must not be weakened merely to obtain a green test count.

A zero-threshold edge case in confidence calculation was also identified and locally guarded. That change remains part of the local follow-on work and must be validated before it is considered complete.

Therefore:

```text
Implemented
    !=
Production-ready automated trading
```

Automatic/live graduation remains blocked until the complete ORB signal, option, risk, execution, and historical option-replay gates are green.

## Exact next work

### 1. Signal fixtures and mathematical contract

Make the test fixture itself satisfy the strategy rather than weakening the strategy:

```text
opening-range breakout
+ VWAP alignment
+ VWAP slope alignment
+ ATR threshold
+ volume confirmation
+ TREND/EXPANSION regime
= valid signal
```

Add one test per gate and one test proving removal of each gate returns `NONE`.

Keep the opening range anchored to 09:15 IST even when the entry window changes.

### 2. Configuration validation

Decide and enforce whether zero `volume_multiplier` is legal. Preferred production behavior is to reject invalid zero thresholds at configuration validation rather than rely on a confidence-calculation special case.

### 3. Expiry semantics

Specify and test the exact meaning of `nearest`, `weekly`, and `any/all`. Use fixed dates in tests; do not use `datetime.now()` for deterministic expiry-selection tests.

### 4. TrueData contract

Complete deterministic tests for:

- stale quote;
- missing quote;
- crossed bid/ask;
- zero/invalid bid/ask;
- low OI;
- low volume;
- excessive spread;
- invalid DTE;
- invalid lot size.

The provider boundary must reject bad observations before order admission.

### 5. Risk/execution

Verify actual premium-domain stop/target translation, worst-case lot-based INR risk, partial fills, order rejection, retries, idempotency, restart recovery, protection arming, position reconciliation, and expiry square-off.

### 6. Historical option replay

Build option-level replay from real historical contracts and premiums. Include spread, slippage, charges, liquidity, expiry, partial fills, actual lot sizes, and quote availability. Never infer option P&L from underlying points alone.

### 7. Research validation

Run walk-forward and out-of-sample tests across distinct market regimes. Report expectancy, profit factor, drawdown, win/loss distribution, MAE, MFE, trade frequency, costs, and sensitivity to parameters.

### 8. Graduation gate

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
