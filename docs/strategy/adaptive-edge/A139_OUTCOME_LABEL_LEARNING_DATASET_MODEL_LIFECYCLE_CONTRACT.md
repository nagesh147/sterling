# A139 — Canonical Outcome, Label, Learning Dataset & Model Lifecycle Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

A139 defines the causal boundary from completed historical decisions to mature outcomes, labels, learning datasets, candidate models, validation, promotion, rollback, and future production versions.

It prevents outcome leakage, immature labels, selection bias, temporal contamination, survivorship bias, multiple-testing contamination, and adaptive feedback from changing historical truth.

## 1. Canonical learning chain

```text
Decision
  -> Outcome Observation
  -> Outcome Maturity
  -> Label
  -> Training Eligibility
  -> Dataset Snapshot
  -> Candidate Model
  -> Validation
  -> Promotion Decision
  -> Production Model Version
  -> Future Decision
```

Learning never mutates historical decisions, fills, positions, labels, or prior model versions.

## 2. Decision identity

Every learning observation references the immutable decision lineage:

```text
decision_id
decision_time
strategy_version
snapshot_id
feature_schema_version
probability_version
economic_assessment_id
eligibility_id
authorization_id
instrument/opportunity identity
```

Learning must not reconstruct historical decisions from current mutable state.

## 3. Outcome observation

An outcome observation records post-decision information, including as applicable:

```text
execution outcome
position outcome
realized economics
market path
contract lifecycle
liquidity/execution outcome
```

Outcome observation is not equivalent to outcome maturity.

## 4. Outcome maturity

An outcome is mature only when every input required by its label policy is causally available.

```text
mature_at(outcome)
    >=
latest_available_at(all required outcome observations)
```

The exact maturity horizon is policy-defined and must be versioned.

## 5. Label contract

```text
Label_i = LabelFunction(
    Decision_i,
    MatureOutcome_i,
    LabelPolicyVersion
)
```

A label policy must define:

```text
source population
positive condition
negative condition
neutral/ambiguous condition where applicable
observation horizon
maturity condition
units
boundary timestamps
missing/ambiguous outcome handling
policy version
```

No label may be selected because it produces attractive model statistics.

## 6. Horizon semantics

The canonical architecture supports multiple outcome horizons because A126 supports adaptive horizons.

A label must explicitly reference the horizon policy applicable to the originating decision:

```text
label_horizon_id
horizon_policy_version
```

A future outcome cannot be assigned to a decision using a horizon that was unavailable or unknown at that decision time.

Numerical horizon boundaries remain validation-dependent; they are not invented by A139.

## 7. Feature/label separation

For decision time `T_d`:

```text
feature.available_at <= T_d
```

For label construction:

```text
label.available_at > T_d
```

where the outcome is genuinely future information.

The label must never be included in the feature snapshot for the originating decision.

## 8. Training eligibility

A record is eligible for training only if:

```text
label_maturity_time <= training_cutoff
```

and all required dataset, feature, policy, and provenance conditions are satisfied.

Training eligibility is distinct from label maturity.

## 9. Dataset snapshot

Every training dataset is immutable and versioned:

```text
dataset_id
dataset_version
population_definition
feature_schema_version
label_policy_version
model_input_schema_version
source_cutoff
label_maturity_cutoff
purge_policy_version
embargo_policy_version
creation_time
```

A future dataset version may supersede an earlier one; historical datasets are never silently modified.

## 10. Population definition

The population must be explicitly defined before model evaluation.

Possible populations include:

```text
all evaluated opportunities
eligible opportunities
authorized opportunities
executed trades
```

The selected population is a policy decision and must not be changed after seeing test performance.

Where the learning target concerns opportunity quality rather than execution quality, filtering only to executed trades is forbidden because it can create selection bias.

## 11. Survivorship

Universe membership must be time-valid.

Historical training cannot use today's surviving instruments as the historical universe.

```text
universe_membership.available_at <= observation/decision boundary
```

Delisted, expired, or otherwise removed instruments remain represented when they belong to the historical population.

## 12. Temporal dependence

Overlapping outcome horizons can make observations dependent.

The dataset contract therefore requires explicit treatment of:

```text
purging
embargo
walk-forward separation
cluster/dependence handling
```

The numerical intervals are policy/validation parameters and must not be selected from test results.

## 13. Train / validation / test boundaries

All learning experiments must define chronological boundaries:

```text
TRAIN
  <
VALIDATION
  <
TEST
```

No sample may cross the boundary in a way that leaks future label or feature information.

The final test set remains untouched until the model/policy selection process is frozen.

## 14. Multiple testing

Every candidate experiment must retain:

```text
experiment_id
hypothesis
candidate configuration
training boundary
validation boundary
test boundary
selection rule
results
```

A failed candidate cannot be silently discarded and its existence forgotten.

Test-set selection is prohibited.

## 15. Candidate model

A candidate model is immutable and references:

```text
model_id
model_version
training_dataset_version
feature_schema_version
label_policy_version
algorithm/version
hyperparameter manifest
training boundary
creation time
```

A model artifact cannot change after creation.

## 16. Model validation

Promotion requires validation against a policy defined before observing the final test outcome.

Validation must evaluate, as applicable:

```text
statistical performance
calibration
stability
coverage
regime sensitivity
execution/economic relevance
risk impact
failure behavior
```

A high predictive metric alone cannot promote a model.

## 17. Model promotion

```text
CANDIDATE
   |
   v
VALIDATED
   |
   v
PROMOTION_ELIGIBLE
   |
   v
PROMOTED
```

Promotion creates a new immutable production version.

No model is promoted by overwriting a prior production version.

## 18. Rollback

A production model version can be deactivated by promoting a previously validated immutable version or a newly validated replacement.

Rollback does not rewrite historical decisions made under the prior version.

```text
Model V3 active
   |
   v
rollback
   |
   v
Model V2 active
```

## 19. Production boundary

A model version becomes eligible for live use only after:

```text
training complete
validation complete
promotion approved
artifact immutable
lineage complete
schema compatibility verified
```

The production decision references the exact model version used.

## 20. Feedback-loop isolation

```text
Past decision
   |
   v
Outcome
   |
   v
Label
   |
   v
Learning
   |
   v
Future model version
   |
   v
Future decision
```

There is no permitted edge from future learning output back into the historical decision that generated the observation.

## 21. Model drift

Drift detection is a separate observation process.

A detected drift condition does not automatically change the production model unless a promotion/replacement policy explicitly authorizes the transition.

No automatic retraining is assumed.

## 22. Data revisions

If a source correction changes historical evidence, the corrected canonical event/version must create a new downstream dataset/model lineage.

It must not silently mutate a previously trained dataset.

## 23. Label ambiguity

Ambiguous outcomes must have an explicit policy:

```text
NEUTRAL
EXCLUDE
UNRESOLVED
```

The policy must be versioned.

No ambiguous record may be assigned a positive/negative class merely to increase sample size.

## 24. Missing outcomes

If a required outcome never becomes available:

```text
LABEL_UNAVAILABLE
```

It must not become a negative outcome by default.

The population impact must be recorded for selection-bias analysis.

## 25. Causal invariants

For every training record `r`:

```text
feature.available_at(r) <= decision_time(r)
label_maturity_time(r) <= training_cutoff
```

For every promoted model:

```text
training_dataset_version
label_policy_version
feature_schema_version
model_version
```

must be immutable and traceable.

## 26. Hostile scenarios

### Immature label

```text
label_maturity_time > training_cutoff
```

Result:

```text
TRAINING_INELIGIBLE
```

### Future feature leakage

```text
feature.available_at > decision_time
```

Result:

```text
DATASET_INVALID
```

### Test-set tuning

Any parameter changed after observing final test results invalidates the test evaluation and requires a new untouched test boundary.

### Survivorship bias

Using current surviving instruments for historical membership invalidates the dataset.

### Selection bias

Restricting the population to profitable/executed observations when the target is defined over opportunities invalidates the population definition.

### Multiple testing

Selecting the best result from undisclosed candidate experiments invalidates the reported test claim.

### Model rollback

Rollback changes future production behavior only. Historical records remain bound to the original model version.

## 27. Frozen architecture

```text
immutable decision lineage
outcome/maturity separation
versioned label policy
causal training eligibility
immutable dataset snapshots
chronological train/validation/test boundaries
survivorship protection
selection-bias protection
purging/embargo boundary
multiple-testing provenance
immutable candidate models
explicit validation/promotion
rollback without historical mutation
feedback-loop isolation
data-revision lineage
explicit ambiguity/missingness semantics
```

## 28. Learned / validation-dependent

```text
label horizon values
label thresholds
population choice
feature set
model algorithm
hyperparameters
calibration method
purge interval
embargo interval
promotion thresholds
retraining cadence
drift thresholds
```

These cannot be selected merely because they improve an in-sample or final-test result.

## 29. External dependencies

```text
historical market/event data
historical universe membership
contract lifecycle history
corporate-action history where applicable
execution history
model artifact storage
configuration/policy registry
```

Where an external source is not yet selected, it remains an implementation dependency rather than an invented fact.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- outcome observation/maturity separation
- immutable decision lineage
- versioned label policies
- causal label maturity
- training eligibility boundary
- immutable dataset snapshots
- chronological train/validation/test separation
- survivorship protection
- selection-bias protection
- temporal dependence treatment boundary
- multiple-testing provenance
- immutable model versions
- validation/promotion state machine
- rollback semantics
- feedback-loop isolation
- historical data-revision lineage
- ambiguity/missingness semantics
- production model lineage

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- concrete historical provider(s) for any still-unselected external datasets
- concrete model artifact registry technology
- concrete dataset storage technology

CONFIGURATION TO VALIDATE:
- outcome horizons
- label thresholds
- population policy
- purge/embargo intervals
- promotion thresholds
- drift thresholds
- retraining cadence

LEARNED / VALIDATION-DEPENDENT:
- label definitions beyond the canonical interface
- model family
- hyperparameters
- calibration method
- promotion criteria

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A140 — Canonical Research, Walk-Forward Validation & Statistical Acceptance Contract
```
