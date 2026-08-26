# A171 — Canonical Execution Persistence Schema & Lifecycle Record Contract

**Status:** CANONICAL  
**Authority:** Canonical durable representation of execution lifecycle records  
**Scope:** Adaptive Edge  
**Dependencies:** A156–A170

## 1. Purpose

A171 defines the canonical persisted record model for execution intent, order lifecycle, provider evidence, fills, position effects, protection, reconciliation, and execution uncertainty. It freezes semantic record boundaries without selecting a database or serialization technology.

## 2. Record-family separation

The following are distinct records:

```text
ExecutionIntent
OrderLifecycle
ProviderOrderEvidence
ProviderTradeEvidence
FillApplication
PositionEffect
ProtectionLifecycle
ReconciliationRecord
ExecutionAuditRecord
```

No record may silently substitute for another.

## 3. Common metadata

Every canonical persisted record requires, as applicable:

```text
record_id
record_type
schema_version
created_at
available_at
source
causal_parent_ids
correlation_id
aggregate_id
aggregate_version
status
```

Provider timestamps and identifiers remain separate fields.

## 4. ExecutionIntent

Minimum semantic fields:

```text
execution_intent_id
decision_id
position_context_id
instrument_identity
side
requested_quantity
execution_policy
risk_authorization_id
configuration_version
policy_version
valid_from
valid_until
status
```

An intent expresses what the system authorized; it does not prove submission or execution.

## 5. OrderLifecycle

Minimum fields:

```text
order_lifecycle_id
execution_intent_id
attempt_number
parent_order_lifecycle_id
provider
provider_order_id
submission_state
order_state
requested_quantity
accepted_quantity
cancel_requested_at
replacement_reason
created_at
updated_at
```

Provider IDs are nullable until known and are never synthesized.

## 6. ProviderOrderEvidence

Preserve external order evidence independently of canonical interpretation:

```text
provider_order_id
exchange_order_id
provider_order_status
provider_order_timestamp
provider_exchange_update_timestamp
provider_exchange_timestamp
provider_update_sequence
raw_evidence_reference
observed_at
received_at
```

Provider evidence must not be rewritten to match local expectations.

## 7. ProviderTradeEvidence

A trade/fill observation is distinct from its parent order:

```text
provider_trade_id
provider_order_id
exchange_trade_id
instrument_identity
side
quantity
price
provider_timestamp
received_at
```

Duplicate provider trade evidence is semantically deduplicated by identity while remaining auditable.

## 8. FillApplication

```text
fill_application_id
provider_trade_id
execution_intent_id
order_lifecycle_id
signed_quantity
execution_price
applied_at
position_before
position_after
application_version
```

A fill application exists only from accepted execution evidence.

## 9. PositionEffect

A position effect records exposure change attributable to an accepted fill application:

```text
position_before + signed_fill_quantity = position_after
```

It must never originate directly from order intent.

## 10. ProtectionLifecycle

```text
protection_id
position_context_id
trigger_basis
requested_quantity
protected_quantity
unprotected_quantity
provider_order_lifecycle_id
state
created_at
updated_at
failure_reason
```

Requested protection is not equivalent to effective protection.

## 11. ReconciliationRecord

```text
reconciliation_id
scope
run_id
observed_at
internal_state_reference
external_state_reference
comparison_result
difference
resolution_state
resolution_evidence
```

Mismatch is preserved as evidence until explicitly resolved.

## 12. Uncertainty

Semantic uncertainty must be explicit:

```text
SUBMISSION_UNKNOWN
CANCEL_UNKNOWN
FILL_UNKNOWN
POSITION_UNKNOWN
RECONCILIATION_UNKNOWN
```

Null is not a substitute for an uncertainty state.

## 13. Partial fills and replacement

The model must support arbitrary fill sequences and preserve replacement lineage:

```text
original lifecycle
    -> partial fills
    -> remaining quantity
    -> replacement lifecycle
```

Replacement cannot erase the original historical state.

## 14. Idempotency

Every applied consequential event must be discoverable through an idempotency record or equivalent:

```text
idempotency_scope
idempotency_key
semantic_hash
first_applied_record_id
first_applied_at
```

A conflicting semantic hash is an idempotency conflict and fails closed.

## 15. Immutability and versioning

Historical records are immutable. Mutable aggregates require a monotonic version or equivalent concurrency token. Corrections are new versioned evidence, never silent mutation.

## 16. Raw evidence boundary

```text
RAW PROVIDER EVIDENCE
        |
        v
NORMALIZATION
        |
        v
CANONICAL INTERPRETATION
```

Original evidence remains recoverable.

## 17. Timestamp semantics

Preserve distinct timestamps for:

```text
provider observation
provider exchange event
system receipt
canonical availability
processing
commit
```

A generic timestamp alone is insufficient.

## 18. Numeric semantics

Quantity, price, currency, lot, contract, unit, and precision semantics must remain recoverable. Serialization must not silently change accounting meaning.

## 19. Referential integrity

Mandatory lineage must remain reconstructible:

```text
decision -> execution intent -> order lifecycle
order lifecycle -> provider order evidence
provider order -> provider trade evidence
provider trade -> fill application -> position effect
position -> protection
all -> reconciliation/audit
```

## 20. Recovery queries

Persistence must reconstruct at minimum:

```text
uncertain execution intents
open order lifecycles
unprocessed provider trades
open positions
active protection lifecycles
unresolved reconciliation records
```

## 21. Schema evolution

A schema change is admissible only when historical interpretation remains deterministic or an explicit versioned migration/reader exists. Historical meaning must not be silently altered.

## 22. Deletion

Canonical execution evidence is append-preserving. Retention/deletion is configuration subject to audit, research, and recovery requirements.

## 23. Hostile cases

The schema must support and test:

```text
duplicate provider trade
conflicting duplicate
missing provider order ID
late fill
partial fill after cancellation
replacement after partial fill
null provider/exchange timestamp
provider status regression
position mismatch
unknown submission after restart
corrupt record
schema-version mismatch
```

## 24. Invariants

```text
INV-171-001  Order intent never proves execution.
INV-171-002  Provider order evidence never proves fill.
INV-171-003  Fill evidence is distinct from fill application.
INV-171-004  Position effects originate from accepted fill applications.
INV-171-005  Historical execution records are immutable.
INV-171-006  Provider evidence is preserved independently from interpretation.
INV-171-007  Unknown execution states are explicit.
INV-171-008  Replacement preserves original lineage.
INV-171-009  Duplicate provider trades cannot create duplicate exposure.
INV-171-010  Conflicting idempotency evidence fails closed.
INV-171-011  Mandatory causal references remain reconstructible.
INV-171-012  Timestamp semantics cannot be collapsed into one generic clock.
```

## 25. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- execution record-family separation
- canonical lifecycle identity
- provider evidence preservation
- fill/application separation
- position-effect accounting
- protection effectiveness representation
- reconciliation records
- explicit uncertainty states
- replacement lineage
- immutable historical records
- version/concurrency identity
- timestamp semantic separation
- referential integrity
- recovery query requirements

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- physical database schema syntax
- indexing technology
- serialization format
- exact partitioning strategy
- archival storage technology

CONFIGURATION TO VALIDATE:
- retention
- indexing/partitioning parameters
- archival cadence
- recovery query performance targets

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification.
Physical persistence implementation remains blocked until technology selection and validation.

NEXT ARTIFACT:
A172 — Canonical Market-Data Event Persistence & Temporal Snapshot Contract
```