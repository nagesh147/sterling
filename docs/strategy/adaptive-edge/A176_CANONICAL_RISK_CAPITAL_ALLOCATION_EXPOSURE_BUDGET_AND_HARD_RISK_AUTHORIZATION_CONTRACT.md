# A176 — Canonical Risk Capital Allocation, Exposure Budget & Hard-Risk Authorization Contract

**Status:** CANONICAL  
**Authority:** Risk-capital and exposure authorization boundary  
**Scope:** Adaptive Edge  
**Dependencies:** A153–A175

## 1. Purpose

A176 defines how economic opportunity becomes a bounded exposure authorization. It separates economic attractiveness from the amount of capital/exposure the system is permitted to assume.

```text
probability + economics
        |
        v
risk assessment
        |
        v
capital/exposure budget
        |
        v
hard-risk authorization
        |
        v
execution intent
```

A176 does not select numerical risk limits, stop distances, or position-sizing coefficients. Those remain validation/configuration dependent.

## 2. Risk domains

The risk engine must distinguish:

```text
account capital
available capital
committed capital
open exposure
pending exposure
maximum permitted exposure
risk-at-entry
worst-case/defined loss
portfolio concentration
instrument/liquidity risk
execution uncertainty
```

These are not interchangeable quantities.

## 3. Risk authorization identity

Every consequential authorization must preserve:

```text
risk_authorization_id
decision_id
position_context_id
instrument_identity
side
requested_quantity
approved_quantity
risk_measure
risk_budget_reference
capital_snapshot_reference
portfolio_snapshot_reference
policy_version
configuration_version
created_at
valid_from
valid_until
status
```

## 4. Hard gate

Execution is permitted only when the requested exposure satisfies all applicable hard constraints.

Conceptually:

```text
requested_exposure <= authorized_exposure
```

and:

```text
risk_authorization.status == VALID
```

A failed hard constraint cannot be overridden by a high probability or high expected economic value.

## 5. Capital snapshot

Capital-dependent authorization must reference a point-in-time capital/account snapshot.

Later deposits, withdrawals, realized P&L, or broker updates cannot retroactively change an earlier authorization.

## 6. Exposure accounting

Exposure must account for existing and pending lifecycle commitments where the contract requires them.

At minimum, the risk layer must be able to distinguish:

```text
current_position
pending_orders
new_requested_exposure
protected_exposure
unprotected_exposure
```

## 7. Position sizing

Position sizing is a policy function:

```text
approved_quantity = f(
    capital,
    risk_budget,
    defined_loss,
    liquidity,
    instrument_contract,
    existing_exposure,
    portfolio_constraints,
    configuration
)
```

The function structure is frozen; numerical parameters remain UNFROZEN.

## 8. Defined loss

A risk authorization must reference an explicit loss definition appropriate to the instrument and lifecycle.

For an option buyer, premium paid is not automatically equivalent to the canonical risk measure in every lifecycle state; the risk definition must be explicit.

No arbitrary stop-loss number may be used merely to manufacture a defined loss.

## 9. Hard-risk stop

A hard-risk condition is a non-optional exposure boundary.

When triggered:

```text
normal_new_exposure = BLOCKED
```

and the applicable protection/emergency lifecycle takes authority according to the frozen lifecycle contract.

## 10. Risk versus protection

Risk authorization answers:

```text
May this exposure be assumed?
```

Protection answers:

```text
How is existing exposure controlled?
```

They remain separate state machines.

## 11. Concentration

The risk layer must support concentration constraints across dimensions relevant to the strategy, such as:

```text
instrument
underlying
option family
expiry
direction
correlated exposure
session/horizon
```

Exact concentration metrics and thresholds are validation/configuration dependent.

## 12. Liquidity-aware risk

A nominal quantity is not automatically executable exposure.

Where required, risk authorization must account for:

```text
available liquidity
spread
expected slippage
market depth
execution uncertainty
```

If the required liquidity evidence is unavailable, the policy may reject or reduce authorization; it must not invent liquidity.

## 13. Pending-order risk

Pending orders can create future exposure.

The risk layer must not authorize multiple orders independently when their combined eventual exposure would violate a hard limit.

## 14. Partial fills

Risk authorization must tolerate:

```text
approved = 100
filled = 40
remaining = 60
```

Actual risk exposure is derived from accepted fills, while remaining authorization is bounded by lifecycle state.

A partial fill cannot silently reset the risk budget.

## 15. Repeated decisions

Repeated signals for the same position context must not bypass aggregate exposure limits.

A new authorization must evaluate the current authoritative exposure state, not a stale pre-trade snapshot.

## 16. Authorization expiry

Risk authorization is time-bounded where execution conditions can change materially.

```text
valid_until < execution_time
    -> authorization invalid
```

The system must not execute using an expired authorization merely because the underlying decision remains valid.

## 17. Configuration boundary

Risk configuration is versioned.

Changing:

```text
risk budget
position-size policy
concentration limit
hard-loss limit
emergency threshold
```

creates a new configuration identity.

Historical authorizations remain bound to their original version.

## 18. Learned quantities

The following may ultimately be learned/validated but are not frozen by A176:

```text
loss-distribution parameters
slippage distribution
fill probability
liquidity-response model
risk-of-ruin parameters
portfolio correlation estimates
regime-conditioned risk parameters
```

Learned quantities require A159 lineage and promotion controls.

## 19. No future information

For authorization time `t`:

```text
available_at(all risk inputs) <= t
```

Future fills, later P&L, later volatility, later liquidity, or later broker state cannot influence the historical authorization.

## 20. Failure behavior

Authorization must fail closed for safety-critical conditions including:

```text
unknown capital
unknown current exposure
unknown pending exposure
invalid instrument
invalid contract
expired authorization
invalid probability/economics
missing required risk input
stale critical data
risk-budget inconsistency
concurrency conflict
configuration mismatch
```

The appropriate operational policy may block, defer, reduce, or enter emergency handling. It must not silently assume zero exposure or zero risk.

## 21. Concurrency

Risk authorization must prevent two concurrent decisions from independently consuming the same remaining risk budget.

Conceptually:

```text
read budget/version
validate exposure
commit authorization
advance version
```

Conflicting versions require rejection/retry according to policy.

## 22. Emergency authority

Emergency flattening and normal risk authorization are distinct authorities.

A normal risk budget must not prevent a separately authorized emergency action whose purpose is to reduce existing exposure.

Emergency actions remain auditable and reconciled.

## 23. Accounting invariant

For each instrument/position context:

```text
position_after
    = position_before
    + accepted_signed_fills
```

Risk exposure must derive from authoritative position/fill state rather than requested orders alone.

## 24. Hostile scenarios

The implementation must test:

```text
zero capital
negative capital
unknown capital
duplicate authorization
concurrent authorizations
stale position
unknown pending order
partial fill
fill after authorization expiry
configuration version mismatch
wrong instrument identity
wrong lot size
liquidity collapse
slippage shock
hard-risk trigger during submission
broker/local exposure mismatch
restart before authorization persistence
```

## 25. Invariants

```text
INV-176-001  Economic attractiveness cannot bypass hard risk limits.
INV-176-002  Risk authorization is explicitly identified and versioned.
INV-176-003  Historical authorization is immutable.
INV-176-004  Capital and exposure snapshots are point-in-time evidence.
INV-176-005  Pending exposure is not ignored when relevant to hard limits.
INV-176-006  Partial fills cannot reset consumed risk budget.
INV-176-007  Expired authorization cannot authorize new exposure.
INV-176-008  Concurrent authorizations cannot double-consume one risk budget.
INV-176-009  Unknown critical risk inputs cannot silently become zero.
INV-176-010  Emergency exposure reduction is distinct from new-exposure authorization.
INV-176-011  Risk exposure is ultimately reconciled to authoritative fill/position evidence.
INV-176-012  No future information influences historical risk authorization.

## 26. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- risk/economics separation
- capital/exposure distinction
- point-in-time authorization
- hard-risk gate
- explicit authorization identity
- pending-exposure treatment
- partial-fill semantics
- authorization expiry
- configuration/version binding
- concurrency protection
- emergency-authority separation
- fill/position-based exposure accounting
- fail-closed critical-input behavior

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact capital-source semantics
- exact broker-account adjustment semantics
- exact portfolio exposure aggregation model
- exact risk registry implementation
- exact concurrency technology

CONFIGURATION TO VALIDATE:
- risk budgets
- concentration limits
- authorization TTL
- hard-loss limits
- pending-order treatment
- liquidity limits
- emergency authority scope

LEARNED / VALIDATION-DEPENDENT:
- loss distributions
- slippage/fill models
- liquidity response
- correlation estimates
- regime-conditioned risk parameters
- numerical position-sizing coefficients

BLOCKERS:
None for specification.
Real-money authorization remains blocked until numerical risk policy is validated and broker/account semantics are empirically verified.

NEXT ARTIFACT:
A177 — Canonical Protection, Stop/Trail, Profit-Lock & Exit-Authority Contract
```
