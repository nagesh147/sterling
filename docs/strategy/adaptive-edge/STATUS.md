# Adaptive Edge — Current Status

## Source authority

The original Adaptive Edge artifacts are anchored to commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`, including the Master Mathematical Specification and supporting canonical specifications.

The Master Mathematical Specification is the sole authority for strategy mathematics and behavior. Provisional F-101..F-114 reconstruction is deprecated.

## Exactness policy

No implementation is classified as exact because it is plausible or approximately equivalent. A source relationship must be directly traceable and tested. Undocumented behavior is removed or marked blocked.

See `EXACTNESS_AUDIT.md` and `TRACEABILITY.md`.

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

TRUEDATA ADAPTER             BLOCKED ON PROVIDER DOCUMENTATION
HISTORICAL DATA              BLOCKED ON PROVIDER CONTRACT
OOS VALIDATION               BLOCKED
PAPER                        BLOCKED
LIVE                         BLOCKED
```

## Removed as non-canonical

The following unanchored strategy-state implementations were removed:

```text
backend/app/engines/adaptive_edge/contracts.py
backend/app/engines/adaptive_edge/state.py
backend/app/engines/adaptive_edge/state_machine.py
```

They introduced named modes or transitions not sufficiently defined by the authoritative source.

## Governing rule

No learned coefficient, probability threshold, calibration parameter, quantile, execution distribution, risk allocation parameter, mode value, or transition rule will be invented merely to make the engine runnable.
