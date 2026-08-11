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
- Edge formula interface now accepts registered implemented formulas.
- Economic evaluation remains separated under F-004.
- DynamicMode/RiskState separation preserved.
- Immutable RiskAuthorization contract preserved.
- Unit and adversarial tests added for the reconstructed formula set.
- Dedicated Adaptive Edge UI remains separate from shared Signals.

## Current status

```text
FORMULAS       IMPLEMENTED v0.1.0
UNIT TESTS     IMPLEMENTED
EDGE PIPELINE  IMPLEMENTED
ECONOMICS      IMPLEMENTED
RISK CONTRACT  IMPLEMENTED
UI             IMPLEMENTED

BACKTEST       NEXT
OOS VALIDATION NEXT
PAPER          BLOCKED UNTIL BACKTEST GATE
LIVE           BLOCKED
```

## Important qualification

F-101..F-114 are a reconstructed model because the original historical equations were not retrievable. They are not represented as recovered historical facts. The branch is now designed to falsify or improve this model quantitatively.

## Next gates

```text
1. Connect authoritative Kite market-data inputs
2. Build historical backtest adapter using the same model functions
3. Run execution-cost/slippage sensitivity
4. Establish in-sample / out-of-sample split
5. Measure expectancy, drawdown, turnover, hit rate, tail loss
6. Reject the model if robustness gates fail
7. Paper/shadow only after robustness passes
8. Live execution only after explicit authorization
```
