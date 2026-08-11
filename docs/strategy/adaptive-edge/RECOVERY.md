# Adaptive Edge — Recovery Ledger

## Historical recovery result — 2026-08-11

The available conversation context and Sterling repository do not expose the exact historical equations that were previously discussed. The F-101..F-114 identifiers were created by the later implementation/recovery artifacts; they are not evidence that the original conversation used those identifiers.

Therefore the branch does **not** claim that the new equations are recovered historical mathematics.

## Decision: implement a reconstructed v0.1.0 model

Per the project decision to proceed rather than remain blocked, F-101..F-114 are now implemented as an explicit, versioned research model.

```text
historical equations unavailable
        |
        v
reconstructed model v0.1.0
        |
        v
unit + adversarial tests
        |
        v
backtest / OOS / cost sensitivity
        |
        v
paper / shadow
        |
        v
production authorization only after validation
```

This is a strategy revision, not a claim of historical recovery.

## Canonical invariants retained

1. Adaptive Edge is a Sterling Kite engine only.
2. SuperTrend, Flow Navigator, and crypto semantics are independent.
3. `DynamicMode` and `RiskState` are separate axes.
4. `RiskAuthorization` is immutable for an opportunity.
5. Causal feature availability is mandatory.
6. Economic evaluation is separate from prediction and risk.
7. `ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost`.
8. BUY uses executable ask; SELL uses executable bid.
9. Signal, authorization, order, fill, position, and accounting are distinct states.
10. The UI does not recompute strategy mathematics.

## Reconstructed formulas

The following are now implemented in `backend/app/engines/adaptive_edge/model.py` and documented in `FORMULAS.md`:

```text
F-101  Composite feature score
F-102  Edge / prediction score
F-103  Opportunity eligibility
F-104  Dynamic operating mode
F-105  Predictive-profit protection
F-106  Dynamic risk schedule
F-107  Risk per unit
F-108  Position sizing
F-109  Instrument selection
F-110  Entry trigger
F-111  Exit trigger
F-112  Protection parameterization
F-113  Re-entry
F-114  Multi-position interaction
```

## Research warning

The reconstructed formulas are **not production-proven**. The implementation is intentionally deterministic so it can now be falsified with backtests instead of remaining theoretical.

No live execution should be enabled from this branch merely because the formulas compile or pass unit tests.
