# A179 — Canonical Trade Lifecycle State Machine, Entry-to-Exit Transition Contract

## Status
CANONICAL

## Purpose
A179 defines the complete trade lifecycle as a temporal state machine. It freezes legal states, transitions, guards, postconditions, idempotency requirements, and forbidden transitions from entry authorization through final closure and reconciliation.

## Canonical lifecycle
```text
CANDIDATE
  -> ELIGIBLE
  -> DECISIONED
  -> RISK_AUTHORIZED
  -> EXECUTION_INTENT
  -> SUBMISSION_PENDING
  -> SUBMITTED / UNKNOWN
  -> ACKNOWLEDGED
  -> PARTIALLY_FILLED
  -> FILLED
  -> PROTECTED
  -> ACTIVE
  -> EXIT_INTENT
  -> EXIT_SUBMITTED / UNKNOWN
  -> EXIT_PARTIALLY_FILLED
  -> CLOSED_PENDING_RECONCILIATION
  -> CLOSED
```

Provider-specific states are mapped into this canonical state machine without losing raw provider evidence.

## State authority
Every state has one canonical authority and immutable transition evidence. Current state is derived from accepted events; historical events are never rewritten.

## Transition contract
Every transition defines:
```text
triggering_event
preconditions
state_before
state_after
side_effects
postconditions
idempotency_key
causal_timestamp
availability_timestamp
audit_reference
failure_behavior
```

## Legal transition rule
A transition is legal only if its source state, triggering event, guard, and authority match the canonical contract. Unknown transitions fail closed and enter an explicit uncertainty/reconciliation path rather than being coerced into a known state.

## Entry lifecycle
Entry cannot progress directly from decision to position. It must pass through authorization, execution intent, order lifecycle, and fill evidence.

```text
DECISION -> RISK_AUTHORIZED -> EXECUTION_INTENT -> SUBMISSION
```

## Submission uncertainty
If broker submission outcome is unknown, state becomes `SUBMITTED / UNKNOWN`. The system must not blindly retry because the original request may have been accepted.

Recovery requires provider evidence and reconciliation.

## Partial fills
Partial fill is a first-class state. Quantity transitions are additive and idempotent:
```text
filled_quantity_new = filled_quantity_old + newly_accepted_fill_quantity
```
The same provider fill cannot be applied twice.

## Position creation
A position becomes canonical only from accepted fill evidence and position accounting, not from order acknowledgement.

## Protection
Protection is attached to the actual canonical position quantity. Protection cannot assume that requested order quantity equals filled quantity.

## Exit lifecycle
Exit is a new lifecycle phase linked to the position identity. Exit intent must preserve the exit authority from A177 and cannot mutate the historical entry decision.

## Closure
A position becomes `CLOSED_PENDING_RECONCILIATION` when the canonical lifecycle believes exposure is zero but final broker/accounting confirmation remains required. `CLOSED` requires the applicable reconciliation condition.

## Re-entry
A closed lifecycle cannot transition directly back to execution. A new signal and A178 decision lifecycle is required.

## Reversal
A reversal is not an implicit close-and-reopen shortcut. It must be represented as explicit exit and new-entry lifecycles unless a separately authorized transformation policy defines otherwise.

## Emergency path
Emergency exit may use a specialized authority but remains within the canonical state machine and audit lineage. Emergency does not mean untracked.

## Session close
Mandatory session closure follows A177 lifecycle authority and creates explicit exit evidence. If execution remains uncertain, the lifecycle remains in uncertainty/reconciliation rather than being marked closed by assumption.

## Recovery
On restart:
```text
persisted events
    -> reconstruct lifecycle
    -> identify uncertainty
    -> query provider evidence
    -> reconcile
    -> resume only from an authorized state
```
No state may be inferred solely from process memory.

## Concurrency
State transitions use an explicit aggregate version or equivalent compare-and-set semantics. A stale worker cannot commit a transition over a newer lifecycle state.

## Idempotency
Repeated delivery of the same canonical event produces no additional state mutation after the first accepted application. Idempotency identity is stable across retries and restarts.

## Causal ordering
Event time and availability time are distinct. A state transition may consume an event only when its availability boundary permits consumption. Later information cannot alter an earlier state transition.

## Failure conditions
Enter explicit uncertainty/reconciliation for:
```text
ambiguous broker submission
unknown order state
unknown fill state
conflicting provider evidence
position mismatch
duplicate/conflicting fill
stale worker version
missing mandatory event
provider outage during consequential lifecycle
```

Never silently mark a lifecycle `FILLED`, `CLOSED`, or `FLAT` from an assumption.

## Forbidden transitions
```text
DECISION -> FILLED
DECISION -> POSITION
ORDER_ACK -> FILLED without fill evidence
PARTIAL_FILL -> CLOSED without zero-position evidence
UNKNOWN_SUBMISSION -> RETRY blindly
EXIT -> REENTRY
PROCESS_RESTART -> assume flat
PROVIDER_OUTAGE -> assume no exposure
```

## Invariants
```text
INV-179-001 Every state transition has a canonical trigger and guard.
INV-179-002 Historical lifecycle events are immutable.
INV-179-003 Order acknowledgement is not fill evidence.
INV-179-004 Fill evidence is required for position creation.
INV-179-005 Partial fills are first-class and idempotent.
INV-179-006 Unknown provider state remains unknown until reconciled.
INV-179-007 Stale workers cannot overwrite newer lifecycle versions.
INV-179-008 Closed status requires the defined reconciliation condition.
INV-179-009 Re-entry requires a new decision lifecycle.
INV-179-010 Future information cannot alter an earlier transition.
INV-179-011 Emergency execution remains inside audit and reconciliation boundaries.
INV-179-012 Lifecycle identity remains stable across retries and restarts.
```

## Parameter classes
### Frozen architecture
State machine, transition separation, uncertainty states, partial-fill semantics, idempotency, concurrency/versioning, reconciliation requirement, causal ordering, forbidden transitions.

### Configuration to validate
Provider polling/reconciliation cadence, timeout policies, emergency escalation, session-close behavior, retry limits, uncertainty escalation.

### Learned / validation-dependent
None. Lifecycle correctness must not depend on learned parameters.

## Adversarial tests
Crash at every transition boundary; duplicate event; duplicate fill; partial fill; cancel/fill race; submission timeout; provider outage; conflicting provider status; stale worker; restart with open position; restart with unknown submission; emergency exit during outage; session cutoff race; reversal; repeated reconciliation.

## Architecture Status
```text
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact Kite order-state and post-restart query semantics; exact provider reconciliation guarantees.
CONFIGURATION TO VALIDATE: polling/reconciliation cadence; timeout; escalation; retry; session-close behavior.
LEARNED / VALIDATION-DEPENDENT: None.
BLOCKERS: None for specification work. Production execution remains blocked until Kite semantics and operational recovery behavior are verified.
NEXT ARTIFACT: A180 — Canonical Portfolio Exposure, Capital Budget & Cross-Position Risk Aggregation Contract
```
