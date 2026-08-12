# A60 — End-to-End Invariant Gate

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A60 is the cross-artifact integrity gate. It does not create new strategy mathematics. It verifies that a complete causal chain exists before execution/accounting claims can be considered structurally valid.

## Canonical causal chain

```text
observation
    -> feature snapshot
    -> prediction
    -> economic decision
    -> risk authorization
    -> operational authorization
    -> execution authorization
    -> order intent
    -> submission
    -> fill
    -> accounting
    -> audit
```

## Required invariants

### 1. Completeness

A complete chain must contain every canonical stage exactly once.

### 2. Causal ordering

Each stage must reference the immediately preceding stage as its causal parent.

### 3. Temporal monotonicity

A child event cannot precede its causal parent.

### 4. Authorization before execution

Order intent requires evidence of:

```text
risk authorization
operational authorization
execution authorization
```

### 5. No inferred lineage

Missing causal identity is a failure, not an invitation to infer lineage from timestamps or mutable state.

## What A60 does not prove

A passing A60 structural gate does not prove:

- strategy profitability
- statistical validity
- live-trading readiness
- provider compatibility
- executable-price correctness
- fill-model correctness
- economic sufficiency
- parameter calibration

Those remain governed by their respective artifacts and current status.

## Relationship to earlier artifacts

A60 composes the boundaries established by A40-A59. It is therefore a structural integration gate, not a replacement for the individual contracts.

## Failure behavior

Any missing stage, broken parent reference, backward timestamp, or missing authorization prerequisite causes the gate to fail closed.

No fallback inference is permitted.
