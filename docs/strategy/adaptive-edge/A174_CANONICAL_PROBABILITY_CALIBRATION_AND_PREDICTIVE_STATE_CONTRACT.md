# A174 — Canonical Probability, Calibration & Predictive-State Contract

**Status:** CANONICAL  
**Authority:** Canonical semantic contract for predictive probability and calibrated predictive state  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A173

## 1. Purpose

A174 defines what a predictive probability means, how it is produced, how calibration is represented, and how uncertainty is propagated without allowing a score, classifier output, or heuristic confidence value to masquerade as a validated probability.

A174 freezes architecture, not numerical calibration values.

## 2. Probability identity

A predictive probability must be represented with:

```text
probability_id
model_id
model_version
feature_snapshot_id
prediction_time
causal_cutoff
event_definition
observation_horizon
raw_score_reference
probability_value
calibration_version
quality_state
configuration_version
```

## 3. Event definition

A probability is meaningless without a precisely defined event.

The event definition must specify:

```text
event_class
entry/reference time
observation horizon
terminal condition
invalid/ambiguous outcome handling
label maturity rule
```

No probability may be consumed without an event definition.

## 4. Probability domain

For a binary event:

```text
0 <= p <= 1
```

For multiclass predictions:

```text
p_k >= 0
Σ p_k = 1
```

Invalid probability vectors fail closed.

## 5. Probability versus score

A raw model score is not automatically a probability.

```text
raw_score != probability
```

A score becomes a probability only through a documented transformation with a versioned calibration contract where calibration is required.

## 6. Calibration

Calibration maps predictive outputs to probabilities using historical evidence without violating the training/validation/test boundaries.

The calibration artifact must identify:

```text
calibration_method
calibration_dataset
fit_boundary
validation_boundary
calibration_version
training_population
```

## 7. Calibration leakage

Calibration parameters must not be fitted using observations unavailable at the historical prediction boundary.

Using future observations to calibrate historical predictions is a look-ahead violation.

## 8. Calibration population

The calibration population must be explicitly defined.

It must preserve:

```text
instrument population
regime/time population
horizon
event definition
label maturity
eligibility rules
```

A calibration population cannot silently change because new data becomes available.

## 9. Out-of-sample calibration

Where calibration is learned, calibration evaluation must be separated from the data used to fit it.

A calibration method cannot be accepted merely because it improves in-sample likelihood.

## 10. Probability quality

Canonical quality states include:

```text
VALID
UNCALIBRATED
INSUFFICIENT_DATA
OUT_OF_DOMAIN
STALE
INVALID
UNKNOWN
```

An `UNCALIBRATED` score cannot be represented as a validated probability.

## 11. Domain shift

A predictive model may receive a feature population materially outside its validated domain.

The predictive state must preserve this condition:

```text
IN_DOMAIN
OUT_OF_DOMAIN
UNKNOWN_DOMAIN
```

The downstream decision policy determines whether an out-of-domain probability is usable.

## 12. Model identity

Every prediction is bound to:

```text
model_id
model_version
feature_set_version
formula/version dependencies
calibration_version
configuration_version
```

A prediction cannot be reinterpreted under a later model version.

## 13. Prediction timing

A prediction is timestamped at the time it became available to the decision process.

It must preserve:

```text
prediction_time
causal_cutoff
```

The model cannot consume feature state produced after the prediction boundary.

## 14. Probability persistence

Once used in a consequential decision, the predictive state is immutable.

Later recalibration produces a new prediction artifact, not mutation of the historical prediction.

## 15. Multiple predictions

Multiple predictions for the same decision context must have explicit version/attempt identity.

The latest prediction cannot silently overwrite earlier predictive evidence.

## 16. Horizon semantics

Probability must be horizon-specific.

```text
P(event within H1)
```

is not interchangeable with:

```text
P(event within H2)
```

A model/horizon mismatch is a conformance failure.

## 17. Class imbalance

Class prevalence is part of the calibration/evaluation population and must not be altered by undocumented resampling when interpreting real-world probability.

Sampling transformations used for training must be recorded separately from deployment probability semantics.

## 18. Selection bias

Probability validation must identify whether observations were selected based on information unavailable at prediction time.

Selection criteria are part of dataset lineage.

## 19. Multiple testing

If multiple model/calibration candidates are evaluated, the selection process must remain auditable.

A winning candidate is not automatically an unbiased estimate of future performance.

## 20. Probability uncertainty

A single point estimate may be insufficient when the predictive sample is sparse or out of domain.

The architecture permits an explicit uncertainty descriptor, but does not require a particular statistical method.

## 21. Decision consumption

Decision logic may consume:

```text
probability_value
probability_quality
calibration_version
model_version
horizon
```

It must not consume an undocumented internal score as if it were the canonical probability.

## 22. Economics separation

Probability is not expected return.

```text
probability
!=
economic_value
```

Economic valuation remains a separate contract.

## 23. Risk separation

Probability does not itself authorize risk.

```text
probability
!=
risk_authorization
```

Risk policy consumes probability together with economics, exposure, state, and policy.

## 24. Label maturity

A probability may be evaluated against an outcome only after the outcome's observation horizon has matured.

Premature evaluation is prohibited.

## 25. Calibration acceptance

Calibration acceptance must be based on out-of-sample evidence and predefined validation criteria.

Exact numerical acceptance thresholds remain UNFROZEN.

## 26. Model promotion

A model/calibration candidate cannot become production-authoritative merely because it has a higher historical metric.

Promotion requires the complete A159/A166 governance path.

## 27. Fallback behavior

If the required probability is unavailable, invalid, or materially out of domain, the system must follow an explicit decision policy.

It must not substitute:

```text
0.5
previous probability
raw score
current model output from another horizon
```

without a canonical rule.

## 28. Hostile scenarios

The implementation must test:

```text
probability < 0
probability > 1
multiclass sum != 1
missing calibration
future calibration data
wrong model version
wrong feature version
wrong horizon
out-of-domain feature population
sparse calibration population
class-prevalence shift
selection bias
multiple-testing selection
premature label
stale prediction
prediction duplicated
prediction revised after decision
```

## 29. Invariants

```text
INV-174-001  A score is not a probability without an explicit mapping.
INV-174-002  Every probability has an explicit event definition.
INV-174-003  Binary probabilities remain within [0,1].
INV-174-004  Multiclass probabilities are non-negative and sum to one.
INV-174-005  Probability computation respects causal feature availability.
INV-174-006  Calibration cannot use future information.
INV-174-007  Calibration population is versioned.
INV-174-008  Model and feature versions are explicit.
INV-174-009  Probability is horizon-specific.
INV-174-010  Probability is not economics.
INV-174-011  Probability is not risk authorization.
INV-174-012  Historical predictions are immutable after consequential use.
INV-174-013  Premature labels cannot validate historical predictions.
INV-174-014  Missing probability cannot silently become a neutral value.
INV-174-015  Model selection lineage remains auditable.

## 30. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- probability identity
- event-definition requirement
- score/probability separation
- probability-domain constraints
- calibration boundary
- calibration leakage prevention
- model/version binding
- horizon binding
- prediction timing
- predictive-state immutability
- domain-state representation
- probability/economics separation
- probability/risk separation
- label-maturity boundary
- promotion boundary
- explicit unavailable/fallback behavior

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- final calibration method
- calibration registry implementation
- exact predictive uncertainty method
- exact domain-shift detector
- exact model registry implementation

CONFIGURATION TO VALIDATE:
- calibration windows
- minimum calibration population
- domain-shift thresholds
- prediction freshness
- probability acceptance criteria

LEARNED / VALIDATION-DEPENDENT:
- model parameters
- calibration parameters
- probability calibration mapping
- empirical domain thresholds

BLOCKERS:
None for specification.
Production probability remains blocked until model/calibration evidence satisfies the research and production gates.

NEXT ARTIFACT:
A175 — Canonical Economic Valuation, Transaction-Cost & Opportunity Contract
```