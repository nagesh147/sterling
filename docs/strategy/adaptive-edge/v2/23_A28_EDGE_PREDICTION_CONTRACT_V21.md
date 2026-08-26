# Adaptive Edge V2.1 — A28 Edge / Prediction Contract

**Artifact:** A28
**Version:** 2.1.0
**Status:** PROPOSED-RESEARCH-CONTRACT
**Depends on:** A26-ND, A27-TD

## 1. Purpose

Define the prediction boundary from an immutable causal FeatureSnapshot to a horizon-conditional directional probability.

## 2. Target event

The prediction event is exactly the A26-ND label:

```text
Y_h ∈ {UP, DOWN, NEUTRAL}
```

for the selected underlying/reference instrument and selected horizon `h`.

The target is based on the terminal normalized future return of that reference instrument.

## 3. Model family

The primary V2.1 baseline is the canonical multinomial logistic family:

```text
P(Y=k | X,h)
    = exp(beta_k · X_h)
      / Σ_j exp(beta_j · X_h)
```

where `X_h` is the causal feature representation available at decision time and associated with horizon `h`.

The model coefficients are learned state, never hand-authored strategy constants.

Empirical similarity and Bayesian estimators remain research comparators unless a promotion policy explicitly selects them.

## 4. Loss

The source-supported training family is:

```text
Loss
    = CrossEntropy + lambda * ||beta||^2
```

`lambda` is a learned/research configuration and is not production-authorized without walk-forward validation.

## 5. Model identity

Every prediction records:

```text
prediction_id
decision_time
feature_snapshot_id
feature_set_version
strategy_version
model_version
model_state_version
horizon_id
raw_logits
raw_output
calibration_version
calibrated_probability
```

## 6. Calibration

V2.1 uses temperature scaling as the baseline calibration method.

Temperature is fitted only on the validation partition and is versioned with the calibration policy.

Holdout labels are never passed to calibration fitting.

## 7. Probability semantics

A value is a probability only when:

```text
its target event is defined
its class space is fixed
its model output is valid
its calibration provenance is present where calibration is required
```

A raw `[0,1]` value is not automatically a probability.

## 8. Causal state evolution

If model state evolves:

```text
state_(t-1)
    -> prediction_t
    -> mature outcome
    -> eligible learning update
    -> state_t
```

No future label may modify the model state used for an earlier prediction.

## 9. Feature restrictions

Prediction may consume only:

```text
FeatureSnapshot
ModelVersion
ModelStateVersion
HorizonState
```

It may not consume:

```text
future outcome
Kite fill
Kite position
realized P&L
future execution cost
future liquidity
future option selection
```

## 10. Thresholds

Probability/decision thresholds are not part of the prediction function.

They belong to the downstream economic/eligibility policy and must be selected independently through the declared research protocol.

## 11. Uncertainty

Prediction output must distinguish:

```text
probability
model uncertainty
estimation uncertainty
calibration state
```

A missing uncertainty estimator must not be represented as zero uncertainty.

## 12. Attack

### Leakage

Future outcomes cannot enter feature normalization or model state before maturity.

### Calibration leakage

Validation labels only may fit temperature. Holdout remains untouched.

### Horizon leakage

If multiple horizons are evaluated, horizon selection is a research-selection operation and must be recorded.

### Model selection leakage

Comparing logistic/similarity/Bayesian models on holdout to select the final model invalidates the holdout.

### Probability misuse

Probability must not be interpreted as economic profitability without the A29 economic layer.

## ARCHITECTURE STATUS

**FROZEN:** target event; multinomial logistic baseline; model/provenance identity; causal state ordering; temperature-scaling calibration boundary; probability/decision separation.

**LEARNED/VALIDATED:** coefficients; L2 regularization; calibration temperature; feature subset; horizon-specific state; decision thresholds.

**UNKNOWN:** final feature subset; horizon values; volatility estimator; minimum-data policies; uncertainty estimator.

**BLOCKERS:** no blocker to the prediction architecture; numerical promotion requires A26/A27 dependencies and walk-forward evidence.

**NEXT ARTIFACT:** A29 — Economic Value, Execution Cost and Conservative Decision Contract.
