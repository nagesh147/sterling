# FEATURE ENGINEERING MATHEMATICAL SPECIFICATION

## Canonical Feature Contract — Version 1.0

## 1. Objective

The feature engine transforms the canonical market state at time `t` into a finite set of mathematically defined quantities that may be supplied to the statistical model.

The fundamental relationship is:

```text
CanonicalState_t
       |
       v
FeatureEngine
       |
       v
FeatureVector_t
```

The feature engine must never access:

```text
Events_(t+1...)
FutureLabels
FutureOutcomes
FutureModelParameters
```

---

# 2. Feature Design Principle

We do not begin with:

"Which indicators should we use?"

We begin with:

"What measurable property of the current market could contain incremental information about future net opportunity?"

Every feature must answer that question.

---

# 3. Feature Admission Pipeline

A candidate feature passes through:

```text
Candidate
   |
   v
Causal Validity
   |
   v
Mathematical Validity
   |
   v
Data Availability
   |
   v
Distribution Stability
   |
   v
Redundancy Test
   |
   v
Incremental Predictive Test
   |
   v
Out-of-Sample Test
   |
   v
Economic Test
   |
   v
ADMIT / REJECT
```

---

# 4. Feature Classes

The initial candidate universe contains:

```text
PRICE
RETURN
MOMENTUM
RANGE
VOLATILITY
FLOW
LIQUIDITY
DEPTH
OPTION
TIME
REGIME
EXECUTION
```

This is a candidate universe, not a mandatory final feature set.

---

# 5. Feature Registry

Every candidate receives:

```text
feature_id
feature_name
class
formula
inputs
lookback
sampling_basis
normalization
missing_data_rule
causal_timestamp
units
version
```

---

# 6. Feature Timestamp

Every feature has:

`feature_timestamp = t`.

Its value must be reproducible from:

```text
Events_<=t
```

and static information known at `t`.

---

# 7. Feature Lookback

Every rolling feature has an explicit:

`L`.

For example:

```text
L = 60 seconds
```

means exactly:

```text
(t - 60 seconds, t]
```

or another explicitly defined interval.

No feature may use an ambiguous phrase such as:

"recent price."

---

# 8. Event-Time Versus Clock-Time

A feature must specify whether its window is:

```text
CLOCK_TIME
```

or:

```text
EVENT_COUNT
```

These are fundamentally different.

---

# 9. Clock-Time Example

A sixty-second return:

```text
R_60(t)
=
P_t / P_(t-60s) - 1
```

requires observations based on timestamps.

---

# 10. Event-Count Example

A fifty-event return:

```text
R_50E(t)
=
P_t / P_(event-50) - 1
```

depends on event count.

This can behave very differently during high and low activity.

---

# 11. No Implicit Resampling

If a feature requires one-second observations but the raw feed does not provide them:

the engine cannot silently fabricate them.

The feature becomes:

`UNAVAILABLE`

unless a formally defined reconstruction method exists.

---

# 12. Price Feature Family

Candidate price features include:

```text
price level
price distance
normalized price distance
price acceleration
price displacement
```

Raw price itself is generally not assumed to be predictive simply because it is available.

---

# 13. Price Distance

For reference price `R_t`:

```text
distance_R(t)
=
(P_t - R_t) / R_t
```

The reference may be:

`session reference`

`rolling reference`

or another causally defined quantity.

---

# 14. Reference Price

Every reference must have an explicit owner.

Examples:

```text
session_open
rolling_mean
VWAP_if_valid
opening_range_reference
```

No feature may implicitly select whichever reference produces the best backtest.

---

# 15. Return Family

Candidate returns:

```text
R_L(t)
```

for multiple lookbacks `L`.

The candidate set may include:

`very short`

`short`

`medium`

`long`.

Exact numerical horizons are not frozen at architecture level.

---

# 16. Return Normalization

Raw return can be normalized against current volatility:

```text
normalized_return_L
=
return_L / volatility_scale_L
```

provided the volatility scale is causally available.

This converts absolute movement into movement relative to prevailing market variability.

---

# 17. Momentum

Momentum is not defined as a particular named indicator.

The canonical concept is:

```text
directional persistence
```

Candidate representations include:

```text
sign persistence
return persistence
velocity persistence
multi-window directional agreement
```

---

# 18. Directional Persistence

For a sequence of signed returns:

```text
s_i = sign(R_i)
```

a persistence statistic can be:

```text
persistence
=
number of same-direction transitions
/
number of valid transitions
```

The exact estimator is a candidate, not a frozen production parameter.

---

# 19. Momentum Acceleration

A candidate momentum acceleration quantity is:

```text
momentum_acceleration
=
momentum_short
-
momentum_long
```

after appropriate normalization.

This attempts to distinguish:

`strong and stable`

from:

`strengthening`.

---

# 20. Momentum Deceleration

Likewise:

```text
momentum_deceleration
=
momentum_long
-
momentum_short
```

when directionally meaningful.

The feature should not be retained if it is merely a duplicate representation.

---

# 21. Range Family

Candidate range quantities include:

```text
rolling_range_L
range_expansion
range_contraction
range_percentile
range_relative_to_volatility
```

---

# 22. Range Expansion

Conceptually:

```text
range_expansion
=
current_range
/
historical_range_scale
```

A value above the historical baseline indicates expansion.

The denominator is learned/validated rather than arbitrarily fixed.

---

# 23. Range Percentile

Instead of:

```text
range > X
```

we can estimate:

```text
F_range(range_t)
```

where:

`F_range`

is the historical conditional distribution constructed without future leakage.

---

# 24. Volatility Family

Candidate volatility measures include:

```text
realized variance
realized standard deviation
absolute-return scale
range-based volatility
event-time volatility
```

We do not assume one estimator is universally superior.

---

# 25. Realized Variance

For returns:

```text
RV_L(t)
=
Σ r_i²
```

over the specified causal window.

The sampling definition must be explicit.

---

# 26. Realized Volatility

```text
RVOL_L(t)
=
sqrt(RV_L(t))
```

subject to the chosen annualization or non-annualized representation.

For intraday trading, the raw local scale may be preferable to annualization if annualization adds no useful information.

---

# 27. Volatility Acceleration

Candidate:

```text
volatility_acceleration
=
volatility_short
-
volatility_long
```

This attempts to detect:

`volatility expansion`

or:

`volatility contraction`.

---

# 28. Volatility Percentile

Instead of an arbitrary threshold:

```text
volatility_percentile_t
=
F_volatility(volatility_t)
```

where `F` is estimated causally.

This directly supports our preference for rolling statistical measures.

---

# 29. Volatility Regime

The regime engine may estimate:

```text
P(LOW | State_t)
P(NORMAL | State_t)
P(HIGH | State_t)
P(EXTREME | State_t)
```

if empirical evidence supports these categories.

The categories themselves remain provisional.

---

# 30. Volatility-of-Volatility

A candidate feature:

```text
volatility_change_variance
```

measures how unstable the volatility state itself is.

This can distinguish:

```text
high but stable volatility
```

from:

```text
rapidly changing volatility
```

---

# 31. Flow Feature Family

If true trade data permits valid classification, candidate flow variables include:

```text
signed_volume
volume_imbalance
flow_acceleration
flow_persistence
flow_reversal
```

---

# 32. Signed Volume

Conceptually:

```text
signed_volume
=
Σ sign(trade_direction_i) * volume_i
```

The exact trade-direction classification must be validated against the actual data semantics.

---

# 33. Flow Imbalance

```text
flow_imbalance
=
buy_volume - sell_volume
--------------------------------
buy_volume + sell_volume
```

when the denominator is positive.

---

# 34. Flow Persistence

A flow signal becomes more interesting if it persists.

A candidate statistic can measure:

```text
fraction of recent intervals
having the same flow direction
```

again using explicit windows.

---

# 35. Flow Reversal

A candidate feature detects:

```text
strong positive flow
        ->
rapid weakening/reversal
```

This may be particularly relevant to exit decisions.

But it must demonstrate incremental value.

---

# 36. Liquidity Feature Family

Candidate liquidity features:

```text
spread
relative spread
visible depth
depth imbalance
trade frequency
quote frequency
volume intensity
```

---

# 37. Spread

Already defined:

```text
spread = ask - bid
```

It is both:

`market-state information`

and:

`execution-cost information`.

The same canonical variable must be reused.

---

# 38. Spread Percentile

Candidate:

```text
spread_percentile
=
F_spread(spread_t)
```

This avoids assuming that:

"one rupee spread"

has the same meaning across all instruments.

---

# 39. Depth Imbalance

Previously defined:

```text
DIB
=
(BidDepth - AskDepth)
/
(BidDepth + AskDepth)
```

This is a candidate predictor.

It is not automatically assumed to represent true future pressure.

---

# 40. Depth Change

Candidate:

```text
depth_change_L
=
depth_t - depth_(t-L)
```

This measures liquidity entering or leaving the visible book.

---

# 41. Depth Acceleration

Candidate:

```text
depth_acceleration
=
depth_change_short
-
depth_change_long
```

This may detect rapidly changing liquidity conditions.

---

# 42. Liquidity Stress

A candidate composite can represent:

```text
liquidity_stress
=
f(
spread_percentile,
depth_percentile,
trade_frequency,
volume_intensity
)
```

But composite features are not automatically preferred.

They can conceal which underlying variable actually carries information.

---

# 43. Time Feature Family

Time features are deterministic.

Candidates include:

```text
time_since_open
time_to_close
session_phase
time_since_session_high
time_since_session_low
opening_range_status
```

---

# 44. Time Since Open

```text
time_since_open
=
t - session_open
```

This is causal and deterministic.

---

# 45. Time To Close

```text
time_to_close
=
session_close - t
```

The session close is known in advance.

Therefore this is causal.

---

# 46. Opening Range

If the strategy uses opening-range information:

the range becomes valid only after the defined observation interval is complete.

Before completion:

```text
opening_range_status
=
INCOMPLETE
```

It must not use the eventual high/low prematurely.

---

# 47. Opening Range Lookahead Trap

At:

`09:10`

we cannot use the final:

`09:15 opening-range high`.

Doing so would leak future information.

---

# 48. Option Feature Family

Candidate option features include:

```text
option_return
option_relative_spread
option_volume
option_open_interest
time_to_expiry
distance_from_strike
moneyness
IV
IV change
option liquidity
```

only where source data supports them.

---

# 49. Moneyness

For underlying price `S` and strike `K`:

```text
moneyness
=
S / K
```

or another explicitly selected representation.

The representation must remain consistent.

---

# 50. Log Moneyness

Alternative:

```text
log_moneyness
=
ln(S / K)
```

This may provide better statistical behavior.

It is a candidate representation, not an automatic production choice.

---

# 51. Time To Expiry

```text
TTE
=
expiry_timestamp - t
```

This is causal because expiry is known.

---

# 52. Option Relative Spread

```text
option_relative_spread
=
(option_ask - option_bid)
/
option_mid
```

when valid.

This is directly relevant to whether an option trade is economically viable.

---

# 53. Option Return

For candidate option:

```text
option_return_L
=
option_price_t / option_price_(t-L) - 1
```

subject to valid observations.

---

# 54. IV Features

If implied volatility is available or rigorously reconstructable:

candidate quantities include:

```text
IV_level
IV_change
IV_percentile
IV_surface_position
```

But these must be admitted only if their historical construction is causal and reproducible.

---

# 55. Greek Features

Greeks such as:

`delta`

`gamma`

`theta`

`vega`

may be considered.

However:

they are derived quantities, not automatically information.

A Greek is admitted only if it contributes incremental predictive/economic information beyond the underlying and option-state variables.

---

# 56. Execution Feature Family

Candidate execution features:

```text
spread
expected_slippage
fill probability
latency sensitivity
liquidity stress
execution cost percentile
```

These are particularly important for micro-scalping.

---

# 57. Expected Slippage

The feature engine may estimate:

```text
E[Slippage | State_t]
```

using only historical information available before `t`.

---

# 58. Execution Cost Percentile

Candidate:

```text
execution_cost_percentile
=
F_cost(expected_execution_cost)
```

This allows the system to distinguish:

`normal`

from:

`abnormally expensive`

execution conditions.

---

# 59. Regime Feature Family

Regime features should describe:

```text
trend state
volatility state
liquidity state
session state
market stress
```

They must not simply be arbitrary labels.

---

# 60. Trend State

Instead of:

```text
UPTREND = price > moving_average
```

we may estimate a probabilistic state:

```text
P(trending_up)
P(trending_down)
P(range)
```

if empirically justified.

---

# 61. Composite Regime

A complete state can theoretically be represented as:

```text
R_t
=
(
volatility_state,
trend_state,
liquidity_state,
session_state
)
```

But the Cartesian product can explode.

We therefore do not automatically create a separate model for every combination.

---

# 62. Feature Interaction

Two features may become predictive only jointly.

For example:

```text
momentum
+
volatility expansion
```

may contain more information than either individually.

Interaction terms are therefore candidates.

---

# 63. Interaction Admission

An interaction is admitted only if:

```text
JointInformation
>
InformationAlreadyAvailable
```

on out-of-sample data.

---

# 64. Feature Redundancy

Two features may be highly correlated.

But correlation alone is not the final redundancy test.

We care about:

```text
incremental predictive information
```

---

# 65. Sequential Feature Admission

Suppose we have:

```text
Feature A
```

Then evaluate:

```text
Model(A)
```

Next:

```text
Model(A + B)
```

Measure the out-of-sample improvement.

If `B` contributes no robust incremental value:

`B = REJECT`.

---

# 66. Feature Removal Test

After building the candidate model:

remove each feature:

```text
Model(full)
vs
Model(without X)
```

If performance does not materially deteriorate:

`X`

is a candidate for removal.

---

# 67. Permutation Test

A feature can also be permuted while preserving the rest of the dataset.

If:

```text
Performance_original
```

is indistinguishable from:

```text
Performance_permuted
```

the feature may contain little useful information.

---

# 68. Temporal Permutation

Random permutation must be used carefully.

For strongly autocorrelated data, naive shuffling can destroy important temporal structure.

The permutation method must preserve the relevant dependence structure where necessary.

---

# 69. Feature Stability

A feature must be evaluated across:

`time`

`volatility`

`liquidity`

`session phase`.

A feature that works only in one narrow historical segment is not automatically rejected, but it must be explicitly classified as conditional.

---

# 70. Feature Drift

For feature `X`:

track:

```text
Distribution(X)_fold_i
```

across walk-forward folds.

Large distribution changes require investigation.

---

# 71. Predictive Stability

Track:

```text
Effect(X)_fold_i
```

rather than only:

`overall effect`.

A feature whose sign repeatedly changes is suspicious.

---

# 72. Feature Sign Stability

Suppose:

```text
Fold 1: positive
Fold 2: positive
Fold 3: positive
Fold 4: negative
Fold 5: positive
```

This may be acceptable depending on uncertainty.

But:

```text
positive
negative
positive
negative
```

suggests instability.

---

# 73. Feature Scaling

Feature scaling is itself a learned transformation.

Therefore scaling parameters must be estimated only from the training data available to that model version.

---

# 74. No Global Standardization

Invalid:

```text
mean = mean(all five years)
std  = std(all five years)
```

when evaluating earlier historical periods.

Correct:

```text
mean_t
std_t
```

must come from information available before the model freeze/test boundary.

---

# 75. Robust Scaling

Potential transformations include:

```text
z-score
rank percentile
median/MAD
quantile transformation
```

The transformation itself becomes a candidate model component.

---

# 76. Percentile Features

Percentile/rank transformations are particularly attractive for our dynamic architecture because they convert raw quantities into:

```text
"What percentile of its historical distribution is the current condition?"
```

This is often more stable than arbitrary absolute thresholds.

But the historical reference distribution must be causal.

---

# 77. Rolling Distribution

A feature may use:

```text
F_t(X)
```

where the distribution is constructed from historical observations available before `t`.

The current observation must not contaminate the reference distribution if the mathematical definition excludes it.

---

# 78. Expanding Distribution

Alternatively:

```text
F_t(X)
=
all eligible historical observations before t
```

This provides more samples but may adapt more slowly.

---

# 79. Recency-Weighted Distribution

A candidate:

```text
F_t(X; λ)
```

weights recent observations more heavily.

`λ` is learned/validated.

It is not hardcoded because it looks mathematically elegant.

---

# 80. Feature Half-Life

We can empirically determine whether predictive information decays with time.

For feature `X`:

measure predictive contribution across historical ages.

This informs whether:

`expanding`

or:

`rolling`

or:

`weighted`

history is appropriate.

---

# 81. Feature Missingness

Missingness itself may contain information.

Therefore we distinguish:

```text
X = MISSING
```

from:

```text
X = 0
```

and may optionally define:

```text
X_missing_indicator
```

if the missingness mechanism is stable and causally meaningful.

---

# 82. Missingness Admission

A missingness indicator is admitted only if:

`its predictive value`

is not merely an artifact of:

`data collection failure`.

Otherwise it could teach the strategy to exploit feed outages.

---

# 83. Feature Quality

Every feature receives:

```text
feature_quality
```

based on:

`input quality`

`coverage`

`mathematical validity`.

---

# 84. Feature Availability

At timestamp `t`:

```text
feature_available_t ∈ {TRUE, FALSE}
```

A model cannot silently substitute an unavailable feature.

---

# 85. Feature Capability

The feature vector may therefore be:

```text
FULL
PARTIAL
```

depending on which required inputs exist.

The capability model determines whether trading remains permitted.

---

# 86. Feature Vector

At time `t`:

```text
X_t
=
[
x_1(t),
x_2(t),
...
x_n(t)
]
```

where every `x_i(t)` satisfies the causal contract.

---

# 87. Feature Vector Is Not Fixed Forever

The candidate feature universe may be large.

The production feature vector must contain only:

`validated features`.

---

# 88. Feature Selection Objective

The objective is not:

```text
maximize number of predictive features
```

It is:

```text
maximize robust incremental information
while minimizing complexity and instability.
```

---

# 89. Feature Selection Criterion

Conceptually:

```text
FeatureValue
=
OutOfSampleIncrementalValue
-
ComplexityCost
-
InstabilityPenalty
```

The exact scoring method belongs to the research protocol.

---

# 90. Economic Feature Selection

A feature can be statistically predictive but economically useless.

Therefore final admission requires:

```text
PredictiveValue
+
EconomicValue
```

not merely:

`PredictiveValue`.

---

# 91. Cost-Aware Feature Testing

For each candidate feature:

evaluate whether its incremental prediction survives:

`spread`

`slippage`

`fees`

`latency`.

---

# 92. Micro-Scalping Feature Standard

Because micro-scalping opportunities are short-lived:

features intended to support micro trades require evidence that:

```text
information_decay_time
>
execution_latency
```

and:

```text
incremental_edge
>
incremental_execution_cost
```

when applicable.

---

# 93. Intraday Feature Standard

Longer-horizon features can tolerate slower information decay.

But they still require:

`causal availability`

and:

`out-of-sample economic value`.

---

# 94. Feature-to-Horizon Interaction

A feature may be predictive at one horizon and useless at another.

Therefore evaluate:

```text
Feature X
   |
   +--> short-horizon label
   +--> medium-horizon label
   +--> intraday label
```

separately.

---

# 95. Feature-to-Mode Interaction

This allows:

`X`

to be admitted for:

`MICRO`

but not necessarily:

`INTRADAY`.

The production registry can therefore contain:

```text
feature_capability
```

rather than assuming universal usefulness.

---

# 96. Feature-to-Direction Interaction

Likewise a feature may predict:

`UP`

but not:

`DOWN`

symmetrically.

The model can learn directional conditional relationships.

---

# 97. No Forced Symmetry

We do not impose:

```text
effect_up = -effect_down
```

unless the data supports it.

---

# 98. Feature Leakage Audit

Every feature receives an automated conceptual audit:

```text
Does it use:
future price?
future volume?
future option state?
future completed bar?
future label?
future regime?
future normalization?
```

If yes:

`REJECT`.

---

# 99. Same-Bar Leakage

This deserves special attention.

If a feature uses:

`high`

of a bar that has not completed at decision time:

`REJECT`.

---

# 100. Same-Tick Leakage

If a decision occurs between events:

the feature may use only the information that had arrived by that exact event timestamp.

No later event in the same recorded timestamp batch may be assumed available unless the source semantics establish the ordering.

---

# 101. Feature Event Ordering

Where multiple events have identical timestamps:

the canonical event sequence must define:

```text event_1
event_2
...
event_n
```

if the source supplies ordering.

Otherwise the system must treat the timestamp as insufficient to establish causal ordering.

---

# 102. Feature Calculation Frequency

Every feature declares:

```text EVENT
TICK
SECOND
MINUTE
SESSION
```

or another explicit frequency.

A minute feature must not be recalculated using an incomplete minute as though it were complete unless explicitly defined as a live partial-bar feature.

---

# 103. Partial-Bar Feature

A live partial-bar feature is valid if defined as:

```text
CurrentPartialBar_t
```

rather than:

```text
CompletedBar_t
```

These are separate variables.

---

# 104. Completed Versus Partial

We therefore distinguish:

```text
bar_complete = TRUE
```

from:

```text
bar_complete = FALSE
```

This prevents accidental lookahead.

---

# 105. Feature Family Compression

If several features measure the same underlying phenomenon:

we prefer a compact representation.

For example:

```text
return_10s
return_20s
return_30s
return_40s
return_50s
return_60s
```

should not automatically all enter the model.

Their incremental value must justify their existence.

---

# 106. Multiple-Window Explosion

This is a major overfitting risk.

If we test:

`100 features`

across:

`20 horizons`

we have already created:

`2,000 candidate hypotheses`.

The research registry must track this.

---

# 107. Multiple-Testing Registry

Every experiment records:

```text
candidate_count
feature_count
horizon_count
model_count
parameter_count
selection_count
```

This makes research complexity auditable.

---

# 108. Feature Family Selection

Before individual optimization:

we may first test whether a family contributes value:

```text
PRICE
vs
PRICE + FLOW
vs
PRICE + VOLATILITY
...
```

This provides a stronger hierarchy than testing thousands of isolated features immediately.

---

# 109. Hierarchical Admission

The preferred order is:

```text
Family
   |
   v
Representation
   |
   v
Feature
   |
   v
Parameterization
```

This limits combinatorial explosion.

---

# 110. Feature Research Order

The initial research order should be:

```text
1. Price/returns
2. Volatility/range
3. Time/session
4. Liquidity/execution
5. Flow
6. Depth
7. Option state
8. Interactions
```

This is a research sequence, not a claim that later families are superior.

---

# 111. Baseline Feature Set

The first model should intentionally use a minimal baseline:

```text
price/return
volatility
time/session
execution cost
```

Then families are added sequentially.

---

# 112. Why Baseline Matters

If the complex model succeeds but:

`baseline`

performs equally well:

the complexity is unjustified.

---

# 113. Feature Ablation

For the final model:

remove each feature family independently.

Measure:

```text
ΔProbabilityQuality
ΔEconomicEV
ΔDrawdown
ΔCalibration
```

---

# 114. Feature Robustness

A feature is robust when:

```text
direction is reasonably stable
+
economic effect persists
+
calibration remains acceptable
+
performance survives costs
```

across multiple walk-forward periods.

---

# 115. Feature Failure Modes

A feature may fail because of:

```text
overfitting
data leakage
non-stationarity
execution irrelevance
redundancy
poor data quality
```

The failure reason must be recorded.

---

# 116. Feature Status

Every candidate eventually receives:

```text
CANDIDATE
TESTING
ADMITTED
CONDITIONAL
REJECTED
RETIRED
```

---

# 117. Conditional Feature

A feature may be admitted only under:

```text
specific regime
specific capability state
specific horizon
specific instrument
```

if that conditional relationship survives validation.

---

# 118. Feature Retirement

If a previously admitted feature loses validated incremental value:

it becomes:

`RETIRED`.

Historical model versions continue to reference the old feature.

---

# 119. Feature Versioning

Every formula change creates:

`FEATURE_VERSION + 1`.

We never silently change the meaning of an existing feature ID.

---

# 120. Final Feature Contract

At runtime:

```text
FeatureVector_t
=
F(
    CanonicalState_<=t,
    FeatureVersion
)
```

Nothing else.

---

# 121. Final Feature Invariant

A feature may influence a decision only if:

```text
CAUSAL
AND
AVAILABLE
AND
VALID
AND
VERSIONED
AND
ADMITTED
```

---

# 122. Current Status

We have now defined:

`feature identity`

`feature causality`

`feature windows`

`feature families`

`feature normalization`

`feature missingness`

`feature stability`

`feature redundancy`

`feature admission`

`feature versioning`

`feature-to-horizon interaction`

`feature-to-mode interaction`

`feature-to-economic-value testing`.

---

# 123. What Remains Empirical

We have deliberately not fixed:

```text
exact lookback durations
exact feature count
exact volatility estimator
exact flow estimator
exact depth representation
exact normalization method
exact percentile window
exact interaction set
exact feature-selection threshold
```

These must come from walk-forward research.

---

# 124. Critical Architectural Result

We have now prevented a major failure mode:

```text
"Let's calculate every indicator we can
and let the model figure it out."
```

That is not our architecture.

Our architecture is:

```text
Candidate hypothesis
       |
       v
Causal feature
       |
       v
Statistical evidence
       |
       v
Economic evidence
       |
       v
Out-of-sample validation
       |
       v
Production admission
```

---

# 125. Next Artifact

The next artifact should now be:

# PROBABILITY ENGINE MATHEMATICAL SPECIFICATION

This is the next major layer.

We will define exactly how:

```text
FeatureVector_t
        |
        v
Historical Conditional Distribution
        |
        v
P(UP)
P(DOWN)
P(NEUTRAL)
        |
        v
Calibration
        |
        v
Uncertainty
        |
        v
Evidence Strength
```

will work.

Most importantly, we will define the exact mechanics of the **empirical/Bayesian hybrid we previously selected**, including how historical states are matched, how sparse states are handled, how probabilities shrink toward broader populations, how regime conditioning works, and how the system prevents a tiny historical sample from producing an absurdly confident probability.