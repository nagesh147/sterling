# Adaptive Edge — Formula Recovery Protocol

## Objective

Recover the exact strategy mathematics previously designed for Adaptive Edge without introducing semantic drift.

## Promotion gate

A formula may move from `LOCKED` to `IMPLEMENTED` only after all fields below are known:

```text
Formula ID
Version
Name
Exact equation OR exact executable pseudocode
Every input variable
Units / dimensional meaning
Boundary conditions
Numerical safeguards
Causal availability requirements
Source evidence
Deterministic examples
Adversarial examples
Backtest/live parity test
```

The executable validator is `backend/app/engines/adaptive_edge/formula_recovery.py`.

## Evidence hierarchy

Use evidence in this order:

```text
1. Explicit prior strategy specification
2. Explicit strategy design decision recorded during development
3. Strategy-specific worked numerical example
4. Strategy-specific test / expected output
5. Existing Adaptive Edge implementation
6. Shared Sterling infrastructure
7. Generic domain knowledge
```

Levels 6 and 7 may explain implementation mechanics but cannot establish an Adaptive Edge formula by themselves.

## Conflict rule

If two historical artifacts disagree:

```text
DO NOT average them
DO NOT choose the more familiar formula
DO NOT choose the implementation that is easier

Mark formula AMBIGUOUS -> resolve specification -> then implement
```

## Recovery record format

For each F-101..F-114:

```text
### F-xxx

Status: LOCKED | AMBIGUOUS | RECOVERED
Version:

Definition:

Equation:

Inputs:

Units:

Boundary conditions:

Causal requirements:

Worked examples:

Counterexamples:

Source evidence:

Implementation owner:

Tests:
```

## Safety rule

A plausible formula is not an exact formula.

For example, the following are not sufficient evidence for an Adaptive Edge equation:

```text
"This looks like a good edge score."
"This is standard for momentum."
"SuperTrend already calculates something similar."
"Kelly sizing would make sense here."
"The old derivatives engine has an edge formula."
```

Those may be research proposals, but they are not recovered strategy definitions.

## Current recovery state

F-101..F-114 remain locked pending exact evidence.

Known canonical economic formula:

```text
F-004
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

This protocol is intentionally strict because the purpose of this branch is to recover the strategy, not redesign it.
