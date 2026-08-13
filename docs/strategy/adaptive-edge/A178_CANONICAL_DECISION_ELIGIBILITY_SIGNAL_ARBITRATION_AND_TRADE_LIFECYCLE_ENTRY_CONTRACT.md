# A178 — Canonical Decision Eligibility, Signal Arbitration & Trade Lifecycle Entry Contract

## Status
CANONICAL

## Purpose
Defines how Adaptive Edge determines whether a candidate opportunity is eligible for a trade decision, arbitrates competing signals, authorizes a new trade lifecycle, and prevents an entry decision from bypassing causal, economic, risk, or execution controls.

It does not freeze numerical signal thresholds, probabilities, expected returns, risk budgets, or model parameters.

```text
OBSERVATION
   -> STATE / FEATURES
   -> PREDICTION
   -> ECONOMICS
   -> ELIGIBILITY
   -> SIGNAL ARBITRATION
   -> DECISION
   -> RISK AUTHORIZATION
   -> EXECUTION INTENT
```

## Fundamental distinctions
```text
signal           != decision
decision         != authorization
authorization    != execution intent
execution intent != order
order            != fill
fill             != position
exit             != re-entry
```

## Candidate signal
A signal must preserve signal identity, instrument identity, observation and feature snapshot references, probability and economics references, strategy/horizon identity, policy/configuration versions, creation and availability timestamps, and causal cutoff. A signal without required provenance is ineligible for consequential use.

## Eligibility
Eligibility is a predicate over data quality, instrument validity, temporal validity, feature completeness, prediction validity, economic validity, lifecycle state, risk preconditions, and configuration validity. Eligibility is not equivalent to profitability and does not authorize execution.

## Fail-closed eligibility
A candidate is not eligible when a safety-critical prerequisite is unknown or invalid, including unknown instrument, unknown position context, causally invalid feature, invalid probability, unknown material economics, expired configuration, stale critical observation, conflicting lifecycle state, or unavailable risk context. Unknown is never converted into an optimistic default.

## Signal arbitration
Multiple eligible signals may coexist. Arbitration must be deterministic for a fixed state, event sequence, policy version, and configuration. Losing candidates remain auditable. Conflicting signals are explicitly resolved or rejected; incompatible intentions are not silently averaged.

## Duplicate signals
Semantically duplicate signals must not create duplicate trade lifecycles. Idempotency is based on canonical identity and decision context, not arrival order.

## Existing-position constraint
Entry eligibility must inspect canonical position context. A new independent entry lifecycle is forbidden when current position state makes it invalid. Scale-in, reversal, pyramiding, and position transformation require explicit lifecycle policy.

## Re-entry
An exit does not authorize re-entry. Re-entry requires a new causal observation, signal identity, eligibility evaluation, decision, authorization, and execution intent.

## Decision object
A consequential decision preserves decision identity, signal identity, instrument identity, position-context identity, feature snapshot, probability and economics references, eligibility and arbitration results, policy/configuration versions, causal cutoff, decision time, and validity boundary. The decision is immutable after issuance.

## Decision validity
A decision is valid only within its defined validity boundary. If material state changes before execution, the execution layer must revalidate or reject it. Stale decisions cannot be silently extended.

## Risk authorization
```text
Decision
   |
   v
Risk Authorization
   |
   v
Execution Intent
```
Risk authorization may reject a decision even when eligibility and economics are positive.

## No direct broker path
Forbidden:
```text
signal -> broker
signal -> order
probability -> order
expected_value -> order
```
Only the canonical authorization and execution lifecycle may produce consequential execution intent.

## Concurrent decisions
Concurrent workers must not create conflicting entry state from the same position context. Explicit concurrency/version control is required so stale decisions cannot commit over newer lifecycle state.

## Position-context versioning
A decision binds to the position context used for eligibility. If that context changes before authorization or execution, the decision is revalidated or rejected according to policy.

## Instrument validity
The candidate must reference canonical instrument identity from A128. Expired, inactive, ambiguous, or otherwise invalid instruments cannot produce executable decisions.

## Horizon consistency
The decision horizon must remain consistent with the horizon identity and policy used to generate prediction and economics. Consumers may not silently reinterpret one horizon as another.

## Causal consistency
For every decision at time `t`:
```text
available_at(input) <= t
```
Future fills, future prices, later calibration results, and later state changes cannot alter historical eligibility or decision state.

## Economic consistency
A decision references the economic estimate available at decision time. Future execution evidence cannot be used to reconstruct and relabel the historical decision basis.

## Signal expiry
Signals may expire because of causal staleness, market-state invalidation, instrument lifecycle change, position-context change, configuration change, or explicit validity boundary. Expired signals cannot be silently revived.

## Decision cancellation
Invalidation preserves the original decision and records the invalidating evidence.

## Partial authorization
If risk authorization permits only a subset of requested exposure, authorized quantity is explicit:
```text
requested_quantity != authorized_quantity
```
Execution intent references authorized quantity.

## Multiple instruments
Portfolio-level shared exposure and correlation constraints may affect arbitration where required by the risk contract. Exact allocation parameters are validation-dependent.

## Options
Option entries preserve underlying identity, option contract identity, strike, expiry, option type, lot/quantity semantics, premium reference, liquidity reference, and execution-price semantics. Underlying signal strength alone does not establish option-entry eligibility.

## Lifecycle initiation
A new trade lifecycle exists only after eligible candidate -> deterministic arbitration -> immutable decision -> valid risk authorization -> execution intent. Lifecycle identity remains stable through order/fill/position events.

## Failure conditions
Reject or defer when signal provenance is incomplete, causal cutoff is violated, instrument is invalid, position context is stale, probability is invalid, material economics are unknown, risk authorization is unavailable, configuration mismatches, concurrency conflicts occur, or a safe execution intent cannot be constructed.

## Recovery
After restart, reconstruct active signals, decisions, authorizations, and pending execution intents from durable evidence. Duplicate reconstruction cannot create a second lifecycle. Consumed or invalidated decisions remain so after recovery.

## Security
Signal data cannot self-authorize privileged execution. Authorization context comes from the security boundary, not signal payload content.

## Parameter classes
### Frozen architecture
Signal/decision/authorization separation; deterministic arbitration; candidate preservation; duplicate prevention; position-context binding; decision immutability; validity boundary; risk gate; direct broker-path prohibition; causal validity; expiry; re-entry separation; partial authorization; lifecycle ordering; recovery semantics.

### Configuration to validate
Signal expiry, arbitration precedence, conflict policy, concurrency policy, position transformation policy, portfolio conflict policy, option-entry acceptance policy.

### Learned / validation-dependent
Signal thresholds, probability thresholds, economic thresholds, ranking parameters, horizon-specific acceptance parameters.

## Adversarial tests
Duplicate signal; opposing signals; concurrent same-instrument signals; stale signal; future feature; future calibration; position changes after signal; position changes after decision; authorization expiry; partial authorization; expired option; wrong option contract; configuration mismatch; worker race; restart after decision; restart after authorization; stale re-entry after exit; direct broker path attempt.

## Invariants
```text
INV-178-001 Signal is not a decision.
INV-178-002 Decision is not risk authorization.
INV-178-003 Risk authorization is not an order.
INV-178-004 Duplicate signals cannot create duplicate trade lifecycles.
INV-178-005 Arbitration is deterministic for identical canonical inputs.
INV-178-006 Losing candidates remain auditable.
INV-178-007 Decisions are bound to the position context used for eligibility.
INV-178-008 Stale position context cannot silently authorize execution.
INV-178-009 Future information cannot influence historical eligibility or decision state.
INV-178-010 Exit does not authorize re-entry.
INV-178-011 Partial authorization is explicitly represented.
INV-178-012 Unknown safety-critical inputs cannot silently produce executable decisions.
INV-178-013 Decision cannot bypass risk authorization.
INV-178-014 Decision identity remains immutable after issuance.
INV-178-015 Recovery cannot create duplicate lifecycle identity.
```

## Architecture Status
```text
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact arbitration persistence mechanism; exact concurrency primitive; exact portfolio conflict implementation; exact option-entry provider verification.
CONFIGURATION TO VALIDATE: signal expiry; arbitration precedence; conflict policy; position transformation; portfolio conflict; option-entry acceptance.
LEARNED / VALIDATION-DEPENDENT: signal, probability, economic and ranking thresholds; horizon-specific acceptance parameters.
BLOCKERS: None for specification work. Production entry remains blocked until provider capabilities, risk policies, execution semantics, and numerical parameters are empirically validated.
NEXT ARTIFACT: A179 — Canonical Trade Lifecycle State Machine, Entry-to-Exit Transition Contract
```
