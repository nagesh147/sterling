# A36 — Position Lifecycle Implementation Boundary

**Status:** LIFECYCLE FRAMEWORK IMPLEMENTED / PROTECTION POLICY BLOCKED

## Implemented

The implementation establishes the source-defined architectural boundary:

```text
confirmed FillEvent
        |
        v
PositionLifecycle
        |
        +--> PositionState
        +--> ProtectionState
```

Position quantity is derived from confirmed fills. An order intent, submission, cancellation, or protection trigger cannot by itself create or close a position.

## Position states

```text
NO_POSITION
OPENING
OPEN
REDUCING
CLOSED
```

## Protection states

```text
UNPROTECTED
PROTECTED
PROTECTION_PENDING
PROTECTION_BREACH
PROTECTION_INVALID
```

The implementation currently supports only the lifecycle-safe invalidation transition. It does not select a protection policy.

## Explicitly unresolved

The source does not define a production rule for:

- stop loss
- trailing protection
- target
- time exit
- session crossing
- expiry handling
- protection thresholds
- exact netting/accounting conventions
- execution/fill semantics

Therefore no defaults are introduced.

## Causal invariant

```text
market observation at t
    -> protection state at t
```

Future highs/lows, future fills, realized P&L, or later execution outcomes cannot influence an earlier protection state.

## Exit separation

```text
Protection/Exit State
    -> ExitDecision
    -> ExitOrderIntent
    -> ExitFill
```

A protection trigger is not an exit fill.

## Completion gate

A36 remains blocked for executable protection until the trigger variable, source, timestamp semantics, threshold, update behavior, and execution interaction are explicitly defined.
