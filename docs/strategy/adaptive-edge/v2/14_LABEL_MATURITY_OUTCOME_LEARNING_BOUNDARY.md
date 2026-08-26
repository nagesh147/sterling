# Adaptive Edge V2 — Label Maturity, Outcome Construction and Learning Boundary

**Artifact:** A38  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A38 defines when a historical decision becomes a valid learning observation and prevents immature outcomes, future information, and adaptive feedback from leaking into earlier decisions.

The canonical temporal chain is:

```text
Decision
  -> Outcome observation
  -> Outcome maturity
  -> Label
  -> Training eligibility
  -> Training dataset
  -> Model/policy candidate
  -> Validation
  -> Promotion
```

A38 does not choose a target, horizon, label threshold, or model update frequency that has not been defined by an authoritative source.

## 2. Core distinction

These are distinct:

```text
OutcomeObserved
OutcomeMature
LabelConstructed
TrainingEligible
TrainingUsed
```

An outcome may be partially observed without being mature enough to construct the final label.

## 3. Decision identity

Every learnable observation must reference the original decision:

```text
DecisionRecord
{
    decision_id
    decision_time
    strategy_version
    feature_snapshot_id
    prediction_version
    economic_assessment_id
    eligibility_id
    risk_authorization_id
    instrument/opportunity identity
}
```

Learning cannot reconstruct the decision from mutable current state.

## 4. Outcome observation

An outcome observation records information that becomes available after the decision.

Possible components include:

```text
execution outcome
position outcome
realized economic result
market path
contract lifecycle event
```

The exact outcome population remains unresolved because A26 target/horizon semantics remain unresolved.

## 5. Label definition

A label is a deterministic transformation:

```text
Label_i = LabelFunction(Decision_i, Outcome_i, LabelPolicyVersion)
```

The label function must be defined before training.

No label is inferred from model performance, desired class balance, or future selection results.

## 6. Required label semantics

A production label definition must specify:

```text
source population
positive condition
negative condition
observation horizon
maturity condition
unit
boundary timestamps
handling of ambiguous outcomes
handling of missing outcomes
policy version
```

A mathematically valid formula without these semantics is incomplete.

## 7. Target/horizon dependency

A38 cannot resolve the actual label until A26 defines:

```text
primary target
outcome horizon
outcome semantics
```

Therefore the canonical label formula remains:

```text
UNKNOWN
```

at this artifact stage.

This is intentional, not a design failure.

## 8. Label maturity

A label becomes mature only when all information required by the label function is known under the policy's causal boundary.

Conceptually:

```text
Mature_i(t)
    = true
```

only when every required observation has become available by `t`.

No future value may be used before that maturity time.

## 9. Maturity timestamp

Every mature label must carry:

```text
label_maturity_time
```

This is the earliest timestamp at which the label could legitimately have been constructed.

The training dataset cannot contain a label as if it existed before this timestamp.

## 10. Training boundary

Training at time `T_train` may use only labels whose maturity time satisfies:

```text
label_maturity_time <= T_train
```

subject to any additional embargo or dependency constraints.

This prevents immature outcomes from entering training.

## 11. Feature timestamp boundary

Features used to predict decision `i` must satisfy:

```text
feature_available_time <= decision_time
```

A feature may have an observation timestamp earlier than its availability timestamp; the availability timestamp is the relevant causal boundary.

## 12. Label-feature separation

A label may depend on future observations relative to the decision because it is an outcome.

The label must never be present as an input feature for the same decision.

Forbidden:

```text
future outcome -> contemporaneous feature
```

## 13. Overlapping outcomes

If outcome horizons overlap across decisions, the resulting observations are not automatically independent.

The learning/evaluation artifact must account for temporal dependence when constructing validation/test samples.

A38 does not select a specific statistical correction yet.

## 14. Purging and embargo

Where training and validation windows overlap through outcome horizons or feature availability, a later learning artifact may require:

```text
purging
embargo
walk-forward separation
```

The exact intervals are not selected here because the target horizon is unresolved.

## 15. Selection bias

Training data must represent the policy that actually generated observations, not only successful or selected trades.

For example, filtering training records to profitable historical trades creates label-selection bias.

Rejected/ineligible decisions may need to remain in the candidate population where the learning target is defined over opportunities rather than executed trades.

The exact population is unresolved.

## 16. Survivorship bias

Historical training populations must not exclude observations solely because instruments later expired, became unavailable, or lost economic relevance.

The historical universe must correspond to what was knowable at each decision time.

## 17. Missing outcomes

If a label requires information that never becomes available or cannot be reconstructed reliably, the observation must be explicitly classified:

```text
LABEL_UNAVAILABLE
LABEL_AMBIGUOUS
LABEL_INVALID
```

It must not be silently assigned a negative label.

## 18. Ambiguous outcomes

If multiple event sequences are compatible with the available historical data and produce different labels, the observation is ambiguous.

A38 forbids choosing the favorable interpretation solely to preserve a trade or increase sample size.

The later evaluation policy must specify whether ambiguous observations are excluded, conservatively resolved, or represented probabilistically.

## 19. Censored outcomes

An outcome may be censored if the observation period ends before the required horizon.

Censored observations must not be treated as mature negatives or positives without an explicit statistical definition.

## 20. Label versioning

Changing any of the following creates a new label-policy version:

```text
target definition
positive/negative condition
horizon
maturity rule
missing-data treatment
ambiguous-outcome treatment
```

Historical labels must retain their original policy version.

## 21. Training population identity

A training dataset must be reproducible from:

```text
source data versions
feature policy version
label policy version
population policy version
cutoff timestamp
embargo/purge policy
```

A dataset cannot be identified only by a mutable database query.

## 22. Training boundary

A model/policy trained at time `T` must not consume observations whose label maturity is after `T`.

This includes observations that are already present in a database but were not causally knowable at `T`.

## 23. Validation boundary

Validation observations must be causally separated from training observations according to the later evaluation policy.

The validation period cannot be used to tune hyperparameters repeatedly and then still be treated as untouched validation evidence.

## 24. Test boundary

The final test population must remain untouched until the model/policy and its selection procedure are frozen.

Repeated test-set inspection converts the test set into a tuning set.

A38 therefore requires explicit test-set protection.

## 25. Model/policy update

An adaptive system may update only through a versioned promotion event:

```text
Mature observations
      |
      v
Training dataset version
      |
      v
Candidate model/policy
      |
      v
Validation
      |
      v
Promotion decision
      |
      v
Active model/policy version
```

A candidate cannot become active merely because it performs better on an in-sample metric.

## 26. Promotion timestamp

Every promoted model/policy must have:

```text
promotion_time
active_from
training_data_cutoff
validation_data_boundary
test-data status
model/policy version
```

The promoted version may influence decisions only at or after `active_from`.

## 27. Rollback

A production model/policy must be rollbackable to a prior known version without rewriting historical decisions.

Rollback changes future behavior only.

## 28. No retroactive adaptation

Forbidden:

```text
newly observed outcome
    -> modify old prediction
    -> modify old eligibility
    -> modify old trade decision
```

The observation may affect a future model/policy version after the defined learning process.

## 29. Multiple-testing attack

If many targets, horizons, features, thresholds, or model variants are tested and the best result is selected, the selection process itself becomes part of the statistical procedure.

A38 therefore requires the final evaluation artifact to account for research-selection effects.

No claim of out-of-sample validity is made merely because one candidate passed a single backtest.

## 30. Adaptive feedback attack

If model performance changes the selection of future data and that future data changes the model again, the learning process becomes path-dependent.

Every promotion event must be recorded so the exact historical policy path can be reconstructed.

## 31. Leakage through normalization

Feature normalization/scaling parameters are learned quantities and must be fit only on the permitted training population.

Using full-history statistics to normalize earlier observations can leak future distribution information.

## 32. Leakage through feature selection

Feature selection performed using validation/test observations contaminates those evaluation boundaries.

The selected feature set must be versioned and trained only within the permitted research boundary.

## 33. Leakage through contract selection

If the model selects among instruments using future realized performance, the selection outcome becomes a label leak.

Historical candidate generation must remain causally valid under A34.

## 34. Learning data lineage

Every training observation should be traceable:

```text
raw event
 -> canonical event
 -> decision
 -> feature snapshot
 -> outcome
 -> mature label
 -> training row
```

A training row without this lineage is not production-auditable.

## 35. Determinism

Given identical source versions, policy versions, cutoff, and deterministic transformation code, the training population and labels must be reproducible.

## 36. Implementation gate

A38 cannot define executable learning code until A26 resolves the target/horizon and the feature/prediction contracts resolve the prediction semantics.

The temporal architecture may be implemented independently.

## 37. Parameter classes

### Frozen architecture

```text
label maturity boundary
training cutoff rule
feature availability boundary
label versioning
training/validation/test separation
promotion versioning
rollback
lineage
no retroactive adaptation
```

### Learned/configurable

```text
label threshold
outcome horizon
model parameters
feature-selection parameters
normalization parameters
update frequency
```

only after their authoritative definitions and validation procedures exist.

### External UNKNOWN

```text
outcome source completeness
execution/accounting maturity guarantees
historical event corrections
```

## 38. Completion criterion

A38 becomes `RESOLVED` when the system can answer for every training row:

```text
What decision generated it?
What information was available then?
When did the outcome become knowable?
When did the label mature?
Why was the row eligible for training?
Which policy/version generated the label?
Which training cutoff included it?
```

and can reproduce the same dataset without future leakage.

## ARCHITECTURE STATUS

**FROZEN:** causal label maturity; feature availability boundary; training cutoff; label versioning; temporal dataset lineage; validation/test separation; promotion timestamps; rollback; no retroactive adaptation.

**UNRESOLVED:** target; outcome horizon; positive/negative condition; training population definition; exact purge/embargo; update frequency; model/policy learning semantics.

**BLOCKERS:** A26 target/horizon remains unresolved. Exact label construction is therefore blocked by source definition.

**NEXT ARTIFACT:** A39 — Training / Validation / Test Walk-Forward Evaluation Contract.
