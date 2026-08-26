# A181 — Canonical Market Regime, Horizon Arbitration & Adaptive Horizon Transition Contract

## Status
CANONICAL

## Purpose
Defines the state-machine semantics for Adaptive Edge's five trading horizons and their evidence-based promotion/downgrade without freezing arbitrary numerical thresholds.

## Horizons
```text
IMPULSE
TACTICAL
INTRADAY_SWING
SESSION_TREND
SESSION_EXTENSION
```
These are semantic operating regimes, not fixed clock buckets. Exact duration distributions remain empirical.

## Horizon identity
Every position and decision has:
```text
initial_horizon
current_horizon
horizon_version
horizon_state_entered_at
horizon_evidence_snapshot
promotion_count
downgrade_count
```
Initial horizon is historical context. Current horizon is the current state.

## State transition
```text
CURRENT_HORIZON + NEW_EVIDENCE
        -> TRANSITION_POLICY
        -> NEW_HORIZON
```
Promotion and downgrade require evidence available at the transition time. Future outcome information cannot trigger a historical transition.

## Promotion
Promotion means the observed trade thesis and market behavior support a longer-lived operating horizon. Promotion is not synonymous with profit.

## Downgrade
Downgrade means evidence indicates the original horizon is no longer supported. Downgrade may occur without thesis invalidation and must not be interpreted as automatic exit.

## Horizon vs thesis
```text
horizon_state != thesis_state
```
A horizon transition does not itself establish thesis validity or invalidity.

## Horizon vs protection
```text
horizon_state != protection_state
```
Protection remains independently governed by A177.

## Horizon vs execution
A horizon transition does not directly submit, cancel, or replace an order. It can only produce a new lifecycle policy state through the canonical decision/risk path.

## Evidence
Transition evidence may include only canonical observations and derived features whose `available_at` is not later than the transition timestamp.

## Stability
The transition system must avoid oscillation caused by duplicate or contradictory evidence. The exact hysteresis/confirmation policy is configuration and validation-dependent.

## Concurrent evidence
Events arriving concurrently must be ordered by the canonical causal/event-order contract. Arrival order alone is not semantic truth when event-time ordering is available and valid.

## Missing evidence
Missing evidence is not evidence for promotion or downgrade. The state remains unchanged or enters an explicit uncertainty/degraded state where the runtime contract requires it.

## Position lifecycle
Horizon state survives restart through durable evidence. Recovery cannot reconstruct a different horizon merely because newer information is available after the historical transition point.

## Session lifecycle
Session close, emergency flatten, and mandatory lifecycle authorities override horizon preference. A horizon cannot extend a position beyond a mandatory lifecycle boundary.

## Numerical policy
The following remain UNFROZEN:
```text
promotion thresholds
downgrade thresholds
minimum confirmation evidence
horizon duration distributions
hysteresis
transition sensitivity
regime-specific risk budgets
```
These must be established through walk-forward validation and must not be selected for convenience.

## Failure conditions
Fail closed or preserve the existing horizon when:
```text
causal evidence invalid
state identity unavailable
configuration invalid
instrument invalid
transition version unavailable
required evidence stale beyond policy
conflicting lifecycle authority
```

## Invariants
```text
INV-181-001 initial_horizon is immutable historical context
INV-181-002 current_horizon is mutable only through the transition contract
INV-181-003 horizon transitions use only causally available evidence
INV-181-004 missing evidence cannot imply promotion or downgrade
INV-181-005 horizon state does not equal thesis state
INV-181-006 horizon state does not equal protection state
INV-181-007 horizon transition cannot directly submit an order
INV-181-008 mandatory lifecycle authority overrides horizon preference
INV-181-009 recovery preserves historical horizon transitions
INV-181-010 numerical transition parameters remain validation-dependent
```

## Adversarial tests
```text
future outcome injected into promotion
future high/low injected into downgrade
rapid alternating evidence
duplicate transition event
out-of-order events
restart after promotion
restart after downgrade
missing transition evidence
stale configuration
session cutoff conflict
emergency-exit conflict
thesis invalidation during transition
partial fill during transition
```

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: empirical horizon distributions, provider-specific evidence availability, final transition persistence mechanism.
CONFIGURATION TO VALIDATE: transition confirmation, hysteresis, evidence freshness, regime-specific policy.
LEARNED / VALIDATION-DEPENDENT: promotion/downgrade thresholds, duration distributions, sensitivity.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A182 — Canonical Data Quality, Staleness, Missingness & Degradation Contract
