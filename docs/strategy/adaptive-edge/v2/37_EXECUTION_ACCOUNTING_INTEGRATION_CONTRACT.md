# A61 — Execution / Accounting Integration Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A61 connects confirmed execution events to position and accounting effects without treating an order intention or submission as an economic fill.

## Causal chain

```text
OrderIntent
    |
    v
Submission
    |
    v
Confirmed FillEvent
    |
    v
PositionEffect
    |
    v
AccountingEvent
```

## Required invariants

1. Position effects require confirmed fills.
2. A position effect must reference the originating fill.
3. Instrument identity must remain consistent.
4. A position effect cannot precede its fill.
5. Accounting events must reference both the fill and position effect.
6. An order intent without a confirmed fill cannot directly produce an accounting event.

## Scope boundary

A61 does not define:

- fill-price semantics
- brokerage/taxes/slippage
- realized/unrealized P&L formulas
- settlement semantics
- provider-specific execution behavior
- position-sizing policy

Those remain governed by the relevant canonical artifacts and provider documentation.

## Failure behavior

Broken execution-to-accounting lineage is a contract failure. The implementation must not infer a fill from submission, acceptance, or order intent.
