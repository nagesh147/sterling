# Normalization Baseline Resolution

## Source boundary

The canonical specification defines causal contextual normalization as:

```text
Percentile_t
    = F(x_t | Context_t, Data<=t)
```

The historical distribution must be causally available at the decision time. The source does not freeze the estimator, context-construction procedure, or minimum-data policy.

## Implemented baseline

The implementation uses an empirical CDF over observations satisfying both conditions:

```text
available_at <= decision_time
context == current_context
```

For eligible values sorted as:

```text
y_1 <= y_2 <= ... <= y_n
```

the implementation computes:

```text
F_hat(x) = #{y_i <= x} / n
```

using a right-continuous empirical CDF.

No fixed normalization threshold, window size, quantile convention beyond the empirical-CDF operator, or learned parameter is introduced.

## Provenance boundary

Each observation carries:

```text
value
available_at
context
```

Therefore the normalization operator does not infer context from future observations and does not silently mix incompatible contexts.

## Insufficient evidence

The source leaves the minimum-data policy unresolved. The implementation therefore does not invent a minimum sample threshold. If no causally eligible observations exist for the supplied context, the operator raises an explicit insufficient-history error rather than manufacturing a normalized value.

## Important distinction

This resolves the mathematical operator, not the full strategy normalization subsystem.

Still unresolved:

- how `Context_t` is constructed
- which contextual dimensions are mandatory
- how volatility/regime/expiry states are defined
- minimum effective evidence policy
- whether dependence adjustment is required for this normalization distribution
- estimator selection beyond the empirical baseline
- walk-forward fitting/update protocol for contextual state definitions

Those are research/configuration contracts and must remain unfrozen until supported by the canonical source or validated research protocol.

## Status

```text
CAUSAL FILTERING          IMPLEMENTED
CONTEXT MATCHING          IMPLEMENTED FOR EXPLICIT CONTEXT INPUT
EMPIRICAL CDF             IMPLEMENTED
FUTURE-DATA EXCLUSION     TESTED
MIN-DATA POLICY           UNFROZEN
CONTEXT CONSTRUCTION      UNFROZEN
FULL §19 SUBSYSTEM        PARTIAL
```
