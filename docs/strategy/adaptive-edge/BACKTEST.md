# Adaptive Edge — Backtest / Validation

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

## Selection rule

No strategy-specific threshold may be selected on the final test set.

## Cost sensitivity

The economic gate must be monotonic with respect to execution cost:

```text
cost ↑ -> expected_net_value cannot ↑
```

## Reporting

Every backtest result must identify:

- strategy version
- formula IDs and versions
- data window
- feature availability semantics
- execution assumptions
- cost assumptions
- risk policy version
- mode policy version

Results without this provenance are not strategy evidence.
