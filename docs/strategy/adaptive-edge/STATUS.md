# Adaptive Edge — Current Status

## Done

- Canonical strategy folder established.
- Strategy semantics separated from SuperTrend and Value Flow Navigator.
- Machine-readable formula registry established.
- F-001..F-008 anchored; F-004 implemented.
- Historical F-101..F-114 recovery audited and found unavailable in retrievable context.
- Decision made to proceed with an explicit reconstructed Adaptive Edge v0.1.0 model rather than remain blocked.
- F-101..F-114 reconstructed equations documented in `FORMULAS.md`.
- F-101..F-114 promoted to versioned registry entries.
- Pure deterministic model implemented in `model.py`.
- Versioned F-102 EdgeFormula adapter implemented.
- Causal feature provenance preserved.
- Economic evaluation remains separated under F-004.
- DynamicMode/RiskState separation preserved.
- Immutable RiskAuthorization contract preserved.
- Unit and adversarial tests added for the reconstructed formula set.
- Deterministic historical replay engine implemented.
- Causal Kite Candle -> Adaptive Edge feature adapter implemented.
- Replay robustness tests added.
- Research-only Kite backtest endpoint module added; it is not wired to live execution.
- Dedicated Adaptive Edge UI remains separate from shared Signals.

## Current status

```text
FORMULAS             IMPLEMENTED v0.1.0
UNIT TESTS           IMPLEMENTED
EDGE PIPELINE        IMPLEMENTED
ECONOMICS            IMPLEMENTED
RISK CONTRACT        IMPLEMENTED
UI                   IMPLEMENTED

HISTORICAL REPLAY    IMPLEMENTED
KITE FEATURE ADAPTER IMPLEMENTED
KITE API ROUTING     PENDING REGISTRATION
OOS VALIDATION       BLOCKED UNTIL DATA RUN
PAPER                BLOCKED UNTIL ROBUSTNESS GATE
LIVE                 BLOCKED
```

## Important qualification

F-101..F-114 are a reconstructed model because the original historical equations were not retrievable. They are not represented as recovered historical facts. The branch is now designed to falsify or improve this model quantitatively.

## Next gates

```text
1. Register the research-only Adaptive Edge router
2. Run historical Kite data through the adapter
3. Run execution-cost/slippage sensitivity
4. Establish chronological in-sample / validation / holdout split
5. Measure expectancy, drawdown, turnover, hit rate, tail loss
6. Run regime and parameter robustness tests
7. Reject the model if robustness gates fail
8. Paper/shadow only after robustness passes
9. Live execution only after explicit authorization
```
