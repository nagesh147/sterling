# Adaptive Edge V2 — Risk Authorization Definition

**Version:** 2.0.0-draft  
**Artifact:** A31  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Depends on:** A25, A30  
**Implementation authorization:** NONE

## 1. Purpose

A31 defines the meaning and lifecycle of `AuthorizedRisk` without inventing a risk-per-unit formula or position-sizing formula.

The purpose is to establish the boundary:

```text
Eligibility
    |
    v
Risk Policy
    |
    v
Risk Authorization
    |
    v
Position Sizing
```

Risk authorization is explicit state. It is not a synonym for prediction, economic value, position quantity, stop distance, premium, or realized loss.

## 2. Core definition

For a decision `d` at time `t_d`, define:

```text
AuthorizedRisk(d, t_d)
```

as the maximum strategy-defined risk exposure that the risk policy explicitly permits for that decision under the applicable strategy and risk-policy versions.

This definition establishes authorization, not the mathematical measurement of economic loss.

The exact unit and risk-measure semantics remain unresolved until the risk-measure artifact is defined.

## 3. Separation of concepts

The following are distinct:

```text
ExpectedNetValue
Prediction
AuthorizedRisk
RiskPerUnit
Quantity
GrossRisk
EffectiveRisk
RealizedLoss
```

No equality between them may be inferred from naming similarity.

In particular, the following are NOT canonical V2 equations:

```text
AuthorizedRisk = ExpectedNetValue
AuthorizedRisk = PredictionScore
AuthorizedRisk = Premium
AuthorizedRisk = StopDistance
AuthorizedRisk = RiskPerUnit * Quantity
AuthorizedRisk = RealizedLoss
```

unless a later authoritative V2 artifact explicitly establishes the relationship.

## 4. Authorization object

```text
RiskAuthorization
{
    authorization_id
    opportunity_id
    strategy_version
    risk_policy_version
    authorization_time
    effective_time
    authorized_risk
    unit
    state
    expiry_or_validity
    reason_codes
    provenance
}
```

The record is immutable once issued. Any later change creates a new authorization/revocation event rather than mutating historical state.

## 5. Authorization states

Architectural state vocabulary:

```text
UNAUTHORIZED
AUTHORIZED
REVOKED
EXPIRED
SUPERSEDED
```

`AUTHORIZED` means permission exists. It does not mean a position exists or that any quantity has yet been calculated.

## 6. Grant transition

A grant may occur only when the risk policy's preconditions are satisfied.

Conceptually:

```text
Eligibility
    +
RiskPolicyState
    +
RequiredRiskInputs
        |
        v
RiskAuthorization
```

The exact preconditions are unresolved.

A risk authorization cannot be created solely because `Eligibility = ELIGIBLE` unless the risk policy explicitly says so.

## 7. Revocation

An authorization may be revoked only through an explicit policy-defined event.

Architectural event classes include:

```text
POLICY_REVOCATION
DATA_INVALIDATION
STRATEGY_DISABLE
AUTHORIZATION_EXPIRY
OPPORTUNITY_INVALIDATION
MANUAL_RISK_LOCK
SYSTEM_SAFETY_LOCK
```

Exact semantics remain later policy dependencies.

Revocation does not itself imply liquidation of an existing position. Position-management semantics are downstream.

## 8. Expiry

An authorization may have an explicit validity interval:

```text
[t_authorized, t_expiry)
```

If no validity interval is defined, the authorization must not be treated as indefinitely valid by assumption.

The exact validity policy remains unresolved.

## 9. Supersession

A new authorization may supersede an earlier authorization for the same opportunity only through an explicit versioned policy event.

Historical authorizations remain immutable.

## 10. Causal boundary

The risk authorization decision at `t_d` may use only information available at `t_d`.

Forbidden contemporaneous inputs include:

```text
future fill
future exit
future realized loss
future label
future P&L
```

A later loss may affect a future risk-policy state only through a separately defined state transition.

## 11. P&L independence

Risk authorization is not automatically recalculated from realized P&L.

The following inference is forbidden:

```text
loss = X
-> authorized risk = previous risk - X
```

unless an explicit risk-consumption policy defines it.

Likewise:

```text
profit = X
-> authorized risk increases
```

is forbidden without an explicit policy transition.

## 12. Dynamic mode independence

A30 establishes:

```text
OperatingMode != RiskAuthorization
```

A31 therefore requires any mode-to-risk relationship to be represented as an explicit versioned risk-policy function:

```text
RiskPolicy(ModeState, RiskInputs, PolicyVersion)
    -> RiskAuthorization
```

The function is not defined numerically here.

## 13. Risk budget versus risk measure

This distinction is central.

```text
AuthorizedRisk
```

is a **budget/permission**.

```text
RiskPerUnit / EffectiveRisk / GrossRisk
```

are candidate **measurements** of exposure.

Position sizing requires both, but their semantics must be defined independently.

Therefore the architectural dependency is:

```text
AuthorizedRisk
       +
ResolvedRiskMeasure
       +
ContractConstraints
       |
       v
PositionSizing
```

## 14. Unit requirement

`AuthorizedRisk` must eventually have a dimensionally explicit unit.

Examples of possible units are not choices:

```text
currency
currency per opportunity
currency per position
percentage of capital
risk units
```

The actual V2 unit remains UNKNOWN.

A quantity with incompatible units cannot be compared directly to `AuthorizedRisk`.

## 15. Capital is separate

The following are distinct constraints:

```text
CapitalAvailable
AuthorizedRisk
```

Capital availability answers whether the account can fund the position.

Risk authorization answers whether the strategy permits the exposure.

A position must satisfy both where both are applicable.

Neither may silently substitute for the other.

## 16. Account-level versus opportunity-level authorization

The architecture distinguishes:

```text
AccountRiskState
OpportunityRiskAuthorization
```

An account-level state may constrain opportunity-level authorization, but the exact allocation rule is unresolved.

No assumption such as:

```text
Every opportunity receives the full account risk budget
```

is permitted.

## 17. Multiple opportunities

A31 does not define portfolio allocation.

If multiple opportunities coexist, the later multi-position artifact must define whether authorizations are:

```text
independent
shared
capped
prioritized
netted
```

Until then, no hidden aggregation rule may be implemented.

## 18. Authorization cannot create quantity

The following is intentionally incomplete:

```text
Q = floor(AuthorizedRisk / RiskPerUnit)
```

The arithmetic may be valid, but the semantics of `RiskPerUnit` and quantity constraints are not yet resolved.

Therefore A31 authorizes a budget but does not authorize a quantity.

## 19. EffectiveRisk relationship

The previously unresolved variables remain distinct:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
AuthorizedRisk
```

A31 explicitly does not define:

```text
EffectiveRisk_i = GrossRisk
EffectiveRisk_i = RiskPerUnit * Q
EffectiveRiskPerUnit = Entry - Stop
```

Those relationships require a later risk-measure specification.

## 20. Stop-loss independence

A stop instruction may eventually constrain realized loss or risk, but the existence of a stop does not itself define the risk budget.

Therefore:

```text
StopDistance -> AuthorizedRisk
```

is not a V2 rule at A31.

## 21. Premium independence

For an option purchase, premium paid may be an economic quantity, but it is not automatically the V2 risk measure.

Therefore:

```text
AuthorizedRisk = PremiumPaid
```

remains UNKNOWN unless explicitly defined later.

## 22. Risk-policy inputs

A complete risk-policy definition must eventually identify:

```text
input source
input semantics
unit
availability time
state dependence
version
failure behavior
```

Possible inputs must not be invented before their semantics are established.

## 23. Fail-closed behavior

Risk authorization must not be granted when required inputs are:

```text
missing
stale
invalid
ambiguous
out-of-order
unauthorized-version
```

unless a documented risk policy explicitly defines a safe fallback.

A missing risk measure must never silently become zero risk.

## 24. Determinism

Given identical:

```text
risk inputs
risk state
policy version
opportunity identity
```

the authorization decision must be deterministic.

Replaying the same causal event stream must reproduce the same authorization state sequence.

## 25. Authorization accounting

The architecture permits a later risk-consumption ledger:

```text
Authorization
    -> Reservation
    -> Consumption
    -> Release / Expiry
```

But A31 does not yet define those quantities mathematically.

In particular, `AuthorizedRisk` must not be confused with `ConsumedRisk`.

## 26. Adversarial scenario — high edge

```text
Prediction = strong
ExpectedNetValue = strong
```

This does not by itself produce a larger risk authorization.

The risk policy must explicitly permit that mapping.

## 27. Adversarial scenario — large capital

```text
CapitalAvailable = large
```

does not imply:

```text
AuthorizedRisk = large
```

Capital and risk policy remain separate.

## 28. Adversarial scenario — small risk budget

If the smallest executable position would exceed the authorized risk budget, the downstream sizing stage must be able to produce no executable quantity rather than exceeding authorization.

A31 does not define the quantity rounding rule.

## 29. Adversarial scenario — stale risk state

If the risk policy state is stale at decision time, authorization must fail closed unless the policy explicitly defines an allowed validity window.

## 30. Adversarial scenario — authorization changes before execution

If authorization changes after issuance but before order submission, the execution artifact must define whether the original authorization remains valid, is revalidated, or is rejected.

A31 records this as a required downstream contract.

## 31. Learning and risk authorization

If any risk-policy parameter is learned, its promotion must follow the V2 learning protocol.

The parameter cannot be updated based on future observations while earlier decisions are being replayed.

A risk-policy update is a semantic strategy change and requires versioning.

## 32. Versioning

Every authorization identifies:

```text
strategy_version
risk_policy_version
```

Changing the meaning, formula, inputs, or transition behavior of risk authorization requires a new risk-policy version.

## 33. Completion criterion

A31 becomes fully RESOLVED only when:

```text
AuthorizedRisk unit is defined
risk budget semantics are defined
risk-policy inputs are defined
grant conditions are defined
revocation conditions are defined
validity/expiry semantics are defined
account/opportunity interaction is defined
risk-consumption semantics are defined
all required input timestamps are defined
all relationships to RiskPerUnit/EffectiveRisk are explicitly defined
```

and the resulting specification survives dimensional, causal, execution, accounting, and adversarial review.

## ARCHITECTURE STATUS

Frozen:

```text
AuthorizedRisk is explicit state
RiskAuthorization != Prediction
RiskAuthorization != ExpectedNetValue
RiskAuthorization != Quantity
RiskAuthorization != RealizedLoss
OperatingMode != RiskAuthorization
Capital != RiskAuthorization
authorization lifecycle is versioned
fail-closed principle
historical authorization immutability
```

## UNRESOLVED

```text
AuthorizedRisk unit
risk-budget source
risk-policy inputs
risk-budget numerical rule
authorization validity window
revocation semantics
consumption semantics
account-to-opportunity allocation
EffectiveRisk relationship
RiskPerUnit relationship
```

## BLOCKERS

A31 architecture is complete.

Production risk authorization remains blocked because the actual risk-measure semantics and numerical policy have not yet been defined. This is intentional.

## NEXT ARTIFACT

**A32 — Risk Measure / EffectiveRisk Definition**

A32 must attempt to resolve the exact semantic meaning of `EffectiveRisk_i`, `EffectiveRiskPerUnit`, `RiskPerUnit`, and `GrossRisk`, including units, required inputs, stop/protection dependence, execution dependence, and causal availability. If no complete definition can be justified, the artifact must remain explicitly blocked rather than inventing one.
