# Adaptive Edge V2 — Opportunity and Outcome Definition

**Version:** 2.0.0-draft
**Artifact:** A26
**Status:** SPECIFICATION-DRAFT
**Depends on:** A25 Strategy Charter
**Implementation authorization:** NONE

## 1. Purpose

This artifact defines the canonical unit on which Adaptive Edge V2 may form a prediction and the future observable outcome from which that prediction can eventually be evaluated and labeled.

It deliberately separates:

```text
opportunity existence
outcome observation
label construction
trading decision
```

The artifact does not define a numerical prediction threshold, trading horizon, strike rule, expiry rule, stop, target, or position size.

## 2. Problem solved

A predictive system is invalid if the object being predicted is ambiguous.

V2 therefore requires an explicit distinction between:

```text
what was known at decision time
        |
        v
what candidate/opportunity existed
        |
        v
what happened afterward
        |
        v
how that future observation is converted into a label
```

No future observation may participate in determining whether the contemporaneous opportunity existed.

## 3. Canonical Opportunity

An `Opportunity` is a time-indexed candidate state that satisfies the structural conditions required for evaluation, before economic eligibility, risk authorization, sizing, and execution.

Canonical schema:

```text
Opportunity
{
    opportunity_id
    strategy_version

    decision_time
    observation_cutoff_time

    instrument_context
    feature_snapshot_reference

    opportunity_definition_version

    status
    reason_codes

    provenance
}
```

`Opportunity` is an informational object. It is not evidence that a trade should occur.

## 4. Opportunity existence rule

The canonical existence predicate is:

```text
OpportunityExists(t_d)
    = structural_conditions_known_at_t_d_are_satisfied
```

The structural conditions must depend only on information with:

```text
availability_time <= t_d
```

The exact structural conditions are deferred to the next strategy-definition artifact. This artifact freezes the semantic boundary, not the numerical signal.

## 5. Opportunity is not prediction

```text
OpportunityExists
    !=
PredictedOutcome
```

An opportunity is a candidate state.

Prediction estimates future outcome conditional on that candidate.

This prevents a model's prediction from becoming part of the definition of the historical population on which the model is trained unless a later artifact explicitly and causally defines such a dependency.

## 6. Opportunity population

For a decision timestamp `t_d`, define:

```text
O(t_d) = set of candidate opportunities generated from
         information available at t_d
```

Every member of `O(t_d)` must have:

```text
unique opportunity_id
strategy version
causal observation cutoff
instrument context
feature snapshot reference
```

The population definition must be deterministic for identical source state and versioned policy.

## 7. No future filtering

The following are forbidden when constructing `O(t_d)`:

```text
future return
future MFE/MAE
future realized P&L
future liquidity
future contract availability
future label
future execution result
```

A candidate may subsequently be labeled as successful, unsuccessful, censored, or invalid. That later classification must not retroactively alter whether the candidate existed at `t_d`.

## 8. Opportunity identity

Two observations must not be merged merely because they concern the same instrument.

Canonical identity is at least:

```text
strategy_version
opportunity_definition_version
instrument_context
observation_cutoff_time
```

The final uniqueness key may be refined when the instrument and event model are frozen.

## 9. Overlapping opportunities

Overlapping opportunities are not automatically duplicates.

For example:

```text
Opportunity A at t1
Opportunity B at t2
```

may both exist for the same instrument if the opportunity definition permits it.

Whether multiple opportunities may coexist in the trading state is a later portfolio/position artifact.

## 10. Opportunity status

Canonical informational statuses:

```text
CANDIDATE
VALID
INVALID_DATA
SUPERSEDED
```

`VALID` means only that the opportunity satisfies the opportunity-definition contract.

It does not mean:

```text
profitable
eligible
risk-authorized
executable
```

## 11. Canonical Outcome Observation

An `OutcomeObservation` records future information that becomes observable after the opportunity decision.

Canonical schema:

```text
OutcomeObservation
{
    outcome_id
    opportunity_id

    outcome_start_time
    outcome_end_time

    observation_set
    observation_availability_boundary

    outcome_definition_version

    maturity_status
    provenance
}
```

The observation is immutable once finalized, subject to explicit source-revision/version semantics defined by the data contract.

## 12. Outcome is not label

```text
OutcomeObservation
    !=
Label
```

The outcome is the future factual observation.

A label is a derived learning target produced from the outcome using a separately versioned labeling rule.

This distinction prevents target semantics from being silently changed by model-training code.

## 13. Outcome information boundary

For an opportunity created at `t_d`, an outcome may only contain observations whose represented event times are after the decision boundary unless the outcome definition explicitly references a contemporaneous value that was already available at `t_d`.

The label must never feed backward into the opportunity definition.

## 14. Outcome horizon

The outcome horizon is represented symbolically as:

```text
H_outcome
```

with:

```text
outcome_end_time = decision_time + H_outcome
```

`H_outcome` is currently **UNRESOLVED**.

It must not be selected because a conventional horizon appears reasonable. It must be established by strategy semantics and subsequently validated.

## 15. Why the horizon cannot be guessed

Changing `H_outcome` changes:

```text
training population labels
class balance
return distribution
risk characteristics
execution-cost exposure
serial dependence
model objective
```

Therefore the horizon is a strategy-defining parameter, not a harmless implementation constant.

## 16. Label maturity

A label derived from an opportunity is not mature until the complete observation window required by its definition has elapsed and all required source observations are available.

Canonical state:

```text
PENDING
MATURE
CENSORED
INVALID
```

A `PENDING` observation must not enter the mature training population.

## 17. Censoring

If the required outcome cannot be fully observed because the data boundary, instrument lifecycle, or other authoritative condition terminates observation before maturity, the observation must be marked `CENSORED` rather than silently assigned a negative or positive label.

The exact treatment of censored observations in learning is deferred to the learning artifact.

## 18. Source revisions

If an authoritative data provider revises an outcome observation, the revised observation must receive explicit provenance/version information.

Historical labels must retain the data versions used to create them.

No silent mutation of an already promoted model's historical training record is permitted.

## 19. Economic outcome boundary

V2 distinguishes:

```text
market outcome
    !=
execution outcome
    !=
accounting outcome
```

A market outcome describes what the instrument did.

An execution outcome describes what orders/fills actually occurred.

An accounting outcome describes realized economic results after the authoritative execution and accounting rules.

This artifact does not collapse these layers.

## 20. Prediction target boundary

The eventual prediction target must be a deterministic function of:

```text
Opportunity
+
OutcomeObservation
+
LabelDefinitionVersion
```

It must not depend on:

```text
model prediction
risk authorization
selected position size
future strategy mode
future P&L
```

unless a future strategy artifact explicitly establishes a causal and versioned dependency.

## 21. Target leakage invariant

For every opportunity `o`:

```text
features(o)
```

must be constructed entirely from information available at `decision_time(o)`.

The mature label may use information after `decision_time(o)`.

The training pipeline may pair them only after label maturity.

## 22. Multiple labels

An opportunity may eventually have more than one derived target, for example:

```text
direction
magnitude
threshold-crossing
risk-adjusted outcome
```

This artifact does not authorize any specific target.

Each target must receive its own:

```text
label_id
label_definition_version
population rule
maturity rule
```

before being used for learning.

## 23. Primary target

V2 does not yet designate a primary predictive target.

Status:

```text
PRIMARY_TARGET = UNKNOWN
```

This is intentional. Selecting a target determines what the model optimizes and therefore cannot be hidden inside implementation.

## 24. Attack — look-ahead

Potential failure:

```text
future price
    -> determines opportunity existence
```

Result:

```text
FORBIDDEN
```

## 25. Attack — label leakage

Potential failure:

```text
future label
    -> feature normalization
```

Result:

```text
FORBIDDEN
```

Normalization is part of the causal feature pipeline and must be fitted only within permitted training boundaries.

## 26. Attack — selection bias

Potential failure:

```text
only generate opportunities that eventually became profitable
```

Result:

```text
FORBIDDEN
```

The opportunity population must be generated independently of its future outcome.

## 27. Attack — survivorship bias

Potential failure:

```text
construct historical opportunity universe using only instruments
that remain tradable today
```

Result:

```text
FORBIDDEN
```

Historical instrument validity must come from the time-valid instrument contract.

## 28. Attack — overlapping-label dependence

If opportunities overlap in time, their outcomes may be statistically dependent.

This does not make them invalid, but the learning artifact must account for the dependence when constructing training/validation/test populations.

No independence assumption is frozen here.

## 29. Attack — target contamination by execution

If the target is defined using actual fills, but historical model training uses fills generated by a different execution policy, the target may encode a different strategy.

Therefore execution-dependent labels require:

```text
execution-policy-version
```

in their provenance.

## 30. Attack — target drift

Changing:

```text
H_outcome
label rule
cost model
instrument universe
```

changes the target population.

Such a change requires a new label definition version and cannot silently reuse an existing trained model.

## 31. Attack — hindsight contract selection

A label must not select the historical contract that produced the best future result after observing the future.

The candidate/contract universe must be frozen by information available at the decision boundary.

## 32. Attack — premature maturity

A label whose horizon has not completed must remain:

```text
PENDING
```

It must not be used as a negative, positive, or neutral training example merely to avoid waiting.

## 33. Attack — zero-imputation of unavailable outcomes

An unavailable outcome must not become:

```text
0
```

unless zero is the explicitly defined value of that outcome state.

Missingness and zero are semantically distinct.

## 34. Attack — circular opportunity definition

Forbidden structure:

```text
Opportunity
    -> prediction
    -> predicted profitability
    -> OpportunityExists
```

The opportunity population must exist independently of the prediction result unless a future artifact explicitly establishes a causal pre-model screening stage.

## 35. Frozen semantics

This artifact freezes:

```text
Opportunity is a decision-time candidate state.
Outcome is future factual observation.
Label is derived from Outcome.
Opportunity existence precedes prediction.
Outcome cannot influence opportunity existence.
Labels require maturity.
Censoring is explicit.
Market, execution, and accounting outcomes remain distinct.
Every target is versioned.
Every outcome retains provenance.
```

## 36. Unresolved parameters

```text
H_outcome                  = UNKNOWN
PRIMARY_TARGET             = UNKNOWN
opportunity structural rule = UNKNOWN
exact outcome variables     = UNKNOWN
censoring treatment         = UNKNOWN
label construction          = DEFERRED
```

These are not implementation gaps to be filled with conventional values.

## 37. Dependencies

### A25 Strategy Charter

Status: RESOLVED for architecture.

### A22 Data & Feature Contract

Status: architectural dependency. Exact provider semantics remain external/UNKNOWN.

### Instrument contract

Status: UNKNOWN for exact V2 tradable universe and contract metadata.

### Execution contract

Status: UNKNOWN for exact venue semantics.

## 38. Completion criterion

A26 is complete as a semantic boundary only when:

```text
opportunity != prediction
outcome != label
market outcome != execution outcome
causal boundaries are explicit
maturity is explicit
censoring is explicit
future information cannot enter opportunity creation
```

The numerical target and horizon remain intentionally unresolved and must be resolved by subsequent artifacts rather than guessed here.

## ARCHITECTURE STATUS

Frozen:

```text
Opportunity as the decision-time candidate unit
OutcomeObservation as future factual state
Label as a separate derived artifact
Causal opportunity population
Maturity state machine
Censoring state
Target versioning
Outcome provenance
Market/execution/accounting separation
```

## UNRESOLVED

```text
exact opportunity structural conditions
exact outcome variables
prediction horizon
primary target
label transformation
censoring treatment for learning
```

## BLOCKERS

No blocker to the semantic separation defined by A26.

The unresolved target parameters block predictive-model specification and implementation of a predictive label, but do not invalidate the artifact.

## NEXT ARTIFACT

**A27 — Canonical Feature Set and Feature Semantics**

A27 must define the information available at `decision_time`, every feature's mathematical semantics, dependencies, units, windows, missing/stale behavior, and causal availability. No feature may be added merely because it is common in trading.
