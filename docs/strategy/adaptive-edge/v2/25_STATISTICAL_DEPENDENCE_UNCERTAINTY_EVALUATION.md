# Adaptive Edge V2 — Statistical Dependence / Uncertainty Evaluation Contract

**Artifact:** A49  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK — dependence representation and uncertainty-method compatibility implemented; estimator selection remains blocked

## 1. Purpose

A49 defines the boundary between observed evaluation evidence and statistical uncertainty claims.

A49 does not select a confidence level, estimator, bootstrap method, p-value threshold, multiple-testing correction, or promotion threshold.

## 2. Governing principle

Adaptive Edge must not apply IID statistical inference merely because observations are represented as rows.

```text
observations
    -> dependence structure
    -> justified uncertainty method
    -> uncertainty result
```

The dependence structure must be recorded before an uncertainty method is accepted.

## 3. Dependence units

A49 represents dependence at the economic-episode level rather than assuming every observation is independent.

Each unit records:

```text
unit_id
cycle_id
episode_id
start_time
end_time
dependence_class
```

The available classes are:

```text
IID_JUSTIFIED
OVERLAPPING
SERIAL
CLUSTERED
UNKNOWN
```

These are representation classes, not claims that any particular class applies to Adaptive Edge data.

## 4. Overlapping outcomes

A39 explicitly requires distinguishing observation count from independent economic episodes.

A49 therefore preserves both populations and refuses to infer independence from observation count alone.

## 5. IID restriction

IID inference is permitted only when every represented dependence unit is explicitly classified `IID_JUSTIFIED` and the uncertainty specification states the corresponding assumption.

Unknown or mixed dependence must not be silently downgraded to IID.

## 6. Temporal dependence

Serial dependence may arise from repeated decisions, market-state persistence, overlapping labels, or other unresolved strategy-specific mechanisms.

A49 records such dependence but does not select an estimator for it.

## 7. Cluster dependence

Clustered dependence may arise when multiple observations belong to a common economic episode, instrument, session, regime, or other grouping.

The grouping definition must come from the canonical strategy/evaluation specification. A49 does not invent one.

## 8. Uncertainty specification

An uncertainty specification must identify:

```text
method_id
dependence_assumption
justification
version
```

The method is accepted only when its declared dependence assumption matches the observed dependence classes.

## 9. Multiple testing

A49 does not solve multiple-testing correction.

A39 requires preservation of the candidate population and research history. Any future multiple-testing procedure must consume that evidence rather than treating the final selected candidate as if it were pre-specified.

## 10. Walk-forward aggregation

A48 preserves cycle-level evidence before aggregation.

A49 must consume that evidence without collapsing cycles into IID observations merely because a single aggregate metric is convenient.

## 11. Confidence intervals / uncertainty estimators

No particular estimator is canonical yet.

The following remain unresolved:

```text
confidence level
IID estimator applicability
block bootstrap design
cluster bootstrap design
serial-correlation adjustment
effective sample-size definition
multiple-testing correction
```

A49 therefore exposes compatibility checks but does not manufacture a numerical uncertainty result.

## 12. Reproducibility

An eventual uncertainty result must be reproducible from:

```text
A48 evidence fingerprint
dependence-unit definitions
uncertainty-method version
method parameters
code version
```

## 13. Invalid inference patterns

The following are prohibited unless explicitly justified by the resolved dependence model:

```text
row count == independent sample size
IID standard error on overlapping outcomes
IID confidence interval on serially dependent results
ignoring cycle boundaries
ignoring clustered episodes
selecting an uncertainty method after observing its favorable result
```

## 14. Completion criterion

A49 becomes RESOLVED when the canonical strategy specification supplies enough information to select and freeze an uncertainty methodology that matches:

```text
target definition
outcome horizon
dependence structure
walk-forward cycle structure
candidate-selection process
multiple-testing history
```

Until then, A49 remains a framework rather than a numerical inference engine.

## ARCHITECTURE STATUS

**FROZEN:** dependence must be represented explicitly; IID cannot be assumed; uncertainty-method compatibility must be checked; A48 cycle evidence must remain auditable.

**IMPLEMENTED:** dependence units; dependence classes; IID guard; uncertainty specification compatibility; deterministic evidence linkage.

**UNRESOLVED:** estimator; confidence level; bootstrap/block structure; effective sample size; multiple-testing correction; exact dependence taxonomy for the strategy.

**BLOCKERS:** A26 target/horizon and unresolved strategy/evaluation semantics.

**NEXT ARTIFACT:** A50 — Research Selection / Multiple-Testing and Candidate-Discovery Registry Contract.
