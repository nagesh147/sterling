# A134 — Canonical Decision, Eligibility & Risk Authorization State Machine

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

Define the temporal state-machine boundary between a candidate decision, eligibility, risk authorization, and permission to create an execution intent.

The artifact deliberately does not define broker execution, position protection, numerical risk parameters, or sizing mathematics.

## 1. State-domain separation

```text
DecisionState
EligibilityState
RiskAuthorizationState
IntentPermissionState
```

The following are distinct:

```text
ACCEPTED    != ELIGIBLE
ELIGIBLE    != AUTHORIZED
AUTHORIZED != ORDERED
ORDERED     != FILLED
FILLED      != POSITION
```

Probability, economic value, risk assessment, authorization, execution, and position protection are separate domains.

## 2. Decision state machine

```text
NOT_EVALUATED
      |
      v
  EVALUATING
    /     \
   v       v
ACCEPTED  REJECTED
   |
   +--> EXPIRED
   +--> SUPERSEDED
```

`ACCEPTED` means only that the decision policy accepted the candidate for further authorization evaluation. It does not mean an order exists.

## 3. Eligibility state machine

```text
UNKNOWN
   |
   v
EVALUATING
 /       \
v         v
ELIGIBLE  INELIGIBLE
   |
   +--> EXPIRED
   +--> INVALID
```

Eligibility may require, as applicable:

```text
causally valid snapshot
valid instrument/contract
tradable contract
valid probability output
valid economic assessment
valid session state
valid lifecycle state
acceptable data quality
```

Unknown, stale, invalid, ambiguous, missing, or causally unavailable required conditions fail closed.

## 4. Risk authorization state machine

```text
NOT_REQUESTED
      |
      v
   PENDING
    /   \
   v     v
AUTHORIZED DENIED
   |
   +--> EXPIRED
   +--> REVOKED
```

Authorization is a temporal permission, not a risk score.

An authorization records at minimum:

```text
authorization_id
decision_id
scope
instrument_id
side
sizing_reference
risk_policy_version
issued_at
expires_at
provenance
```

## 5. Sizing boundary

A134 does not invent order quantity.

If a required sizing result is unavailable:

```text
sizing unavailable
    -> authorization blocked
```

No default lot, default quantity, or arbitrary capital allocation is permitted.

The sizing model is owned by a separate risk/sizing contract.

## 6. Risk boundary

A134 consumes a versioned risk assessment where required:

```text
risk_assessment_id
risk_measure_version
risk_value
risk_limit_reference
risk_status
available_at
provenance
```

A134 does not define the numerical risk estimator or its thresholds.

If a mandatory risk input is unknown or unavailable, authorization fails closed unless an explicit policy proves that the input is not required for the specific action.

## 7. Authorization temporal validity

```text
issued_at <= current_time < expires_at
```

An expired authorization cannot be reused.

If a material dependency changes before execution, the authorization must be revalidated or revoked according to the applicable policy.

No fixed revalidation interval is assumed by architecture.

## 8. Internal idempotency

Repeated evaluation of the same logical decision must not create duplicate authorization records.

The authorization identity incorporates the canonical decision/action scope and relevant policy/version context.

Internal idempotency is distinct from broker idempotency.

```text
internal idempotency != broker idempotency
```

## 9. Permission consumption

```text
NOT_PERMITTED
      |
      v
  PERMITTED
      |
      v
   CONSUMED
```

A permission can be consumed once.

Consumption must be atomic with the transition into the execution-intent boundary. Failed intent creation must not silently consume a permission.

## 10. Forbidden transitions

```text
REJECTED   -> AUTHORIZED
INELIGIBLE -> AUTHORIZED
EXPIRED    -> AUTHORIZED
REVOKED    -> AUTHORIZED
DENIED     -> AUTHORIZED
CONSUMED   -> PERMITTED
```

A later evaluation creates new lineage rather than mutating historical authorization.

## 11. Causal transition invariant

For every transition at time `t`:

```text
available_at(input) <= t
```

Database insertion time, current-state time, or replay time cannot substitute for the information's actual causal availability time.

## 12. Position interaction

A material position/account state change can invalidate an authorization.

Example:

```text
AUTHORIZED
    |
material position/risk/account change
    |
    v
REVALIDATE or REVOKE
```

Historical authorization is never rewritten to reflect later state.

## 13. Emergency/protection boundary

Normal new exposure uses A134 authorization.

Existing-position protection and emergency flattening remain owned by the lifecycle/execution contracts.

```text
normal exposure -> A134 -> execution intent
protection      -> lifecycle -> execution
emergency       -> lifecycle -> emergency execution
```

Protection actions must not be forced through normal-entry authorization semantics.

## 14. Audit lineage

Every authorization must trace:

```text
decision_id
snapshot_id
probability_id
economic_assessment_id
risk_assessment_id
sizing_reference
policy_version
instrument_version
authorization_id
```

All referenced artifacts are immutable/versioned.

## 15. Hostile scenarios

### Duplicate workers

Same logical candidate must resolve to one internal authorization lineage through deterministic idempotency.

### Authorization expires during preparation

Execution-intent creation is blocked or reauthorization is required.

### Risk changes after authorization

Revalidation/revocation is required before normal exposure is created.

### Positive economic value but excessive risk

Authorization is denied. Positive EV does not override risk policy.

### Missing risk

Authorization is unavailable, not risk-free.

### Late market event

The late event cannot rewrite an already-created decision; it belongs to a later causal state.

### Broker fills after cancellation

Actual execution remains owned by A127. A134 does not fabricate execution state.

## 16. Frozen architecture

```text
separate decision/eligibility/authorization domains
explicit states and transitions
fail-closed required unknowns
authorization scope and expiry
revocation/revalidation
internal idempotency
single-use permission consumption
immutable historical lineage
causal transitions
risk/authorization separation
sizing boundary
account boundary
execution boundary
protection boundary
```

## 17. Non-frozen / validation-dependent

```text
risk estimator
risk limits
sizing model
authorization lifetime
revalidation policy
eligibility thresholds
risk acceptance thresholds
```

Numerical values must not be invented; they require historical/walk-forward validation or authoritative operational constraints as appropriate.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- decision/eligibility/risk-authorization separation
- explicit state machines
- transition guards
- forbidden transitions
- fail-closed unknowns
- authorization scope
- authorization expiry
- revocation/revalidation
- deterministic internal idempotency
- permission consumption semantics
- immutable decision history
- causal transitions
- risk/authorization separation
- sizing boundary
- account-state boundary
- execution boundary
- protection boundary
- complete lineage

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that block the state-machine architecture.

CONFIGURATION TO VALIDATE:
- authorization lifetime
- account-state freshness
- non-mandatory revalidation cadence
- quality acceptance policies

LEARNED / VALIDATION-DEPENDENT:
- risk estimator
- risk thresholds
- sizing model
- statistically derived authorization thresholds

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A135 — Canonical Order Construction, Submission, and Execution-Reconciliation Contract
```
