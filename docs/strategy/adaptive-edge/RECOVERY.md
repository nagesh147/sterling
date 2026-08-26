# Adaptive Edge — Recovery Ledger

## Canonical source recovery

The original Adaptive Edge master strategy specification has been recovered:

```text
adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md
commit: 38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1
blob: 5ccfde7fcb039282a6753de9440c1484ffc2dfe8
```

A208 and A224 are authoritative recovery decisions.

## Important state correction

The older 2026-08-11 audit below correctly described the state **before** source recovery, but it is now historical. It must not be interpreted as the current source state.

Current state:

```text
SOURCE-RECOVERED
      |
      v
formula canonicalization
      |
      +--> complete -> RESOLVED
      |
      +--> incomplete -> RESOLVED-BLOCKED
```

Source recovery does not unlock production execution.

## Recovered strategy semantics

The V1.0 source establishes:

- causal information through event `t` only;
- liquidity imbalance, delta, delta velocity and market-state construction;
- probabilistic regime and horizon distributions;
- candidate CE/PE option economics;
- option selection by maximum `ExpectedNetEV` subject to liquidity, slippage, risk and data-quality constraints;
- conservative expected value using a lower confidence bound;
- `BUY_CE` / `BUY_PE` mandatory entry gates;
- `RiskPerUnit`, `GrossRisk`, and `Q = floor(MaxRisk / EffectiveRiskPerUnit)`;
- immutable TradePlan and PositionState;
- continuation value and emergency-reversal management;
- monotonic stop protection and no-risk-expansion after entry;
- explicit position state transitions;
- session termination;
- walk-forward learning and model-freeze boundaries.

## Formula recovery disposition

```text
F-101..F-113  SOURCE-RECOVERED / canonicalization + validation required
F-114        SOURCE-RECOVERED / exact multi-position aggregation unresolved
```

## Existing platform contracts remain distinct

The following are not silently imported into Adaptive Edge:

- Navigator signal semantics;
- SuperTrend signal semantics;
- unrelated derivatives-edge equations;
- generic option moneyness heuristics;
- platform risk formulas that are not established as equivalent by the source.

## Data boundary

A197 historical calibration remains a separate evidence gate. Source recovery does not manufacture historical observations or calibrated parameters.

The canonical learning sequence remains:

```text
TRAIN -> FREEZE -> VALIDATE -> TEST -> RECORD -> ADVANCE
```

## Production boundary

The formula registry remains locked. Execution remains fail-closed until every required formula passes its promotion contract and the portfolio interaction semantics are resolved.
