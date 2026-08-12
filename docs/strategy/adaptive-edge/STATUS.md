# Adaptive Edge — Current Status

## Current status

```text
SOURCE RECOVERY              COMPLETE
SOURCE TRACEABILITY          IMPLEMENTED
EXACTNESS AUDIT              COMPLETE

PRICE / VOLUME / DELTA MATH  EXACT FOR IMPLEMENTED OPERATORS
LIQUIDITY MATH               EXACT
NORMALIZATION                BASELINE EMPIRICAL CDF IMPLEMENTED / CONTEXT+MIN-DATA UNFROZEN
DIRECTIONAL PROBABILITY      BASELINE IMPLEMENTED / PARAMETERS UNFROZEN
LOGISTIC MODEL               PARTIAL — FITTING/OPTIMIZATION UNFROZEN
SIMILARITY                   PARTIAL — EFFECTIVE-SAMPLE/SELECTION GATE IMPLEMENTED / FULL PROCEDURE UNFROZEN
BAYESIAN STATE               PARTIAL — EXPLICIT STATE/DECAY BOUNDARY IMPLEMENTED / INITIALIZATION+LEARNING UNFROZEN
PROBABILITY CALIBRATION      BLOCKED — METHOD/PROTOCOL/PARAMETERS UNDEFINED
HORIZON DISTRIBUTION         BLOCKED — TARGET/HORIZON/DISTRIBUTION SEMANTICS UNDEFINED
ECONOMIC COST MODEL          PARTIAL — PROVIDER DISTRIBUTIONS UNRESOLVED
OPTION SELECTION             PARTIAL — CANDIDATE INPUT DERIVATION UNRESOLVED
TARGET/STOP EV               EXACT FOR SUPPLIED VALIDATED INPUTS
CONSERVATIVE EV              EXACT FOR SUPPLIED LCB
RISK PER UNIT                EXACT OPERATOR / STRATEGY SEMANTICS BLOCKED
POSITION SIZING              CONSTRAINT BOUNDARY IMPLEMENTED / EFFECTIVE-RISK SEMANTICS BLOCKED
```

## V2.1 new-definition implementation

A26 recovery established that the repository did not contain complete authoritative definitions for F-101..F-114. The repository's resolution protocol permits a new versioned strategy definition as the alternative unlock path.

That path is now implemented as:

```text
A26-ND
Version: 2.1.0-proposed
Status: PROPOSED / RESEARCH-ONLY
```

The implementation is:

```text
backend/app/engines/adaptive_edge/strategy_v21.py
backend/tests/engines/adaptive_edge/test_strategy_v21.py
backend/app/engines/adaptive_edge/promotion.py
```

The following formula family is implemented and registered under version 2.1.0:

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

## Critical status distinction

```text
FORMULAS IMPLEMENTED       YES
STRATEGY DEFINITION        PROPOSED
WALK-FORWARD VALIDATION    REQUIRED
PROMOTION                  NOT APPROVED
EXECUTION                  BLOCKED
```

Implementation does not imply that the proposed parameters are optimal or economically validated.

The production readiness gate now requires both:

```text
all F-101..F-114 = IMPLEMENTED
AND
strategy promotion = APPROVED
```

The current promotion state is `RESEARCH_ONLY`, so Adaptive Edge remains non-executable.

## Research configuration

The initial V2.1 configuration is explicitly versioned in `StrategyParameters`. It includes the initial research horizon, normalization parameters, edge threshold, mode thresholds, risk multipliers, protection parameters, re-entry constraints, and portfolio constraints.

These are research parameters, not recovered historical constants.

## Next validation gate

```text
1. Run the complete Adaptive Edge test suite.
2. Run walk-forward evaluation over historical data.
3. Evaluate parameter sensitivity without test leakage.
4. Evaluate execution-cost sensitivity.
5. Protect the final holdout.
6. Produce a validation report and candidate identity.
7. Explicitly approve promotion only if the pre-declared promotion policy passes.
8. Only then may the execution gate become authorized.
```

No production trade authorization is implied by this implementation commit.
