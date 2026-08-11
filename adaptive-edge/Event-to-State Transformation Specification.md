# Event-to-State Transformation Specification
## Canonical Tick-Level State Reconstruction — Version 1.0

## 1. Objective

For every valid incoming market event:

`E_t`

the system must deterministically transform the previous state:

`S_(t-1)`

into:

`S_t`.

The canonical transformation is:

`S_t = T(S_(t-1), E_t)`.

The transformation must be:

`Deterministic`

`Causal`

`Chronological`

`Replayable`

`Idempotent for duplicate events`

`Safe under malformed events`.

No predictive model is involved in this layer.

This layer reconstructs what the market state actually was.

---

# 2. Event-Time Principle

Every event has at least two temporal concepts:

`ExchangeTime`

and:

`ReceiveTime`.

The market state is indexed primarily by:

`ExchangeTime`.

Receive time is used for:

`Latency`

`Data-quality`

`Execution`.

Therefore:

`MarketStateTime != necessarily ReceiveTime`.

---

# 3. Canonical Event

The abstract event is:

`E_t = {I, T_e, T_r, P, Q, V, D, O}`

where:

`I = instrument`

`T_e = exchange timestamp`

`T_r = receive timestamp`

`P = price information`

`Q = quantity information`

`V = volume information`

`D = trade/depth information`

`O = auxiliary information`.

The exact TrueData field mapping remains `TBD`.

---

# 4. Event Validation

Before an event can modify state:

`Validate(E_t)`.

Validation checks:

`Instrument exists`

`Timestamp valid`

`Sequence/order valid`

`Price valid`

`Quantity valid`

`Event type valid`

`Timestamp not impossible`

`Data entitlement valid`.

If validation fails:

`E_t -> REJECTED_EVENT`.

The rejected event must not mutate market state.

---

# 5. Duplicate Event

If:

`EventIdentity(E_t) = EventIdentity(previous event)`

then:

`E_t = DUPLICATE`.

Expected transformation:

`S_t = S_(t-1)`.

No state variable changes.

This is an invariant.

---

# 6. Out-of-Order Event

If:

`T_e < LastProcessedExchangeTime`

the event is out of chronological order.

There are two possibilities.

If deterministic reordering is supported:

`Event -> reorder buffer`.

Otherwise:

`Event -> DATA_UNSAFE`.

The system must never silently process an old event as though it were current.

---

# 7. Missing Event

A missing event cannot be inferred simply from:

`absence of data`.

Therefore:

`No event != zero movement`.

If a detectable sequence gap exists:

`SequenceGap = TRUE`.

The state becomes:

`DATA_QUALITY_DEGRADED`.

The severity depends on the validated impact.

---

# 8. State Partition

The complete state is divided into:

`S_t = {`

`SessionState`

`PriceState`

`TradeFlowState`

`OrderBookState`

`VolumeState`

`VolatilityState`

`LiquidityState`

`OptionState`

`ExecutionState`

`DataQualityState`

`PositionState`

`PortfolioState`

`ModelState`

`EvidenceState`

`}`.

Not every incoming event updates every component.

---

# 9. Session State

Session state contains:

`SessionID`

`MarketOpenTime`

`CurrentSessionTime`

`TimeFromOpen`

`TimeToClose`

`SessionPhase`

`TradingDay`.

The exact market-session boundaries will be obtained from the production market specification.

---

# 10. Session Reset

At the start of a new trading session:

session-dependent variables are reset.

Examples:

`IntradayVolume = 0`

`SessionTradeCount = 0`

`SessionVWAP accumulators reset`

`IntradayHigh`

`IntradayLow`

`SessionFlowProfile`.

But longer historical variables do not reset.

For example:

`LongTermVolatilityHistory`

remains.

This prevents accidental contamination between:

`session-local`

and:

`historical`.

---

# 11. Price State

Price state contains the currently observable executable market:

`BestBid`

`BestAsk`

`LastTradedPrice`

`MidPrice`

`Spread`

`SpreadRelative`.

Where:

`MidPrice = (Bid + Ask) / 2`

and:

`Spread = Ask - Bid`.

These quantities are only valid when both bid and ask are available.

---

# 12. Executable Price Principle

For a hypothetical immediate long entry:

`EntryPrice_long = Ask`.

For a hypothetical immediate long exit:

`ExitPrice_long = Bid`.

For a hypothetical short entry:

`EntryPrice_short = Bid`.

For a hypothetical short exit:

`ExitPrice_short = Ask`.

Therefore:

`MidPrice`

is a state measurement.

It is not automatically an executable trading price.

---

# 13. Price Return

For a reference price `P_ref`:

`R_t = P_t / P_ref - 1`.

Multiple reference horizons exist:

`R_micro`

`R_short`

`R_medium`

`R_session`.

The exact windows remain learned/configurable.

Crucially, every reference must be constructed exclusively from:

`timestamps <= t`.

---

# 14. Log Return

For statistical modeling:

`r_t = ln(P_t / P_(t-1))`.

The log return is useful for:

`volatility`

`distribution`

`normalization`.

It is not itself a trading signal.

---

# 15. Price Velocity

Over event-time interval:

`ΔP / Δt`.

Therefore:

`Velocity_t = (P_t - P_prev) / (T_t - T_prev)`.

If:

`Δt = 0`

the value is invalid.

The system must not divide by zero.

---

# 16. Price Acceleration

Price acceleration measures the change in velocity:

`Acceleration_t = (Velocity_t - Velocity_prev) / Δt`.

This is an observation.

It does not mean:

"price will continue."

The probability engine determines whether the historical relationship is predictive.

---

# 17. Trade Event Classification

Each transaction event may be classified, when the data permits, as:

`BUY_AGGRESSOR`

or:

`SELL_AGGRESSOR`

or:

`UNKNOWN`.

This classification must be based on the actual available market information and the validated classification method.

Unknown events remain unknown.

They are not arbitrarily assigned.

---

# 18. Executed Volume

For event `t`:

`V_t = executed quantity`.

Cumulative session volume:

`CumVolume_t = CumVolume_(t-1) + V_t`.

This is an additive state variable.

---

# 19. Buy Volume

For classified aggressive buying:

`BuyVolume_t = BuyVolume_(t-1) + V_t`.

For non-buy events:

`BuyVolume_t = BuyVolume_(t-1)`.

Unknown classification does not become buy volume.

---

# 20. Sell Volume

Similarly:

`SellVolume_t = SellVolume_(t-1) + V_t`

only when classified as aggressive selling.

---

# 21. Delta

Cumulative delta:

`Delta_t = BuyVolume_t - SellVolume_t`.

Incremental delta:

`ΔDelta_t = BuyVolumeIncrement_t - SellVolumeIncrement_t`.

Both are retained because:

`cumulative`

and:

`local`

flow answer different questions.

---

# 22. Flow Imbalance

A normalized flow imbalance may be:

`FI_t = (BuyVolume_t - SellVolume_t) / (BuyVolume_t + SellVolume_t)`.

Therefore:

`-1 <= FI_t <= 1`.

If:

`BuyVolume + SellVolume = 0`

then:

`FI = undefined`.

It must not be converted to:

`0`

without an explicit semantic rule.

---

# 23. Why Both Delta and Imbalance Exist

Delta measures:

`absolute directional volume`.

Imbalance measures:

`relative directional dominance`.

A large delta with enormous total volume may produce a moderate imbalance.

A small delta in a low-volume environment may produce a large imbalance.

They are therefore not duplicates.

---

# 24. Volume Rate

For interval `W`:

`VolumeRate_W = Volume_W / W`.

But `W` can be:

`clock time`

or:

`event count`.

These must remain separate.

---

# 25. Event-Time Versus Clock-Time

This distinction is critical for scalping.

Clock-time window:

`10 seconds`.

Event-time window:

`last N events`.

They are not equivalent.

A high-activity market may generate thousands of events in ten seconds.

A quiet market may generate very few.

Both representations should remain available.

---

# 26. Rolling Windows

Every rolling statistic is represented:

`Feature_t(W)`.

The window must contain only:

`events <= t`.

For a time window:

`[t-W, t]`.

For an event window:

`last N valid events ending at t`.

No future observation may enter.

---

# 27. Rolling Mean

For feature `X`:

`μ_t(W) = mean(X_(t-W:t))`.

The implementation may optimize the calculation, but the mathematical meaning remains:

`historical information available at t`.

---

# 28. Rolling Variance

`σ²_t(W) = variance(X_(t-W:t))`.

The estimator definition must be fixed globally.

The model cannot switch silently between:

`population variance`

and:

`sample variance`.

---

# 29. Volatility State

Volatility state contains multiple horizons:

`σ_micro`

`σ_short`

`σ_medium`

`σ_session`.

The system does not assume one volatility number represents the market.

---

# 30. Realized Volatility

For returns:

`RV_W = sqrt(Σ r_i²)`.

The exact annualization is unnecessary for intraday decision-making unless specifically required.

The important property is:

`RV_W`

uses only information available through `t`.

---

# 31. Volatility Acceleration

We may track:

`VolAcceleration = σ_short / σ_medium`.

This indicates whether short-term volatility is expanding relative to the broader state.

It is not itself a directional signal.

---

# 32. Volatility Regime

The system derives:

`VolatilityState_t`

from the conditional distribution of volatility.

Possible state:

`LOW`

`NORMAL`

`HIGH`

`EXTREME`.

These labels are descriptive.

The actual classification boundaries are learned.

---

# 33. Order-Book State

Where depth data is available:

`BidDepth_k`

`AskDepth_k`

for depth levels:

`k = 1...K`.

The exact maximum depth depends on entitlement.

---

# 34. Top-Level Imbalance

For selected depth:

`OBI = (ΣBidDepth - ΣAskDepth) / (ΣBidDepth + ΣAskDepth)`.

This produces:

`-1 <= OBI <= 1`.

Again:

`denominator = 0`

means:

`undefined`.

---

# 35. Depth-Weighted Imbalance

Different levels can receive distance weights:

`w_k`.

Then:

`OBI_weighted =`

`Σ(w_k × BidDepth_k) - Σ(w_k × AskDepth_k)`

divided by:

`Σ(w_k × BidDepth_k) + Σ(w_k × AskDepth_k)`.

The weighting function remains unfrozen.

---

# 36. Depth Is Not Executed Flow

This distinction is mandatory:

`DisplayedDepth != ExecutedVolume`.

Therefore:

`OrderBookImbalance`

cannot be interpreted as:

`actual buying/selling`.

They are separate evidence domains.

---

# 37. Liquidity State

Liquidity state contains:

`Spread`

`Depth`

`DepthConcentration`

`ExecutionRate`

`FillProbability`

`LiquidityChange`.

The exact executable metrics depend on the available market feed.

---

# 38. Spread State

Relative spread:

`SpreadRelative = (Ask-Bid)/Mid`.

This allows comparison across different price levels.

---

# 39. Spread Shock

Define:

`SpreadShock = CurrentSpread / HistoricalSpreadState`.

If spread suddenly expands:

`ExecutionRisk ↑`.

The trading engine must not treat this as merely another feature.

It can directly affect:

`ExecutionEligibility`.

---

# 40. Depth Shock

Similarly:

`DepthShock = CurrentDepth / HistoricalDepthState`.

A sudden reduction in available depth indicates:

`ExecutionRisk ↑`.

---

# 41. Price-Flow Response

One of our important microstructure variables is:

`PriceResponseToFlow`.

Conceptually:

`PRS = ΔPrice / ΔAggressiveVolume`.

This asks:

"How much price movement is occurring per unit of directional execution?"

---

# 42. Absorption

A candidate absorption condition exists when:

`DirectionalFlow ↑`

while:

`PriceResponse ↓`.

But this is only a state description.

The model determines whether this historically predicts:

`continuation`

or:

`reversal`.

---

# 43. Flow Persistence

For directional flow:

`Persistence_W = proportion of recent intervals/events supporting the same direction`.

This captures:

`one-off burst`

versus:

`persistent pressure`.

---

# 44. Flow Acceleration

`FlowAcceleration = ΔFlow / Δt`.

A sudden increase in aggressive activity can be distinguished from:

`steady flow`.

---

# 45. Flow Exhaustion

A potential exhaustion state can be represented through:

`FlowAcceleration ↓`

while:

`CumulativeFlow remains high`.

Again:

`exhaustion state != automatic reversal`.

---

# 46. Price-Flow Divergence

Suppose:

`Delta ↑`

but:

`Price ↓`.

The state becomes:

`Divergence_UP`.

Opposite:

`Delta ↓`

while:

`Price ↑`

becomes:

`Divergence_DOWN`.

These states are fed into the statistical model.

---

# 47. Time-of-Day State

The same microstructure condition may have different meaning at:

`09:20`

versus:

`14:45`.

Therefore the state includes:

`TimeOfSession`.

It may also include:

`HistoricalTimeOfDayDistribution`.

---

# 48. Session Phase

The abstract phase state:

`OPEN`

`EARLY`

`MID`

`LATE`

`PRE_CLOSE`.

Exact boundaries are not fixed here.

The empirical model determines whether boundaries should be continuous rather than categorical.

---

# 49. Opening State

The system maintains:

`OpeningPrice`

`OpeningRange`

`OpeningVolume`

`OpeningFlow`.

The opening-range construction is strictly causal.

---

# 50. Opening Range

If the model eventually uses an opening range:

`OR_high_t = max(price <= t within opening window)`

`OR_low_t = min(price <= t within opening window)`.

Before the opening window ends:

the range is incomplete.

It must not be treated as final.

This prevents a subtle look-ahead error.

---

# 51. Intraday High/Low

At time `t`:

`High_t = max(P <= t)`

`Low_t = min(P <= t)`.

Future highs/lows cannot influence the current state.

---

# 52. VWAP State

Cumulative VWAP:

`VWAP_t = Σ(P_i × V_i) / ΣV_i`.

The numerator and denominator are session-dependent accumulators.

Only completed trades through `t` are included.

---

# 53. VWAP Is State, Not Signal

The system does not say:

`Price > VWAP => BUY`.

Instead:

`DistanceFromVWAP`

becomes a feature.

Its predictive value is estimated historically.

---

# 54. Option State

For each candidate option:

`OptionPrice`

`Bid`

`Ask`

`Spread`

`Volume`

`OpenInterest`

`IV`

`Greeks`

`UnderlyingPrice`

`TimeToExpiry`.

Not all fields are guaranteed to exist.

Unavailable fields remain:

`UNKNOWN`.

---

# 55. Option Moneyness

Moneyness is represented continuously rather than merely:

`ITM`

`ATM`

`OTM`.

For example:

`Moneyness = Strike / UnderlyingPrice`

or an equivalent validated representation.

The exact canonical representation will be chosen after the TrueData contract is known.

---

# 56. Time to Expiry

`τ_t = ExpiryTimestamp - CurrentTimestamp`.

As time advances:

`τ_t ↓`.

This is a deterministic temporal state variable.

---

# 57. Option Relative Movement

For candidate option:

`OptionReturn = OptionPrice_t / OptionPrice_reference - 1`.

This allows the system to distinguish:

`underlying movement`

from:

`option response`.

---

# 58. Underlying-Option Relationship

The system maintains:

`ObservedOptionResponse`

relative to:

`ObservedUnderlyingMovement`.

This allows estimation of:

`realized option sensitivity`.

It should not assume theoretical Greeks perfectly describe real market behavior.

---

# 59. IV State

Where implied volatility is available:

`IV_t`.

The state can include:

`IVLevel`

`IVChange`

`IVPercentile`

`IVAcceleration`.

All are causal.

---

# 60. IV Shock

If:

`ΔIV`

is statistically abnormal:

`IVShock = TRUE`.

This directly affects:

`OptionEconomicDistribution`.

---

# 61. Execution State

Execution state contains:

`FeedLatency`

`OrderLatency`

`ExpectedSlippage`

`ObservedSpread`

`FillProbability`

`PendingOrderAge`.

This is distinct from market prediction.

---

# 62. Feed Latency

`FeedLatency_t = ReceiveTime - ExchangeTime`.

This quantity can be used for:

`execution eligibility`.

It must not be used to retroactively modify:

`historical market state`.

---

# 63. Pending Order Age

For order created at:

`T_order`:

`Age = CurrentTime - T_order`.

The age must be based on the execution clock.

---

# 64. Position State

If no position:

`PositionQuantity = 0`.

If long:

`PositionDirection = LONG`.

If short:

`PositionDirection = SHORT`.

For our directional option-buying strategy:

the actual option position is long premium.

---

# 65. Entry Price

Once filled:

`EntryPrice = actual executed average price`.

Not:

`signal price`.

Not:

`mid price`.

Not:

`requested price`.

---

# 66. Current P&L

We maintain one canonical quantity:

`NetPnL_t`.

We do not separately maintain ambiguous variables such as:

`CurrentProfit`

and:

`CurrentPnL`.

The canonical quantity is:

`NetPnL`.

Gross components can exist separately.

---

# 67. Peak Net P&L

For an open position:

`PeakNetPnL_t = max(PeakNetPnL_(t-1), NetPnL_t)`.

This variable can never decrease.

---

# 68. Giveback

`Giveback_t = PeakNetPnL_t - NetPnL_t`.

Therefore:

`Giveback >= 0`.

If:

`NetPnL = PeakNetPnL`

then:

`Giveback = 0`.

---

# 69. Maximum Favorable Excursion

For the actual position:

`MFE_t = max historical favorable excursion since entry`.

This is updated whenever a new favorable extreme occurs.

---

# 70. Maximum Adverse Excursion

Similarly:

`MAE_t = max historical adverse excursion since entry`.

It records the worst adverse movement experienced.

---

# 71. Stop State

The position contains:

`InitialStop`

`CurrentStop`.

We intentionally do not maintain:

`TrailingStop`

as an independent canonical variable.

`CurrentStop`

is the canonical protection level.

---

# 72. Stop Update

Candidate:

`S_candidate`.

Then:

`S_new = max(S_current, S_candidate)`

for a long-risk protection boundary expressed in price space.

The exact directional transformation for options must account for whether the protection variable is:

`option price`

or:

`underlying-derived risk boundary`.

This remains part of the final execution contract.

---

# 73. Target State

We avoid maintaining a single fixed:

`TargetPrice`.

Instead the system maintains:

`ContinuationValue`

and:

`ProfitProtectionBoundary`.

This is consistent with our earlier decision to avoid static targets.

---

# 74. Trade Horizon State

We retain one canonical variable:

`ExpectedHorizonDistribution`.

We do not maintain both:

`ExpectedHoldingTime`

and:

`ExpectedHorizon`.

`ExpectedHorizonDistribution`

is the canonical quantity.

Any UI representation such as:

`ExpectedHoldingTime`

is a derived presentation value.

---

# 75. Trade Mode

Derived from the horizon distribution:

`MICRO`

`SCALP`

`EXTENDED_SCALP`

`INTRADAY`.

The exact classification boundaries are learned.

The classification itself does not determine entry.

---

# 76. Probability State

After state reconstruction, the probability engine receives:

`FeatureSnapshot_t`.

It produces:

`P_UP`

`P_DOWN`

`P_NEUTRAL`

plus uncertainty.

The state layer does not calculate these probabilities.

---

# 77. Evidence State

The evidence engine receives:

`FeatureSnapshot`

`ProbabilityState`

`HistoricalDistributionState`.

It produces:

`EvidenceScore`

`EvidenceClass`

`DomainStatus`.

Again:

state reconstruction does not decide whether evidence is sufficient.

---

# 78. Causal Dependency

The dependency chain is:

```text
RAW EVENT
   |
   +--> DATA VALIDATION
   |
   +--> PRICE STATE
   |
   +--> FLOW STATE
   |
   +--> ORDER BOOK STATE
   |
   +--> VOLUME STATE
   |
   +--> VOLATILITY STATE
   |
   +--> LIQUIDITY STATE
   |
   +--> OPTION STATE
   |
   +--> EXECUTION STATE
   |
   v
FEATURE SNAPSHOT
   |
   v
PROBABILITY
   |
   v
EVIDENCE
   |
   v
ECONOMIC VALUE
   |
   v
DECISION
```

---

# 79. No Circular Dependency

State reconstruction cannot depend on:

`Probability`

or:

`Decision`.

Therefore:

`State_t`

is independent of the current model decision.

This prevents feedback contamination.

---

# 80. Critical Separation

The architecture has three fundamentally different categories.

### Observed State

What the market actually did:

`Price`

`Volume`

`Depth`

`Flow`

`IV`

`Spread`.

### Derived State

What can be mathematically calculated from observed history:

`Volatility`

`VWAP`

`Delta`

`Imbalance`

`Velocity`

`MFE`

`MAE`.

### Predictive State

What the model believes may happen:

`P_UP`

`P_DOWN`

`ContinuationValue`

`ReversalProbability`.

The first two must never depend on the third.

---

# 81. This Prevents Circular Learning

Incorrect:

`Decision → affects feature → feature → predicts decision`.

Correct:

`Market → state → feature → prediction → decision`.

The resulting trade outcome may later enter:

`historical learning`.

But not the current state retroactively.

---

# 82. Event Processing Order

For every event:

```text
1. Receive event

2. Validate event

3. Validate chronology

4. Update data-quality state

5. Update session state

6. Update price state

7. Update trade-flow state

8. Update volume state

9. Update order-book state

10. Update volatility state

11. Update liquidity state

12. Update option state

13. Update execution state

14. Update position state

15. Construct feature snapshot

16. Evaluate domain

17. Calculate probabilities

18. Calculate evidence

19. Calculate economic value

20. Apply portfolio constraints

21. Produce decision

22. Record immutable event/state snapshot
```

This is the canonical temporal order.

---

# 83. Decision Does Not Modify Historical State

Suppose the decision is:

`BUY_CE`.

The state variables describing what the market did remain unchanged.

The position state changes because an order has been submitted or filled.

Therefore:

`MarketState != PositionState`.

This distinction is important.

---

# 84. Order Submission

Submitting an order creates:

`OrderState = PENDING`.

It does not create:

`Position`.

Only an execution fill changes:

`PositionQuantity`.

---

# 85. Fill Event

A fill event updates:

`PositionState`.

Then:

`EntryPrice`

`Quantity`

`Risk`

`InitialStop`

are recalculated from actual execution.

---

# 86. Partial Fill

Each fill event updates:

`FilledQuantity`.

The average entry price becomes:

`Σ(FillPrice_i × FillQuantity_i) / ΣFillQuantity_i`.

The position state therefore evolves incrementally.

---

# 87. Cancel Event

Cancellation updates:

`PendingOrderQuantity`.

It does not change already-filled quantity.

This avoids accidentally deleting an existing position when an unfilled remainder is cancelled.

---

# 88. Session Close

At the defined operational cutoff:

new entries are disabled.

Existing positions must follow:

`ExitPolicy`.

The exact cutoff is an operational parameter.

The strategy cannot assume:

"market close automatically means zero risk"

until execution confirmation exists.

---

# 89. Data Integrity Override

At any event:

if:

`DataIntegrity = UNSAFE`

then:

`NewEntry = FALSE`.

Existing position management follows the emergency policy.

This is a safety layer above predictive logic.

---

# 90. State Snapshot

After every accepted event:

`Snapshot_t`

contains the complete relevant state.

Conceptually:

`Snapshot_t = {`

`EventID`

`Timestamp`

`MarketState`

`FeatureState`

`ProbabilityState`

`EvidenceState`

`DecisionState`

`PositionState`

`PortfolioState`

`ModelVersion`

`ParameterVersion`

`}`.

This is essential for forensic analysis.

---

# 91. Replay Property

Given:

`Snapshot_0`

and:

`E_1...E_n`.

The replay engine must reproduce:

`Snapshot_1...Snapshot_n`.

Therefore:

`Replay(E_1...E_n) = OriginalStateSequence`.

If not:

the state transformation specification or implementation is invalid.

---

# 92. Event Idempotency

For duplicate event:

`T(S, E_duplicate) = S`.

This is a formal idempotency requirement.

---

# 93. Event Ordering

For valid ordered events:

`E_1 < E_2 < ... < E_n`.

The state is:

`S_n = T(...T(T(S_0,E_1),E_2)...,E_n)`.

The ordering is part of the mathematics.

---

# 94. State Mutation Rule

Every state variable must declare:

`Owner`

`InputEvents`

`UpdateFunction`

`ResetCondition`

`Units`

`Precision`

`AllowedRange`.

This will become part of the canonical variable registry.

---

# 95. Variable Ownership

Examples:

`BestBid -> PriceState`

`Delta -> TradeFlowState`

`Spread -> LiquidityState`

`NetPnL -> PositionState`

`P_UP -> ProbabilityState`

`EvidenceScore -> EvidenceState`.

No variable may have two authoritative owners.

---

# 96. Derived Variable Rule

A derived variable must have exactly one canonical mathematical definition.

For example:

`NetPnL`

must not be independently calculated in:

`risk`

`execution`

and:

`position management`.

One module owns it.

Others consume it.

---

# 97. Units

Every numerical state variable must specify units.

Examples:

`Price -> INR`

`Quantity -> units/contracts`

`Volume -> units`

`Spread -> INR`

`Return -> dimensionless`

`Volatility -> dimensionless or normalized return units`

`Time -> milliseconds/seconds`

`Probability -> [0,1]`.

A dimensionless quantity must not silently be mixed with a price quantity.

---

# 98. Precision

The exact precision must ultimately follow:

`TrueData precision`

and:

`exchange instrument tick size`.

The mathematical model should not invent precision beyond the source data.

This remains:

`TBD`.

---

# 99. Missing-Value Semantics

Every variable must distinguish:

`VALID`

`MISSING`

`STALE`

`INVALID`

`NOT_APPLICABLE`.

These are not equivalent.

For example:

`IV = MISSING`

is different from:

`IV = 0`.

---

# 100. Final Transformation Contract

The complete mathematical contract is:

`E_t`

→ validate

→ update causal market state

→ update derived state

→ produce feature snapshot

→ produce probability state

→ produce evidence state

→ produce economic state

→ produce decision.

The incoming event itself never directly becomes:

`BUY_CE`.

It must pass through the entire causal chain.

---

# 101. Current Status

We have now defined:

`Event validation`

`Chronology`

`Session state`

`Price state`

`Volume state`

`Flow state`

`Order-book state`

`Volatility state`

`Liquidity state`

`Option state`

`Execution state`

`Position state`

`Feature construction`

`Probability boundary`

`Evidence boundary`

`Decision boundary`

`Replay requirements`

`Variable ownership`

`Missing-data semantics`.

---

# 102. What Remains Unresolved

These are intentionally not invented:

`TrueData exact event schema`

`TrueData exact timestamp semantics`

`TrueData sequence guarantees`

`TrueData tick/depth availability`

`TrueData option fields`

`TrueData historical tick availability`

`TrueData historical depth availability`

`TrueData retention period`

`TrueData aggregation semantics`

`Broker execution-event semantics`

`Exchange tick-size semantics`.

These become mandatory when we reach the actual data-source contract.

---

# 103. The Next Artifact

We have reached the point where another broad conceptual layer would become redundant.

The next artifact should therefore be the **Canonical Variable Registry v2 + Dependency Matrix**, now populated from this event-to-state contract.

For every variable we should establish:

`VariableID`

`CanonicalName`

`Owner`

`Definition`

`Formula`

`Unit`

`InputEvent`

`UpdateTrigger`

`UpdateFrequency`

`Lookback`

`ResetRule`

`MissingSemantics`

`AllowedRange`

`DownstreamConsumers`

`Learned/Derived/Observed`

`CausalStatus`

`TrueDataField = TBD`.

That registry will become the single authoritative mapping between the mathematical architecture and the eventual implementation.

After that, the next serious task is not another abstract strategy layer. It is to take the actual TrueData documentation you mentioned earlier and perform a **source-contract reconciliation**:

`OUR REQUIRED VARIABLE`

vs.

`ACTUAL TRUE DATA FIELD`

vs.

`AVAILABLE HISTORICALLY`

vs.

`AVAILABLE LIVE`

vs.

`PRECISION`

vs.

`UPDATE SEMANTICS`.

Any variable we cannot legitimately construct from the real feed will be marked explicitly rather than approximated silently.