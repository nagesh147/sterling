# A191 — FeatureSnapshot, Provenance & Quality-State Conformance Contract

## Status
CANONICAL IMPLEMENTATION CONTRACT

## Purpose
A191 closes the first concrete implementation-conformance gap identified by A190. It defines the runtime representation required for a causally valid, auditable feature snapshot without inventing strategy-specific feature mathematics.

## Canonical object
A consequential FeatureSnapshot must contain immutable:
```text
snapshot_id
strategy_version
feature_set_version
decision_time
observation_cutoff_time
feature_values
feature_statuses
source_event_references
instrument_context
provenance
```

## Feature status
Every feature value has exactly one canonical status:
```text
VALID
MISSING
STALE
INVALID
NOT_APPLICABLE
```
A status is semantic state, not a numeric sentinel.

## Value rule
A numeric feature value may exist only when permitted by its feature contract. Missing, stale, or invalid values must not silently become zero.

## Provenance
Every consequential feature must be traceable:
```text
source event(s)
 -> canonical event/state
 -> feature formula/version
 -> feature value/status
 -> FeatureSnapshot
```
A provider field name alone is not provenance.

## Causal boundary
For every feature dependency:
```text
available_at <= decision_time
```
For derived features this applies recursively to every source dependency. `observation_time` and `available_at` remain distinct.

## Snapshot immutability
After a snapshot is used by a decision, its identity and semantic content cannot be mutated. Corrections require a new versioned snapshot.

## Versioning
`feature_set_version` identifies feature membership and ordering. Individual feature versions identify formula and semantic definitions. Strategy version identifies the consuming strategy contract.

## Instrument context
Instrument context must resolve to the canonical instrument identity. Ambiguous identity is rejected.

## Quality propagation
Materially degraded source dependencies propagate an appropriate degraded status unless the feature definition explicitly proves the dependency irrelevant.

## Consumer acceptance
Feature status does not authorize a trade. Downstream consumers define accepted statuses. Execution-critical consumers fail closed when required inputs are unavailable, stale beyond policy, or invalid.

## Serialization
Serialization must preserve semantic fields, timestamps, status, and provenance. Exact persistence technology remains implementation-dependent.

## Compatibility
A snapshot is consumable only when strategy version, feature-set version, feature versions, instrument identity, and schema are supported by the consumer.

## Invariants
```text
INV-191-001 every consequential snapshot has immutable identity
INV-191-002 every consequential feature has explicit status
INV-191-003 missing is never silently encoded as zero
INV-191-004 stale is never silently treated as current
INV-191-005 invalid data is never silently repaired in the snapshot layer
INV-191-006 every consequential feature has provenance
INV-191-007 future availability cannot enter an earlier decision snapshot
INV-191-008 snapshot mutation after decision use is forbidden
INV-191-009 unsupported versions are rejected
INV-191-010 ambiguous instrument identity is rejected
```

## Adversarial tests
```text
future availability
missing value represented as zero
stale value represented as current
invalid quote represented as valid
provider field substituted without mapping
source event removed after snapshot creation
feature formula version mismatch
feature-set membership mismatch
instrument identity collision
snapshot mutation after decision
serialization dropping provenance
serialization changing timestamp precision
```

## Parameter classes
### Frozen
Snapshot identity, status semantics, provenance requirement, causal availability rule, immutability, version compatibility.

### Configuration
Consumer-specific accepted statuses, serialization format, retention policy.

### Learned
None.

## Status
```text
ARCHITECTURE STATUS: COMPLETE
IMPLEMENTATION CONTRACT: COMPLETE
UNRESOLVED: exact persistence/serialization technology
BLOCKERS: none for contract implementation
NEXT ARTIFACT: A192 — Feature Engine Conformance Implementation and Invariant Test Contract
```
