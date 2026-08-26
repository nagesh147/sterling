# Statistical Identifiability and Evidence Specification
## Canonical Evidence Layer — Version 1.0

### 1. Purpose

This specification determines whether a calculated statistical quantity is sufficiently supported by historical evidence to influence a trading decision.

The central distinction is:

`EstimatedQuantity != ReliableQuantity`.

For every model output:

`Prediction = {Value, Evidence, Uncertainty, DomainStatus}`.

A prediction without sufficient evidence cannot be treated as a normal prediction.

---

# 2. Evidence State

Every statistical output receives one of four evidence states:

`E0 = INSUFFICIENT`

`E1 = WEAK`

`E2 = VALID`

`E3 = STRONG`.

These are evidence classifications, not trading signals.

The mapping from statistical diagnostics to these states is learned and validated.

---

# 3. Evidence Vector

For a prediction `Y_t`, define:

`Evidence_t = {N_eff, Uncertainty, Calibration, Stability, DomainDistance}`.

Where:

`N_eff = effective sample size`

`Uncertainty = statistical uncertainty`

`Calibration = historical probability calibration`

`Stability = temporal/regime stability`

`DomainDistance = distance from validated historical states`.

No single metric determines evidence quality.

---

# 4. Effective Sample Size

For weighted historical observations:

`N_eff = (Σw_i)^2 / Σw_i²`.

This is more appropriate than simply counting observations because highly similar observations may receive large weights.

Example:

`N = 10,000`

does not necessarily mean:

`N_eff = 10,000`.

If most weight is concentrated in a few observations:

`N_eff << N`.

---

# 5. Minimum Evidence

For every learned quantity:

`N_eff >= N_min`

is required before treating the estimate as statistically usable.

But:

`N_min`

must not be a universal number.

The required evidence depends on:

`Model variance`

`Tail probability`

`Decision sensitivity`

`Cost of error`.

Therefore each model component has its own evidence requirement.

---

# 6. Rare Event Rule

Suppose:

`P(reversal)`

is estimated from only a small number of historical reversals.

The system must not produce:

`P(reversal) = 0`

merely because no reversal occurred in the sample.

Likewise it must not produce:

`P(reversal) = 1`

because every observation reversed.

Probability estimates require smoothing.

---

# 7. Bayesian Smoothing

For binary event probability:

`Y ∈ {0,1}`

use:

`Beta(α,β)`.

Posterior:

`Beta(α+s, β+f)`.

Posterior mean:

`p = (α+s)/(α+β+s+f)`.

The prior prevents extreme probabilities caused by sparse observations.

The prior itself is validated using walk-forward data.

---

# 8. Probability Interval

A point estimate is insufficient.

For:

`P = 0.72`

we also require an uncertainty interval:

`[P_low, P_high]`.

The interval must reflect:

`sample size`

`model uncertainty`

`parameter uncertainty`

where applicable.

Therefore the system may encounter:

`P = 0.72`

with:

`wide interval`.

That prediction is weak.

---

# 9. Conservative Probability

For decision-making, the system may use a conservative bound:

`P_conservative = Q_q(P_distribution)`.

Where:

`q`

is a learned lower-tail quantile for favorable events.

For adverse events:

the corresponding conservative upper bound may be used.

This prevents optimistic point estimates from dominating risk decisions.

---

# 10. Probability Reliability

A directional probability becomes decision-eligible only if:

`EvidenceState >= VALID`

and:

`CalibrationStatus = VALID`

and:

`DomainStatus = IN_DOMAIN`.

Otherwise:

`DecisionProbability = downgraded`.

The exact downgrade function is learned.

---

# 11. Evidence Score

A continuous evidence score may be defined as:

`ES_t = f(N_eff, Uncertainty, Calibration, Stability, DomainDistance)`.

Normalize:

`0 <= ES_t <= 1`.

This allows gradual degradation rather than abrupt binary rejection.

But the production system still has hard boundaries:

`ES < θ_min → insufficient`.

---

# 12. Evidence-Adjusted Probability

Suppose:

`P_raw`

is the model probability.

Define:

`P_adjusted = h(P_raw, ES)`.

The adjustment must move uncertain predictions toward the neutral/base-rate distribution.

It must not arbitrarily move them toward:

`0.5`.

The correct reference is the relevant historical prior:

`P_base`.

Conceptually:

`P_adjusted = P_base + ES × (P_raw - P_base)`.

Thus:

if:

`ES = 1`

then:

`P_adjusted = P_raw`.

If:

`ES = 0`

then:

`P_adjusted = P_base`.

This is a useful canonical shrinkage mechanism.

---

# 13. Why Shrink Toward the Base Rate?

Suppose:

`P_raw = 0.90`.

But evidence is weak.

We should not blindly accept:

`90%`.

The system should instead move the estimate toward:

`P_base`.

This is mathematically preferable to inventing artificial certainty.

---

# 14. Base Rate

The base rate must be conditional where appropriate.

For example:

`P(UP | NIFTY, time_of_day, volatility_regime)`.

Not merely:

`P(UP | all historical data)`.

The base-rate hierarchy can therefore be:

`Instrument`

→ `SessionContext`

→ `VolatilityContext`

→ `MarketRegime`.

The hierarchy is used only where sample size supports the additional conditioning.

---

# 15. Hierarchical Fallback

Suppose the most specific state has insufficient evidence:

`NIFTY + 10:17 + extreme volatility + near-expiry`

has too few historical observations.

The system should back off:

`Specific State`

→ `Broader Volatility State`

→ `Instrument State`

→ `Market-Class State`

→ `Global Prior`.

This is hierarchical evidence fallback.

---

# 16. Fallback Rule

Let:

`E_specific < E_min`.

Then:

`Use broader distribution`.

Continue backing off until:

`Evidence >= E_min`

or:

`Global prior reached`.

If even the global prior is insufficient:

`NO_TRADE`.

The system never invents a probability.

---

# 17. Example

Suppose:

`SpecificState`

has:

`N_eff = 14`.

Insufficient.

Broader state:

`N_eff = 220`.

Valid.

The model uses:

`BroaderStateDistribution`.

It does not pretend the specific state has a reliable probability.

---

# 18. Evidence Is Not Direction

A strong evidence score does not mean:

`BUY`.

It means:

"The model's estimate is statistically well-supported."

Therefore:

`Evidence`

and:

`ExpectedValue`

remain separate quantities.

---

# 19. Evidence and Expected Value

Suppose:

`RawEV = +₹500`.

But:

`Evidence = weak`.

Then:

`ConservativeEV`

may become:

`<= 0`.

The system rejects the trade.

This prevents sparse historical patterns from becoming trades simply because their point estimate is attractive.

---

# 20. Evidence and Risk

Risk sizing should also respond to evidence.

Conceptually:

`RiskCapacity = BaseRisk × RiskConfidenceMultiplier`.

Where:

`0 <= RiskConfidenceMultiplier <= 1`.

Low evidence:

`RiskMultiplier ↓`.

Insufficient evidence:

`RiskMultiplier = 0`.

Therefore:

`NO_TRADE`.

---

# 21. Evidence Must Never Increase Risk

An evidence mechanism may reduce uncertainty.

It must never independently increase risk beyond the portfolio's hard limits.

Formally:

`RiskAllowed <= HardRiskLimit`.

Always.

---

# 22. Feature Identifiability

A feature must demonstrate incremental information.

For candidate feature `X_j`:

compare:

`Model_without_Xj`

against:

`Model_with_Xj`.

The feature is useful only if its incremental out-of-sample contribution is sufficiently stable.

A feature that merely duplicates another feature should not receive independent importance simply because it correlates with the target.

---

# 23. Multicollinearity

Suppose we include:

`PriceVelocity`

`Momentum`

`Return`

`DeltaVelocity`.

These may be highly correlated.

A model may appear to have four independent signals when it effectively has one.

Therefore feature dependence must be measured.

Possible diagnostics:

`Correlation`

`Rank correlation`

`Variance Inflation Factor`

`Mutual Information`.

The exact diagnostic depends on model structure.

---

# 24. Redundant Feature Rule

If two features provide effectively identical information:

`X1 ≈ X2`

the system should not interpret:

`X1 + X2`

as independent confirmation.

This directly addresses our earlier desire for multiple confirmation layers.

**Multiple measurements of the same phenomenon are not independent confirmation.**

---

# 25. Evidence Independence

The strongest confirmation comes from partially independent information domains.

For example:

`Price response`

`Executed volume`

`Liquidity`

`Volatility`

`Option economics`.

These are preferable to:

`RSI`

`MACD`

`Momentum`

all confirming the same price movement.

The evidence layer therefore tracks feature-domain dependence.

---

# 26. Conditional Independence

We must not assume independence unless validated.

For example:

`Delta`

and:

`AggressiveVolume`

are likely correlated.

Therefore:

`P(A and B) = P(A) × P(B)`

must never be assumed without evidence.

---

# 27. Joint Evidence

If several features are correlated, their combined information must be estimated jointly.

This is another reason the model should consume:

`FeatureVector`

rather than manually adding confirmation points.

---

# 28. Parameter Identifiability

A parameter is identifiable if materially different parameter values produce distinguishable model behavior based on available data.

Suppose:

`θ = 0.4`

and:

`θ = 0.41`

produce almost identical outputs.

Then the exact value:

`0.4`

is not economically meaningful.

The model should not claim false numerical precision.

---

# 29. Parameter Stability

For each parameter:

`θ`

calculate its walk-forward estimates:

`θ_1, θ_2, ..., θ_n`.

Evaluate:

`Mean(θ)`

`Variance(θ)`

`Range(θ)`

`Sensitivity`.

A robust parameter should occupy a reasonably stable region.

---

# 30. Parameter Surface

Instead of asking:

"What is the optimal parameter?"

we ask:

"Is there a stable region where the model performs acceptably?"

For example:

```text
Performance
   ^
   |       ______
   |      /      \
   |_____/        \____
   |
   +--------------------> Parameter
```

A broad performance plateau is preferable to a narrow optimum.

---

# 31. Overfitting Signature

A parameter is suspicious when:

`Tiny parameter change`

causes:

`Huge performance change`.

This suggests the model may be fitting noise.

---

# 32. Regime-Specific Evidence

A model may be valid globally but invalid in a particular regime.

Therefore evidence is evaluated conditionally:

`Evidence(Model | Regime)`.

Example:

`Trend regime → strong evidence`

`Mean-reverting regime → weak evidence`.

The system should then reduce confidence in the second regime.

---

# 33. Time Stability

Evidence must also survive time.

A feature that worked:

`2019–2020`

but failed:

`2024–2026`

may represent historical structure rather than persistent edge.

Therefore:

`TemporalStability`

is a required evidence dimension.

---

# 34. Regime Stability

Similarly:

`RegimeStability`.

A feature that works only in one volatility regime cannot be treated as universally valid.

---

# 35. Tail Events

Rare events are especially dangerous.

Suppose a strategy has:

`99.5%`

of outcomes within normal conditions.

The remaining:

`0.5%`

may contain catastrophic losses.

Therefore the evidence layer must explicitly evaluate:

`TailLoss`

`ExtremeMAE`

`ExecutionShock`.

Average performance is insufficient.

---

# 36. Tail Sample Problem

Rare events have few observations.

Therefore the system must avoid pretending that a tiny sample accurately estimates the extreme tail.

Where evidence is insufficient:

`TailRisk = UNKNOWN`.

Unknown tail risk is not interpreted as:

`low tail risk`.

It causes risk reduction.

---

# 37. Unknown Is Not Safe

This is a critical invariant:

`UNKNOWN != SAFE`.

If the system cannot estimate:

`ExecutionRisk`

or:

`MAE`

or:

`ReversalRisk`

with adequate evidence:

it must not assume the missing risk is small.

---

# 38. Missing Data

If a required feature is missing:

`FeatureStatus = MISSING`.

The system may use a validated fallback only if that fallback has been explicitly tested.

Otherwise:

`NO_TRADE`.

Missing information must never be silently replaced by:

`0`.

---

# 39. Stale Data

A feature may technically exist but be stale.

Therefore:

`FeatureFreshness`

is distinct from:

`FeatureAvailability`.

A stale value is not equivalent to a current value.

---

# 40. Out-of-Domain State

Define:

`D_t = distance(CurrentFeatureState, ValidatedTrainingDomain)`.

If:

`D_t > θ_domain`

then:

`OUT_OF_DOMAIN`.

The system reduces confidence or rejects the trade.

The exact threshold is validated.

---

# 41. Multivariate Domain Detection

Domain detection must consider the joint state.

A market may have individually normal values:

`Volume = normal`

`Volatility = normal`

`Spread = normal`

but an unusual combination:

`Volume + Spread + Delta + Volatility`.

Therefore:

`DomainDistance`

should be evaluated in multivariate feature space.

---

# 42. Covariance-Aware Distance

A candidate formulation is:

`D² = (X_t - μ)^T Σ^(-1)(X_t - μ)`.

This is the Mahalanobis distance.

It accounts for feature covariance.

The covariance estimate itself must be causal and learned.

---

# 43. Evidence Degradation

Evidence should degrade when:

`DomainDistance ↑`

`CalibrationError ↑`

`Drift ↑`

`SampleSupport ↓`.

Conceptually:

`Evidence_t = h(N_eff, uncertainty, calibration, stability, domain)`.

The function is learned.

---

# 44. Evidence Recovery

Evidence can recover when new historical observations accumulate.

But live observations cannot instantly create validated evidence.

The system needs:

`MaturedHistoricalOutcomes`.

Therefore:

`Evidence_t`

does not automatically increase simply because today's market generated many ticks.

Ticks are observations.

Outcomes are evidence for predictive relationships.

---

# 45. Important Distinction: Observation Density

One million ticks does not mean one million independent samples.

If:

`1,000,000 ticks`

represent one continuous market episode, their effective statistical information may be much lower.

Therefore:

`TickCount != SampleSize`.

---

# 46. Effective Independent Sample

For temporal data, autocorrelation reduces effective sample size.

Therefore evidence calculations must account for temporal dependence.

A sequence:

`tick_1, tick_2, ..., tick_1000`

cannot automatically be treated as:

`1000 independent observations`.

---

# 47. Episode-Based Validation

Where appropriate, outcomes should be grouped into independent market episodes.

Examples:

`Trade opportunity`

`Market regime`

`Breakout episode`

`Reversal episode`.

This reduces false confidence caused by clustered observations.

---

# 48. Cluster Leakage

If multiple observations belong to the same market episode, splitting them between training and test can make performance appear stronger than it really is.

Therefore related observations must remain in the appropriate temporal/episode partition.

---

# 49. Evidence for Micro-Scalping

Micro-scalping has the most demanding evidence requirements because:

`ExpectedEdge`

may be small.

Therefore:

`ExecutionCost`

`Latency`

`Spread`

`FillProbability`

must be estimated with particularly high confidence.

If:

`ExpectedEdge <= uncertainty + executionCost`

then:

`NO_TRADE`.

---

# 50. Evidence for Longer Intraday Trades

Longer trades may tolerate larger execution costs relative to expected movement.

But they introduce:

`Longer exposure`

`More regime transitions`

`Greater path uncertainty`.

Therefore evidence shifts from:

`microstructure precision`

toward:

`trajectory distribution`.

The same mathematical framework can support both horizons.

---

# 51. Evidence-Adjusted EV

The final economic quantity is:

`EV_conservative = Q_q(EV | Evidence, State)`.

A trade is eligible only when:

`EV_conservative > 0`.

This is the principal economic gate.

---

# 52. Evidence-Adjusted Reversal

For reversal probability:

`P_rev_raw`.

We calculate:

`P_rev_adjusted`.

If evidence is weak:

`P_rev_adjusted → P_rev_base`.

Therefore the system does not suddenly exit because of a weakly supported reversal pattern.

---

# 53. Evidence-Adjusted Giveback

Likewise:

`GivebackDistribution`

must have adequate evidence.

If the system has insufficient examples of similar profitable states:

the profit floor should become more conservative rather than inventing a precise giveback estimate.

---

# 54. Evidence-Adjusted Position Size

Position size becomes:

`Q = floor(RiskBudget × ConfidenceFactor / RiskPerContract)`.

Where:

`ConfidenceFactor`

is bounded:

`0 <= ConfidenceFactor <= 1`.

If evidence is insufficient:

`ConfidenceFactor = 0`.

Therefore:

`Q = 0`.

---

# 55. Evidence Hierarchy

The final decision hierarchy becomes:

`Hard Safety`

→ `Data Validity`

→ `Model Domain`

→ `Statistical Evidence`

→ `Economic Value`

→ `Portfolio Risk`

→ `Execution`

→ `Trade Decision`.

No statistically attractive trade can bypass inadequate evidence.

---

# 56. What Evidence Cannot Do

Evidence cannot:

`Create an edge`

`Override hard risk`

`Override bad execution`

`Override data corruption`

`Predict the future with certainty`.

It only determines how much trust the system is permitted to place in an estimate.

---

# 57. Evidence State Machine

The evidence layer itself can be represented as:

```text
                  insufficient
                 +-------------+
                 |             v
          +------+------+
          | INSUFFICIENT|
          +------+------+
                 |
                 | evidence accumulates
                 v
             +-------+
             | WEAK  |
             +---+---+
                 |
                 | validated
                 v
             +-------+
             | VALID |
             +---+---+
                 |
                 | strong support
                 v
             +--------+
             | STRONG |
             +--------+
```

Evidence can also move backward:

`STRONG → VALID → WEAK → INSUFFICIENT`

when:

`Drift ↑`

or:

`Calibration ↓`

or:

`DomainDistance ↑`.

---

# 58. Evidence Is Time-Dependent

Therefore:

`Evidence_t != Evidence_(t+1)`.

A model can become less reliable without its coefficients changing.

This is important.

Model parameters and model evidence are different state variables.

---

# 59. Model Confidence Versus Market Confidence

We explicitly separate:

`ModelConfidence`

from:

`MarketDirectionConfidence`.

For example:

`P_up = 0.80`

but:

`ModelConfidence = low`.

The system should not treat this as an 80% high-quality opportunity.

---

# 60. Final Trade Eligibility

The canonical trade eligibility function becomes:

`TradeEligible =`

`DataValid`

AND

`ModelInDomain`

AND

`EvidenceValid`

AND

`ConservativeEV > 0`

AND

`PortfolioRiskValid`

AND

`ExecutionValid`

AND

`RiskCapacity > 0`.

If any mandatory condition is false:

`NO_TRADE`.

---

# 61. Statistical Evidence Invariants

The following are now permanent invariants:

`I1: Unknown evidence is never treated as positive evidence.`

`I2: Tick count is not equivalent to independent sample count.`

`I3: Sparse states cannot produce unrestricted confidence.`

`I4: Extreme probabilities require sufficient evidence.`

`I5: Future outcomes cannot increase current evidence.`

`I6: Evidence cannot override hard risk.`

`I7: Evidence cannot compensate for negative net EV.`

`I8: Correlated features cannot be counted as independent confirmation.`

`I9: Parameter precision cannot exceed statistical identifiability.`

`I10: Out-of-domain predictions are degraded or rejected.`

---

# 62. Verification Tests Added

The synthetic test suite must now include:

`Sparse-state attack`

`Rare-event attack`

`Overconfident probability attack`

`Correlated-feature attack`

`Out-of-domain attack`

`Distribution-drift attack`

`Low-effective-sample attack`

`Tail-risk uncertainty attack`

`Missing-feature attack`

`Stale-feature attack`.

A strategy that passes these tests is considerably more defensible statistically.

---

# 63. Current Architecture

We now have:

`Market Events`

→ `Data Integrity`

→ `Market State`

→ `Feature State`

→ `Probability State`

→ `Evidence State`

→ `Economic Value`

→ `Portfolio Risk`

→ `Execution`

→ `Decision`

→ `Position Management`

→ `Outcome`

→ `Learning`.

The evidence layer sits between prediction and economic action.

That is intentional.

---

# 64. What This Prevents

This architecture prevents the system from saying:

"Pattern detected, therefore trade."

Instead it must establish:

"Pattern detected."

then:

"Prediction estimated."

then:

"Prediction sufficiently supported."

then:

"Expected economic value remains positive after costs."

then:

"Portfolio can accept the risk."

then:

"Execution is feasible."

Only then:

`TRADE`.

---

# 65. Remaining Pre-Implementation Gap

We have now specified:

`What to calculate`

`How to label`

`How to learn`

`How to validate`

`How to determine evidence`

`How to reject insufficient evidence`.

The next remaining mathematical problem is **model calibration and statistical decision theory**.

Specifically, we need to define how the probability distributions become economically optimal decisions when:

`probability is uncertain`

`payoff is asymmetric`

`execution costs vary`

`risk is constrained`

`multiple opportunities compete for capital`.

This is where we formally derive:

`Bayes decision rule`

`utility function`

`risk-adjusted EV`

`opportunity cost`

`trade ranking`

`capital allocation`

and:

`NO_TRADE`.

That is the next layer before we can meaningfully bind the specification to actual TrueData fields.