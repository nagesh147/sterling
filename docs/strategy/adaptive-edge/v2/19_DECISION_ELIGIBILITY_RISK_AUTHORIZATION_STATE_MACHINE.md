# Adaptive Edge V2 — Decision, Eligibility and Risk-Authorization State Machine

**Artifact:** A43  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

## 1. Purpose

A43 defines the state-machine boundary between a candidate decision, eligibility evaluation, risk authorization, and an executable order intent.

It prevents the system from conflating:

```text
prediction
eligibility
risk authorization
order intent
execution
position
```

A43 does not invent numerical risk limits, sizing formulas, probability thresholds, or execution parameters.

## 2. Canonical causal chain

```text
DecisionInput
    |
    v
EligibilityEvaluation
    |
    v
RiskAuthorizationRequest
    |
    v
RiskAuthorization
    |
    v
OrderIntent
    |
    v
Execution
```

No stage may silently substitute for another.

## 3. State domains

A43 treats the following as separate state machines:

```text
DecisionState
EligibilityState
RiskAuthorizationState
OrderIntentState
```

They may be causally related but are not the same state variable.

## 4. Decision states

Architectural states:

```text
NOT_EVALUATED
EVALUATING
ACCEPTED
REJECTED
EXPIRED
SUPERSEDED
```

`ACCEPTED` means the decision policy accepted the opportunity for further authorization evaluation; it does not mean an order was placed.

## 5. Eligibility states

Architectural states:

```text
UNKNOWN
ELIGIBLE
INELIGIBLE
EXPIRED
INVALID
```

Eligibility must be computed from the canonical decision input and policy version.

## 6. Risk authorization states

Architectural states:

```text
NOT_REQUESTED
PENDING
AUTHORIZED
DENIED
EXPIRED
REVOKED
INVALID
```

Authorization is a temporal permission, not a permanent property of a signal.

## 7. Order-intent states

A43 consumes the order contract from A35. The architectural states are:

```text
NOT_CREATED
CREATED
SUBMITTED
CANCEL_REQUESTED
CANCELLED
REJECTED
EXPIRED
```

Actual fill state remains downstream of execution and is not an order-intent state.

## 8. Eligibility definition

Eligibility must identify every required condition:

```text
condition_id
source
value
availability_time
policy version
result
failure reason
```

An eligibility formula without defined inputs and source semantics is incomplete.

## 9. Eligibility aggregation

If multiple independent eligibility conditions are required, the canonical architecture is:

```text
Eligible
    = all(required_conditions == PASS)
```

This is structural only. The actual conditions are strategy-specific.

## 10. Unknown condition behavior

A required condition that is `UNKNOWN`, `STALE`, `INVALID`, or otherwise causally unusable cannot silently become `PASS`.

The default architecture is fail-closed:

```text
required condition unresolved
    -> eligibility not granted
```

## 11. Risk authorization definition

Risk authorization must eventually specify:

```text
risk measure
risk state
risk limit
requested exposure
reservation semantics
authorization duration
revocation conditions
release conditions
```

These are not numerically defined by A43.

## 12. Authorization versus risk estimate

A risk estimate is an input to authorization.

Authorization is the resulting policy decision.

Therefore:

```text
RiskEstimate != RiskAuthorization
```

## 13. Authorization versus sizing

Sizing determines a requested quantity under a policy.

Authorization determines whether that requested exposure is permitted.

They must remain separate unless the canonical risk contract explicitly combines them.

## 14. Authorization lifecycle

Canonical lifecycle:

```text
NOT_REQUESTED
      |
      v
PENDING
   /     \
  v       v
AUTHORIZED DENIED
   |
   v
REVOKED / EXPIRED
```

A revoked authorization cannot be treated as active.

## 15. Authorization timestamp

Every authorization must contain:

```text
authorization_id
requested_at
authorized_at
expires_at
policy_version
risk_state_version
scope
```

Exact fields may expand with the risk contract.

## 16. Authorization scope

Authorization must identify what it authorizes:

```text
instrument/opportunity
side
maximum quantity or exposure
strategy/version
account scope
validity interval
```

An authorization for one instrument cannot silently authorize another.

## 17. Revalidation

If material decision/risk inputs change before order submission, the system must determine whether the authorization remains valid.

A43 requires an explicit revalidation policy.

No implicit assumption that authorization remains valid indefinitely.

## 18. Expiry

An authorization must not be used after its expiry boundary.

The exact duration is unresolved.

If no valid expiry semantics exist, executable authorization is blocked.

## 19. Revocation

Authorization may become invalid due to an explicitly defined event such as:

```text
risk-state change
policy disable
account-state change
market/instrument invalidation
execution constraint failure
system safety event
```

Only explicitly defined events may revoke authorization.

## 20. Revocation versus position liquidation

Revoking permission for a new order does not automatically imply liquidation of an existing position.

Existing positions are governed by A36 protection/position policy.

## 21. Decision acceptance versus order creation

```text
Decision ACCEPTED
    !=
OrderIntent CREATED
```

An order intent may still be blocked by risk, execution, contract, or system constraints.

## 22. Order intent idempotency

The same decision/authorization pair must not create duplicate order intents merely because the evaluation loop runs twice.

A stable idempotency key is required.

The exact construction is implementation-specific and must preserve semantic uniqueness.

## 23. Re-evaluation

Repeated evaluation of the same opportunity must have explicit semantics:

```text
NEW_DECISION
REUSE_EXISTING_DECISION
SUPERSEDE_PRIOR_DECISION
NO_ACTION
```

The system must not accidentally create repeated orders from repeated observations.

## 24. State transition contract

Every transition must identify:

```text
triggering event
preconditions
state transformation
postconditions
forbidden transitions
```

This requirement applies independently to decision, eligibility, authorization, and order-intent states.

## 25. Decision transition examples

Valid architectural transitions:

```text
NOT_EVALUATED -> EVALUATING
EVALUATING -> ACCEPTED
EVALUATING -> REJECTED
ACCEPTED -> EXPIRED
ACCEPTED -> SUPERSEDED
```

Invalid example:

```text
NOT_EVALUATED -> SUBMITTED
```

because risk authorization and order-intent creation are bypassed.

## 26. Authorization transition examples

Valid:

```text
NOT_REQUESTED -> PENDING
PENDING -> AUTHORIZED
PENDING -> DENIED
AUTHORIZED -> EXPIRED
AUTHORIZED -> REVOKED
```

Invalid:

```text
DENIED -> ORDER_SUBMITTED
```

without a new valid authorization event.

## 27. Risk ledger dependency

Authorization consumes the risk state defined by the risk/accounting architecture.

The authorization layer cannot invent `EffectiveRisk`.

If the risk quantity is undefined, authorization remains blocked.

## 28. `EffectiveRisk` dependency

A43 explicitly depends on the unresolved A32 definition of `EffectiveRisk` or its canonical replacement.

Therefore:

```text
EffectiveRisk = UNKNOWN
```

until its source definition and every input semantic are resolved.

No mathematically plausible substitute is permitted.

## 29. Capacity and reservation

If risk is reserved before execution, reservation must have explicit:

```text
reservation_id
amount/measure
scope
creation_time
expiry/release condition
source authorization
```

The exact reservation quantity remains blocked by A32.

## 30. Authorization failure

Authorization must fail closed when required inputs are:

```text
missing
stale
invalid
ambiguous
unauthorized
out-of-order
```

No default risk value is invented.

## 31. Data race / stale authorization attack

Invalid:

```text
authorize at t0
risk state materially changes at t1
submit at t2
without revalidation
```

unless the authorization contract explicitly guarantees validity across that state change.

## 32. Duplicate order attack

Invalid:

```text
same accepted decision
same authorization
loop executes twice
-> two orders
```

Idempotency must prevent this.

## 33. Authorization scope attack

Invalid:

```text
authorization for instrument A
-> order for instrument B
```

Scope mismatch must fail closed.

## 34. Expired authorization attack

Invalid:

```text
authorization expires
-> delayed order submission
-> treated as authorized
```

## 35. Future-information attack

Eligibility and authorization may use only information causally available at their evaluation timestamp.

Future outcome, future price, or future account state cannot alter the historical authorization decision.

## 36. Risk-loss confusion attack

Invalid:

```text
realized loss
-> infer that historical authorization was invalid
```

Authorization validity is determined by information available when authorization was issued.

Later outcome may inform future policy learning, not historical authorization.

## 37. Position interaction

A43 governs new authorization/order creation.

It does not own existing-position protection.

That remains A36.

This prevents:

```text
risk authorization revoked
-> silently rewrite position state
```

## 38. Decision provenance

The final decision record must be traceable:

```text
FeatureSnapshot
 -> Prediction
 -> EconomicAssessment
 -> Eligibility
 -> RiskAssessment
 -> RiskAuthorization
 -> OrderIntent
```

Every node must retain version/provenance identifiers.

## 39. Parameter classes

### Frozen architecture

```text
state separation
explicit state machines
fail-closed unknown conditions
authorization scope
authorization expiry concept
revocation concept
revalidation requirement
order-intent idempotency
provenance
no retroactive authorization changes
```

### Learned/configurable

```text
risk limits
authorization duration
revalidation interval
sizing parameters
eligibility thresholds
```

only after their exact definitions and walk-forward validation.

### External UNKNOWN

```text
risk-accounting semantics
EffectiveRisk definition
account capacity
broker constraints
instrument constraints
```

## 40. Implementation gate

A43 can implement the state-machine framework without numerical risk logic.

Actual authorization cannot be implemented until:

```text
EffectiveRisk
risk limits
risk reservation semantics
sizing semantics
execution constraints
```

are defined.

## 41. Completion criterion

A43 becomes `RESOLVED` when every accepted decision can be reconstructed as:

```text
DecisionInput
 -> Eligibility
 -> RiskAssessment
 -> Authorization
 -> OrderIntent
```

with exact timestamps, scope, policy versions, preconditions, postconditions, and failure reasons.

## ARCHITECTURE STATUS

**FROZEN:** separate decision/eligibility/authorization/order states; fail-closed unknowns; authorization scope; expiry/revocation concepts; revalidation; idempotency; provenance; no retroactive authorization changes; separation from existing-position protection.

**UNRESOLVED:** EffectiveRisk; risk limits; reservation quantity; sizing; authorization duration; revalidation interval; exact eligibility conditions; execution constraints.

**BLOCKERS:** A32 EffectiveRisk/risk semantics; A35 execution semantics; account/instrument constraints.

**NEXT ARTIFACT:** A44 — Order Construction, Submission and Execution-Reconciliation State Machine.
