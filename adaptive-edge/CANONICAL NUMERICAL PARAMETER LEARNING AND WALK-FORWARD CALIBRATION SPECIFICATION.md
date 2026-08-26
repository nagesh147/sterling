# CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how every non-invariant numerical quantity in the strategy is obtained from historical data.

The system must distinguish between:

```text
FIXED ARCHITECTURAL RULES
LEARNED PARAMETERS
OBSERVED STATE VARIABLES
DERIVED FEATURES
MODEL OUTPUTS
```

A numerical value must never be placed into the strategy merely because it "looks reasonable."

If a quantity is designated as learned, its value must emerge from a defined historical estimation procedure.

---

# 2. Fundamental Principle

At historical decision time `t`:

```text
Parameter_t
=
Estimate(
InformationAvailableBeforeOrAt_t
)
```

Never:

```text
Parameter_t
=
Estimate(
EntireHistoricalDataset
)
```

because the latter allows future information to determine past behavior.

The strategy may replay many years of history, but each historical timestamp must behave as though the future does not yet exist.

---

# 3. Three Different Types of Numerical Quantity

We formally separate:

```text
OBSERVED
```

A quantity directly obtained from the market/data source.

Example:

```text price_t
volume_t
bid_t
ask_t
```

Then:

```text DERIVED
```

A deterministic transformation of currently available observations.

Example:

```text ATR_t
return_t
volatility_t
momentum_t
```

Then:

```text LEARNED
```

A quantity estimated from historical observations.

Example:

```text continuation threshold
profit-floor quantile
probability calibration
mode-transition sensitivity
```

These categories must never be conflated.

---

# 4. Parameter Registry

Every learned parameter receives a canonical identity:

```text ParameterID
Definition
Units
AllowedDomain
EstimationDataset
LabelDefinition
EstimationMethod
ValidationMethod
UpdateFrequency
ActivationRule
ExpirationRule
FallbackRule
```

No learned quantity may exist outside this registry.

---

# 5. Parameter Classes

The learned quantities are grouped into:

```text PREDICTION PARAMETERS
ECONOMIC PARAMETERS
RISK PARAMETERS
MODE PARAMETERS
EXECUTION PARAMETERS
CALIBRATION PARAMETERS
```

This classification prevents one optimization process from accidentally changing unrelated parts of the system.

---

# 6. Prediction Parameters

These govern statistical prediction.

Examples:

```text probability calibration parameters
conditional distribution parameters
continuation thresholds
state sensitivity
minimum evidence requirements
```

They influence:

```text "How likely is a future outcome?"
```

They do not directly determine position size.

---

# 7. Economic Parameters

These determine whether an opportunity has sufficient expected value.

Examples:

```text minimum expected net return
minimum cost-adjusted EV
minimum opportunity/risk ratio
option-selection thresholds
```

They answer:

```text "Is the predicted opportunity economically worth trading?"
```

---

# 8. Risk Parameters

These govern:

```text protection sensitivity
profit-floor quantile
emergency reversal threshold
maximum tolerated adverse excursion
```

They answer:

```text "How much adverse movement are we willing to tolerate?"
```

---

# 9. Mode Parameters

These determine when the strategy changes its inferred trading horizon.

Examples:

```text MICRO -> SCALP sensitivity
SCALP -> INTRADAY sensitivity
INTRADAY -> SCALP sensitivity
persistence requirement
hysteresis requirement
```

These parameters affect classification.

They do not increase permitted risk.

---

# 10. Execution Parameters

These describe the empirically acceptable execution environment.

Examples:

```text maximum spread
maximum estimated slippage
minimum liquidity
maximum execution delay
```

These parameters answer:

```text "Can the theoretical trade actually be executed?"
```

---

# 11. Calibration Parameters

These govern statistical reliability itself.

Examples:

```text minimum sample size
probability calibration bins
confidence bounds
minimum evidence
```

They do not predict direction.

They determine whether the prediction is trustworthy enough to use.

---

# 12. Historical Observation

For every decision timestamp `t`, define an information set:

```text I_t
```

where:

```text I_t
=
all information legitimately available at or before t.
```

The model is:

```text P(Y_future | I_t)
```

not:

```text P(Y_future | EntireDataset)
```

---

# 13. Historical Label

For a decision at `t`, define a future observation window:

```text [t + h_min, t + h_max]
```

where the exact horizon is determined by the label definition.

The label cannot become available until the required future information has actually occurred.

---

# 14. Label Maturity

If a label requires future information until:

```text t + H
```

then:

```text LabelMaturityTime = t + H
```

The observation cannot enter training before that time.

This is crucial.

---

# 15. Example

Suppose a decision occurred at:

```text 10:00
```

and its label requires the next:

```text 30 minutes.
```

The label becomes eligible only after:

```text 10:30.
```

The system cannot train the:

```text 10:00
```

model using that outcome while pretending it was known at:

```text 10:01.
```

---

# 16. Expanding Historical Replay

We can still replay five or ten years of historical data.

But the historical learner must behave sequentially:

```text 2019
  ↓
learn from eligible past
  ↓
evaluate later 2019

2020
  ↓
learn from matured history
  ↓
evaluate later 2020

2021
  ↓
learn from matured history
  ↓
evaluate later 2021
```

The strategy never receives future labels prematurely.

---

# 17. Rolling Versus Expanding Training

Two primary training-window structures exist.

Expanding:

```text [start -------------------------- t]
```

Rolling:

```text              [window -------- t]
```

Expanding retains all eligible history.

Rolling retains only the most recent historical window.

The choice itself must be validated.

It cannot be selected after seeing final test performance.

---

# 18. Regime-Aware Training

Market behavior changes.

Therefore the system may eventually compare:

```text expanding history
```

against:

```text rolling history
```

and potentially:

```text regime-conditioned history.
```

But regime classification itself must also obey point-in-time causality.

---

# 19. No Global Normalization

A subtle source of leakage is global normalization.

For example:

```text z = (x - global_mean) / global_std
```

where:

```text global_mean
global_std
```

were calculated using future data.

This is forbidden.

At time `t`:

```text mean_t
std_t
```

must be estimated only from information eligible at `t`.

---

# 20. Empirical Distribution Construction

For a state variable `X`, define an empirical conditional distribution:

```text F_t(x | S)
```

where `S` represents the relevant historical state.

Only observations that satisfy:

```text observation_time < t
```

and:

```text label_maturity_time < t
```

are eligible.

---

# 21. Conditional State Definition

The conditioning state must itself be composed only of information available at the decision timestamp.

For example:

```text direction
volatility regime
time of day
momentum state
distance from opening range
liquidity state
mode
```

can be used only if each component is point-in-time valid.

---

# 22. Sparse-State Problem

A very specific state may have very few historical examples.

For example:

```text high volatility
strong bullish momentum
late-session
large opening-range expansion
specific option liquidity state
```

may produce insufficient observations.

The system must not pretend that:

```text 7 observations
```

provide the same statistical confidence as:

```text 7,000 observations.
```

---

# 23. Minimum Evidence

Every learned conditional estimate therefore has an evidence requirement.

Conceptually:

```text EffectiveSampleSize >= MinimumEvidence
```

The numerical threshold remains learned/validated.

Until then:

```text insufficient evidence.
```

---

# 24. Sparse-State Fallback

When a state lacks sufficient observations, the system may use a predefined hierarchy:

```text exact state
    ↓
broader state
    ↓
broader regime
    ↓
global distribution
    ↓
NO_TRADE
```

The fallback hierarchy must be explicitly defined.

The system cannot invent a fallback dynamically.

---

# 25. Critical Rule

A fallback cannot use a broader distribution simply because it produces a more favorable probability.

The fallback is selected by the structural hierarchy.

Otherwise fallback selection itself becomes a hidden optimization mechanism.

---

# 26. Probability Estimation

Suppose:

```text N
```

historical opportunities satisfy the current state definition.

Let:

```text K
```

be the number producing the defined positive outcome.

The naive empirical probability is:

```text p_hat = K / N
```

But the system does not automatically treat this as sufficiently reliable.

---

# 27. Probability Uncertainty

The probability estimate must retain uncertainty.

Conceptually:

```text p_hat
+
confidence interval
```

or:

```text posterior distribution
```

rather than a single unexplained number.

This is where a statistically boring model remains preferable.

---

# 28. Bayesian Calibration

A simple Bayesian formulation may be used for binary outcomes:

```text p ~ Beta(alpha, beta)
```

After:

```text K successes
N-K failures
```

the posterior becomes:

```text Beta(alpha + K, beta + N - K)
```

The prior must be fixed independently of the test period.

It cannot be chosen because it improves test results.

---

# 29. Empirical Distribution Plus Bayesian Reliability

The architecture can therefore use both:

```text empirical distributions
```

for actual outcome behavior and:

```text Bayesian smoothing
```

for uncertainty in sparse states.

This avoids unnecessarily complex machine learning.

---

# 30. Important Distinction

Bayesian updating does not mean:

```text model learns from future market events in real time.
```

It means:

```text when an outcome becomes historically mature,
that observation updates the eligible historical statistical state.
```

The temporal boundary remains absolute.

---

# 31. Quantile Learning

Suppose future favorable excursion is:

```text MFE
```

and the system needs a profit-floor quantile.

The quantile:

```text Q_q(MFE | State)
```

must be learned from historical observations.

The value of:

```text q
```

is itself not invented.

It must be selected through the calibration process.

---

# 32. Parameter Search

Suppose candidate quantiles are:

```text q1
q2
q3
...
qN
```

We cannot select the one producing the highest test profit.

Instead:

```text training
    ↓
candidate selection
    ↓
validation
    ↓
frozen candidate
    ↓
test
```

The test set is touched only once for final evaluation.

---

# 33. Multiple Testing Problem

If we test:

```text 5 quantiles
10 thresholds
8 mode sensitivities
6 horizons
4 stop structures
```

we have already performed thousands of combinations.

The system must record all candidates.

Otherwise we can accidentally select noise.

---

# 34. Candidate Registry

Every candidate must receive:

```text CandidateID
ParameterSet
TrainingWindow
ValidationWindow
FeatureSet
ModelVersion
ResultMetrics
SelectionReason
```

Failed candidates remain recorded.

---

# 35. Selection Criterion

The best parameter is not:

```text highest historical profit.
```

The selection criterion must consider:

```text predictive quality
economic value
drawdown
stability
turnover
execution cost
sample size
regime robustness
parameter sensitivity
```

The exact weighting remains a validation decision.

---

# 36. Stability Requirement

Suppose:

```text parameter = 0.72
```

is excellent.

But:

```text 0.71 -> poor
0.72 -> excellent
0.73 -> terrible
```

This is suspicious.

A robust parameter should generally occupy a region where nearby values produce reasonably similar behavior.

This becomes a parameter-stability test.

---

# 37. Parameter Surface

For each important learned parameter, we should eventually examine:

```text parameter value
        ↓
out-of-sample performance
```

We want a stable region, not a single sharp peak.

---

# 38. Walk-Forward Structure

The canonical walk-forward cycle is:

```text TRAIN
   |
   v
VALIDATE
   |
   v
FREEZE
   |
   v
TEST / FORWARD PERIOD
   |
   v
ADVANCE WINDOW
   |
   v
NEW TRAIN
```

The process repeats chronologically.

---

# 39. Example

Conceptually:

```text TRAIN:       January - June
VALIDATE:        July
FORWARD TEST:    August
```

Then:

```text TRAIN:       February - July
VALIDATE:        August
FORWARD TEST:    September
```

and so forth.

The exact durations are not yet fixed.

---

# 40. Forward Test Is Sacrosanct

During the August forward test:

```text no parameter modification
no threshold modification
no feature removal
no model replacement
```

based on August outcomes.

Otherwise August is no longer an out-of-sample test.

---

# 41. Retraining Boundary

At the next permitted retraining boundary:

```text August matured observations
```

may become eligible for future training.

But only after their labels have matured.

---

# 42. Overlapping Labels

This is a major issue.

Suppose:

```text observation A at 10:00
```

uses a future horizon until:

```text 10:30.
```

and:

```text observation B at 10:05
```

also uses:

```text 10:35.
```

These observations overlap.

They are not necessarily independent.

The validation system must account for this.

---

# 43. Purging

When a training observation's label window overlaps a validation/test interval, the observation must be excluded from the training side.

Conceptually:

```text TRAIN LABEL WINDOW
        X
        |
        | overlaps
        v
VALIDATION PERIOD
```

The overlapping training observation is purged.

---

# 44. Embargo

An additional temporal gap may be imposed between training and validation/test boundaries.

This reduces contamination through closely related observations.

The exact embargo duration must be empirically determined or structurally justified.

---

# 45. Why This Matters

Without purging and embargo:

```text training observation
```

can indirectly contain information about:

```text validation outcome.
```

Even though the timestamps appear separated.

This is especially important for high-frequency data.

---

# 46. Tick-Level Data Does Not Mean Tick-Level Independence

One million ticks do not necessarily represent:

```text one million independent observations.
```

Adjacent ticks may represent nearly identical market states.

Therefore effective sample size is not simply:

```text number_of_ticks.
```

---

# 47. Opportunity-Level Sampling

The learner should generally operate on defined decision opportunities rather than treating every tick as an independent trade outcome.

Ticks update the state.

Decision opportunities generate labels.

This distinction prevents enormous artificial sample sizes.

---

# 48. State Observation Frequency

The live engine can update:

```text every tick.
```

But the learning dataset does not necessarily need one training row per tick.

The canonical distinction is:

```text TICK
updates state.

DECISION OPPORTUNITY
creates an evaluable prediction.

MATURED LABEL
creates an eligible learning observation.
```

---

# 49. Parameter Update Frequency

A parameter can update:

```text every event
```

only if that parameter's definition explicitly permits it.

Otherwise it may update:

```text every minute
every trade
every session
every day
every week
```

The update frequency is part of the parameter contract.

---

# 50. No Continuous Parameter Mutation Without Contract

We do not allow:

```text parameter_t = f(every new tick)
```

merely because historical data exists.

Frequent parameter changes increase instability and make attribution difficult.

The update cadence must be explicit.

---

# 51. Parameter Freeze

Once a parameter set is selected for a forward period:

```text ParameterSetVersion = V
```

it remains immutable for that period.

All trades during that period reference `V`.

---

# 52. Parameter Activation

A new parameter set becomes active only at:

```text ActivationTime.
```

Before activation:

```text old parameter set.
```

After activation:

```text new parameter set.
```

No retroactive application.

---

# 53. Parameter Rollback

If a newly activated parameter set violates a predefined production validity condition, rollback may occur only according to a predefined operational rule.

It cannot be triggered merely because:

```text "today's P&L is bad."
```

unless that criterion was defined beforehand.

---

# 54. Avoiding Adaptive Overreaction

The live strategy must not repeatedly learn:

```text bad trade
    ↓
change parameter
    ↓
next trade
    ↓
bad trade
    ↓
change parameter
```

This creates unstable online optimization.

Learning must occur on a controlled schedule.

---

# 55. Regime Change

If the market regime changes dramatically, the strategy may eventually require faster adaptation.

But adaptation speed itself must be part of the validated design.

The system cannot simply say:

```text market changed
therefore change everything.
```

---

# 56. Parameter Sensitivity Test

For each major parameter:

```text θ
```

evaluate nearby alternatives:

```text θ - δ
θ
θ + δ
```

and potentially a broader grid.

We seek:

```text performance stability
```

rather than a single optimal point.

---

# 57. Parameter Interaction

Parameters cannot always be evaluated independently.

For example:

```text profit quantile
```

may interact with:

```text continuation threshold.
```

Therefore the calibration framework must distinguish:

```text independent parameter sensitivity
```

from:

```text joint parameter interaction.
```

But joint searches must be controlled because combinatorial search dramatically increases multiple-testing risk.

---

# 58. Complexity Budget

The first production model should have a deliberately limited parameter search space.

We are not trying to find:

```text best possible historical strategy.
```

We are trying to find:

```text simplest statistically defensible strategy
```

that survives unseen data.

---

# 59. Parameter Freeze Rule

Once a parameter has been frozen for a final test period:

```text it cannot be changed because of test performance.
```

If it performs poorly:

```text test failed.
```

We do not repair the test.

---

# 60. Test Contamination

The following are prohibited:

```text seeing test results
    ↓
changing parameter
    ↓
rerunning test
```

because the resulting dataset is no longer a true test.

---

# 61. Final Holdout

The architecture should retain a final untouched historical period.

This period is not used for:

```text feature selection
parameter selection
threshold selection
model selection
strategy design
```

It exists to answer:

```text Does the complete development process survive truly unseen data?
```

---

# 62. Development / Validation / Test Separation

The canonical hierarchy is:

```text DEVELOPMENT
    |
    +-- feature design
    +-- parameter estimation
    +-- model construction

VALIDATION
    |
    +-- candidate selection
    +-- threshold selection
    +-- robustness selection

FINAL TEST
    |
    +-- evaluation only
```

---

# 63. Synthetic Data Has a Different Role

Synthetic scenarios are not substitutes for market validation.

They verify:

```text state-machine correctness
invariant preservation
edge-case behavior
```

Historical data verifies:

```text statistical/economic behavior.
```

These must remain separate.

---

# 64. Backtest Versus Walk-Forward

A conventional backtest can answer:

```text "What would this fixed specification have done?"
```

A walk-forward simulation answers:

```text "What would the system have known,
learned, selected, and deployed at each historical point?"
```

The second is closer to the intended production architecture.

---

# 65. Full Historical Replay

The five-year or longer historical dataset is therefore not treated as one giant training dataset.

It becomes:

```text chronological simulation environment.
```

The strategy effectively experiences history sequentially.

---

# 66. What the Strategy "Learns"

At historical time `t`, it may know:

```text matured historical outcomes
current market state
previous parameter versions
previous validated model versions
historical execution behavior
```

It does not know:

```text future market movement
future labels
future volatility
future regime
future execution outcome.
```

---

# 67. Historical Knowledge State

We can therefore define:

```text KnowledgeState_t
```

as the complete set of information legitimately accumulated by time `t`.

Then:

```text Model_t
=
Learn(KnowledgeState_t)
```

subject to the learning schedule.

This becomes a major canonical variable.

---

# 68. Parameter Provenance

Every production parameter must be traceable to:

```text ParameterVersion
TrainingWindow
ValidationWindow
DataVersion
FeatureVersion
LabelVersion
SelectionProcedure
ActivationTime
```

This makes the system auditable.

---

# 69. Parameter Lineage

For example:

```text PROFIT_FLOOR_QUANTILE_V17
        |
        +-- training data: historical window X
        +-- label: MFE definition Y
        +-- candidate set: Q1...Qn
        +-- validation: window Z
        +-- selected value: q*
        +-- activation: T
```

Nothing is a mysterious magic number.

---

# 70. Parameter Expiration

A parameter set may eventually become invalid due to:

```text scheduled retraining
```

or:

```text predefined validity horizon.
```

The expiration mechanism itself must be predefined.

The system cannot silently keep using an obsolete parameter forever if the architecture requires retraining.

---

# 71. Fallback Parameter

If a new parameter set fails validation:

```text candidate rejected.
```

The previous validated parameter set remains active.

There is no automatic deployment of an unvalidated alternative.

---

# 72. Catastrophic Learning Failure

If:

```text no valid candidate exists
```

the system must prefer:

```text conservative fallback
```

over:

```text forced optimization.
```

For a new entry parameter, the fallback may be:

```text NO_TRADE.
```

Existing positions continue under their already-established risk protections.

---

# 73. Learning Cannot Widen Existing Risk

This invariant remains absolute.

A newly learned:

```text wider volatility estimate
```

cannot retroactively widen:

```text existing protection boundary.
```

The parameter affects future candidate calculations only.

---

# 74. New Parameter Versus Existing Position

This gives us an important temporal rule:

```text New parameters may influence future decisions.
They cannot rewrite historical state.
```

Existing:

```text EntryPrice
PeakPnL
RealizedPnL
ProtectionFloor
TradeHistory
```

remain immutable.

---

# 75. Parameter Promotion Does Not Rewrite History

Suppose:

```text Model V1
```

managed a trade.

Later:

```text Model V2
```

is promoted.

The historical trade remains:

```text Model V1.
```

Its outcome cannot be reclassified under V2.

---

# 76. Counterfactual Analysis

V2 may be evaluated on the same historical period as a counterfactual.

But:

```text counterfactual result
```

cannot be substituted for:

```text actual historical result.
```

This distinction is essential for research.

---

# 77. Strategy Evolution

The strategy can therefore evolve through:

```text historical observation
    ↓
matured label
    ↓
training
    ↓
candidate parameter/model
    ↓
validation
    ↓
promotion
    ↓
future deployment
```

not:

```text future result
    ↓
rewrite historical decision.
```

---

# 78. This Solves the "Five Years Stronger" Idea

Your original idea can be preserved, but correctly.

The strategy can effectively walk through five years of historical time and repeatedly learn from matured information.

At the end:

```text final parameter/model
```

has benefited from historical experience.

But the validation process must also prove that its performance was not manufactured by repeatedly adapting to the same historical data.

That is why the untouched final holdout is necessary.

---

# 79. Numerical Parameters That Remain Unfrozen

The current architecture intentionally leaves these unresolved:

```text entry probability threshold
minimum EV
profit-floor quantile
emergency reversal threshold
continuation threshold
mode sensitivity
mode persistence
mode hysteresis
training-window length
validation-window length
retraining cadence
minimum evidence
execution-cost threshold
liquidity threshold
slippage tolerance
```

Their numerical values are not to be invented now.

---

# 80. Parameters That Are NOT Learned

These remain architectural:

```text no future information
no protection widening
no position without fill
no implicit reversal
no over-exit
no test contamination
exit priority
state-transition legality
model-version immutability
```

These are invariants.

Historical optimization cannot change them.

---

# 81. Calibration Objective

The ultimate calibration objective is not:

```text maximize historical profit.
```

It is closer to:

```text maximize robust out-of-sample economic utility
subject to
risk,
execution,
complexity,
stability,
and statistical-validity constraints.
```

The exact utility function itself must be specified before final calibration.

---

# 82. Calibration Output

Every calibration cycle produces:

```text ParameterSetVersion
ModelVersion
TrainingPeriod
ValidationPeriod
ForwardPeriod
CandidateRegistry
SelectionMetrics
RobustnessMetrics
DataVersion
ActivationTimestamp
```

This becomes part of the permanent audit trail.

---

# 83. Final Calibration Invariant

For every production decision at time `t`:

```text ParameterSetUsed(t)
```

must be reconstructable exactly.

If we cannot reproduce which parameters were active at a historical timestamp, the backtest is not auditable.

---

# 84. Final Learning Invariant

For every production decision:

```text InformationUsed(t)
```

must be reconstructable.

This is the ultimate defense against look-ahead bias.

---

# 85. Final Walk-Forward Contract

The production simulation therefore becomes:

```text Historical Data
      |
      v
Chronological Event Stream
      |
      v
State Reconstruction
      |
      v
Matured Historical Labels
      |
      v
Eligible Knowledge State
      |
      v
Parameter / Model Training
      |
      v
Validation
      |
      v
Promotion
      |
      v
Forward Deployment Simulation
      |
      v
Next Historical Period
```

This repeats until the historical dataset ends.

---

# 86. Completion Status

This artifact now defines the architecture for:

```text WHAT is learned
WHEN it becomes learnable
FROM WHICH observations
HOW it is estimated
HOW candidates are compared
HOW leakage is prevented
HOW overlapping labels are handled
HOW parameters are frozen
HOW models are promoted
HOW failures are handled
HOW historical evolution is simulated
```

The exact numerical values remain intentionally unresolved.

That is correct.

---

# 87. Remaining Pre-Implementation Boundary

We have now reached the point where the remaining work is no longer about inventing strategy logic.

The next major artifact should be:

```text CANONICAL DATA-TO-MATHEMATICS CONTRACT
```

This is where we take every variable in the registry and map:

```text Variable
    ↓
TrueData source field
    ↓
timestamp semantics
    ↓
precision
    ↓
update frequency
    ↓
historical availability
    ↓
entitlement
    ↓
transformation
    ↓
dependency
    ↓
validation rule
```

We have deliberately postponed the exact TrueData field names until you provide the authoritative documentation.

That was the correct decision.

Once that documentation is available, we replace the remaining `TODO` contracts with actual source-level definitions without changing the mathematical architecture.