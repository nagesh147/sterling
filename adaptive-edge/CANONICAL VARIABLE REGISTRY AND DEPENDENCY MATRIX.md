# CANONICAL VARIABLE REGISTRY AND DEPENDENCY MATRIX
## Strategy Specification — Version 1.0

## 1. Registry Rule

Every mathematical quantity in the system receives exactly one canonical identity.

The fundamental rule is:

`ONE CONCEPT = ONE CANONICAL VARIABLE`

A variable may have many consumers, but only one owner and one mathematical definition.

No downstream component is allowed to independently redefine it.

The dependency structure is temporal:

`Event_t -> State_t -> Features_t -> Prediction_t -> Evidence_t -> Economics_t -> Decision_t -> Position_t`

Future information can enter only after its corresponding historical outcome has matured and the walk-forward learning boundary permits it.

---

# 2. Variable Classes

Every variable belongs to exactly one primary class:

`OBSERVED`

Directly obtained from the market/data source.

`DERIVED`

Deterministically calculated from observed information.

`PREDICTIVE`

Estimated from historical statistical relationships.

`EVIDENCE`

Measures reliability of predictive estimates.

`ECONOMIC`

Describes expected monetary outcomes.

`RISK`

Describes capital and downside constraints.

`EXECUTION`

Describes actual or expected execution.

`POSITION`

Describes the currently held trade.

`PORTFOLIO`

Describes aggregate exposure.

`LEARNING`

Describes historical model estimation and validation.

---

# 3. Global Temporal Rule

For every variable `X_t` used in a trading decision:

`X_t = f(E_<=t, S_<=t, M_<=t)`

where `M_<=t` represents only model information legally available at time `t`.

No variable used at `t` may depend on:

`E_(>t)`

or:

`Outcome_(>t)`

or:

`FutureModelVersion`.

This is the master anti-lookahead invariant.

---

# 4. Event Registry

`EVT-001 EVENT_ID`

Type: OBSERVED.

Definition:

Unique identifier of an incoming market event.

Source:

`TrueData TBD`.

Used by:

Data integrity, replay, audit.

It must be immutable.

---

`EVT-002 EXCHANGE_TIMESTAMP`

Type: OBSERVED.

Definition:

Timestamp assigned by the market/data source to the event.

Unit:

Time.

Used by:

Chronology, state reconstruction, latency analysis.

---

`EVT-003 RECEIVE_TIMESTAMP`

Type: OBSERVED.

Definition:

Timestamp at which the system receives the event.

Used by:

Latency and execution analysis.

It must not redefine historical market chronology.

---

`EVT-004 INSTRUMENT_ID`

Type: OBSERVED.

Definition:

Canonical instrument identifier.

Used by:

All instrument-specific state.

---

`EVT-005 EVENT_TYPE`

Type: OBSERVED.

Examples include:

trade, quote, depth, option update.

Exact values:

`TBD from TrueData`.

---

# 5. Price-State Registry

`PRC-001 BEST_BID`

Type: OBSERVED.

Definition:

Current best executable bid.

Unit:

INR.

Owner:

PriceState.

---

`PRC-002 BEST_ASK`

Type: OBSERVED.

Definition:

Current best executable ask.

Unit:

INR.

---

`PRC-003 LTP`

Type: OBSERVED.

Definition:

Latest traded price.

Important:

`LTP != necessarily executable entry price`.

---

`PRC-004 MID_PRICE`

Type: DERIVED.

Formula:

`MID = (BEST_BID + BEST_ASK) / 2`

Valid only when both bid and ask are valid.

---

`PRC-005 SPREAD`

Type: DERIVED.

Formula:

`SPREAD = BEST_ASK - BEST_BID`

---

`PRC-006 RELATIVE_SPREAD`

Type: DERIVED.

Formula:

`REL_SPREAD = SPREAD / MID_PRICE`

when:

`MID_PRICE > 0`.

---

`PRC-007 LOG_RETURN`

Type: DERIVED.

Formula:

`r_t = ln(P_t / P_(t-1))`.

Reference price must be explicitly defined for each use.

---

`PRC-008 PRICE_VELOCITY`

Type: DERIVED.

Formula:

`V_t = ΔP / Δt`.

---

`PRC-009 PRICE_ACCELERATION`

Type: DERIVED.

Formula:

`A_t = ΔV / Δt`.

---

# 6. Volume and Trade-Flow Registry

`FLW-001 TRADE_QUANTITY`

Type: OBSERVED.

Definition:

Quantity associated with an executed trade event.

---

`FLW-002 BUY_AGGRESSOR_VOLUME`

Type: DERIVED.

Definition:

Quantity classified as aggressive buying.

---

`FLW-003 SELL_AGGRESSOR_VOLUME`

Type: DERIVED.

Definition:

Quantity classified as aggressive selling.

---

`FLW-004 CUMULATIVE_DELTA`

Type: DERIVED.

Formula:

`DELTA = BUY_VOLUME - SELL_VOLUME`.

---

`FLW-005 INCREMENTAL_DELTA`

Type: DERIVED.

Formula:

`ΔDELTA = ΔBUY_VOLUME - ΔSELL_VOLUME`.

---

`FLW-006 FLOW_IMBALANCE`

Type: DERIVED.

Formula:

`FI = (BUY_VOLUME - SELL_VOLUME) / (BUY_VOLUME + SELL_VOLUME)`.

Range:

`[-1, +1]`.

Undefined when denominator equals zero.

---

`FLW-007 FLOW_RATE`

Type: DERIVED.

Definition:

Directional flow per defined temporal interval.

The interval must explicitly specify whether it is:

`clock-time`

or:

`event-time`.

---

`FLW-008 FLOW_ACCELERATION`

Type: DERIVED.

Definition:

Change in flow rate over time.

---

`FLW-009 FLOW_PERSISTENCE`

Type: DERIVED.

Definition:

Persistence of directional flow over a causal rolling window.

---

`FLW-010 PRICE_FLOW_RESPONSE`

Type: DERIVED.

Conceptual formula:

`ΔPRICE / ΔAGGRESSIVE_VOLUME`.

Used to distinguish:

high flow/high response

from:

high flow/low response.

---

`FLW-011 PRICE_FLOW_DIVERGENCE`

Type: DERIVED.

Definition:

State where directional flow and price movement disagree.

Examples:

`BUY_FLOW ↑ + PRICE ↓`

or:

`SELL_FLOW ↑ + PRICE ↑`.

It is a feature, not a trading decision.

---

# 7. Order-Book Registry

`OBK-001 BID_DEPTH[k]`

Type: OBSERVED.

Definition:

Displayed bid quantity at depth level `k`.

---

`OBK-002 ASK_DEPTH[k]`

Type: OBSERVED.

Definition:

Displayed ask quantity at depth level `k`.

---

`OBK-003 TOTAL_BID_DEPTH`

Type: DERIVED.

`Σ BID_DEPTH[k]`.

---

`OBK-004 TOTAL_ASK_DEPTH`

Type: DERIVED.

`Σ ASK_DEPTH[k]`.

---

`OBK-005 ORDER_BOOK_IMBALANCE`

Type: DERIVED.

Formula:

`OBI = (BID_DEPTH - ASK_DEPTH) / (BID_DEPTH + ASK_DEPTH)`.

---

`OBK-006 WEIGHTED_ORDER_BOOK_IMBALANCE`

Type: DERIVED.

Formula:

`WOBI = weighted_bid_depth - weighted_ask_depth`

divided by:

`weighted_bid_depth + weighted_ask_depth`.

The weighting function remains learned/configurable.

---

`OBK-007 DEPTH_SHOCK`

Type: DERIVED.

Definition:

Current displayed liquidity relative to its validated historical distribution.

---

# 8. Liquidity Registry

`LIQ-001 SPREAD_STATE`

Derived from:

`PRC-005`.

---

`LIQ-002 DEPTH_STATE`

Derived from:

`OBK-003`, `OBK-004`.

---

`LIQ-003 LIQUIDITY_STATE`

Type: DERIVED.

Composite description of current liquidity conditions.

It must not duplicate individual raw liquidity variables.

---

`LIQ-004 SPREAD_SHOCK`

Type: DERIVED.

Current spread relative to historical spread distribution.

---

`LIQ-005 FILL_PROBABILITY`

Type: PREDICTIVE.

Probability that a submitted order receives the required execution.

It is not observed directly unless actual execution occurs.

---

# 9. Volatility Registry

`VOL-001 REALIZED_VOLATILITY_MICRO`

Type: DERIVED.

Computed from causal short-horizon returns.

---

`VOL-002 REALIZED_VOLATILITY_SHORT`

Type: DERIVED.

---

`VOL-003 REALIZED_VOLATILITY_MEDIUM`

Type: DERIVED.

---

`VOL-004 REALIZED_VOLATILITY_SESSION`

Type: DERIVED.

---

`VOL-005 VOLATILITY_RATIO`

Type: DERIVED.

Conceptually:

`SHORT_VOL / MEDIUM_VOL`.

---

`VOL-006 VOLATILITY_STATE`

Type: DERIVED.

Represents the current location within the validated volatility distribution.

---

`VOL-007 VOLATILITY_SHOCK`

Type: DERIVED.

Indicates statistically abnormal volatility expansion.

---

# 10. Session Registry

`SES-001 SESSION_ID`

Observed/derived from exchange calendar.

---

`SES-002 SESSION_TIME`

Derived from exchange timestamp.

---

`SES-003 TIME_FROM_OPEN`

Derived.

---

`SES-004 TIME_TO_CLOSE`

Derived.

---

`SES-005 SESSION_PHASE`

Derived.

Possible representation:

continuous or categorical.

Final representation remains unfrozen.

---

`SES-006 SESSION_OPEN_PRICE`

Derived from first valid market observation according to the canonical session rule.

---

`SES-007 SESSION_HIGH`

Derived.

Must satisfy:

`HIGH_t = max(P_<=t)`.

---

`SES-008 SESSION_LOW`

Derived.

Must satisfy:

`LOW_t = min(P_<=t)`.

---

`SES-009 VWAP`

Derived.

Formula:

`VWAP = Σ(P_i × V_i) / ΣV_i`.

---

# 11. Opening-Range Registry

`OR-001 OPENING_RANGE_HIGH`

Derived.

Only information available inside the defined opening-range interval may be used.

---

`OR-002 OPENING_RANGE_LOW`

Derived.

---

`OR-003 OPENING_RANGE_COMPLETE`

Boolean derived state.

Before completion:

`FALSE`.

After completion:

`TRUE`.

This prevents an incomplete opening range from being treated as final.

---

# 12. Option Registry

`OPT-001 OPTION_BID`

Observed.

---

`OPT-002 OPTION_ASK`

Observed.

---

`OPT-003 OPTION_LTP`

Observed.

---

`OPT-004 OPTION_SPREAD`

Derived.

---

`OPT-005 STRIKE`

Observed/static contract property.

---

`OPT-006 EXPIRY_TIMESTAMP`

Observed/static contract property.

---

`OPT-007 TIME_TO_EXPIRY`

Derived.

Formula:

`τ = ExpiryTimestamp - CurrentTimestamp`.

---

`OPT-008 OPTION_VOLUME`

Observed.

---

`OPT-009 OPTION_OPEN_INTEREST`

Observed where available.

---

`OPT-010 IMPLIED_VOLATILITY`

Observed or derived depending on source.

Exact provenance must be established from TrueData documentation.

---

`OPT-011 MONEyness`

Derived.

Canonical formula remains to be selected after source-contract reconciliation.

---

`OPT-012 OPTION_RESPONSE`

Derived.

Measures realized option movement conditional on underlying movement.

---

`OPT-013 OPTION_EXECUTION_QUALITY`

Derived.

Represents spread, liquidity, fillability and execution conditions.

---

# 13. Data-Quality Registry

`DQ-001 EVENT_VALID`

Boolean.

---

`DQ-002 SEQUENCE_VALID`

Boolean.

---

`DQ-003 TIMESTAMP_VALID`

Boolean.

---

`DQ-004 EVENT_DUPLICATE`

Boolean.

---

`DQ-005 EVENT_OUT_OF_ORDER`

Boolean.

---

`DQ-006 DATA_STALE`

Boolean.

---

`DQ-007 DATA_GAP`

Boolean.

---

`DQ-008 DATA_QUALITY_STATE`

Canonical aggregate data-quality state.

Possible states:

`VALID`

`DEGRADED`

`UNSAFE`.

---

`DQ-009 FEED_LATENCY`

Formula:

`ReceiveTimestamp - ExchangeTimestamp`.

---

# 14. Feature-Snapshot Registry

`FTR-001 FEATURE_SNAPSHOT`

Canonical immutable feature vector at timestamp `t`.

It references derived quantities rather than independently duplicating them.

Conceptually:

`F_t = {Price, Flow, Book, Liquidity, Volatility, Session, Option, Execution}`.

---

`FTR-002 FEATURE_FRESHNESS`

Defines whether every required component of the feature vector is current enough to be used.

---

`FTR-003 FEATURE_COMPLETENESS`

Measures whether required features are available.

---

# 15. Domain Registry

`DOM-001 MARKET_DOMAIN_DISTANCE`

Measures distance between the current feature state and validated historical feature domain.

Candidate mathematical representation:

`D² = (X-μ)^T Σ⁻¹(X-μ)`.

Final method remains empirically validated.

---

`DOM-002 DOMAIN_STATUS`

Possible states:

`IN_DOMAIN`

`DEGRADED`

`OUT_OF_DOMAIN`.

---

# 16. Probability Registry

`PRB-001 P_UP_RAW`

Estimated probability of the upward directional outcome.

---

`PRB-002 P_DOWN_RAW`

Estimated probability of the downward directional outcome.

---

`PRB-003 P_NEUTRAL_RAW`

Estimated probability of insufficient directional movement / neutral outcome.

Constraint:

`P_UP + P_DOWN + P_NEUTRAL = 1`.

---

`PRB-004 P_UP_ADJUSTED`

Evidence-adjusted upward probability.

---

`PRB-005 P_DOWN_ADJUSTED`

Evidence-adjusted downward probability.

---

`PRB-006 P_NEUTRAL_ADJUSTED`

Evidence-adjusted neutral probability.

---

`PRB-007 PROBABILITY_UNCERTAINTY`

Represents statistical uncertainty around the estimated probability.

---

# 17. Evidence Registry

`EVD-001 EFFECTIVE_SAMPLE_SIZE`

Formula for weighted observations:

`N_eff = (Σw_i)² / Σw_i²`.

---

`EVD-002 CALIBRATION_ERROR`

Measures historical difference between predicted probability and realized frequency.

---

`EVD-003 DISTRIBUTION_STABILITY`

Measures whether the predictive relationship remains temporally stable.

---

`EVD-004 DOMAIN_CONFIDENCE`

Confidence that current conditions remain within validated historical support.

---

`EVD-005 EVIDENCE_SCORE`

Canonical continuous evidence measure.

Range:

`[0,1]`.

---

`EVD-006 EVIDENCE_CLASS`

Possible states:

`INSUFFICIENT`

`WEAK`

`VALID`

`STRONG`.

---

# 18. Evidence-Adjusted Probability

Canonical conceptual transformation:

`P_adjusted = P_base + EvidenceScore × (P_raw - P_base)`.

This is a shrinkage representation.

Therefore:

`EvidenceScore = 0`

produces:

`P_adjusted = P_base`.

And:

`EvidenceScore = 1`

produces:

`P_adjusted = P_raw`.

The exact evidence transformation remains subject to walk-forward validation.

---

# 19. Horizon Registry

We previously identified a naming duplication here.

We therefore retain exactly one canonical predictive quantity:

`HRZ-001 EXPECTED_HORIZON_DISTRIBUTION`.

It represents:

`P(Horizon | CurrentState)`.

We do NOT separately maintain:

`ExpectedHoldingTime`

as an independent model variable.

Any expected duration shown to the user is derived from:

`EXPECTED_HORIZON_DISTRIBUTION`.

---

`HRZ-002 TRADE_MODE`

Derived from the horizon distribution.

Possible modes:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

The boundaries remain learned.

---

# 20. Economic Registry

`ECO-001 GROSS_PNL_DISTRIBUTION`

Conditional distribution of trade outcome before execution costs.

---

`ECO-002 EXECUTION_COST_DISTRIBUTION`

Conditional distribution of:

spread

slippage

fees

and other applicable costs.

---

`ECO-003 NET_PNL_DISTRIBUTION`

Canonical economic outcome distribution:

`GrossPnL - ExecutionCosts`.

---

`ECO-004 EXPECTED_NET_PNL`

Expected value of the net P&L distribution.

---

`ECO-005 CONSERVATIVE_NET_EV`

Conservative estimate used for trade eligibility.

---

`ECO-006 CONTINUATION_VALUE`

Expected incremental value of maintaining the current position.

---

`ECO-007 EXIT_VALUE`

Economic value of exiting at the current state.

---

# 21. Risk Registry

`RSK-001 EXPECTED_MAE`

Expected maximum adverse excursion distribution.

---

`RSK-002 TAIL_LOSS`

Validated adverse-tail loss quantity.

---

`RSK-003 EXECUTION_TAIL_RISK`

Risk arising from abnormal execution conditions.

---

`RSK-004 TRADE_RISK`

Current risk attributable to one position.

---

`RSK-005 PORTFOLIO_RISK`

Aggregate portfolio risk.

---

`RSK-006 INCREMENTAL_PORTFOLIO_RISK`

Change in portfolio risk if a candidate trade is added.

---

`RSK-007 RISK_CAPACITY`

Remaining permissible risk capacity.

---

`RSK-008 HARD_RISK_LIMIT`

Non-negotiable maximum allowed risk.

---

# 22. Protection Registry

`PRT-001 INITIAL_STOP`

Initial protection level established from actual execution and validated risk distribution.

---

`PRT-002 CURRENT_STOP`

The sole canonical current protection level.

We explicitly reject separate competing variables such as:

`TrailingStop`

`DynamicStop`

`ActiveStop`.

Those can be descriptive labels, but:

`CURRENT_STOP`

is authoritative.

---

`PRT-003 PEAK_NET_PNL`

Formula:

`PeakNetPnL_t = max(PeakNetPnL_(t-1), NetPnL_t)`.

---

`PRT-004 GIVEBACK`

Formula:

`Giveback = PeakNetPnL - NetPnL`.

---

`PRT-005 PROFIT_PROTECTION_BOUNDARY`

Validated minimum acceptable retained-profit boundary.

---

`PRT-006 REVERSAL_PROBABILITY`

Probability that the current profitable state transitions into an adverse outcome.

---

# 23. Position Registry

`POS-001 POSITION_STATUS`

Possible states:

`FLAT`

`ENTRY_PENDING`

`OPEN`

`EXIT_PENDING`

`CLOSED`.

---

`POS-002 POSITION_DIRECTION`

For this strategy:

`LONG_PREMIUM_CE`

or:

`LONG_PREMIUM_PE`.

---

`POS-003 POSITION_QUANTITY`

Actual filled quantity.

---

`POS-004 ENTRY_PRICE`

Actual weighted-average execution price.

---

`POS-005 CURRENT_MARK_PRICE`

Current executable/marking price according to the valuation rule.

---

`POS-006 NET_PNL`

Canonical current position P&L.

We explicitly eliminate separate authoritative variables:

`CurrentProfit`

`CurrentPnL`.

Only:

`NET_PNL`

is canonical.

---

`POS-007 MFE`

Maximum favorable excursion.

---

`POS-008 MAE`

Maximum adverse excursion.

---

`POS-009 TIME_IN_TRADE`

Elapsed time since actual entry execution.

---

# 24. Execution Registry

`EXE-001 ORDER_STATUS`

Possible states:

`NOT_SUBMITTED`

`PENDING`

`PARTIAL`

`FILLED`

`CANCELLED`

`REJECTED`.

---

`EXE-002 REQUESTED_QUANTITY`

Quantity submitted.

---

`EXE-003 FILLED_QUANTITY`

Actual executed quantity.

---

`EXE-004 REMAINING_QUANTITY`

Formula:

`Requested - Filled`.

---

`EXE-005 ACTUAL_EXECUTION_PRICE`

Actual fill price.

---

`EXE-006 REALIZED_SLIPPAGE`

Difference between reference executable price and actual execution.

---

`EXE-007 ORDER_AGE`

Elapsed time since order submission.

---

`EXE-008 EXECUTION_VALID`

Boolean indicating whether execution conditions satisfy the validated execution model.

---

# 25. Portfolio Registry

`PFL-001 TOTAL_CAPITAL`

Current capital basis.

---

`PFL-002 AVAILABLE_CAPITAL`

Capital not currently committed.

---

`PFL-003 USED_RISK`

Current portfolio risk consumption.

---

`PFL-004 AVAILABLE_RISK_CAPACITY`

Remaining risk capacity.

---

`PFL-005 DIRECTIONAL_EXPOSURE`

Aggregate directional exposure.

---

`PFL-006 CORRELATED_EXPOSURE`

Aggregate exposure attributable to correlated positions.

---

`PFL-007 INCREMENTAL_UTILITY`

Change in portfolio utility caused by adding a candidate position.

---

# 26. Decision Registry

`DEC-001 CANDIDATE_DIRECTION`

Possible:

`UP`

`DOWN`

`NONE`.

---

`DEC-002 CANDIDATE_OPTION`

Selected CE/PE contract if eligible.

---

`DEC-003 CONSERVATIVE_UTILITY`

Conservative utility estimate of the candidate.

---

`DEC-004 NO_TRADE_UTILITY`

Canonical baseline.

Conceptually:

`0`

plus any validated opportunity-value adjustment.

---

`DEC-005 DECISION_MARGIN`

Difference between best candidate utility and competing alternative.

---

`DEC-006 TRADE_ELIGIBLE`

Boolean.

---

`DEC-007 FINAL_DECISION`

Possible:

`NO_TRADE`

`BUY_CE`

`BUY_PE`

For an open position:

`HOLD`

`UPDATE_PROTECTION`

`EXIT`.

---

# 27. Learning Registry

`LRN-001 LABEL_STATUS`

Possible:

`IMMATURE`

`MATURE`.

---

`LRN-002 MODEL_VERSION`

Identifier for the statistical model used at that historical timestamp.

---

`LRN-003 PARAMETER_VERSION`

Identifier for the parameter set.

---

`LRN-004 TRAINING_WINDOW`

Historical interval used for estimation.

---

`LRN-005 VALIDATION_WINDOW`

Historical interval used for model selection.

---

`LRN-006 TEST_WINDOW`

Historical interval reserved for out-of-sample evaluation.

---

`LRN-007 MODEL_PROMOTION_STATUS`

Possible:

`CHALLENGER`

`VALIDATED`

`CHAMPION`

`REJECTED`.

---

# 28. Dependency Matrix

The primary dependencies are:

`BEST_BID <- Event`

`BEST_ASK <- Event`

`LTP <- Event`

`MID_PRICE <- BEST_BID, BEST_ASK`

`SPREAD <- BEST_BID, BEST_ASK`

`RELATIVE_SPREAD <- SPREAD, MID_PRICE`

`LOG_RETURN <- Price_t, Price_(t-1)`

`PRICE_VELOCITY <- Price_t, Price_(t-1), Time`

`PRICE_ACCELERATION <- Velocity_t, Velocity_(t-1), Time`

`BUY_VOLUME <- TradeClassification, TradeQuantity`

`SELL_VOLUME <- TradeClassification, TradeQuantity`

`DELTA <- BUY_VOLUME, SELL_VOLUME`

`FLOW_IMBALANCE <- BUY_VOLUME, SELL_VOLUME`

`FLOW_RATE <- Volume, Time`

`FLOW_PERSISTENCE <- HistoricalFlow`

`PRICE_FLOW_RESPONSE <- PriceChange, FlowChange`

`ORDER_BOOK_IMBALANCE <- BidDepth, AskDepth`

`SPREAD_SHOCK <- Spread, HistoricalSpread`

`DEPTH_SHOCK <- Depth, HistoricalDepth`

`REALIZED_VOLATILITY <- Returns`

`VOLATILITY_STATE <- RealizedVolatility, HistoricalDistribution`

`VWAP <- Price, Volume`

`OPTION_SPREAD <- OptionBid, OptionAsk`

`TIME_TO_EXPIRY <- Expiry, CurrentTime`

`MONEYNESS <- Strike, UnderlyingPrice`

`FEATURE_SNAPSHOT <- All required causal state`

`DOMAIN_DISTANCE <- FeatureSnapshot, HistoricalFeatureDistribution`

`P_RAW <- FeatureSnapshot, HistoricalLabels, ModelVersion`

`EVIDENCE_SCORE <- SampleSupport, Uncertainty, Calibration, Stability, Domain`

`P_ADJUSTED <- P_RAW, BaseRate, EvidenceScore`

`GROSS_PNL_DISTRIBUTION <- Prediction, OptionState, Horizon`

`EXECUTION_COST_DISTRIBUTION <- Spread, Liquidity, Latency, ExecutionHistory`

`NET_PNL_DISTRIBUTION <- GrossPnLDistribution, ExecutionCostDistribution`

`CONSERVATIVE_NET_EV <- NetPnLDistribution, Uncertainty`

`INCREMENTAL_PORTFOLIO_RISK <- CandidateRisk, ExistingPortfolio`

`INCREMENTAL_UTILITY <- NetEV, Risk, PortfolioState`

`FINAL_DECISION <- Utility, Evidence, Risk, Execution, DataValidity`

`POSITION_STATE <- ActualExecutionEvents`

`NET_PNL <- PositionState, CurrentMarketState`

`PEAK_NET_PNL <- HistoricalNetPnL_since_entry`

`GIVEBACK <- PeakNetPnL, NetPnL`

`CURRENT_STOP <- PreviousCurrentStop, ProtectionCandidate`

`CONTINUATION_VALUE <- CurrentState, FutureOutcomeDistribution`

`EXIT_DECISION <- HardRisk, Protection, ContinuationValue, ExecutionSafety`.

---

# 29. Dependency Direction

The canonical dependency direction is:

```text
OBSERVED
   |
   v
DERIVED MARKET STATE
   |
   v
FEATURE STATE
   |
   v
PREDICTIVE STATE
   |
   v
EVIDENCE
   |
   v
ECONOMICS
   |
   v
RISK
   |
   v
DECISION
   |
   v
EXECUTION
   |
   v
POSITION
   |
   v
REALIZED OUTCOME
   |
   v
LEARNING
```

Learning can influence a future model version.

It cannot modify the already completed historical state.

---

# 30. Critical Dependency Prohibition

The following dependencies are forbidden:

`Probability -> RawMarketState`

`Decision -> Feature`

`Decision -> HistoricalFeature`

`FutureOutcome -> CurrentDecision`

`FutureOutcome -> CurrentFeature`

`FutureOutcome -> CurrentProbability`

`PositionOutcome -> SameTradeEntryDecision`.

The only legal feedback is through the explicitly defined historical learning pipeline after label maturation.

---

# 31. Temporal DAG

The system is therefore not one static DAG.

It is a temporal DAG:

`G_t = G(Event_<=t)`.

At time `t`:

only information available at `t` exists.

At time `t+1`:

new information extends the graph.

This preserves causal ordering.

---

# 32. State Ownership Matrix

`PriceState`

owns:

`BEST_BID`

`BEST_ASK`

`LTP`

`MID_PRICE`

`SPREAD`.

`FlowState`

owns:

`BUY_VOLUME`

`SELL_VOLUME`

`DELTA`

`FLOW_IMBALANCE`.

`LiquidityState`

owns:

`SPREAD_SHOCK`

`DEPTH_SHOCK`

`LIQUIDITY_STATE`.

`PositionState`

owns:

`NET_PNL`

`PEAK_NET_PNL`

`MFE`

`MAE`

`CURRENT_STOP`.

`ProbabilityState`

owns:

`P_UP`

`P_DOWN`

`P_NEUTRAL`.

`EvidenceState`

owns:

`EVIDENCE_SCORE`

`EVIDENCE_CLASS`.

`DecisionState`

owns:

`FINAL_DECISION`.

No variable may have multiple authoritative owners.

---

# 33. Canonical Variable Elimination

The registry deliberately eliminates several previously ambiguous concepts.

There is no separate canonical:

`CurrentProfit`

and:

`CurrentPnL`.

There is only:

`NET_PNL`.

There is no separate canonical:

`ExpectedHoldingTime`

and:

`ExpectedHorizon`.

There is only:

`EXPECTED_HORIZON_DISTRIBUTION`.

There is no separate canonical:

`TrailingStop`

and:

`DynamicStop`.

There is only:

`CURRENT_STOP`.

There is no independent:

`TargetPrice`

that competes with:

`ContinuationValue`.

Profit-taking is governed by:

`CONTINUATION_VALUE`

and:

`PROFIT_PROTECTION_BOUNDARY`.

---

# 34. Variable Lifecycle

Every variable has one of four lifecycle states:

`UNINITIALIZED`

`VALID`

`STALE`

`INVALID`.

A variable cannot silently transition:

`INVALID -> VALID`

without a new valid source event.

---

# 35. Reset Rules

Session-dependent state resets at the canonical session boundary.

Trade-dependent state resets at:

`POSITION CLOSED`.

Historical model state resets only when:

`MODEL_VERSION`

changes.

Portfolio state resets only according to actual account/execution events.

These reset domains must never be mixed.

---

# 36. Precision Rule

The registry does not authorize precision beyond the source.

If TrueData provides:

`price precision = X`

the mathematical state cannot pretend:

`X + additional meaningful decimals`.

Similarly:

`timestamp precision`

determines the finest causal ordering available.

---

# 37. TrueData Boundary

Every observed variable currently has:

`TrueDataField = TBD`.

This is intentional.

The mathematical architecture is not blocked by the documentation.

However, implementation is blocked at the point where a required observed variable cannot be mapped to an actual source field with known semantics.

---

# 38. Required Source Reconciliation

For every `OBSERVED` variable we must eventually determine:

`Exact field name`

`Source`

`Live availability`

`Historical availability`

`Timestamp semantics`

`Precision`

`Update frequency`

`Sequence semantics`

`Entitlement`

`Missing-data behavior`.

No implementation assumption is permitted before this reconciliation.

---

# 39. Master Dependency Invariant

For every canonical variable `X`:

`X = f(Parents(X))`.

Every parent must be explicitly registered.

Therefore there can be no hidden dependency.

If a variable requires something that is not registered:

`SPECIFICATION_ERROR`.

---

# 40. Master Duplication Invariant

If two variables have:

`identical semantic meaning`

they must be merged.

If two variables have similar names but different meanings:

their distinction must be explicitly documented.

This prevents the architecture from slowly accumulating duplicate representations.

---

# 41. Master Causality Invariant

For every decision at `t`:

`Decision_t`

may depend only on:

`ObservedState_<=t`

`DerivedState_<=t`

`ModelState_<=t`

`EvidenceState_<=t`

`HistoricalLabels_<t`.

It may never depend on:

`Outcome_t+`

or:

`FutureState`.

---

# 42. Current Architecture Status

The canonical registry now connects:

`TrueData Event`

to:

`Market State`

to:

`Feature`

to:

`Probability`

to:

`Evidence`

to:

`Economic Value`

to:

`Risk`

to:

`Decision`

to:

`Execution`

to:

`Position`

to:

`Learning`.

At this point, adding another abstract strategy layer would mostly duplicate existing architecture.

The next correct operation is therefore an audit.

# NEXT: CANONICAL REGISTRY AUDIT

The audit will attempt to break this registry in four ways.

First:

`Duplicate variable attack`.

We search for two variables representing the same quantity.

Second:

`Circular dependency attack`.

We attempt to find:

`A -> B -> C -> A`.

Third:

`Temporal leakage attack`.

We attempt to find any variable whose definition accidentally requires information unavailable at its timestamp.

Fourth:

`Unobservable-variable attack`.

We identify every variable that the strategy mathematically requires but that may not actually be reconstructible from the TrueData feed.

Only after those four attacks pass should the registry be considered implementation-ready.