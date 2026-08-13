# A173 — Canonical Feature Snapshot, Provenance & Point-in-Time Computation Contract

**Status:** CANONICAL  
**Authority:** Canonical definition of point-in-time feature computation and feature lineage  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A172

## 1. Purpose

A173 defines how canonical market/state evidence becomes a feature snapshot that is reproducible, causally valid, versioned, and traceable to the exact observations available at decision time.

A feature is not merely a numeric value. It is a value plus its provenance, availability boundary, formula version, inputs, quality, and computation context.

## 2. Canonical feature identity

Minimum fields:

```text
feature_snapshot_id
feature_id
feature_version
snapshot_id
decision_time
causal_cutoff
instrument_identity
horizon_context
value
unit
quality_state
formula_version
configuration_version
input_reference_set
created_at
```

## 3. Point-in-time rule

For every feature `f` computed for decision time `t`:

```text
∀ input i ∈ Inputs(f,t):
    available_at(i) <= t
```

Any violation is a conformance failure.

## 4. Feature formula authority

Every canonical feature must reference exactly one formula authority:

```text
feature_id
    -> formula_registry_entry
    -> formula_version
```

A feature implementation cannot silently change mathematical semantics without a new version.

## 5. Input provenance

Every material input must be traceable to:

```text
raw/provider evidence
    -> canonical event
    -> temporal state/snapshot
    -> feature input
```

Derived features must preserve dependency lineage.

## 6. No hidden inputs

A feature implementation must not consume undeclared global state, current wall-clock state, future cache contents, current model state, or mutable configuration that is absent from the feature provenance record.

## 7. Snapshot binding

A feature snapshot is bound to one causal market snapshot and one applicable state/version set.

Changing the source snapshot changes the feature snapshot identity.

## 8. Feature quality

Canonical quality states include:

```text
VALID
MISSING_INPUT
STALE_INPUT
INVALID_INPUT
OUT_OF_DOMAIN
UNAVAILABLE
UNKNOWN
```

A feature with material invalid provenance cannot be silently represented as a valid numeric value.

## 9. Missing-value semantics

Missingness must remain explicit unless a formula's canonical definition specifies a deterministic missing-value transformation.

```text
missing
!=
zero
!=
neutral
```

## 10. Units

Every numerical feature must have explicit unit semantics where meaningful.

Unit conversion is part of the canonical formula/input contract and cannot be implicit.

## 11. Normalization

Normalization is a separate semantic operation from raw feature calculation.

A normalized feature must preserve:

```text
raw_feature_version
normalization_method_version
reference_population/version
fit boundary
```

No future observations may influence historical normalization parameters.

## 12. Learned normalization

If normalization parameters are learned, their lineage must include:

```text
population
training boundary
label-independent eligibility
fit timestamp/version
promotion status
```

Parameters fit using future observations are prohibited from historical decision computation.

## 13. Rolling calculations

For a rolling feature with window `W`, the eligible input set must be defined explicitly.

The implementation must not accidentally include:

```text
current incomplete future bar
post-decision revisions
later-arriving observations unavailable at t
```

unless the feature definition explicitly permits them.

## 14. Multi-timeframe features

A higher-timeframe feature may consume only a completed higher-timeframe observation that was causally available at decision time, unless the feature contract explicitly defines intrabar construction from available lower-timeframe events.

The phrase "same timestamp" is insufficient to establish causal availability.

## 15. Cross-instrument features

For cross-instrument features, every dependency must carry its own:

```text
instrument identity
availability boundary
quality state
```

A missing secondary instrument must not silently become a zero contribution.

## 16. Option features

Option-derived features must reference canonical option contract identity and preserve:

```text
underlying
expiry
strike
option_type
quote timestamp
contract status
```

Provider symbols alone are insufficient.

## 17. Feature snapshot immutability

Once a feature snapshot has been used for a consequential decision, its semantic content is immutable.

A correction produces a new feature version/snapshot rather than rewriting historical decision evidence.

## 18. Feature cache semantics

A cache is an optimization, not an authority.

Cache contents must be reproducible from canonical inputs and versions.

A cache hit must not bypass causal validation.

## 19. Computation determinism

Given identical:

```text
input references
formula version
configuration version
snapshot
software implementation version
```

the feature computation must be deterministic, subject only to explicitly declared numerical tolerance.

## 20. Numerical precision

Precision and rounding rules must be explicit where they affect downstream economics, risk, or classification.

Rounding must not silently alter raw evidence.

## 21. Feature dependencies

The feature dependency graph must be acyclic within a decision snapshot.

```text
raw evidence
    -> base feature
    -> derived feature
    -> normalized feature
```

A feature cannot directly or indirectly depend on itself.

## 22. Circular dependency attack

If:

```text
F1 -> F2
F2 -> F1
```

computation must fail closed.

No iterative resolution is permitted unless explicitly specified as part of the mathematical contract.

## 23. Feature selection

Feature selection must be versioned.

A model receiving feature set V3 must not silently receive V4 features merely because they exist in the runtime.

## 24. Feature availability

A feature can be:

```text
AVAILABLE
UNAVAILABLE
STALE
INVALID
UNKNOWN
```

Availability is distinct from the numerical value.

## 25. Feature lineage

The canonical lineage must support:

```text
feature
 -> formula
 -> configuration
 -> snapshot
 -> canonical events
 -> provider evidence
```

A reviewer must be able to reconstruct why the value existed at decision time.

## 26. Research/live separation

Research-generated features must not be treated as live features unless their provenance contract is equivalent and the implementation/version is explicitly authorized.

## 27. Dataset boundary

A feature snapshot becomes a training example only after label maturity and dataset eligibility rules are satisfied under A158/A159.

Feature computation itself must not inspect future labels.

## 28. Formula registry

The final formula registry implementation/version authority remains a dependency identified by prior artifacts. Until implemented, canonical feature records must still carry a stable formula identifier/version rather than embedding an unversioned expression.

## 29. Configuration registry

Feature-affecting configuration must be versioned and referenced by the snapshot. Mutable runtime configuration cannot retroactively change a historical feature.

## 30. Hostile scenarios

The implementation must test:

```text
future input
late input
missing input
stale input
duplicate input
revised input
wrong instrument
wrong option expiry
wrong timeframe boundary
incomplete bar
future normalization population
feature-version mismatch
formula-version mismatch
configuration mutation
cache poisoning
circular dependency
numerical overflow
invalid domain
```

## 31. Causal attack examples

### Future input

```text
feature_time = 10:01:00
input.available_at = 10:01:01
```

Feature computation must fail or mark unavailable.

### Later correction

An observation corrected at 10:05 cannot modify a feature snapshot already used at 10:01.

### Future normalization

A z-score parameter fit using observations after the decision boundary cannot be consumed by the historical feature.

## 32. Invariants

```text
INV-173-001  Every material feature input is provenance-linked.
INV-173-002  Every material input is causally available at feature time.
INV-173-003  Every canonical feature references a formula version.
INV-173-004  Feature quality is explicit.
INV-173-005  Missing is not silently converted to zero.
INV-173-006  Units are explicit where meaningful.
INV-173-007  Learned normalization cannot use future observations.
INV-173-008  Higher-timeframe features respect completion/availability semantics.
INV-173-009  Cross-instrument dependencies preserve identity and availability.
INV-173-010  Feature snapshots used by decisions are immutable.
INV-173-011  Caches cannot bypass causal validation.
INV-173-012  Feature dependency graphs cannot contain undeclared cycles.
INV-173-013  Feature-set versions are explicit.
INV-173-014  Historical corrections cannot rewrite completed decisions.
INV-173-015  Feature computation is reproducible from recorded provenance.
INV-173-016  Feature computation never consumes future labels.

## 33. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- point-in-time computation
- feature provenance
- formula/version binding
- input availability rule
- quality/missing semantics
- unit semantics
- normalization separation
- learned-normalization boundary
- multi-timeframe causal semantics
- cross-instrument provenance
- option-contract provenance
- snapshot immutability
- cache non-authority
- deterministic computation
- dependency acyclicity
- feature-set versioning
- research/live separation

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- final formula registry implementation
- final configuration registry implementation
- exact feature persistence technology
- exact numerical precision policy per feature family
- empirical provider field semantics required by individual features

CONFIGURATION TO VALIDATE:
- feature freshness thresholds
- normalization windows/populations
- numerical tolerances
- cache retention
- feature computation performance targets

LEARNED / VALIDATION-DEPENDENT:
- normalization parameters
- empirical feature acceptance thresholds
- learned feature transforms

BLOCKERS:
None for specification.
Feature production remains blocked for any feature whose required input semantics/provider evidence are unverified.

NEXT ARTIFACT:
A174 — Canonical Probability, Calibration & Predictive-State Contract
```