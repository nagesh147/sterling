# Adaptive Edge v0.1.0 — Backtest / Validation

## Purpose

Validate the reconstructed research model against historical Kite data before any paper or live execution.

## Parity requirement

The same strategy formula implementation must execute in historical and live environments.

Only adapters differ:

```text
historical market adapter
historical execution model
simulated clock

vs

live market adapter
broker execution
live clock
```

## Replay contract

The deterministic replay engine consumes already-fetched observations and does not call Kite or a broker.

Each replay bar requires:

```text
close
spread_bps
ATR
trend
momentum
relative_volume
volatility_expansion
expected_move
confidence
staleness
session state
```

## Execution assumptions

```text
BUY  -> ask-side reference + adverse slippage
SELL -> bid-side reference + adverse slippage
round-trip fee applied to traded notional
non-overlapping positions in v0.1.0
cooldown after exit
```

## Required validation

Before live authorization:

1. causal/lookahead audit
2. deterministic unit tests
3. execution-cost sensitivity
4. boundary tests
5. out-of-sample evaluation
6. walk-forward validation where applicable
7. fill/reconciliation tests
8. mode/risk invariant tests
9. accounting/profit-giveback tests
10. paper/shadow/live parity review

## Robustness gates

### Cost monotonicity

```text
execution cost ↑ -> expected net value cannot ↑
```

### Risk monotonicity

Under the v0.1.0 risk schedule, higher volatility, lower confidence, or greater drawdown must not increase authorized risk when other inputs are held constant.

### Parameter sensitivity

A result that exists only at one exact parameter point is rejected as fragile.

### Regime robustness

Report results separately for trending, ranging, high-volatility, and low-volatility periods.

### Out-of-sample integrity

Threshold selection cannot use the final evaluation period. Use chronological development/validation/holdout periods.

## Reporting provenance

Every result must identify:

- strategy version
- formula IDs and versions
- data window
- feature availability semantics
- execution assumptions
- cost assumptions
- risk policy version
- mode policy version

Results without this provenance are not strategy evidence.

## Current state

```text
Model implementation        READY FOR RESEARCH REPLAY
Deterministic replay         IMPLEMENTED
Historical Kite wiring       NEXT
OOS validation               BLOCKED until data run
Paper execution              BLOCKED
Live execution               BLOCKED
```

Passing unit tests is not evidence of profitability.
