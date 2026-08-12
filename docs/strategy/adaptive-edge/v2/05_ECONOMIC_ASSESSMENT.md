# Adaptive Edge V2 — Economic Assessment and Eligibility Definition

**Version:** 2.0.0-draft
**Artifact:** A29
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Depends on:** A25, A26, A27, A28
**Implementation authorization:** NONE

## 1. Purpose

A29 defines the boundary between predictive information and the economic decision to consider an opportunity eligible for trading.

The causal boundary is:

```text
FeatureSnapshot(t_d)
      -> Prediction(t_d)
      -> EconomicAssessment(t_d)
      -> Eligibility(t_d)
      -> RiskAuthorization
```

Every pre-trade input must be available at `decision_time`. Future fills, realized P&L, mature labels, or future market observations cannot influence contemporaneous eligibility.

## 2. Frozen economic relationship

The existing canonical relationship is:

```text
ExpectedNetValue
    = ExpectedGrossValue - ExpectedExecutionCost
```

A29 preserves this relationship and does not invent the definitions of its components.

## 3. Canonical object

```text
EconomicAssessment
{
    assessment_id
    opportunity_id
    strategy_version
    decision_time
    prediction_reference
    instrument_reference
    execution_cost_model_version
    expected_gross_value
    expected_execution_cost
    expected_net_value
    eligibility_result
    rejection_reason_codes
    provenance
}
```

The assessment is immutable for the decision it represents.

## 4. Expected gross value

`ExpectedGrossValue` means the model-implied expected economic value before execution costs.

Conceptually:

```text
ExpectedGrossValue
    = E[GrossEconomicOutcome | information available at t_d]
```

The exact random variable is currently UNKNOWN because A26 has not resolved the target/horizon and the instrument/payoff mapping is not yet frozen.

A mathematically valid expectation is not sufficient to authorize implementation.

## 5. Expected execution cost

`ExpectedExecutionCost` represents pre-trade expected cost. Potential components may include spread, slippage, fees, commissions, exchange charges, or other documented costs, but none is automatically included.

Every component requires:

```text
source
semantic definition
unit
timestamp/availability
estimation method
version
```

Actual future fill/slippage cannot be used as the contemporaneous estimate.

Historical cost parameters may be learned only under the later temporal learning protocol.

## 6. Dimensional consistency

`ExpectedGrossValue`, `ExpectedExecutionCost`, and `ExpectedNetValue` must have identical economic units before subtraction.

The following is invalid without an explicit conversion:

```text
ExpectedGrossValue = points
ExpectedExecutionCost = currency
```

No final unit is frozen until target and contract economics are resolved.

## 7. Contract/payoff dependency

Converting a prediction into option economics requires a time-valid contract definition, potentially including:

```text
underlying
strike
expiry
option_type
contract_multiplier
entry semantics
exit semantics
payoff definition
```

Those semantics are not invented here. Instrument and execution artifacts must establish them first.

## 8. Probability is not value

If the eventual prediction is:

```text
p = P(Y = 1 | X)
```

then `p` is not monetary value. A payoff/state mapping is required.

Likewise, a regression prediction is not automatically currency, points, or return percentage. Its target unit must be explicitly defined.

## 9. Eligibility

The architectural rule is:

```text
Eligible(t_d)
    = EconomicAssessment(t_d)
      satisfies StrategyEligibilityPolicy(version)
```

No threshold is invented. In particular, none of the following is currently authorized:

```text
ExpectedNetValue > 0
ExpectedNetValue > fixed currency amount
ExpectedNetValue > cost * arbitrary multiple
```

A threshold, if required, is a versioned strategy parameter and must have a validation population, temporal validation boundary, update frequency, and promotion rule.

## 10. Failure states

The economic layer must distinguish at least:

```text
ELIGIBLE
INELIGIBLE
INSUFFICIENT_INFORMATION
INVALID_ECONOMICS
STALE_INPUT
```

Missing economic information must not silently become zero cost, zero value, or an optimistic default.

## 11. Pre-trade versus realized economics

```text
ExpectedNetValue != RealizedNetValue
```

The pre-trade assessment is an expectation. Realized economics are produced later from authoritative execution/accounting state and cannot rewrite the original assessment.

## 12. Parameter classes

### Frozen architecture

```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

### Source-defined configuration

Semantics supplied by authoritative strategy/instrument/execution documentation.

### Learned parameters

Historical estimates governed by the later temporal learning protocol.

### Strategy thresholds

Explicit eligibility parameters requiring validation and versioning.

No numerical value is selected merely to complete a formula.

## 13. Attack

### Look-ahead

Future price, spread, liquidity, fill, exit, or P&L entering pre-trade economics is forbidden.

### Cost leakage

Actual future fill/slippage cannot define its own pre-trade cost estimate.

### Circularity

Forbidden base dependency:

```text
EconomicEligibility -> target -> prediction -> EconomicEligibility
```

### Threshold overfitting

A threshold selected using final-test performance is invalid.

### Multiple testing

Testing many targets, horizons, cost models, payoff definitions, or thresholds and selecting the best on the final test period is invalid.

### Unit mismatch

Economically incompatible units cannot be combined without an explicit conversion.

### Contract hindsight

A future-selected strike/expiry cannot be used to construct historical economic value.

### Missing/stale data

Missing or stale inputs require explicit policy; they cannot silently become favorable values.

### Risk contamination

Economic eligibility does not silently increase risk authorization.

```text
EconomicEligibility -> RiskAuthorization
```

not:

```text
higher edge -> hidden risk multiplier
```

## 14. Current production-authorized mathematics

Only this relationship is frozen:

```text
ExpectedNetValue
    = ExpectedGrossValue - ExpectedExecutionCost
```

All three quantities remain subject to complete semantic definitions before implementation.

## 15. Dependencies

```text
A26  -> target/horizon semantics
A28  -> prediction semantics
Instrument artifact -> contract/payoff/unit semantics
Execution artifact -> executable price/cost semantics
Learning artifact -> learned cost/threshold validation
```

## 16. Current state

```text
ExpectedGrossValue definition    = UNKNOWN
ExpectedExecutionCost definition = PARTIAL
ExpectedNetValue unit            = UNKNOWN
payoff mapping                   = UNKNOWN
eligibility threshold            = UNKNOWN
cost-model parameters            = UNKNOWN
option-specific economics        = UNKNOWN
```

## 17. Completion criterion

A29 becomes RESOLVED only when:

```text
prediction -> economic variable mapping
+ payoff semantics
+ execution-cost semantics
+ units
+ availability boundaries
+ eligibility policy
+ threshold validation methodology
+ provenance/versioning
```

are explicitly defined and survive dimensional, causal, statistical, and execution attack.

## ARCHITECTURE STATUS

**FROZEN**

```text
prediction/economics separation
ExpectedNetValue relationship
pre-trade economic boundary
cost-model provenance
unit-consistency requirement
explicit insufficient-information state
threshold versioning
no hidden risk coupling
```

**UNRESOLVED**

```text
primary economic target
payoff mapping
exact execution-cost model
units
eligibility threshold
option economics
learned cost parameters
```

**BLOCKERS**

A29 cannot be fully resolved until A26/A28 resolve target and prediction semantics and the later instrument/execution contracts resolve exact economic mapping.

The architectural relationship itself is not blocked.

## NEXT ARTIFACT

**A30 — Operating Mode and Eligibility State Machine**

A30 will define the state machine from a causally valid economic assessment to operating-mode/eligibility state without silently coupling prediction magnitude to risk authorization.
