# Adaptive Edge V2 — Similarity Sample Sufficiency Boundary

**Artifact:** A23 implementation boundary
**Status:** FRAMEWORK IMPLEMENTED / STRATEGY PARAMETER UNRESOLVED
**Canonical source:** Master Mathematical Specification, §23

## 1. Purpose

The canonical similarity specification requires a minimum effective sample size. It does not recover the complete neighbourhood-selection procedure, effective-sample estimator, threshold, or parameter-fitting policy.

This boundary therefore implements only parameterized sufficiency mechanics.

## 2. Implemented

A generic weighted-sample effective sample size utility is provided:

```text
ESS = (sum(w))^2 / sum(w^2)
```

This is a generic statistical utility. It is not asserted to be the source-defined Adaptive Edge estimator.

A separate gate accepts an explicitly supplied effective sample size and an explicitly supplied minimum threshold:

```text
eligible = effective_samples >= minimum_effective_samples
```

## 3. Explicitly not resolved

```text
feature weights
neighbourhood size
candidate selection
ESS estimator authority
minimum effective sample threshold
threshold learning
similarity calibration
fallback policy
```

No numerical threshold or learned parameter is introduced.

## 4. Leakage boundary

The sufficiency inputs must be constructed only from observations eligible at the relevant decision time. The gate itself does not perform temporal selection and must not be used as evidence that a candidate set is leakage-free.

## 5. Status

```text
Distance operator                 IMPLEMENTED
Similarity weight operator        IMPLEMENTED
ESS utility                       IMPLEMENTED AS GENERIC UTILITY
Sufficiency gate                  IMPLEMENTED / PARAMETERIZED
Strategy ESS definition           UNRESOLVED
Strategy threshold                UNRESOLVED
Neighbourhood selection           UNRESOLVED
```
