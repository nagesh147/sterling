# Adaptive Edge V2 — Bayesian State Boundary

**Artifact:** §24 implementation boundary
**Status:** PARTIAL

## 1. Source relationship

The canonical formula defines a Beta state:

```text
Beta(α, β)

α_t = ρ α_(t-1) + Successes_t
β_t = ρ β_(t-1) + Failures_t
```

The source states that `ρ` is learned and validated. Initialization and the learning procedure remain unresolved.

## 2. Implementation boundary

`backend/app/engines/adaptive_edge/bayesian_state.py` provides only the source-supported state transition boundary:

```text
BetaState(α, β)
        |
        +--> additive update
        |
        +--> explicit-ρ decayed update
        |
        v
BetaState(α', β')
```

All initialization values, observations, and decay values are explicit inputs.

## 3. Prohibited assumptions

The implementation does not choose:

```text
α_0
β_0
ρ
learning schedule
window length
prior strength
promotion threshold
```

No strategy-specific values are embedded in the state module.

## 4. Evidence constraints

Successes and failures must be non-negative observed quantities. A Beta state requires positive `α` and `β` parameters.

The implementation does not define how observations are generated, how `ρ` is learned, or when a Bayesian estimate is promoted for trading.

## 5. Posterior mean

For an already constructed state, the mathematical posterior mean is exposed as a deterministic derived quantity:

```text
E[p | α, β] = α / (α + β)
```

This does not constitute a strategy calibration rule.

## 6. Remaining blockers

The complete §24 component remains `PARTIAL` because the source does not recover:

1. authoritative initialization semantics;
2. the learning procedure for `ρ`;
3. observation-generation semantics;
4. calibration/promotion criteria.
