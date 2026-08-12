# Adaptive Edge — Current Status

## Original-source status

The original Master Mathematical Specification remains the authority for recovered historical semantics. Several strategy-specific quantities remain unresolved in that original source.

```text
SOURCE RECOVERY              COMPLETE
SOURCE TRACEABILITY          IMPLEMENTED
EXACTNESS AUDIT              COMPLETE

PRICE / VOLUME / DELTA MATH  EXACT FOR IMPLEMENTED OPERATORS
LIQUIDITY MATH               EXACT
NORMALIZATION                PARTIAL — baseline empirical CDF implemented
DIRECTIONAL PROBABILITY      PARTIAL — baseline empirical probability implemented
LOGISTIC MODEL               PARTIAL IN ORIGINAL SOURCE / V2.1 FITTER IMPLEMENTED
SIMILARITY                   PARTIAL — source-specific selection procedure unresolved
BAYESIAN STATE               PARTIAL — source-specific initialization/learning unresolved
PROBABILITY CALIBRATION      BLOCKED IN ORIGINAL SOURCE / V2.1 TEMPERATURE SCALING IMPLEMENTED
HORIZON DISTRIBUTION         BLOCKED IN ORIGINAL SOURCE / V2.1 EMPIRICAL HORIZON IMPLEMENTED
ECONOMIC COST MODEL          PARTIAL — provider distributions unresolved
OPTION SELECTION             PARTIAL — candidate generation unresolved
TARGET/STOP EV               EXACT FOR SUPPLIED VALIDATED INPUTS
CONSERVATIVE EV              EXACT FOR SUPPLIED LCB
RISK PER UNIT                PARTIAL IN ORIGINAL SOURCE / V2.1 SEMANTICS IMPLEMENTED
POSITION SIZING              PARTIAL IN ORIGINAL SOURCE / V2.1 SEMANTICS IMPLEMENTED
```

## V2.1 new-definition implementation

A26 recovery established that the repository did not contain complete authoritative definitions for F-101..F-114. The repository's resolution protocol permits a new versioned strategy definition as the alternative unlock path.

```text
A26-ND
Version: 2.1.0-proposed
Status: PROPOSED / RESEARCH-ONLY
```

Implemented strategy modules:

```text
backend/app/engines/adaptive_edge/strategy_v21.py
backend/app/engines/adaptive_edge/parameter_fitting.py
backend/app/engines/adaptive_edge/calibration.py
backend/app/engines/adaptive_edge/horizon_distribution.py
backend/app/engines/adaptive_edge/promotion.py
```

Formula family:

```text
F-101  weighted normalized feature score
F-102  three-state directional edge
F-103  causal opportunity eligibility
F-104  volatility/drawdown operating mode
F-105  monotonic profit protection
F-106  dynamic risk schedule
F-107  protection-and-cost risk per unit
F-108  increment-aligned position sizing
F-109  directional option selection
F-110  directional entry trigger
F-111  protection/target/horizon exit
F-112  protection parameterization
F-113  cooldown/new-opportunity re-entry
F-114  shared-risk multi-position constraint
```

Research infrastructure now additionally includes:

```text
multinomial logistic batch fitting
L2 regularization
validation-only temperature calibration
empirical horizon distribution
empirical quantile extraction
```

## Critical status distinction

```text
FORMULAS IMPLEMENTED       YES
STRATEGY DEFINITION        PROPOSED
WALK-FORWARD VALIDATION    REQUIRED
PROMOTION                  NOT APPROVED
EXECUTION                  BLOCKED
```

The production readiness gate requires:

```text
all F-101..F-114 = IMPLEMENTED
AND
strategy promotion = APPROVED
```

The current promotion state is `RESEARCH_ONLY`, so Adaptive Edge remains non-executable.

## Research configuration

The initial V2.1 configuration is explicitly versioned in `StrategyParameters`. Numerical values are research configuration, not recovered historical constants.

## Validation gate

```text
1. Run complete Adaptive Edge tests.
2. Fit only on causal TRAIN partitions.
3. Calibrate only on VALIDATION partitions.
4. Evaluate on untouched HOLDOUT data.
5. Evaluate execution-cost sensitivity.
6. Evaluate parameter sensitivity and multiple-testing controls.
7. Produce a versioned validation report.
8. Explicitly approve promotion only if the pre-declared promotion policy passes.
9. Only then may the execution gate become authorized.
```

No production trade authorization is implied by the V2.1 implementation.
