# Adaptive Edge V2 — Position Lifecycle and Protection Contract

**Artifact:** A36
**Version:** 2.0.0-draft
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Market/research data:** TrueData only
**Trading/execution provider:** Zerodha Kite Connect v3 only
**Implementation:** PARTIAL — fill-derived lifecycle infrastructure exists; strategy protection semantics remain unresolved

## Purpose

A36 defines the canonical lifecycle of a position after execution and the boundary for protection/exit decisions.

It separates:

```text
position state
protection state
exit decision
exit order
fill
realized outcome
```

A36 does not invent stop distances, trailing parameters, targets, holding periods, or exit thresholds.

## Canonical dependency

```text
Adaptive Edge OrderIntent
    -> Kite Order
    -> Kite FillEvents
    -> PositionLifecycle
    -> ProtectionState
    -> ExitDecision
    -> Kite ExitOrder
    -> Kite ExitFill
```

Actual position truth comes from confirmed Kite fills, not order intent.

TrueData observations may drive protection decisions, but they remain market observations and never prove execution.

## Position states

```text
NO_POSITION
OPENING
OPEN
REDUCING
CLOSED
```

These describe position lifecycle, not strategy eligibility or risk authorization.

## Position identity

A canonical position record must identify:

```text
position_id
strategy_version
instrument_id
Kite account/portfolio scope
opened_at
closed_at
current_quantity
entry_fill references
exit_fill references
position_state
provenance
```

Exact account/netting semantics depend on the Kite/account contract.

## Position quantity truth

```text
PositionQuantity(t)
    = cumulative signed confirmed Kite fill quantity
      applicable to the position through t
```

A submitted or accepted order without a fill cannot create position quantity.

## Opening / reducing / closing

A position enters `OPENING` when execution produces a non-zero fill toward a new position.

A reducing execution decreases existing position magnitude without fully closing it.

A position becomes `CLOSED` only when canonical quantity reaches the defined flat state.

A rejected, unfilled, or merely cancelled Kite order cannot create an open or closed position state.

## Protection state

Protection is separate from position existence:

```text
Position
    |
    v
ProtectionPolicy
    |
    v
ProtectionState
```

Architectural states:

```text
UNPROTECTED
PROTECTED
PROTECTION_PENDING
PROTECTION_BREACH
PROTECTION_INVALID
```

Exact transitions remain unresolved.

## Protection definition

A protection rule must eventually specify:

```text
trigger variable
trigger source
trigger timestamp
comparison operator
threshold/parameter
unit
activation condition
reset/update condition
failure behavior
policy version
```

A mathematically valid threshold without these semantics is insufficient.

## Stop-loss

A36 does not select:

```text
fixed percentage stop
fixed point stop
ATR stop
volatility stop
structure stop
option-premium stop
underlying-based stop
```

No stop rule is selected by convention.

## Trailing protection

A trailing mechanism requires an explicit causal reference state.

If introduced, its update timing and favorable-direction behavior must be explicit.

Future highs/lows cannot update an earlier protection state.

## Protection update timing

Every protection update must identify:

```text
TrueData observation time
calculation time
activation time
Kite order-submission time
Kite acknowledgement/fill time
```

These timestamps are distinct.

## Intrabar ambiguity

If historical TrueData bar data contains both a protection trigger and a favorable extreme but does not establish event order, the simulator must not invent the order from hindsight. The execution/backtest artifact must define a valid resolution rule or mark the observation ambiguous.

## Exit decision versus exit execution

```text
Protection/Exit State
        |
        v
ExitDecision
        |
        v
ExitOrderIntent
        |
        v
Kite ExitOrder
        |
        v
Kite ExitFill
```

A triggered exit does not prove that the position was actually exited.

## Exit reasons

Architectural categories include:

```text
PROTECTION_TRIGGER
STRATEGY_EXIT
TIME_EXPIRY
INVALIDATION
MANUAL_DISABLE
SYSTEM_SAFETY
OTHER_EXPLICIT_POLICY
```

An exit reason cannot be inferred merely from the position losing money.

## Mode changes while positioned

```text
OperatingMode change != Position close
```

If a mode change requires position management, that relationship must be explicitly defined by position/protection policy.

## Risk authorization while positioned

Revocation or expiry of a new-entry risk authorization does not automatically prove that an existing position must be closed.

Existing-position protection is a separate policy decision.

## Protection versus sizing risk

A protection rule may affect potential future loss, but it does not automatically define:

```text
AuthorizedRisk
RiskPerUnit
EffectiveRisk
```

Those remain separate artifacts.

## Realized outcome

A realized outcome is computed only after the relevant Kite exit fills are known. It is downstream of the decision and cannot influence that decision retrospectively.

## P&L accounting

A36 does not freeze final P&L because exact contract multiplier, fees, taxes, settlement, and accounting conventions remain external/contract dependencies. The accounting artifact must define these before production P&L claims.

## Partial exits

```text
Position(before)
    -> Kite ExitFill(q)
    -> Position(after)
```

The remaining position retains its lifecycle and protection state.

## Protection invalidation

Protection becomes invalid if required input is:

```text
missing
stale
invalid
ambiguous
out-of-order
from an unauthorized policy version
```

The result must fail closed according to the safety policy; no synthetic protective price is invented.

## Execution gap risk

A protection trigger does not guarantee execution at that value:

```text
ProtectionTriggerPrice != GuaranteedKiteFillPrice
```

Actual exit price comes from Kite execution events.

## Session boundary

A36 does not assume always-intraday, overnight holding, or automatic force-close. The policy must explicitly define session behavior.

## Expiry and instrument lifecycle

Expiry is an external contract event. The position policy must explicitly define behavior near/at expiry.

Contract adjustments, suspension, corporate actions, and other lifecycle events require authoritative contract/accounting semantics.

## State invariants

```text
CLOSED -> no further normal position reduction events
NO_POSITION -> no position-specific protection trigger
position quantity derives from Kite fills
exit decision != exit fill
mode transition != automatic liquidation
risk authorization != existing position fact
TrueData market event != Kite execution event
```

Any violation is a state-machine error.

## Deterministic replay

Given the same ordered TrueData market observations, Kite fill events, position policy version, protection policy version, and event ordering, replay must produce the same position/protection state sequence.

## Adversarial attacks

### Future high used for trail

```text
TrueData bar high at t+1 -> compute trail at t
```

Invalid.

### Trigger implies fill

```text
stop trigger -> assume Kite exit fill at stop
```

Invalid.

### Cancelled exit

```text
Kite exit order cancelled -> position closed
```

Invalid unless actual Kite fills establish closure.

### Mode disable

```text
strategy DISABLED -> automatically close every position
```

Invalid unless an explicit protection policy defines that transition.

### Expiry hindsight

Using knowledge that a contract will expire worthless to alter an earlier protection decision is invalid.

## Implementation gate

A36 cannot become executable protection logic until the protection rule is fully specified, including trigger variable, source, timestamp semantics, threshold, activation/update behavior, and Kite execution interaction.

## Parameter classes

**Frozen:** fill-derived position truth; Kite execution authority; TrueData market observation authority; lifecycle state separation; protection/position separation; exit decision/fill separation; causal protection updates; explicit reason codes; fail-closed invalid protection.

**Source-defined:** contract expiry/lifecycle, account netting, Kite execution status semantics.

**Learned:** no protection parameter is selected by A36.

**UNKNOWN:** stop rule, trailing rule, target rule, time exit, session policy, expiry handling, accounting specifics.

## Completion criterion

A36 becomes `RESOLVED` only when the system can deterministically reconstruct:

```text
TrueData market observations
 -> position/protection state
 -> exit decision
 -> Kite exit order
 -> Kite exit fills
 -> closed position
 -> realized outcome
```

without future information influencing earlier protection decisions.

## ARCHITECTURE STATUS

**FROZEN:** TrueData market boundary; Kite execution boundary; position lifecycle; fill-derived position truth; protection/position separation; exit decision/fill separation; causal protection updates; explicit reason codes; fail-closed protection.

**UNRESOLVED:** stop rule; trailing rule; target rule; time exit; session behavior; expiry handling; protection thresholds; exact P&L/accounting semantics.

**BLOCKERS:** Exact V2 protection/exit policy and execution/accounting semantics are not yet defined. This blocks executable protection logic, not the lifecycle architecture.

**NEXT ARTIFACT:** A37 — Accounting, P&L and Risk-Reconciliation Contract.
