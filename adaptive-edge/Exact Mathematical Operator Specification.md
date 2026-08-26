# Exact Mathematical Operator Specification
## Canonical Mathematical Layer — Version 1.0

### 1. Mathematical Convention

At event time `t`, every quantity is explicitly indexed by time.

The fundamental rule is:

`X_t = f(E_0, E_1, ..., E_t)`

A future-dependent quantity is written separately:

`Y_(t,h) = g(E_t, E_(t+1), ..., E_(t+h))`

`Y_(t,h)` may be used for historical labeling, but never for the decision at `t`.

All learned parameters are represented by:

`θ`

and are estimated only through the walk-forward learning process.

---

# 2. Primitive Market Operators

Let:

`P_t = LTP`

`B_t = Bid`

`A_t = Ask`

`Q^B_t = Bid Quantity`

`Q^A_t = Ask Quantity`

`V_t = cumulative volume`

`OI_t = open interest`.

The midpoint is:

`M_t = (B_t + A_t) / 2`

when both quotes are valid.

Spread:

`S_t = A_t - B_t`

Relative spread:

`RS_t = S_t / M_t`

when:

`M_t > 0`.

Price change:

`ΔP_t = P_t - P_(t-1)`.

Log return:

`r_t = ln(P_t / P_(t-1))`.

Log returns are preferred for statistical modeling because they are additive across consecutive periods.

---

# 3. Event-Time Velocity

For irregularly spaced events:

`Δτ_t = τ_t - τ_(t-1)`.

Price velocity:

`v_t = ΔP_t / Δτ_t`.

This is used only when:

`Δτ_t > 0`.

If timestamps are duplicated or invalid:

`v_t = undefined`.

The system must not manufacture a velocity from invalid timestamps.

---

# 4. Price Acceleration

Velocity change:

`Δv_t = v_t - v_(t-1)`.

Acceleration:

`a_t = Δv_t / Δτ_t`.

Acceleration is particularly sensitive to timestamp noise, so its statistical usefulness must be validated rather than assumed.

---

# 5. Liquidity Imbalance

Define:

`LQ_t = Q^B_t + Q^A_t`.

If:

`LQ_t > 0`

then:

`LI_t = (Q^B_t - Q^A_t) / LQ_t`.

Therefore:

`-1 <= LI_t <= 1`.

A value near:

`+1`

means displayed bid liquidity dominates.

A value near:

`-1`

means displayed ask liquidity dominates.

This is a state variable, not a directional trading rule.

---

# 6. Quote Dynamics

Bid change:

`ΔB_t = B_t - B_(t-1)`.

Ask change:

`ΔA_t = A_t - A_(t-1)`.

Bid-quantity change:

`ΔQ^B_t = Q^B_t - Q^B_(t-1)`.

Ask-quantity change:

`ΔQ^A_t = Q^A_t - Q^A_(t-1)`.

Spread change:

`ΔS_t = S_t - S_(t-1)`.

These feed the liquidity-dynamics model.

---

# 7. Trade Classification

For a trade price `T_t` and valid quote:

If:

`T_t >= A_t`

then:

`BuyClass_t = 1`.

If:

`T_t <= B_t`

then:

`SellClass_t = 1`.

Otherwise:

`UnknownClass_t = 1`.

For trade quantity `q_t`:

`ABV_t = q_t × BuyClass_t`

`ASV_t = q_t × SellClass_t`.

Unknown volume:

`UV_t = q_t × UnknownClass_t`.

The system must not force unknown trades into buy or sell classifications.

---

# 8. Delta

Event delta:

`δ_t = ABV_t - ASV_t`.

For interval `W`:

`Δ_W(t) = Σ δ_j`

for all events:

`τ_j ∈ (t-W,t]`.

Cumulative session delta:

`CD_t = Σ_(j=session start)^t δ_j`.

The system therefore maintains both:

`rolling delta`

and:

`session cumulative delta`.

They are distinct variables.

---

# 9. Delta Velocity

For a selected interval:

`δv_t = (Δ_W(t) - Δ_W(t-ΔW)) / ΔW`.

Delta acceleration:

`δa_t = (δv_t - δv_(t-1)) / ΔW`.

These are descriptive features.

No threshold is assigned here.

---

# 10. Volume Rate

For window `W`:

`VR_W(t) = Volume(t-W,t) / W`.

Trade frequency:

`TF_W(t) = NumberOfTrades(t-W,t) / W`.

Average trade size:

`ATS_W(t) = Volume(t-W,t) / NumberOfTrades(t-W,t)`.

If trade count is zero:

`ATS_W = undefined`.

---

# 11. Volume Intensity

Let:

`μ_V(c,t)`

be the historical expected volume rate for context `c`.

Let:

`σ_V(c,t)`

be its historical dispersion.

Then:

`Z_V(t) = (VR_t - μ_V(c,t)) / σ_V(c,t)`.

And the percentile representation:

`F_V(t) = P(VR <= VR_t | c, history <= t)`.

The percentile is preferred for cross-regime comparability.

---

# 12. Realized Volatility

For return observations:

`r_1, r_2, ..., r_n`

within window `W`:

`RV_W = sqrt(Σ r_i²)`.

Alternative estimators may be evaluated later, but exactly one canonical volatility estimator must be selected for each model version.

We do not mix incompatible volatility definitions inside one probability model without explicitly specifying the transformation.

---

# 13. Volatility Context

For current volatility `σ_t`:

`VolPercentile_t = F_σ(σ_t | Context_t, History<=t)`.

The context may include:

`instrument`

`time_of_day`

`expiry_state`

`market_regime`.

This converts raw volatility into a conditional statistical position.

---

# 14. Volume Profile

For price bucket `p`:

`VP_t(p) = Σ q_j`

where:

`price_j ∈ p`

and:

`τ_j <= τ_t`.

The profile is therefore causal.

POC:

`POC_t = argmax_p VP_t(p)`.

The exact price-bucketing resolution becomes a learned/validated implementation parameter.

---

# 15. Distance From POC

For current price:

`DPOC_t = P_t - POC_t`.

Normalized distance:

`NDPOC_t = DPOC_t / σ_price,t`.

This makes the quantity comparable across volatility regimes.

---

# 16. Profile Acceptance

Define price occupancy around a region `R`:

`Occupancy(R,t) = TimeSpentInside(R) / ObservationTime`.

Acceptance becomes a normalized statistical quantity rather than a binary visual judgment.

The exact region construction must be defined by the profile algorithm.

---

# 17. Order-Flow Efficiency

One important derived variable is:

`FlowEfficiency_t`.

Define:

`FE_t = |ΔP_t| / (|Δ_t| + ε)`.

where:

`ε > 0`

prevents division by zero.

Interpretation:

High directional flow producing little price movement can indicate absorption.

Large price movement relative to flow can indicate efficient directional movement.

The usefulness and exact transformation of this variable must be validated.

---

# 18. Absorption Score

Absorption is not:

`Delta > threshold`.

Instead we construct:

`AbsorptionEvidence_t`

from:

`AggressiveFlow`

`PriceResponse`

`Liquidity`

`Volume`.

A generic form is:

`A_t = f(FlowIntensity_t, PriceResponse_t, LiquidityResponse_t)`.

The exact statistical transformation belongs to the learned feature model.

The architectural invariant is:

`AbsorptionScore` must not be manually assigned from a single indicator.

---

# 19. Directional Efficiency

Define:

`DE_W(t) = |P_t - P_(t-W)| / Σ|ΔP_i|`.

Therefore:

`0 <= DE <= 1`.

Near:

`1`

means movement was relatively directional.

Near:

`0`

means movement was dominated by back-and-forth price movement.

This becomes a regime feature.

---

# 20. Feature Vector

The canonical feature vector is:

`X_t = [X_price, X_flow, X_volume, X_liquidity, X_volatility, X_profile, X_options, X_time]`.

Each component must be normalized where appropriate.

We do not allow raw variables with wildly different scales to enter a regularized model without preprocessing.

---

# 21. Robust Normalization

For feature `x_i`:

`z_i = (x_i - μ_i) / σ_i`.

Where distributions are strongly non-Gaussian, the system may use:

`robust_z_i = (x_i - median_i) / MAD_i`.

The choice is model-version specific and must be validated.

---

# 22. Directional Model

For three outcomes:

`Y ∈ {UP, DOWN, NEUTRAL}`

the baseline model is:

`P(Y=k|X) = exp(β_k^T X) / Σ_j exp(β_j^T X)`.

With reference class:

`β_NEUTRAL = 0`.

Regularized objective:

`L(β) = -Σ log P(Y_i|X_i) + λΣ||β_k||²`.

`λ` is learned.

---

# 23. Directional Edge

Let:

`P1 = max(P_UP,P_DOWN)`

and:

`P2 = min(P_UP,P_DOWN)`.

Then:

`DirectionalEdge = P1 - P2`.

But this alone is insufficient.

We also require:

`P_neutral`

to be sufficiently low relative to the candidate direction.

Therefore the actual decision uses the complete probability vector rather than edge alone.

---

# 24. Empirical Conditional Distribution

For a target quantity `Y`, historical observations similar to `X_t` are selected.

Distance:

`d_j = sqrt(Σ_i w_i(z_i,t-z_i,j)²)`.

Weight:

`ω_j = exp(-d_j² / τ)`.

Effective sample size:

`N_eff = (Σω_j)² / Σω_j²`.

If:

`N_eff`

is insufficient, the empirical estimate is marked:

`LOW_EVIDENCE`.

It cannot be treated as a high-confidence probability.

---

# 25. Bayesian Binary Probability

For event:

`Y ∈ {0,1}`

prior:

`Beta(α_0,β_0)`.

Observed successes:

`s`.

Failures:

`f`.

Posterior:

`Beta(α_0+s,β_0+f)`.

Posterior mean:

`p = (α_0+s)/(α_0+β_0+s+f)`.

The prior and update-decay parameters are learned through walk-forward validation.

---

# 26. Probability Fusion

Let:

`P_param`

be the parametric model.

`P_emp`

be the empirical model.

`P_bayes`

be the Bayesian estimate.

The combined estimate is:

`P_raw = w1P_param + w2P_emp + w3P_bayes`

subject to:

`w1+w2+w3=1`

and:

`w_i >= 0`.

The weights:

`w1,w2,w3`

are learned.

If an evidence source is unavailable or statistically unreliable, its weight may approach zero.

---

# 27. Probability Calibration

Raw probability:

`P_raw`.

Calibration transformation:

`P_cal = C(P_raw)`.

The calibration function `C` is learned only from historical validation data.

The calibration dataset must be strictly later than the dataset used to fit the raw model.

---

# 28. Probability Uncertainty

For a predicted probability:

`P`.

We maintain an uncertainty estimate:

`U(P)`.

It may incorporate:

`sample size`

`model disagreement`

`posterior variance`

`calibration error`.

The system should distinguish:

`P = 0.75, high evidence`

from:

`P = 0.75, weak evidence`.

The numerical probability alone is not enough.

---

# 29. Horizon Distribution

Define horizon categories:

`H1 = <=3m`

`H2 = >3m to <=5m`

`H3 = >5m to <=15m`

`H4 = >15m to <=30m`

`H5 = >30m to <=45m`

`H6 = >45m`.

The model outputs:

`P(H_k | X_t)`.

The categories are classification buckets, not mandatory exit times.

---

# 30. Expected Horizon

The scalar expectation is:

`E[T|X_t] = Σ P(H_k|X_t) × E[T|H_k,X_t]`.

The internal conditional duration estimates are learned.

Therefore:

`ExpectedHorizon`

is not hard-coded.

---

# 31. Future MFE

For a long position:

`MFE_h(t) = max(P_(t:t+h)) - P_t`.

For a short position:

`MFE_h(t) = P_t - min(P_(t:t+h))`.

The system stores the empirical conditional distribution:

`F_MFE(m | X_t)`.

---

# 32. Future MAE

For a long position:

`MAE_h(t) = P_t - min(P_(t:t+h))`.

For a short position:

`MAE_h(t) = max(P_(t:t+h)) - P_t`.

The distribution is:

`F_MAE(a | X_t)`.

These are labels during training.

During live operation, their conditional distributions are predictions.

---

# 33. Target Probability

For target distance `g` and adverse boundary `s`:

`P_target_first(g,s | X_t)`.

This is estimated from historical trajectories.

Similarly:

`P_stop_first(g,s | X_t)`.

And:

`P_neither(g,s | X_t)`.

These probabilities should approximately satisfy:

`P_target + P_stop + P_neither = 1`

within numerical estimation error.

---

# 34. Expected Trade Value

For candidate target `g` and stop `s`:

`EV = P_target × G - P_stop × L - Cost`

where:

`G = expected net gain conditional on target-first`

`L = expected net loss conditional on stop-first`.

More accurately:

`EV = E[NetPnL | X_t,g,s]`.

The simplified equation is only an interpretable decomposition.

The actual implementation should use the conditional outcome distribution.

---

# 35. Conservative Expected Value

Let:

`EV_distribution`

be the uncertainty distribution of expected value.

Then:

`ConservativeEV = Q_q(EV_distribution)`.

Where:

`q < 0.5`

and `q` is learned.

This converts:

"expected value is positive"

into:

"expected value remains positive under conservative uncertainty."

---

# 36. Execution Cost

For an option:

`Cost = SpreadCost + Slippage + Fees + Taxes + LatencyCost`.

Spread cost for a marketable buy is related to:

`Ask - Mid`.

For an executable sell:

`Mid - Bid`.

The exact execution model must use the actual order type.

---

# 37. Option Candidate Score

For candidate option `i`:

`OptionScore_i = ConservativeEV_i / EffectiveRisk_i`.

Subject to:

`Liquidity_i >= minimum validated liquidity`

`Spread_i <= maximum validated spread`

`Slippage_i <= validated limit`.

The selected option:

`i* = argmax(OptionScore_i)`.

If no candidate passes:

`NO_TRADE`.

---

# 38. Risk Budget

Define:

`C_t = current account equity`.

`D_t = current drawdown`.

`E_t = validated edge`.

`V_t = current volatility`.

`L_t = liquidity state`.

Then:

`RiskBudget_t = R(C_t,D_t,E_t,V_t,L_t;θ_R)`.

The functional form is learned and validated.

But:

`RiskBudget_t <= MaximumAllowedRisk(C_t)`.

The system cannot exceed the global risk constraint.

---

# 39. Position Size

Effective risk per contract:

`R_contract = ExpectedLossPerContract + ExecutionRisk`.

Then:

`Q = floor(RiskBudget / R_contract)`.

If:

`Q < 1`

then:

`NO_TRADE`.

This prevents fractional or economically meaningless positions.

---

# 40. Continuation Probability

For an open position:

`P_cont_t = P(FutureNetPnL > ExitAlternative | CurrentState_t)`.

This is more useful than merely asking:

`P(price goes up)`.

The relevant question is whether remaining exposure has positive economic value.

---

# 41. Continuation Value

Define:

`CV_t = E[FutureNetPnL | CurrentState_t] - OpportunityCost_t`.

A more complete representation:

`CV_t = E[FutureGain] - E[FutureLoss] - E[FutureCost]`.

The position remains eligible only while:

`ConservativeCV_t > 0`.

The exact conservative operator is learned.

---

# 42. Profit Giveback

For a long option:

`PeakNetPnL_t = max(PeakNetPnL_(t-1), CurrentNetPnL_t)`.

Then:

`Giveback_t = PeakNetPnL_t - CurrentNetPnL_t`.

For a new peak:

`Giveback_t = 0`.

---

# 43. Giveback Distribution

Historical observations produce:

`G = PeakNetPnL - CurrentNetPnL`

conditioned on:

`State`

`PeakProfit`

`MFE`

`Horizon`

`Volatility`

`Regime`.

Therefore:

`F_G(g | X_t, ProfitState_t)`.

---

# 44. Allowed Giveback

The permitted giveback is:

`G*_t = Q_q(F_G | X_t, ProfitState_t)`.

`q` is learned.

This is not a fixed percentage of profit.

It is a conditional statistical quantity.

---

# 45. Profit Floor

For a long option:

`ProfitFloorPrice_t = PeakPrice_t - G*_t`.

For an option, because P&L and underlying price are not linearly identical, the preferred production implementation is actually:

`ProfitFloorPnL_t = PeakNetPnL_t - G*_t`.

Then this P&L boundary is converted to an executable option-price boundary using the current position quantity and execution model.

This avoids incorrectly assuming:

`OptionPriceMovement = UnderlyingPriceMovement`.

That distinction is important.

---

# 46. Candidate Stop

The candidate stop is:

`S_candidate = max(S_initial_boundary, S_profit_boundary, S_dynamic_boundary)`.

Then:

`S_current,t = max(S_current,t-1, S_candidate)`.

The stop therefore has monotonic favorable movement.

---

# 47. Reversal Score

Reversal evidence is not a single indicator.

Define:

`RScore_t = f(P_reversal, FlowReversal, LiquidityReversal, PriceFailure, RegimeTransition)`.

The model estimates:

`P(Reversal | X_t)`.

The score is therefore a representation of probability, not an arbitrary point system.

---

# 48. Regime Transition Score

Let current regime distribution be:

`R_t`.

Previous regime distribution:

`R_(t-1)`.

A distributional change can be measured using divergence:

`D_KL(R_t || R_(t-1))`.

Because KL divergence can become unstable when probabilities approach zero, a symmetric alternative such as Jensen-Shannon divergence may be used:

`JS(R_t,R_(t-1))`.

The transition model therefore evaluates both:

`Magnitude of change`

and:

`Statistical confidence of change`.

A large change caused by noisy low-confidence probabilities should not automatically trigger a regime transition.

---

# 49. Shock Score

Define:

`ShockScore_t`

from unusually large simultaneous changes in:

`Price`

`Delta`

`Volume`

`Liquidity`

`Volatility`.

Conceptually:

`ShockScore = MahalanobisDistance(X_t - X_(t-1))`.

A covariance matrix:

`Σ`

normalizes correlated feature movement:

`D² = ΔX^T Σ^(-1) ΔX`.

The shock threshold is learned.

---

# 50. Management Severity

Rather than using binary:

`normal / emergency`

we define:

`ManagementSeverity ∈ [0,1]`.

It is derived from:

`P_reversal`

`ShockScore`

`ProfitGiveback`

`ContinuationValue`

`ExecutionRisk`.

Higher severity means:

`tighter protection`.

This gives us continuous adaptation rather than arbitrary mode switching.

---

# 51. Exit Score

The exit engine evaluates:

`ExitPressure`.

Conceptually:

`ExitPressure = f(NegativeContinuationValue, ReversalProbability, GivebackRisk, ExecutionRisk, SessionConstraint)`.

The system exits when the validated decision boundary is crossed.

This is preferable to a fixed percentage stop/target rule.

---

# 52. Hard Exit Override

Regardless of model output:

If:

`ExecutablePrice <= ProtectiveBoundary`

for a long position:

`EXIT`.

This is a deterministic risk override.

No probability model may veto it.

---

# 53. Session Exit

At the validated session termination condition:

`SessionExit = TRUE`.

Then:

`EXIT`.

The model cannot decide to remain overnight if the strategy is explicitly intraday-only.

---

# 54. Data Safety Operator

Define:

`DataQualityScore ∈ [0,1]`.

It incorporates:

`FeedCompleteness`

`TimestampIntegrity`

`SequenceIntegrity`

`QuoteFreshness`

`Latency`.

If:

`DataQualityScore < θ_data`

then:

`NewEntry = FALSE`.

The threshold is validated.

---

# 55. Model Validity Operator

Define:

`ModelValidityScore`.

Inputs:

`FeatureDrift`

`PredictionDrift`

`CalibrationDrift`

`ExecutionDrift`.

If model validity falls below its validated safety boundary:

`NewEntry = FALSE`.

This does not necessarily force an existing position to close immediately.

The risk engine handles existing exposure separately.

---

# 56. Entry Operator

The final entry function is:

`EntryDecision_t = D(P_t, EV_t, Risk_t, Execution_t, DataQuality_t, ModelValidity_t)`.

The output is exactly:

`NO_TRADE`

`BUY_CE`

`BUY_PE`.

There is no fourth state.

---

# 57. Position Management Operator

For an open position:

`ManagementDecision_t = M(CV_t, Giveback_t, Stop_t, Reversal_t, Execution_t, Session_t)`.

Output:

`HOLD`

`UPDATE_STOP`

`EXIT`.

---

# 58. Stop Update Operator

`StopUpdate_t = max(CurrentStop_(t-1), CandidateStop_t)`.

If:

`StopUpdate_t > CurrentStop_(t-1)`

then:

`UPDATE_STOP`.

Otherwise:

`NO_STOP_CHANGE`.

A stop update does not itself imply an exit.

---

# 59. Complete Mathematical Decision Chain

The complete causal calculation is:

`E_t`

→ `State_t`

→ `Feature_t`

→ `Probability_t`

→ `Candidate_t`

→ `OptionEV_t`

→ `Risk_t`

→ `EntryDecision_t`.

After entry:

`E_t`

→ `UpdatedState_t`

→ `UpdatedProbability_t`

→ `ContinuationValue_t`

→ `GivebackDistribution_t`

→ `ProfitFloor_t`

→ `Stop_t`

→ `ManagementDecision_t`.

After exit:

`Trade_t`

→ `FuturePath`

→ `Outcome_t`

→ `LearningDataset`.

---

# 60. Dimensional Consistency Rules

Every mathematical operator must preserve units.

For example:

`Price / Time = velocity`.

`Velocity / Time = acceleration`.

`Price / Price = dimensionless`.

`Volume / Time = volume rate`.

`PnL / Risk = dimensionless`.

Therefore:

`EVPerRisk`

is dimensionless.

We must not add quantities with incompatible dimensions.

For example:

`Price + Volume`

is mathematically invalid.

Any feature-combination model must normalize heterogeneous variables first.

---

# 61. Probability Constraints

For every probability distribution:

`0 <= P <= 1`.

For mutually exclusive directional states:

`P_up + P_down + P_neutral = 1`.

For regime states:

`Σ P_regime = 1`.

For horizon states:

`Σ P_horizon = 1`.

If numerical estimation produces:

`ΣP != 1`

the vector must be normalized before downstream use.

---

# 62. Distribution Validity

Every predicted distribution must satisfy:

`CDF(x) ∈ [0,1]`.

`CDF(x)` must be monotonically non-decreasing.

And:

`lim x→-∞ CDF(x) = 0`

`lim x→+∞ CDF(x) = 1`.

Invalid distributions are rejected.

---

# 63. Learned Parameter Separation

The specification now distinguishes:

### Structural constants

These define mathematics.

Examples:

`log-return definition`

`probability normalization`

`state-machine transitions`

`stop monotonicity`.

These are fixed.

### Learned parameters

These determine numerical behavior.

Examples:

`β`

`λ`

`w_i`

`q`

`τ`

`risk coefficients`

`transition thresholds`.

These are learned.

### Source parameters

These depend on TrueData.

Examples:

`field names`

`timestamp precision`

`depth levels`

`historical retention`.

These remain `TBD`.

---

# 64. What We Have Deliberately Not Defined Numerically

We have not invented:

`Probability threshold`

`EV threshold`

`Profit-floor quantile`

`Reversal threshold`

`Shock threshold`

`Data-quality threshold`

`Model-drift threshold`

`Risk percentage`

`Similarity radius`

`Bayesian decay`

`Calibration window`

`Minimum effective sample size`.

Those are empirical parameters.

They belong to the parameter-learning specification.

---

# 65. Mathematical Integrity Audit

The operator specification has been checked for the major classes of error.

### Look-ahead

Prevented by explicit temporal indexing.

### Circular probability/decision dependency

Prevented by making probability upstream of decision.

### Risk/probability circularity

Prevented by making risk consume probability rather than influence it.

### Stop recursion

Resolved using:

`Stop_t = max(Stop_(t-1), CandidateStop_t)`.

### Profit/price ambiguity

Resolved by using P&L-space profit protection before translating to executable option price.

### Holding-time ambiguity

Resolved by:

`HorizonDistribution`

plus:

`ExpectedHorizon`.

### Model/learning contamination

Resolved by separate trading and learning machines.

### Dimensional inconsistency

Controlled through explicit units and normalization.

---

# 66. Canonical Mathematical Layer

The system now has four formal layers:

`Layer 1 — Architecture`

What components exist.

`Layer 2 — Variables`

What quantities exist.

`Layer 3 — Dependencies`

What depends on what.

`Layer 4 — Operators`

How each quantity is mathematically transformed.

The next layer is therefore not another conceptual layer.

It is:

`Parameterization + Historical Label Specification`.

That is where we define exactly what the system is trying to learn from historical data and how every learned parameter gets estimated without look-ahead.