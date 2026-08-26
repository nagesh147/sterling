# A56 — Operational State / Trading State Interaction Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A56 defines the explicit interface by which operational state constrains trading permissions. It does not infer strategy behavior from infrastructure health and does not authorize live trading.

## Permission dimensions

A trading state records four independent permissions:

```text
allow_signal_generation
allow_new_entries
allow_existing_position_management
allow_exit_submission
```

This prevents a single boolean such as `system_healthy` from collapsing distinct trading responsibilities.

## Structural invariants

```text
BLOCK_NEW -> allow_new_entries = false
HALTED    -> allow_new_entries = false
HALTED    -> allow_signal_generation = false
```

A halted system may still retain `allow_exit_submission` when the governing operational policy permits exit handling. This contract does not assume that halting requires liquidation.

## State vocabulary

```text
NORMAL
DEGRADED
BLOCK_NEW
HALTED
UNKNOWN
```

The labels are state identities, not numeric thresholds.

## Required lineage

Each operational trading state retains:

- state identity
- operational state
- observation identity
- policy identity
- policy version
- explicit permission vector

## Non-inferences

A56 does not define:

- automatic liquidation
- stop-loss behavior
- recovery timing
- reconnect thresholds
- provider-specific failure rules
- capital or risk limits
- strategy entry/exit mathematics

Those remain governed by authoritative strategy or operational artifacts.

## Boundary

```text
A55 operational observation/control
        |
        v
A56 operational trading state
        |
        +--> signal permission
        +--> new-entry permission
        +--> existing-position management
        +--> exit permission
```

Operational state therefore constrains execution without becoming a trading signal itself.
