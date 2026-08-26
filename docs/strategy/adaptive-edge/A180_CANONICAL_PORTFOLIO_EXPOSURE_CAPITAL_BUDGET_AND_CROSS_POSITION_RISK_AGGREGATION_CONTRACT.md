# A180 — Canonical Portfolio Exposure, Capital Budget & Cross-Position Risk Aggregation Contract

## Status
CANONICAL

## Purpose
A180 defines the portfolio-level risk boundary above individual trade authorization. It prevents individually valid trades from collectively exceeding capital, exposure, concentration, correlation, liquidity, or operational risk limits.

## Canonical flow
```text
individual decision
    -> individual risk authorization
    -> portfolio context
    -> aggregate exposure
    -> capital budget
    -> cross-position constraints
    -> portfolio authorization
    -> execution intent
```

Portfolio authorization is independent of signal quality.

## Exposure domains
The portfolio layer may track, as applicable:
```text
notional exposure
premium exposure
margin requirement
maximum loss
open risk
realized loss
unrealized loss
liquidity exposure
concentration
underlying concentration
sector/category concentration where configured
correlated exposure
operational exposure
```

Exact numerical limits are not frozen here.

## Position aggregation
All active positions must be aggregated using canonical instrument identity and current canonical quantities. Stale or uncertain positions cannot be treated as zero exposure.

```text
UNKNOWN EXPOSURE != ZERO EXPOSURE
```

## Capital budget
The capital allocator must distinguish:
```text
available capital
reserved capital
committed capital
at-risk capital
realized P&L
unrealized P&L
withdrawable/settled capital where provider semantics require it
```

Exact broker balance semantics remain an external dependency.

## Cross-position risk
A new trade may be rejected even if its standalone risk is acceptable when aggregate exposure violates a portfolio constraint.

```text
standalone_safe
    !=
portfolio_safe
```

## Correlation
Where portfolio risk requires correlation, the correlation estimate must be point-in-time and versioned. Future returns cannot influence historical authorization.

The exact correlation estimator and thresholds are validation-dependent.

## Option exposure
Options must preserve contract-specific exposure semantics, including quantity/lot size, premium, underlying relationship, expiry, and defined-risk/undefined-risk characteristics where applicable.

## Liquidity aggregation
Portfolio liquidity must account for simultaneous exit assumptions where required. Individual order liquidity cannot automatically be summed as independent capacity when positions compete for the same market liquidity.

## Concentration
Concentration constraints may apply at multiple identity levels:
```text
instrument
underlying
strategy/horizon
portfolio
```
The hierarchy is configuration, not hard-coded numerical policy.

## Drawdown interaction
Portfolio authorization may consume canonical realized/unrealized accounting and drawdown state. It must not rewrite accounting or infer drawdown from unverified provider balances.

## Unknown state
If portfolio exposure, capital, or position state is materially unknown, new risk-increasing execution must fail closed unless an explicitly authorized emergency/recovery policy applies.

## Concurrency
Portfolio authorization must bind to a portfolio version. Concurrent authorizations cannot independently spend the same risk budget.

```text
portfolio_version_before
    -> authorize
    -> portfolio_version_after
```
A stale version is rejected and re-evaluated.

## Reservation semantics
Where capital or risk is reserved before execution, reservation must have:
```text
reservation_id
portfolio_version
quantity/exposure
creation_time
expiry/validity
owner lifecycle
release condition
```
Reservation is not realized exposure and cannot be counted twice.

## Partial fills
Reservations and exposure must reconcile to actual fills. Unfilled quantity must not remain permanently committed after its reservation expires or lifecycle terminates.

## Recovery
After restart, reconstruct portfolio exposure and active reservations from durable evidence and provider reconciliation. Never assume zero exposure because local process state is empty.

## Failure conditions
Reject/defer risk-increasing execution for:
```text
unknown active position
unknown material capital state
stale portfolio version
exceeded capital budget
exceeded exposure limit
exceeded concentration limit
insufficient liquidity evidence
invalid instrument identity
unreconciled emergency state
provider/accounting inconsistency
```

## Invariants
```text
INV-180-001 Aggregate exposure uses canonical position identity.
INV-180-002 Unknown exposure is never treated as zero.
INV-180-003 Standalone risk approval does not imply portfolio approval.
INV-180-004 Portfolio authorization is version-bound.
INV-180-005 Concurrent workers cannot spend the same risk budget twice.
INV-180-006 Reservations are distinct from realized exposure.
INV-180-007 Partial fills update exposure and reservations explicitly.
INV-180-008 Historical portfolio authorization is immutable.
INV-180-009 Future information cannot influence historical portfolio authorization.
INV-180-010 Recovery cannot assume flatness from missing process state.
INV-180-011 Emergency policies cannot silently become normal risk authorization.
```

## Parameter classes
### Frozen architecture
Portfolio boundary, exposure aggregation, unknown-state semantics, version-bound authorization, reservation separation, partial-fill handling, recovery, causal ordering.

### Configuration to validate
Capital budget hierarchy, concentration limits, liquidity policy, reservation expiry, drawdown gates, correlation policy, emergency override scope.

### Learned / validation-dependent
Correlation distributions, liquidity interaction models, portfolio risk estimates, empirical drawdown parameters.

## Adversarial tests
Two workers spending one budget; stale portfolio version; unknown position; duplicated position; partial fill; reservation leak; simultaneous exits; correlated positions; option lot mismatch; provider balance mismatch; restart with open exposure; emergency state plus new entry; future correlation data injected.

## Architecture Status
```text
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact Kite balance/margin semantics; exact settlement semantics; exact portfolio liquidity model.
CONFIGURATION TO VALIDATE: capital budgets, concentration, liquidity, reservation expiry, drawdown, correlation, emergency override.
LEARNED / VALIDATION-DEPENDENT: portfolio risk distributions and empirical correlation/liquidity parameters.
BLOCKERS: None for specification work. Production authorization remains blocked until provider/accounting semantics and empirical risk validation are verified.
NEXT ARTIFACT: A181 — Canonical Market Regime, Horizon Arbitration & Adaptive Horizon Transition Contract
```
