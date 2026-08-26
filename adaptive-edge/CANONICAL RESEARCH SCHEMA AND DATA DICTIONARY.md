# CANONICAL RESEARCH SCHEMA AND DATA DICTIONARY

## Canonical Field Registry — Version 1.0

## 1. Purpose

This registry defines every variable that can exist in the research and trading system.

Every variable must have exactly one canonical definition.

The system must never have two different variables representing the same concept.

The fundamental rule is:

```text
ONE CONCEPT
    =
ONE CANONICAL VARIABLE
    =
ONE DEFINITION
    =
ONE OWNER
```

---

# 2. Variable Classes

Every variable belongs to exactly one primary class:

```text
OBSERVED
DERIVED
STATE
FEATURE
LABEL
MODEL_PARAMETER
DECISION
POSITION
EXECUTION
METRIC
CONFIGURATION
```

These classifications are not interchangeable.

---

# 3. Temporal Classification

Every variable also has a temporal status:

```text
CAUSAL_AT_T
KNOWN_BEFORE_T
KNOWN_AFTER_T
FUTURE_LABEL
STATIC_METADATA
```

A runtime decision may only consume:

```text
CAUSAL_AT_T
KNOWN_BEFORE_T
STATIC_METADATA
```

---

# 4. Naming Convention

Canonical variables use semantic names.

For example:

```text
timestamp
instrument_id
last_price
bid_price
ask_price
spread
realized_volatility
predicted_up_probability
predicted_down_probability
expected_net_value
```

We do not create ambiguous names such as:

```text
value1
range2
profit_new
atr_final
signal_temp
```

---

# 5. Identifier

Every canonical variable receives a permanent:

`VariableID`.

Example:

```text
VAR.MKT.LAST_PRICE
VAR.MKT.BID_PRICE
VAR.FEAT.REALIZED_VOL
VAR.MODEL.P_UP
VAR.DECISION.ACTION
```

The exact identifier convention can be refined, but the principle is mandatory.

---

# 6. Ownership

Every variable has exactly one owner domain.

For example:

```text
last_price
    -> MarketData

realized_volatility
    -> FeatureEngine

predicted_up_probability
    -> ProbabilityModel

expected_net_value
    -> EconomicDecisionEngine

protected_stop
    -> RiskState
```

No two modules independently redefine the same canonical quantity.

---

# 7. Source Classification

Each variable records:

```text
SOURCE_TYPE
```

with values:

```text
TRUE_DATA
DERIVED
MODEL
STATE_MACHINE
EXECUTION
RESEARCH_LABEL
STATIC_METADATA
```

---

# 8. Core Market Variables

The foundational observed variables are:

```text
timestamp
instrument_id
event_type
last_price
bid_price
ask_price
trade_quantity
cumulative_volume
open_interest
```

Actual availability remains a TrueData documentation TODO.

---

# 9. Timestamp

Canonical name:

`timestamp`

Definition:

The exact canonical event timestamp.

Class:

`OBSERVED`

Temporal status:

`CAUSAL_AT_T`

Unit:

`absolute timestamp`

Precision:

`source-dependent`

Dependency:

`source event`

---

# 10. Session Date

Canonical name:

`session_date`

Definition:

Trading session associated with the event.

Class:

`DERIVED`

Dependency:

`timestamp + exchange calendar`

---

# 11. Session Phase

Canonical name:

`session_phase`

Definition:

The deterministic classification of the current timestamp within the trading session.

Examples:

```text
OPEN
EARLY
MID
LATE
CLOSE
```

These labels are conceptual.

Their actual boundaries must not yet be hardcoded.

---

# 12. Instrument ID

Canonical name:

`instrument_id`

Definition:

Unique canonical identity of the traded instrument.

Class:

`OBSERVED / NORMALIZED`

Dependency:

`source instrument identity`

---

# 13. Instrument Type

Canonical name:

`instrument_type`

Possible conceptual values:

```text
INDEX
EQUITY
FUTURE
OPTION
```

---

# 14. Option Type

Canonical name:

`option_type`

Possible values:

```text
CE
PE
```

Only applicable to options.

---

# 15. Strike

Canonical name:

`strike_price`

Class:

`OBSERVED / STATIC_METADATA`

For an option:

```text
strike_price
```

is fixed throughout the contract lifecycle.

---

# 16. Expiry

Canonical name:

`expiry_timestamp`

Class:

`STATIC_METADATA`

Temporal status:

`KNOWN_BEFORE_T`

At time `t`:

```text
time_to_expiry
=
expiry_timestamp - timestamp
```

is therefore causal.

---

# 17. Last Price

Canonical name:

`last_price`

Definition:

Most recent valid traded price available at timestamp `t`.

Class:

`OBSERVED`

---

# 18. Bid Price

Canonical name:

`bid_price`

Definition:

Best valid bid available at `t`.

Class:

`OBSERVED`

---

# 19. Ask Price

Canonical name:

`ask_price`

Definition:

Best valid ask available at `t`.

Class:

`OBSERVED`

---

# 20. Mid Price

Canonical name:

`mid_price`

Definition:

```text
mid_price
=
(bid_price + ask_price) / 2
```

only when both sides are valid.

Class:

`DERIVED`

---

# 21. Spread

Canonical name:

`spread`

Definition:

```text
spread
=
ask_price - bid_price
```

only when:

```text
bid_price <= ask_price
```

and both are valid.

---

# 22. Relative Spread

Canonical name:

`relative_spread`

Definition:

```text
relative_spread
=
spread / mid_price
```

provided:

`mid_price > 0`.

---

# 23. Trade Quantity

Canonical name:

`trade_quantity`

Definition:

Quantity associated with the observed trade event.

Class:

`OBSERVED`

---

# 24. Volume

Canonical name:

`volume`

Definition must explicitly distinguish:

`event volume`

from:

`session cumulative volume`.

Therefore these are separate canonical variables.

---

# 25. Event Volume

Canonical:

`event_volume`

Definition:

Quantity associated with the current event.

---

# 26. Session Volume

Canonical:

`session_volume`

Definition:

Cumulative valid volume within the current trading session according to the source semantics.

---

# 27. Open Interest

Canonical:

`open_interest`

Class:

`OBSERVED`

Important distinction:

```text
volume != open_interest
```

They must never be substituted.

---

# 28. Depth Variables

If available, canonical depth variables include:

```text
bid_depth_1
ask_depth_1
bid_depth_2
ask_depth_2
...
```

or a normalized depth representation.

The final structure depends on the actual TrueData feed.

---

# 29. Total Visible Bid Depth

Canonical:

`visible_bid_depth`

Definition:

Sum of valid bid quantities across the configured observable depth levels.

The configured depth range remains empirical/source-dependent.

---

# 30. Total Visible Ask Depth

Canonical:

`visible_ask_depth`

Definition:

Sum of valid ask quantities across the configured observable depth levels.

---

# 31. Depth Imbalance

Canonical:

`depth_imbalance`

Definition:

```text
depth_imbalance
=
(
visible_bid_depth - visible_ask_depth
)
/
(
visible_bid_depth + visible_ask_depth
)
```

only when denominator is positive.

---

# 32. Price Return

Canonical:

`return`

Definition depends on the selected interval.

For interval `[t-L,t]`:

```text
return_L
=
price_t / price_(t-L) - 1
```

The interval must always be explicit.

---

# 33. Log Return

Canonical:

`log_return_L`

Definition:

```text
log_return_L
=
ln(price_t / price_(t-L))
```

---

# 34. Price Velocity

Canonical:

`price_velocity`

Definition:

Change in price normalized by elapsed time.

Conceptually:

```text
price_velocity
=
(price_t - price_(t-L)) / L
```

---

# 35. Price Acceleration

Canonical:

`price_acceleration`

Definition:

Change in velocity over time.

The exact estimator will be selected during feature research.

---

# 36. Realized Volatility

Canonical:

`realized_volatility_L`

Definition:

A volatility estimator calculated solely from observations available within the specified historical window.

The exact estimator is deliberately not frozen yet.

---

# 37. Range

Canonical:

`range_L`

Definition:

```text
range_L
=
max(price)
-
min(price)
```

within the explicitly defined interval.

---

# 38. Range Normalization

Canonical:

`normalized_range_L`

Conceptually:

```text
normalized_range_L
=
range_L / reference_price
```

The reference price must be explicitly defined.

---

# 39. Volatility Regime

Canonical:

`volatility_regime`

This is a model/feature classification derived from historical volatility information.

It is not an observed market field.

---

# 40. Volatility Regime Probability

Canonical:

`volatility_regime_probability`

Instead of forcing:

```text
LOW
NORMAL
HIGH
```

the model may retain a probability distribution:

```text
P(LOW)
P(NORMAL)
P(HIGH)
P(EXTREME)
```

if validated.

---

# 41. Directional Probability

The core model variables are:

```text
p_up
p_down
p_neutral
```

with:

```text
p_up + p_down + p_neutral = 1
```

subject to numerical tolerance.

---

# 42. Probability Support

Every probability estimate must also carry:

`probability_support`.

This represents the amount and quality of historical evidence supporting the estimate.

---

# 43. Probability Uncertainty

Canonical:

`probability_uncertainty`

The exact statistical representation depends on the selected estimator.

---

# 44. Probability Calibration

Canonical:

`calibrated_p_up`

and:

`calibrated_p_down`.

The calibration transformation is itself a versioned model component.

---

# 45. Horizon Distribution

The system must not maintain only:

`expected_horizon`.

Instead the canonical representation is:

```text
horizon_distribution
```

from which quantities such as:

```text
horizon_median
horizon_quantile
horizon_probability_under_h
```

may be derived.

---

# 46. Expected Horizon

Canonical:

`expected_horizon`

Definition:

Expected value of the validated opportunity-persistence distribution.

Important:

```text
expected_horizon
```

is not identical to:

```text
projected_trade_duration
```

---

# 47. Projected Trade Duration

We eliminate this as an independent canonical variable.

Reason:

It overlaps semantically with horizon.

The strategy uses:

`opportunity persistence`

as the canonical concept.

---

# 48. Mode

Canonical:

`trade_mode`

Possible states:

```text
MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

The mode is derived from:

`horizon distribution`

and:

`current state`.

It is descriptive, not risk-authorizing.

---

# 49. Mode Confidence

Canonical:

`mode_confidence`

Measures evidence supporting the current mode.

---

# 50. Mode Transition Evidence

Canonical:

`mode_transition_score`

Measures evidence that the current mode should change.

---

# 51. Gross Expected Return

Canonical:

`expected_gross_return`

Definition:

Expected favorable economic return before transaction costs.

---

# 52. Expected Execution Cost

Canonical:

`expected_execution_cost`

Includes the validated execution-cost components applicable to the candidate trade.

---

# 53. Expected Net Value

Canonical:

`expected_net_value`

Definition:

```text
expected_net_value
=
expected_gross_return
-
expected_execution_cost
```

Any additional explicitly modeled costs must be included here.

---

# 54. Net Return Distribution

Canonical:

`net_return_distribution`

This is more fundamental than:

`expected_net_return`.

The expected value is derived from the distribution.

---

# 55. Probability of Positive Net Return

Canonical:

`p_positive_net_return`

Definition:

```text
P(NetReturn > 0 | State_t)
```

---

# 56. Downside Quantile

Canonical:

`net_return_downside_quantile`

The exact quantile is learned/selected during validation.

It must not be permanently hardcoded at architecture level.

---

# 57. Maximum Favorable Excursion

Canonical:

`future_mfe`

Class:

`LABEL`

Temporal status:

`FUTURE_LABEL`

Definition:

Maximum favorable movement after the decision timestamp within the label horizon.

---

# 58. Maximum Adverse Excursion

Canonical:

`future_mae`

Class:

`LABEL`

Definition:

Maximum adverse movement after decision within the relevant label horizon.

---

# 59. Peak Profit

Canonical:

`peak_unrealized_profit`

Class:

`STATE`

This is different from:

`future_mfe`.

`future_mfe` describes what eventually happened historically.

`peak_unrealized_profit` describes what the live position has achieved so far.

---

# 60. Current Unrealized P&L

Canonical:

`unrealized_pnl`

This is the current mark-to-market value of the open position.

It is a state variable.

---

# 61. Current Profit

We eliminate:

`current_profit`

as a separate canonical variable.

Reason:

It duplicates the economic meaning of:

`unrealized_pnl`.

Therefore:

```text
current_profit
        X
```

is not permitted.

---

# 62. Realized P&L

Canonical:

`realized_pnl`

Once realized:

it is immutable for that completed position/trade.

---

# 63. Peak Profit

Canonical:

`peak_unrealized_pnl`

Definition:

```text
peak_unrealized_pnl_(t)
=
max(
    peak_unrealized_pnl_(t-1),
    unrealized_pnl_t
)
```

for an open position.

---

# 64. Giveback

Canonical:

`profit_giveback`

Definition:

```text
profit_giveback
=
peak_unrealized_pnl
-
unrealized_pnl
```

when peak profit is positive.

---

# 65. Giveback Ratio

Canonical:

`profit_giveback_ratio`

Definition:

```text
profit_giveback_ratio
=
giveback / peak_unrealized_pnl
```

when peak profit is positive.

---

# 66. Protected Profit Floor

Canonical:

`protected_profit_floor`

This is a live risk-state variable.

It represents the minimum permitted economic outcome under the active protection state.

---

# 67. Protected Stop

Canonical:

`protected_stop_price`

This is the actual price boundary corresponding to the current protection policy.

---

# 68. Initial Risk Boundary

Canonical:

`initial_risk_boundary`

This is determined when the position is opened.

It is not automatically equivalent to:

`ATR × constant`.

---

# 69. Maximum Permitted Loss

Canonical:

`maximum_permitted_loss`

This is the risk boundary applicable to the position.

---

# 70. Risk Remaining

Canonical:

`remaining_risk`

Conceptually:

```text
remaining_risk
=
maximum_permitted_loss
-
realized/protected risk state
```

The exact mathematical definition will be finalized with the risk-state specification.

---

# 71. Continuation Value

Canonical:

`continuation_value`

Definition:

Expected incremental economic value of continuing the current position rather than exiting now.

This is one of the central variables in the dynamic exit system.

---

# 72. Exit Value

Canonical:

`exit_value`

Economic value of terminating the position under current execution conditions.

---

# 73. Continue Versus Exit

The decision compares:

```text
continuation_value
```

against:

```text
exit_value
```

subject to protection invariants.

---

# 74. Emergency Reversal Evidence

Canonical:

`reversal_evidence`

Measures validated evidence that the directional thesis has materially deteriorated.

---

# 75. Trade Eligibility

Canonical:

`trade_eligible`

Boolean:

```text
TRUE
FALSE
```

It is a derived decision gate.

---

# 76. Direction Decision

Canonical:

`direction_decision`

Possible values:

```text
NONE
UP
DOWN
```

---

# 77. Option Decision

Canonical:

`option_decision`

Possible values:

```text
NONE
CE
PE
```

---

# 78. Final Action

Canonical:

`action`

Possible values:

```text
NO_TRADE
BUY_CE
BUY_PE
EXIT
HOLD
```

Additional actions may exist in the execution layer, but these are the strategy-level actions.

---

# 79. Option Candidate Score

Canonical:

`option_economic_score`

Each candidate option receives a score derived from:

`net-return distribution`

`liquidity`

`execution`

`risk`

and:

`directional compatibility`.

---

# 80. Selected Option

Canonical:

`selected_option_id`

This is a decision output.

---

# 81. Position Size

Canonical:

`position_quantity`

Determined by:

`validated risk capacity`

`candidate risk`

`option contract constraints`

and:

`execution constraints`.

---

# 82. Position Risk

Canonical:

`position_risk`

Represents the estimated risk associated with the selected quantity.

---

# 83. Risk Capacity

Canonical:

`risk_capacity`

Represents the maximum risk the current portfolio/account state permits.

---

# 84. Position State

Canonical:

`position_state`

Values:

```text
FLAT
LONG
SHORT
```

Any transitional states must be explicitly defined.

---

# 85. Entry Timestamp

Canonical:

`entry_timestamp`

Immutable once the position is opened.

---

# 86. Entry Price

Canonical:

`entry_price`

The actual or simulated executable entry price.

It must not be confused with:

`signal_price`.

---

# 87. Signal Price

Canonical:

`signal_price`

The market price observed when the strategy generated the decision.

---

# 88. Exit Timestamp

Canonical:

`exit_timestamp`

Immutable after exit.

---

# 89. Exit Price

Canonical:

`exit_price`

Actual or simulated executable exit price.

---

# 90. Holding Time

Canonical:

`holding_time`

Definition:

```text
holding_time
=
exit_timestamp - entry_timestamp
```

This is an observed realized quantity after exit.

It is not the same as:

`expected_horizon`.

---

# 91. Expected Horizon Versus Holding Time

This distinction is now explicit:

```text
expected_horizon
=
forecast

holding_time
=
realized outcome
```

They must never be merged.

---

# 92. Slippage

Canonical:

`realized_slippage`

This belongs to the execution/outcome layer.

Expected slippage belongs to:

`expected_execution_cost`.

---

# 93. Expected Slippage

Canonical:

`expected_slippage`

A model estimate before execution.

---

# 94. Execution Quality

Canonical:

`execution_quality`

A post-execution metric comparing:

`expected execution`

against:

`actual execution`.

---

# 95. Capability State

Canonical:

`capability_state`

Values:

```text
FULL
PARTIAL
DEGRADED
UNUSABLE
```

---

# 96. Data Quality State

Canonical:

`data_quality_state`

Values:

```text
VALID
PARTIAL
INVALID
UNKNOWN
```

---

# 97. Model Version

Canonical:

`model_version`

Every decision must identify the exact model version used.

---

# 98. Feature Version

Canonical:

`feature_version`

Every decision must identify the exact feature definition.

---

# 99. Label Version

Canonical:

`label_version`

Used in historical research only.

---

# 100. Execution Model Version

Canonical:

`execution_model_version`

Identifies the execution assumptions used.

---

# 101. Dataset Version

Canonical:

`dataset_version`

Identifies the exact underlying data.

---

# 102. Decision ID

Canonical:

`decision_id`

Unique identifier for a strategy decision opportunity.

---

# 103. Trade ID

Canonical:

`trade_id`

Unique identifier for an actual position lifecycle.

One trade may contain multiple decisions/state transitions.

---

# 104. Event ID

Canonical:

`event_id`

Unique identifier for the source/normalized event.

---

# 105. Model Parameters

Model parameters are not ordinary variables.

They belong to:

`MODEL_PARAMETER`.

Each parameter requires:

```text
parameter_id
value
estimation_method
training_period
validation_period
confidence/uncertainty
model_version
```

---

# 106. Learned Parameter Rule

No learned parameter can enter production unless it has:

```text
training evidence
validation evidence
out-of-sample evidence
version
lineage
```

---

# 107. Fixed Configuration

Configuration values are distinct from learned parameters.

Examples may include:

`market calendar`

`instrument universe`

`maximum operational time`

`data safety constraints`.

They are not allowed to masquerade as learned quantities.

---

# 108. Strategy-Defining Versus Operational Constraints

We distinguish:

```text
STRATEGY
```

from:

```text
OPERATIONAL
```

For example:

"Do not initiate new positions after the configured Indian-market cutoff"

is an operational constraint.

The exact cutoff remains a strategy specification decision and should not be confused with learned market behavior.

---

# 109. Label Variables

The label registry includes:

```text
future_return
future_mfe
future_mae
future_horizon
future_net_return
future_max_drawdown
future_option_return
future_execution_outcome
```

Each requires its own:

`maturity rule`.

---

# 110. Label Horizon

Every label must have:

`label_horizon_definition`.

It cannot simply say:

"future."

---

# 111. Label Maturity

Canonical:

`label_maturity_timestamp`

This determines when the label becomes legally usable for training.

---

# 112. Evidence Count

Canonical:

`effective_sample_size`

This is distinct from:

`raw_observation_count`.

---

# 113. Observation Count

Canonical:

`observation_count`

Raw number of observations contributing to an estimate.

---

# 114. Effective Sample Size

Canonical:

`effective_sample_size`

Accounts for dependence/correlation where the selected statistical method supports such estimation.

---

# 115. Statistical Confidence

Canonical:

`estimate_uncertainty`

Represents uncertainty associated with a learned quantity.

---

# 116. Distribution Support

Canonical:

`distribution_support`

Records the amount of historical evidence supporting a conditional distribution.

---

# 117. Model Health

Canonical:

`model_health_state`

Possible conceptual states:

```text
VALID
DEGRADED
UNSUPPORTED
```

Exact state transitions belong to model monitoring.

---

# 118. Calibration Error

Canonical:

`calibration_error`

Measures difference between predicted probabilities and observed frequencies.

---

# 119. Prediction Drift

Canonical:

`prediction_distribution_drift`

Measures change in the distribution of model predictions.

---

# 120. Feature Drift

Canonical:

`feature_distribution_drift`

Measures change in feature distributions.

---

# 121. Economic Drift

Canonical:

`economic_edge_drift`

Measures deterioration or change in observed net economic value.

---

# 122. Execution Drift

Canonical:

`execution_cost_drift`

Measures change in:

`spread`

`slippage`

`fill behavior`

and other execution characteristics.

---

# 123. Variable Dependency Contract

Every variable must explicitly record:

```text
DEPENDENCIES
```

For example:

```text
expected_net_value
    |
    +-- expected_gross_return
    +-- expected_execution_cost
```

---

# 124. Dependency Direction

Dependencies always point:

```text
SOURCE
  ->
DERIVED
  ->
MODEL
  ->
DECISION
```

Never backward.

---

# 125. Canonical Dependency Examples

```text
last_price
    ->
return
    ->
realized_volatility
    ->
p_up
    ->
expected_gross_return
    ->
expected_net_value
    ->
trade_eligible
    ->
action
```

This is a valid causal chain.

---

# 126. Label Dependency

Separately:

```text
decision_timestamp
      +
future_events
      ->
future_mfe
future_mae
future_net_return
future_horizon
```

These labels feed historical learning only.

---

# 127. Circular Dependency Prohibition

The registry must reject:

```text
A -> B
B -> C
C -> A
```

unless the relationship is explicitly represented as a temporal state transition.

---

# 128. Temporal Feedback

A legitimate temporal dependency can exist:

```text
State_t
   ->
Decision_t
   ->
Position_(t+1)
   ->
State_(t+1)
```

This is not a circular mathematical dependency.

It is a temporal transition.

---

# 129. State Versus Feature

A feature describes information derived from current/past observations.

A state variable persists because of prior state.

Example:

```text
realized_volatility
=
FEATURE

peak_unrealized_pnl
=
STATE
```

---

# 130. State Versus Label

This distinction is absolute:

```text
peak_unrealized_pnl
=
what the live trade has achieved so far

future_mfe
=
what eventually happened after the decision
```

They are not interchangeable.

---

# 131. Forecast Versus Realized

Another mandatory distinction:

```text
expected_net_value
=
forecast

realized_pnl
=
outcome
```

---

# 132. Forecast Versus State

Likewise:

```text
expected_horizon
=
forecast

holding_time
=
realized state/outcome
```

---

# 133. Forecast Versus Risk Boundary

And:

```text
expected_mae
=
forecast

protected_stop_price
=
live risk boundary
```

---

# 134. Canonical Registry Rule

If two variables answer the same mathematical question:

they must be merged.

This is why we removed:

`current_profit`

and:

`projected_trade_duration`.

---

# 135. Variable Promotion Rule

A provisional variable becomes canonical only when:

```text
definition
+
owner
+
dependencies
+
temporal semantics
```

are established.

---

# 136. Variable Retirement Rule

A variable may be retired if:

`duplicate`

`unused`

`redundant`

or:

`statistically unsupported`.

Retired variables remain documented historically.

They are not silently reused.

---

# 137. TrueData Mapping Columns

Every source-backed variable ultimately requires:

```text
truedata_field
truedata_endpoint
source_type
subscription_required
historical_available
historical_start
timestamp_semantics
precision
unit
update_frequency
missing_semantics
```

All currently remain:

`TODO`.

---

# 138. Source Mapping Rule

A source field is accepted only after verifying:

```text
NAME
+
SEMANTICS
+
TEMPORAL BEHAVIOR
+
HISTORICAL AVAILABILITY
```

A matching field name alone is insufficient.

---

# 139. Canonical Registry Snapshot

The current top-level structure is:

```text
MARKET
 |
 +-- timestamp
 +-- instrument_id
 +-- last_price
 +-- bid_price
 +-- ask_price
 +-- volume
 +-- open_interest
 +-- depth

DERIVED MARKET
 |
 +-- mid_price
 +-- spread
 +-- returns
 +-- volatility
 +-- range
 +-- flow
 +-- liquidity

MODEL
 |
 +-- p_up
 +-- p_down
 +-- p_neutral
 +-- horizon_distribution
 +-- expected_horizon
 +-- continuation_value
 +-- expected_net_value

POSITION
 |
 +-- position_state
 +-- entry_price
 +-- unrealized_pnl
 +-- peak_unrealized_pnl
 +-- protected_stop_price
 +-- protected_profit_floor

DECISION
 |
 +-- trade_eligible
 +-- direction_decision
 +-- option_decision
 +-- selected_option_id
 +-- position_quantity
 +-- action

EXECUTION
 |
 +-- expected_slippage
 +-- realized_slippage
 +-- execution_quality

LABEL
 |
 +-- future_return
 +-- future_mfe
 +-- future_mae
 +-- future_horizon
 +-- future_net_return

RESEARCH
 |
 +-- dataset_version
 +-- feature_version
 +-- label_version
 +-- model_version
 +-- execution_model_version
```

---

# 140. Single Source of Truth

This registry is now the canonical authority for variable identity.

The mathematical specification references these canonical variables.

The dependency graph references these canonical variables.

The state machine references these canonical variables.

The historical experiments reference these canonical variables.

The eventual implementation must reference these canonical variables.

---

# 141. Implementation Rule

When implementation begins:

```text
CODE VARIABLE
      |
      v
CANONICAL VARIABLE ID
```

Every important runtime quantity must map back to this registry.

This prevents:

```text
strategy specification
        !=
backtest implementation
        !=
live implementation
```

---

# 142. Current Unknowns

The following remain intentionally unresolved:

```text
TrueData exact field names
TrueData endpoints
TrueData tick availability
TrueData depth semantics
TrueData option-chain historical reconstruction
TrueData timestamp semantics
TrueData historical retention
TrueData update frequency
TrueData precision
TrueData entitlement requirements
TrueData missing-value behavior
TrueData sequence identifiers
```

These are now isolated to the source-mapping layer.

---

# 143. Important Result

We have now separated:

```text
WHAT THE STRATEGY NEEDS
```

from:

```text
HOW TRUE DATA PROVIDES IT
```

That is exactly what we wanted.

The strategy architecture no longer depends on assumptions about the vendor API.

---

# 144. Next Artifact

The next logical artifact is:

# FEATURE ENGINEERING MATHEMATICAL SPECIFICATION

Not a generic list of indicators.

We will define, mathematically and causally, the exact feature families the strategy is allowed to consider:

```text
PRICE
RETURN
MOMENTUM
VOLATILITY
RANGE
FLOW
LIQUIDITY
DEPTH
OPTION
TIME
REGIME
EXECUTION
```

For every candidate feature we will specify:

```text
formula
input variables
lookback
event frequency
window semantics
normalization
missing-data behavior
minimum evidence
causal availability
redundancy test
stability test
```

Most importantly, we will define the feature-selection protocol so that we do **not** end up with a giant collection of indicators that looks sophisticated but adds no independent predictive information.