# Adaptive Edge — Design

## Layer ownership

```text
FeatureLayer
  pure transformations from causally available market observations

EdgeLayer
  strategy-specific prediction/opportunity computation

EconomicEvaluation
  gross opportunity -> execution costs -> expected net value

ModePolicy
  strategy behavior/state transition

RiskAuthorization
  explicit loss budget authorization

Sizing
  converts authorized risk into quantity under instrument constraints

Execution
  creates intent only; broker/router determines actual execution
```

## Formula-first implementation rule

The canonical formula registry is the boundary between specification and code:

```text
canonical formula ID
        |
        v
formula_registry.py
        |
        +--> implementation
        +--> tests
        +--> audit/provenance
        +--> UI explanation
```

A formula is executable only when its registry status is `IMPLEMENTED` and its
implementation version equals the registry version. Locked formula IDs fail
closed.

## Feature -> Edge -> Economic Evaluation contract

The implementation must preserve this exact dependency direction:

```text
FeatureSnapshot
      |
      | formula_ids
      v
EdgeAssessment
      |
      | formula_id + formula_version
      v
EconomicAssessment
      |
      | F-004
      v
DecisionCandidate
```

No feature module may call execution. No economic module may mutate risk authorization. No UI component may calculate strategy formulas.

## FeatureSnapshot

The snapshot carries timestamps for its inputs so causal availability can be checked, plus formula provenance:

```text
observation_time
feature_values
source timestamps
formula_ids
quality/staleness metadata
instrument context
```

## EdgeAssessment

Contract:

```text
prediction / opportunity
confidence or score
expected gross value inputs
explanation / feature provenance
formula_id + formula_version
```

F-102 remains locked until recovered.

## EconomicAssessment

Contract:

```text
expected_gross_value
expected_execution_cost
expected_net_value
eligible
reason_codes
formula_id + formula_version
```

Canonical equation: F-004.

## Risk boundary

Economic eligibility is not authorization.

```text
eligible == true
    does not mean
risk_authorized == true
```

## Test architecture

Every layer gets:

1. deterministic unit tests
2. boundary tests
3. causal/lookahead tests
4. monotonicity tests where mathematically applicable
5. integration contract tests
6. backtest/live parity tests
