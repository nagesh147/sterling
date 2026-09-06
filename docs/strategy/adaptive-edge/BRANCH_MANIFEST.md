# Adaptive Edge — Formula Recovery / Implementation Branch Manifest

## Branch

`feature/adaptive-edge-formula-recovery`

## Scope

This branch is restricted to Adaptive Edge formula definition, deterministic implementation, provenance, testing, and research replay. It must not modify SuperTrend, Value Flow Navigator, or unrelated Sterling strategies.

## Current implementation

```text
backend/app/engines/adaptive_edge/
    formula_registry.py
    formula_recovery.py
    feature_engine.py
    edge.py
    economic.py
    pipeline.py
    contracts.py
    model.py
    reconstructed_edge.py
    replay.py

backend/tests/engines/
    test_adaptive_edge_formula_registry.py
    test_adaptive_edge_formula_recovery.py
    test_adaptive_edge_feature_provenance.py
    test_adaptive_edge_model.py
    test_adaptive_edge_reconstructed_edge.py
    test_adaptive_edge_replay.py
```

## Formula status

F-001..F-008 are anchored platform/strategy invariants. F-101..F-114 are implemented as reconstructed Adaptive Edge v0.1.0 mathematics because the historical equations were not retrievable.

## Non-goals

- no live execution enablement
- no production authorization from unit tests alone
- no replacement of SuperTrend/Navigator logic
- no unrelated market implementation
- no borrowing of unrelated derivative strategy equations

## Next completion gate

```text
same model
+ authoritative historical data
+ realistic execution model
        |
        v
backtest
        |
        v
OOS + sensitivity + robustness
        |
        v
paper/shadow
        |
        v
explicit production authorization
```
