# A170 — Persistence, Transactionality, Idempotency & Recovery Implementation Contract

**Status:** CANONICAL  
**Authority:** Durable state, evidence, idempotency, transactionality, and recovery implementation boundary  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A169

## 1. Purpose

A170 translates the frozen persistence and recovery architecture into an implementation contract without selecting a technology prematurely.

It defines what must be durable, what must be atomic, how duplicate delivery is prevented from producing duplicate semantic effects, how crashes are recovered, and how external execution state is reconciled after recovery.

It does not choose a database, event bus, ORM, serialization format, or cloud service.

## 2. Persistence authority

The persistence layer is an evidence and state durability mechanism. It is not a second domain authority.

```text
DOMAIN CONTRACT
      |
      v
STATE TRANSITION
      |
      v
DURABLE EVIDENCE / STATE
```

Persistence must not silently reinterpret business semantics.

## 3. Durable categories

At minimum, the implementation must preserve:

```text
canonical events
state transitions
execution intents
provider order identities
provider trade/fill evidence
authorization records
decision snapshots
position state
protection state
reconciliation evidence
outcome evidence
label maturity state
model/version lineage
configuration/version lineage
audit evidence
```

Retention policy is configuration and must be validated against audit and research requirements.

## 4. Event durability

A consequential canonical event must not be acknowledged as durably accepted unless the system can recover it according to the event contract.

An event may be:

```text
RECEIVED
VALIDATED
PERSISTED
PROCESSED
REJECTED
QUARANTINED
```

These states must not be collapsed.

## 5. Semantic atomicity

For a state transition that creates consequential downstream effects, the implementation must provide an atomic semantic boundary equivalent to:

```text
validate
  -> compute transition
  -> persist transition/evidence
  -> make resulting event publishable
```

The exact mechanism may be a transaction, transactional outbox, durable command record, or another implementation satisfying the same semantics.

## 6. Transaction boundary

A transaction must encompass all data that must succeed or fail together to preserve one canonical semantic transition.

It must not attempt to make an external broker API transactionally atomic with local storage.

External side effects remain independently uncertain and require reconciliation.

## 7. External side-effect rule

The implementation must assume:

```text
local commit != broker commit
broker acknowledgement != exchange execution
```

Therefore a local transaction cannot mark an order filled merely because an order submission record committed.

## 8. Idempotency

Every externally repeatable consequential operation requires an idempotency identity.

Examples:

```text
canonical_event_id
execution_intent_id
order_lifecycle_id
provider_order_id
provider_trade_id
reconciliation_run_id
```

Provider identifiers must not be substituted for canonical lifecycle identities.

## 9. Idempotent processing

For an already-applied semantic event:

```text
re-delivery
    -> retrieve prior application
    -> verify identity/version compatibility
    -> produce no second semantic effect
```

A conflicting duplicate must fail loudly rather than being treated as an ordinary duplicate.

## 10. Idempotency conflict

If the same idempotency key arrives with materially different semantic content:

```text
IDEMPOTENCY_CONFLICT
```

must be raised.

The existing committed effect must not be overwritten.

## 11. Ordering

Persistence must retain enough causal metadata to reconstruct:

```text
observed order
available order
processing order
commit order
```

Commit order must never be used as a substitute for market chronology.

## 12. Concurrency control

Concurrent transitions affecting the same lifecycle identity require deterministic serialization or conflict detection.

At minimum this applies to:

```text
same position
same execution intent
same order lifecycle
same protection lifecycle
same reconciliation scope
```

The implementation must prevent lost updates and double application.

## 13. Optimistic conflict

If optimistic concurrency is used, every mutable authoritative aggregate must have a version.

Conceptually:

```text
read version = V
apply only if current version = V
commit version = V + 1
```

A conflict must cause retry/reconciliation according to the operation's semantics, not blind overwrite.

## 14. Recovery point

Recovery must begin from durable evidence, not in-memory assumptions.

The implementation must identify a deterministic recovery boundary such that after restart:

```text
recovered_state
```

is derivable from durable evidence plus explicitly permitted external reconciliation.

## 15. Crash scenarios

The implementation must handle crashes at each consequential boundary:

```text
before persistence
between persistence and publication
after publication before acknowledgement
during provider submission
after provider submission before response
after partial fill
during protection update
during reconciliation
```

No crash point may produce an impossible canonical state.

## 16. Outbox/equivalent requirement

If local state and event publication cannot share one transaction, an equivalent durable mechanism must guarantee:

```text
committed consequential state
    -> eventually publishable resulting event
```

and:

```text
published event
    -> safely deduplicable
```

The exact technology remains UNKNOWN/TODO until selected.

## 17. Recovery and broker uncertainty

After restart, any execution intent in an uncertain state must remain uncertain until broker reconciliation establishes its external state.

Forbidden recovery behavior:

```text
unknown submission
    -> assume rejected
    -> resubmit
```

or:

```text
unknown submission
    -> assume filled
```

without evidence.

## 18. Position reconstruction

Derived position must be reconstructible from accepted fill evidence.

Conceptually:

```text
position(t)
    = opening_position
    + sum(accepted signed fills through t)
```

The exact treatment of corporate actions, transfers, broker adjustments, and non-strategy positions remains an external/accounting dependency and must be explicitly classified.

## 19. Reconciliation after recovery

Recovery must perform external reconciliation for execution-sensitive state.

At minimum:

```text
open orders
fills/trades
positions
protection state where externally represented
```

A mismatch must become explicit evidence, not an overwrite operation.

## 20. Partial-fill recovery

If durable evidence records:

```text
intent = 100
accepted fill = 40
```

then recovery must reconstruct:

```text
filled = 40
remaining = 60
```

unless later external evidence changes the canonical lifecycle.

## 21. Duplicate recovery

If the same provider trade is observed before and after restart, the provider trade identity must prevent double counting.

A missing provider identifier is a reconciliation/data-quality condition, not permission to count the event twice.

## 22. Tombstones and negative evidence

The implementation must distinguish absence of evidence from explicit negative evidence.

For example:

```text
NO_ORDER_FOUND
```

is not necessarily equivalent to:

```text
ORDER_CONFIRMED_REJECTED
```

Negative evidence must preserve its source and observation context.

## 23. Retention

Retention must preserve all evidence required for:

```text
regulatory/audit requirements where applicable
incident reconstruction
reconciliation
research reproducibility
model lineage
causal replay
```

Exact duration is CONFIGURATION TO VALIDATE.

## 24. Serialization

Serialization must preserve semantic identity, timestamps, numeric units, precision requirements, optionality, and version identity.

Lossy serialization is prohibited for canonical evidence unless explicitly authorized by the relevant contract.

## 25. Schema evolution

Persisted records must carry schema/version identity sufficient to determine how they should be interpreted after deployment changes.

Backward-compatible evolution is preferred but is not assumed.

Incompatible records require an explicit migration or reader strategy.

## 26. Migration safety

A migration must not silently alter historical meaning.

For canonical evidence:

```text
old meaning
    !=
new interpretation
```

unless the migration is proven semantics-preserving and recorded.

Historical evidence must remain reproducible under the version that created it.

## 27. Recovery idempotency

Recovery itself must be safely repeatable.

Running recovery twice must not:

```text
double-count fills
duplicate orders
rewrite historical decisions
advance labels incorrectly
create duplicate reconciliation effects
```

## 28. Manual intervention

Manual intervention is itself an auditable consequential action.

It must have:

```text
actor
authority
reason
scope
timestamp
before-state
action
after-state
```

Manual intervention must not bypass canonical accounting.

## 29. Emergency recovery

If normal persistence or reconciliation infrastructure is degraded while market exposure exists, the emergency path must preserve the minimum evidence necessary to reconstruct:

```text
what exposure existed
what action was attempted
what provider reported
what remains uncertain
```

Exact emergency durability technology remains TODO.

## 30. Failure classification

Persistence failures must remain distinguishable from business rejections:

```text
PERSISTENCE_UNAVAILABLE
TRANSACTION_CONFLICT
SERIALIZATION_FAILURE
SCHEMA_FAILURE
DURABILITY_UNKNOWN
RECOVERY_FAILURE
RECONCILIATION_FAILURE
IDEMPOTENCY_CONFLICT
```

The runtime must not convert these into successful business outcomes.

## 31. Data corruption

Detected corruption must cause controlled quarantine or halt according to severity.

The implementation must never silently repair canonical evidence by guessing.

Repair requires:

```text
source evidence
repair rationale
new version/evidence
audit record
```

## 32. Backup and restore

Production durability requires tested restore capability.

A backup that has never been restored is not evidence of recoverability.

Restore testing must verify:

```text
identity preservation
causal ordering
schema interpretation
position reconstruction
execution reconciliation
audit continuity
```

## 33. Recovery invariant

The recovery function is conceptually:

```text
R(durable_evidence, permitted_external_evidence, version_set)
    -> canonical_state
```

It must be deterministic for identical evidence and version inputs.

## 34. Forbidden behaviors

```text
silent overwrite of authoritative evidence
assume-fill after timeout
assume-rejection after timeout
blind retry of uncertain side effect
double application after restart
use wall clock to reconstruct historical causality
lossy canonical serialization
implicit schema reinterpretation
manual database edits without audit
```

## 35. Hostile scenarios

The implementation must test:

```text
crash before commit
crash after commit before publish
crash after publish
duplicate delivery
conflicting duplicate
two workers same lifecycle
provider timeout then fill
restart during unknown submission
restart after partial fill
restore from backup
schema version mismatch
corrupt record
reconciliation mismatch
manual intervention during outage
```

## 36. Frozen architecture

```text
DURABLE EVIDENCE > IN-MEMORY STATE
CANONICAL STATE > CACHE
EXTERNAL EXECUTION > LOCAL ASSUMPTION
UNKNOWN > GUESSED OUTCOME
RECONCILIATION > BLIND RETRY
VERSIONED EVIDENCE > AMBIGUOUS SERIALIZATION
```

## 37. Invariants

```text
INV-170-001  Consequential state transitions have a durable semantic boundary.
INV-170-002  Duplicate delivery cannot duplicate semantic effects.
INV-170-003  Conflicting idempotency keys fail closed.
INV-170-004  External side effects are never assumed transactionally atomic with local state.
INV-170-005  Unknown broker outcomes remain unknown until reconciled.
INV-170-006  Position reconstruction is fill-evidence based.
INV-170-007  Recovery is repeatable without duplicate semantic effects.
INV-170-008  Historical evidence retains version identity.
INV-170-009  Canonical evidence is not silently overwritten.
INV-170-010  Backup restore is tested, not merely configured.
INV-170-011  Manual intervention remains auditable.
INV-170-012  Corrupt evidence is quarantined rather than guessed.
INV-170-013  Recovery preserves causal and lifecycle identity.
INV-170-014  Persistence failure cannot become business success.
```

## 38. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- durable evidence boundary
- semantic transaction boundary
- idempotency
- idempotency conflict handling
- concurrency control
- recovery model
- external-side-effect uncertainty
- position reconstruction
- reconciliation after restart
- partial-fill recovery
- schema/version identity
- migration safety
- recovery idempotency
- manual intervention auditability
- corruption handling
- backup/restore requirement

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- database technology
- event bus/queue technology
- transaction/outbox technology
- serialization format
- backup technology
- restore infrastructure
- exact concurrency primitive

CONFIGURATION TO VALIDATE:
- retention duration
- transaction timeouts
- retry limits
- queue capacities
- backup frequency
- restore objectives
- reconciliation cadence

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification.
Production implementation remains blocked until persistence and recovery
are implemented and failure-tested.

NEXT ARTIFACT:
A171 — Canonical Execution Persistence Schema & Lifecycle Record Contract
```
