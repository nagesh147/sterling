# Adaptive Edge — Formula Recovery Branch Manifest

## Branch

`feature/adaptive-edge-formula-recovery`

## Scope

This branch is restricted to recovering and validating the strategy mathematics and its provenance. It must not modify SuperTrend, Value Flow Navigator, crypto engines, or unrelated Sterling strategies.

## Changes on this branch

```text
backend/app/engines/adaptive_edge/formula_recovery.py
backend/tests/engines/test_adaptive_edge_formula_recovery.py
docs/strategy/adaptive-edge/FORMULA_RECOVERY_PROTOCOL.md
docs/strategy/adaptive-edge/RECOVERY_COMPLETE.md
docs/strategy/adaptive-edge/BRANCH_MANIFEST.md
```

## Non-goals

- no execution enablement
- no live candidate generation from guessed mathematics
- no replacement of SuperTrend/Navigator logic
- no crypto implementation
- no borrowing of unrelated derivative strategy equations

## Completion rule

The branch is complete when the recovery process is deterministic, auditable, and fail-closed. Exact F-101..F-114 definitions are external inputs to the next promotion step, not values to be invented here.
