# Adaptive Edge — Current Status

## Source recovery correction

The original conversation-generated Adaptive Edge artifacts have now been located in Git commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`.

Primary source:

```text
adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md
Master Mathematical Specification — Version 1.0
```

The source set contains the complete strategy mathematics and supporting canonical specifications. See `ORIGINAL_SOURCE_MANIFEST.md`.

## Completed on this branch

- Located the original Master Mathematical Specification.
- Registered the source commit and artifact set.
- Added source-derived mathematical operators.
- Added source-section traceability registry.
- Added canonical economic evaluation layer.
- Added canonical risk authorization and sizing layer.
- Added canonical continuation/protection layer.
- Added deterministic tests for the source-derived mathematics.
- Retired provisional F-101..F-114 formulas from the executable formula registry.
- Preserved the old F-101..F-114 identifiers only as deprecated compatibility metadata.
- Kept all work isolated to Adaptive Edge for Sterling Kite.

## Explicitly rejected as canonical

The earlier reconstructed model in `model.py` contained invented numerical weights and thresholds. Those values are **not** present in the Master Mathematical Specification and are no longer treated as canonical strategy mathematics.

Examples of rejected provisional assumptions include fixed feature weights, fixed confidence thresholds, fixed ATR stop multipliers, and a fixed target delta for option selection.

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
Risk Authorization
        |
        v
Position Sizing
        |
        v
Forward Management + Backward Profit Protection
        |
        v
Realistic Execution
```

## Current status

```text
SOURCE RECOVERY          COMPLETE
SOURCE TRACEABILITY      IMPLEMENTED
CORE MATH OPERATORS      IMPLEMENTED
ECONOMIC LAYER           IMPLEMENTED
RISK LAYER               IMPLEMENTED
PROTECTION LAYER         IMPLEMENTED
PROVISIONAL F-101..114   DEPRECATED

PROBABILITY TRAINING     NEXT
OPTION SELECTION         NEXT
STATE/EVENT INTEGRATION  NEXT
KITE HISTORICAL REPLAY   NEXT
OOS VALIDATION            BLOCKED UNTIL DATA RUN
PAPER                     BLOCKED UNTIL ROBUSTNESS GATE
LIVE                      BLOCKED
```

## Governing rule

No learned coefficient, probability threshold, calibration parameter, quantile, execution distribution, or risk allocation parameter will be invented merely to make the engine runnable. Those values must come from the specified walk-forward learning and validation process.
