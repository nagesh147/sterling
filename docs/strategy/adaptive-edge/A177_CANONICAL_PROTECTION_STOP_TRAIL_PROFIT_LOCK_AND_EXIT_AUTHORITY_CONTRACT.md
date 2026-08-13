# A177 — Canonical Protection, Stop/Trail, Profit-Lock & Exit-Authority Contract

## Status
CANONICAL

## Purpose
Defines independent exit authorities and protection state without freezing numerical stop, trail, profit-lock, or target parameters.

## Authority separation
```text
THESIS INVALIDATION
HARD RISK
MANDATORY LIFECYCLE
PROTECTIVE STOP
TRAILING PROTECTION
PROFIT LOCK
ECONOMIC EXIT
SESSION CLOSE
EMERGENCY EXIT
```
Each authority has distinct trigger semantics, precedence, audit reason, and lifecycle effect.

```text
trigger != exit order != fill != position closure
requested protection != effective protection
unrealized profit != realized profit
future extrema != historical trailing state
```

## Protection state
A position protection snapshot must contain:
```text
position_id
instrument_identity
protection_version
reference_state
stop_reference
trail_reference
profit_lock_reference
authority
created_at
available_at
causal_cutoff
policy_version
configuration_version
```
Protection state is immutable historically; a newer version supersedes it without rewriting history.

## Causal trailing
For decision time `t`, trailing state may consume only extrema and observations with:
```text
available_at <= t
```
Future extrema cannot alter a historical protection decision.

## Effective protection
The effective protection boundary is the result of the applicable authority and current lifecycle state. It must never be inferred from display-only values.

## Partial fills
Protection quantity must reflect the actual protected position, not merely the originally requested quantity. Partial fills create explicit protection updates.

## Exit precedence
Hard-risk and mandatory lifecycle authorities cannot be weakened by economic or strategy preference. Exact numerical precedence and policy parameters remain configurable only within the frozen authority hierarchy.

## Exit/re-entry separation
An exit creates no implicit re-entry authorization. Re-entry requires a new causal observation, signal, eligibility, decision, risk authorization, and execution intent under A178.

## Emergency exit
Emergency execution may bypass ordinary optimization but cannot bypass identity, audit, reconciliation, or causal evidence requirements.

## Session cutoff
The lifecycle contract preserves the canonical pre-close cutoff and emergency flattening policy from A126. Numerical timing remains a validated configuration, not a learned value.

## Failure conditions
Fail closed or escalate when:
- protected position identity is unknown
- effective quantity is unknown
- protection state is stale beyond policy
- provider acknowledgement is ambiguous
- position reconciliation conflicts with local state
- required price/execution semantics are unavailable
- causal ordering is violated

## Invariants
```text
INV-177-001 exit authorities remain distinct
INV-177-002 hard risk cannot be weakened by strategy preference
INV-177-003 historical protection state is immutable
INV-177-004 future observations cannot modify historical trailing decisions
INV-177-005 requested protection is not assumed effective protection
INV-177-006 partial fills produce proportional/explicit protection state
INV-177-007 exit cannot implicitly authorize re-entry
INV-177-008 realized P&L cannot rewrite historical unrealized estimates
INV-177-009 emergency execution remains auditable and reconcilable
INV-177-010 protection applies only to the canonical position identity
```

## Parameter classes
### Frozen
Authority separation, causal ordering, immutable protection history, partial-fill semantics, exit/re-entry separation, auditability.

### Configuration to validate
Stop/trail/profit-lock policy, cutoff timing, protection update cadence, stale-state policy, emergency authority scope.

### Learned / validation-dependent
Stop distance, trailing distance, profit-lock thresholds, volatility-conditioned protection, horizon-conditioned protection.

## Adversarial tests
Future high/low injection; partial fill; cancel/fill race; stale protection; position reversal; duplicate exit; emergency exit during broker uncertainty; session cutoff race; restart during active protection; realized-fill overwrite of historical protection.

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact provider order semantics, exact executable-price semantics, empirical protection distributions.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A178 — Canonical Decision Eligibility, Signal Arbitration & Trade Lifecycle Entry Contract
