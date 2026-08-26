# A209 — F-101 Canonical Formula Recovery

**Status:** `[CANONICAL RECOVERY / IMPLEMENTATION PREPARATION]`
**Date:** 2026-08-17
**Formula:** F-101 — Feature normalization / feature score
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Purpose

This artifact re-opens F-101 using the recovered authoritative Version 1.0 strategy source. It replaces the previous assumption that the mathematical source was unavailable.

It does **not** freeze learned parameters and does **not** authorize production execution.

## 2. Source-defined semantics

The recovered source defines the feature state as a multidimensional causal vector:

```text
X_t = {P, D, V, L, sigma, VP, MP, O, T, Q}
```

where:

```text
P   = Price
D   = Directional / OrderFlow
V   = Volume
L   = Liquidity
sigma = Volatility
VP  = VolumeProfile
MP  = MarketProfile
O   = Options
T   = Temporal
Q   = DataQuality
```

The source requires raw and normalized variables to be retained. Normalization is conditional on historical information available before the decision point rather than a universal fixed threshold.

Conceptually, for variable `x_t`:

```text
Percentile_t = F(x_t | Context_t, Data <= t)
```

with context potentially including:

```text
instrument
time_of_day
volatility_state
expiry_state
market_regime
```

The normalization distribution must be estimated without future-information contamination.

## 3. F-101 interpretation

For the current registry, F-101 is therefore the canonical transformation from the causal feature state into the normalized feature representation used by the downstream probability/edge layer.

It is **not** a single arbitrary weighted sum and it is **not** equivalent to the trial score currently used by the research harness.

The trial implementation may be used for software plumbing only. Its weights, windows, and thresholds remain non-canonical.

## 4. Required inputs

The source-defined feature families are:

```text
Price
Directional / OrderFlow
Volume
Liquidity
Volatility
VolumeProfile
MarketProfile
Options
Temporal
DataQuality
```

For the currently authorized TrueData research slice, A206 remains binding:

```text
LiquidityImbalance = authorized
DeltaVelocity = removed
DeltaVelocity proxy = prohibited
```

The absence of a provider-supported input must produce an explicit feature-status condition. It must not be replaced by invented data.

## 5. Causal contract

Every normalized feature used at decision time `t` must satisfy:

```text
available_at(feature_t) <= decision_time_t
```

Historical normalization statistics must be constructed only from observations that were available before the decision point under the walk-forward training boundary.

The test period cannot influence:

```text
normalization distribution
feature scaling parameters
threshold selection
model coefficients
```

before that test period is completed.

## 6. Units and representation

F-101 must preserve the distinction between:

```text
raw market quantity
normalized representation
statistical context
feature validity
```

Normalization does not erase provenance or source units. Each feature must retain its source event lineage and the normalization/version metadata required to reproduce the decision.

The normalized representation is dimensionless where percentile/rank normalization is used.

## 7. Parameters

No production parameter values are frozen by this artifact.

The following are learned or selected through chronological research and remain `[UNFROZEN]`:

```text
historical conditioning windows
minimum sample requirements
normalization estimator parameters
regime/context partitioning
winsorization/outlier policy, if empirically justified
feature inclusion/exclusion decisions
```

A parameter becomes production-authorized only after train/validation/test evidence satisfies the existing promotion contract.

## 8. Numerical safeguards

F-101 must fail closed for invalid or unusable inputs.

Required behavior includes:

```text
zero/invalid denominator -> INVALID or MISSING
insufficient history -> MISSING / insufficient-evidence state
stale input -> STALE
future availability -> reject
provider field absent -> explicit unavailable status
non-finite normalized result -> INVALID
```

No invalid normalized value may silently enter the probability or decision layer.

## 9. Boundary conditions

At minimum:

```text
BidQty + AskQty <= 0
    -> LiquidityImbalance unavailable

historical sample insufficient
    -> normalization unavailable

feature available_at > decision_time
    -> causal violation; reject

missing provider field
    -> explicit missing status; no proxy unless separately authorized
```

## 10. Implementation boundary

Existing causal feature infrastructure is compatible with this contract because the canonical `FeatureSnapshot` requires feature status, availability timestamps, provenance, strategy version, and feature-set version, and rejects lookahead when `available_at > decision_time`. 

Therefore the implementation task is not to redesign the feature boundary. It is to replace the trial F-101 mathematical evaluation with a source-conformant, walk-forward-normalized implementation once the remaining estimator choices are resolved.

## 11. Resolution status

```text
Source definition recovered:       YES
Core mathematical semantics:       RECOVERED
Causal semantics:                   RECOVERED
Input families:                     RECOVERED
A206 input authorization:           RECOVERED
Production parameters:              NOT FROZEN
Estimator details:                  RESEARCH / TO BE SELECTED
Calibration evidence:               BLOCKED until sufficient historical data
Production implementation:         NOT AUTHORIZED
Execution:                          BLOCKED
```

F-101 should therefore move from the old source-absence interpretation to:

```text
SOURCE-RECOVERED / PARAMETER-UNFROZEN
```

It must not yet be marked `IMPLEMENTED`.

## 12. Next step

Implement the deterministic F-101 normalization research boundary with train-only fitting and test-time transform, while preserving the production registry as locked until calibration and validation are complete.
