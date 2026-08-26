# A218 — F-112 Dynamic Protection Canonical Recovery

**Status:** `[SOURCE-RECOVERED / EXISTING IMPLEMENTATION RECONCILED / PARAMETERS UNFROZEN]`
**Formula:** F-112

## 1. Role

F-112 governs post-entry protection. It controls stop, profit-lock, and trailing behavior without increasing accepted risk.

The recovered source establishes a monotonic stop invariant:

```text
Stop_(t+1) >= Stop_t
```

for a long option, and a corresponding non-increasing protective level for short-side semantics.

## 2. Protection stages

The canonical lifecycle concept is:

```text
INITIAL_PROTECTION
       |
       v
PROFIT_LOCK
       |
       v
TRAILING_PROTECTION
       |
       v
EXIT
```

The active stage is driven by the current causal market state and validated protection parameters.

## 3. No-risk-expansion invariant

After entry:

```text
AcceptedRisk_(t+1) <= AcceptedRisk_t
```

A new market observation may tighten protection but may not widen the original accepted risk merely because the market has moved against the position.

## 4. Existing implementation

`backend/app/engines/adaptive_edge/protection.py` already implements a stateful protection engine whose later marks tighten rather than loosen the tracked extreme and can trigger protective stop, profit lock, or trailing protection. fileciteturn97file0L2-L6

Its numeric distances are intentionally caller-supplied policy values rather than pretending to be recovered F-112 production parameters. This is the correct separation.

## 5. Horizon adaptation

Protection policy may depend on the active management horizon:

```text
MICRO / IMPULSE
SCALP / TACTICAL
EXTENDED_SCALP
INTRADAY / SESSION_TREND
```

But horizon adaptation cannot loosen already accepted risk.

## 6. Parameter governance

Unfrozen quantities include:

```text
initial stop distance
trail distance
profit-lock activation
profit-lock offset
ATR multipliers
horizon-specific policy coefficients
```

These require walk-forward calibration before production promotion.

## 7. Failure behavior

Invalid or absent protection parameters must fail closed. The system must not silently invent a default stop as a substitute for an unresolved production parameter.

## 8. Resolution

```text
Source semantics:              RECOVERED
Existing stateful engine:      EXISTS
Monotonic protection:          IMPLEMENTED
Parameter calibration:         REQUIRED
Production parameter freeze:   NOT COMPLETE
```

F-112 therefore advances to implementation-validation rather than requiring a second protection engine.

## 9. Next

F-113 should resolve session/horizon termination and forced-exit semantics, including the canonical session cutoff and the rule that termination overrides continued prediction when the position has reached its permitted lifecycle boundary.
