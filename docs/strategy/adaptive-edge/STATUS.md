# Adaptive Edge — Current Status

## Canonical development branch

All active Adaptive Edge implementation work is consolidated on:

```text
feature/adaptive-edge-artifact-resolution
```

All previous Adaptive Edge feature branches were consolidated and removed from the remote repository. New Adaptive Edge changes must be made only on this branch.

## Source authority

The original Adaptive Edge artifacts are anchored to commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`, including the Master Mathematical Specification and supporting canonical specifications.

The Master Mathematical Specification is the sole authority for strategy mathematics and behavior. Provisional F-101..F-114 reconstruction is deprecated.

TrueData provider documentation is retained under `truedata-docs/` and is the source authority for TrueData transport/API semantics. It does not override Adaptive Edge strategy specifications.

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
SIMILARITY                   PARTIAL — EFFECTIVE-SAMPLE/SELECTION GATE UNFROZEN
BAYESIAN STATE               PARTIAL — INITIALIZATION/LEARNING UNFROZEN
ECONOMIC COST MODEL          PARTIAL — PROVIDER DISTRIBUTIONS UNRESOLVED
OPTION SELECTION             PARTIAL — CANDIDATE INPUT DERIVATION UNRESOLVED
TARGET/STOP EV               EXACT FOR SUPPLIED VALIDATED INPUTS
CONSERVATIVE EV              EXACT FOR SUPPLIED LCB
RISK PER UNIT                EXACT OPERATOR / STRATEGY SEMANTICS BLOCKED
POSITION SIZING              CONSTRAINT BOUNDARY IMPLEMENTED / EFFECTIVE-RISK SEMANTICS BLOCKED
CONTINUATION VALUE           EXACT OPERATOR
PROFIT PROTECTION            PARTIAL / LEARNED QUANTILE UNRESOLVED
MONOTONIC STOP               EXACT INVARIANT / UPSTREAM BOUNDARIES UNRESOLVED
NO RISK EXPANSION            EXACT INVARIANT
DYNAMIC MODE                 BLOCKED
ENTRY GATES                  BLOCKED — UPSTREAM DERIVATIONS
EXIT ORCHESTRATION           BLOCKED
STATE TRANSITIONS            BLOCKED
WALK-FORWARD DATA CONTRACT   IMPLEMENTED
PARAMETER FITTING            PARTIAL
A33 POSITION SIZING          CONSTRAINT FRAMEWORK IMPLEMENTED / SIZING FORMULA BLOCKED
A40 FEATURE LINEAGE          IMPLEMENTED
A41 PREDICTION CONTRACT      INTERFACE IMPLEMENTED
A42 DECISION UTILITY         INTERFACE IMPLEMENTED
A43 AUTHORIZATION STATE      FRAMEWORK IMPLEMENTED
A44 EXECUTION STATE          FRAMEWORK IMPLEMENTED
A45 ACCOUNTING RECONCILIATION FRAMEWORK IMPLEMENTED
A46 HISTORICAL REPLAY        FRAMEWORK IMPLEMENTED
A47 OOS CLAIM PROTECTION     FRAMEWORK IMPLEMENTED
A48 EVIDENCE AGGREGATION     FRAMEWORK IMPLEMENTED
A49 STATISTICAL UNCERTAINTY  FRAMEWORK IMPLEMENTED
A50 RESEARCH SELECTION       FRAMEWORK IMPLEMENTED
A51 FINAL HOLDOUT / CLAIM    FRAMEWORK IMPLEMENTED
A52 STATISTICAL VALIDITY     FRAMEWORK IMPLEMENTED / METHOD UNRESOLVED
A53 PROMOTION / CLAIM BOUNDARY FRAMEWORK IMPLEMENTED
A54 DEPLOYMENT GATE          FRAMEWORK IMPLEMENTED
A55 OPERATIONAL CONTROLS     FRAMEWORK IMPLEMENTED
A56 OPERATIONAL/TRADING STATE FRAMEWORK IMPLEMENTED
A57 RECOVERY / RESUME        FRAMEWORK IMPLEMENTED
A58 DECISION/AUTHORIZATION AUDIT CHAIN FRAMEWORK IMPLEMENTED
A59 EXECUTION BOUNDARY       FRAMEWORK IMPLEMENTED / PROVIDER SEMANTICS BLOCKED
A60 END-TO-END INVARIANT GATE FRAMEWORK IMPLEMENTED
A61 EXECUTION/ACCOUNTING INTEGRATION FRAMEWORK IMPLEMENTED

TRUEDATA DOCUMENTATION       RETAINED UNDER truedata-docs/
TRUEDATA ADAPTER             IMPLEMENTED FROM SUPPLIED DOCUMENTATION
HISTORICAL DATA              PARTIAL — PROVIDER SEMANTICS STILL CONSTRAINED
OOS VALIDATION               BLOCKED
PAPER                        BLOCKED
LIVE                         BLOCKED
```

## Consolidation rule

The canonical branch contains the latest usable Adaptive Edge implementation lineage plus source-defined A38/A39/A40 infrastructure, A41 prediction boundary, A42 economic-decision boundary, A43 authorization state-machine framework, A44 execution/reconciliation state-machine framework, A45 accounting-reconciliation framework, A46 deterministic replay framework, A47 out-of-sample claim-protection framework, A48 cycle-level evidence aggregation framework, A49 statistical-dependence/uncertainty framework, A50 research-selection/multiple-testing registry framework, A51 final-holdout/claim-assembly framework, A52 statistical-validity framework, A53 promotion/claim boundary framework, A54 deployment-gate framework, A55 operational-control framework, A56 operational/trading-state interaction framework, A57 recovery/resume framework, A58 decision/authorization audit-chain framework, A59 execution-boundary framework, A60 end-to-end invariant gate, A61 execution/accounting integration, the source-defined probability baseline, the source-supported normalization baseline, and the A33 quantity-constraint boundary. Where older branches conflicted, the later canonical implementation was retained and source-defined infrastructure was integrated without inventing strategy semantics.

## Governing rule

No learned coefficient, probability threshold, calibration parameter, quantile, execution distribution, risk allocation parameter, mode value, or transition rule will be invented merely to make the engine runnable.

## Current next resolution target

```text
Similarity — resolve the source-supported distance/weight operators
while keeping feature weights, neighborhood selection, and effective-
sample sufficiency explicitly parameterized/unfrozen.
```
