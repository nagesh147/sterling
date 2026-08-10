# Adaptive Edge Formula Registry

Formula IDs are immutable identifiers. Changing a formula's meaning requires a new version and an explicit strategy change review.

## F-001 — Causal availability

```text
availability_time(x) <= decision_time
```

A decision may consume only information that was causally available at decision time.

## F-002 — Peak P&L

```text
PeakPnL(t) = max(CurrentPnL(τ)) for τ <= t
```

## F-003 — Profit giveback

```text
ProfitGiveback(t) = PeakPnL(t) - CurrentPnL(t)
```

## F-004 — Expected net value

```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

Holding other variables constant, increasing execution cost cannot increase expected net value.

## F-005 — Risk authorization immutability

Risk authorization is state, not a derived function of current P&L.

```text
AuthorizedRisk(t+1) > AuthorizedRisk(t)
```

is forbidden unless an explicitly specified risk-policy transition authorizes it.

## F-006 — Mode/risk independence

```text
DynamicMode != DynamicRisk
```

A mode transition alone cannot increase authorized risk.

## F-007 — Executable BUY reference

```text
BUY reference price = executable ASK
```

## F-008 — Executable SELL reference

```text
SELL reference price = executable BID
```

## Strategy-specific formulas — LOCKED OUT until recovered

These IDs are reserved. No implementation may invent their definitions.

```text
F-101  Feature normalization / feature score
F-102  Edge / prediction score
F-103  Opportunity eligibility
F-104  Dynamic-mode transition
F-105  Predictive-profit protection
F-106  Dynamic-risk schedule
F-107  Risk-per-unit
F-108  Position sizing
F-109  Instrument / option selection
F-110  Entry trigger
F-111  Exit trigger
F-112  Trailing / profit-protection parameterization
F-113  Re-entry
F-114  Multi-position interaction
```

## Formula contract

Every unlocked formula must be promoted with:

```text
Formula ID
Version
Definition
Inputs
Units
Availability timestamp semantics
Boundary conditions
Numerical safeguards
Owner module
Unit tests
Adversarial tests
Backtest parity test
```

Until that metadata exists, the formula is not production-authorized.
