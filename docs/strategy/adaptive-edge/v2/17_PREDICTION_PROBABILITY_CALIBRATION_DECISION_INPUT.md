# Adaptive Edge V2 — Prediction, Probability Calibration and Decision-Input Contract

**Artifact:** A41  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A41 defines the boundary from an immutable feature snapshot to a prediction, probability/score representation, calibration state, and the downstream decision input.

It does not invent the model family, target, horizon, probability definition, threshold, or calibration method.

## 2. Canonical causal chain

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

## 3. Prediction identity

A canonical prediction record must contain:

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

Exact fields may expand with the model contract.

## 4. Raw output versus probability

A raw model output is not automatically a probability.

For example:

```text
raw_output = 0.72
```

does not establish:

```text
P(Y=1 | X) = 0.72
```

A probability interpretation requires an explicitly defined target, sample space, horizon, and calibration semantics.

## 5. Probability definition

A production probability must specify:

```text
random event
conditioning information
observation horizon
label definition
population
probability meaning
model version
calibration version
```

The actual event remains UNKNOWN because A26 target/horizon semantics are unresolved.

## 6. Score definition

If the system uses a score rather than probability, the score must have a canonical semantic definition and ordering meaning.

A score cannot be treated as probability merely because it lies in `[0,1]`.

## 7. Calibration

Calibration is a mapping from a raw prediction representation to an interpreted probability, if a probability is actually required:

```text
p_calibrated = CalibrationFunction(raw_output, CalibrationVersion)
```

The function is not selected here.

Candidate methods may include statistical calibration procedures, but no method is frozen without validation.

## 8. Calibration training boundary

Calibration parameters are learned quantities.

They must be fit only on data causally available under the relevant training/validation protocol.

Using future outcomes to calibrate predictions used earlier is leakage.

## 9. Calibration population

A calibration population must specify:

```text
source observations
label policy version
maturity boundary
feature/model version
time interval
selection policy
```

The calibration population cannot be selected using the final test performance of the calibrated model.

## 10. Calibration versus discrimination

A model can rank outcomes well while producing poorly calibrated probabilities.

Therefore these properties must be evaluated separately:

```text
ranking/discrimination
calibration
```

No numerical calibration criterion is selected here.

## 11. Probability bounds

If the output is a probability, it must satisfy:

```text
0 <= p <= 1
```

A value outside the domain is invalid unless the representation is explicitly a non-probability score.

## 12. Probability semantics and label mismatch

A probability is meaningless if the label event changes.

Changing:

```text
target
horizon
positive condition
population
```

requires a new prediction/calibration contract version.

A calibrated probability for one event cannot be silently reused for another.

## 13. Class imbalance

Class prevalence is part of probability semantics.

A calibration method or threshold cannot assume a fixed prevalence if the target population changes through time.

The population definition must therefore be explicit.

## 14. Selection-conditioned probability

If predictions are only generated after eligibility filters, the probability's conditioning population may differ from the overall opportunity population.

The system must explicitly identify whether the probability means:

```text
P(outcome | all opportunities, X)
```

or

```text
P(outcome | eligible opportunities, X)
```

or another explicitly defined population.

No interpretation is selected here.

## 15. Missing/invalid features

A prediction must not be produced from silently substituted invalid features unless the feature/imputation contract explicitly permits it.

The prediction record must preserve feature quality state.

Possible states include:

```text
VALID
DEGRADED
INVALID
UNAVAILABLE
```

Exact decision consequences are downstream.

## 16. Model version

A prediction must reference the model/policy version active at the decision timestamp.

The current/latest model cannot be substituted retrospectively.

## 17. Adaptive model state

If the model contains state updated through prior observations, prediction requires the state snapshot valid at `t_d`.

Conceptually:

```text
Prediction_t
    = Model(X_t, State_{t-1})
```

where the exact state transition is model-specific.

## 18. State update ordering

For an adaptive model, the system must define whether the current observation can update model state before its own prediction.

Unless explicitly defined otherwise, the conservative causal architecture is:

```text
state_{t-1}
    -> prediction_t
    -> outcome later
    -> eligible learning update
    -> state_t
```

No same-observation future outcome may update the prediction that produced the decision.

## 19. Decision-input contract

The decision layer should consume a canonical object:

```text
DecisionInput {
    prediction_id
    prediction_type
    prediction_value
    calibration_version
    feature_snapshot_id
    economic_context_reference
    model_version
    decision_time
}
```

This object is an input to economic/eligibility logic, not itself a trade decision.

## 20. Prediction versus decision

A prediction may be positive while the final decision is negative because economics, risk, execution, contract, or policy constraints fail.

Therefore:

```text
Prediction != Eligibility
Prediction != Decision
Prediction != ExpectedProfit
```

## 21. Probability versus expected value

A probability alone does not determine economic value.

Expected economic value requires additional defined quantities such as outcome magnitudes and costs.

The economic artifact must establish the exact transformation.

## 22. Thresholds

No probability or score threshold is frozen by A41.

A threshold is a policy parameter that must be validated under the complete economic and risk architecture.

## 23. Threshold optimization leakage

Selecting a threshold using final test performance contaminates the test set.

Threshold selection belongs inside the research/validation process and must be versioned.

## 24. Calibration drift

Calibration can change through time because the population or conditional relationship changes.

If recalibration is allowed, the update process must be versioned and causally constrained.

No recalibration frequency is chosen here.

## 25. Probability drift versus model drift

These are distinct:

```text
model output relationship changes
probability calibration changes
base-rate changes
feature distribution changes
```

Monitoring must eventually distinguish them rather than treating all deterioration as model failure.

## 26. Calibration monitoring

A production calibration monitor requires mature outcomes and therefore operates with a delay.

It cannot use future outcomes to alter predictions retrospectively.

## 27. Research multiple testing

Trying many calibration methods and selecting the best one on the final test set is a form of test overfitting.

All evaluated calibration candidates must be registered under A39.

## 28. Adversarial attack — raw score interpreted as probability

Invalid:

```text
model output = 0.8
therefore 80% probability
```

unless the model's output is explicitly defined as a probability for the exact target event.

## 29. Adversarial attack — future calibration

Invalid:

```text
future outcomes
 -> calibrate model
 -> apply calibrated probabilities to historical decisions
```

Calibration must respect the temporal training boundary.

## 30. Adversarial attack — latest model replay

Invalid:

```text
2026 decision
 -> use 2028 model
```

Historical replay must reconstruct the active model version at the decision time.

## 31. Adversarial attack — threshold selected after test

Invalid:

```text
test every threshold
 -> choose best test threshold
 -> report that same test performance
```

That converts the test into a tuning set.

## 32. Adversarial attack — eligibility conditioning hidden

If the model was trained only on executed trades but the probability is interpreted as applying to all opportunities, the conditioning population is wrong.

The training/population contract must explicitly define this distinction.

## 33. Determinism

Given the same feature snapshot, model version, model state, calibration version, and configuration, prediction must be reproducible.

## 34. Implementation gate

A41 cannot implement an actual probability or calibration function until:

```text
target event
label definition
model output semantics
calibration population
calibration training boundary
```

are resolved.

A prediction interface may be implemented independently.

## 35. Parameter classes

### Frozen architecture

```text
prediction identity
feature snapshot linkage
model-version linkage
raw-output/probability separation
calibration separation
decision-input separation
causal model-state ordering
threshold versioning
```

### Learned/configurable

```text
model parameters
calibration parameters
calibration method
threshold
recalibration frequency
```

only after validation under A39.

### External UNKNOWN

```text
actual target event
model family
label horizon
calibration source population
```

## 36. Completion criterion

A41 becomes `RESOLVED` when the system can answer for every prediction:

```text
What event does this prediction represent?
Which feature snapshot produced it?
Which model version produced it?
Was the output actually a probability?
If calibrated, which calibration data and version were used?
What population does the probability condition on?
What was known at decision time?
```

and reproduce the prediction without future leakage.

## ARCHITECTURE STATUS

**FROZEN:** prediction identity; feature linkage; model-version linkage; raw-output/probability separation; calibration separation; decision-input boundary; causal state ordering; threshold versioning.

**UNRESOLVED:** target event; label horizon; model family; probability semantics; calibration method; calibration population; threshold; recalibration frequency.

**BLOCKERS:** A26 target/horizon and model/prediction definitions remain unresolved. Therefore no numerical probability or calibration implementation is authorized.

**NEXT ARTIFACT:** A42 — Economic Value, Expected Value and Decision Utility Contract.
