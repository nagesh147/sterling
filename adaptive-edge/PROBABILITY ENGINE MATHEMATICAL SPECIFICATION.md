# PROBABILITY ENGINE MATHEMATICAL SPECIFICATION

## Canonical Probability Contract — Version 1.0

## 1. Objective

The probability engine transforms the current causal feature state into a probability distribution over future market outcomes.

The fundamental transformation is:

```text
FeatureVector_t
      |
      v
Historical State Matching
      |
      v
Conditional Outcome Distribution
      |
      v
Statistical Estimation
      |
      v
Bayesian Shrinkage
      |
      v
Calibration
      |
      v
Uncertainty
      |
      v
Probability State_t
```

The output is not:

```text
BUY
```

The output is a probabilistic description of what the market is historically likely to do under the current information state.

---

# 2. Probability State

The canonical probability state is:

```text
P_t =
{
    p_up,
    p_down,
    p_neutral,
    uncertainty,
    evidence_strength,
    calibration_state
}
```

subject to:

```text
p_up + p_down + p_neutral = 1
```

within numerical tolerance.

---

# 3. Probability Is Not Prediction

The engine does not say:

```text
"The market will go up."
```

It says:

```text
"Given the information available now,
historically similar states produced these outcomes
with this estimated probability."
```

That distinction is fundamental.

---

# 4. Outcome Definition

The probability engine requires an explicitly versioned outcome variable.

For a chosen horizon `H`:

```text
R_H(t)
=
P_(t+H) / P_t - 1
```

or the appropriate causally defined future return measure.

The exact horizon is part of the label specification.

---

# 5. Three-State Outcome

The simplest directional outcome classification is:

```text
UP
DOWN
NEUTRAL
```

based on a validated outcome classification rule.

We do not permanently define:

```text UP = +X%
DOWN = -X%
```

at architecture level.

Those boundaries are learned/validated from historical distributions.

---

# 6. Why Three States

A binary model forces every small movement into:

`UP`

or:

`DOWN`.

That is inappropriate for our strategy.

A market can have:

```text
directional uncertainty
+
insufficient movement
+
high transaction cost
```

and therefore economically represent:

`NEUTRAL`.

---

# 7. Economic Neutrality

Ultimately, the most useful neutral concept is not merely:

```text
small price movement.
```

It is:

```text
insufficient net opportunity.
```

Therefore the probability engine may eventually support:

```text
directional outcome
```

and:

```text
economic outcome
```

as separate distributions.

---

# 8. Separate Direction From Economics

We therefore distinguish:

```text
DirectionalProbability
```

from:

```text
EconomicReturnDistribution
```

This prevents the mistake:

```text
P(UP) high
    =>
trade profitable
```

which is not necessarily true for options.

---

# 9. Historical State Representation

At time `t`, define:

```text
X_t
```

as the canonical feature vector.

Historical observations are:

```text
(X_i, Y_i)
```

where:

`X_i`

was available at historical time `i`.

`Y_i`

is the subsequently observed outcome.

---

# 10. Causality Requirement

For every historical observation:

```text
X_i
```

must be constructible using only:

```text
Events_<=i
```

while:

```text
Y_i
```

may use:

```text
Events_>i
```

only for label construction.

---

# 11. State Similarity

We need to determine which historical observations are sufficiently comparable to:

```text
X_t.
```

We do not require exact equality.

Exact state matching would become extremely sparse.

---

# 12. Feature Representation

The feature vector is transformed into a validated statistical representation:

```text
Z_t = T(X_t)
```

where `T` may include:

```text
normalization
rank transformation
categorical state encoding
dimension reduction
```

only if independently validated.

---

# 13. Prefer Distributional Features

Where possible, raw values are represented relative to historical context.

For example:

```text
current volatility
```

becomes:

```text
current volatility percentile
```

rather than:

```text
volatility = 0.0042
```

This reduces dependence on absolute scale.

---

# 14. Historical Reference Population

For current state `X_t`, define an eligible historical population:

```text
H_t
=
{i :
i < t
and
i satisfies data-validity rules
and
i satisfies training-window rules}
```

Critically:

```text i < t
```

is mandatory.

---

# 15. No Future Historical Observations

For a historical decision at time `t`:

observations from:

```text
t+1
```

onward cannot contribute to the probability estimate available at `t`.

This remains true even if those observations are within the same calendar day.

---

# 16. Walk-Forward Population

The historical population is not necessarily:

```text all historical data.
```

It is:

```text eligible historical data
available before the model's estimation boundary.
```

The precise walk-forward structure is defined by the validation protocol.

---

# 17. Similarity Function

Define a similarity function:

```text
S(X_t, X_i)
```

which measures how similar historical state `i` is to current state `t`.

---

# 18. Distance

A candidate distance is:

```text
d(X_t, X_i)
```

using normalized feature coordinates.

A simpler first production version should favor interpretable distance structures.

---

# 19. Feature Weighting

Different features may carry different relevance.

Therefore:

```text
d(X_t, X_i)
=
Σ w_j d_j(X_tj, X_ij)
```

where:

`w_j`

are learned/validated weights.

They must not be manually selected because they make the backtest look better.

---

# 20. Feature Weight Constraint

Weights should satisfy an explicit normalization rule, such as:

```text
w_j >= 0
```

and:

```text
Σ w_j = 1
```

if that representation is selected.

---

# 21. Initial Simplicity Rule

Before learning complicated similarity functions:

we first test:

```text
equal weighting
```

against:

```text
validated weighting.
```

If equal weighting performs similarly:

the additional complexity is rejected.

---

# 22. Historical Neighbor Set

The system selects sufficiently similar historical observations:

```text
N_t
```

from:

```text
H_t.
```

The selection method could be:

```text
distance threshold
```

or:

```text
adaptive nearest-neighbor population
```

or:

```text
distributional binning.
```

The final method is empirical.

---

# 23. Why Adaptive Neighborhoods

A fixed number such as:

```text
K = 100
```

is not universally appropriate.

In a dense state region:

100 observations may be highly representative.

In a rare state:

100 observations may be extremely dissimilar.

Therefore neighborhood size should be determined by:

```text
evidence quality
+
state density
+
similarity.
```

---

# 24. Effective Historical Evidence

Define:

```text
N_eff
```

as effective historical evidence.

This need not equal raw sample count.

If observations are highly correlated:

```text
N_raw
```

can substantially overstate independent evidence.

---

# 25. Temporal Dependence

Adjacent market observations are not independent.

Therefore the probability engine must not treat:

```text
10:00:01
10:00:02
10:00:03
```

as three independent pieces of evidence automatically.

---

# 26. Dependence Adjustment

The statistical estimator may use:

```text
effective sample size
```

or another dependence-aware uncertainty estimator.

The exact method is selected during validation.

---

# 27. Outcome Counts

For a historical neighborhood:

```text
n_up
n_down
n_neutral
```

are observed outcome counts.

---

# 28. Empirical Probability

The simplest estimator is:

```text
p_up_emp
=
n_up / N
```

and similarly:

```text
p_down_emp
=
n_down / N

p_neutral_emp
=
n_neutral / N
```

---

# 29. Problem With Raw Empirical Probability

Suppose:

```text
n_up = 9
n_down = 1
n_neutral = 0
```

Then the naive estimate is:

```text
p_up = 0.90
```

But ten observations are nowhere near sufficient to justify:

```text
90% certainty.
```

This is where Bayesian shrinkage enters.

---

# 30. Hierarchical Probability Structure

We use:

```text
Broad Population
      |
      v
Regime Population
      |
      v
Local State Population
      |
      v
Current Probability
```

The local estimate is allowed to move toward broader evidence when local evidence is weak.

---

# 31. Prior Distribution

For three outcomes:

```text
θ = (θ_up, θ_down, θ_neutral)
```

we can use a Dirichlet prior:

```text
θ ~ Dirichlet(α_up, α_down, α_neutral)
```

The prior parameters are themselves estimated only from permissible historical information.

---

# 32. Posterior

Given counts:

```text
n = (n_up, n_down, n_neutral)
```

the posterior becomes:

```text
θ | data
~
Dirichlet(
    α_up + n_up,
    α_down + n_down,
    α_neutral + n_neutral
)
```

---

# 33. Posterior Mean

The posterior mean is:

```text
E[θ_up | data]
=
(α_up + n_up)
/
(α_total + N)
```

and analogously for the other outcomes.

---

# 34. Shrinkage Interpretation

The posterior estimate can be viewed as:

```text
local evidence
+
prior evidence
```

weighted by their respective evidence strengths.

This prevents sparse states from producing extreme probabilities.

---

# 35. Prior Is Not Arbitrary

This is critical.

We cannot say:

```text
α_up = 1
α_down = 1
α_neutral = 1
```

and call the problem solved.

That is merely a mathematical convenience.

The hierarchical prior structure must itself be validated.

---

# 36. Hierarchical Prior

A stronger structure is:

```text
Global Distribution
        |
        v
Regime Distribution
        |
        v
Local Distribution
```

The local prior is informed by the broader population.

---

# 37. Example

Suppose:

```text
Global:
UP    45%
DOWN  35%
NEUTRAL 20%
```

and the current regime historically shows:

```text
UP    60%
DOWN  25%
NEUTRAL 15%
```

A rare local state with only a few observations should shrink toward:

`60/25/15`

rather than toward an arbitrary uniform prior.

---

# 38. Sparse-State Behavior

If:

```text
N_eff -> small
```

then:

```text
posterior
    ->
broader population
```

If:

```text
N_eff -> large
```

then:

```text
posterior
    ->
local empirical evidence
```

This is exactly the behavior we want.

---

# 39. Dense-State Behavior

For abundant and consistent historical evidence:

the local state should dominate the prior.

The model should not remain permanently conservative simply because a prior exists.

---

# 40. Evidence Strength

Canonical:

`evidence_strength`.

This is not probability.

It measures:

```text
How much trustworthy historical information
supports this probability estimate?
```

---

# 41. Evidence Components

Evidence strength may incorporate:

```text
effective sample size
state similarity
temporal independence
data quality
regime consistency
distribution stability
```

---

# 42. Probability Uncertainty

The posterior distribution itself provides uncertainty.

We do not retain only:

```text
p_up = 0.71
```

We retain information about:

```text
uncertainty around 0.71.
```

---

# 43. Credible Interval

For each probability:

```text
p_up
```

we can derive a posterior interval:

```text
[p_low, p_high]
```

The exact interval convention is not frozen.

---

# 44. Decision Probability

The decision layer should not blindly consume:

```text posterior_mean
```

when uncertainty is large.

It may use:

```text conservative_probability
```

derived from the posterior distribution.

---

# 45. Conservative Probability

For an upward trade:

a conservative estimate might use a lower posterior quantile:

```text
p_up_conservative
=
Quantile_q(θ_up | data)
```

The exact `q` remains learned/validated.

---

# 46. Why This Matters

Suppose:

```text
posterior mean = 0.72
```

but uncertainty is enormous.

A conservative probability may be:

```text
0.51
```

which correctly prevents:

`false confidence`.

---

# 47. Probability Calibration

Even a statistically valid estimator can be poorly calibrated.

Therefore:

```text
Raw Probability
      |
      v
Calibration Layer
      |
      v
Calibrated Probability
```

---

# 48. Calibration Objective

If the model predicts:

```text P(UP) ≈ 0.70
```

across many sufficiently comparable cases:

approximately:

```text 70%
```

should actually result in UP outcomes.

---

# 49. Calibration Dataset

Calibration must use data separate from the observations used to fit the raw probability estimator.

Otherwise the model can calibrate itself on its own training errors.

---

# 50. Calibration Method

The first candidates should remain statistically simple:

```text isotonic calibration
```

or:

```text logistic calibration
```

depending on the probability structure and empirical behavior.

No neural calibration model is necessary.

---

# 51. Multiclass Calibration

Because we have:

```text UP
DOWN
NEUTRAL
```

calibration must preserve:

```text p_up + p_down + p_neutral = 1.
```

---

# 52. Calibration Drift

Calibration must be monitored over walk-forward periods.

A model that was:

```text 70% calibrated
```

historically may become:

```text 55%
```

under distribution shift.

---

# 53. Calibration Failure

If calibration deteriorates beyond the validated tolerance:

the probability engine enters:

`DEGRADED`

or:

`UNSUPPORTED`.

The strategy must not pretend the probabilities remain trustworthy.

---

# 54. Regime Conditioning

Probability should be conditioned on relevant regime information.

Conceptually:

```text
P(Y | X)
```

rather than:

```text P(Y)
```

But we must avoid creating excessively sparse combinations.

---

# 55. Hierarchical Regime Backoff

If the complete state is too rare:

```text
Full State
   |
   v
Regime State
   |
   v
Broad State
   |
   v
Global State
```

This is the canonical backoff mechanism.

---

# 56. Backoff Rule

The system chooses the most specific population whose evidence passes the validated support requirements.

If the local population fails:

`back off`.

---

# 57. No Artificial Confidence

The system must never say:

```text "rare state = highly predictive."
```

Rarity is not evidence.

---

# 58. Probability Stability

A probability estimate should not change dramatically because of one weakly informative observation.

The Bayesian posterior naturally moderates this.

But the final implementation must test:

```text sensitivity to one observation
```

explicitly.

---

# 59. Leave-One-Out Sensitivity

For important states:

remove one observation and recompute:

```text Δp_up
Δp_down
Δp_neutral
```

Large instability indicates insufficient evidence.

---

# 60. Temporal Stability

The probability relationship must be tested across:

```text consecutive walk-forward windows.
```

A relationship that exists only in one period is not automatically production-grade.

---

# 61. Probability Drift

Define:

```text probability_drift
=
distance(
    P_current,
    P_reference
)
```

The distance measure is selected during validation.

---

# 62. Probability Drift Is Not Automatically Bad

Markets evolve.

Therefore:

```text drift != failure.
```

The important question is:

```text Does calibration and economic validity remain acceptable?
```

---

# 63. Learning Update

The model can update through the historical learning process:

```text New Matured Outcomes
        |
        v
Training Population
        |
        v
Re-estimation
```

But this is not the same as:

```text runtime self-modification.
```

---

# 64. Runtime Versus Research Learning

Runtime:

```text State_t
-> probability using frozen validated model
```

Research:

```text matured historical data
-> re-estimate model
-> validate
-> freeze new model version
```

This distinction is mandatory.

---

# 65. No Mid-Trade Retraining

A live trade cannot cause the statistical model to retrain itself because:

"the trade is going badly."

The live state can change.

The frozen model cannot arbitrarily mutate.

---

# 66. What Can Change Live

Runtime may update:

```text current probability
current volatility
current liquidity
current mode
current continuation value
current protection boundary
```

because these are state-dependent quantities.

---

# 67. What Cannot Change Arbitrarily Live

Runtime cannot silently change:

```text model coefficients
prior structure
feature definitions
label definitions
calibration mapping
risk parameters
```

unless explicitly designed as a validated online-learning component.

Our initial production system does not include that.

---

# 68. Probability Refresh

The probability can be recalculated whenever the relevant state changes.

For tick-driven operation:

```text Event_t
   |
   v
State_t
   |
   v
Feature_t
   |
   v
Probability_t
```

---

# 69. Event Throttling

Not every raw tick necessarily needs a complete expensive probability calculation.

The architecture may distinguish:

```text state-changing event
```

from:

```text probability-relevant event.
```

This is an implementation optimization, not a mathematical shortcut.

---

# 70. Probability Snapshot

At each decision point:

```text ProbabilitySnapshot_t
```

contains:

```text p_up
p_down
p_neutral
uncertainty
evidence_strength
calibration_state
model_version
```

---

# 71. Probability Snapshot Immutability

Once used for a decision:

the snapshot is immutable.

This makes the decision auditable.

---

# 72. Probability-to-Economic Layer

The probability engine does not determine:

`BUY CE`.

It only supplies probabilistic market information.

The economic engine must determine:

```text Is the probability sufficiently favorable
after option payoff and execution costs?
```

---

# 73. Directional Probability Is Insufficient

For example:

```text p_up = 0.70
```

does not imply:

```text BUY CE.
```

because the option may have:

`poor liquidity`

`large spread`

`high premium`

`rapid theta decay`

or:

`insufficient expected movement`.

---

# 74. Joint Distribution

The stronger object is:

```text OutcomeDistribution_t
```

which can describe:

```text magnitude
direction
duration
adverse excursion
favorable excursion
```

rather than only direction.

---

# 75. Direction + Magnitude

Conceptually:

```text P(R_H <= r | X_t)
```

is more informative than only:

```text P(UP | X_t).
```

This distribution will feed the economic decision layer.

---

# 76. Horizon-Conditional Distribution

Because our strategy dynamically distinguishes:

`micro`

`scalp`

`extended scalp`

`intraday`

the probability engine must support:

```text P(R_H | X_t)
```

across candidate horizons.

---

# 77. Horizon Is a Distribution

We do not select one hard-coded:

```text H = 20 minutes.
```

Instead estimate:

```text P(Horizon | X_t).
```

The economic layer can then evaluate the opportunity over the relevant horizon distribution.

---

# 78. Multi-Horizon Consistency

The model may estimate:

```text P(R_H1)
P(R_H2)
P(R_H3)
...
```

but these cannot be treated as independent observations.

They are nested temporal outcomes.

---

# 79. Avoiding Horizon Contradictions

If:

```text short-horizon probability = UP
```

but:

```text longer-horizon probability = DOWN
```

that is not automatically an error.

It may indicate:

```text initial momentum
followed by reversal.
```

This is exactly the type of structure our dynamic mode architecture is intended to capture.

---

# 80. Probability Surface

Conceptually, the engine produces:

```text
ProbabilitySurface
=
P(Direction, ReturnMagnitude, Horizon | State_t)
```

This is much more powerful than a single scalar prediction.

---

# 81. But We Keep the First Model Simple

We should not immediately estimate a giant multidimensional distribution.

The production baseline should build:

```text direction
+
magnitude
+
horizon
```

incrementally.

Each additional dimension must justify its complexity.

---

# 82. Probability Model Hierarchy

The research architecture is therefore:

```text
LEVEL 0
Unconditional distribution

LEVEL 1
Regime-conditioned distribution

LEVEL 2
Feature-conditioned distribution

LEVEL 3
Local-state distribution

LEVEL 4
Hierarchical/shrunk estimate

LEVEL 5
Calibrated probability
```

The system should use the simplest level that provides robust incremental information.

---

# 83. Model Selection

If:

```text LEVEL 1
```

performs as well as:

```text LEVEL 4
```

we prefer LEVEL 1.

Complexity must earn its existence.

---

# 84. Probability Model Objective

The optimization target is not:

```text maximize training accuracy.
```

It is closer to:

```text maximize calibrated out-of-sample information
while preserving economic usefulness and stability.
```

---

# 85. Proper Scoring

Probability quality should be evaluated with proper scoring rules such as:

```text log loss
Brier score
multiclass Brier score
```

depending on the outcome structure.

---

# 86. Why Accuracy Is Insufficient

A model predicting:

```text UP 51%
```

and:

```text UP 99%
```

may have the same classification accuracy.

But their probability quality is completely different.

We therefore evaluate the probability itself.

---

# 87. Calibration Versus Sharpness

A useful probability model requires both:

```text calibration
```

and:

```text discrimination/sharpness.
```

A model that always predicts:

```text 33/33/34
```

may be calibrated but economically useless.

---

# 88. Probability Value

Therefore:

```text Probability Quality
=
Calibration
+
Discrimination
+
Stability
+
Economic Relevance
```

not merely:

`accuracy`.

---

# 89. Probability Rejection Rule

The probability engine may output:

```text UNSUPPORTED
```

rather than an apparently precise probability.

This is essential when:

`evidence is insufficient`.

---

# 90. No-Trade Through Uncertainty

If:

```text evidence_strength
```

is too weak,

the downstream decision engine receives:

```text probability_state = INSUFFICIENT_EVIDENCE
```

and can select:

`NO_TRADE`.

The exact support threshold is empirical.

---

# 91. Probability Monotonicity Test

Synthetic verification should confirm:

if the generator increases true directional edge:

```text estimated probability
```

should generally move in the corresponding direction.

It need not move monotonically on every finite sample, but systematic inversion indicates a problem.

---

# 92. Null Calibration Test

In a true null market:

```text p_up
```

must converge toward the unconditional base rate rather than systematically becoming extreme.

---

# 93. Known-Edge Test

When synthetic data injects:

```text true P(UP) = 0.70
```

the estimated probability should converge toward:

```text 0.70
```

as evidence increases.

---

# 94. Sparse-State Test

With only a few observations:

the estimate must remain close to the broader population.

It must not jump to:

```text 0%
```

or:

```text 100%
```

because of a tiny sample.

---

# 95. Regime-Switch Test

When the synthetic generator changes:

```text regime A -> regime B
```

the probability estimate should eventually adapt through the validated historical learning process.

But it should not instantly "know" the regime has changed unless the current causal features contain information identifying that transition.

---

# 96. Lookahead Test

The probability engine must produce identical results whether or not future labels are stored in the same database, provided the decision-time information set is unchanged.

If the output changes:

`FAIL`.

---

# 97. Probability Determinism

Given:

```text FeatureSnapshot_t
ModelVersion
HistoricalDatasetVersion
```

the probability output must be reproducible.

---

# 98. Probability Lineage

Every probability snapshot must be traceable to:

```text id="w8iz5f"
feature_version
model_version
training_dataset
calibration_version
probability_method
timestamp
```

---

# 99. Probability Registry

The canonical probability registry therefore contains:

```text id="pqz55b"
p_up
p_down
p_neutral
probability_uncertainty
evidence_strength
calibrated_p_up
calibrated_p_down
calibrated_p_neutral
probability_state
model_version
calibration_version
```

---

# 100. Probability State Machine

Conceptually:

```text
INSUFFICIENT_EVIDENCE
        |
        v
SUPPORTED
        |
        v
CALIBRATED
        |
        v
DECISION_ELIGIBLE
```

A model may also transition:

```text
CALIBRATED
    |
    v
DEGRADED
    |
    v
UNSUPPORTED
```

when monitoring detects failure.

---

# 101. Probability Does Not Control Risk

This is another hard boundary.

Higher:

```text p_up
```

does not automatically mean:

`larger position`.

Position sizing is separately constrained by:

`risk capacity`

and:

`candidate downside`.

---

# 102. Probability Does Not Control Protection

Likewise:

```text p_up increases
```

cannot automatically loosen a previously established protective stop.

Probability informs continuation value.

Protection remains governed by risk invariants.

---

# 103. Probability Does Not Define Mode

Probability alone does not decide:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

Mode depends on:

`opportunity persistence`

and:

`state evolution`.

---

# 104. Complete Probability Architecture

```text
                    FeatureVector_t
                          |
                          v
                  Historical Population
                          |
                          v
                    State Matching
                          |
                          v
                  Local Outcome Counts
                          |
                          v
                Hierarchical Prior/Backoff
                          |
                          v
                  Posterior Distribution
                          |
                +---------+---------+
                |                   |
                v                   v
          Probability          Uncertainty
                |                   |
                +---------+---------+
                          |
                          v
                     Calibration
                          |
                          v
                  Probability State
                          |
              +-----------+-----------+
              |           |           |
              v           v           v
            UP          DOWN       NEUTRAL
```

---

# 105. Fundamental Mathematical Contract

At decision time `t`:

```text
ProbabilityState_t
=
Calibrate(
    Posterior(
        OutcomeLabels
        |
        HistoricalStates
        similar_to
        FeatureState_t
    )
)
```

subject to:

```text
HistoricalStateTime < t
```

and:

```text
OutcomeLabel
```

being used only for historical estimation, never as a decision-time feature.

---

# 106. What Remains Unfrozen

We intentionally have not fixed:

```text
exact similarity metric
exact feature weights
exact neighborhood definition
exact minimum evidence
exact prior strength
exact hierarchical structure
exact calibration method
exact calibration interval
exact conservative probability quantile
exact horizon set
exact outcome boundaries
```

These are empirical quantities.

---

# 107. What Is Now Frozen

The architecture itself is frozen:

```text
Empirical evidence
        +
Hierarchical Bayesian shrinkage
        +
Uncertainty
        +
Calibration
        +
Walk-forward validation
        +
Economic separation
```

No opaque AI model is required.

---

# 108. Most Important Design Decision

The probability engine is explicitly allowed to say:

```text
"I don't know."
```

That means:

```text INSUFFICIENT_EVIDENCE
```

and ultimately:

```text NO_TRADE
```

This is preferable to manufacturing a precise probability from insufficient historical evidence.

---

# 109. Next Artifact

The next artifact should now be:

# ECONOMIC DECISION ENGINE MATHEMATICAL SPECIFICATION

That is where probability finally becomes an economically testable trade.

We will mathematically connect:

```text
P(direction)
+
return distribution
+
horizon distribution
+
option payoff
+
option price
+
spread
+
slippage
+
fees
+
theta
+
risk
+
position sizing
```

and produce exactly one of:

```text
NO_TRADE
BUY_CE
BUY_PE
```

with the precise mathematical reason for rejection or acceptance.

That layer is where we finally answer the question:

```text
"Even if our prediction is right,
does this particular option trade actually make money?"
```