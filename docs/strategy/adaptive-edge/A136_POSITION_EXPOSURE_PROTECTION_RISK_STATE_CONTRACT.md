# A136 — Canonical Position, Exposure, Protection & Risk-State Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

Define authoritative state for actual position, exposure, risk and protection after execution. A136 does not redefine A126 lifecycle semantics, A127 execution truth, A128 instrument identity, or A133 economic mathematics.

## 1. Domain separation

```text
ORDER INTENT != POSITION
POSITION    != EXPOSURE
EXPOSURE    != RISK
RISK        != PROTECTION
```

## 2. Position derivation

For instrument `i` at time `t`:

```text
Q_net(i,t) = sum(signed_fill_quantity(i))
```

using only confirmed fills causally available by `t`.

```text
BUY  = +
SELL = -
```

Submitted quantity or strategy intent is never position truth.

## 3. Position identity

```text
position_id
instrument_id
contract_version
account_scope
product_scope
```

Canonical A128 identity is mandatory. Provider symbols are never canonical position keys.

## 4. Position lifecycle

```text
FLAT
  |
  v
OPENING
  |
  v
OPEN
  +--> REDUCING
  +--> PROTECTED
  +--> EXITING
  |
  v
FLAT
```

Exceptional states:

```text
UNCERTAIN
RECONCILIATION_REQUIRED
EMERGENCY
```

A submitted exit does not make a position flat. Confirmed execution/reconciliation establishes zero exposure.

## 5. Partial fills

For requested quantity `Q`:

```text
filled_quantity = sum(q_i)
remaining_quantity = Q - filled_quantity
0 <= filled_quantity <= Q
```

Partial execution produces partial exposure.

## 6. Average entry and reversals

For a same-direction position:

```text
AverageEntry = sum(q_i * execution_price_i) / sum(q_i)
```

A reversal must be decomposed into closing quantity and new opening quantity. A single weighted-average calculation across zero crossing is forbidden.

## 7. Realized and unrealized economics

```text
RealizedPnL     = economics of confirmed closed quantity
UnrealizedPnL(t) = mark-to-market economics of remaining exposure
```

Realized economics use actual executions. Unrealized valuation requires a causally valid A129 market observation.

## 8. Exposure

Exposure is multidimensional and may include:

```text
directional exposure
notional exposure
instrument exposure
underlying exposure
option exposure
gross exposure
net exposure
```

No single generic notional formula is imposed where a risk-specific representation is required.

## 9. Risk state

Canonical semantic states:

```text
UNKNOWN
NORMAL
ELEVATED
BREACHED
EMERGENCY
```

These are states, not numerical thresholds. Unknown risk is never interpreted as zero risk.

## 10. Protection state

```text
UNPROTECTED
PROTECTION_PENDING
PROTECTED
PROTECTION_DEGRADED
PROTECTION_FAILED
EMERGENCY_PROTECTION
```

Protection is independent of thesis and entry authorization.

## 11. Thesis boundary

A136 consumes A126 thesis state. It does not redefine thesis transitions.

Thesis invalidity and economic profitability may coexist:

```text
THESIS_INVALID + PnL > 0
```

is valid state, subject to A126 lifecycle policy.

## 12. Protection lineage

Every protection state traces:

```text
protection_id
position_id
policy_version
trigger_definition
reference_snapshot_id
created_at
updated_at
status
```

If protection uses an order, lineage continues through A135.

## 13. Protection failure

If required protection cannot be established:

```text
PROTECTION_FAILED
```

The system does not invent a stop price or numerical response. A126 owns the lifecycle action policy.

## 14. Emergency state

Emergency state represents a condition in which normal optimization cannot safely continue. Examples include unreconciled exposure, protection failure, material account inconsistency, broker-state uncertainty, defined session-cutoff conditions, or critical data uncertainty.

Exact triggers remain owned by the relevant lifecycle/execution/risk policies.

## 15. Data uncertainty

Position/risk state distinguishes:

```text
KNOWN
STALE
DEGRADED
UNKNOWN
RECONCILIATION_REQUIRED
```

Conflicting local and broker position truth produces uncertainty/reconciliation, not an averaged or guessed value.

## 16. Market valuation

For valuation at time `t`:

```text
valuation_time <= t
available_at <= t
```

Current market data cannot be injected into historical risk state.

Executable price and valuation price remain distinct.

## 17. Option-specific exposure

Option state retains A128 identity:

```text
underlying
expiry
strike
option_type
contract_version
quantity
```

Greeks, IV and other derived quantities are observations/models with their own provenance; they are not immutable contract facts.

## 18. Session lifecycle

Position lifecycle consumes authoritative session state. A136 does not invent a cutoff value.

Session transition can cause lifecycle escalation through A126.

## 19. Reconciliation

Compare:

```text
internal fill-derived position
vs
broker position
```

and, where required:

```text
orders
trades
positions
```

Mismatch produces `RECONCILIATION_REQUIRED`. No silent averaging or inference is permitted.

## 20. Accounting invariant

For each instrument, subject to explicit contract/corporate-action transformations:

```text
OpeningPosition + sum(SignedFills) = CurrentPosition
```

Any unexplained violation is an accounting inconsistency.

## 21. Protection invariant

If lifecycle policy requires protection while a position is active, protection cannot silently be represented as absent without a recorded degradation/failure transition.

## 22. Forbidden states

Examples:

```text
submitted exit + position FLAT
without confirmed zero exposure

broker +100 + local FLAT
without reconciliation state

protection required + active normal lifecycle
with unrecorded protection failure
```

These are invalid state combinations.

## 23. Hostile scenarios

The architecture must survive:

```text
partial fill
reversal
exit race
broker disconnect
position mismatch
protection rejection
thesis invalidation while profitable
option expiry
stale valuation
conflicting position authorities
```

Required behavior is explicit uncertainty/escalation, never guessed state.

## 24. Frozen architecture

```text
execution-derived position truth
partial-fill accounting
position identity
reversal semantics
realized/unrealized separation
exposure/risk/protection separation
thesis/protection independence
risk uncertainty states
protection failure states
reconciliation semantics
causal valuation
option-risk provenance
session dependency
emergency state
immutable lineage
accounting invariants
```

## 25. Learned/configurable

Not frozen numerically:

```text
risk estimator
exposure model
option-risk model
protection distance
trailing/profit-lock parameters
risk thresholds
emergency thresholds
position-sizing model
```

These require walk-forward validation or authoritative operational constraints.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that block the position-state architecture.

CONFIGURATION TO VALIDATE:
- risk-state thresholds
- protection requirements
- protection degradation policy
- reconciliation cadence
- valuation-source acceptance
- session-transition policy

LEARNED / VALIDATION-DEPENDENT:
- risk estimator
- exposure model
- option-risk model
- protection distance
- trailing/profit-lock parameters
- emergency thresholds
- sizing model

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A137 — Canonical Exit, Protection-Action & Position-Reduction Decision Contract
```
