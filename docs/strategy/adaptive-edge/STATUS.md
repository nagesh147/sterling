# Adaptive Edge — Current Status

## Canonical development branch

All active Adaptive Edge implementation work is now consolidated on:

```text
feature/adaptive-edge-canonical
```

The older Adaptive Edge branches are historical work branches only. New changes must not be started on them.

## Source authority

The original Adaptive Edge artifacts are anchored to commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`, including the Master Mathematical Specification and supporting canonical specifications.

The Master Mathematical Specification is the sole authority for strategy mathematics and behavior. Provisional F-101..F-114 reconstruction is deprecated.

## Current status

```text
SOURCE RECOVERY              COMPLETE
SOURCE TRACEABILITY          IMPLEMENTED
EXACTNESS AUDIT              COMPLETE

PRICE / VOLUME / DELTA MATH  EXACT FOR IMPLEMENTED OPERATORS
LIQUIDITY MATH               EXACT
NORMALIZATION                PARTIAL
DIRECTIONAL PROBABILITY      PARTIAL
LOGISTIC MODEL               PARTIAL
SIMILARITY                   PARTIAL
BAYESIAN STATE               PARTIAL
ECONOMIC COST MODEL          PARTIAL
OPTION SELECTION             BLOCKED
TARGET/STOP EV               EXACT FOR SUPPLIED VALIDATED INPUTS
CONSERVATIVE EV              EXACT FOR SUPPLIED LCB
RISK PER UNIT                EXACT OPERATOR
POSITION SIZING              PARTIAL
CONTINUATION VALUE           EXACT OPERATOR
PROFIT PROTECTION            PARTIAL
MONOTONIC STOP               EXACT INVARIANT
NO RISK EXPANSION            EXACT INVARIANT
DYNAMIC MODE                 BLOCKED
ENTRY GATES                  BLOCKED
EXIT ORCHESTRATION           BLOCKED
STATE TRANSITIONS            BLOCKED
WALK-FORWARD DATA CONTRACT   IMPLEMENTED
PARAMETER FITTING            PARTIAL
A40 FEATURE LINEAGE          IMPLEMENTED
A41 PREDICTION CONTRACT      INTERFACE IMPLEMENTED

TRUEDATA ADAPTER             BLOCKED ON PROVIDER DOCUMENTATION
HISTORICAL DATA              BLOCKED ON PROVIDER CONTRACT
OOS VALIDATION               BLOCKED
PAPER                        BLOCKED
LIVE                         BLOCKED
```

## Consolidation rule

The canonical branch contains the latest usable Adaptive Edge implementation lineage plus the source-defined A38/A39/A40 infrastructure and A41 prediction boundary. Where older branches conflicted, the later canonical implementation was retained and source-defined infrastructure was integrated without inventing strategy semantics.

## Governing rule

No learned coefficient, probability threshold, calibration parameter, quantile, execution distribution, risk allocation parameter, mode value, or transition rule will be invented merely to make the engine runnable.

## Current next artifact

```text
A42 — Economic Value, Expected Value and Decision Utility Contract
```
