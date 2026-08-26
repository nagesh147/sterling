# A130 — Canonical Feature and State Snapshot Contract

**Status:** Canonical implementation source of truth  
**Depends on:** A126, A127, A128, A129  
**Purpose:** Define the immutable, causally reproducible feature/state snapshot presented to downstream decision consumers.

## 1. Purpose

A130 defines exactly what evidence and derived state a consumer may observe at decision time `t`.

It prevents mutable-state contamination, hidden dependencies, future-information leakage, inconsistent feature recomputation, and irreproducible historical decisions.

The canonical flow is:

```text
canonical events
    -> feature computation
    -> state derivation
    -> immutable snapshot
    -> consumer
    -> decision
```

A130 owns snapshot composition and provenance. It does not own trading logic, feature mathematics, lifecycle transitions, execution semantics, or learned-model training.

## 2. Canonical terms

### 2.1 Snapshot time

`decision_time` is the causal boundary at which a consumer evaluates the snapshot.

### 2.2 Availability

Every dependency has `available_at`: the earliest time at which that dependency is legitimately observable to the system.

For every consumed dependency `d`:

```text
available_at(d) <= decision_time
```

is mandatory.

### 2.3 Snapshot identity

Each snapshot has:

```text
snapshot_id
instrument_id
observation_time
decision_time
snapshot_version
feature_schema_version
state_schema_version
formula_registry_version
configuration_version
source_event_ids
created_at
```

`created_at` is provenance only and cannot substitute for `decision_time` or `available_at`.

## 3. Feature value contract

Every feature value is represented by:

```text
feature_id
value
value_type
observation_time
available_at
formula_id
formula_version
dependency_ids
source_event_ids
quality_status
missing_reason?
```

A bare scalar without provenance is not a canonical feature value.

## 4. State snapshot contract

State is represented separately from feature evidence.

Canonical state domains are:

```text
MARKET_STATE
STRATEGY_STATE
POSITION_STATE
EXECUTION_STATE
RISK_STATE
DATA_STATE
```

State variables remain owned by their defining contracts. A130 only composes their causally valid values into the snapshot.

A snapshot cannot authorize an order, change a thesis, mutate a position, or modify lifecycle state.

## 5. Dependency graph

Feature dependencies form a directed acyclic graph.

```text
raw event -> feature -> derived feature -> consumer
```

Circular dependencies are invalid. Every node must identify its direct dependencies and provenance.

## 6. Quality and missingness

Canonical quality states:

```text
VALID
DEGRADED
MISSING
INVALID
STALE
CAUSALLY_UNAVAILABLE
```

Missingness retains cause. Canonical reasons include:

```text
NOT_YET_AVAILABLE
SOURCE_MISSING
SOURCE_INVALID
INSUFFICIENT_HISTORY
CONTRACT_NOT_APPLICABLE
CALCULATION_FAILED
STALE_SOURCE
CAUSALITY_VIOLATION
```

Missing values must not silently become zero, previous value, mean, or interpolation. Such transformations require an explicit downstream feature contract.

## 7. Formula authority

The canonical formula authority is the **versioned Adaptive Edge formula registry** under repository-controlled canonical strategy documentation.

Each formula has a stable `formula_id` and immutable `formula_version`. A formula version is identified by its canonical specification content/version and may not be silently changed in place.

Runtime implementations are consumers of the registry; they do not redefine formula semantics.

A formula used without a registered version is invalid.

## 8. Configuration authority

The canonical configuration authority is the **versioned Adaptive Edge configuration manifest** associated with the strategy/research run.

Configuration is immutable for a given run/version and includes only explicitly declared configurable parameters. A historical replay must resolve the configuration version recorded by the snapshot; it may not read current configuration implicitly.

Configuration does not become business logic merely because it is configurable.

## 9. Learned-model authority

A130 does not define model training. When a learned model is consumed, the canonical authority is the **versioned model artifact plus its model manifest**.

The manifest must identify:

```text
model_id
model_version
training_dataset_version
training_boundary
validation_boundary
test_boundary
feature_schema_version
label_schema_version
promotion_status
```

A model output without a resolvable model version is not eligible for a production decision.

## 10. Persistence and serialization authority

The canonical semantic object is the immutable snapshot contract, not a particular database or serialization technology.

The persistence boundary is frozen as:

```text
canonical snapshot
    -> versioned durable representation
    -> deterministic reconstruction
```

The physical storage engine and wire format remain implementation choices, provided they preserve every canonical field, version, timestamp, dependency identifier, and provenance relationship.

Therefore persistence/serialization is **not an architectural unknown**. The implementation must conform to the semantic contract and must define a deterministic, lossless encoding before production.

## 11. Determinism

Given identical:

```text
canonical events
instrument/contract versions
formula versions
configuration version
model versions
state-transition versions
```

the snapshot must be reproducible.

If a dependency is nondeterministic, it must be explicitly represented and versioned; hidden ambient state is forbidden.

## 12. No ambient-state reads

Snapshot computation must not implicitly read:

```text
current clock
latest configuration
latest model
current instrument master
current position
latest database row
```

unless that value is explicitly part of the causal input set for `decision_time`.

## 13. Consumer isolation

A snapshot is evidence, not authorization.

Consumers may derive decisions from it, but cannot mutate it.

Separate consumer views may be constructed from the same canonical snapshot lineage, but independently recomputing the same feature under different semantics is forbidden.

## 14. State reconstruction

For decision time `t`:

```text
State(t) = Fold(events where available_at <= t)
```

Historical state must be reconstructed from causally valid events, not from today's mutable position/state tables.

## 15. Snapshot completeness

A snapshot is complete for consumer `C` iff every dependency declared mandatory by `C` is present and satisfies its quality and causal contract.

There is no universal percentage-complete threshold.

If a required dependency is unavailable or invalid, the consumer must fail closed or enter an explicitly defined degraded state.

## 16. Version compatibility

The following versions are part of snapshot identity:

```text
feature_schema_version
state_schema_version
formula_registry_version
configuration_version
model_version(s), when applicable
```

Incompatible versions cannot be silently mixed.

## 17. Temporal invariants

For every snapshot at `t`:

```text
available_at(feature) <= t
available_at(state_dependency) <= t
available_at(model) <= t
available_at(configuration) <= t
```

No future observation may enter an earlier snapshot because it exists in a historical database today.

## 18. Lineage

Canonical lineage is:

```text
raw data
 -> canonical event
 -> feature dependency
 -> feature value
 -> state derivation
 -> snapshot
 -> decision
```

The snapshot records the identifiers required to traverse this lineage.

## 19. Learned quantities

A130 learns no trading parameter.

If a learned model contributes a feature, the model's own learning contract must specify:

```text
historical population
label definition
observation horizon
label maturity
training boundary
validation boundary
test boundary
update frequency
promotion rule
```

A130 only records which approved model version produced the value.

## 20. Failure conditions

Snapshot creation must fail or explicitly degrade for:

```text
future dependency
missing required dependency
invalid dependency
unknown formula version
unknown configuration version
unknown model version
incompatible schema version
circular feature dependency
ambiguous state authority
non-deterministic hidden dependency
causal timestamp violation
lossy serialization of required lineage
```

No fallback may conceal one of these failures.

## 21. Hostile review

The design must survive:

```text
late market event
provider correction
future database row
current configuration applied historically
current model applied historically
mutable position table used in replay
feature recomputed with changed formula
circular dependency
missing bid/ask-derived feature
partial source failure
duplicate event
schema migration
serialization round-trip
replay from persisted snapshot
```

Expected behavior is rejection, explicit degradation, or creation of a new versioned snapshot—not mutation of historical evidence.

## 22. Frozen architecture

```text
immutable snapshot semantics
causal availability boundary
feature/state separation
feature provenance
state provenance
DAG dependency requirement
quality semantics
missingness semantics
formula versioning
configuration versioning
model versioning
consumer isolation
no ambient-state reads
deterministic replay requirement
lossless semantic persistence requirement
version compatibility
explicit failure states
```

## 23. Learned / configurable parameters

A130 introduces no learned numerical trading parameters.

Consumer-specific quality acceptance, retention duration, physical encoding, and storage partitioning are implementation/configuration concerns and must be versioned. They cannot change the semantic meaning of an existing snapshot.

## 24. Resolved dependency decisions

The following are no longer unresolved:

| Dependency | Canonical authority | Status |
|---|---|---|
| Formula semantics | Versioned Adaptive Edge formula registry | RESOLVED |
| Runtime formula implementation | Must conform to registered formula/version | RESOLVED |
| Configuration | Versioned Adaptive Edge configuration manifest | RESOLVED |
| Learned model identity | Versioned model artifact + model manifest | RESOLVED |
| Snapshot persistence semantics | Immutable, lossless, versioned representation | RESOLVED |
| Physical database/wire format | Implementation choice under semantic contract | NOT AN ARCHITECTURAL DEPENDENCY |
| Feature quality acceptance | Consumer contract, versioned configuration | RESOLVED |
| Retention | Operational policy, versioned configuration | RESOLVED |

No specific database, serialization library, ML registry vendor, or deployment technology is invented here.

## 25. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- immutable snapshot contract
- causal availability
- feature/state separation
- provenance and lineage
- formula/version authority
- configuration/version authority
- model/version authority
- persistence semantic contract
- deterministic reconstruction
- consumer isolation
- quality and missingness semantics
- version compatibility
- fail-closed behavior for unresolved required dependencies

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that block the architecture.

IMPLEMENTATION VALIDATION:
- select concrete persistence technology
- select concrete serialization format
- validate round-trip fidelity
- validate registry loading and version resolution
- validate operational retention policy

These are implementation validation tasks, not architectural blockers.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A131 — Canonical Feature Mathematics and Dependency Contract
```
