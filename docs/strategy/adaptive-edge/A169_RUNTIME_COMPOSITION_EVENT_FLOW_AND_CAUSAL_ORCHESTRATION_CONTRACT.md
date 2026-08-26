# A169 — Runtime Composition, Event Flow & Causal Orchestration Contract

**Status:** CANONICAL  
**Authority:** Runtime composition and causal orchestration gate  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A168

## 1. Purpose

A169 defines how canonical events move through the Adaptive Edge runtime without changing their meaning, violating causal ordering, duplicating effects, or allowing orchestration to become a second business-rule authority.

It freezes runtime sequencing, ownership, idempotency, concurrency boundaries, failure propagation, and recovery behavior. It does not select strategy parameters.

## 2. Canonical causal pipeline

```text
external observation
    -> provider adapter
    -> canonical event
    -> temporal admission
    -> canonical state update
    -> feature/state snapshot
    -> probability / edge
    -> economics
    -> eligibility / decision
    -> risk authorization
    -> execution intent
    -> broker submission
    -> acknowledgement / uncertainty
    -> fill
    -> position state
    -> protection / lifecycle
    -> reconciliation
    -> outcome
    -> mature label
    -> research dataset
```

No downstream stage may influence an earlier stage in the same causal chain.

## 3. Runtime roles

```text
ADAPTER       external protocol -> canonical event
INGESTOR      admission, ordering, deduplication
STATE ENGINE  canonical state transition
FEATURE ENGINE deterministic derived state/features
DECISION      probability/economics/eligibility
AUTHORITY     risk authorization
EXECUTOR      execution intent -> broker
RECONCILER    external truth vs derived state
ORCHESTRATOR  sequencing only
AUDIT         consequential lineage
PERSISTENCE   durable evidence/state
```

The orchestrator coordinates these capabilities. It must not redefine their business semantics.

## 4. Event identity

Every canonical event requires stable identity and causal metadata sufficient for:

```text
event_id
source
observed_at
available_at
received_at
sequence/cursor where provided
parent/correlation identity where applicable
schema/version identity
```

`received_at` must never substitute for `observed_at` when determining market chronology.

## 5. Admission

An external event is admitted only when its identity, schema, instrument identity, timestamps, and required data-quality conditions satisfy the applicable contract.

Invalid events are rejected or quarantined according to their failure class. They are never silently transformed into valid business facts.

## 6. Causal rule

For any derived artifact `Y` created at decision time `t`:

```text
forall d in Dependencies(Y):
    available_at(d) <= t
```

If the condition cannot be established, `Y` is not eligible for a consequential decision.

## 7. Event ordering

The runtime must distinguish:

```text
chronological order
arrival order
processing order
commit order
```

These are not assumed equivalent.

Provider sequence information, timestamps, and canonical ordering rules determine admissibility. An out-of-order event may be delayed, rejected, or reconciled; it must not silently rewrite already-authorized history.

## 8. Idempotency

Every consequential effect must have a stable idempotency key derived from canonical identity and lifecycle semantics.

Duplicate delivery must satisfy:

```text
duplicate event
    -> no duplicate semantic effect
```

Idempotency does not mean duplicate evidence is discarded. Duplicate observations may remain auditable while producing one semantic transition.

## 9. Concurrency

Concurrent processing is permitted only where operations are semantically independent.

Operations affecting the same lifecycle identity must have a deterministic serialization/coordination rule.

Examples requiring coordination include:

```text
same position
same execution intent
same order lifecycle
same protection lifecycle
same reconciliation scope
```

## 10. Atomicity boundary

A consequential state transition must not expose an intermediate semantic state to downstream consumers.

Conceptually:

```text
validate
  -> compute transition
  -> persist authoritative transition/evidence
  -> publish resulting event
```

The exact transaction/outbox technology remains implementation-dependent.

## 11. Side-effect rule

Pure computation may be retried when deterministic and side-effect free.

External side effects require explicit lifecycle identity and uncertainty handling.

```text
compute != submit
submit != acknowledge
acknowledge != fill
fill != position reconciliation
```

## 12. Execution uncertainty

If submission outcome is unknown:

```text
UNKNOWN
```

must remain a first-class state.

The runtime must reconcile before treating the lifecycle as absent or safe to duplicate.

## 13. Failure propagation

Failures are classified rather than flattened into generic success/failure values.

At minimum:

```text
INVALID_INPUT
DATA_QUALITY
CAUSAL_VIOLATION
DEPENDENCY_UNAVAILABLE
AUTHORIZATION_FAILURE
BROKER_REJECTION
EXECUTION_UNKNOWN
PERSISTENCE_FAILURE
RECONCILIATION_MISMATCH
INTERNAL_CONTRACT_FAILURE
```

A lower-level failure cannot become a successful consequential business result merely because orchestration caught an exception.

## 14. Retry rule

Retry is permitted only when the operation's idempotency and side-effect semantics make retry safe.

For uncertain broker submissions, retry is forbidden until reconciliation establishes the prior submission's state or an explicit broker lifecycle rule authorizes a safe recovery path.

## 15. State ownership

The runtime never directly mutates canonical state outside the state owner's transition API/contract.

Orchestration requests transitions; state ownership validates and applies them.

## 16. Decision snapshot

A consequential decision is bound to the exact causal snapshot from which it was produced:

```text
decision_id
snapshot_id
feature/version identities
probability/version identity
economics/version identity
configuration/version identity
policy/version identity
created_at
valid_until where applicable
```

Later state cannot retroactively alter the historical decision.

## 17. Authorization freshness

Risk authorization must be checked against the execution-relevant validity boundary.

An expired or invalid authorization cannot be reused merely because the decision itself was previously valid.

## 18. Fill processing

A fill is an external execution fact.

The runtime must process:

```text
full fill
partial fill
duplicate fill
late fill
cancel/fill race
unknown fill
```

Position quantity is derived from accepted fill evidence and must not be inferred from order intent.

## 19. Position lifecycle

After any exposure-changing fill:

```text
fill accepted
    -> position update
    -> protection evaluation
    -> lifecycle evaluation
    -> reconciliation scheduling
```

Protection must not be delayed merely because the original order lifecycle remains open.

## 20. Reconciliation

Reconciliation compares independently derived internal state against authoritative external execution/position evidence.

A mismatch becomes an explicit state/evidence condition.

It must not be silently corrected by overwriting one side with the other.

## 21. Emergency path

Emergency execution is a separate operational pathway with explicit authority.

It must remain usable when normal decision orchestration is degraded, subject to its own safety controls.

Emergency execution still records intent, action, provider response, uncertainty, and reconciliation evidence.

## 22. Persistence/recovery

After restart, the runtime reconstructs state from durable canonical evidence and then reconciles external execution state where required.

Recovery must preserve:

```text
identity
causal ordering
partial fills
unknown submissions
open positions
protection state
reconciliation discrepancies
```

## 23. Backpressure

When downstream processing cannot keep pace, the runtime must use an explicit policy such as queueing, controlled degradation, rejection, or halt.

It must never silently drop consequential events.

The exact capacity thresholds are configuration/operational validation items.

## 24. Clock rule

Business logic consumes explicit timestamps/clock inputs.

Scattered wall-clock reads are forbidden in causal decision logic because they undermine deterministic replay and temporal testing.

## 25. Audit rule

Every consequential transition records enough lineage to reconstruct:

```text
input event(s)
state snapshot
calculation/version context
decision/authorization
execution lifecycle
resulting state
```

Operational logs do not replace canonical audit evidence.

## 26. Runtime graph invariant

The runtime dependency graph must preserve this direction:

```text
EVENT -> STATE -> DERIVATION -> DECISION -> AUTHORIZATION
                                      |
                                      v
                                  EXECUTION
                                      |
                                      v
                                    FILL
                                      |
                                      v
                                   POSITION
                                      |
                                      v
                              RECONCILIATION
```

Feedback from later stages may create a **new future event/state transition**. It may not mutate the causal meaning of a previously completed stage.

## 27. Hostile scenarios

A conformant runtime must explicitly handle:

```text
future event
out-of-order event
duplicate event
missing event
provider disconnect
stale quote
schema mismatch
parallel decisions on same position
authorization expiry during submission
submission timeout followed by actual fill
partial fill followed by crash
cancel/fill race
broker/local position mismatch
persistence failure
restart during uncertainty
emergency action during normal-path outage
```

## 28. Frozen architecture

```text
ORCHESTRATION = sequencing authority only
DOMAIN        = semantic authority
EXTERNAL DATA = untrusted until normalized/admitted
EXECUTION     = uncertain until externally evidenced
POSITION      = fill-derived and reconciled
RECOVERY      = evidence reconstruction + external reconciliation
LATER EVENTS  = may influence only future decisions
```

## 29. Invariants

```text
INV-169-001  No future information influences an earlier decision.
INV-169-002  Duplicate delivery cannot create duplicate semantic effects.
INV-169-003  Event arrival order is not assumed to equal event chronology.
INV-169-004  Orchestration cannot redefine domain semantics.
INV-169-005  Unknown execution state remains unknown until reconciled.
INV-169-006  Position quantity is derived from accepted fill evidence.
INV-169-007  Partial fills trigger position supervision.
INV-169-008  Authorization validity is checked at execution-relevant time.
INV-169-009  Recovery preserves lifecycle identity and uncertainty.
INV-169-010  Consequential events cannot be silently dropped.
INV-169-011  Later evidence cannot retroactively alter prior decisions.
INV-169-012  Emergency execution remains auditable and reconcilable.
INV-169-013  Consequential state transitions are atomic at their semantic boundary.
INV-169-014  Every consequential transition remains causally traceable.
```

## 30. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- canonical runtime sequence
- event admission
- causal ordering
- event identity
- idempotency
- concurrency boundaries
- state ownership
- side-effect separation
- execution uncertainty
- retry constraints
- decision snapshots
- authorization freshness
- fill processing
- position lifecycle
- reconciliation
- emergency path
- recovery semantics
- backpressure principle
- explicit clock boundary
- audit lineage
- future-event-only feedback

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact event bus/queue technology
- exact transaction/outbox implementation
- exact concurrency primitive
- exact backpressure implementation
- exact persistence implementation

CONFIGURATION TO VALIDATE:
- queue capacities
- retry limits
- timeout values
- concurrency limits
- backpressure thresholds
- reconciliation cadence

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification.
Implementation requires A167 conformance mapping and A168 ownership boundaries.

NEXT ARTIFACT:
A170 — Persistence, Transactionality, Idempotency & Recovery Implementation Contract
```
