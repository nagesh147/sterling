# A53 — Promotion / Claim Boundary Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A53 separates evidence validity from the policy decision to promote a candidate, publish a claim, or proceed toward deployment.

## Dependency chain

```text
A50 research selection
    -> A51 untouched final holdout
    -> A52 statistical validity
    -> A53 promotion-policy decision boundary
```

A53 requires upstream holdout and statistical evidence to share the same evaluation identity. A statistically invalid or unresolved claim cannot enter the promotion-decision boundary.

## Decision identity

A promotion decision must retain:

- decision identity
- evaluation identity
- policy identity
- policy version
- outcome
- rationale

Allowed outcomes are `approved`, `rejected`, and `deferred`.

## Important separation

`eligible_for_policy_decision` does not mean `approved`.

It means only that the upstream evidence has satisfied the repository's currently implemented A51/A52 lineage requirements and may be evaluated by an explicitly identified promotion policy.

## Prohibited invention

A53 does not define:

- profitability thresholds
- Sharpe thresholds
- confidence levels
- p-value thresholds
- economic significance thresholds
- live-trading eligibility
- position sizing
- execution rules
- risk limits
- deployment automation

Those require authoritative source specifications or an explicitly approved policy artifact.

## Claim semantics

A53 therefore provides a hard boundary:

```text
valid evidence
    !=
promotion approval
```

and:

```text
promotion eligibility
    !=
live trading authorization
```
