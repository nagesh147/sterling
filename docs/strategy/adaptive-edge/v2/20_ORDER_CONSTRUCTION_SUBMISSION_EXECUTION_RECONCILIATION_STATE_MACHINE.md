# Adaptive Edge V2 — Order Construction, Submission and Execution-Reconciliation State Machine

**Artifact:** A44  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

A44 defines the boundary from an authorized order intent to an externally submitted order and then to an internally reconciled execution state.

A44 does **not** define instrument selection, quantity, order type, price policy, slippage model, broker-specific request fields, retry policy, or fill assumptions. Those require their governing contracts and must not be invented here.

## State separation

```text
A43 RiskAuthorization
        |
        v
OrderConstruction
        |
        v
OrderIntent
        |
        v
SubmissionAttempt
        |
        v
ExternalOrder
        |
        v
ExecutionObservation
        |
        v
ReconciledExecution
```

The following are distinct objects:

```text
OrderIntent
    = what the strategy authorized the system to attempt

SubmissionAttempt
    = one attempt to transmit that intent to an execution venue

ExternalOrder
    = the venue's representation, if any

ExecutionObservation
    = an externally observed order/fill/cancel/reject event

ReconciledExecution
    = the internally accepted interpretation of observed execution state
```

A local `SUBMITTED` event is not evidence of an external order. External acknowledgement is not evidence of a fill. A fill observation is not complete until reconciliation establishes its relation to the intended order and execution quantity.

## Order-construction states

```text
NOT_READY
READY
CONSTRUCTED
INVALID
EXPIRED
CANCELLED
```

`READY` means all required upstream authorization inputs are available. It does not imply that the order is valid for a particular venue.

`CONSTRUCTED` means a deterministic order representation was produced from the authorized intent and an explicit execution contract.

## Submission states

```text
NOT_SUBMITTED
SUBMISSION_PENDING
SUBMITTED
SUBMISSION_UNKNOWN
SUBMISSION_REJECTED
SUBMISSION_CANCELLED
```

`SUBMISSION_UNKNOWN` is mandatory for transport outcomes where the system cannot establish whether the venue accepted the request. The system must not automatically duplicate such a request merely because the local transport operation failed.

Every submission attempt requires a stable idempotency identity derived from the authorized order intent and attempt semantics. A retry is a new attempt and must preserve lineage to the same intent.

## External-order states

```text
UNKNOWN
ACKNOWLEDGED
OPEN
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
REJECTED
EXPIRED
```

Venue state is observed data. The reconciliation layer must not fabricate a venue state when the venue has not provided sufficient evidence.

## Reconciliation states

```text
NOT_RECONCILED
RECONCILING
RECONCILED_OPEN
RECONCILED_PARTIAL
RECONCILED_FILLED
RECONCILED_CANCELLED
RECONCILED_REJECTED
RECONCILIATION_EXCEPTION
```

A reconciliation exception is an explicit state, not an implicit fallback to the last known local state.

## Core invariants

1. An order cannot be constructed without an applicable authorization.
2. Authorization expiry/revocation invalidates further submission unless a new authorization explicitly permits the attempt.
3. An order intent cannot silently mutate after authorization. Material changes require a new intent and authorization lineage.
4. A submission attempt must reference exactly one order intent.
5. An external order identifier, when supplied, must be stored as external evidence rather than used as a local decision identifier.
6. A fill quantity must not exceed the authorized/constructed quantity. The exact quantity semantics remain blocked by the sizing contract.
7. Duplicate external observations must be idempotently reconciled.
8. Conflicting external observations must enter `RECONCILIATION_EXCEPTION`; they must not be resolved by preference for the newest local event alone.
9. Reconciliation cannot manufacture execution price, fees, slippage, or fill quantity when those values are absent from authoritative execution evidence.
10. Position state must be derived only through the separately governed position/accounting contract; A44 does not redefine position accounting.

## Failure taxonomy

```text
AUTHORIZATION_MISSING
AUTHORIZATION_EXPIRED
AUTHORIZATION_REVOKED
ORDER_CONSTRUCTION_INVALID
ORDER_CONSTRUCTION_EXPIRED
SUBMISSION_REJECTED
SUBMISSION_UNKNOWN
EXTERNAL_STATE_UNKNOWN
RECONCILIATION_CONFLICT
RECONCILIATION_INCOMPLETE
EXECUTION_DATA_INVALID
POLICY_DISABLED
```

Failures are persisted with provenance and timestamps. A transport failure is not equivalent to a venue rejection.

## Required lineage

Every A44 object must preserve, where applicable:

```text
order_intent_id
decision_id
authorization_id
submission_attempt_id
external_order_id
execution_observation_id
reconciliation_id
instrument_id
policy_version
execution_contract_version
created_at
observed_at
```

The exact schema and required fields remain implementation-gated by the execution contract.

## Reconciliation principle

```text
local intent
    + external evidence
    + authoritative observation ordering
    -> reconciled state
```

Never:

```text
local intent
    -> assume fill
```

and never:

```text
submission timeout
    -> assume rejection
```

or:

```text
missing fill report
    -> assume zero fill
```

## Implementation gate

A44 permits implementation of typed state domains, lineage records, transition guards, idempotency boundaries, and explicit reconciliation exceptions.

It does **not** authorize live order construction/submission until the unresolved execution, sizing, instrument, broker, account, cost, and position/accounting contracts are available.

## Status

**FROZEN:** separation of intent/submission/external order/observation/reconciliation; explicit unknown states; idempotency; lineage; fail-closed reconciliation; no fabricated fills or venue state; authorization expiry/revocation boundary.

**UNRESOLVED:** quantity semantics; instrument/contract selection; order type; price policy; broker adapter contract; retry semantics; execution costs; slippage; partial-fill policy; cancel/replace policy; position/accounting mapping.

**NEXT ARTIFACT:** A45 — Position/Execution Accounting Reconciliation Contract.
