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
ECONOMIC COST MODEL          PARTIAL — V2.1 provider/accounting contract defined; empirical cost model remains research
OPTION SELECTION             PARTIAL — V2.1 causal candidate contract defined; numerical policy remains research
TARGET/STOP EV               EXACT FOR SUPPLIED VALIDATED INPUTS
CONSERVATIVE EV              EXACT FOR SUPPLIED LCB
RISK PER UNIT                PARTIAL IN ORIGINAL SOURCE / V2.1 semantics defined
POSITION SIZING              PARTIAL IN ORIGINAL SOURCE / V2.1 semantics defined
```

## V2.1 new-definition status

A26 recovery established that the original repository did not contain a unique complete opportunity/target/horizon definition. The V2.1 new-definition path is now documented rather than hidden inside implementation.

Canonical V2.1 specification closure:

```text
A26-ND  docs/strategy/adaptive-edge/v2/21_A26_ND_TARGET_HORIZON_LABEL_DEFINITION.md
A27-TD  docs/strategy/adaptive-edge/v2/22_A27_TRUEDATA_FIELD_LEVEL_FEATURE_CONTRACT.md
A28     docs/strategy/adaptive-edge/v2/23_A28_EDGE_PREDICTION_CONTRACT_V21.md
A29     docs/strategy/adaptive-edge/v2/24_A29_ECONOMIC_VALUE_EXECUTION_COST_CONTRACT_V21.md
A32     docs/strategy/adaptive-edge/v2/25_A32_EFFECTIVE_RISK_AUTHORIZATION_CONTRACT_V21.md
A34     docs/strategy/adaptive-edge/v2/26_A34_OPTION_CANDIDATE_SELECTION_CONTRACT_V21.md
A36     docs/strategy/adaptive-edge/v2/27_A36_POSITION_PROTECTION_AND_SQUARE_OFF_CONTRACT_V21.md
A37     docs/strategy/adaptive-edge/v2/28_A37_ACCOUNTING_PNL_RECONCILIATION_CONTRACT_V21.md
A38     docs/strategy/adaptive-edge/v2/29_A38_LABEL_MATURITY_LEARNING_DATASET_CONTRACT_V21.md
A39     docs/strategy/adaptive-edge/v2/30_A39_WALK_FORWARD_RESEARCH_PROMOTION_CONTRACT_V21.md
CLOSURE docs/strategy/adaptive-edge/v2/99_V21_CANONICAL_SPECIFICATION_CLOSURE.md
```

### V2.1 frozen target family

```text
Y_h ∈ {UP, DOWN, NEUTRAL}

Z(t,h) = Return(t,h) / sigma_t

UP       if Z > theta_h
DOWN     if Z < -theta_h
NEUTRAL  otherwise
```

The target is defined on the underlying/reference instrument and uses completed TrueData bar closes for deterministic historical reconstruction. No fixed horizon or threshold is invented; those are research quantities selected through the declared walk-forward process.

### V2.1 source boundary

```text
Adaptive Edge market/research data = TrueData only
Adaptive Edge trading/execution    = Zerodha Kite only
Kite fills                          = execution truth
Kite positions                      = broker position truth
Kite order-wise charges             = accounting charge source
```

No fallback market-data provider is permitted.

### V2.1 research architecture

```text
TrueData
 -> canonical state
 -> features
 -> calibrated directional probability
 -> economic option candidate evaluation
 -> risk authorization
 -> Kite order
 -> Kite fill
 -> Kite position/accounting
 -> future TrueData outcome
 -> mature label
 -> walk-forward learning
```

## Causal infrastructure status

The V2 causal infrastructure includes:

```text
A38  label maturity / outcome-learning boundary
A39  walk-forward evaluation architecture
A40  feature availability / snapshot / lineage architecture
A41  prediction / probability-calibration / decision-input interface
A42  economic value / expected value / decision-input interface
A43  decision / eligibility / risk-authorization state-machine framework
A44  order-intent / submission / fill / reconciliation framework
A45  accounting / execution reconciliation framework
A46  historical replay / deterministic state reconstruction
A47  out-of-sample claim-protection primitives
A48  cycle-level evaluation evidence aggregation
A49  statistical-dependence / uncertainty framework
A50  research-selection / multiple-testing registry
A51  final-holdout protection / claim assembly
A52  statistical-validity contract
A53  promotion / claim boundary
A54  deployment-readiness gate
A55  operational-control framework
A56  operational/trading-state interaction framework
A57  recovery/resume framework
A58  decision/authorization audit-chain framework
A59  execution-boundary framework
A60  end-to-end causal/safety invariant gate
A61  execution/accounting integration boundary
```

## Accounting integrity hardening

```text
backend/app/engines/adaptive_edge/accounting_integrity.py
```

enforces immutable source-event identity, currency/policy provenance, derived-effect lineage, causal timestamps, idempotent reprocessing, conflict rejection and correction/supersession lineage.

## Decision-operator closure

```text
backend/app/engines/adaptive_edge/decision_operators.py
```

implements the source-defined EV/ConservativeEV/entry-gate operators for supplied validated inputs without manufacturing missing strategy parameters.

## Global completeness gate

```text
backend/app/engines/adaptive_edge/completeness_gate.py
```

remains fail-closed. Software existence is not equivalent to semantic resolution or promotion.

## Critical status distinction

```text
CANONICAL SPECIFICATION    COMPLETE FOR V2.1 RESEARCH DEFINITION
IMPLEMENTATION             PARTIAL / EXISTING BOUNDARIES
LEARNED PARAMETERS         NOT YET EMPIRICALLY VALIDATED
TRUE-DATA DATASET          REQUIRED
KITE EXECUTION VALIDATION  REQUIRED
WALK-FORWARD VALIDATION    REQUIRED
PROMOTION                  NOT APPROVED
LIVE EXECUTION             BLOCKED
```

## Remaining work is evidence, not invented semantics

The remaining blockers are now empirical/operational:

```text
1. Acquire and version the entitled TrueData historical/live dataset.
2. Verify exact TrueData timestamp/availability semantics under the actual entitlement.
3. Freeze the actual research configuration before evaluation.
4. Run causal walk-forward experiments.
5. Select horizon/threshold/features/model/cost/risk parameters without holdout contamination.
6. Evaluate on untouched holdout.
7. Validate execution-cost sensitivity using Kite execution observations.
8. Validate risk capacity/drawdown and multi-position behavior.
9. Validate operational recovery and reconciliation.
10. Produce promotion evidence.
```

No numerical parameter may be promoted merely because it appears reasonable.

## Production gate

```text
SPECIFICATION COMPLETE
        AND
DATA SOURCE CONTRACT VERIFIED
        AND
CAUSAL WALK-FORWARD PASSES
        AND
HOLDOUT PASSES
        AND
COST/RISK SENSITIVITY PASSES
        AND
OPERATIONAL GATES PASS
        AND
PROMOTION APPROVED
        |
        v
LIVE AUTHORIZATION
```

Until then:

```text
LIVE_AUTHORIZATION = FALSE
```
