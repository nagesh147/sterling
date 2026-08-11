# CANONICAL PERFORMANCE, RISK, AND ATTRIBUTION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how the strategy's performance is measured, decomposed, validated, and ultimately judged.

The system must answer six different questions:

```text
1. Was the prediction correct?
2. Did the prediction create economic value?
3. Did execution preserve that value?
4. Was the risk taken reasonable?
5. Is the observed performance statistically credible?
6. Does the result survive unseen and adversarial conditions?
```

These questions must not be collapsed into a single P&L number.

---

# 2. Primary Principle

The system must never define success as:

```text
BacktestProfit > 0
```

Nor:

```text
Return > Benchmark
```

Nor:

```text
WinRate > 50%
```

A strategy is considered potentially valid only when multiple independent dimensions of evidence agree.

---

# 3. Performance Layers

Performance is separated into:

```text
PREDICTION PERFORMANCE
        |
        v
TRADE ECONOMICS
        |
        v
EXECUTION PERFORMANCE
        |
        v
PORTFOLIO/RISK PERFORMANCE
        |
        v
STATISTICAL VALIDITY
        |
        v
ROBUSTNESS
```

Each layer has its own measurements.

---

# 4. Prediction Performance

Prediction quality asks:

```text
Did the statistical model correctly estimate future directional behavior?
```

It does not ask whether the resulting trade made money.

Possible quantities include:

```text directional accuracy
probability calibration
Brier-type scoring
log-loss-type scoring
precision by probability bucket
recall by opportunity class
conditional outcome distributions
```

The exact metric set will be finalized after the label specification is frozen.

---

# 5. Probability Calibration

If the model says:

```text P(up) = 0.70
```

then across a sufficiently large population of comparable predictions, approximately:

```text 70%
```

should produce the defined positive outcome.

If predictions labeled:

```text 0.70
```

actually succeed only:

```text 54%
```

the probability is poorly calibrated.

This is different from whether the strategy made money.

---

# 6. Calibration Curve

Predictions can be grouped into probability ranges:

```text 0.50 - 0.55
0.55 - 0.60
0.60 - 0.65
...
0.90 - 0.95
```

For each group:

```text predicted probability
vs.
observed frequency
```

are compared.

The ideal relationship is approximately:

```text observed ≈ predicted.
```

---

# 7. Prediction Discrimination

Calibration asks:

```text "Are probabilities numerically trustworthy?"
```

Discrimination asks:

```text "Can the model distinguish better opportunities from worse opportunities?"
```

A model can have acceptable calibration while having weak discrimination.

Both properties matter.

---

# 8. Economic Performance

A correct directional prediction does not automatically produce a profitable option trade.

Therefore:

```text Prediction
    ↓
Option translation
    ↓
Execution
    ↓
Costs
    ↓
Net P&L
```

must be separately measured.

---

# 9. Gross Versus Net P&L

Every trade retains:

```text GrossPnL
ExecutionCost
TransactionCost
Slippage
NetPnL
```

where conceptually:

```text NetPnL
=
GrossPnL
-
AllApplicableCosts
```

The exact cost taxonomy remains subject to the execution/accounting contract.

---

# 10. Trade Expectancy

A basic economic quantity is:

```text E[PnL] id="wq9m1d"
```

estimated from the realized trade distribution.

But average P&L alone is insufficient.

A strategy could have:

```text positive mean
+
catastrophic tail risk.
```

Therefore the distribution must be examined.

---

# 11. Outcome Distribution

The system must retain the complete distribution of:

```text NetPnL
MFE
MAE
HoldingTime
ProfitGiveback
Slippage
```

not merely their averages.

The tails matter.

---

# 12. Win Rate

Win rate is:

```text WinningTrades / TotalClosedTrades
```

It is diagnostic.

It is not an objective function.

A strategy with:

```text 40% winners
```

can be superior to one with:

```text 70% winners
```

if the payoff distributions differ sufficiently.

---

# 13. Average Win and Average Loss

The system records:

```text AverageWin
AverageLoss
```

and their distributions.

A basic payoff relationship is:

```text PayoffRatio
=
AverageWin / |AverageLoss|
```

This is useful diagnostically but should not be optimized in isolation.

---

# 14. Expectancy Decomposition

Trade expectancy can conceptually be expressed as:

```text E[PnL]
=
P(win) × E(win)
+
P(loss) × E(loss)
```

with:

```text E(loss) < 0.
```

The actual system uses the full empirical distribution rather than assuming only two outcomes.

---

# 15. Maximum Drawdown

The equity curve is:

```text Equity_t
=
InitialCapital
+
CumulativeRealizedPnL_t.
```

Maximum drawdown is derived from the largest decline from a historical equity peak.

Conceptually:

```text Drawdown_t
=
PeakEquity_t - Equity_t.
```

The maximum observed value is:

```text MaximumDrawdown.
```

---

# 16. Drawdown Is Not Just a Statistic

Drawdown determines whether the strategy is operationally survivable.

A strategy that produces:

```text +100% return
```

but requires:

```text -80% drawdown
```

may be unacceptable regardless of its final return.

---

# 17. Intratrade Drawdown

Portfolio drawdown and trade-level adverse excursion are different.

The system separately records:

```text TradeMAE
PortfolioDrawdown
```

A trade can have severe adverse movement without producing a large portfolio drawdown if position sizing is small.

---

# 18. Maximum Adverse Excursion

For each trade:

```text MAE
```

measures the worst adverse movement experienced before closure.

This becomes useful for:

```text protection calibration
risk validation
stress analysis
```

---

# 19. Maximum Favorable Excursion

For each trade:

```text MFE
```

measures the maximum favorable movement available during the trade.

MFE helps answer:

```text Did the strategy exit too early?
```

and:

```text Was continuation actually available?
```

It must not be confused with realized profit.

---

# 20. Profit Capture

A useful diagnostic is the relationship between:

```text RealizedProfit
```

and:

```text MFE.
```

Conceptually:

```text ProfitCapture
=
RealizedProfit / MFE
```

where meaningful and properly normalized.

This measures how much of the available favorable excursion was actually captured.

It is diagnostic, not an optimization target by itself.

---

# 21. Giveback

The system retains:

```text PeakPnL
CurrentPnL
ProfitGiveback
```

throughout the trade.

This allows us to determine whether the dynamic management system is protecting accumulated gains or repeatedly surrendering them.

---

# 22. Holding-Time Distribution

The system must measure:

```text ExpectedHorizon
ActualHoldingTime
```

separately.

We previously identified this distinction as important.

Expected horizon is a prediction.

Actual holding time is an outcome.

They must never share one variable.

---

# 23. Time-to-Outcome

For each prediction, the system may measure:

```text TimeToTarget
TimeToFailure
TimeToMaximumFavorableExcursion
TimeToMaximumAdverseExcursion
```

These help validate the temporal assumptions underlying MICRO, SCALP, and INTRADAY modes.

---

# 24. Mode Attribution

Performance must be segmented by:

```text MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

if those modes survive the final architecture.

We need to know whether a mode is actually adding value.

---

# 25. Mode Transition Attribution

For every transition:

```text SCALP -> INTRADAY
```

we should eventually evaluate:

```text What happened after transition?
```

and compare against:

```text What would have happened without the transition?
```

The latter is counterfactual analysis.

It must not be confused with actual historical behavior.

---

# 26. Dynamic Risk Attribution

We explicitly separate:

```text DynamicMode
```

from:

```text DynamicRisk.
```

This means a mode transition can change:

```text expected horizon
continuation interpretation
```

without automatically changing:

```text previously established protection.
```

Performance reports must verify this invariant.

---

# 27. Entry Attribution

Each trade's entry can be evaluated independently.

Questions include:

```text Was the directional probability well calibrated?
Was expected value positive?
Was the selected option economically suitable?
Was execution feasible?
```

This determines whether poor results originated at entry.

---

# 28. Management Attribution

A trade may have had a good entry but poor management.

Therefore:

```text EntryValue
```

and:

```text ManagementValue
```

must be separated conceptually.

---

# 29. Exit Attribution

For each exit:

```text ExitReason
```

is recorded.

Results can then be grouped by:

```text HARD_RISK
EMERGENCY_REVERSAL
NORMAL_EXIT
SESSION_CLOSE
EXECUTION_FAILURE
```

This tells us which mechanisms actually determine realized outcomes.

---

# 30. Execution Attribution

P&L must also be decomposed by execution quality.

For example:

```text TheoreticalExitValue
-
ActualExitValue
=
ExecutionImpact
```

subject to the final marking convention.

This allows us to determine whether the strategy's theoretical edge is being destroyed by execution.

---

# 31. Cost Attribution

Total costs must be decomposed where the data supports it:

```text spread cost
brokerage
exchange charges
taxes/fees
slippage
other execution costs
```

The exact categories depend on the actual trading environment.

---

# 32. Directional Attribution

Because the system buys only directional options, we need to distinguish:

```text UnderlyingPredictionOutcome
```

from:

```text OptionTradeOutcome.
```

A correct NIFTY directional prediction can still produce a losing CE trade because of:

```text option premium behavior
theta
volatility changes
spread
execution
```

Therefore:

```text directional correctness != trade profitability.
```

---

# 33. Option Translation Attribution

The system should eventually quantify:

```text UnderlyingMove
        ↓
OptionResponse
```

and determine whether the chosen option captured the predicted movement efficiently.

This becomes part of option-selection validation.

---

# 34. Opportunity-Level Attribution

Every eligible opportunity should have:

```text OpportunityID
```

regardless of whether a trade was executed.

This allows comparison:

```text ALL OPPORTUNITIES
        |
        +--> TRADED
        |
        +--> REJECTED
```

Without this, we cannot determine whether the entry filter is actually useful.

---

# 35. Rejected Opportunity Analysis

For a rejected opportunity:

```text NO_TRADE
```

the system records the primary rejection reason:

```text insufficient probability
insufficient EV
poor option
poor liquidity
excessive cost
insufficient evidence
risk restriction
data-quality restriction
```

This allows us to evaluate whether the filters are genuinely eliminating poor opportunities.

---

# 36. Selection Bias Test

If:

```text traded opportunities
```

perform well but:

```text rejected opportunities
```

also perform equally well, the entry filter may be doing little useful work.

Conversely, if rejected opportunities consistently have worse forward outcomes, the filter has evidence of discriminative value.

---

# 37. Counterfactual Benchmark

For every trade:

```text ActualStrategyOutcome
```

can be compared with defined counterfactuals.

Examples:

```text no dynamic management
fixed protection
alternative mode policy
alternative option
```

These comparisons are research tools.

They do not alter actual historical results.

---

# 38. Benchmark Hierarchy

The strategy should eventually be compared against:

```text random-entry baseline
simple directional baseline
fixed-rule ORB baseline
buy-and-hold/reference baseline where appropriate
simplified version of our own strategy
```

The purpose is not to prove superiority through arbitrary benchmarks.

The purpose is to establish whether complexity actually contributes value.

---

# 39. Complexity Premium

Suppose:

```text SimpleStrategy = +X
ComplexStrategy = +X + ε
```

but the complex strategy requires:

```text many parameters
many states
many data dependencies
high execution sensitivity
```

then the additional complexity may not be justified.

We should demand evidence that each major architectural component earns its complexity.

---

# 40. Ablation Testing

The system should eventually test:

```text FullStrategy
```

against variants with individual components removed.

For example:

```text without dynamic mode
without dynamic risk adaptation
without option filter
without continuation model
without execution filter
without probability calibration
```

If removing a component produces essentially identical performance, that component may not be contributing meaningful edge.

---

# 41. Statistical Significance

Observed profitability does not prove a genuine edge.

We need to ask:

```text How likely is this result under a suitable null hypothesis?
```

The exact statistical methodology will depend on:

```text dependence structure
overlapping observations
trade frequency
autocorrelation
multiple testing
```

A naive IID significance test is not automatically valid.

---

# 42. Dependence

High-frequency observations are strongly dependent.

Therefore:

```text number_of_ticks
```

cannot be treated as:

```text independent_sample_size.
```

Likewise, overlapping opportunity labels can create dependence.

The effective sample size must be considered.

---

# 43. Bootstrap

A suitable resampling procedure may eventually be used to estimate uncertainty in:

```text mean return
drawdown
expectancy
risk metrics
```

But the resampling scheme must respect temporal dependence.

Randomly shuffling individual ticks would generally destroy the structure we are trying to evaluate.

---

# 44. Block-Based Resampling

Where appropriate, historical observations may be resampled in blocks to preserve some temporal dependence.

The block definition must be chosen independently of the final test result.

This is a validation methodology decision.

---

# 45. Confidence Intervals

Performance metrics should eventually be accompanied by uncertainty estimates.

For example:

```text ExpectedNetPnL
+
confidence interval
```

rather than:

```text ExpectedNetPnL = exact truth.
```

---

# 46. Probability of Ruin

Because this is a leveraged options strategy, we must evaluate whether the combination of:

```text position sizing
loss distribution
capital
drawdown
```

creates an unacceptable probability of capital impairment.

This is a risk constraint, not a return optimization.

---

# 47. Risk of Catastrophic Loss

The system must specifically stress:

```text sudden underlying move
option spread expansion
liquidity collapse
gap
execution delay
stop slippage
multiple consecutive losses
```

The objective is to determine whether the strategy can remain solvent under plausible adverse conditions.

---

# 48. Loss Clustering

Losses may cluster.

Therefore:

```text consecutive losses
```

must be analyzed.

We should not assume that historical average loss frequency is independent from one trade to the next.

---

# 49. Drawdown Duration

Two strategies can have the same maximum drawdown but radically different recovery behavior.

Therefore measure:

```text MaximumDrawdown
DrawdownDuration
RecoveryTime
```

These are operationally distinct.

---

# 50. Equity Curve Stability

The system should examine performance across chronological segments:

```text month
quarter
year
market regime
time of day
volatility state
```

The objective is not to demand that every segment be profitable.

The objective is to determine whether profitability depends entirely on one narrow historical episode.

---

# 51. Regime Robustness

Performance must eventually be segmented across conditions such as:

```text low volatility
normal volatility
high volatility

strong trend
weak trend
reversal

opening expansion
compressed session
late-session movement
```

Only regimes defined without future information may be used.

---

# 52. Time-of-Day Attribution

Because our strategy explicitly cares about exchange timing, performance should be analyzed by:

```text opening period
early session
mid-session
late session
closing period
```

Exact time buckets remain to be validated.

The purpose is to discover whether the edge is genuinely temporal.

---

# 53. Day-of-Week Analysis

Day-of-week behavior can be analyzed.

But we must be careful.

If a pattern appears only because:

```text one unusual historical event
```

occurred on a particular weekday, it should not automatically become a trading rule.

This remains diagnostic unless validated.

---

# 54. Monthly and Yearly Stability

The system should produce chronological performance reports.

For each period:

```text Trades
NetPnL
Expectancy
Drawdown
WinRate
MFE
MAE
Costs
Execution quality
```

This allows us to see whether the strategy's behavior is stable.

---

# 55. Rolling Performance

A rolling window can show whether the strategy's edge is deteriorating.

For example:

```text rolling expectancy
rolling calibration error
rolling drawdown
rolling execution cost
```

These are monitoring variables.

They must not automatically trigger parameter changes unless such adaptation has been explicitly validated.

---

# 56. Performance Degradation

We distinguish:

```text random short-term variation
```

from:

```text statistically credible degradation.
```

The latter may justify retraining or suspension only according to predefined rules.

---

# 57. Production Monitoring

The eventual live system should monitor:

```text prediction calibration
execution quality
slippage
trade expectancy
drawdown
data quality
model stability
parameter stability
```

But monitoring is not automatically adaptation.

This preserves the separation:

```text OBSERVE
vs.
ACT.
```

---

# 58. Dynamic Risk Constraint

A critical invariant from our earlier adversarial analysis remains:

```text New information may tighten risk.
It cannot relax previously established protection merely because the inferred mode changed.
```

Performance reporting must verify that this never happened.

---

# 59. Risk Budget

Position sizing is governed by:

```text RiskBudget_t.
```

The system must distinguish:

```text available capital
```

from:

```text permitted strategy risk.
```

A large account balance does not imply unlimited risk capacity.

---

# 60. Risk Utilization

For each trade:

```text RiskUtilization
=
CapitalAtRisk / PermittedRiskBudget.
```

This allows us to evaluate whether the position-sizing system is actually respecting its intended constraints.

---

# 61. Exposure Concentration

Because the initial architecture targets directional option buying, exposure can concentrate rapidly.

The system must eventually monitor:

```text simultaneous exposure
directional concentration
instrument concentration
expiry concentration
```

The exact portfolio constraints will be defined if the architecture expands beyond one position.

---

# 62. Current Baseline

For the first implementation, the cleanest baseline remains:

```text one active directional trade at a time
```

unless the earlier specification explicitly authorizes multiple simultaneous positions.

If multiple positions are eventually allowed, portfolio-level risk becomes an additional state layer.

---

# 63. Return Normalization

Raw rupee profit is insufficient for comparison across periods.

Performance should also be expressed relative to:

```text capital
risk budget
maximum drawdown
```

depending on the metric.

This prevents a strategy from appearing better merely because more capital was deployed.

---

# 64. Risk-Adjusted Performance

Possible diagnostic metrics include:

```text return / volatility
return / drawdown
return / risk unit
```

More sophisticated ratios may be considered later.

No single ratio should become the optimization target.

---

# 65. Tail Metrics

The system must explicitly inspect:

```text worst trade
worst day
worst session
worst sequence
left-tail P&L quantiles
maximum adverse excursion
```

The average hides tail behavior.

---

# 66. Profit Concentration

A dangerous strategy may derive most of its total return from:

```text one or two exceptional trades.
```

Therefore calculate:

```text contribution of top trades
contribution of top days
contribution of top months
```

If almost all profits come from a tiny number of observations, robustness is questionable.

---

# 67. Loss Concentration

The same applies to losses.

Determine whether:

```text one rare event
```

dominates total downside.

If so, the strategy's risk model must explicitly account for it.

---

# 68. Parameter Stability

Performance must be measured around the selected parameter values.

If tiny parameter changes cause massive performance changes:

```text parameter fragility.
```

A fragile strategy receives lower confidence even if the selected parameter happens to perform extremely well.

---

# 69. Regime Stability

Likewise, if performance disappears when:

```text volatility
```

changes slightly, the strategy may be regime-dependent.

Regime dependence is not automatically bad.

Unrecognized regime dependence is bad.

---

# 70. Execution Stability

The strategy should be tested under:

```text observed execution
+
reasonable adverse execution stress.
```

If profitability disappears immediately under modest slippage deterioration, the strategy may not have sufficient execution margin.

---

# 71. Cost Margin

Define conceptually:

```text CostMargin
=
GrossEdge - ActualExecutionCost.
```

A healthy strategy should possess meaningful economic margin rather than:

```text gross profit = 100
cost = 99.
```

Such an edge is extremely fragile.

---

# 72. Stress Matrix

The final validation system should eventually run combinations of:

```text prediction degradation
+
slippage increase
+
spread widening
+
latency
+
lower fill probability
+
higher transaction cost
+
regime shift.
```

This is substantially more informative than one idealized backtest.

---

# 73. Adversarial Validation

The strategy must be attacked under:

```text high volatility
low volatility
rapid reversal
false breakout
gap
trend continuation
range compression
liquidity deterioration
execution delay
data gaps
```

The objective is not to make every scenario profitable.

The objective is to verify:

```text no impossible state
no hidden future information
no uncontrolled risk expansion
no catastrophic execution assumption.
```

---

# 74. Edge Classification

At the end of research, the strategy should be classified as one of:

```text NO_EVIDENCE
```

```text PROMISING_BUT_UNPROVEN
```

```text OUT_OF_SAMPLE_EDGE
```

```text ROBUST_EDGE
```

```text PRODUCTION_READY
```

The last category requires more than profitability.

---

# 75. Production-Ready Requirements

Conceptually:

```text Valid data pipeline
+
correct state machine
+
validated execution model
+
out-of-sample edge
+
acceptable drawdown
+
stable parameters
+
execution robustness
+
statistical credibility
+
adversarial survival
+
complete auditability.
```

Failure of a critical component means:

```text NOT_PRODUCTION_READY.
```

---

# 76. Attribution Tree

The complete performance attribution becomes:

```text TOTAL NET P&L
        |
        +-- Directional Prediction
        |
        +-- Option Translation
        |
        +-- Entry Timing
        |
        +-- Dynamic Management
        |
        +-- Exit Timing
        |
        +-- Execution
        |
        +-- Costs
        |
        +-- Risk/Sizing
```

Each component is analyzed separately.

---

# 77. Why This Matters

Suppose the final strategy earns:

```text +₹500,000.
```

That number alone tells us almost nothing.

We need to know whether:

```text prediction created +₹800,000
execution destroyed -₹100,000
costs destroyed -₹100,000
poor management destroyed -₹100,000
```

or whether:

```text prediction contributed almost nothing
one lucky trade created nearly all the profit.
```

The attribution system reveals the difference.

---

# 78. Final Performance Decision

The final question is not:

```text "Did the backtest make money?"
```

It is:

```text "Does the complete causal system demonstrate a statistically credible,
economically meaningful, execution-survivable, risk-controlled,
out-of-sample advantage that remains stable under reasonable adversarial conditions?"
```

Only a positive answer justifies progression toward paper trading.

---

# 79. Canonical Performance Invariants

```text PERF-001 id="o0h0pk"
Prediction quality and profitability are measured separately.

PERF-002
Gross and net P&L are separate.

PERF-003
Theoretical and executed P&L are separate.

PERF-004
Trade outcomes and opportunity outcomes are separate.

PERF-005
Realized P&L derives from actual execution.

PERF-006
Risk metrics cannot be replaced by return metrics.

PERF-007
Maximum drawdown is measured independently of total return.

PERF-008
Parameter selection cannot use final-test performance.

PERF-009
Execution assumptions must be explicitly classified.

PERF-010
High-frequency observations are not automatically treated as independent samples.

PERF-011
Counterfactual results never replace actual historical results.

PERF-012
A profitable backtest alone does not establish an edge.

PERF-013
Dynamic mode changes cannot retroactively weaken established protection.

PERF-014
A strategy must survive predefined robustness and adversarial tests before production classification.
```

---

# 80. Architecture Status

We now have the complete conceptual chain:

```text
TRUE DATA
   ↓
CANONICAL EVENT
   ↓
STATE
   ↓
FEATURES
   ↓
PROBABILITY
   ↓
ECONOMIC VALUE
   ↓
ENTRY
   ↓
EXECUTION
   ↓
ACTIVE TRADE
   ↓
DYNAMIC MANAGEMENT
   ↓
EXIT
   ↓
REALIZED OUTCOME
   ↓
LABEL
   ↓
LEARNING
   ↓
WALK-FORWARD CALIBRATION
   ↓
PERFORMANCE VALIDATION
   ↓
ROBUSTNESS
```

This is substantially different from a conventional backtest. We have defined a **causal, event-driven, learnable trading system** rather than merely a collection of indicators and entry/exit rules.

---

# 81. Remaining External TODOs

The major unresolved external facts remain:

```text TrueData exact field mappings
TrueData timestamp semantics
TrueData historical coverage
TrueData tick/quote sequencing
TrueData option-data coverage
TrueData depth availability
Broker execution semantics
Actual transaction-cost schedule
Actual fill/cancellation semantics
```

These remain outside the mathematical architecture until the authoritative documentation is supplied.

---

# 82. Next Artifact

The next logical artifact is now:

# CANONICAL RESEARCH EXPERIMENT AND VALIDATION PROTOCOL

That specification will define exactly **how we are allowed to experiment on this architecture without corrupting it**.

It will cover:

```text experiment IDs
dataset versioning
feature-version control
parameter-version control
train/validation/test chronology
walk-forward experiment execution
multiple-testing accounting
ablation experiments
baseline experiments
stress experiments
adversarial experiments
statistical tests
accept/reject criteria
final holdout protection
experiment reproducibility
```

This is the layer that prevents us, as researchers, from accidentally cheating while trying to improve the strategy.

And that is particularly important now: **the mathematical architecture is becoming complex enough that our research process itself can become a source of overfitting.**