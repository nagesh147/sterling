# Adaptive Edge V2 — Prediction, Probability Calibration and Decision-Input Contract

**Artifact:** A41  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** INTERFACE-ONLY

## Purpose

A41 defines the boundary from an immutable feature snapshot to a prediction, probability/score representation, calibration state, and downstream decision input.

It does not invent the model family, target, horizon, probability definition, threshold, or calibration method.

## Causal chain

```text
FeatureSnapshot(t_d)
        |
        v
Model/PolicyVersion(t_d)
        |
        v
RawModelOutput
        |
        v
Probability/Score Representation
        |
        v
Calibration Policy
        |
        v
DecisionInput
```

Every prediction must be tied to the exact model/policy version active at the decision boundary.

## Prediction identity

A canonical prediction record contains at minimum:

```text
prediction_id
decision_time
feature_snapshot_id
model_version
model_state_version
raw_output
output_type
calibration_version
calibrated_output
prediction_provenance
```

## Raw output versus probability

A raw model output is not automatically a probability. A value in `[0,1]` is not sufficient evidence that the value is a probability for a defined event.

## Calibration

Calibration is a versioned mapping from a raw prediction representation to an interpreted probability, if a probability is actually required. Calibration parameters must be learned within the applicable causal training/validation boundary.

## Decision-input boundary

The decision layer consumes a canonical object linking prediction, feature snapshot, model version, calibration version, economic context, and decision time. This object is not itself a trade decision.

```text
Prediction != Eligibility
Prediction != Decision
Prediction != ExpectedProfit
```

## Adaptive model state

If model state evolves through prior observations, prediction must use the state valid at the decision boundary. The conservative causal ordering is:

```text
state_{t-1}
    -> prediction_t
    -> outcome later
    -> eligible learning update
    -> state_t
```

## Thresholds

No probability/score threshold is frozen by A41. Threshold selection is a research policy and must be versioned and validated without contaminating the final test boundary.

## Implementation gate

A41 permits implementation of the prediction/decision-input **interface** independently. It does not authorize a numerical probability or calibration function until the target event, label horizon, output semantics, calibration population, and calibration training boundary are resolved.

## Status

**FROZEN:** prediction identity; feature linkage; model-version linkage; raw-output/probability separation; calibration separation; decision-input boundary; causal state ordering; threshold versioning.

**UNRESOLVED:** target event; label horizon; model family; probability semantics; calibration method; calibration population; threshold; recalibration frequency.

**NEXT ARTIFACT:** A42 — Economic Value, Expected Value and Decision Utility Contract.
