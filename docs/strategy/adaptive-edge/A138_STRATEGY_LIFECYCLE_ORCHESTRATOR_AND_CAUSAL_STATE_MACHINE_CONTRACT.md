# A138 — Canonical Strategy Lifecycle Orchestrator & Causal State-Machine Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

Define the orchestration boundary connecting canonical events, state reconstruction, snapshots, features, probability, economics, authorization, position lifecycle, protection/exit actions, execution, fills, reconciliation, and future learning without transferring ownership of domain semantics to the orchestrator.

## 1. First principle

A138 owns:

```text
sequence
causality
state transition coordination
dependency resolution
event dispatch
idempotency
recovery
```

It does not own feature formulas, probability estimation, economic calculations, risk formulas, exit thresholds, order pricing, or broker semantics.

## 2. Causal processing model

```text
CanonicalEvent
      |
      v
Temporal Gate
      |
      v
State Reconstruction
      |
      v
Immutable Snapshot
      |
      v
Features
      |
      v
Probability
      |
      v
Economics
      |
      v
Decision / Eligibility / Authorization
      |
      v
Position / Protection / Exit Action
      |
      v
Execution Intent
      |
      v
Execution Evidence
      |
      v
Position Reconciliation
```

Every transition consumes only information causally available at its transition time.

## 3. Causal invariant

For every input `d` consumed by a transition at time `t`:

```text
available_at(d) <= t
```

Receipt order, database insertion order, or replay order cannot substitute for information availability.

## 4. Temporal state

States are versioned immutable snapshots/lineages:

```text
S0 -> E1 -> S1 -> E2 -> S2
```

A correction produces a new lineage. Historical decisions are never mutated.

## 5. Domain ownership

```text
A126 -> lifecycle semantics
A127 -> execution truth
A128 -> contract identity
A129 -> market data integrity
A130 -> snapshot semantics
A131 -> feature mathematics
A132 -> probability
A133 -> economics
A134 -> authorization
A135 -> order/fill/reconciliation
A136 -> position/risk/protection
A137 -> exit/protection actions
A138 -> coordination only
```

No artifact may become an alternate owner of another domain.

## 6. Canonical evaluation cycle

```text
1. receive canonical event
2. validate identity
3. validate temporal eligibility
4. reconstruct applicable state
5. create immutable snapshot
6. evaluate dependent features
7. evaluate probability
8. evaluate economics
9. evaluate decision eligibility
10. evaluate risk authorization
11. evaluate position lifecycle
12. evaluate protection/exit actions
13. create execution intent where authorized
14. dispatch through execution boundary
15. consume execution evidence asynchronously
16. reconcile resulting position
17. persist resulting state lineage
```

No step may consume information that is causally later than its evaluation time.

## 7. Execution is asynchronous

```text
order intent != broker acceptance
broker acceptance != fill
fill != position
```

Execution evidence returns to the orchestrator as new canonical events.

## 8. Semantic atomicity

Domain transitions that must appear as one logical operation are atomically committed from the canonical state perspective. The physical transaction mechanism is implementation-dependent, but partial semantic commits are forbidden.

## 9. Event idempotency

Duplicate delivery of the same canonical event must not create duplicate state transitions, authorizations, or execution intents.

Conceptually:

```text
process(event_id) + process(event_id)
    = one logical event effect
```

unless the owning domain explicitly defines an independently repeatable action.

## 10. Out-of-order and late events

Events have distinct:

```text
event_time
available_at
receipt_time
processing_time
```

Receipt order is not causal order.

Late events may be classified as:

```text
ON_TIME
LATE_BUT_USABLE
LATE_AND_NON_REPLAYABLE
INVALID
```

The numerical lateness policy is configuration, not architecture.

A late event never silently rewrites a previously issued decision.

## 11. Replay

Historical replay must resolve:

```text
event versions
instrument versions
feature/formula versions
model versions
configuration versions
state-transition versions
```

Same causal inputs and versions must produce the same state trajectory, subject only to explicitly declared nondeterministic external dependencies.

## 12. Live/replay parity

The semantic contracts are identical across:

```text
LIVE
REPLAY
BACKTEST
SIMULATION
```

Only event-source and execution-environment adapters may differ.

## 13. Failure taxonomy

```text
DOMAIN_REJECTION
DATA_INVALID
CAUSALITY_VIOLATION
DEPENDENCY_UNAVAILABLE
EXECUTION_UNCERTAIN
RECONCILIATION_REQUIRED
INTERNAL_FAILURE
```

Failure categories must not be silently collapsed. For example, execution uncertainty is not automatically a broker rejection.

## 14. Fail-closed policy

For normal new exposure:

```text
unknown critical state -> NO_NEW_EXPOSURE
```

Protection and emergency actions follow their separate lifecycle paths and must not be disabled merely because normal decision evaluation is unavailable.

## 15. Dependency failure

Unavailable upstream artifacts produce explicit unavailable/degraded state. No historical value, previous value, neutral probability, or zero-risk value may be substituted unless the owning canonical contract explicitly defines that behavior.

## 16. Transition record

Every important state transition records:

```text
transition_id
source_state
trigger_event
preconditions
transition_policy_version
target_state
postconditions
transition_time
provenance
```

## 17. Forbidden transition principle

A transition not defined by an owning state-machine contract is invalid. The orchestrator may not invent a default transition.

## 18. Concurrency

Concurrent event streams may arrive for the same aggregate, including:

```text
market events
order updates
trade fills
position updates
```

Their effect on a particular aggregate must be serialized according to canonical event/state ordering rules. Concurrent workers must not produce two authoritative states for the same aggregate.

## 19. Reentrancy

A causal event may cause downstream events, but uncontrolled recursive self-triggering is forbidden. Every new state-changing action requires a distinct causal event or explicitly defined transition.

## 20. Learning boundary

The feedback chain is:

```text
execution -> fill -> position -> outcome -> label -> learning -> future model version
```

Learning cannot mutate past decisions, fills, or positions. It can only produce future versioned artifacts.

## 21. Emergency precedence

Semantic precedence is:

```text
EMERGENCY
    > required risk protection
    > position exit
    > position reduction
    > new exposure
```

This is not a numerical score. Emergency/protection actions cannot be delayed because expected value is positive.

## 22. Session termination

When the authoritative session lifecycle enters termination/cutoff:

```text
normal new exposure -> disabled
```

Existing exposure follows the lifecycle, action, and execution contracts. A138 does not invent the session cutoff.

## 23. Restart recovery

After restart:

```text
load durable state
    -> load unprocessed canonical events
    -> reconstruct causal state
    -> reconcile broker state
    -> resume
```

Process memory is never treated as authoritative state.

## 24. Crash between authorization and submission

If authorization is durable but execution intent is absent after restart, the orchestrator must determine whether the authorization is valid, expired, superseded, or consumed before any new submission. Blind duplication is forbidden.

## 25. Crash after broker submission

If submission may have reached the broker before process failure:

```text
SUBMISSION_UNKNOWN
    -> reconciliation
```

No blind retry is permitted.

## 26. Audit lineage

The complete causal chain must remain traceable:

```text
raw data
 -> canonical event
 -> instrument version
 -> snapshot
 -> feature
 -> probability
 -> economics
 -> decision
 -> authorization
 -> order intent
 -> broker order
 -> fill
 -> position
 -> outcome
 -> label
 -> learning
 -> future model version
```

## 27. Frozen architecture

```text
causal event processing
domain ownership boundaries
temporal state machine
event idempotency
immutable state lineage
out-of-order semantics
late-event semantics
replay semantics
live/replay parity
semantic atomicity
concurrency boundary
reentrancy boundary
failure taxonomy
fail-closed normal exposure
emergency/protection separation
restart recovery
broker reconciliation boundary
complete audit lineage
versioned transitions
```

## 28. Configuration / implementation validation

```text
event lateness tolerance
watermark policy
reprocessing horizon
reconciliation cadence
worker concurrency
retry timing
transaction mechanism
queue technology
storage technology
```

These are not strategy parameters and must not alter canonical business semantics.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- causal orchestration
- domain ownership
- temporal state machine
- event idempotency
- immutable state lineage
- out-of-order event semantics
- late-event classification
- replay semantics
- live/replay parity
- atomic state-transition semantics
- concurrency boundary
- reentrancy boundary
- failure taxonomy
- fail-closed normal exposure
- emergency/protection separation
- restart recovery
- broker reconciliation boundary
- complete audit lineage
- versioned transitions

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that block orchestration architecture.

CONFIGURATION TO VALIDATE:
- lateness tolerance
- watermark policy
- reprocessing horizon
- reconciliation cadence
- worker concurrency
- retry timing

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A139 — Canonical Outcome, Label, Learning Dataset & Model Lifecycle Contract
```
