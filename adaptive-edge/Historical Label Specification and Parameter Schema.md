# Historical Label Specification and Parameter Schema
## Canonical Learning and Validation Specification — Version 1.0

### 1. Purpose

This specification defines exactly what the system learns from historical data.

It establishes:

`What constitutes an outcome`

`When that outcome becomes observable`

`Which future observations are permitted for labeling`

`How labels are generated`

`How training, validation, and testing are separated`

`Which parameters may change`

`When parameters may change`

`How parameter changes are validated`

`What information is permanently prohibited from entering a historical decision`.

The objective is not to maximize historical returns.

The objective is to estimate relationships that remain valid on unseen future observations.

---

# 2. Fundamental Temporal Rule

For every decision timestamp `t`:

`InformationAvailable(t) = {E_0, E_1, ..., E_t}`

The model may use only:

`InformationAvailable(t)`.

A future observation:

`E_(t+1), E_(t+2), ...`

cannot influence the decision at `t`.

Future observations are permitted only when constructing the historical outcome label for a decision that has already occurred.

Therefore:

`Decision_t = f(History <= t)`

while:

`Label_t = g(FuturePath > t)`.

This distinction is fundamental.

---

# 3. Historical Observation Record

Every historical decision point is represented as:

`O_t = {X_t, P_t, D_t, C_t, Y_t}`

where:

`X_t = feature state`

`P_t = probability state`

`D_t = decision`

`C_t = candidate trade`

`Y_t = future outcome label`.

The feature state is frozen at `t`.

The label is generated afterward.

---

# 4. Label Timestamp

Every label must contain:

`label_start_timestamp = t`

and:

`label_end_timestamp = t + H`

where `H` is the explicitly defined evaluation horizon.

The label generator must never use observations outside its declared horizon.

---

# 5. Horizon Specification

We retain the conceptual horizon structure:

`H1 = <= 3 minutes`

`H2 = >3 to <=5 minutes`

`H3 = >5 to <=15 minutes`

`H4 = >15 to <=30 minutes`

`H5 = >30 to <=45 minutes`

`H6 = >45 minutes / intraday horizon`.

These are **labeling horizons**, not mandatory trading durations.

The exact horizon boundaries remain configurable and must be validated against the actual strategy objective.

---

# 6. Why Multiple Horizons Exist

A single future endpoint is insufficient.

Consider:

`Entry → +10% → +3% → +15% → +8% → Exit`.

A model trained only on the final endpoint loses information about the path.

Therefore the system learns:

`MFE`

`MAE`

`time_to_MFE`

`time_to_MAE`

`target-first`

`stop-first`

`terminal return`

`path volatility`.

This is necessary for dynamic position management.

---

# 7. Directional Label

For a historical underlying state at `t`, define future return:

`R_(t,H) = P_(t+H) / P_t - 1`.

However, a simple positive/negative return label is insufficient for our strategy.

The canonical directional label is therefore based on economically meaningful movement.

For candidate direction `d`:

`d ∈ {UP, DOWN}`.

A direction succeeds if the future path demonstrates sufficient favorable movement before the defined adverse boundary.

---

# 8. Directional Path Label

For UP:

`MFE_UP(t,H) = max(P_(t,t+H)) - P_t`.

For DOWN:

`MFE_DOWN(t,H) = P_t - min(P_(t,t+H))`.

Similarly:

`MAE_UP(t,H) = P_t - min(P_(t,t+H))`.

`MAE_DOWN(t,H) = max(P_(t,t+H)) - P_t`.

These are expressed in normalized units when comparing different instruments.

---

# 9. Three-State Directional Label

At each horizon:

`Y_direction ∈ {UP, DOWN, NEUTRAL}`.

The exact classification is not based on an arbitrary fixed percentage.

Instead, the movement boundaries are derived from the contemporaneous volatility state.

Conceptually:

`MovementThreshold_t = f(Volatility_t, Instrument_t, Liquidity_t, ExecutionCost_t)`.

Then:

`UP` if favorable movement exceeds the validated threshold.

`DOWN` if adverse movement exceeds the validated threshold.

`NEUTRAL` otherwise.

The threshold function is learned from training data.

---

# 10. Why Fixed Return Labels Are Rejected

A fixed label such as:

`+0.5% = UP`

would behave differently under:

`Low volatility`

versus:

`Extreme volatility`.

The same percentage movement can represent completely different statistical events.

Therefore the label must be normalized relative to the contemporaneous market state.

---

# 11. MFE Label

For each decision timestamp:

`MFE_H(t)`

is the maximum favorable executable movement within horizon `H`.

For long exposure:

`MFE_H = max(ExecutableSellPrice_(t:t+H)) - ExecutableEntryPrice`.

For short exposure:

`MFE_H = ExecutableEntryPrice - min(ExecutableBuyPrice_(t:t+H))`.

The use of executable prices rather than theoretical mid-prices is important.

---

# 12. MAE Label

For long exposure:

`MAE_H = ExecutableEntryPrice - min(ExecutableSellPrice_(t:t+H))`.

For short exposure:

`MAE_H = max(ExecutableBuyPrice_(t:t+H)) - ExecutableEntryPrice`.

MAE therefore represents actual economically accessible adverse excursion.

---

# 13. Option-Level Labels

Because we trade options, the system must maintain two distinct label spaces.

Underlying label:

`Y_underlying`.

Option label:

`Y_option`.

The underlying tells us whether the directional thesis was correct.

The option tells us whether the chosen contract was economically effective.

This distinction prevents the system from incorrectly concluding:

"Underlying prediction was correct, therefore option trade was good."

That is false when:

`Spread`

`IV`

`Theta`

`Gamma`

`Liquidity`

or:

`Slippage`

destroy the expected value.

---

# 14. Option MFE

For candidate option `i`:

`MFE_option_i,H`

is measured using executable option prices.

Similarly:

`MAE_option_i,H`.

The option label therefore captures the actual tradability of the contract.

---

# 15. Target-First Label

For a candidate target `G` and adverse boundary `L`:

`Y_target_first = 1`

if the target is reached before the adverse boundary within the specified horizon.

Otherwise:

`Y_target_first = 0`.

But ties and simultaneous boundary crossings must be handled by actual event ordering.

No arbitrary bar-level assumption such as:

"high happened before low"

is permitted when tick/event ordering is available.

---

# 16. Stop-First Label

Similarly:

`Y_stop_first = 1`

if the adverse boundary is reached before the target.

If neither occurs:

`Y_neither = 1`.

Therefore:

`Y_target_first + Y_stop_first + Y_neither = 1`.

---

# 17. Boundary Ordering

When both target and adverse boundary appear inside the same aggregated interval, the system must use the finest available historical ordering.

If tick-level ordering is available:

`TickOrder`.

If only lower-resolution data exists:

the observation is marked:

`AMBIGUOUS`.

It must not be assigned arbitrarily.

This is particularly important during high-volatility periods.

---

# 18. Time-to-Event Labels

For each candidate:

`T_MFE = time at which maximum favorable excursion occurs`.

`T_MAE = time at which maximum adverse excursion occurs`.

Also:

`T_target = first time target is reached`.

`T_stop = first time adverse boundary is reached`.

These labels allow the horizon model to learn the temporal structure of trades.

---

# 19. Continuation Label

For an already profitable historical position at time `t`, define:

`FutureIncrementalPnL_H`

as the additional net P&L available after `t`.

The continuation label is:

`Y_continuation = FutureIncrementalPnL_H`.

This is superior to simply asking whether price rises.

The model is learning:

"Given that I am already in this position, is remaining exposure economically valuable?"

---

# 20. Reversal Label

A reversal is defined relative to the current position direction.

For a long position:

`Reversal = future adverse movement sufficient to invalidate the current continuation state`.

For a short position:

the inverse applies.

The reversal label must incorporate:

`Price`

`Order Flow`

`Liquidity`

`Volatility`

and:

`Position State`.

The exact invalidation boundary is learned and validated.

---

# 21. Profit-Giveback Label

At each historical profitable state:

`PeakNetPnL_t`

is known from the path before `t`.

Future drawdown from that peak is:

`FutureGiveback_H = PeakNetPnL_t - min(FutureNetPnL)`.

The distribution:

`F_G(g | CurrentState, ProfitState)`

becomes the training target for profit protection.

This directly trains the backward protection mechanism.

---

# 22. Profit-Floor Label

The model learns the conditional distribution:

`P(Giveback <= g | State_t, ProfitState_t)`.

The eventual production profit floor is therefore based on a conditional distribution rather than:

`fixed percentage of peak profit`.

---

# 23. Regime Label

Each historical state receives a future regime label.

For example:

`TREND`

`MEAN_REVERSION`

`BREAKOUT`

`ABSORPTION`

`EXHAUSTION`

`HIGH_VOLATILITY`

`LOW_LIQUIDITY`.

However, these names are descriptive.

The actual regime definition must be based on measurable statistical properties.

The system must not train on manually labeled chart patterns.

---

# 24. Regime Label Construction

A future regime label is derived from future market behavior:

`FutureReturnDistribution`

`FutureVolatility`

`FutureDirectionalEfficiency`

`FutureFlowBehavior`

`FutureLiquidityBehavior`.

The resulting regime is assigned after the fact.

That label is then associated with:

`State_t`.

The model learns:

`P(FutureRegime | CurrentState)`.

---

# 25. Horizon Label

For each historical state:

`Y_H = actual time required for the relevant future event`.

Examples:

`TimeToTarget`

`TimeToMFE`

`TimeToReversal`.

The model therefore learns a conditional horizon distribution rather than a single deterministic duration.

---

# 26. Execution Labels

Every historical candidate also receives:

`ExpectedSlippage`

`RealizedSlippage`

`SpreadAtDecision`

`SpreadAtExecution`

`Latency`

`FillProbability`.

This allows the system to distinguish:

"the market signal was correct"

from:

"the trade was actually executable."

---

# 27. Full Historical Label Vector

Each historical observation can therefore produce:

`Y_t = {`

`Y_direction`

`Y_MFE`

`Y_MAE`

`Y_target_first`

`Y_stop_first`

`Y_horizon`

`Y_continuation`

`Y_reversal`

`Y_giveback`

`Y_regime`

`Y_execution`

`Y_net_PnL`

`}`

Not every label is necessarily available immediately.

Each label has its own maturity timestamp.

---

# 28. Label Maturity

A label is usable for learning only after its full observation window has elapsed.

If:

`Decision_t`

has horizon:

`H = 45 minutes`

then the label cannot become training data before:

`t + 45 minutes`.

If a longer outcome label requires the remainder of the session:

it becomes available only after session completion.

---

# 29. No Partial Label Leakage

Suppose a 45-minute label is still maturing.

The model cannot use the partially observed outcome as though it were complete.

Therefore:

`IncompleteLabel = EXCLUDED`.

This prevents subtle leakage.

---

# 30. Training Observation Construction

For model version `M_k`, define:

`TrainingCutoff = T_train`.

Every training observation must satisfy:

`DecisionTimestamp <= T_train`

and:

`LabelMaturityTimestamp <= T_train`.

This second condition is critical.

A decision may be old enough to look historical while its label is not yet fully known.

---

# 31. Validation Window

After training:

`Training`

→ `Validation`.

Validation observations must be strictly later than the training observations.

No parameter fitting is performed on validation outcomes except where explicitly part of a nested validation procedure.

---

# 32. Test Window

The final test set is untouched until all model decisions have been frozen.

The order is:

`TRAIN`

→ `VALIDATE`

→ `FREEZE`

→ `TEST`.

The test set is not used to:

`choose features`

`choose thresholds`

`choose models`

`choose weights`

or:

`tune parameters`.

---

# 33. Walk-Forward Structure

The canonical structure is:

```text
TIME ------------------------------------------------------------>

|---- TRAIN ----|-- VALIDATE --|-- TEST --|

                    advance

       |---- TRAIN ----|-- VALIDATE --|-- TEST --|

                                  advance

              |---- TRAIN ----|-- VALIDATE --|-- TEST --|
```

Each subsequent cycle moves forward in time.

No observation travels backward.

---

# 34. Expanding Versus Rolling Training

Two approaches are permitted for evaluation.

Expanding:

`Train = all valid history before cutoff`.

Rolling:

`Train = most recent W observations before cutoff`.

The system should evaluate both.

The final choice must be based on:

`Out-of-sample stability`

rather than historical return alone.

---

# 35. Regime-Aware Training

Because Indian markets change over time, the training process must preserve regime diversity.

The training sample should therefore be evaluated for:

`Volatility regimes`

`Trend regimes`

`Liquidity regimes`

`Market-event regimes`

`Time-of-day regimes`.

The model must not accidentally train almost entirely on one market condition.

---

# 36. Time-of-Day Stratification

The system should maintain conditional distributions by:

`MarketOpen`

`Morning`

`Midday`

`Afternoon`

`PreClose`.

The exact boundaries remain data-dependent.

This matters because:

`Volume`

`Spread`

`Volatility`

`Liquidity`

and:

`ExecutionQuality`

are strongly time-dependent in intraday Indian markets.

---

# 37. Instrument Stratification

Training data must distinguish:

`Index`

`Stock`

`Option`.

A feature distribution learned from NIFTY cannot automatically be assumed valid for an individual stock option.

The hierarchy is therefore:

`Instrument`

→ `InstrumentClass`

→ `MarketContext`.

---

# 38. Expiry Stratification

Option behavior changes with time to expiry.

Therefore the model context should include:

`DaysToExpiry`

or an equivalent continuous expiry-state representation.

The model must not treat:

`far-from-expiry`

and:

`near-expiry`

as statistically identical without validation.

---

# 39. Parameter Registry

Every learned parameter receives:

`ParameterID`

`Name`

`Model`

`Definition`

`AllowedRange`

`TrainingData`

`ValidationMethod`

`UpdateFrequency`

`PromotionRule`

`CurrentVersion`.

---

# 40. Parameter Categories

### Probability parameters

`β`

`λ`

`calibration parameters`

`Bayesian priors`

`fusion weights`.

### Distribution parameters

`similarity bandwidth`

`kernel parameters`

`quantiles`

`tail parameters`.

### Risk parameters

`risk-budget coefficients`

`position-sizing coefficients`.

### Management parameters

`continuation thresholds`

`reversal thresholds`

`giveback quantiles`

`regime-transition sensitivity`.

### Operational parameters

`data-quality thresholds`

`execution-quality thresholds`.

---

# 41. Parameter Immutability During a Trading Session

Once a production model is activated:

`θ_session = constant`.

The parameters cannot change merely because today's market behaves differently.

Otherwise the strategy could unintentionally adapt to outcomes that are not yet statistically validated.

Real-time adaptation happens through:

`State_t`

not through arbitrary parameter mutation.

---

# 42. Parameter Update Boundary

A new parameter set can only be introduced after:

`Training`

→ `Validation`

→ `Test`

→ `Promotion`.

Then:

`θ_(k+1)`

replaces:

`θ_k`.

The replacement timestamp is recorded.

---

# 43. Parameter Versioning

Every decision records:

`ModelVersion`

and:

`ParameterVersion`.

Therefore every historical trade can answer:

"Exactly which mathematical configuration generated this decision?"

---

# 44. Parameter Drift

A parameter should not be changed simply because:

`RecentPnL < historicalPnL`.

Parameter updates require evidence of:

`distribution shift`

or:

`persistent degradation`.

Otherwise the learning engine may chase random noise.

---

# 45. Feature Selection Governance

A new feature cannot enter production merely because it improves historical backtest return.

It must demonstrate:

`Incremental predictive information`

and:

`Out-of-sample stability`.

The feature must also have:

`causal timestamp validity`

and:

`data availability`.

---

# 46. Feature Removal

A feature should be removed when it demonstrates:

`No incremental information`

or:

`unstable out-of-sample behavior`

or:

`excessive missingness`

or:

`unacceptable latency`

or:

`dependency on unavailable production data`.

---

# 47. Parameter Search Constraint

Parameter optimization must be performed inside the training/validation process.

The system must never:

`Run entire historical period`

→ `find best parameters`

→ `declare success`.

That is classic in-sample optimization.

---

# 48. Multiple Testing Protection

If many feature combinations and parameter sets are tested, some will appear successful by chance.

Therefore the evaluation must track:

`NumberOfExperiments`

and use appropriate multiple-testing controls.

A strategy that survives one test after thousands of unrecorded alternatives is not credible.

---

# 49. Selection Bias Control

Every experiment must be logged:

`ExperimentID`

`Hypothesis`

`Features`

`Parameters`

`TrainingWindow`

`ValidationWindow`

`TestWindow`

`Result`

`Decision`.

This prevents selective reporting of successful experiments.

---

# 50. Purging

When observations have overlapping future horizons, ordinary random splitting is invalid.

Example:

Observation A at:

`t`

has a label extending to:

`t + 45m`.

Observation B at:

`t + 10m`

has another label extending to:

`t + 55m`.

These observations share future information.

Therefore overlapping observations around validation boundaries must be purged.

---

# 51. Embargo

After the training period, an embargo interval may be imposed before validation/test observations are admitted.

Conceptually:

`TRAIN | EMBARGO | VALIDATE | EMBARGO | TEST`.

The embargo length must reflect the maximum label horizon and any dependency introduced by feature windows.

---

# 52. Feature Lookback Constraint

If a feature uses a lookback:

`W`.

Then the earliest information available at time `t` is:

`t-W`.

The feature is valid only if:

`All data <= t`.

No future-centered rolling statistics are permitted.

---

# 53. Profile Lookback Constraint

A profile at `t` must be:

`Profile_t = Profile(events <= t)`.

A completed end-of-day profile cannot be used to calculate a morning feature.

---

# 54. Normalization Constraint

For every normalized feature:

`μ_t`

and:

`σ_t`

must be computed only from data available before or at `t`.

Not:

`μ_full_dataset`.

Not:

`σ_full_dataset`.

This is one of the most common sources of hidden look-ahead bias.

---

# 55. Option Chain Constraint

Option selection at `t` may use only contracts and market information observable at `t`.

The system cannot know:

`future liquidity`

`future IV`

`future spread`

or:

`future option price`.

Those belong to the outcome label.

---

# 56. Survivorship Bias

The historical universe must include instruments that existed at each historical time.

The system must not construct a historical universe using only today's surviving/liquid instruments.

Otherwise the historical dataset is biased toward survivors.

---

# 57. Corporate Action Handling

For stocks, historical data must account for:

`Splits`

`Bonuses`

`Corporate actions`

`Symbol changes`.

The adjustment methodology must preserve consistency between:

`historical price`

`volume`

`option contracts`

and:

`instrument identity`.

This remains partly dependent on the actual TrueData historical data semantics.

---

# 58. Transaction-Cost Labels

Every historical trade outcome must include:

`Brokerage`

`Exchange charges`

`Taxes`

`Slippage`

`Spread`

`Execution latency`.

The exact values will be sourced from the production execution environment.

Until then:

`CostModel = TBD`.

A backtest without realistic costs is not considered production evidence.

---

# 59. Stress Labeling

Historical outcomes should additionally be tagged by:

`Normal`

`HighVolatility`

`LiquidityShock`

`FastTrend`

`SharpReversal`

`Gap/Event`.

This allows us to evaluate whether the model's apparent edge comes from only one favorable regime.

---

# 60. Parameter Stability Test

For every important learned parameter:

`θ`

we evaluate:

`θ_1, θ_2, ..., θ_n`

across walk-forward periods.

A robust parameter should not require an extremely narrow value to remain profitable.

If:

`θ = 0.731`

works spectacularly but:

`θ = 0.729`

and:

`θ = 0.733`

fail,

that is evidence of instability and possible overfitting.

---

# 61. Performance Stability

We evaluate:

`MeanNetPnL`

`MedianNetPnL`

`WinRate`

`ProfitFactor`

`ExpectedValue`

`MaxDrawdown`

`TailLoss`

`MAE`

`MFE`

`CalibrationError`

`ExecutionSlippage`.

No single metric determines promotion.

---

# 62. Distributional Validation

The model's predicted probabilities must be compared with actual frequencies.

For example, among observations predicted:

`P_up ≈ 0.70`

the realized frequency should approach approximately:

`70%`

within statistical uncertainty.

This is calibration.

A model can have good directional accuracy but poor probability calibration.

Our system requires both.

---

# 63. Expected Calibration Error

For probability bins `B_k`:

`ECE = Σ_k (|B_k|/N) × |accuracy(B_k) - confidence(B_k)|`.

The exact binning method is configurable.

Calibration must be evaluated out-of-sample.

---

# 64. Economic Validation

A statistically predictive feature is not necessarily economically useful.

Therefore:

`PredictiveEdge`

must ultimately translate into:

`PositiveNetEV`.

The model must survive:

`ExecutionCost`

`Slippage`

`PositionConstraints`

`RiskConstraints`.

---

# 65. Parameter Promotion Gate

A new model version may be promoted only if:

`OutOfSampleEV > RequiredEvidence`

AND

`Calibration acceptable`

AND

`Drawdown acceptable`

AND

`TailLoss acceptable`

AND

`Parameter stability acceptable`

AND

`Execution robustness acceptable`

AND

`No look-ahead detected`.

The exact numerical criteria remain learned/validated policy parameters.

---

# 66. Champion-Challenger Structure

Production uses:

`ChampionModel`.

A new candidate is:

`ChallengerModel`.

Both can be evaluated on the same future validation stream, but the challenger cannot influence production decisions until formally promoted.

This prevents uncontrolled online experimentation.

---

# 67. Parameter Update Hierarchy

The update hierarchy is:

```text
RAW DATA
   |
   v
FEATURE PARAMETERS
   |
   v
PROBABILITY PARAMETERS
   |
   v
ECONOMIC PARAMETERS
   |
   v
RISK PARAMETERS
   |
   v
MANAGEMENT PARAMETERS
```

A downstream parameter must not silently modify an upstream probability model.

---

# 68. Immutable Structural Parameters

The following are not learned from market outcomes:

`State-machine topology`

`Temporal causality`

`No-lookahead rules`

`Probability normalization`

`Stop monotonicity`

`Position existence rules`

`Fill/close definitions`

`Model versioning`

`Data safety invariants`.

These are architectural constraints.

---

# 69. Adaptable Parameters

The following may adapt through validated learning:

`Probability coefficients`

`Calibration`

`Feature weights`

`Conditional distributions`

`Risk mapping`

`Continuation threshold`

`Reversal threshold`

`Giveback quantile`

`Regime sensitivity`

`Execution-cost model`.

---

# 70. Never Automatically Adaptive

The following must never be changed merely from live P&L:

`Risk invariants`

`Maximum allowable exposure`

`No-lookahead rules`

`State transitions`

`Hard safety conditions`.

Otherwise the system can learn to violate the rules that were supposed to protect it.

---

# 71. Historical Replay Requirement

Before any live deployment, every historical event must be replayable in chronological order.

At event `t`, the replay engine must reconstruct:

`State_t`

`Features_t`

`Probabilities_t`

`Decision_t`.

The result must be identical when replayed again using the same model version.

This gives us deterministic reproducibility.

---

# 72. Reproducibility Requirement

For fixed:

`DataVersion`

`ModelVersion`

`ParameterVersion`

`ExecutionModelVersion`

the system must produce:

`identical state transitions`.

If two runs produce different decisions, the system is not yet sufficiently specified.

---

# 73. Historical Dataset Version

Every training dataset receives:

`DatasetVersion`.

It records:

`Data source`

`Date range`

`Instrument universe`

`Cleaning rules`

`Corporate-action treatment`

`Missing-data rules`

`Timestamp policy`

`Label version`.

A model cannot simply say:

"trained on five years of data."

It must identify the exact dataset version.

---

# 74. Label Version

Labels themselves receive:

`LabelVersion`.

If we change:

`MFE definition`

or:

`target-first logic`

or:

`cost treatment`

then:

`LabelVersion`

must change.

Old and new models cannot silently share incompatible labels.

---

# 75. Parameter Registry Example

```text
PARAM-001
Name: DirectionModelCoefficients
Type: Learned
Model: DirectionModel
Training: Walk-forward
Validation: Out-of-sample
Update: Model promotion
Status: TBD

PARAM-002
Name: ProbabilityCalibration
Type: Learned
Model: Calibration
Training: Validation data
Update: Model promotion
Status: TBD

PARAM-003
Name: GivebackQuantile
Type: Learned
Model: ProfitProtection
Training: Walk-forward
Status: TBD

PARAM-004
Name: ContinuationBoundary
Type: Learned
Model: PositionManagement
Training: Walk-forward
Status: TBD

PARAM-005
Name: ReversalBoundary
Type: Learned
Model: ReversalModel
Training: Walk-forward
Status: TBD

PARAM-006
Name: RiskMapping
Type: Learned
Model: RiskEngine
Training: Walk-forward
Status: TBD
```

---

# 76. Complete Learning Pipeline

The canonical learning pipeline is:

```text
Historical Events
       |
       v
Chronological Replay
       |
       v
State Reconstruction
       |
       v
Feature Snapshot at t
       |
       v
Decision Snapshot at t
       |
       v
Wait Until Label Matures
       |
       v
Generate Outcome Label
       |
       v
Historical Dataset
       |
       v
Purging / Embargo
       |
       v
Training
       |
       v
Validation
       |
       v
Parameter Freeze
       |
       v
Unseen Test
       |
       v
Robustness Tests
       |
       v
Champion/Challenger
       |
       v
Promotion
```

---

# 77. The Most Important Rule

The model is never allowed to learn from:

`What happened after the decision`

until that information has become historically available according to the label's maturity timestamp.

This means our five-year historical replay does **not** magically give the model five years of knowledge on day one.

Instead:

`Day 1 model`

knows only:

`History before Day 1`.

Then it evolves:

`Day 2`

using information that would actually have been available by Day 2.

And so on.

This is how we obtain the desired historical evolution without creating the illusion that the model possessed future knowledge.

---

# 78. Five-Year Walk-Forward Simulation

If we have five years of historical data:

```text
Year 1
   |
   v
Initial Model
   |
   v
Walk forward
   |
   v
Year 2
   |
   v
Updated Model
   |
   v
Walk forward
   |
   v
Year 3
   |
   v
Updated Model
   |
   v
Year 4
   |
   v
Updated Model
   |
   v
Year 5
```

At every point:

`Model_t`

knows only:

`Data <= t`.

This gives us the evolutionary behavior we wanted earlier without look-ahead bias.

---

# 79. Final Parameter Governance Rule

Every learned parameter must answer five questions:

`What does it control?`

`What data estimates it?`

`What historical period estimates it?`

`What validation proves it is stable?`

`What event permits it to change?`

If any parameter cannot answer all five, it cannot enter production.

---

# 80. Current Status

At this point:

`Architecture = defined`

`Variables = defined`

`Dependencies = defined`

`State transitions = defined`

`Operators = defined`

`Labels = defined`

`Parameter categories = defined`

`Learning boundaries = defined`

`Walk-forward structure = defined`

`Look-ahead controls = defined`

`Parameter governance = defined`.

Still unresolved:

`TrueData exact field mapping`

`Historical availability`

`Exact execution-cost schedule`

`Exact learned numerical parameters`

`Final empirical horizon boundaries`

`Final feature subset`

`Final parameter values`.

These remain deliberately unresolved.

---

# 81. Next Mandatory Exercise

Before implementation, we should now perform the exercise you proposed:

# BRUTAL ADVERSARIAL MATHEMATICAL ATTACK

We should attempt to break the entire specification.

Not by asking:

"Does it work?"

but by asking:

"Under what conditions does this system fail catastrophically?"

We should construct synthetic scenarios including:

`False breakout`

`Immediate reversal`

`Extreme volatility spike`

`Liquidity disappearance`

`Bid/ask explosion`

`Order-flow spoof-like behavior`

`Delta-price divergence`

`Delayed feed`

`Dropped ticks`

`Duplicate ticks`

`Out-of-order events`

`Option spread explosion`

`IV shock`

`Gamma acceleration`

`Near-expiry behavior`

`Zero-volume periods`

`Sudden market-wide shock`

`Repeated whipsaws`

`Long profitable trade followed by reversal`

`Short profitable trade followed by reversal`

`Scalp-to-intraday transition`

`Intraday-to-scalp transition`

`Partial fill`

`No fill`

`Stop slippage`

`Simultaneous target/stop conditions`

`Model probability overconfidence`

`Distribution drift`

`Parameter instability`.

For each scenario, we should calculate the state transitions manually and ask:

`What does the system believe?`

`What does it do?`

`What should it do?`

`Can it lose more than intended?`

`Can it accidentally widen risk?`

`Can it use future information?`

`Can it get stuck in a state?`

`Can it generate contradictory decisions?`

`Can it repeatedly trade the same bad condition?`

`Can execution invalidate the mathematical edge?`

That adversarial pass should happen **before we bind the system to TrueData and before implementation**.