# Adaptive Edge Formula Registry

Formula IDs are immutable identifiers. Changing a formula's meaning requires a new version and an explicit strategy change review.

## Governing resolution contract

A strategy-specific formula is `RESOLVED` only when the authoritative definition **and every required input's semantics** are causal, versioned, testable, and complete.

The original V1.0 master strategy specification has been recovered. Therefore F-101..F-114 are `SOURCE-RECOVERED`, not source-absent. The machine-readable registry intentionally remains `LOCKED` until promotion conditions are satisfied.

## F-001 — Causal availability

```text
availability_time(x) <= decision_time
```

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

## F-005 — Risk authorization immutability

Risk authorization is state and cannot increase merely because current P&L or prediction improves.

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

## Strategy-specific formulas — SOURCE-RECOVERED / REGISTRY-LOCKED

The authoritative V1.0 source establishes the following roles:

```text
F-101  Feature/state construction and normalization
F-102  Probability/regime state
F-103  Candidate eligibility / NO_TRADE boundary
F-104  Adaptive horizon distribution
F-105  Target/stop competition and conservative EV
F-106  Option candidate economics
F-107  Effective risk semantics
F-108  Position sizing
F-109  Option selection by validated ExpectedNetEV subject to constraints
F-110  BUY_CE / BUY_PE mandatory entry gate
F-111  Position-management exit state machine
F-112  Monotonic dynamic protection / profit floor
F-113  Post-exit / re-entry boundary
F-114  Final decision interaction with PositionState and CapitalState
```

### F-109 canonical selection

```text
O* = argmax ExpectedNetEV_i
```

subject to:

```text
Liquidity_i >= required level
ExpectedSlippage_i <= allowable level
Risk_i <= risk budget
DataQuality >= required level
```

ATM is therefore **not** a canonical selection rule. A moneyness ladder may generate candidates, but economic selection decides the winner.

### F-110 canonical entry gate

```text
BUY_CE = DataOK
       ∧ DirectionalEdgeOK
       ∧ EV_CE > 0
       ∧ ConservativeEV_CE > 0
       ∧ LiquidityOK
       ∧ SlippageOK
       ∧ RiskOK
```

`BUY_PE` has the analogous condition. Otherwise `NO_TRADE`.

### F-111 canonical exit semantics

Exit is permitted/required on validated hard protection, non-positive conservative continuation value, emergency reversal conditions, or session termination. The state machine does not permit `NO_TRADE -> OPEN` without signal and execution gates.

### F-112 canonical protection invariant

```text
Stop_(t+1) >= Stop_t
MaximumAcceptedRisk_(t+1) <= MaximumAcceptedRisk_t
```

Learned giveback/continuation parameters remain unfrozen until walk-forward validation.

### F-114 status

The source defines the canonical decision function:

```text
Decision_t = D(
    MarketState_t,
    ProbabilityState_t,
    CapitalState_t,
    ExecutionState_t,
    PositionState_t
)
```

It does not uniquely specify a multi-position portfolio-risk aggregation equation. F-114 therefore remains blocked specifically on that mathematical resolution.

## Formula promotion contract

Every formula promoted to `RESOLVED` must have:

```text
Formula ID
Version
Definition
Inputs
Input semantics
Units
Availability timestamp semantics
Boundary conditions
Numerical safeguards
Parameter-estimation methodology
Owner module
Unit tests
Adversarial tests
Backtest/parity test
Provenance
```

Until that metadata exists, the formula is not production-authorized.

## Risk semantic prohibition

No silent equivalence is permitted between:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
```

unless the authoritative source explicitly establishes the relationship.
