# Adaptive Edge V2 — Similarity Operator Implementation Boundary

**Artifact:** A43-extension / §23 implementation boundary  
**Status:** IMPLEMENTED / SELECTION PARTIAL  
**Source:** Master Mathematical Specification §23; `docs/strategy/adaptive-edge/FORMULAS.md`

## Implemented operators

The implementation provides only the source-defined mathematical operators:

```text
Z_i = (X_i - mu_i) / sigma_i

d(X_t, X_j)
    = sqrt(sum(w_i * (Z_i,t - Z_i,j)^2))

w_j
    = exp(-d_j^2 / tau)
```

The implementation validates finite inputs, positive standard deviation, equal vector dimensions, non-negative feature weights, finite non-negative distance, and positive finite `tau`.

## Deliberately unresolved

This artifact does not define:

```text
feature-weight learning
neighbourhood size / K
candidate-selection policy
distance threshold
tau-learning policy
minimum effective sample size
fallback behavior when evidence is insufficient
```

Those remain research/strategy inputs and must be recovered or learned under the walk-forward contract before they can be promoted to strategy-authorized parameters.

## Boundary

```text
normalized feature vectors
        |
        v
source-defined distance
        |
        v
source-defined similarity weight
        |
        v
[selection / effective-sample gate unresolved]
        |
        v
probability estimation
```

No numerical research parameter is introduced by this implementation.
