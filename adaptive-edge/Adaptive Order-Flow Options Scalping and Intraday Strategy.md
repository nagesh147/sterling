# Adaptive Order-Flow Options Scalping and Intraday Strategy
## Master Mathematical Specification — Version 1.0

### 1. System Objective

The system trades liquid Indian index and stock options using high-resolution market data.

The primary objective is not to maximize historical profit.

The objective is:

`maximize probability-adjusted capital growth`

subject to:

`bounded risk`

`positive out-of-sample expectancy`

`realistic execution`

`controlled drawdown`

`statistical robustness`

`no look-ahead bias`

`no future-information contamination`.

The system may produce exactly three entry decisions:

`NO_TRADE`

`BUY_CE`

`BUY_PE`

After entry, the position-management engine may produce:

`HOLD`

`UPDATE_STOP`

`EXIT`.

The system never increases previously accepted risk merely because its prediction becomes more optimistic.

---

# 2. Global Architecture

The complete system is:

`RAW_MARKET_EVENT`

→ `EVENT_VALIDATION`

→ `CANONICAL_EVENT`

→ `MARKET_STATE`

→ `FEATURE_STATE`

→ `PROBABILITY_STATE`

→ `TRADE_CANDIDATE`

→ `TRADE_PLAN`

→ `POSITION_STATE`

→ `EXIT_DECISION`

→ `TRADE_OUTCOME`

→ `LEARNING_UPDATE`

→ `MODEL_VALIDATION`

→ `CHAMPION / CHALLENGER`

→ `LIVE_MODEL`.

The architecture is immutable.

Only statistical estimates and explicitly designated learned parameters may change.

---

# 3. Fundamental Information Rule

At event time `t`:

`Information_t = {E_0, E_1, ..., E_t}`

Every variable used by the trading engine must satisfy:

`Variable_t = f(E_0 ... E_t)`

No variable may depend on:

`E_(t+1), E_(t+2), ...`

Future information may only be used to construct historical labels after the decision point has been recorded.

Therefore:

`Feature_t` uses data through `t`.

`Outcome_t` may use data after `t`.

`Feature_t` must never use `Outcome_t`.

This is the primary anti-look-ahead invariant.

---

# 4. Event Model

Every incoming market event is represented as:

`E_t = {symbol, exchange_timestamp, receive_timestamp, sequence, event_type, payload}`

The event types are conceptually:

`TRADE`

`QUOTE`

`ORDER_BOOK_CHANGE`

`OPTION_CHAIN_UPDATE`

`REFERENCE`

The exact event types depend on the TrueData feed actually delivered to the account.

The raw event must be preserved unchanged.

The canonical representation is separate from the raw representation.

---

# 5. Event Validation

An event is accepted only if its mandatory fields are valid.

For example:

`timestamp != null`

`symbol != null`

`sequence != null`

`LTP > 0`

and, where available:

`Bid > 0`

`Ask > 0`

`Bid <= Ask`

`LTQ >= 0`

`Volume >= 0`

`OI >= 0`.

Invalid events are excluded from trading calculations and recorded as data-quality events.

Duplicate events must not double-count volume, delta, or order-flow information.

Sequence violations are explicitly recorded.

Exchange timestamp and receive timestamp must remain separate.

Network latency is:

`Latency_t = ReceiveTimestamp_t - ExchangeTimestamp_t`

where the timestamps are normalized to a common clock representation.

---

# 6. Instrument State

For every instrument `i`, maintain:

`S_i(t)`

where:

`S_i(t) = F(S_i(t-1), E_i(t))`.

The state contains price, trade, volume, liquidity, volatility, profile, options, temporal and data-quality information.

The state must be updated incrementally.

The system must not require recomputation of the entire historical event stream for every new event.

---

# 7. Price State

Maintain:

`LTP_t`

`Bid_t`

`Ask_t`

`Mid_t`

`Spread_t`

`RelativeSpread_t`

`PriceChange_t`

`Return_t`

`Velocity_t`

`Acceleration_t`.

Definitions:

`Mid_t = (Bid_t + Ask_t) / 2`

`Spread_t = Ask_t - Bid_t`

`RelativeSpread_t = Spread_t / Mid_t`

`PriceChange_t = LTP_t - LTP_(t-1)`

`Return_t = PriceChange_t / LTP_(t-1)`

`Velocity_t = PriceChange_t / Δt`

`Acceleration_t = ΔVelocity_t / Δt`.

Multiple horizons are maintained.

The horizons are measurement scales, not fixed trading rules.

---

# 8. Trade State

Maintain:

`LTQ_t`

`TTQ_t`

`ATP_t`

`OI_t`

and other feed-provided fields.

Incremental volume is:

`ΔVolume_t = TTQ_t - TTQ_(t-1)`.

If:

`ΔVolume_t < 0`

the event is treated as a volume-reset/data-integrity event rather than negative trading volume.

---

# 9. Aggressor State

When the trade can be reliably classified:

If:

`TradePrice >= Ask`

then:

`AggressiveBuyVolume += TradeSize`.

If:

`TradePrice <= Bid`

then:

`AggressiveSellVolume += TradeSize`.

If:

`Bid < TradePrice < Ask`

the aggressor classification is:

`UNKNOWN`

unless an explicitly validated alternative classification method is available.

Unknown volume must not be silently classified as buying or selling.

---

# 10. Delta

For event or interval `t`:

`Delta_t = AggressiveBuyVolume_t - AggressiveSellVolume_t`.

Maintain:

`Delta_1s`

`Delta_5s`

`Delta_15s`

`Delta_1m`

`Delta_5m`

`Delta_session`.

Cumulative delta:

`CumDelta_t = CumDelta_(t-1) + Delta_t`.

Delta velocity:

`DeltaVelocity_t = ΔDelta_t / Δt`.

Delta acceleration:

`DeltaAcceleration_t = ΔDeltaVelocity_t / Δt`.

---

# 11. Liquidity State

Maintain:

`BidQty`

`AskQty`

`Spread`

`RelativeSpread`

`LiquidityImbalance`.

Where:

`LiquidityImbalance = (BidQty - AskQty) / (BidQty + AskQty)`

when:

`BidQty + AskQty > 0`.

Also maintain:

`ΔBidQty`

`ΔAskQty`

`ΔSpread`

`LiquidityChangeRate`.

If true order-level TBT is available, additionally maintain:

`OrdersAdded`

`OrdersCancelled`

`OrdersModified`

`OrdersExecuted`

`LiquidityAdded`

`LiquidityRemoved`

`LiquidityConsumed`

`LiquidityReplenishment`.

These variables must only exist when the feed genuinely supplies sufficient information.

---

# 12. Volume State

Maintain:

`VolumeRate`

`VolumeIntensity`

`TradeFrequency`

`TradeSizeDistribution`.

Volume intensity is normalized against the historical expected volume for the relevant instrument and temporal state.

Conceptually:

`VolumeIntensity_t = CurrentVolumeRate_t / ExpectedVolumeRate(time_of_day, instrument, regime)`.

No universal fixed volume threshold is used.

---

# 13. Volatility State

Maintain volatility at multiple horizons:

`σ_micro`

`σ_scalp`

`σ_intraday`.

Current volatility is normalized against historically relevant observations:

`VolatilityPercentile_t = F_σ(σ_t | historical_information_available_before_t)`.

Volatility regimes are statistical states rather than permanent fixed numerical thresholds.

---

# 14. Volume Profile

For each price level `p`:

`VP_t(p) = Σ TradeVolume at p up to t`.

Derived variables may include:

`POC`

`ValueArea`

`HVN`

`LVN`

`DistanceFromPOC`

`PositionWithinValueArea`.

The profile must be calculated only using information available at the current event.

A complete end-of-day profile cannot be used for an earlier intraday decision.

---

# 15. Market Profile

Market Profile state represents time distribution across price levels.

The system maintains:

`Price × Time`.

The profile is evaluated incrementally.

It provides context such as:

`Acceptance`

`Rejection`

`TimeConcentration`

`PriceMigration`.

These are features, not direct trade commands.

---

# 16. Options State

For each eligible option:

`LTP`

`LTQ`

`Bid`

`Ask`

`BidQty`

`AskQty`

`Volume`

`OI`

`OIChange`

and, where provided:

`IV`

`Delta`

`Gamma`

`Theta`

`Vega`.

The underlying instrument generates the primary directional state.

The option is primarily an execution instrument.

Therefore:

`UnderlyingState → Direction`

and:

`OptionState → InstrumentSelection + ExecutionQuality`.

The option itself must not independently override a strong underlying directional model without validated statistical evidence.

---

# 17. Temporal State

Maintain:

`ExchangeTime`

`TimeSinceOpen`

`TimeUntilClose`

`TimeOfDayState`.

Historical statistics are conditioned on temporal state.

The system therefore recognizes that market behavior at different parts of the trading session can have different distributions.

---

# 18. Feature Vector

Step One produces:

`X_t = {P, D, V, L, σ, VP, MP, O, T, Q}`

where:

`P = Price`

`D = Directional/OrderFlow`

`V = Volume`

`L = Liquidity`

`σ = Volatility`

`VP = VolumeProfile`

`MP = MarketProfile`

`O = Options`

`T = Temporal`

`Q = DataQuality`.

Raw variables and normalized variables are both retained.

---

# 19. Statistical Normalization

For a variable `x_t`, the preferred normalization is its conditional historical distribution.

Conceptually:

`Percentile_t = F(x_t | Context_t, Data<=t)`.

Context may include:

`instrument`

`time_of_day`

`volatility_state`

`expiry_state`

`market_regime`.

No fixed universal threshold such as:

`delta > 1000`

is used unless that threshold survives walk-forward validation and is demonstrably robust.

---

# 20. Probability State

Step Two transforms:

`X_t`

into:

`ProbabilityState_t`.

The probability state contains:

`P_up`

`P_down`

`P_neutral`

`P_regime`

`P_horizon`

`MFE_distribution`

`MAE_distribution`

`ExecutionDistribution`

`Uncertainty`.

---

# 21. Directional Probability

For horizon `h`:

`P_up(h | X_t)`

`P_down(h | X_t)`

`P_neutral(h | X_t)`.

A meaningful movement is defined using volatility-normalized future movement.

For example:

`NormalizedReturn(t,h) = Return(t,h) / σ_t`.

The movement threshold itself is learned and validated.

---

# 22. Statistical Model

The baseline directional model is a regularized statistical model.

The initial candidate is multinomial logistic regression:

`P(Y=k|X) = exp(β_k·X) / Σ_j exp(β_j·X)`.

The optimization objective includes regularization:

`Loss = CrossEntropy + λ||β||²`.

`λ` is learned through walk-forward validation.

No neural network, reinforcement-learning system, LLM or other complex model is required for Version 1.

---

# 23. Empirical Model

For the current state `X_t`, identify historically similar states.

Standardize features:

`Z_i = (X_i - μ_i) / σ_i`.

Similarity:

`d(X_t,X_j) = sqrt(Σ w_i(Z_i,t - Z_i,j)²)`.

Similarity weight:

`w_j = exp(-d_j² / τ)`.

The empirical distribution is constructed from sufficiently similar historical states.

The system must enforce a minimum effective sample size.

Insufficient historical evidence reduces confidence rather than producing artificial certainty.

---

# 24. Bayesian State

Important binary outcomes may be represented by Beta distributions.

For:

`Y ∈ {success,failure}`

maintain:

`Beta(α,β)`.

Posterior:

`Beta(α + successes, β + failures)`.

Adaptive decay:

`α_t = ρ α_(t-1) + Successes_t`

`β_t = ρ β_(t-1) + Failures_t`.

`ρ` is learned and validated.

Bayesian updating cannot use future information unavailable at the update time.

---

# 25. Probability Calibration

Raw probabilities are calibrated against realized frequencies.

Candidate calibration methods include:

`Platt scaling`

or:

`Isotonic regression`.

Calibration must itself be performed walk-forward.

A model that predicts:

`P = 0.80`

should empirically produce approximately eighty-percent occurrence for the corresponding event, within statistical uncertainty.

---

# 26. Combined Probability

The final probability combines:

`P_model`

`P_empirical`

`P_bayesian`.

The combination weights are learned through validation and regularized.

The system must not assume equal weights.

The output includes:

`P_final`

`Confidence`

`SampleSize`

`UncertaintyInterval`.

---

# 27. Regime State

Possible regimes include:

`TREND_UP`

`TREND_DOWN`

`BALANCE`

`BREAKOUT_UP`

`BREAKOUT_DOWN`

`REVERSAL`

`ABSORPTION`

`EXHAUSTION`

`LIQUIDITY_STRESS`

`NOISE`.

The regime model outputs probabilities rather than merely a hard label.

Fast and stable regime estimates are maintained.

`FastRegime`

responds quickly.

`StableRegime`

responds more slowly.

---

# 28. Horizon Distribution

The system does not define scalping through a fixed clock threshold.

Instead it estimates:

`P(T<3m)`

`P(3m≤T<5m)`

`P(5m≤T<15m)`

`P(15m≤T<30m)`

`P(30m≤T<45m)`

`P(T>45m)`.

These are statistical expectations.

A trade can evolve naturally from a short-horizon opportunity into a longer-horizon opportunity without changing its identity.

---

# 29. Future Outcome Distributions

For every historical state:

`X_t`

the future outcomes include:

`Return_h`

`MFE_h`

`MAE_h`

`TimeToMFE`

`TimeToMAE`

`TargetBeforeStop`

`StopBeforeTarget`.

These outcomes are generated only after the original decision point has been frozen.

---

# 30. Trade Candidate

Step Three receives `ProbabilityState_t`.

It constructs candidate instruments:

`CE_candidates`

`PE_candidates`.

For each candidate option `O_i`:

`ExpectedGrossEV_i`

`ExecutionCost_i`

`ExpectedNetEV_i`

`Risk_i`

`Liquidity_i`

`Slippage_i`

`Confidence_i`.

---

# 31. Execution Cost

Total expected execution cost:

`Cost_i = SpreadCost_i + Slippage_i + Brokerage_i + ExchangeCharges_i + Taxes_i + LatencyCost_i`.

All available costs must be represented.

Backtests must never assume execution at LTP merely because LTP is available.

---

# 32. Option Selection

For eligible options:

`O* = argmax ExpectedNetEV_i`

subject to:

`Liquidity_i >= required level`

`ExpectedSlippage_i <= allowable level`

`Risk_i <= risk budget`

`DataQuality >= required level`.

The selected option is the option with the best validated risk-adjusted economic opportunity, not necessarily ATM.

---

# 33. Target/Stop Competition

For candidate stop `s` and favorable excursion `m`:

`P_target_first(s,m | X_t)`

is estimated empirically.

Also:

`P_stop_first(s,m | X_t)`

and:

`P_neither(s,m | X_t,h)`.

Expected value:

`EV(s,m) = P_target × E[Gain] - P_stop × E[Loss] - Costs`.

The optimal candidate is:

`(s*,m*) = argmax ConservativeEV(s,m)`

subject to risk and execution constraints.

---

# 34. Conservative Expected Value

Raw expected value is insufficient.

The system evaluates a conservative estimate:

`EV_conservative = LowerConfidenceBound(EV)`.

If:

`EV_conservative <= 0`

then:

`NO_TRADE`.

This prevents uncertain positive averages from being treated as reliable edge.

---

# 35. Entry Decision

The system may produce:

`BUY_CE`

only if all mandatory gates pass.

Conceptually:

`BUY_CE = DataOK ∧ DirectionalEdgeOK ∧ EV_CE>0 ∧ ConservativeEV_CE>0 ∧ LiquidityOK ∧ SlippageOK ∧ RiskOK`.

Similarly:

`BUY_PE = DataOK ∧ DirectionalEdgeOK ∧ EV_PE>0 ∧ ConservativeEV_PE>0 ∧ LiquidityOK ∧ SlippageOK ∧ RiskOK`.

Otherwise:

`NO_TRADE`.

---

# 36. Initial Risk

For a long option:

`RiskPerUnit = EntryPrice - InitialStop`.

For position quantity `Q`:

`GrossRisk = RiskPerUnit × Q`.

Expected execution effects are incorporated into effective risk.

Position size:

`Q = floor(MaxRisk / EffectiveRiskPerUnit)`.

`MaxRisk` is determined by the risk model and capital state.

The strategy never assumes the entire account should be deployed.

---

# 37. Trade Plan

Every entry produces an immutable initial `TradePlan`.

It contains:

`Instrument`

`Direction`

`ExpectedEntry`

`InitialStop`

`MFE_distribution`

`MAE_distribution`

`ExpectedHorizon`

`ExpectedEV`

`ConservativeEV`

`MaximumRisk`

`PositionSize`

`ExecutionAssumptions`

`ModelVersion`

`ProbabilityStateVersion`.

The original trade thesis is frozen for later audit.

---

# 38. Position State

After entry:

`PositionState_t`

contains:

`EntryPrice`

`CurrentPrice`

`PeakPrice`

`CurrentPnL`

`PeakPnL`

`CurrentMFE`

`CurrentMAE`

`CurrentRegime`

`P_continuation`

`P_reversal`

`ExpectedAdditionalMFE`

`ExpectedAdditionalMAE`

`ExpectedRemainingHorizon`

`CurrentStop`

`ProfitFloor`

`ExecutionState`.

---

# 39. Forward Management

At every event after entry, calculate:

`P_continuation`

`P_reversal`

`ExpectedAdditionalMFE`

`ExpectedAdditionalMAE`

`ContinuationValue`.

Conceptually:

`ContinuationValue_t = ExpectedFutureProfit_t - ExpectedFutureRisk_t - ExpectedFutureCost_t`.

If continuation value remains positive, the trade remains eligible to continue.

---

# 40. Backward Profit Protection

Maintain:

`PeakProfit_t`

`CurrentProfit_t`

`Giveback_t = PeakProfit_t - CurrentProfit_t`.

The system estimates:

`P(Giveback | CurrentState, PeakProfit, MFE)`.

Allowed giveback:

`AllowedGiveback_t = Q_q(Giveback | CurrentState, ProfitState)`.

The quantile `q` is learned through walk-forward validation.

Profit floor:

`ProfitFloor_t = PeakPrice_t - AllowedGiveback_t`.

---

# 41. Stop Invariant

For a long position:

`Stop_(t+1) >= Stop_t`.

Candidate stop:

`CandidateStop_t = max(OriginalRiskBoundary, ProfitFloor_t, DynamicRiskBoundary_t)`.

Actual stop:

`Stop_t = max(Stop_(t-1), CandidateStop_t)`.

Therefore:

`Stop_t` can tighten.

`Stop_t` cannot loosen.

This is an immutable safety invariant.

---

# 42. No Risk Expansion

After entry:

`MaximumAcceptedRisk_(t+1) <= MaximumAcceptedRisk_t`.

A change from scalp-like conditions to intraday-like conditions cannot increase risk.

A model becoming more optimistic cannot reduce already-protected profit.

The adaptive engine may allow more upside participation only by maintaining or tightening protection.

---

# 43. Regime Transition

A trade is not switched between modes using elapsed time.

Instead:

`TradeMode_t = f(ExpectedHorizonDistribution_t, Regime_t, ContinuationValue_t)`.

The descriptive states may be:

`MICRO_SCALP`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

These are management classifications, not independent strategies.

---

# 44. Emergency Reversal

If:

`P_reversal`

increases materially relative to:

`P_continuation`

and the state transition exceeds historically validated transition sensitivity:

`ShockState = TRUE`.

Then:

`AllowedGiveback` is reduced.

The profit floor tightens.

If:

`ContinuationValue <= ExitThreshold`

the position exits.

The exact threshold is learned.

---

# 45. Hard Exit

The position exits immediately when the executable protective condition is breached.

The simulator and live engine must distinguish:

`TheoreticalStop`

`TriggerPrice`

`ExpectedExecutionPrice`

`ActualExecutionPrice`.

No assumption of perfect stop execution is permitted.

---

# 46. Continuation Exit

If:

`ConservativeContinuationValue <= 0`

then:

`EXIT`.

This allows the strategy to exit even when the physical stop has not been reached.

The rationale is that remaining expected opportunity is no longer sufficient to justify remaining exposure.

---

# 47. Position State Machine

The complete state machine is:

`NO_TRADE`

→ `CANDIDATE`

→ `VALIDATED_SIGNAL`

→ `ENTRY_PENDING`

→ `OPEN`

From `OPEN`:

`OPEN → HOLD`

`OPEN → UPDATE_STOP`

`OPEN → EXIT`

After exit:

`EXIT → OUTCOME_RECORDED`

Then:

`OUTCOME_RECORDED → LEARNING_QUEUE`.

The system cannot transition directly from:

`NO_TRADE → OPEN`

without passing the signal and execution gates.

---

# 48. State Transition Rules

`NO_TRADE → CANDIDATE`

when a statistically interesting market state appears.

`CANDIDATE → VALIDATED_SIGNAL`

when directional probability, uncertainty, expected value and data quality satisfy the validated requirements.

`VALIDATED_SIGNAL → ENTRY_PENDING`

when an eligible option and executable price exist.

`ENTRY_PENDING → OPEN`

only after an actual or realistically simulated fill.

`OPEN → UPDATE_STOP`

when the calculated protection improves.

`OPEN → HOLD`

when no management condition requires action.

`OPEN → EXIT`

when hard risk, continuation loss, emergency reversal, session termination or another validated exit condition occurs.

`EXIT → OUTCOME_RECORDED`

after actual/simulated execution is finalized.

`OUTCOME_RECORDED → LEARNING_QUEUE`

only after all future information required to evaluate the trade becomes available.

---

# 49. Session Termination

The strategy must have a validated session boundary.

For the current intended intraday system, no position is permitted to remain unintentionally exposed beyond the defined trading session.

The exact forced-exit time is an explicit configuration parameter and must be validated against the instrument and exchange rules.

---

# 50. Learning Boundary

A trade cannot influence the model that made that same trade.

The sequence is:

`Model_N`

→ `Trade`

→ `Outcome`

→ `LearningDataset`

→ `Model_(N+1)`.

Never:

`Model_N`

→ `Trade`

→ `Outcome`

→ immediately alter the parameters used to evaluate that same trade.

---

# 51. Walk-Forward Learning

Historical time is processed chronologically.

For each evaluation period:

`TRAIN`

→ `FREEZE`

→ `VALIDATE`

→ `TEST`

→ `RECORD`

→ `ADVANCE`.

The test period is unseen during model creation.

After the test period has finished, it may become eligible for future training.

---

# 52. Training Data Boundary

At evaluation time `T`:

`TrainingData <= T_train_end`.

`ValidationData > T_train_end`.

`TestData > ValidationEnd`.

No event from the test period may influence:

`feature normalization`

`model coefficients`

`Bayesian priors`

`calibration`

`parameter selection`

`threshold selection`

before the test is completed.

---

# 53. Parameter Categories

Immutable parameters include:

`System architecture`

`State definitions`

`Data contracts`

`Safety invariants`

`Execution direction`

`No-lookahead rules`

`State-machine structure`.

Learned parameters include:

`Model coefficients`

`Probability calibration`

`Bayesian priors/posteriors`

`MFE/MAE distributions`

`Profit-floor quantiles`

`Continuation thresholds`

`Reversal thresholds`

`Regime-transition sensitivity`

`Execution/slippage distributions`

`Risk allocation parameters`.

---

# 54. Parameter Stability

A parameter is not considered robust merely because one exact value maximizes historical return.

We seek stable regions.

If:

`Parameter ∈ [a,b]`

produces broadly similar out-of-sample performance, that is stronger evidence than a single isolated optimum.

Sharp performance peaks are treated as potential overfitting.

---

# 55. Model Validation

Every candidate model is evaluated using:

`NetReturn`

`ExpectedValue`

`ProfitFactor`

`MaximumDrawdown`

`Sharpe`

`Sortino`

`TailLoss`

`WinRate`

`AverageWin`

`AverageLoss`

`MAE`

`MFE`

`TradeFrequency`

`Slippage`

`Latency`

`CalibrationError`

`ProbabilityOfRuin`

`MilestoneProbability`.

No single metric determines promotion.

---

# 56. Execution Stress Testing

The strategy must be tested under:

`increased latency`

`increased slippage`

`wider spread`

`reduced liquidity`

`delayed fills`

`partial fills`

`adverse execution`.

A strategy that only works with perfect execution is rejected.

---

# 57. Monte Carlo Validation

Historical trade outcomes are resampled to estimate:

`CapitalTrajectoryDistribution`

`MaximumDrawdownDistribution`

`RuinProbability`

`MilestoneProbability`.

The objective is not to prove one historical path.

The objective is to estimate the distribution of plausible paths.

---

# 58. Champion/Challenger Architecture

The currently deployed model is:

`CHAMPION`.

A new candidate is:

`CHALLENGER`.

The challenger must demonstrate robust out-of-sample superiority according to predefined criteria.

A higher historical return alone is insufficient.

The champion remains active until the challenger passes promotion criteria.

---

# 59. Model Drift

Live market distributions are compared against training distributions.

Monitor:

`Delta`

`Volume`

`Spread`

`Liquidity`

`Volatility`

`TradeIntensity`

`ExecutionSlippage`

`PredictionCalibration`.

If the current distribution moves materially outside the validated domain:

`ModelConfidence ↓`.

If drift exceeds the validated safety boundary:

`NO_TRADE`.

The system does not attempt to compensate by blindly increasing aggressiveness.

---

# 60. Data Failure

If:

`FeedDisconnected`

or:

`SequenceIntegrityFailed`

or:

`TimestampIntegrityFailed`

or:

`MarketStateIncomplete`

then:

`NewEntries = DISABLED`.

Existing positions are handled according to their independent protective execution mechanism.

Data uncertainty must never be interpreted as trading opportunity.

---

# 61. Live Learning

Live trading does not continuously mutate the active model after every tick.

The active model is frozen.

New outcomes enter the learning dataset.

At a predefined learning boundary:

`new evidence`

→ `candidate update`

→ `validation`

→ `challenger`

→ `promotion only if validated`.

This prevents unstable feedback loops.

---

# 62. Capital Objective

For capital:

`C_t`

the next milestone is:

`M_t`.

The system tracks:

`CurrentCapital`

`PeakCapital`

`CurrentDrawdown`

`NextMilestone`

`DistanceToMilestone`

`ProbabilityOfMilestone`.

The objective is:

`maximize P(reach required milestone | current state)`

subject to:

`P(ruin) <= allowed level`

and:

`maximum drawdown <= allowed level`.

The exact challenge rules must be encoded before live deployment.

---

# 63. Capital Compounding

Position sizing depends on current capital.

Conceptually:

`RiskBudget_t = f(Capital_t, Drawdown_t, Edge_t, Volatility_t, Liquidity_t)`.

Position size:

`Q_t = floor(RiskBudget_t / EffectiveRiskPerUnit_t)`.

Capital increases do not automatically imply proportionally larger risk if current market conditions do not justify it.

---

# 64. Strategy-Level Invariants

The following can never be violated.

No future information may influence a historical decision.

No invalid market event may silently enter the feature state.

No duplicate event may double-count volume.

No theoretical fill may occur at an unavailable price.

No position may exceed its validated risk budget.

A protective stop may not move backward.

A profitable trade may not deliberately increase previously accepted downside risk.

A model cannot replace the champion solely because of in-sample performance.

A low-confidence prediction cannot be treated as a high-confidence prediction.

Data failure cannot create a trading signal.

The system must always be allowed to produce:

`NO_TRADE`.

---

# 65. Canonical Decision Function

At event `t`:

`Decision_t = D(MarketState_t, ProbabilityState_t, CapitalState_t, ExecutionState_t, PositionState_t)`.

If no position exists:

`Decision_t ∈ {NO_TRADE, BUY_CE, BUY_PE}`.

If a position exists:

`Decision_t ∈ {HOLD, UPDATE_STOP, EXIT}`.

---

# 66. Canonical Trade Objective

For candidate trade `i`:

`NetEV_i = E[Profit_i] - E[Loss_i] - E[ExecutionCost_i]`.

The candidate is economically valid only when:

`LowerConfidenceBound(NetEV_i) > 0`.

Risk-adjusted efficiency:

`EVPerRisk_i = ConservativeEV_i / EffectiveRisk_i`.

The preferred candidate is the eligible option maximizing validated risk-adjusted expected value.

---

# 67. Canonical Learning Objective

The learning engine does not maximize historical profit.

It maximizes robustness of future performance.

Conceptually:

`maximize OutOfSampleRiskAdjustedPerformance`

subject to:

`DrawdownConstraint`

`RuinConstraint`

`ExecutionConstraint`

`CalibrationConstraint`

`DataIntegrityConstraint`.

---

# 68. Canonical System Loop

The complete live loop is:

`EVENT`

→ validate

→ normalize

→ update state

→ calculate features

→ calculate probabilities

→ evaluate opportunity

→ evaluate option

→ evaluate expected value

→ evaluate risk

→ execute or remain flat

→ if position exists, update forward and backward state

→ update protection

→ exit when required

→ record outcome

→ feed outcome into future learning dataset.

The historical loop is identical except that execution is simulated using realistic historical market conditions and learning occurs according to chronological walk-forward boundaries.

---

# 69. What Is Fixed

The following are fixed by architecture:

`Event model`

`Market-state model`

`Feature/state separation`

`Probability-state concept`

`Decision-state machine`

`Risk invariants`

`No-lookahead rule`

`Walk-forward methodology`

`Champion/challenger architecture`

`Execution realism requirement`

`Data-integrity requirements`.

---

# 70. What Is Learned

The following remain empirical:

`Probability coefficients`

`Calibration`

`Similarity weights`

`Bayesian decay`

`MFE/MAE distributions`

`Profit-floor quantile`

`Continuation threshold`

`Reversal threshold`

`Shock sensitivity`

`Risk allocation`

`Execution/slippage distributions`

`Option-selection parameters`

`Time-of-day effects`.

No arbitrary numerical values are declared optimal before historical validation.

---

# 71. Final State Machine

The canonical lifecycle is:

`NO_TRADE`

→ `CANDIDATE`

→ `SIGNAL`

→ `ENTRY_PENDING`

→ `OPEN`

→ `HOLD`

→ `UPDATE_STOP`

→ `REGIME_TRANSITION`

→ `PROFIT_PROTECTION`

→ `CONTINUATION_OR_REVERSAL`

→ `EXIT`

→ `OUTCOME`

→ `LEARNING`

→ `VALIDATION`

→ `CHALLENGER`

→ `CHAMPION`

→ `LIVE`.

The loop then repeats.

---

# 72. Final Strategy Definition

The strategy is therefore not:

"buy when delta is high."

It is:

`Observe the market at event resolution.`

`Construct a causally valid market state.`

`Estimate the probability distribution of future outcomes from statistically comparable historical states.`

`Determine whether a directional opportunity has positive conservative expected value after execution costs.`

`Select the option with the best validated risk-adjusted opportunity.`

`Size the position according to effective risk.`

`Once open, continuously evaluate both future opportunity and accumulated-profit risk.`

`Allow profitable positions to continue when continuation remains economically justified.`

`Tighten protection when reversal probability increases.`

`Never loosen previously accepted risk.`

`Exit when risk, continuation value, execution quality, or session constraints require it.`

`Record the complete outcome.`

`Learn only after the outcome becomes causally available.`

`Validate the updated model on genuinely unseen future data.`

`Promote a new model only when it demonstrates robust out-of-sample superiority.`

That is the canonical strategy.

No neural network.

No reinforcement learning.

No LLM decision-making.

No arbitrary "one ATR" rule.

No arbitrary "ninety percent" rule.

No fixed scalp/intraday timer controlling the trade.

No perfect-fill assumptions.

No look-ahead.

No unlimited parameter optimization.

No requirement to trade.

The system's strongest possible decision remains:

`NO_TRADE`.

And the final governing principle is:

`Predict probabilistically.`
`Risk conservatively.`
`Execute realistically.`
`Learn causally.`
`Validate out-of-sample.`
`Never increase risk because the model is optimistic.`