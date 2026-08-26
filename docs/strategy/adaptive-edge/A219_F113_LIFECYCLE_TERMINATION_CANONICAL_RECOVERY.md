# A219 — F-113 Lifecycle Termination and Session Cutoff Recovery

**Status:** `[SOURCE-RECOVERED / EXISTING IMPLEMENTATION RECONCILED]`
**Formula:** F-113 / lifecycle termination boundary

## 1. Canonical termination precedence

F-113 defines conditions that terminate a position regardless of continued predictive confidence.

Highest-priority exits are:

```text
EMERGENCY
HARD_RISK_BREACH
SESSION_CUTOFF
PROTECTION HIT
THESIS_INVALID
ECONOMIC_COLLAPSE
```

A position must not remain open merely because a prediction model remains positive after a hard lifecycle boundary has been reached.

## 2. Session cutoff

For the canonical NSE intraday session:

```text
Session close = 15:30 IST
Normal trading cutoff = 14:45 IST
```

At or after the cutoff:

```text
new entries = forbidden
horizon upgrades = forbidden
active positions = flatten
```

The existing A126 lifecycle engine explicitly implements the `SESSION_CLOSE - 45 minutes` rule and forces flattening when the cutoff evidence is reached. fileciteturn102file0L2-L6

## 3. Thesis invalidation

A position exits immediately when the causal evidence state becomes:

```text
THESIS_INVALID
```

This is independent of whether the position is profitable.

## 4. Risk breach

A hard risk breach overrides all promotion/downgrade logic and produces immediate exit.

## 5. Protection precedence

Protective stop, profit-lock, and trailing events are terminal when triggered. Session cutoff cannot be suppressed by an optimistic horizon state.

## 6. State-machine invariant

The lifecycle engine must preserve:

```text
initial_horizon != current_horizon != exit_condition
```

Horizon, thesis, protection, and overlays remain orthogonal state dimensions. fileciteturn102file0L2-L6

## 7. No invented thresholds

F-113 does not invent numerical promotion/downgrade thresholds. Evidence must be supplied explicitly by the strategy decision/evidence layer.

## 8. Auditability

Every lifecycle transition must produce an immutable `TransitionRecord` containing:

```text
transition identity
position identity
time
from/to horizon
from/to thesis
from/to protection
trigger
supporting evidence
risk state
economic state
model version
configuration version
reason code
```

The existing A126 engine already carries this transition structure. fileciteturn102file0L2-L6

## 9. Resolution

```text
Termination semantics:       RECOVERED
Session cutoff:              IMPLEMENTED
Hard-risk precedence:        IMPLEMENTED
Thesis invalidation:         IMPLEMENTED
Audit transition records:    IMPLEMENTED
Promotion thresholds:        UNFROZEN / evidence-driven
```

F-113 requires validation and promotion governance, not a second lifecycle engine.

## 10. Next

F-114 is the final formula boundary: multi-position interaction, portfolio-level risk/economic overlays, and canonical strategy-state aggregation. It must not be allowed to bypass individual position-level protection or risk constraints.
