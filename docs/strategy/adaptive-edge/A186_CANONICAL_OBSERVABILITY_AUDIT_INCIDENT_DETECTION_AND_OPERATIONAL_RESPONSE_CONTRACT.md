# A186 — Canonical Observability, Audit, Incident Detection & Operational Response Contract

## Status
CANONICAL

## Purpose
Defines the evidence required to operate Adaptive Edge safely, detect material failures, reconstruct consequential decisions, and respond without inventing state.

## Observability domains
The runtime must expose sufficient evidence for:
```text
system health
data health
decision health
risk state
execution state
position state
reconciliation state
provider state
model state
security state
persistence/recovery state
```

## Audit lineage
Every consequential decision must eventually be traceable:
```text
raw data
 -> canonical event
 -> state
 -> feature
 -> probability
 -> economics
 -> decision
 -> authorization
 -> execution
 -> fill
 -> position
 -> outcome
 -> label
 -> learning
```

Audit evidence is immutable historical evidence.

## Event identity
Observability records must preserve canonical event identity, timestamps, version set, actor/authority, and source/provider identity where applicable.

## Health is multidimensional
A single `healthy=true` indicator is insufficient.

The system must distinguish at least:
```text
READY
DEGRADED
BLOCKED
UNKNOWN
FAILED
RECOVERING
```
for material subsystems.

## Alerting
Alerts must be tied to explicit operational conditions, not arbitrary noise thresholds. Critical alerts must identify:
```text
condition
scope
first observed time
current state
required authority/action
related evidence
```

## Incident identity
An incident has:
```text
incident_id
severity
opened_at
source condition
affected scope
current status
actions
authority
resolution evidence
```

## Incident lifecycle
```text
DETECTED
 -> TRIAGED
 -> CONTAINED
 -> RECOVERING
 -> RESOLVED
 -> CLOSED
```
A closed incident remains auditable.

## Exposure-aware response
Operational response must account for current position and execution uncertainty. A system outage does not imply a flat position.

## Reconciliation visibility
Operators must be able to identify:
```text
open positions
unknown orders
partial fills
provider/local mismatches
pending reconciliation
protection failures
```

## Emergency response
Emergency actions must be separately identifiable and must preserve causal and audit evidence. Emergency authority cannot silently mutate normal decision history.

## Audit storage
The exact storage technology remains UNKNOWN/TODO. The architectural requirement is durable, queryable, integrity-preserving evidence with defined retention and access control.

## Security observability
Security-sensitive actions must be observable:
```text
credential use
privileged authorization
manual intervention
break-glass activation
model promotion
configuration mutation
production release
```

## Recovery observability
Recovery must record:
```text
failure point
recovery start
reconstructed state
external reconciliation
recovery outcome
```

## Metrics
Metrics must distinguish:
```text
system metric
market metric
decision metric
execution metric
financial outcome
research metric
```
No metric should silently mix estimated and realized values.

## No false recovery
A subsystem is not marked recovered merely because its process restarted. Recovery requires state reconstruction and required external reconciliation.

## Invariants
```text
INV-186-001 consequential decisions are reconstructable
INV-186-002 audit history is immutable
INV-186-003 health is multidimensional
INV-186-004 incident state is explicit
INV-186-005 outage does not imply flat position
INV-186-006 unknown execution remains visible until reconciled
INV-186-007 emergency actions remain separately auditable
INV-186-008 privileged actions are observable
INV-186-009 recovery requires evidence, not process restart alone
INV-186-010 estimated and realized metrics remain distinct
```

## Adversarial tests
```text
missing audit event
out-of-order audit event
provider outage while position open
unknown order during incident
recovery with stale local state
manual intervention without authorization
break-glass action without review
false healthy signal
metrics using future information
incident closure before reconciliation
```

## Parameter classes
Frozen: lineage, audit immutability, multidimensional health, incident lifecycle, exposure-aware recovery.

Configuration: retention, alert thresholds, severity policy, escalation routing, review windows.

Validation-dependent: anomaly thresholds, operational SLOs, statistical alert sensitivity.

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact telemetry backend, audit store, alerting platform, incident-management integration.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A187 — Canonical Security, Identity, Secret, Credential & Break-Glass Contract
