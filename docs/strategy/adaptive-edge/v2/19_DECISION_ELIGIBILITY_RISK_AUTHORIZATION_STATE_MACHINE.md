# Adaptive Edge V2 — Decision, Eligibility and Risk-Authorization State Machine

**Artifact:** A43  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

A43 defines the state-machine boundary between a candidate decision, eligibility evaluation, risk authorization, and executable order intent.

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

Prediction, eligibility, risk authorization, order intent, execution, and position are separate state domains.

## State domains

```text
DecisionState
EligibilityState
RiskAuthorizationState
OrderIntentState
```

Architectural states are explicit and independently versioned. `ACCEPTED` means only that the decision policy accepted the opportunity for further authorization evaluation; it does not mean an order was placed.

### Decision

```text
NOT_EVALUATED
EVALUATING
ACCEPTED
REJECTED
EXPIRED
SUPERSEDED
```

### Eligibility

```text
UNKNOWN
ELIGIBLE
INELIGIBLE
EXPIRED
INVALID
```

### Risk authorization

```text
NOT_REQUESTED
PENDING
AUTHORIZED
DENIED
EXPIRED
REVOKED
INVALID
```

### Order intent

```text
NOT_CREATED
CREATED
SUBMITTED
CANCEL_REQUESTED
CANCELLED
REJECTED
EXPIRED
```

A43 requires fail-closed handling for required conditions that are unknown, stale, invalid, ambiguous, missing, or causally unavailable.

Authorization is a temporal permission. It requires explicit scope, expiry, revocation, revalidation, policy version, and provenance. A risk estimate is not itself a risk authorization, and authorization is not position protection.

Repeated evaluation must not create duplicate order intents. A stable idempotency key is required for the decision/authorization pair.

The authorization layer cannot invent `EffectiveRisk`. That quantity remains blocked by the unresolved risk contract. Likewise, sizing, risk limits, reservation semantics, authorization duration, and execution constraints remain unresolved.

## Implementation gate

A43 permits implementation of the state-machine framework and transition guards without numerical risk logic. Actual authorization remains blocked until the required risk, sizing, account, instrument, and execution semantics are resolved.

## Status

**FROZEN:** separate state domains; fail-closed unknowns; authorization scope; expiry/revocation concepts; revalidation; idempotency; provenance; no retroactive authorization changes; separation from existing-position protection.

**UNRESOLVED:** EffectiveRisk; risk limits; reservation quantity; sizing; authorization duration; revalidation interval; exact eligibility conditions; execution constraints.

**NEXT ARTIFACT:** A44 — Order Construction, Submission and Execution-Reconciliation State Machine.
