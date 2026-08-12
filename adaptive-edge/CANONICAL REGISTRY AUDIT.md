# CANONICAL REGISTRY AUDIT
## Duplicate, Circular, Temporal-Leakage, and Observability Attack
### Version 1.0

## 1. Audit Objective

The registry is accepted only if every canonical variable satisfies:

`Unique`

`Causal`

`Observable or derivable`

`Dimensionally valid`

`Owned by exactly one state`

`Dependent only on registered parents`

`Computable at its declared timestamp`.

The audit therefore attempts to break the specification rather than confirm it.

---

# 2. Attack A — Duplicate Variable Audit

We compare every variable by semantic meaning rather than name.

The first important result is that the previous consolidation already eliminated the major duplicates:

`CurrentProfit`
and
`CurrentPnL`

collapse into:

`NET_PNL`.

`ExpectedHoldingTime`
and
`ExpectedHorizon`

collapse into:

`EXPECTED_HORIZON_DISTRIBUTION`.

`TrailingStop`
and
`DynamicStop`

collapse into:

`CURRENT_STOP`.

This is correct.

However, several additional potential overlaps require explicit separation.

---

# 3. P&L Duplication Attack

Potential variables:

`GROSS_PNL`

`NET_PNL`

`REALIZED_PNL`

`UNREALIZED_PNL`

These are not duplicates.

They describe different economic quantities.

Canonical interpretation:

`GROSS_PNL`

= price-derived P&L before costs.

`NET_PNL`

= current economic P&L after applicable costs.

`REALIZED_PNL`

= P&L from completed execution.

`UNREALIZED_PNL`

= mark-to-market component of an open position.

Therefore:

`NET_PNL = REALIZED + UNREALIZED - applicable costs`

where applicable components depend on the position lifecycle.

The critical rule is that:

`NET_PNL`

remains the canonical decision-facing P&L variable.

---

# 4. Risk Duplication Attack

Potential overlap:

`TRADE_RISK`

`EXPECTED_MAE`

`TAIL_LOSS`

`HARD_RISK_LIMIT`.

They are distinct.

`EXPECTED_MAE`

describes a statistical distribution.

`TAIL_LOSS`

describes an adverse tail quantity.

`TRADE_RISK`

describes the current position's risk.

`HARD_RISK_LIMIT`

is the maximum permissible risk.

Therefore:

`Distribution -> RiskEstimate -> Constraint`.

They must not be collapsed.

---

# 5. Volatility Duplication Attack

Potential overlap:

`REALIZED_VOLATILITY`

`VOLATILITY_STATE`

`VOLATILITY_SHOCK`.

They are distinct.

`REALIZED_VOLATILITY`

is the measured quantity.

`VOLATILITY_STATE`

is its location within a historical conditional distribution.

`VOLATILITY_SHOCK`

is an abnormal-change condition.

Therefore:

`Measurement != Regime != Shock`.

---

# 6. Flow Duplication Attack

Potential overlap:

`DELTA`

`FLOW_IMBALANCE`

`FLOW_RATE`

`FLOW_PERSISTENCE`.

These remain distinct.

For example:

`DELTA`

answers:

"How much net directional volume occurred?"

`FLOW_IMBALANCE`

answers:

"How dominant was directional flow relative to total classified flow?"

`FLOW_RATE`

answers:

"How quickly is flow arriving?"

`FLOW_PERSISTENCE`

answers:

"How consistently does directional flow persist?"

No merge required.

---

# 7. Price Duplication Attack

Potential overlap:

`LTP`

`MID_PRICE`

`MARK_PRICE`

`EXECUTION_PRICE`.

These must remain explicitly separated.

`LTP`

= latest transaction.

`MID_PRICE`

= quote-derived reference.

`MARK_PRICE`

= valuation convention.

`EXECUTION_PRICE`

= actual fill.

A major invariant follows:

`EXECUTION_PRICE != automatically LTP`.

And:

`MARK_PRICE != automatically MID`.

---

# 8. Stop Duplication Attack

Potential variables:

`INITIAL_STOP`

`CURRENT_STOP`

`PROFIT_PROTECTION_BOUNDARY`.

These are distinct.

`INITIAL_STOP`

is established after entry.

`CURRENT_STOP`

is the current executable protection boundary.

`PROFIT_PROTECTION_BOUNDARY`

is derived from accumulated profit and reversal/giveback risk.

The latter may influence:

`CURRENT_STOP`.

But it is not itself:

`CURRENT_STOP`.

Therefore:

`ProtectionModel -> CandidateStop -> CURRENT_STOP`.

---

# 9. Horizon Duplication Attack

Potential variables:

`EXPECTED_HORIZON_DISTRIBUTION`

`TRADE_MODE`

`TIME_IN_TRADE`.

These are distinct.

`EXPECTED_HORIZON_DISTRIBUTION`

is predictive.

`TRADE_MODE`

is a derived classification.

`TIME_IN_TRADE`

is observed from the actual position lifecycle.

Therefore the system cannot confuse:

"expected duration"

with:

"actual elapsed duration."

This distinction is now formally locked.

---

# 10. Probability Duplication Attack

Potential variables:

`P_UP_RAW`

`P_UP_ADJUSTED`

`P_UP_CONSERVATIVE`.

These are not three independent predictions.

The hierarchy is:

`P_UP_RAW`

→ evidence adjustment

→ conservative decision representation.

The registry should therefore classify:

`P_UP_RAW`

as the model output.

`P_UP_ADJUSTED`

as the evidence-adjusted output.

Any conservative probability used in decision-making must be explicitly derived from the probability distribution and uncertainty.

We must not allow three independently learned "UP probabilities."

That would create hidden model duplication.

---

# 11. Evidence Duplication Attack

Potential overlap:

`EVIDENCE_SCORE`

`MODEL_CONFIDENCE`

`DOMAIN_CONFIDENCE`.

These cannot remain ambiguous.

Canonical rule:

`EVIDENCE_SCORE`

is the single aggregate evidence variable.

`DOMAIN_CONFIDENCE`

is one component of evidence.

If we later use the term:

`MODEL_CONFIDENCE`

it must be a presentation alias or explicitly defined subcomponent.

It cannot become a second independent confidence system.

---

# 12. Decision Duplication Attack

Potential variables:

`TRADE_ELIGIBLE`

`DECISION_MARGIN`

`FINAL_DECISION`.

These are distinct.

`TRADE_ELIGIBLE`

answers:

"Can this candidate legally/economically proceed?"

`DECISION_MARGIN`

answers:

"How much better is the candidate than the alternative?"

`FINAL_DECISION`

answers:

"What action is actually selected?"

---

# 13. Result of Duplicate Audit

No fundamental duplication remains.

But three naming rules are now mandatory:

`One probability model`

`One evidence system`

`One decision utility`.

Any future variable introduced in these domains must be justified against those canonical quantities.

---

# 14. Attack B — Circular Dependency

We now attempt to create a cycle.

Potential cycle:

`Decision`

→ `Position`

→ `P&L`

→ `Feature`

→ `Probability`

→ `Decision`.

This appears circular.

But it is actually temporal.

The correct sequence is:

`Decision_t`

creates or modifies:

`Position_(t+)`.

That position produces future:

`P&L_(t+1...)`.

Those future outcomes may eventually become:

`LearningData`.

They do not modify:

`Feature_t`.

Therefore the apparent cycle is broken by time.

---

# 15. Temporal Feedback Rule

The legal feedback path is:

`Decision_t`

→ `Execution`

→ `Position_(t+)`

→ `Outcome_(future)`

→ `MaturedLabel`

→ `FutureModelTraining`

→ `ModelVersion_(future)`.

This is legal.

The illegal path is:

`Decision_t`

→ `Outcome_future`

→ `Probability_t`.

That is prohibited.

---

# 16. Learning Cycle

The system does contain a feedback loop:

`Model`

→ `Decision`

→ `Outcome`

→ `Learning`

→ `NewModel`.

This is intentional.

But it is not a same-timestamp dependency.

It is:

`ModelVersion_n`

→ outcomes

→ validation

→ `ModelVersion_(n+1)`.

Therefore it remains a temporal DAG.

---

# 17. Attack: Position Affecting Prediction

Suppose we are already long CE.

Can:

`POSITION_DIRECTION`

influence:

`P_UP`?

Answer:

Not as a market-prediction input.

Otherwise the model risks becoming self-referential.

The predictive model must estimate:

`P(MarketOutcome | MarketState)`.

Not:

`P(MarketOutcome | MarketState, MyDesiredPosition)`.

Position state can affect:

`Risk`

`Utility`

`Exit`.

It cannot arbitrarily alter the underlying market prediction.

---

# 18. Attack: Current P&L Affecting Probability

Can:

`NET_PNL`

change:

`P_UP`?

No.

It can change:

`Risk`

`ProfitProtection`

`ContinuationDecision`.

But the market prediction remains based on market state.

This is a major architectural invariant.

---

# 19. Attack: Stop Affecting Prediction

Can:

`CURRENT_STOP`

change:

`P_UP`?

No.

It changes:

`Risk`

and:

`Exit`.

This keeps prediction and position management separate.

---

# 20. Attack: Decision Affecting Feature

Can:

`BUY_CE`

change:

`FLOW_IMBALANCE`?

No.

The market may subsequently change because of external market activity, but the feature is reconstructed from observed market events.

The algorithm's own decision is not itself market-flow data.

---

# 21. Attack: Order Submission as Market Data

An internal order submission is not:

`BUY_AGGRESSOR_VOLUME`.

Only actual market execution events qualify as market observations.

This distinction is critical.

---

# 22. Attack: Our Own Fill as Market Flow

Even when our order fills:

our execution event can update:

`Position`

and:

`ExecutionState`.

It must not automatically be treated as evidence that the entire market experienced equivalent directional pressure.

Our own fill is not independent market information.

---

# 23. Circular Dependency Result

No prohibited circular dependency exists if these boundaries remain enforced:

`MarketState`

does not consume:

`DecisionState`.

`PredictionState`

does not consume:

`PositionState`.

`EvidenceState`

does not consume:

`FutureOutcome`.

`LearningState`

cannot modify an already active historical state.

---

# 24. Attack C — Temporal Leakage

This is the most dangerous audit.

We test every variable against:

"What information was actually known at timestamp t?"

---

# 25. Rolling Volatility Attack

Incorrect:

`VOLATILITY_t`

uses the entire trading day's returns.

Correct:

`VOLATILITY_t`

uses only:

`returns <= t`.

This is now an invariant.

---

# 26. VWAP Attack

Incorrect:

`VWAP_10:00`

uses total daily volume.

Correct:

`VWAP_10:00`

uses volume through:

`10:00`.

---

# 27. Session High Attack

Incorrect:

`SESSION_HIGH_10:00`

uses the day's eventual high.

Correct:

`SESSION_HIGH_10:00 = max(P_<=10:00)`.

---

# 28. Opening Range Attack

Before the opening-range interval finishes:

`OPENING_RANGE_COMPLETE = FALSE`.

The system must not know the eventual opening-range high or low.

This prevents a particularly easy backtest leak.

---

# 29. Label Attack

Suppose the prediction timestamp is:

`10:00`.

The outcome horizon ends:

`10:30`.

The label cannot become available at:

`10:00`.

It becomes eligible only after:

`10:30`

and after the defined outcome-maturity conditions are satisfied.

---

# 30. Overlapping Label Attack

Suppose labels are:

`10:00 -> 10:30`

and:

`10:05 -> 10:35`.

These observations overlap.

They cannot automatically be treated as independent samples.

The statistical evidence layer must account for the resulting dependence.

---

# 31. Normalization Attack

Incorrect:

`Z = (X_t - DailyMean) / DailyStd`

where DailyMean and DailyStd use future observations.

Correct:

the normalization parameters must be estimated from:

`information available before or at t`.

---

# 32. Quantile Attack

Suppose current volatility is compared against:

`historical volatility quantile`.

The reference distribution must contain only observations whose information would have been available at the decision timestamp.

No future regime observations may enter the current quantile.

---

# 33. Calibration Attack

Calibration must be performed on historical predictions whose outcomes have already matured.

Current unfinished predictions cannot participate.

---

# 34. Parameter Update Attack

Suppose a trade at:

`10:00`

loses at:

`10:45`.

The loss cannot update the parameter set used at:

`10:00`.

It may enter:

`future learning`.

Therefore:

`ParameterVersion_t`

is immutable during its declared validity interval.

---

# 35. Model Promotion Attack

A model that performs extremely well on today's data cannot become the active model halfway through today's session merely because today's outcome looks favorable.

Promotion requires:

`defined evaluation window`

`validation`

`promotion rule`.

This protects against adaptive hindsight.

---

# 36. Execution-Latency Attack

Suppose:

`ExchangeTime = 10:00:00`

but:

`ReceiveTime = 10:00:01`.

The system cannot reconstruct a decision at:

`10:00:00`

using information that was only received at:

`10:00:01`.

For live decision-making:

`AvailableInformationTime`

is constrained by actual receipt.

For historical market-state reconstruction:

`ExchangeTime`

defines market chronology.

These two concepts must not be conflated.

---

# 37. Historical Replay Rule

There are therefore two clocks:

`MARKET_CLOCK`

and:

`SYSTEM_CLOCK`.

Market state:

`MarketState_t`

uses market chronology.

Decision availability:

`DecisionAvailable_t`

must respect system receipt chronology.

This distinction is essential for realistic backtesting.

---

# 38. Attack D — Unobservable Variable

Now we ask:

"Can every required variable actually be constructed from the eventual source data?"

Several variables are currently dependent on external contracts.

The following are therefore:

`SOURCE-DEPENDENT`.

---

# 39. Aggressor Classification

`BUY_AGGRESSOR_VOLUME`

and:

`SELL_AGGRESSOR_VOLUME`

require sufficient trade/quote information or an accepted classification method.

If the feed cannot support defensible classification:

the variables cannot be silently fabricated.

They become:

`UNAVAILABLE`.

---

# 40. Order-Book Imbalance

`ORDER_BOOK_IMBALANCE`

requires actual depth information.

If only top-of-book data exists:

we cannot claim to have:

`full-depth imbalance`.

We must use only what is actually observable.

---

# 41. Fill Probability

`FILL_PROBABILITY`

is not directly observable from market data.

It must be learned from:

`historical order/execution observations`.

If execution history is unavailable:

the variable has insufficient evidence.

---

# 42. Slippage Distribution

Similarly:

`EXECUTION_COST_DISTRIBUTION`

requires historical execution observations or a defensible external execution model.

It cannot be inferred purely from:

`LTP`.

---

# 43. Option IV

If TrueData supplies IV directly:

use the supplied field after semantic validation.

If not:

we may derive IV from option price and a pricing model.

But then:

`IV`

is a derived model quantity, not observed data.

The distinction must remain explicit.

---

# 44. Greeks

Greeks may be:

`source-provided`

or:

`model-derived`.

They cannot be treated as ground truth simply because they appear as broker/data-provider fields.

Their calculation methodology must eventually be documented.

---

# 45. Historical Depth

The strategy requires historical depth only if a validated feature actually uses it.

If the API provides:

`live depth`

but not:

`historical depth`

then historical training for depth-based features is impossible without another source.

That feature must then remain:

`TBD / unavailable for historical learning`.

---

# 46. Tick-Level Historical Availability

The architecture requires tick-level information for the most granular strategy.

But:

`live tick availability`

does not imply:

`five-year historical tick availability`.

These are separate source-contract questions.

---

# 47. Important Architectural Consequence

We do NOT delete a mathematically useful variable merely because its source is currently unknown.

Instead:

`Required`

→ `Source TBD`

→ `Validate availability`

→ `Implement only if reconstructible`.

This preserves architectural completeness without pretending that data exists.

---

# 48. Unobservable-Variable Rule

If a variable is required for a decision and cannot be reliably reconstructed:

`Decision = NO_TRADE`

for any strategy state requiring that variable.

There is no silent substitution.

---

# 49. Attack: Proxy Contamination

Suppose exact order-flow data is unavailable.

We might be tempted to substitute:

`price movement`

for:

`aggressive flow`.

That is prohibited unless the substitute is explicitly defined as a different variable and independently validated.

A proxy is not the original measurement.

---

# 50. Attack: Broker-Derived Feature

A broker UI indicator must not be treated as:

`raw market truth`

unless its exact construction and timestamp semantics are known.

Our system should preferably derive required features from raw source information.

---

# 51. Attack: Double Counting

Suppose:

`PRICE_VELOCITY`

and:

`MOMENTUM_INDICATOR`

both derive almost entirely from the same price history.

We cannot treat them as independent confirmation.

The feature-dependence audit must identify this.

---

# 52. Attack: Derived-on-Derived Leakage

Suppose:

`Feature A`

already contains future information accidentally.

Then:

`Feature B = f(Feature A)`

inherits the leak.

Therefore auditing only raw variables is insufficient.

Causality must be verified recursively through the entire dependency graph.

---

# 53. Recursive Causality Rule

For every variable:

`Causal(X) = TRUE`

only if:

`Causal(all Parents(X)) = TRUE`

and:

`UpdateTime(X) >= max(UpdateTime(Parents))`

and:

`No future information enters the transformation`.

This gives us a formal recursive causality test.

---

# 54. Dimension Audit

We also attack dimensional consistency.

Example:

`Price / Time`

produces:

`price velocity`.

Valid.

But:

`Price + Probability`

is dimensionally meaningless.

Any formula combining incompatible dimensions is:

`SPECIFICATION_ERROR`.

---

# 55. Probability Constraint

The probability vector must satisfy:

`0 <= P_i <= 1`.

And:

`ΣP_i = 1`.

If not:

`ProbabilityState = INVALID`.

---

# 56. Imbalance Constraint

For:

`FI`

and:

`OBI`:

`-1 <= value <= +1`.

Violation indicates:

`STATE_ERROR`.

---

# 57. Quantity Constraint

For every position:

`FilledQuantity >= 0`.

And:

`FilledQuantity <= RequestedQuantity`

for the same order lifecycle.

---

# 58. Stop Constraint

For a long premium position where the stop is expressed in option-price space:

`CURRENT_STOP_(t+1) >= CURRENT_STOP_t`.

The exact inequality must be transformed appropriately if the protection variable is instead represented in underlying-risk space.

The invariant is economic:

`Protection cannot intentionally become less protective without an explicit, validated risk transition`.

---

# 59. Profit Constraint

`PEAK_NET_PNL_(t+1) >= PEAK_NET_PNL_t`.

Therefore peak profit can only remain constant or increase.

---

# 60. Position-P&L Consistency

At every event:

`NET_PNL`

must be reconstructible from:

`ActualEntry`

`ActualExit/current mark`

`Quantity`

`Costs`.

If not:

`P&L_STATE_INVALID`.

---

# 61. Audit Result

The registry survives the four major attacks conceptually.

But the audit exposed several **source-contract blockers**:

`Aggressor classification`

`Historical depth`

`Historical tick availability`

`Execution history`

`Fill probability`

`Slippage distribution`

`IV provenance`

`Greek provenance`

`TrueData timestamp semantics`.

These are not architecture failures.

They are data-contract questions.

---

# 62. More Important Finding

We also discovered one architectural refinement.

The system needs two distinct notions of time:

`MARKET_TIME`

and:

`INFORMATION_TIME`.

Market time answers:

"When did this market event occur?"

Information time answers:

"When could our system legitimately know about it?"

This distinction must become a canonical part of the registry.

---

# 63. New Canonical Variables

Add:

`TMP-001 MARKET_TIMESTAMP`

The event's market/exchange timestamp.

And:

`TMP-002 INFORMATION_TIMESTAMP`

The timestamp at which the system can legitimately consume the event.

Then:

`TMP-003 OBSERVATION_LATENCY`

`= INFORMATION_TIMESTAMP - MARKET_TIMESTAMP`.

These are now first-class temporal variables.

---

# 64. Decision Timestamp

For a decision:

`DECISION_TIMESTAMP`

is the actual system timestamp at which the decision becomes executable.

This prevents historical simulation from assuming:

"we saw the event exactly when the exchange generated it."

---

# 65. New Temporal Causality Rule

For a live decision at:

`InformationTime = τ`

the decision may consume only events satisfying:

`InformationTimestamp <= τ`.

Even if an event's:

`MarketTimestamp < τ`.

If the event had not yet arrived, it was not available.

This is the correct live causality rule.

---

# 66. Historical Backtest Rule

A realistic backtest therefore needs to replay:

`MarketTimestamp`

and:

`InformationTimestamp`.

It must not simply process the market tape in exchange-time order and assume zero latency.

That would systematically overstate the edge of very short-duration trades.

---

# 67. Final Canonical Causal Chain

The architecture is now:

```text id="3i1c2v"
MARKET EVENT
    |
    v
MARKET TIME
    |
    v
INFORMATION ARRIVAL
    |
    v
DATA VALIDATION
    |
    v
CAUSAL STATE
    |
    v
FEATURE SNAPSHOT
    |
    v
PREDICTION
    |
    v
EVIDENCE
    |
    v
ECONOMICS
    |
    v
PORTFOLIO RISK
    |
    v
DECISION
    |
    v
ORDER
    |
    v
ACTUAL EXECUTION
    |
    v
POSITION
    |
    v
OUTCOME
    |
    v
MATURED LABEL
    |
    v
FUTURE MODEL VERSION
```

This is now the canonical temporal architecture.

---

# 68. Audit Verdict

`DUPLICATION: PASS`

`CIRCULAR DEPENDENCY: PASS`

`TEMPORAL CAUSALITY: PASS`

`DIMENSIONAL CONSISTENCY: PASS`

`STATE OWNERSHIP: PASS`

`REPLAYABILITY: PASS`

`OBSERVABILITY: CONDITIONAL`

The architecture itself is no longer the blocker.

The remaining uncertainty is concentrated at the actual data and execution boundary.

---

# 69. Next Artifact

The next artifact should therefore **not** be another abstract strategy layer.

It should be:

# TRUE DATA SOURCE-CONTRACT RECONCILIATION

We take every:

`OBSERVED`

variable in the registry and map it against the actual API documentation.

For each variable:

`Canonical Variable`

`Exact API Field`

`Endpoint`

`Live/Historical`

`Tick/Quote/Depth/Option`

`Timestamp Semantics`

`Precision`

`Update Frequency`

`Historical Retention`

`Entitlement`

`Missing-Data Semantics`

`Can Reconstruct?`

`Confidence`.

Anything that cannot be proven from the documentation goes into:

`SOURCE TODO`.

Only after that reconciliation should we finalize the implementation-level data contract.

That is the correct boundary between mathematical architecture and actual software.