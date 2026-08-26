# Adaptive Edge Engine

Sterling Kite strategy engine.

## Scope

Adaptive Edge is an independent Kite engine. It is not a crypto engine and it does not replace SuperTrend or Flow Navigator.

```text
Sterling Kite
├── SuperTrend
├── Flow Navigator
└── Adaptive Edge
```

## Strategy preservation rule

The implementation MUST preserve the strategy mathematics, rules, invariants, and adversarial discoveries established during the design phase. Implementation convenience is never a reason to change strategy semantics.

In particular:

- Dynamic mode and dynamic risk are separate state axes.
- A mode transition can never grant additional risk by implication.
- Previously authorized risk cannot be increased merely because predictive profit, mark-to-market profit, or mode state improved.
- Prediction, economic eligibility, risk authorization, execution, position state, and accounting are separate concepts.
- Historical decisions may use only information causally available at the decision timestamp.
- Actual fills, not order intent, determine position and accounting state.
- Backtest semantics must match engine semantics; only data/execution environments differ.
- Every strategy-specific formula must have one authoritative implementation.

## Boundary

The engine owns:

```text
strategy state
feature calculation
prediction/economic evaluation
opportunity lifecycle
dynamic mode transitions
risk-request semantics
strategy-specific entry/exit rules
strategy-specific validation
```

Sterling Kite shared infrastructure owns:

```text
Kite authentication
market-data transport
broker execution
live-safety gate
accounting primitives
position reconciliation
platform observability
```

The engine must not duplicate broker execution logic already provided by Sterling Kite.

## Implementation rule

Do not invent missing strategy mathematics while coding. If a formula or rule is not recoverable from the frozen strategy specification, stop at the interface boundary and restore the specification before implementing it.
