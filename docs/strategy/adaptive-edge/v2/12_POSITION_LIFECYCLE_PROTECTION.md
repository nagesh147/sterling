# Adaptive Edge V2 — Position Lifecycle and Protection Contract

**Artifact:** A36  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** NONE

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
OrderIntent
    -> FillEvents
    -> PositionLifecycle
```

Actual position truth comes from confirmed fills, not order intent.

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
account/portfolio scope
opened_at
closed_at
current_quantity
entry_fill references
exit_fill references
position_state
provenance
```

Exact account/portfolio identifiers depend on the execution/account contract.

## Position quantity truth

Position quantity is derived from confirmed fills.

Conceptually:

```text
PositionQuantity(t)
    = cumulative signed fill quantity
      applicable to the position
      through t
```

The exact netting/accounting convention remains a downstream dependency.

## Opening / reducing / closing

A position enters `OPENING` when execution produces a non-zero fill toward a new position.

A reducing execution decreases an existing position magnitude without fully closing it.

A position becomes `CLOSED` only when canonical quantity reaches the defined flat state.

A rejected, unfilled, or merely cancelled order cannot create an open or closed position state.

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
reset condition
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

Potential concepts such as highest favorable price, lowest favorable price, maximum unrealized P&L, or volatility-adjusted reference are candidates only, not V2 definitions.

If a trailing rule is later introduced, its update timing and favorable-direction behavior must be explicit.

## Protection update timing

Every protection update must identify:

```text
observation time
calculation time
activation time
execution submission time
```

A protection level cannot use a future high/low merely because it is visible in historical OHLC data.

## Intrabar ambiguity

If a historical bar contains both a protection trigger and a favorable extreme, bar data alone may not establish event order.

The system must not invent the order from hindsight. The execution/backtest artifact must define a valid resolution rule or mark the observation ambiguous.

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
ExitFill
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

## Exit versus invalidation

A strategy signal becoming invalid does not automatically mean the position is closed. The protection/exit policy must explicitly define whether invalidation creates an exit decision.

## Mode changes while positioned

An operating-mode change is not an automatic liquidation:

```text
OperatingMode change != Position close
```

If mode changes require position management, that relationship must be explicitly defined by position/protection policy.

## Risk authorization while positioned

Revocation or expiry of a new-entry risk authorization does not automatically prove that an existing position must be closed. Existing-position protection is a separate policy decision.

## Protection versus sizing risk

A protection rule may affect potential future loss, but it does not automatically define:

```text
AuthorizedRisk
RiskPerUnit
EffectiveRisk
```

Those remain separate artifacts.

## Realized outcome

A realized outcome is computed only after the relevant exit fills are known. It is downstream of the decision and cannot influence that decision retrospectively.

## P&L accounting

A36 does not freeze final P&L because exact contract multiplier, fees, taxes, financing, and accounting conventions remain external/contract dependencies. The accounting artifact must define these before production P&L claims.

## Partial exits

```text
Position(before)
    -> ExitFill(q)
    -> Position(after)
```

The remaining position retains its lifecycle and protection state. An exit fill is not a full close unless resulting canonical quantity is flat.

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
ProtectionTriggerPrice != GuaranteedFillPrice
```

The actual exit price comes from execution events.

## Session boundary

A36 does not assume:

```text
always intraday
always overnight
always force-close
```

Whether positions can cross a session boundary is a later explicit strategy/execution policy.

## Expiry and instrument lifecycle

For expiring instruments, expiry is an external contract event. The position policy must explicitly define what happens near or at expiry.

Contract adjustments, suspension, corporate actions, and other lifecycle events require authoritative contract/accounting semantics. The strategy must not infer them from price alone.

## State invariants

At all times:

```text
CLOSED -> no further normal position reduction events
NO_POSITION -> no position-specific protection trigger
position quantity derives from fills
exit decision != exit fill
mode transition != automatic liquidation
risk authorization != existing position fact
```

Any violation is a state-machine error.

## Deterministic replay

Given the same ordered fill events, position policy version, protection policy version, and market observations, replay must produce the same position/protection state sequence.

## Adversarial attacks

### Future high used for trail

```text
bar high at t+1 -> compute trail at t
```

Invalid: direct look-ahead.

### Trigger implies fill

```text
stop trigger -> assume exit fill at stop
```

Invalid: execution must establish the actual fill.

### Cancelled exit

```text
exit order cancelled -> position closed
```

Invalid: position remains open unless actual fills establish closure.

### Mode disable

```text
strategy DISABLED -> automatically close every position
```

Invalid unless an explicit position-protection policy defines that transition.

### Expiry hindsight

Using knowledge that a contract will expire worthless to alter an earlier protection decision is invalid.

## Implementation gate

A36 cannot become executable protection logic until the protection rule is fully specified, including trigger variable, source, timestamp semantics, threshold, activation/update behavior, and execution interaction.

## Parameter classes

**Frozen:** fill-derived position truth, lifecycle state separation, protection/position separation, exit decision/fill separation, causal protection updates, explicit reason codes, fail-closed invalid protection.

**Source-defined:** contract expiry/lifecycle, account netting, execution status semantics.

**Learned:** no protection parameter is learned or selected by A36.

**UNKNOWN:** stop rule, trailing rule, target rule, time exit, session policy, expiry handling, accounting specifics.

## Completion criterion

A36 becomes `RESOLVED` only when the system can deterministically reconstruct:

```text
fills
 -> position state
 -> protection state
 -> exit decision
 -> exit order
 -> exit fills
 -> closed position
 -> realized outcome
```

without future information influencing earlier protection decisions.

## ARCHITECTURE STATUS

**FROZEN:** position lifecycle; fill-derived position truth; protection/position separation; exit decision/fill separation; causal protection updates; explicit reason codes; fail-closed protection.

**UNRESOLVED:** stop rule; trailing rule; target rule; time exit; session behavior; expiry handling; protection thresholds; exact P&L/accounting semantics.

**BLOCKERS:** Exact V2 protection/exit policy and execution/accounting semantics are not yet defined. This blocks executable protection logic, not the lifecycle architecture.

**NEXT ARTIFACT:** A37 — Accounting, P&L and Risk-Reconciliation Contract.
