# Adaptive Edge — Current Status

## Source recovery correction

The original Adaptive Edge artifacts are anchored to commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`, including the Master Mathematical Specification and its supporting canonical specifications.

## Completed on this branch

- Located and registered the original strategy specification.
- Added source-derived mathematical operators.
- Added source-section traceability.
- Added canonical probability-model contract without invented coefficients.
- Added leakage-safe multinomial probability fitting for the §22 model family.
- Added immutable risk authorization and sizing.
- Added continuation/profit-protection mathematics.
- Added source-defined economic evaluation and conservative EV gates.
- Added §32 option candidate selection using expected net value subject to explicitly supplied validated constraints.
- Added §33 target/stop candidate selection using caller-supplied validated conservative EV.
- Added monotonic position-management state transitions and exit intent generation without broker-side fill assumptions.
- Retired provisional F-101..F-114 equations from executable strategy logic.
- Reworked the research replay so it consumes decisions from the strategy pipeline rather than implementing a second strategy.
- Added a causal research-dataset contract with feature availability provenance.
- Added chronological walk-forward folds with explicit purge and embargo windows.
- Added deterministic tests for causal dataset validation and fold boundaries.
- Added tests proving validation rows do not alter fitted parameters.
- Kept all work isolated to Adaptive Edge for Sterling Kite.

## Explicitly rejected as canonical

The earlier reconstructed model in `model.py` contained invented numerical weights and thresholds. Those values are not present in the Master Mathematical Specification and are no longer treated as canonical strategy mathematics.

Calibration/model-selection code that introduced unanchored thresholds was removed from this branch. Calibration remains a downstream validation phase until the exact source-defined method and walk-forward evidence are available.

## Current architecture

```text
Canonical Event / Market State
        |
        v
Causal Feature State
        |
        v
Parameterized Probability State
        |
        v
Economic Evaluation
        |
        v
Option Candidate Selection
        |
        v
Target / Stop Evaluation
        |
        v
Risk Authorization
        |
        v
Position Sizing
        |
        v
Forward Management + Profit Protection
        |
        v
Research Execution Replay
        |
        v
Validation / Calibration / OOS
```

## Current status

```text
SOURCE RECOVERY          COMPLETE
SOURCE TRACEABILITY      IMPLEMENTED
CORE MATH OPERATORS      IMPLEMENTED
ECONOMIC LAYER           IMPLEMENTED
OPTION SELECTION         IMPLEMENTED
TARGET/STOP EVALUATION   IMPLEMENTED
RISK LAYER               IMPLEMENTED
PROTECTION LAYER         IMPLEMENTED
POSITION MANAGEMENT      IMPLEMENTED
CAUSAL DATASET CONTRACT  IMPLEMENTED
WALK-FORWARD SPLITTER    IMPLEMENTED
PARAMETER FITTING        IMPLEMENTED
RESEARCH REPLAY          IMPLEMENTED

STATE/EVENT INTEGRATION  NEXT
CALIBRATION              BLOCKED UNTIL CORE PATH IS COMPLETE
KITE HISTORICAL DATA     NEXT
OOS VALIDATION           BLOCKED UNTIL DATA RUN
PAPER                    BLOCKED UNTIL ROBUSTNESS GATE
LIVE                     BLOCKED
```

## Governing rule

No learned coefficient, probability threshold, calibration parameter, quantile, execution distribution, or risk allocation parameter will be invented merely to make the engine runnable. Those values must come from the specified walk-forward learning and validation process.
