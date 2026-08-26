# PARAMETER LEARNING AND WALK-FORWARD EXPERIMENT SPECIFICATION
## Canonical Statistical Learning Contract — Version 1.0

## 1. Objective

The strategy architecture is now fixed.

The numerical parameters are not.

The purpose of this specification is to determine those parameters from historical observations without:

`LOOKAHEAD`

`OVERFITTING`

`DATA SNOOPING`

`SURVIVORSHIP BIAS`

`LABEL LEAKAGE`

or:

`EXECUTION OPTIMISM`.

The fundamental principle is:

```text
Historical Data
      |
      v
Causal State Reconstruction
      |
      v
Historical Labels
      |
      v
Training
      |
      v
Validation
      |
      v
Frozen Candidate
      |
      v
Untouched Test
      |
      v
Promotion / Rejection
```

---

# 2. Parameter Classes

Every numerical quantity belongs to exactly one class.

`P1 = Source-derived parameters`

`P2 = Statistical parameters`

`P3 = Decision parameters`

`P4 = Risk parameters`

`P5 = Execution parameters`

`P6 = Model-selection parameters`.

No parameter may belong to multiple classes without explicit ownership.

---

# 3. Source-Derived Parameters

Examples:

`rolling volatility`

`ATR`

`spread distribution`

`volume distribution`

`time-of-day distributions`.

These are calculated directly from information available at time `t`.

They are not optimized constants.

---

# 4. Statistical Parameters

Examples:

`P(up | state)`

`P(down | state)`

`expected return`

`return quantiles`

`MFE distribution`

`MAE distribution`

`horizon distribution`.

These are estimated from historical observations.

---

# 5. Decision Parameters

Examples:

`minimum probability evidence`

`minimum expected value`

`minimum continuation value`

`reversal evidence threshold`.

These are learned through validation.

---

# 6. Risk Parameters

Examples:

`profit-floor quantile`

`giveback sensitivity`

`stop sensitivity`

`emergency protection threshold`.

These are learned from the distribution of adverse outcomes and validated economically.

---

# 7. Execution Parameters

Examples:

`slippage quantiles`

`latency penalty`

`spread tolerance`

`fill probability`.

These must be estimated from actual or conservatively reconstructed execution conditions.

---

# 8. Model-Selection Parameters

These determine:

`which feature subset`

`which model variant`

`which regime`

`which fallback`.

They must be learned without using the final test set.

---

# 9. No Global Optimization

We explicitly prohibit:

```text
Run 50,000 parameter combinations
        |
        v
Pick maximum P&L
```

That is not acceptable.

It produces:

`winner's curse`

and:

`selection bias`.

---

# 10. Parameter Objective

The optimization target is not:

`MAX(P&L)`.

The primary objective is:

`MAX(ExpectedNetEconomicValue)`

subject to:

`Risk`

`Drawdown`

`Execution`

`Calibration`

`Stability`

and:

`OutOfSampleValidity`.

---

# 11. Multi-Objective Evaluation

Every candidate parameterization receives a vector:

```text
Performance =
{
    NetEV,
    TailLoss,
    Drawdown,
    Calibration,
    Stability,
    ExecutionSensitivity,
    RegimeRobustness
}
```

A parameter set that maximizes one metric while catastrophically degrading another is rejected.

---

# 12. Historical Time Ordering

All learning follows:

```text
Past -> Present
```

Never:

```text
Past + Future -> Past
```

For every decision timestamp:

`D_t`

only information:

`I_<=t`

may influence the decision.

---

# 13. Walk-Forward Structure

The historical timeline is divided into sequential blocks.

Conceptually:

```text
TRAIN 1 -> VALIDATE 1 -> TEST 1
                         |
                         v
TRAIN 2 -> VALIDATE 2 -> TEST 2
                         |
                         v
TRAIN 3 -> VALIDATE 3 -> TEST 3
                         |
                         v
...
```

The model never trains on a future block.

---

# 14. Expanding Versus Rolling Training

Two possible structures exist.

`EXPANDING`

```text
TRAIN:
[A]
[A+B]
[A+B+C]
[A+B+C+D]
```

`ROLLING`

```text
TRAIN:
[A]
[B]
[C]
[D]
```

The architecture should support both.

The choice must be determined empirically based on:

`regime persistence`

and:

`parameter stability`.

---

# 15. Why We Do Not Assume One

Markets are non-stationary.

Old information may remain useful.

Old information may also become harmful.

Therefore we measure:

`ValueOfHistory(age)`.

The data determines whether older observations should retain weight.

---

# 16. Recency Weighting

If recency weighting is used:

```text
weight(age) = f(age)
```

The function itself must be validated.

We do not arbitrarily choose:

`0.99`

or:

`0.95`.

---

# 17. Effective Sample Size

Weighted observations do not behave like independent observations.

For weights:

`w_i`

effective sample size is:

`N_eff = (Σw_i)^2 / Σ(w_i²)`.

This becomes a core statistical quantity.

---

# 18. Why N_eff Matters

Suppose:

`1,000,000 ticks`

come from a small number of highly correlated market episodes.

They do not represent:

`1,000,000 independent samples`.

The model must therefore track:

`N_eff`.

---

# 19. Label Formation

For decision time:

`t`

the label is constructed using:

`future interval`

but only after that interval has completely matured.

For example:

```text
Decision:
t

Observation:
I_<=t

Outcome:
O_(t,t+h]

Label:
L_t = function(O_(t,t+h])
```

The outcome cannot enter the decision state at `t`.

---

# 20. Label Families

We maintain separate labels.

`L_direction`

`L_option_return`

`L_net_return`

`L_MFE`

`L_MAE`

`L_horizon`

`L_reversal`

`L_execution`.

This prevents one label from being overloaded.

---

# 21. Direction Label

For a selected horizon:

`H`

define:

```text
R_underlying(t,H)
=
(P_t+H - P_t) / P_t
```

Direction:

```text
UP      if R > threshold
DOWN    if R < -threshold
NEUTRAL otherwise
```

The threshold is itself learned/validated where appropriate.

It cannot simply be assumed to be zero because transaction costs and noise matter.

---

# 22. Option Economic Label

For an actual candidate option:

```text
R_option_net
=
ExitValue
-
EntryCost
-
TransactionCosts
-
Slippage
```

normalized appropriately.

This is the economically relevant label.

---

# 23. MFE

For a long position:

`MFE_t`

is the maximum favorable economic excursion observed after entry and before the label horizon.

Critically:

at decision time:

`MFE = 0`.

As future events arrive:

`MFE`

is updated only retrospectively for training labels.

---

# 24. MAE

Similarly:

`MAE_t`

is the maximum adverse excursion.

This distribution becomes a primary input to risk-model learning.

---

# 25. Horizon Label

Instead of:

`trade lasted X minutes`

we estimate:

`future opportunity persistence`.

The target is therefore a conditional distribution:

`P(Horizon | State_t)`.

This is important because the system predicts duration rather than merely measuring elapsed duration.

---

# 26. Parameter Discovery

For each parameter:

```text
Candidate Parameter
        |
        v
Training Estimate
        |
        v
Validation Evaluation
        |
        v
Stability Test
        |
        v
Frozen Candidate
        |
        v
Untouched Test
```

---

# 27. Example: Profit-Floor Quantile

Suppose the architecture requires:

`Q_profit`.

We do not declare:

`Q = 0.25`.

Instead:

Training estimates the conditional distribution:

`P(FutureGiveback | State, MFE)`.

Candidate quantiles might be evaluated.

The exact candidate grid itself must be predetermined before test evaluation.

---

# 28. Profit-Floor Selection

For every candidate:

`q`

calculate:

`ExpectedNetPnL`

`Drawdown`

`RetainedProfit`

`ExitFrequency`

`ContinuationOpportunity`.

We select a region that satisfies the risk constraints.

Not merely:

`highest P&L`.

---

# 29. Profit-Floor Robustness

Suppose:

`q = 0.23`

performs extremely well.

But:

`q = 0.22`

and:

`q = 0.24`

perform badly.

That is suspicious.

A robust parameter should generally occupy a stable neighborhood.

---

# 30. Parameter Plateau Principle

Prefer:

`stable performance region`

over:

`single optimum`.

Conceptually:

```text
Performance

   ^
   |       ______
   |      /      \
   |_____/        \____
   +--------------------> parameter
```

rather than:

```text
   ^
   |          /\
   |         /  \
   |________/    \____
   +-------------------->
```

The second is highly sensitive.

---

# 31. Reversal Threshold

The reversal mechanism estimates:

`P(reversal | current state)`.

The decision threshold is not:

`50%`.

Instead, it is determined by economic comparison:

```text
ExpectedValue(hold)
vs
ExpectedValue(exit)
```

after:

`cost`

`risk`

and:

`profit protection`.

---

# 32. Continuation Threshold

Similarly:

`ContinuationValue`

must be compared against:

`ExitValue`.

The system holds only when:

```text
ContinuationValue
>
ExitValue
+
RequiredRiskCompensation
```

The compensation term is learned from historical outcomes.

---

# 33. Stop Sensitivity

We do not directly optimize:

`ATR × 1.5`.

Instead we estimate:

`P(MAE | State, Volatility, OptionStructure)`.

The stop is then derived from the conditional adverse distribution.

Therefore:

`StopDistance`

becomes a function:

```text
StopDistance_t
=
f(
    volatility_t,
    liquidity_t,
    option_state_t,
    regime_t,
    confidence_t
)
```

---

# 34. Dynamic ATR

ATR is not itself the stop.

ATR is one measurement of current price variability.

The actual protection boundary derives from:

`conditional adverse excursion`.

Therefore:

`ATR`

is an input.

Not:

`the strategy`.

---

# 35. Volatility Normalization

Many variables should be expressed relative to current volatility.

For example:

```text
NormalizedMove
=
PriceMove / VolatilityScale
```

This allows the model to distinguish:

`10-point move during low volatility`

from:

`10-point move during extreme volatility`.

---

# 36. Volatility Scale

The volatility scale can be derived from rolling distributions.

Potential measures include:

`realized volatility`

`range`

`ATR`

`high-low dispersion`

`intraday return distribution`.

The final feature set is selected through training/validation.

---

# 37. Time-of-Day Conditioning

Every parameter candidate is evaluated conditionally on:

`session position`.

For example:

`opening`

`early session`

`mid-session`

`late session`.

The system does not assume the same statistical distribution throughout the day.

---

# 38. Session Conditioning

A feature therefore conceptually becomes:

`X_t | SessionPhase_t`.

This prevents averaging fundamentally different market behaviors together.

---

# 39. Regime Conditioning

Similarly:

`X_t | VolatilityRegime_t`.

Potential regime classification can use empirical distributions rather than arbitrary labels.

The regime boundaries themselves must be learned and validated.

---

# 40. No Manual Regime Naming

We should not arbitrarily declare:

`ATR < 1% = low volatility`.

Instead, the historical distribution determines meaningful partitions.

---

# 41. Probability Calibration

Raw statistical scores must be converted into calibrated probabilities.

If the system says:

`P = 0.70`

then observations classified around:

`0.70`

should empirically occur approximately:

`70%`

of the time, subject to sampling uncertainty.

---

# 42. Calibration Evaluation

Calibration is evaluated separately from discrimination.

A model can rank opportunities correctly but produce badly calibrated probabilities.

Both properties matter.

---

# 43. Probability Uncertainty

A probability estimate must carry uncertainty.

Conceptually:

`P_UP = 0.72`

is incomplete.

We also need:

`EvidenceStrength`

and:

`Uncertainty`.

A sample-supported:

`0.72`

is not equivalent to a sparse:

`0.72`.

---

# 44. Bayesian Updating

The statistical architecture can use Bayesian updating where appropriate.

Conceptually:

```text
Prior
  |
  v
Current Evidence
  |
  v
Posterior
```

But the prior must itself be constructed only from information historically available at that point.

---

# 45. Empirical Distribution Layer

For quantities such as:

`MFE`

`MAE`

`giveback`

`horizon`

`slippage`

we prefer empirical conditional distributions where sufficient data exists.

This preserves interpretability.

---

# 46. Parametric Distribution Layer

A parametric approximation may be considered only if:

`empirical support`

is insufficient and:

`distributional assumptions`

are validated.

We do not force normality.

---

# 47. Heavy Tails

Financial returns and execution outcomes frequently exhibit non-Gaussian behavior.

Therefore tail quantities should generally be estimated empirically or with validated heavy-tailed models.

We do not assume:

`normal distribution`.

---

# 48. Conditional Quantiles

For protection:

we care about:

`Q_MAE(alpha | State)`.

For profit retention:

we care about:

`Q_Giveback(alpha | State)`.

For execution:

we care about:

`Q_Slippage(alpha | State)`.

These are directly useful to the strategy.

---

# 49. Parameter Stability Test

A parameter must be evaluated across:

`time`

`volatility`

`direction`

`session`

`liquidity`

`execution conditions`.

A parameter that only works in one environment is not globally promoted.

---

# 50. Regime Stability

Suppose:

`ProfitFloor`

works during:

`low volatility`.

But fails during:

`high volatility`.

The system should either:

create a validated conditional parameter

or:

disable trading in the high-volatility state.

---

# 51. Parameter Adaptation

Parameters may evolve over time only through:

`scheduled offline retraining`.

Not:

`arbitrary tick-by-tick optimization`.

The runtime adapts:

`state`.

The offline learner adapts:

`parameters`.

This separation is critical.

---

# 52. Model Freeze

Once a model version is promoted:

all parameters are frozen.

Example:

`MODEL_V17`

contains:

`P1`

`P2`

`P3`

...

Each parameter has a versioned value/distribution.

---

# 53. Model Deployment

A production model is:

```text
MODEL_ID
TRAINING_END
VALIDATION_END
TEST_INTERVAL
PARAMETER_SET
FEATURE_SET
DATA_VERSION
LABEL_VERSION
EXECUTION_ASSUMPTION
```

This makes every trade reproducible.

---

# 54. Walk-Forward Test

For each test window:

the model is frozen before the test window begins.

No:

`parameter changes`

`feature selection`

`threshold adjustment`

or:

`model selection`

using test outcomes.

---

# 55. Test Results

The test produces:

`NetPnL`

`ExpectedValue`

`Drawdown`

`TailLoss`

`Calibration`

`TradeCount`

`CostSensitivity`

`LatencySensitivity`

`RegimePerformance`.

These results remain immutable.

---

# 56. Promotion Criterion

A model is promoted only if it passes all hard conditions.

Conceptually:

```text
VALIDATED
AND
POSITIVE_NET_EV
AND
RISK_LIMIT_OK
AND
CALIBRATION_OK
AND
EXECUTION_ROBUST
AND
REGIME_STABLE
AND
NO_LOOKAHEAD
```

Otherwise:

`REJECT`.

---

# 57. No Single-Metric Promotion

The model cannot be promoted solely because:

`NetPnL > 0`.

Likewise:

`Sharpe > threshold`

alone is insufficient.

The strategy must survive the entire validation contract.

---

# 58. Multiple Testing Control

If:

`N`

candidate models are evaluated, the probability of finding a false winner increases.

Therefore the research process must record:

`number of experiments`

`candidate parameter sets`

`feature variants`

`model variants`.

This is part of the experiment metadata.

---

# 59. Research Registry

Every experiment receives:

`EXPERIMENT_ID`.

It records:

`dataset`

`features`

`parameters`

`label definition`

`training period`

`validation period`

`test period`

`results`.

Nothing disappears.

---

# 60. Failed Experiments

A failed experiment is retained.

We must not delete failures simply because they make the research history look cleaner.

Otherwise the final result suffers from:

`publication bias`.

---

# 61. Parameter Search Budget

The candidate search space must be constrained before evaluation.

We should not repeatedly expand the search because the current result is unsatisfactory.

Otherwise:

`researcher degrees of freedom`

become hidden optimization parameters.

---

# 62. Validation Hierarchy

The evaluation hierarchy becomes:

```text
LEVEL 1
Data correctness

LEVEL 2
Causal correctness

LEVEL 3
Statistical validity

LEVEL 4
Economic validity

LEVEL 5
Execution validity

LEVEL 6
Risk robustness

LEVEL 7
Out-of-sample performance
```

A model cannot skip a lower level because it performs well at a higher one.

---

# 63. Synthetic Validation First

Before historical optimization:

the model must pass the synthetic adversarial suite.

Otherwise parameter optimization would merely optimize a flawed state machine.

This ordering is now mandatory.

---

# 64. Historical Validation Second

After synthetic verification:

we run the model against historical data.

The historical engine must reproduce:

`event order`

`state transitions`

`available information`.

---

# 65. Replay Validation

Where event-level replay is available, the replay must reproduce:

`timestamp`

`sequence`

`quote`

`trade`

and:

`depth`

information as accurately as the source permits.

The strategy remains blind to future replay events.

---

# 66. Paper Execution Layer

Before live capital:

the strategy runs with:

`real-time data`

but:

`simulated execution`.

This measures:

`prediction`

`latency`

`spread`

`slippage assumptions`

and:

`state behavior`.

---

# 67. Shadow Mode

The strategy can generate:

`BUY`

`EXIT`

and:

`NO_TRADE`

decisions without sending orders.

Every decision is logged.

This creates a production-like observational dataset.

---

# 68. Live Deployment

Only after:

`historical validation`

+

`replay validation`

+

`paper/shadow validation`

does actual capital become eligible.

Even then:

`risk limits`

remain independently enforced.

---

# 69. Parameter Learning Frequency

We explicitly separate:

`EVENT-TIME STATE UPDATE`

from:

`PARAMETER UPDATE`.

Every incoming event may update:

`state`.

But parameter updates occur only according to the validated retraining schedule.

---

# 70. Why This Matters

Otherwise:

```text
tick
 -> parameter update
 -> new probability
 -> trade
 -> new outcome
 -> parameter update
```

would create an uncontrolled self-adaptive system.

That is difficult to validate.

Our first production model remains:

`statistically boring`

and:

`auditable`.

---

# 71. Dynamic Runtime

The runtime can still be highly dynamic.

Every event can update:

`volatility`

`flow`

`liquidity`

`expected horizon`

`probability`

`continuation value`

`profit protection`

`execution risk`.

But the mathematical mapping itself remains frozen until a new validated model version is deployed.

---

# 72. Parameter Dependency Graph

Every learned parameter must declare:

`INPUTS`

`LABEL`

`TRAINING WINDOW`

`VALIDATION WINDOW`

`OUTPUT`

`DEPENDENCIES`.

For example:

```text
ProfitFloorQuantile
        |
        +-- MFE
        +-- Giveback
        +-- Volatility
        +-- TradeMode
        +-- Liquidity
        |
        v
ProtectionBoundary
```

---

# 73. No Circular Learning

A learned parameter cannot depend on an outcome generated using that same parameter unless the learning procedure explicitly accounts for the resulting selection bias.

For example:

`StopParameter`

cannot simply learn from:

`trades selected by the same StopParameter`

without careful treatment.

Otherwise the system becomes self-referential.

---

# 74. Selection Bias From Stopping

This is particularly important.

A stop changes:

`observed trade duration`

and:

`observed P&L`.

Therefore:

`Stop`

changes the labels used to evaluate itself.

The research methodology must account for this.

---

# 75. Counterfactual Risk Analysis

For risk parameters, we should evaluate:

"What would have happened under alternative protection boundaries?"

using historical event sequences.

But this analysis must use only information available at each historical timestamp.

---

# 76. Counterfactual Stop Evaluation

For each historical entry:

simulate candidate protection policies:

`S1`

`S2`

`S3`

...

using the actual subsequent event sequence.

The event sequence is the observed future outcome.

The stop parameter is selected only inside training/validation.

---

# 77. Counterfactual Protection Does Not Leak

Using future events to calculate the historical label is legitimate.

Using those future events to determine the parameter before the historical decision is not.

This distinction is essential:

```text
Future events -> label/evaluation

Future events -X-> historical decision state
```

---

# 78. Same Principle for Horizon

For each historical state:

we can observe how long the subsequent opportunity persisted.

That becomes:

`HorizonLabel`.

We cannot expose that future persistence to the historical predictor.

---

# 79. Same Principle for Reversal

We can label:

`whether reversal occurred`.

We cannot use:

`future reversal`

to calculate the state that supposedly predicted it.

---

# 80. Same Principle for Execution

We can measure:

`future realized slippage`.

But entry decision can use only:

`current execution conditions`

and:

`historically learned conditional slippage distribution`.

---

# 81. Final Parameter Registry

Each parameter must eventually have:

```text
ParameterID
Definition
MathematicalFormula
InputVariables
Label
TrainingWindow
ValidationWindow
TestWindow
EstimationMethod
CandidateSearchSpace
SelectionMetric
HardConstraints
StabilityTests
PromotionRule
Version
```

No parameter is allowed to exist outside this registry.

---

# 82. Current Unfrozen Parameter Families

The principal families now awaiting historical estimation are:

`Probability calibration`

`Evidence threshold`

`Horizon distribution`

`Horizon transition sensitivity`

`Continuation value threshold`

`Reversal threshold`

`MFE quantiles`

`MAE quantiles`

`Giveback quantiles`

`Profit-floor quantiles`

`Stop sensitivity`

`Execution-cost distributions`

`Slippage distributions`

`Latency penalty`

`Liquidity thresholds`

`Model degradation thresholds`.

---

# 83. What We Will NOT Do

We will not start by asking:

"What numbers look good?"

We will ask:

"What statistical quantity is this number estimating?"

Then:

"What historical label estimates it?"

Then:

"Can that label be generated causally?"

Then:

"Does the estimate survive walk-forward testing?"

Then:

"Does it remain economically useful after costs?"

---

# 84. Final Mathematical Principle

Every numerical parameter must ultimately have the form:

```text
Parameter_t
=
Estimator(
    HistoricalInformation_<=t
)
```

or:

```text
Parameter
=
FrozenValidatedValue
```

It must never have the form:

```text
Parameter_t
=
function(FutureInformation_>t)
```

---

# 85. Complete Learning Architecture

```text
                  HISTORICAL DATA
                         |
                         v
                CAUSAL RECONSTRUCTION
                         |
                         v
                    STATE_t
                         |
             +-----------+-----------+
             |                       |
             v                       v
       FEATURES_t              FUTURE OUTCOME
             |                       |
             |                       v
             |                    LABEL_t
             |                       |
             +----------+------------+
                        |
                        v
                  TRAINING SET
                        |
                        v
                 PARAMETER ESTIMATE
                        |
                        v
                    VALIDATION
                        |
              +---------+---------+
              |                   |
           REJECT              FREEZE
              |                   |
              |                   v
              |               TEST SET
              |                   |
              |                   v
              |              ROBUSTNESS
              |                   |
              +---------+---------+
                        |
                        v
                   PROMOTION
                        |
                        v
                 MODEL VERSION
                        |
                        v
                 PRODUCTION RUNTIME
```

---

# 86. The Critical Separation

The system now has three completely separate clocks:

`MARKET CLOCK`

Incoming events update the market state.

`DECISION CLOCK`

The strategy evaluates whether to enter, hold, modify protection, or exit.

`LEARNING CLOCK`

Validated historical data updates model parameters.

These clocks must not contaminate one another.

---

# 87. Final Status

Architecture:

`FROZEN`

Mathematical operators:

`SUBSTANTIALLY FROZEN`

State machine:

`FROZEN`

Adversarial invariants:

`FROZEN`

Data capability framework:

`FROZEN`

Numerical parameters:

`INTENTIONALLY UNFROZEN`

Historical estimators:

`NEXT RESEARCH STAGE`

Production implementation:

`NOT YET AUTHORIZED`.

---

# 88. Next Artifact

The next artifact should be:

# THE HISTORICAL EXPERIMENT MATRIX

This will be more concrete than the current parameter specification.

For every parameter family, we will create an exact experiment contract:

```text
PARAMETER
    ->
DATA REQUIRED
    ->
EVENT SAMPLING UNIT
    ->
LABEL
    ->
CONDITIONING VARIABLES
    ->
TRAINING WINDOW
    ->
VALIDATION WINDOW
    ->
PURGE
    ->
EMBARGO
    ->
ESTIMATOR
    ->
CANDIDATE SEARCH
    ->
METRICS
    ->
STABILITY TEST
    ->
OUT-OF-SAMPLE TEST
    ->
PROMOTION RULE
```

Then we can systematically determine **which historical experiments actually need tick data, which need minute data, which can use daily data, and where our TrueData historical limitations genuinely matter**.

That is the point where the entire strategy becomes experimentally executable without prematurely writing code.