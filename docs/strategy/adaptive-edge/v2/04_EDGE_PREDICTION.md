# Adaptive Edge V2 — Edge / Prediction Definition

**Version:** 2.0.0-draft
**Artifact:** A28
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Depends on:** A25 Strategy Charter, A26 Opportunity and Outcome Definition, A27 Canonical Feature Set and Feature Semantics
**Implementation authorization:** NONE

## 1. Purpose

A28 defines the prediction boundary of Adaptive Edge V2.

The prediction layer answers:

> Given an Opportunity Evaluation and its causally valid FeatureSnapshot, what future quantity does V2 estimate, with what uncertainty and provenance?

A28 does not decide whether to trade, authorize risk, select a contract, size a position, or execute an order.

## 2. Causal position

The prediction pipeline is:

```text
FeatureSnapshot(t_d)
        |
        v
Prediction Model Version
        |
        v
Prediction Object
        |
        v
Calibration / uncertainty representation
        |
        v
Economic Assessment
```

The prediction may consume only information available at `decision_time`.

## 3. Prediction input contract

Canonical input:

```text
PredictionInput
{
    opportunity_id
    strategy_version
    feature_set_version
    feature_snapshot_reference
    model_version
    decision_time
    instrument_context
    provenance
}
```

The prediction model may not directly read raw future observations, mature labels, execution results, realized P&L, or later risk state.

## 4. Prediction output contract

Canonical architecture:

```text
Prediction
{
    prediction_id
    opportunity_id
    strategy_version
    model_version
    feature_set_version
    decision_time

    target_definition_version
    horizon_definition_version

    prediction_type
    prediction_value
    uncertainty
    calibration_reference

    provenance
}
```

The exact target and prediction type remain unresolved.

## 5. Prediction is not opportunity

```text
OpportunityExists
    !=
Prediction
```

The opportunity population must be constructible without knowing the eventual prediction.

A prediction can be generated only after the opportunity and FeatureSnapshot exist.

## 6. Prediction is not economic value

```text
Prediction
    !=
ExpectedGrossValue
```

A prediction may describe a probability, return, magnitude, distribution, or another target.

Economic value requires a separate mapping that accounts for payoff and execution economics.

No such mapping is frozen by A28.

## 7. Prediction target dependency

A valid prediction requires:

```text
TargetDefinition
+
ObservationHorizon
+
Label/Outcome Semantics
```

A26 currently leaves:

```text
PRIMARY_TARGET = UNKNOWN
H_outcome = UNKNOWN
```

Therefore a production prediction target cannot yet be frozen.

This is a genuine dependency, not a parameter to guess.

## 8. Prediction target candidates

Architecturally, V2 could predict a quantity such as:

```text
P(Y = 1 | X_t)
E[Y | X_t]
quantiles(Y | X_t)
P(Y >= threshold | X_t)
```

These are candidate mathematical forms only.

A28 does not select one until the outcome/label semantics are resolved.

## 9. Probability semantics

If V2 eventually predicts a probability:

```text
p_t = P(Y = 1 | X_t)
```

then the event `Y = 1` must be defined by the authoritative label definition.

The number `p_t` has no strategy meaning until that event is defined.

Therefore no probability threshold is selected here.

## 10. Regression semantics

If V2 eventually predicts a continuous outcome:

```text
m_t = E[Y | X_t]
```

then the units and outcome horizon of `Y` must be frozen first.

No return unit, point target, percentage target, or monetary target is assumed.

## 11. Distributional semantics

If V2 predicts a distribution:

```text
F_t(y) = P(Y <= y | X_t)
```

then the target's support, observation horizon, censoring treatment, and calibration method must be specified.

No distributional model is selected here.

## 12. Horizon dependency

Every prediction must identify the horizon definition used to construct its target:

```text
horizon_definition_version
```

A prediction generated with horizon H1 cannot be silently compared with a label generated under H2.

Changing the horizon creates a new target definition and requires a new prediction/model version.

## 13. Model versioning

Every prediction must identify:

```text
model_version
feature_set_version
target_definition_version
horizon_definition_version
strategy_version
```

A model version is immutable after promotion.

A changed model is a new version, even if the implementation class remains the same.

## 14. Learned quantities

Any fitted model parameters are learned state.

Before promotion, the learning artifact must define:

```text
historical population
positive/negative or continuous label
observation horizon
label maturity
training boundary
validation boundary
test boundary
feature-set version
model-selection procedure
hyperparameter-selection procedure
calibration procedure
update frequency
promotion rule
rollback rule
```

A28 does not invent these procedures.

## 15. Training boundary

For a prediction at `t_d`, model parameters used by that prediction must be trained only from observations whose labels were mature by the permitted training cutoff.

A future-matured label cannot be used merely because its feature observation occurred before the prediction date.

The maturity boundary belongs to A26 and the detailed learning protocol belongs to a later artifact.

## 16. Validation boundary

The validation set must remain separate from the final test set.

Repeated inspection of test performance to select:

```text
features
horizon
model class
hyperparameters
thresholds
```

is prohibited.

## 17. Calibration

If the prediction is probabilistic, calibration is a separate transformation from prediction generation.

Conceptually:

```text
raw_model_output
      |
      v
calibration_model_version
      |
      v
calibrated_probability
```

The calibration method, population, and update policy remain unresolved.

Calibration must obey the same temporal validation boundaries as the predictive model.

## 18. Uncertainty

A prediction may optionally include uncertainty.

Uncertainty is not automatically equivalent to:

```text
risk
volatility
execution uncertainty
```

These are distinct semantic objects.

If uncertainty becomes part of economic eligibility, that dependency must be explicitly defined in the economic artifact.

## 19. Missing features

A prediction cannot silently replace an invalid required feature with a strategy-defined value unless the feature/model contract explicitly authorizes that behavior.

Canonical prediction statuses may include:

```text
VALID
INSUFFICIENT_FEATURES
INVALID_INPUT
MODEL_UNAVAILABLE
CALIBRATION_UNAVAILABLE
```

A failed prediction must not silently become a neutral or zero prediction.

## 20. Prediction determinism

Given identical:

```text
FeatureSnapshot
model_version
calibration_version
strategy_version
```

and identical deterministic inference configuration, the prediction must be reproducible.

If stochastic inference is ever introduced, its randomness/provenance must be explicitly versioned and reproducible.

No stochastic model is required by A28.

## 21. Economic boundary

The economic layer may consume the prediction, but the prediction layer must not contain economic eligibility logic.

Forbidden:

```text
prediction -> hidden minimum-profit threshold
prediction -> hidden risk increase
prediction -> hidden contract selection
prediction -> hidden quantity
```

Those are later strategy artifacts.

## 22. Attack — target leakage

Forbidden:

```text
future label -> feature selection
future label -> normalization
future label -> contemporaneous prediction input
```

The mature target may be used for training only after its defined maturity boundary.

## 23. Attack — horizon leakage

If the target horizon is defined using information after the intended observation boundary, the prediction target can encode future information inconsistently.

Therefore horizon semantics must be explicit and versioned.

## 24. Attack — calibration leakage

A calibration model fitted on the final test period invalidates the test evaluation.

Calibration must have its own training/validation boundary.

## 25. Attack — model-selection leakage

Selecting a model because it performs best on the final test period is forbidden.

Model selection belongs inside the training/validation process.

## 26. Attack — economic contamination

If the prediction model is trained directly on realized strategy P&L generated by a later position-sizing or execution policy, the prediction target may silently change when execution policy changes.

The target must therefore identify whether it represents:

```text
market outcome
execution outcome
accounting outcome
```

as established by A26.

## 27. Attack — circular risk dependency

Forbidden:

```text
risk authorization
    -> prediction input
    -> prediction
    -> predicted value
    -> risk authorization
```

Unless a later artifact explicitly introduces a causal state variable, the base V2 prediction path remains independent of risk authorization.

## 28. Attack — feature overfitting

The model must not use all candidate features merely because they are available.

Feature selection is part of model selection and must be included in temporal validation.

A27's feature inventory is therefore not automatically the final model input set.

## 29. Attack — class imbalance

If the target becomes binary, class imbalance must be measured from the authoritative training population.

No synthetic balancing method, class weight, oversampling ratio, or threshold is selected here.

## 30. Attack — non-stationarity

Market relationships may change over time.

V2 therefore treats model parameters and calibration as versioned learned state rather than permanent truths.

The learning artifact must later define monitoring and promotion criteria.

## 31. Attack — multiple testing

If multiple targets, horizons, models, features, or hyperparameters are explored, the validation design must account for the resulting selection process.

The final test set must remain untouched until the specification and model-selection procedure are frozen.

## 32. Attack — survivorship

The training population must use time-valid instruments and opportunities from A26/A23 rather than only contracts that remain available at the end of the sample.

## 33. Attack — data revisions

A prediction's provenance must retain the data/model versions used to generate it.

A later source-data revision cannot silently rewrite a historical prediction record.

## 34. Prediction object and causal graph

The intended dependency is:

```text
FeatureSnapshot(t_d)
       |
       v
ModelVersion trained only on eligible historical data
       |
       v
Prediction(t_d)
       |
       v
EconomicAssessment(t_d)
```

The training process is separate:

```text
Mature historical outcomes
       |
       v
LabelDataset(version)
       |
       v
Temporal train/validation/test split
       |
       v
Model fitting/selection
       |
       v
Promoted ModelVersion
```

A promoted model may then be used only on future decision timestamps within its authorized validity period.

## 35. Current prediction specification

At this stage the only production-authorized mathematical boundary is:

```text
Prediction_t
    = ModelVersion(FeatureSnapshot_t)
```

subject to the causal and versioning contracts above.

The exact target function remains unresolved because A26 has not yet defined `Y` or `H_outcome`.

## 36. Explicitly NOT chosen

A28 does not choose:

```text
logistic regression
linear regression
random forest
gradient boosting
neural network
reinforcement learning
LLM
probability threshold
return threshold
prediction horizon
training window
retraining frequency
calibration method
model coefficients
```

The first implementation should use the simplest model justified by the later statistical specification and validation results. No model-class complexity is frozen here.

## 37. Dependencies

### A26 — Opportunity and Outcome Definition

Required to resolve:

```text
Y
H_outcome
label definition
maturity semantics
```

### A27 — Feature Set

Provides the causally valid feature vocabulary and FeatureSnapshot contract.

### A29 — Economic Assessment

Will define how the prediction becomes an economic quantity and eligibility decision.

### Learning artifact

Will define training, validation, test, calibration, promotion, and update rules.

## 38. Current unresolved state

```text
PRIMARY_TARGET               = UNKNOWN
H_outcome                    = UNKNOWN
prediction_type              = UNKNOWN
probability/regression choice= UNKNOWN
calibration method           = UNKNOWN
model class                  = UNKNOWN
training window              = UNKNOWN
retraining frequency         = UNKNOWN
promotion rule               = DEFERRED
```

These are not implementation TODOs to fill with conventional defaults.

## 39. Completion criterion

A28 becomes fully RESOLVED only when:

```text
target semantics
+ target horizon
+ prediction type
+ input feature set/version
+ model-selection protocol
+ training/validation/test boundaries
+ calibration semantics where applicable
+ uncertainty semantics where applicable
+ promotion/update rules
```

are explicitly defined and survive causal/statistical attack.

## ARCHITECTURE STATUS

Frozen:

```text
prediction-layer ownership
causal prediction input boundary
prediction object/versioning
model provenance
prediction/economics separation
training vs inference separation
calibration separation
missing-input failure states
model-selection leakage prohibition
```

## UNRESOLVED

```text
primary target
outcome horizon
prediction type
final feature set
model class
calibration
training population
validation protocol
promotion/update rules
```

## BLOCKERS

A28 cannot be fully resolved until A26 resolves the target and observation horizon.

No production prediction model or threshold may be implemented before those dependencies are resolved.

## NEXT ARTIFACT

**A29 — Economic Assessment and Eligibility Definition**

A29 must define how a prediction is transformed into expected economic value, execution-cost treatment, and a causally valid eligibility decision. It must not silently assume a target, horizon, strike, expiry, or risk formula that A26/A23/A24 have not resolved.
