# A220 — F-114 Final Interaction / Portfolio Boundary

**Status:** `[SOURCE-RECOVERED / SEMANTICS REQUIRES EXPLICIT RESOLUTION]`
**Formula:** F-114

## 1. Decision

F-114 is the final integration boundary across the strategy decision state, risk state, economic state, instrument state, and active-position state.

Unlike F-101 through F-113, the repository evidence currently does not provide a sufficiently explicit, uniquely identifiable mathematical F-114 equation to justify inventing one.

Therefore F-114 is **not** promoted merely because the preceding formulas exist.

## 2. Required role

The final interaction boundary must answer:

```text
Can this candidate/position exist concurrently with the current portfolio state?
```

It must account for:

```text
candidate economic eligibility
candidate authorized risk
existing active-position risk
portfolio concentration
instrument overlap
correlated underlying exposure
capital constraints
session/lifecycle state
data quality
execution authorization
```

## 3. Architectural ordering

F-114 cannot bypass earlier boundaries:

```text
F-101 Feature State
      |
F-102 Probability
      |
F-103 Opportunity
      |
F-104 Horizon
      |
F-105 Economics
      |
F-106 Option Economics
      |
F-107 Effective Risk
      |
F-108 Quantity
      |
F-109 Instrument
      |
F-110 Order Intent
      |
F-111 Execution Event
      |
F-112 Protection
      |
F-113 Lifecycle
      |
      v
F-114 Portfolio / Final Interaction
```

The final layer may reduce or reject a candidate. It may not enlarge upstream authorization.

## 4. Risk invariant

For a portfolio containing active positions `i` and candidate `c`:

```text
PortfolioRisk_after(c) <= PortfolioRiskBudget
```

The exact portfolio-risk aggregation function is unresolved and must not be invented here.

Possible risk aggregation choices such as simple sum, correlation-adjusted aggregation, or stress aggregation are materially different strategy semantics and require explicit source/approval.

## 5. Correlation / overlap

The system must distinguish:

```text
same instrument
same underlying
same directional exposure
highly correlated underlying
independent exposure
```

Two nominally different option contracts may still represent substantially the same portfolio risk.

No arbitrary correlation threshold is frozen by A220.

## 6. Concurrency

A second trade must not be admitted simply because its standalone F-103/F-105/F-106 evaluation is eligible.

The portfolio decision is:

```text
standalone eligibility
        AND
portfolio eligibility
        AND
execution authorization
```

If the portfolio boundary cannot be evaluated reliably:

```text
NO_TRADE
```

## 7. No risk creation

F-114 cannot:

```text
increase AuthorizedRisk
increase EffectiveRisk budget
increase F-108 quantity
remove a protection constraint
extend a forced lifecycle cutoff
bypass execution gate
```

It may only preserve, reduce, or reject exposure.

## 8. Causality

Portfolio state at decision time `t` must contain only positions and risk information known by `t`.

Future fills, exits, realized P&L, or future correlations cannot influence the original admission decision.

## 9. Current implementation disposition

The existing Adaptive Edge architecture already separates risk authorization, position sizing, lifecycle supervision, and execution authorization. F-114 should therefore be implemented only after its aggregation semantics are explicitly resolved.

The V2 risk artifact confirms that risk authorization, risk measurement, and quantity are distinct layers and explicitly rejects assuming an unspecified aggregation formula. fileciteturn107file0L2-L6

## 10. Canonical status

```text
F-114 role:                 identified
Portfolio boundary:        identified
Causal requirements:       identified
No-risk-expansion rule:    identified
Exact mathematical model:  UNRESOLVED
Production implementation: NOT AUTHORIZED
```

This is a deliberate stop on **mathematical invention**, not a stop on engineering work.

## 11. Next engineering action

With F-101..F-113 canonicalized/reconciled and F-114 explicitly isolated as the remaining unresolved strategy mathematics, the next phase is:

```text
F-101..F-113
     |
     v
integration test matrix
     |
     v
historical TrueData calibration
     |
     v
F-114 portfolio-model resolution
     |
     v
full formula promotion review
```

F-114 should be resolved from authoritative strategy evidence or an explicitly versioned new strategy definition—not by selecting a convenient portfolio formula.
