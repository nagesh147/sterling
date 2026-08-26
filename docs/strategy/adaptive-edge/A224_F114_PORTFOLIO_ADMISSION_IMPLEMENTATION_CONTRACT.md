# A224 — F-114 Portfolio Admission Implementation Contract

**Status:** `[IMPLEMENTED / FAIL-CLOSED / MATHEMATICAL AGGREGATION UNRESOLVED]`

F-114 is now implemented as an architectural admission boundary without inventing the unresolved portfolio-risk aggregation equation identified by A220. fileciteturn95file0L2-L2

## Contract

A candidate can be admitted only when:

```text
standalone eligibility
        AND
execution authorization
        AND
portfolio assessment available
        AND
portfolio decision permits exposure
```

The portfolio assessment is immutable and requires:

```text
assessment_id
model_version
causal_cutoff
reason
approved_quantity
```

## Decision semantics

```text
ADMIT       -> candidate may proceed, never above candidate quantity
REDUCE      -> candidate is capped by approved quantity
REJECT      -> no exposure
UNAVAILABLE -> no exposure
```

F-114 cannot increase upstream authorization or quantity.

## Explicit non-solution

This implementation does **not** claim to know the correct portfolio-risk aggregation function. A220 explicitly identifies that equation as unresolved and prohibits selecting a convenient sum/correlation/stress formula without authoritative strategy evidence. fileciteturn95file0L2-L2

Therefore the current model version is intentionally named:

```text
unresolved-portfolio-v0
```

It is an integration boundary only and cannot unlock production execution.

## Result

We can now test the entire architecture through F-114 while preserving the mathematical stop condition:

```text
F-101..F-113
     |
     v
candidate quantity
     |
     v
F-114 assessment
     |
     +--> unavailable/reject -> NO_TRADE
     |
     +--> reduce -> bounded quantity
     |
     +--> admit -> candidate quantity unchanged
```

The next task is therefore evidence resolution for the portfolio aggregation model, not another invented implementation.
