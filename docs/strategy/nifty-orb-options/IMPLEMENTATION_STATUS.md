# NIFTY ORB Options — Implementation Status and Execution Plan

Date: 2026-08-20

## Status

**Implemented, but not approved for unattended automated options trading.**

The current implementation has the core ORB/VWAP/ATR signal path, option selection, liquidity controls, risk sizing, TrueData integration controls, and shared execution ownership.

The strategy remains a **long-options-only** system:

```text
LONG  -> BUY CE
SHORT -> BUY PE
NONE  -> NO ORDER
```

No option selling is permitted.

## Verified green

Adaptive Edge was reconciled with `main` and its dedicated suite reached:

```text
141 passed
0 failed
```

The ORB work is intentionally tested separately because ORB is an independent strategy and must not inherit Adaptive Edge signal semantics.

## ORB implementation currently present

### A. Market structure

- NIFTY underlying.
- 5-minute bars.
- IST normalization.
- 15-minute opening range anchored to 09:15 IST.
- Completed-bar protection for realtime callers.

### B. Signal model

- ORB breakout distance normalized by ATR.
- VWAP calculated from typical price and volume.
- Directional VWAP alignment.
- VWAP slope confirmation.
- Volume confirmation.
- TREND/EXPANSION regime requirement.
- RANGE/UNKNOWN produces no trade.
- Entry-window gate.

### C. Option model

- CE for LONG.
- PE for SHORT.
- ATM/ITM/OTM selection.
- Strike-step configuration.
- DTE bounds.
- Expiry-day avoidance.
- Liquidity filtering.
- Spread filtering.
- OI filtering.
- Volume filtering.
- Quote freshness filtering.

### D. Risk model

- Whole-lot quantity.
- INR risk ceiling.
- Underlying stop representation.
- Premium-domain protection fields.
- Maximum daily trade count.

### E. Data architecture

Kite and TrueData are normalized into the same ORB market-data representation. TrueData advanced observations are used for data quality and option-contract selection, not as an additional directional signal engine.

### F. Execution architecture

ORB does not own Paper/Live or Manual/Auto mode. It uses the universal account/execution mode and shared safety/idempotency/protection infrastructure.

## Current blocker

The latest local ORB targeted verification is not green. The latest run reported:

```text
15 passed
5 failed
```

The failures are primarily around test fixture semantics and the stricter canonical ORB contract. They must be fixed without weakening the production filters.

A zero `volume_multiplier` edge case also exposed a division-by-zero path in confidence calculation. A local guard has been added during the current work but still requires final validation and an explicit decision on whether zero is a legal configuration value.

## Exact next changes

### Step 1 — Repair signal fixtures

Create deterministic fixture bars that satisfy the complete canonical LONG and SHORT predicates.

LONG fixture must demonstrate:

```text
close > OR_high
close - OR_high >= min_breakout_atr * ATR
close > VWAP
VWAP_slope > 0
volume_ratio >= volume_multiplier
regime in {TREND, EXPANSION}
```

SHORT must mirror the inequalities.

Do not set `volume_multiplier=0` to make fixtures pass.

### Step 2 — Isolate every signal gate

Add independent tests for:

- entry window;
- OR breakout;
- ATR threshold;
- VWAP side;
- VWAP slope;
- volume;
- regime;
- completed-bar requirement;
- missing opening range.

Each failed prerequisite must produce `NONE` or a deliberate validation error.

### Step 3 — Validate configuration

Explicitly validate:

- interval > 0;
- opening-range duration > 0;
- valid entry window;
- ATR period > 0;
- slope lookback > 0;
- volume multiplier > 0 unless a zero value is intentionally specified as a supported bypass;
- max risk > 0;
- max trades > 0;
- spread >= 0;
- minimum volume/OI >= 0;
- DTE range valid.

Preferred behavior: invalid configuration is rejected at configuration validation rather than interpreted as a strategy bypass.

### Step 4 — Make expiry semantics explicit

Define:

- `nearest` = minimum eligible DTE;
- `weekly` = nearest eligible weekly contract according to an explicit expiry-calendar rule;
- `any/all` = no preference beyond eligibility.

Tests must use fixed dates and explicit expiry calendars.

### Step 5 — Complete TrueData contract

Canonical quote observation:

```text
symbol
quote_timestamp
ltp
bid
ask
volume
oi
```

Reject at the provider boundary when required:

```text
missing quote
stale quote
crossed market
non-positive premium
invalid bid/ask
insufficient OI
insufficient volume
excessive spread
invalid DTE
invalid lot size
```

The option candidate must not reach order admission after a failed required data-quality check.

### Step 6 — Complete execution truth

Test:

- signal-to-order idempotency;
- duplicate execution attempts;
- broker rejection;
- partial fill;
- remaining quantity;
- position reconciliation;
- restart recovery;
- stop/protection registration;
- stop/protection disarming;
- expiry square-off;
- daily trade-limit persistence.

### Step 7 — Build real option replay

The current underlying signal backtest is insufficient for automated options approval.

Build historical option replay with:

```text
underlying bars
+ actual option contract
+ actual option premium
+ bid/ask
+ spread
+ slippage
+ charges
+ lot size
+ liquidity
+ expiry
+ partial fills
+ execution timing
```

No synthetic option P&L from underlying points.

### Step 8 — Walk-forward and OOS

Evaluate across separate regimes and periods. Report:

- expectancy;
- profit factor;
- net P&L after costs;
- maximum drawdown;
- win rate;
- average win/loss;
- MAE;
- MFE;
- trade frequency;
- consecutive losses;
- parameter sensitivity.

Reject configurations that depend on narrow historical parameter choices.

### Step 9 — Production gate

Automation is eligible only when:

```text
ORB unit tests green
        |
        v
TrueData contract green
        |
        v
execution/reconciliation replay green
        |
        v
historical option replay green
        |
        v
walk-forward green
        |
        v
out-of-sample stable
        |
        v
realistic costs/slippage validated
        |
        v
production safety audit green
        |
        v
UNATTENDED LIVE ELIGIBLE
```

## Explicit design decisions

1. ORB remains independent from Adaptive Edge.
2. TrueData advanced data is used where it improves observation quality and option-contract selection, not to inject Adaptive Edge-style signal intelligence.
3. The underlying generates direction; the option is the execution vehicle.
4. Only option buying is permitted.
5. Shared execution infrastructure owns Paper/Live and Manual/Auto.
6. Backtests must not fabricate option P&L.
7. Safety and causal-data gates must not be removed to make tests or backtests look better.
