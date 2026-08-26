# CANONICAL STATISTICAL ESTIMATION AND CALIBRATION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how the strategy converts historical observations into statistically estimated quantities.

The baseline philosophy is:

```text
Simple
Causal
Empirical
Calibrated
Uncertainty-aware
Auditable
```

The baseline model does not use:

```text Neural Networks
Reinforcement Learning
LLMs
Deep Learning
```

unless a later research stage provides strong evidence that the baseline architecture is insufficient.

---

# 2. Statistical Architecture

The baseline statistical pipeline is:

```text
Historical Opportunities
        ↓
Causal Conditioning
        ↓
Empirical Conditional Distribution
        ↓
Sample Sufficiency Check
        ↓
Statistical Estimator
        ↓
Probability / Distribution
        ↓
Calibration
        ↓
Uncertainty Assessment
        ↓
Economic Evaluation
```

---

# 3. Core Statistical Object

At decision time `t`, define:

```text F_t
```

as the information state available at `t`.

For an outcome `Y`:

```text P(Y | F_t)
```

is the canonical target.

The system never estimates:

```text P(Y | F_t, Future_t)
```

for live decision-making.

---

# 4. Conditioning State

The information state may contain:

```text DirectionalEvidence
VolatilityState
MomentumState
MarketStructureState
TimeOfDayState
OpeningRangeState
OptionState
```

but only variables that have been validated as predictive and are available at `t`.

---

# 5. Baseline Estimator

The default estimator is empirical.

For a binary event:

```text Y ∈ {0,1}
```

and historical conditioning population:

```text D(F_t)
```

define:

```text p_hat
=
Σ w_i Y_i
/
Σ w_i
```

where:

```text w_i
```

is an explicitly defined observation weight.

The default is:

```text w_i = 1
```

unless a research experiment explicitly evaluates another weighting scheme.

---

# 6. Why Empirical First

The empirical estimator has several advantages:

```text transparent
easy to reproduce
low parameter count
easy to audit
easy to stress-test
difficult to hide model assumptions.
```

The system therefore begins with the least complex estimator capable of representing the required conditional relationship.

---

# 7. Conditioning Population

For a current state:

```text F_t = f
```

the historical conditioning population is:

```text D_f
=
{i : historical state_i satisfies the declared conditioning rule}
```

The conditioning rule must be defined before evaluating its forward performance.

---

# 8. Exact-Match Conditioning

A naïve approach would require:

```text F_i == F_t
```

for historical observations.

This is generally too sparse for continuous variables.

Therefore the baseline system uses explicitly defined state partitions or bins.

---

# 9. State Binning

Continuous variables may be transformed into discrete states.

For example:

```text VolatilityState
=
LOW / NORMAL / HIGH
```

or:

```text quantile-based bins.
```

The binning rule itself is a learned/configured research parameter and must be determined without future information.

---

# 10. Binning Leakage Rule

Historical bins used at time `t` must be computed using information available by `t`.

For example, a percentile threshold must not be calculated from the entire future dataset.

Correct:

```text historical data up to t
        ↓
threshold
        ↓
current state.
```

Incorrect:

```text entire dataset
        ↓
threshold
        ↓
historical state.
```

---

# 11. Conditional Probability

For condition `C`:

```text p_hat(C)
=
N(Y=1 | C)
/
N(C)
```

This is the baseline probability estimate.

---

# 12. Sample Sufficiency

A probability estimate cannot be trusted merely because it can be calculated.

The system therefore requires:

```text minimum effective sample requirement.
```

The exact numerical threshold is:

```text UNFROZEN.
```

---

# 13. Effective Sample Size

When observations are correlated, raw count is insufficient.

For weighted observations:

```text ESS
=
(Σw_i)^2
/
Σ(w_i²)
```

For the baseline:

```text w_i = 1
```

but serial dependence may still reduce effective information.

The research system must therefore separately record:

```text raw sample count
effective sample estimate
```

where appropriate.

---

# 14. Sparse State Handling

If a conditioning state has insufficient historical evidence:

```text ProbabilityState = INSUFFICIENT_DATA
```

The system does not manufacture a precise probability.

The decision engine then follows the explicit:

```text insufficient-evidence policy.
```

The baseline policy is:

```text NO_TRADE.
```

---

# 15. Hierarchical Fallback

A sparse state may optionally fall back to a broader parent population.

Example:

```text ExactState
    ↓ insufficient data
Volatility + Direction
    ↓ insufficient
Direction only
    ↓ insufficient
Global population
```

Every fallback level must be predefined.

The model cannot dynamically search for whichever historical subset produces the best probability.

---

# 16. Fallback Integrity

The fallback hierarchy must be:

```text deterministic
ordered
versioned
fixed before evaluation.
```

No performance-based fallback selection is permitted.

---

# 17. Bayesian Smoothing

Bayesian smoothing may be used to stabilize sparse binary probabilities.

The canonical baseline is the Beta-Binomial formulation.

Prior:

```text p ~ Beta(α, β)
```

Observed:

```text successes = S
failures = F
```

Posterior:

```text p | D
~
Beta(α + S, β + F)
```

Posterior mean:

```text E[p | D]
=
(α + S)
/
(α + β + S + F)
```

---

# 18. Bayesian Prior Policy

The prior must not encode an arbitrary belief chosen to improve historical performance.

Baseline:

```text weakly informative / symmetric prior.
```

Exact:

```text α, β = UNFROZEN.
```

They must be determined under the research protocol.

---

# 19. Empirical Versus Bayesian Decision

The architecture supports:

```text Empirical estimator
Bayesian-smoothed estimator
```

but they are treated as candidate statistical specifications.

The selection criterion is:

```text out-of-sample calibration
+
economic usefulness
+
stability
```

not in-sample P&L.

---

# 20. Calibration

A model producing:

```text P = 0.70
```

should correspond approximately to:

```text 70% observed event frequency
```

over sufficiently large populations of comparable predictions.

This is calibration.

---

# 21. Calibration Dataset

Calibration parameters must be learned using data separate from the data used to fit the underlying estimator where required by the selected methodology.

The calibration layer cannot inspect forward outcomes.

---

# 22. Calibration Methods

The architecture permits simple methods such as:

```text empirical bin calibration
isotonic regression
logistic calibration
Beta calibration
```

but the baseline should begin with the simplest method supported by sample size.

---

# 23. Calibration Complexity Rule

If:

```text raw probability
```

is already adequately calibrated, no calibration layer is required.

Additional calibration complexity must demonstrate measurable benefit.

---

# 24. Calibration Metrics

The research system should measure:

```text Brier Score
Log Loss
Calibration Error
Reliability Curve
```

and relevant discrimination metrics where appropriate.

No single metric is sufficient.

---

# 25. Discrimination Versus Calibration

These are different properties.

A model can:

```text rank outcomes correctly
```

while producing:

```text poorly calibrated probabilities.
```

The strategy uses probabilities economically, so calibration is essential.

---

# 26. Probability Confidence

The system must distinguish:

```text estimated probability
```

from:

```text confidence in the estimate.
```

For example:

```text p = 0.72
```

with:

```text N = 12
```

is not equivalent to:

```text p = 0.72
```

with:

```text N = 12000.
```

---

# 27. Uncertainty Representation

The probability engine should support:

```text point estimate
uncertainty interval
sample size
effective sample size
conditioning state
model version
```

The exact interval methodology remains open.

---

# 28. Conservative Probability

Where uncertainty is material, the decision engine may use a conservative probability estimate.

Conceptually:

```text p_conservative
=
lower confidence/credible bound
```

rather than the point estimate.

The exact construction is intentionally unfrozen.

---

# 29. Distribution Estimation

For continuous outcomes:

```text Y ∈ R
```

the baseline target is:

```text empirical conditional distribution:
F(y | C)
```

rather than immediately assuming:

```text Normal distribution.
```

---

# 30. Why Empirical Distributions

Trading outcomes often exhibit:

```text skewness
fat tails
heteroskedasticity
regime dependence
```

Therefore a parametric distribution should not be assumed without evidence.

---

# 31. Empirical CDF

Given observations:

```text Y_1 ... Y_n
```

the empirical cumulative distribution function is:

```text F_hat(y)
=
(1/n)
Σ I(Y_i <= y)
```

subject to the declared weighting scheme.

---

# 32. Quantile Estimation

The profit-floor quantity is derived from:

```text Q_q(Y | C)
```

where `q` is a learned/configured quantile.

The exact `q` is not frozen.

---

# 33. Quantile Stability

A quantile is considered useful only if it demonstrates sufficient stability across:

```text walk-forward folds
market regimes
reasonable parameter perturbations.
```

A quantile that produces an edge only in one historical period is not accepted.

---

# 34. Conditional Quantile

The canonical profit-floor model is therefore:

```text ProfitFloor_t
=
Q_q(
FutureOutcome
|
F_t
)
```

where the historical population is causally eligible at `t`.

---

# 35. Expected Value

Expected value is:

```text E[Y | F_t]
```

estimated from the historical conditional distribution.

But the decision engine should not rely exclusively on the mean.

---

# 36. Tail Information

The system records:

```text lower quantile
median
mean
upper quantile
```

where sample sufficiency allows.

This provides a more complete representation of outcome uncertainty.

---

# 37. Expected Holding Horizon

For duration:

```text H
```

the system may estimate:

```text E[H | F_t]
```

and/or its conditional distribution.

This remains distinct from the label horizon.

---

# 38. Time-to-Event Estimation

If the research requires estimating:

```text probability that an economic condition persists until time h
```

a survival-analysis formulation may be appropriate.

The architecture allows:

```text survival function S(h | F_t)
```

without requiring it in the baseline implementation.

---

# 39. Continuation Probability

A continuation event can be defined as:

```text C_h = 1
```

if the predefined continuation condition remains satisfied through horizon `h`.

Then:

```text P(C_h = 1 | F_t)
```

is estimated using the same causal historical procedure.

---

# 40. Emergency Reversal Probability

Similarly:

```text R_h = 1
```

if the predefined reversal condition occurs within horizon `h`.

Then:

```text P(R_h = 1 | F_t)
```

is estimated.

---

# 41. Competing Outcomes

Continuation and reversal are not necessarily independent.

The research framework must preserve their joint relationship.

It must not independently estimate probabilities that mathematically imply:

```text P(continue) + P(reverse) > 1.
```

where the events are mutually exclusive under the label definition.

---

# 42. Conditional Distribution Registry

Every learned distribution receives:

```text DistributionID
ConditionDefinition
OutcomeDefinition
TrainingCutoff
TrainingDatasetVersion
Estimator
ParameterVersion
CalibrationVersion
```

---

# 43. Historical Distribution Update

At each walk-forward cutoff:

```text NewTrainingData
        ↓
Reconstruct eligible distribution
        ↓
Fit estimator
        ↓
Validate
        ↓
Create new DistributionVersion.
```

The previous distribution remains immutable.

---

# 44. No Online Self-Contamination

Live trade outcomes cannot silently update the model during a trade.

If online updating is later introduced, it must be:

```text explicitly specified
versioned
delayed until label maturity
validated separately.
```

The baseline does not require online learning.

---

# 45. Sample Weighting

Possible weighting schemes include:

```text equal weighting
time-decay weighting
regime weighting
```

but equal weighting is the baseline.

Any alternative must demonstrate out-of-sample benefit.

---

# 46. Time Decay

If time decay is tested:

```text w_i = f(age_i)
```

the decay function becomes a learned/configured parameter.

It cannot be selected by repeatedly inspecting forward performance.

---

# 47. Regime Weighting

Regime weighting is particularly dangerous because it can encode hindsight.

Therefore:

```text regime definitions must be causal
```

and:

```text weighting rules must be predetermined.
```

---

# 48. Distribution Drift

The system must monitor whether:

```text P(Y | C)
```

appears materially different across chronological periods.

Possible tests include:

```text distribution distance
calibration degradation
conditional mean drift
quantile drift.
```

The exact test is not frozen.

---

# 49. Drift Does Not Automatically Mean Refit

Observed drift does not automatically justify:

```text model change.
```

The research system must distinguish:

```text statistical variation
```

from:

```text persistent distributional change.
```

---

# 50. Stability Testing

For each learned quantity:

```text θ
```

evaluate:

```text θ_fold1
θ_fold2
θ_fold3
...
```

The goal is not identical values.

The goal is:

```text economically acceptable stability.
```

---

# 51. Parameter Sensitivity

A parameter is considered fragile if small changes produce large changes in:

```text probability
decision frequency
expected value
drawdown
net performance.
```

Fragile parameters require additional scrutiny.

---

# 52. Multiple-Testing Control

If many statistical formulations are evaluated:

```text every candidate must be recorded. id="6gvv5k"
```

The final result must account for the fact that selection occurred.

Otherwise:

```text best-of-many
```

can masquerade as genuine evidence.

---

# 53. Baseline Comparison

Every statistical model must be compared against simple baselines.

Examples:

```text unconditional probability
time-of-day baseline
direction-only baseline
opening-range-only baseline.
```

A complex conditional model must outperform relevant baselines out-of-sample.

---

# 54. Economic Relevance

Statistical significance alone is insufficient.

The model must produce an economically meaningful improvement after:

```text transaction costs
spread
slippage
execution constraints
risk limits.
```

---

# 55. Probability-to-Economics Boundary

The probability engine produces:

```text P(Direction | F_t)
```

The economic engine independently determines:

```text ExpectedNetValue.
```

The probability engine does not decide whether the trade is profitable.

---

# 56. Calibration-to-Risk Boundary

Calibration cannot directly increase:

```text StrategyRiskBudget.
```

A highly confident prediction does not authorize unlimited exposure.

Probability and risk remain separate layers.

---

# 57. No Probability Chasing

A rising probability does not imply:

```text increase position size.
```

Position sizing is governed by the risk specification.

---

# 58. Statistical Failure State

If the probability model is invalid because of:

```text insufficient sample
calibration failure
distribution instability
data contamination
version mismatch
```

then:

```text ProbabilityState = INVALID.
```

The decision engine follows the no-trade policy.

---

# 59. Statistical Version Lineage

Every probability must be traceable:

```text Probability
    ↓
ModelVersion
    ↓
ParameterVersion
    ↓
DistributionVersion
    ↓
DatasetVersion
    ↓
RawDatasetVersion.
```

This gives full research lineage.

---

# 60. Reproducibility Requirement

Given:

```text DatasetVersion
FeatureVersion
LabelVersion
ModelVersion
ParameterVersion
```

the same probability output must be reproducible.

---

# 61. Statistical Invariants

```text STAT-001 id="x8t6j0"
No estimator may use future information.

STAT-002
Insufficient data cannot produce a normal valid probability.

STAT-003
Probability ∈ [0,1].

STAT-004
Historical distributions are versioned.

STAT-005
Quantiles are estimated only from causally eligible observations.

STAT-006
Calibration parameters are temporally isolated.

STAT-007
Forward data cannot influence the model under evaluation.

STAT-008
Model selection records unsuccessful candidates.

STAT-009
Raw sample count is not treated as independent sample count.

STAT-010
Probability and risk are separate.

STAT-011
Statistical significance does not imply economic significance.

STAT-012
Complexity must earn its existence through out-of-sample evidence.

STAT-013
A failed statistical state produces NO_TRADE rather than fabricated certainty.

STAT-014
Every prediction has complete model/data lineage.
```

---

# 62. What Remains Unfrozen

We have intentionally not selected:

```text conditioning-bin boundaries
minimum sample size
Bayesian α, β
quantile q
calibration method
uncertainty method
weighting scheme
drift thresholds
stability thresholds
exact estimator combinations.
```

These are research parameters.

---

# 63. What Is Now Frozen

The architecture is substantially fixed:

```text empirical estimation is the baseline
conditional distributions are causal
Bayesian smoothing is optional and subordinate
calibration is explicit
uncertainty is explicit
sparse-state handling is explicit
fallback hierarchy is explicit
future information is prohibited
model lineage is mandatory
risk remains separate.
```

---

# 64. Architecture Status

```text Mathematical Specification              COMPLETE
Variable Registry                          COMPLETE
Event Schema                               COMPLETE
State Schema                               COMPLETE
State Transition Specification              COMPLETE
Research Dataset Specification              COMPLETE
Walk-Forward Specification                  COMPLETE
Statistical Estimation Specification       COMPLETE
```

The numerical statistical parameters remain deliberately unfrozen.

---

# 65. Next Artifact

The next artifact should be the:

# CANONICAL ECONOMIC DECISION AND OPTION SELECTION SPECIFICATION

This will connect statistical outputs to actual trade economics.

We will formally specify:

```text probability
→ outcome distribution
→ expected value
→ profit floor
→ execution cost
→ option candidate valuation
→ CE versus PE selection
→ risk-adjusted expectancy
→ minimum economic edge
→ NO_TRADE / BUY_CE / BUY_PE
```

The critical objective is to ensure that a statistically predictive signal does not automatically become a trade unless the **actual option trade remains economically favorable after spread, slippage, decay, liquidity, and risk constraints**.