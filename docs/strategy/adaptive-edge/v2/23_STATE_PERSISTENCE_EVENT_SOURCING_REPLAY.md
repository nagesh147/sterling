# Adaptive Edge V2 — State Persistence, Event Sourcing and Replay Contract

**Artifact:** A47  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A47 defines how Adaptive Edge persists immutable events and reconstructs decision, strategy, authorization, execution, position, accounting, and learning state deterministically.

The primary requirement is:

```text
historical state must be reconstructible
without silently substituting current mutable state
```

A47 does not prescribe a particular database, event broker, or storage engine.

## 2. Canonical event model

A canonical event contains at minimum:

```text
event_id
event_type
aggregate_id
aggregate_type
event_time
availability_time
recorded_time
schema_version
producer
producer_version
payload
causation_id
correlation_id
provenance
```

Exact persistence technology is implementation-specific.

## 3. Immutable events

Source events are append-only.

Corrections, reversals, supersessions, and reinterpretations must create new events rather than silently rewriting the historical event.

This preserves auditability and replayability.

## 4. Event identity

Every event must have a stable identity.

Reprocessing the same source event must not create a second economic effect.

Idempotency is therefore an event-store requirement as well as an execution requirement.

## 5. Aggregate state

Derived state may be reconstructed from an ordered event stream:

```text
Event_1
 -> State_1
Event_2
 -> State_2
...
Event_n
 -> State_n
```

A state snapshot may accelerate reconstruction but must not become the sole historical source of truth unless its provenance and replay contract are equivalent to the underlying event history.

## 6. Event ordering

Events must be ordered according to authoritative event time and deterministic tie-breaking rules.

Receipt order cannot automatically replace event order.

Where the provider supplies sequence numbers, those semantics must be retained.

## 7. Causation and correlation

Events should preserve:

```text
causation_id
correlation_id
```

so the system can answer:

```text
What caused this event?
Which decision/execution workflow did it belong to?
```

## 8. Decision lineage

A decision must remain traceable to:

```text
market observations
feature snapshot
model/policy version
prediction
economic assessment
eligibility
risk authorization
sizing
order intent
```

A mutable current-state lookup cannot replace this lineage.

## 9. Execution lineage

Execution must remain traceable through:

```text
OrderIntent
 -> SubmissionAttempt
 -> ProviderOrder
 -> ProviderStatus
 -> FillEvent
 -> PositionEffect
 -> AccountingEffect
```

An execution record without provider/source provenance is incomplete.

## 10. Learning lineage

A training row must remain traceable through:

```text
source event
 -> decision
 -> feature snapshot
 -> outcome
 -> maturity
 -> label
 -> training dataset
 -> candidate model/policy
 -> promotion
```

This is required to prove absence of future leakage.

## 11. Snapshotting

Snapshots may be used to reduce replay cost.

A snapshot must identify:

```text
snapshot_id
aggregate_id
snapshot_time
source_event_position
state_schema_version
state_hash/provenance where supported
```

A snapshot must never be interpreted as having existed before its snapshot time.

## 12. Replay boundary

Replay must specify:

```text
start_time
end_time
event-source version
policy versions
code/version
initial state
```

A replay cannot use the current active model/policy for historical periods where earlier versions were active.

## 13. Point-in-time reconstruction

The system must support:

```text
state_at(t)
```

where the state contains only events causally available according to the selected replay semantics.

The implementation must not query today's mutable tables and infer historical state from current values.

## 14. Replay modes

Architectural modes include:

```text
CAUSAL_HISTORICAL_REPLAY
LIVE_RECONSTRUCTION
AUDIT_REPLAY
SCENARIO_REPLAY
```

Each mode must declare which data/version semantics it uses.

## 15. Causal replay

Causal replay answers:

```text
What would Adaptive Edge have known and done at time t?
```

It must use historical availability boundaries and active policy/model versions.

## 16. Audit replay

Audit replay answers:

```text
What did the system actually record and decide?
```

It should preserve the original event lineage even when later corrections exist.

## 17. Scenario replay

Scenario replay may intentionally alter assumptions, but the altered assumptions must be explicitly versioned and must not be mistaken for historical truth.

## 18. Current-state separation

The following are distinct:

```text
HistoricalState(t)
CurrentState(now)
ScenarioState
```

A current-state mutation must not retroactively change `HistoricalState(t)`.

## 19. Versioned semantics

Changes to event schemas, policy definitions, feature definitions, execution models, or accounting rules must be versioned.

Historical replay must know which version applied to each event/decision.

## 20. Event schema evolution

Schema evolution must preserve the ability to interpret historical events.

Breaking changes require a new schema version and an explicit migration/compatibility strategy.

A parser must not reinterpret an old payload under new semantics without version evidence.

## 21. Correction events

A correction must preserve:

```text
original_event_id
correction_event_id
correction_reason
correction_time
source/provider
```

A corrected value does not prove that the corrected value was historically available.

## 22. Replay and corrections

Replay must support at least two distinct questions:

```text
what was known then?
what is the corrected historical record now?
```

Those questions may legitimately produce different results.

## 23. Determinism

For deterministic replay, identical:

```text
event stream
policy versions
model versions
feature transformations
calendar versions
execution model versions
initial state
code version
```

must produce identical derived state and decision sequence.

## 24. Randomness

If any component uses randomness, the replay contract must preserve:

```text
random seed
random algorithm/version
sampling policy
```

or otherwise record sufficient state to reproduce the result.

## 25. External dependencies

A replay must identify external dependencies whose behavior can change over time:

```text
market data
contract metadata
calendar
broker/provider semantics
model registry
configuration
```

A network call to today's provider state is not a valid substitute for historical state.

## 26. Event-store failure

If required historical events are missing, the replay result must explicitly indicate:

```text
INCOMPLETE_REPLAY
```

rather than silently filling the gap from current state.

## 27. Event gap detection

The system should detect gaps in expected event sequences where source semantics permit.

A gap may indicate:

```text
provider outage
storage loss
filtering error
missing backfill
```

The cause must not be guessed without evidence.

## 28. Duplicate detection

The same event identity must not be applied twice.

If two records claim the same identity but contain different payloads, the system must classify the conflict explicitly rather than choosing one silently.

## 29. Transactional boundaries

Where multiple canonical events represent one atomic state transition, the persistence layer must preserve sufficient transaction/batch identity to reconstruct whether the transition was complete or partial.

Exact database transaction semantics are implementation-specific.

## 30. Partial failure

If event processing fails after some derived effects are applied, recovery must be idempotent and able to resume without duplicating prior effects.

## 31. State hash / integrity

Where practical, derived state should expose an integrity identity such as a deterministic hash over relevant canonical state/version information.

The exact hash algorithm is implementation-specific.

## 32. Backtest provenance

A backtest result must identify:

```text
data version
feature version
label version
model/policy version
execution model version
accounting version
calendar version
code version
configuration version
```

A single mutable `backtest_id` without these dependencies is insufficient for audit-grade reproducibility.

## 33. Live provenance

Live decisions must identify the actual versions and source observations available at the decision boundary.

The live system must not rely on an implicit assumption that the latest deployed code is enough to reconstruct historical behavior.

## 34. Security and integrity boundary

Event provenance and state reconstruction must not depend on mutable user-editable identifiers alone.

Authentication, authorization, and secret management are infrastructure concerns but must preserve event integrity and access boundaries.

## 35. Retention

Retention policy must preserve all records required for:

```text
regulatory/audit obligations where applicable
strategy replay
risk reconciliation
execution reconciliation
learning lineage
```

The exact retention period is not defined by A47.

## 36. Deletion

Hard deletion of events that are required for historical audit or replay is prohibited by the canonical architecture unless a higher-order legal/security policy explicitly requires it and preserves an auditable deletion record.

## 37. Adversarial cases

### Current-state contamination

```text
historical replay
-> reads current contract metadata
```

Invalid.

### Missing event

```text
event absent
-> assume no event occurred
```

Invalid unless the source completeness contract proves absence.

### Correction overwrite

```text
old event replaced by corrected payload
```

Invalid for append-only historical provenance.

### Duplicate processing

Replaying the same event twice must not double-count position, accounting, or risk effects.

### Version drift

Replaying an old decision with today's model version is invalid for adaptive historical reconstruction.

## 38. Implementation gate

A47 framework implementation may provide:

```text
event schema
append-only event store interface
idempotent consumers
snapshots
replay engine
causation/correlation
version registry
integrity checks
```

Production replay remains dependent on upstream source/version contracts.

## 39. Parameter classes

### Frozen architecture

```text
append-only events
stable identity
causation/correlation
versioned semantics
point-in-time reconstruction
snapshot provenance
idempotent replay
correction lineage
incomplete-replay state
```

### Source-defined configuration

```text
event retention
provider sequence semantics
source completeness
calendar versioning
storage durability
```

### Learned

No learned state-persistence parameter is introduced by A47.

### External UNKNOWN

```text
historical source completeness
provider correction retention
exact broker event history
retention requirements
```

## 40. Completion criterion

A47 becomes `RESOLVED` when the system can reconstruct any historical state and explain:

```text
which events produced it
which versions were active
what information was available
what corrections occurred later
why each derived transition happened
```

without dependence on mutable current state.

## ARCHITECTURE STATUS

**FROZEN:** immutable event lineage; point-in-time state; versioned semantics; deterministic replay; correction lineage; idempotency; snapshot provenance; incomplete-replay handling.

**UNRESOLVED:** exact storage technology; retention; source completeness; provider historical event guarantees; deployment-level durability.

**BLOCKERS:** Production-grade replay depends on completeness of external historical event sources. Framework implementation is not blocked.

**NEXT ARTIFACT:** A48 — Configuration, Policy Versioning and Runtime Governance Contract.
