# Adaptive Edge V2 — Probability Calibration Boundary

**Artifact:** §25 implementation boundary
**Status:** BLOCKED

## 1. Source relationship

The canonical probability specification establishes probability outputs and separately identifies calibration as a required research concern. The repository's prediction contract explicitly does **not** choose a calibration method, calibration threshold, or probability threshold.

The source therefore supports the existence of a calibration boundary, but does not provide enough information to select a specific calibration operator or parameterization as strategy truth.

## 2. Current mathematical boundary

The probability layer may expose a raw model probability vector:

```text
p_raw = (p_1, p_2, ..., p_K)
```

A calibrated output would conceptually be:

```text
p_calibrated = Calibration(p_raw, calibration_state)
```

However, `Calibration(...)` is not source-defined sufficiently to implement faithfully as a canonical strategy operator.

## 3. Explicitly unresolved

The repository does not recover authoritative values or choices for:

```text
calibration method
calibration data partition
calibration window
calibration parameters
calibration objective
calibration acceptance criterion
probability threshold
recalibration schedule
```

No implementation may silently choose Platt scaling, isotonic regression, temperature scaling, beta calibration, binning, or another method and label that choice as canonical Adaptive Edge mathematics.

## 4. Causal boundary

Any future calibration implementation must preserve the existing causal partition:

```text
TRAIN
  -> fit model

VALIDATION / calibration data
  -> calibrate / select according to an explicitly declared research protocol

HOLDOUT
  -> untouched final evaluation
```

A holdout observation must not be used to fit or calibrate the model before final claim evaluation.

## 5. Promotion boundary

Calibration quality is not itself a trading authorization rule. A calibrated probability must remain downstream of the prediction boundary and upstream of economic evaluation, conservative EV, and risk authorization.

```text
Prediction
    -> Calibration
    -> Economic evaluation
    -> Conservative decision
    -> Risk authorization
```

Calibration must not alter the historical decision or execution state.

## 6. Implementation decision

No `calibration_engine` implementation is added by this artifact.

This is intentional. The correct state is `BLOCKED`, not `PARTIAL`, until an authoritative source artifact or an explicitly versioned research specification defines the calibration method and its validation protocol.

## 7. Required unblock artifact

Before implementation, the project needs a versioned research contract defining at minimum:

1. calibration method;
2. training/calibration/validation partition semantics;
3. calibration objective;
4. parameter-fitting procedure;
5. acceptance criterion;
6. recalibration policy;
7. untouched holdout procedure.
