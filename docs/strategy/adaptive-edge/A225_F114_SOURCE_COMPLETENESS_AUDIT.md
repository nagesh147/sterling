# A225 — F-114 Source Completeness Audit

**Status:** `[AUDITED / MATHEMATICS STILL UNRESOLVED]`

## Finding

The recovered V1.0 master strategy is authoritative and complete enough for formula recovery generally. fileciteturn109file0L2-L2

However, inspection of the recovered mathematical sections establishes the following:

```text
Option Selection
Target/Stop Competition
Conservative EV
Entry Decision
Initial Risk
Trade Plan
Position State
Forward Management
Protection
Lifecycle
Learning
```

The source explicitly defines option selection as an `argmax ExpectedNetEV` subject to liquidity, slippage, risk, and data-quality constraints. fileciteturn112file0L2-L2

It also explicitly defines the entry gates, risk sizing, immutable trade plan, and post-entry state. fileciteturn112file0L2-L2

But no uniquely identifiable equation in the recovered source specifies a **multi-position portfolio aggregation function** for combining an existing portfolio with a new candidate.

## Consequence

We cannot legitimately promote any of these as F-114:

```text
sum(position risks)
correlation-adjusted VaR
stress loss
max individual risk
portfolio delta aggregation
```

Each would be a new strategy definition.

## What is resolved

The source does establish these invariants:

```text
candidate must pass upstream gates
risk is bounded
accepted risk cannot expand
position state is explicit
entry requires execution gates
```

The source also establishes that the system is not allowed to increase previously accepted risk merely because prediction becomes more optimistic. fileciteturn111file0L2-L2

## Engineering disposition

F-114 therefore has two separate states:

```text
ARCHITECTURAL BOUNDARY      = RESOLVED
PORTFOLIO AGGREGATION MATH  = UNRESOLVED
```

The newly implemented `f114_portfolio_boundary.py` enforces the first without pretending to solve the second.

## Promotion blocker

F-114 cannot become a production formula until one of the following occurs:

1. an authoritative strategy artifact provides the aggregation equation;
2. an explicitly approved strategy revision defines it and versions it;
3. portfolio interaction is formally declared out of scope for the first production deployment.

Until then:

```text
F-114 = LOCKED
ExecutionGate = BLOCKED
```
