# Adaptive Edge V2 — Feature Availability, Snapshot and Feature-Lineage Contract

**Artifact:** A40  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A40 defines the causal contract for constructing, timestamping, versioning, storing, and consuming features.

The central question is:

```text
Could the exact feature value used by a historical decision
actually have been known at that decision timestamp?
```

A40 does not define specific trading features.

## 2. Canonical causal chain

```text
Raw Observation
    |
    v
Canonical Event
    |
    v
Feature Transformation
    |
    v
Feature Snapshot
    |
    v
Prediction
    |
    v
Decision
```

Every transition must preserve provenance and causal timestamps.

## 3. Feature identity

Every feature must have a stable identity:

```text
feature_id
feature_definition_version
transformation_version
source_dataset_version
unit
semantic_definition
```

Changing the meaning of a feature requires a new version.

## 4. Observation timestamp versus availability timestamp

These are distinct:

```text
observation_time
availability_time
```

`observation_time` describes when the underlying phenomenon occurred.

`availability_time` describes when the system could legitimately know the value.

The causal constraint is:

```text
availability_time <= decision_time
```

not merely:

```text
observation_time <= decision_time
```

## 5. Example of availability leakage

A daily value may represent information observed during a prior period but published only later.

Using its period-end timestamp alone could create look-ahead bias.

The feature contract therefore requires publication/availability semantics wherever relevant.

## 6. Snapshot identity

A prediction must reference an immutable feature snapshot:

```text
FeatureSnapshot {
    snapshot_id
    decision_time
    feature_schema_version
    feature_values
    source_versions
    transformation_versions
    availability_watermark
    quality_state
}
```

The exact storage technology is not prescribed.

## 7. Snapshot immutability

Once a snapshot has been used for a decision, its historical value cannot be silently changed.

Corrections create a new version/correction lineage.

Historical replay must be able to recover the exact prior snapshot.

## 8. Feature calculation time

Feature calculation may occur after raw observation arrival.

Therefore the system should distinguish:

```text
observation_time
availability_time
calculation_time
snapshot_time
decision_time
```

These timestamps must not be collapsed without justification.

## 9. Watermark

A feature pipeline may require a causal watermark indicating the latest source state that is safely available.

The exact watermark mechanism is implementation-specific.

A snapshot must not incorporate data beyond its causal availability boundary.

## 10. Multi-source features

A feature derived from multiple sources is available only when every required dependency is causally available.

Conceptually:

```text
FeatureAvailability
    = max(dependency availability times)
```

This is a structural relationship; exact source timestamps must be supplied by the data contracts.

## 11. Missing dependency

If a required dependency is unavailable or invalid at decision time, the feature must not be synthesized from future information.

The feature state must explicitly represent:

```text
AVAILABLE
MISSING
STALE
INVALID
AMBIGUOUS
```

## 12. Staleness

A feature may be historically available but too old for its intended semantics.

A staleness rule requires:

```text
reference time
maximum tolerated age
unit
source
failure behavior
```

No maximum age is selected here.

## 13. Feature freshness versus feature validity

Freshness and validity are distinct:

```text
fresh != necessarily valid
valid != necessarily fresh
```

Both may affect feature usability.

## 14. Missingness semantics

Missingness must not automatically mean zero, false, neutral, or negative.

If a model requires an imputation rule, that rule must be explicitly defined and trained within the causal evaluation boundary.

## 15. Imputation leakage

Imputation statistics must not be learned from future validation/test data.

For example, a full-history mean used to fill earlier missing observations is invalid for causal evaluation.

## 16. Normalization/scaling

Scaling parameters are learned quantities.

They must be fit only on the permitted training population for each walk-forward cycle.

A full-history scaler is forbidden for causal backtesting.

## 17. Rolling features

A rolling feature at time `t` may consume only observations whose availability time is <= `t`.

The window definition must specify:

```text
lookback boundary
inclusion/exclusion rule
sampling frequency
missing-data treatment
```

No future observation may enter the window.

## 18. Bar-close features

If a feature uses a bar's close, high, low, or volume, the feature cannot be considered available until the bar itself is complete and its value is available under the source contract.

Using the completed bar while simulating an intra-bar decision is forbidden unless the source explicitly provides the value at that intra-bar time.

## 19. Intrabar ambiguity

Historical OHLC bars do not necessarily reveal the ordering of intra-bar events.

A feature or trigger requiring event ordering cannot infer that ordering from the final bar alone.

The data must support the required temporal resolution or the state is ambiguous.

## 20. Revisions and corrections

If a source revises historical data, the system must distinguish:

```text
originally available value
later corrected value
```

A historical replay must use the value that was actually available at the simulated decision time when evaluating historical causal behavior, unless the evaluation explicitly targets revised-data reconstruction.

The chosen dataset version must therefore be explicit.

## 21. Corporate/instrument events

Features involving instrument metadata, contract lifecycle, corporate actions, or symbol mappings require historically valid versions.

Current metadata must not overwrite historical semantics.

## 22. Cross-sectional features

A cross-sectional feature is available only if every constituent observation used by its calculation was available at the decision boundary.

Future constituents or future membership information are forbidden.

## 23. Universe membership

If a feature uses a universe, the universe itself is a time-varying dependency:

```text
Universe(t)
```

Current universe membership cannot be applied to historical decisions without a historical-membership source.

## 24. Feature selection

Feature selection is a research operation and must be versioned.

A feature selected using future validation/test performance cannot be treated as though it was known at an earlier training cutoff.

## 25. Feature lineage

Every feature value must be traceable:

```text
feature value
 -> transformation version
 -> source canonical events
 -> source dataset version
 -> source availability timestamps
```

A feature without lineage is not production-auditable.

## 26. Feature provenance record

A canonical provenance record should contain:

```text
feature_id
feature_version
snapshot_id
decision_time
source_event_ids
source_dataset_versions
transformation_version
availability_watermark
quality_state
```

## 27. Feature reproducibility

Given identical source versions, transformation version, snapshot timestamp, and configuration, the feature snapshot must be reproducible.

## 28. Feature dependency graph

Feature dependencies must be acyclic at a given evaluation time.

Circular feature definitions are invalid unless the dependency is explicitly modeled as a prior-state transition rather than a same-time dependency.

## 29. Recursive/adaptive features

If a feature uses a previous model prediction, policy state, or learned parameter, that dependency must be explicit:

```text
Feature_t
    <- State_{t-1}
```

It must not consume the current decision's future outcome.

## 30. Model-state contamination

An adaptive model's state is itself a temporal dependency.

Historical replay must reconstruct the model state available at each decision time rather than using the final model state.

## 31. Feature cache attack

A cached feature generated later from revised or future data must not silently replace the original historical snapshot.

Cache identity must include the relevant source/version/provenance information.

## 32. Feature availability attack

Invalid:

```text
observation timestamp <= decision time
therefore feature available
```

Correct:

```text
availability timestamp <= decision time
```

with source semantics supporting that availability claim.

## 33. Future-bar attack

Invalid:

```text
decision at 10:15
feature uses 10:15-10:30 completed bar
```

unless the feature source genuinely makes that completed-bar information available at 10:15, which is normally impossible.

## 34. Data revision attack

Invalid:

```text
2026 replay
uses a historical value corrected in 2028
as though it were known in 2026
```

unless the evaluation explicitly models revised data rather than real-time causal knowledge.

## 35. Implementation gate

A40 cannot define actual feature implementations until each feature has:

```text
semantic definition
source
availability semantics
unit
transformation
version
missingness policy
staleness policy where applicable
```

Features without these definitions are BLOCKED.

## 36. Parameter classes

### Frozen architecture

```text
availability boundary
snapshot identity
feature versioning
lineage
immutability
watermark concept
missingness states
source-version tracking
causal rolling-window rule
model-state temporal reconstruction
```

### Learned/configurable

```text
lookback lengths
imputation parameters
normalization parameters
staleness thresholds
feature-selection parameters
```

only after proper validation.

### External UNKNOWN

```text
source publication latency
historical revision behavior
source completeness
historical universe membership
TrueData field semantics
```

## 36. Implementation status

The feature-lineage framework can be implemented without choosing any feature formula.

Actual feature implementations are blocked until their source definitions are exact.

## 37. Completion criterion

A40 becomes `RESOLVED` when, for every feature consumed by a decision, the system can demonstrate:

```text
what the feature means
where it came from
when its source became available
which transformation created it
which version was used
what value was consumed
why that value was causally available
```

and reproduce the same snapshot from the declared source versions.

## ARCHITECTURE STATUS

**FROZEN:** availability-time causality; immutable feature snapshots; feature versioning; provenance; source-version tracking; missingness/validity states; causal rolling windows; adaptive model-state reconstruction; revision awareness.

**UNRESOLVED:** actual feature definitions; source publication latency; staleness thresholds; imputation/scaling parameters; historical universe membership; TrueData semantics.

**BLOCKERS:** Any feature lacking an exact semantic/source/availability definition is blocked from implementation. This does not block the feature-lineage architecture.

**NEXT ARTIFACT:** A41 — Prediction / Probability Calibration and Decision-Input Contract.
