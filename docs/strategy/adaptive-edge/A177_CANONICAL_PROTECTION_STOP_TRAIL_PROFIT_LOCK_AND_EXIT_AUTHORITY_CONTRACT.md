# A177 — Canonical Protection, Stop/Trail, Profit-Lock & Exit-Authority Contract

**Status:** CANONICAL
**Authority:** Exposure protection and exit-authority boundary
**Scope:** Adaptive Edge
**Dependencies:** A153–A176

## 1. Purpose

A177 defines how existing exposure is protected, how protective and economic exits are represented, and which authority may cause an exposure-reducing action.

It freezes semantic boundaries, lifecycle identity, causality, and authority separation. It does not select numerical stop distances, trailing coefficients, profit targets, or other strategy parameters.

```text
EXPOSURE
   |
   +--> HARD RISK
   +--> PROTECTION
   +--> ECONOMIC EXIT
   +--> PROFIT PROTECTION
   +--> SESSION / LIFECYCLE CLOSE
   +--> EMERGENCY ACTION
```

## 2. Fundamental distinctions

```text
trigger        != exit order
exit order     != fill
fill           != position closure
requested protection != effective protection
unrealized profit != realized profit
current price  != historical trigger evidence
```

## 3. Protection identity

Every consequential protection lifecycle preserves, as applicable:

```text
protection_id
position_context_id
instrument_identity
authority_type
trigger_definition
trigger_snapshot_id
trigger_time
causal_cutoff
protected_quantity
unprotected_quantity
reference_price
state
policy_version
configuration_version
created_at
valid_from
valid_until
```

Historical protection decisions are immutable.

## 4. Authority taxonomy

Canonical authority classes are:

```text
HARD_RISK
PROTECTIVE_STOP
TRAILING_PROTECTION
PROFIT_LOCK
ECONOMIC_EXIT
SESSION_CLOSE
LIFECYCLE_CLOSE
EMERGENCY
```

An implementation may combine mechanically compatible actions, but must preserve originating authority and rationale.

## 5. Hard-risk authority

Hard-risk conditions are non-optional exposure boundaries. When active:

```text
new_normal_exposure = BLOCKED
```

The applicable exposure-reduction lifecycle takes precedence according to the risk contract.

## 6. Protective stop

A protective stop is an exposure-control policy based on a defined reference and trigger condition. The trigger definition must specify reference, comparison/operator, threshold semantics, observation source, availability boundary, activation state, and invalid-input behavior.

A numerical threshold without reference, units, and timing semantics is non-conformant.

## 7. Trailing protection

Trailing protection is stateful. It must preserve the historical extreme, or an equivalent canonical state, from which the current protection boundary is derived.

```text
new_observation
    -> admissible extreme update
    -> protection boundary update
```

Later observations may tighten protection according to policy, but may not retroactively alter an issued historical decision. Future extrema must never reconstruct an earlier protection boundary.

## 8. Monotonicity

Where a trailing policy is defined as monotonic tightening, the implementation must preserve that invariant. The exact monotonic direction is determined by position side and the canonical trailing policy.

## 9. Profit lock

Profit-lock protection is distinct from ordinary stop protection. It may activate only after its explicit activation condition is satisfied. Activation and subsequent protection state must be preserved independently of displayed unrealized P&L.

Profit-lock logic must not assume unrealized profit is realizable at the displayed price.

## 10. Economic exit

Economic exit answers whether continuing exposure remains economically justified. It is distinct from protection:

```text
protection -> control downside/exposure
economics  -> evaluate continued opportunity
```

An economic exit may close exposure even when no protective trigger has fired.

## 11. Session and lifecycle exits

Session close, expiry, instrument invalidation, strategy lifecycle termination, and other mandatory lifecycle conditions remain separate authorities. A strategy cannot suppress a mandatory lifecycle exit merely because economic expectation remains positive.

## 12. Emergency authority

Emergency action is an explicitly authorized exposure-reduction pathway for degraded or unsafe operating conditions. It remains usable when normal decision orchestration is impaired, subject to emergency controls.

## 13. Trigger timing

For a trigger evaluated at time `t`:

```text
available_at(all trigger inputs) <= t
```

must hold. Later prices, fills, extrema, volatility, account state, or provider observations cannot establish a historical trigger that was not observable at `t`.

## 14. Trigger evidence

A consequential trigger preserves enough evidence to reconstruct input events, state snapshot, reference value, threshold/policy version, trigger result, trigger time, and causal cutoff.

The system must not reconstruct trigger history from current state alone.

## 15. Trigger versus execution

```text
protection state
    -> trigger
    -> exit/protection intent
    -> order lifecycle
    -> provider evidence
    -> fill evidence
    -> position effect
    -> reconciliation
```

A triggered protection rule does not prove that an exit occurred.

## 16. Partial fills

Protection must account for partial fills.

```text
protected target = 100
exit fill = 40
remaining exposure = 60
```

Remaining exposure remains subject to applicable protection unless the lifecycle explicitly establishes otherwise.

## 17. Protection effectiveness

The implementation must distinguish:

```text
UNPROTECTED
PROTECTION_REQUESTED
PROTECTION_PENDING
PARTIALLY_PROTECTED
PROTECTED
PROTECTION_FAILED
PROTECTION_UNKNOWN
```

A submitted protection order is not automatically effective protection.

## 18. Replacement and modification

A protection modification preserves lineage:

```text
original protection lifecycle
    -> modification/replacement
    -> resulting lifecycle
```

Historical protection records cannot be overwritten merely because a newer level exists.

## 19. Multiple authorities

Multiple exit authorities may become active concurrently. The system must preserve authority identities, trigger evidence, precedence rule, and resulting action.

If multiple authorities produce the same exposure-reducing action, the action may be deduplicated operationally while retaining all causal authority evidence.

## 20. Precedence

The architecture requires an explicit precedence relation. At minimum:

```text
EMERGENCY / HARD_RISK
        > mandatory lifecycle protection
        > ordinary protective policies
        > economic exit / profit-lock policies
        > strategy preference
```

The exact precedence matrix must be validated against the complete lifecycle contract before production.

## 21. Re-entry separation

An exit authority must not implicitly authorize a new entry.

```text
exit != re-entry
```

Any re-entry requires a new decision, new authorization, and new execution lifecycle.

## 22. Session close

If the strategy forbids exposure beyond a defined session boundary, session-close authority remains independent of ordinary stop/target state. The implementation must not rely on absence of a signal to infer that exposure should be closed.

## 23. Invalid or stale trigger inputs

A stale, missing, conflicting, or causally unavailable trigger input must not silently become a trigger or non-trigger. Policy may block, defer, escalate, or enter emergency handling according to failure class.

## 24. Price semantics

Protection triggers must explicitly identify price/reference semantics.

```text
LTP != BID
LTP != ASK
LTP != EXECUTABLE_PRICE
```

## 25. Options

For options, protection state preserves canonical contract identity and relevant price/quantity semantics. Underlying movement may be used only when the applicable strategy contract explicitly defines the relationship between underlying state and option-exposure protection.

## 26. Configuration and versioning

Protection policy is versioned. Changes to stop methodology, trailing methodology, profit-lock methodology, activation rules, precedence, session-close policy, or emergency thresholds create a new configuration/policy identity. Historical decisions remain bound to their original versions.

## 27. Failure behavior

Protection fails closed for safety-critical unknowns including unknown position, unknown quantity, unknown instrument, unknown trigger reference, unknown price semantics, stale critical observation, configuration mismatch, concurrency conflict, and provider execution uncertainty.

The implementation must not claim effective protection when effectiveness is unknown.

## 28. Recovery

After restart, protection state is reconstructed from durable evidence and reconciled with externally represented protection/order state. Recovery preserves active protection, triggered-but-unsubmitted protection, submission uncertainty, partial exit, remaining exposure, protection failure, and emergency actions. Recovery is idempotent.

## 29. No retroactive mutation

Later market observations or provider corrections may create new evidence or a new future protection state, but must not rewrite the meaning of a completed historical trigger or exit decision.

## 30. Realized outcome separation

Protection decisions are decision-time evidence. Realized P&L and execution quality are later outcome evidence.

```text
protection decision != realized outcome
```

## 31. Hostile scenarios

The implementation must test future/late trigger input, duplicate/conflicting trigger, market-data gaps, stale/crossed quotes, partial exit fill, exit fill after trigger replacement, cancel/fill race, unknown protection submission, restart at each consequential boundary, simultaneous authorities, hard-risk during normal exit, emergency action during provider outage, configuration mismatch, position mismatch, wrong option contract, underlying/option timing mismatch, and session-boundary races.

## 32. Invariants

```text
INV-177-001  Trigger evidence is distinct from exit execution evidence.
INV-177-002  Protection effectiveness is not inferred from order submission alone.
INV-177-003  Historical protection decisions are immutable.
INV-177-004  Trailing state cannot use future extrema.
INV-177-005  Monotonic trailing policies cannot loosen through ordinary retracement.
INV-177-006  Partial exits leave remaining exposure subject to applicable protection.
INV-177-007  Multiple authorities remain causally distinguishable.
INV-177-008  Hard-risk and emergency authority cannot be bypassed by ordinary strategy preference.
INV-177-009  Exit does not authorize re-entry.
INV-177-010  Invalid/stale critical trigger inputs cannot silently produce normal protection decisions.
INV-177-011  Historical trigger meaning cannot be rewritten by later observations.
INV-177-012  Protection state is recoverable and reconciliation-aware.
INV-177-013  Price semantics are explicit for consequential triggers.
INV-177-014  Configuration/policy versions remain bound to historical protection decisions.
```

## 33. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- protection authority boundary
- authority taxonomy
- trigger/execution separation
- trigger evidence
- trailing-state semantics
- monotonicity principle
- profit-lock separation
- economic-exit separation
- lifecycle/session exit separation
- emergency authority
- partial-fill protection
- protection effectiveness states
- replacement lineage
- multi-authority evidence
- exit/re-entry separation
- price-semantic boundary
- recovery semantics
- historical immutability

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact protection-state persistence implementation
- exact external protection capability verification
- exact precedence matrix validation
- exact price-reference methodology
- exact emergency execution mechanism

CONFIGURATION TO VALIDATE:
- stop methodology
- trailing methodology
- profit-lock activation
- authority precedence
- session-close policy
- protection freshness limits
- emergency thresholds
- protection modification cadence

LEARNED / VALIDATION-DEPENDENT:
- stop distances
- trailing coefficients
- profit-lock thresholds
- empirical adverse-move distributions
- execution/fill probabilities
- protection slippage distributions

BLOCKERS:
None for specification.
Production protection remains blocked until numerical policy, provider capabilities, and execution/reconciliation behavior are empirically validated.

NEXT ARTIFACT:
A178 — Canonical Decision Eligibility, Signal Arbitration & Trade Lifecycle Entry Contract
```
