# CANONICAL P&L, ACCOUNTING, AND PERFORMANCE ATTRIBUTION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how the system calculates and attributes financial outcomes from actual executions.

The accounting chain is:

```text
Market Events
    ↓
Orders
    ↓
Fills
    ↓
Position Ledger
    ↓
Gross P&L
    ↓
Execution Costs
    ↓
Net P&L
    ↓
Trade Performance
    ↓
Strategy Performance
```

The accounting system is downstream of trading decisions.

It must never become an upstream input to the historical decision being evaluated.

---

# 2. Fundamental Accounting Principle

The authoritative financial result comes from:

```text
actual fills
+
canonical accounting rules.
```

It does not come from:

```text chart movement
last traded price
model prediction
hypothetical entry price
hypothetical exit price.
```

---

# 3. Three Distinct P&L Concepts

The system must distinguish:

```text
Current P&L
Realized P&L
Peak P&L
```

These are separate variables.

There must not be a duplicate:

```text CurrentProfit
CurrentPnL
```

representing the same concept.

The canonical variable is:

```text CurrentPnL.
```

---

# 4. Realized P&L

Realized P&L represents economic outcome from completed executions.

For a long position:

```text RealizedGrossPnL
=
ExitValue
-
EntryValue
```

using actual fill prices and quantities.

---

# 5. Net Realized P&L

The canonical net result is:

```text NetRealizedPnL
=
GrossRealizedPnL
-
ExecutionCosts
-
ApplicableCharges.
```

The exact fee and tax categories remain dependent on the broker/exchange contract.

---

# 6. Unrealized P&L

For an open position:

```text UnrealizedPnL
```

represents the current mark-to-market value relative to actual entry fills.

For a long option:

```text UnrealizedGrossPnL
=
CurrentExitValue
-
ActualEntryValue.
```

The current exit value must use the declared executable valuation convention.

---

# 7. Current P&L

The canonical:

```text CurrentPnL
```

is:

```text CurrentPnL
=
RealizedPnL
+
UnrealizedPnL
-
ApplicableAccruedCosts.
```

The exact accounting convention must be consistent across research and live execution.

---

# 8. P&L Is Derived

P&L is a derived accounting state.

It is not independently assigned.

Therefore:

```text CurrentPnL
```

must always be reconstructible from:

```text fills
position
valuation
cost ledger.
```

---

# 9. Entry Basis

For each position:

```text EntryCostBasis
=
Σ(fill_price_i × fill_quantity_i)
+
applicable entry costs.
```

Each component remains individually auditable.

---

# 10. Exit Proceeds

For completed exits:

```text ExitProceeds
=
Σ(exit_fill_price_i × exit_fill_quantity_i).
```

Applicable exit costs are separately recorded.

---

# 11. Average Entry Price

For position quantity `Q`:

```text AverageEntryPrice
=
Σ(entry_price_i × quantity_i)
/
Σ(quantity_i)
```

This is an accounting quantity.

It must not be confused with:

```text theoretical entry price
```

used during research.

---

# 12. Average Exit Price

For completed exits:

```text AverageExitPrice
=
Σ(exit_price_i × quantity_i)
/
Σ(exit_quantity_i).
```

---

# 13. Partial Exits

If only part of a position is closed:

```text ClosedQuantity < OriginalQuantity.
```

The system calculates realized P&L for the closed portion.

The remaining quantity retains its appropriate cost basis.

---

# 14. Position Ledger

The authoritative position ledger records:

```text PositionLedger {
    position_id
    instrument_id

    opening_fills[]
    closing_fills[]

    quantity
    cost_basis

    realized_pnl
    unrealized_pnl

    fees
    slippage
    status
}
```

---

# 15. Quantity Conservation

At all times:

```text CurrentQuantity
=
TotalEntryQuantity
-
TotalExitQuantity.
```

This is an accounting invariant.

---

# 16. Fill-Driven Accounting

A fill can modify:

```text position quantity
cost basis
realized P&L
execution cost.
```

An ordinary market tick cannot modify realized P&L.

---

# 17. Market Data Cannot Create P&L

A market event may change:

```text UnrealizedPnL.
```

It cannot change:

```text RealizedPnL.
```

Realized P&L changes only through actual closing executions.

---

# 18. Peak P&L

Define:

```text PeakPnL_t
=
max(PnL_0, PnL_1, ..., PnL_t).
```

Therefore:

```text PeakPnL_(t+1)
>=
PeakPnL_t.
```

Peak P&L is monotonic non-decreasing.

---

# 19. Profit Giveback

Define:

```text ProfitGiveback
=
max(0, PeakPnL - CurrentPnL).
```

This measures deterioration from the best observed P&L.

It does not represent realized loss.

---

# 20. Drawdown

At portfolio level:

```text Drawdown_t
=
PeakEquity_t
-
CurrentEquity_t.
```

For percentage drawdown:

```text DrawdownPct_t
=
Drawdown_t
/
PeakEquity_t.
```

The exact treatment when equity is zero or negative must be defined separately.

---

# 21. Trade Drawdown

For an individual trade:

```text TradeDrawdown
=
PeakTradePnL
-
CurrentTradePnL.
```

This is distinct from account-level drawdown.

---

# 22. Maximum Drawdown

For a sequence of equity values:

```text MaxDrawdown
=
max_t(Drawdown_t).
```

It is calculated over the defined evaluation interval.

---

# 23. Gross Versus Net Performance

Every performance report must distinguish:

```text GrossPnL
NetPnL.
```

A strategy cannot be considered profitable merely because:

```text GrossPnL > 0.
```

---

# 24. Execution Cost Attribution

Net P&L should be decomposable as:

```text GrossTradingPnL
-
SpreadCost
-
SlippageCost
-
Brokerage
-
Taxes
-
OtherApplicableCosts
=
NetPnL.
```

The exact charge categories depend on the external execution contract.

---

# 25. Spread Cost

Where a benchmark permits explicit decomposition:

```text SpreadCost
```

represents the economic cost attributable to crossing the bid/ask spread.

---

# 26. Slippage Cost

Slippage is:

```text actual execution
-
declared execution benchmark.
```

The sign convention must be fixed globally.

The reporting layer should normalize the sign so that:

```text positive cost = worse execution.
```

---

# 27. Market Impact

If the order consumes multiple price levels:

```text MarketImpactCost
```

may be separately attributed.

This prevents large-order execution degradation from being hidden inside generic slippage.

---

# 28. Expected Versus Realized Cost

The accounting system records both:

```text ExpectedExecutionCost
RealizedExecutionCost.
```

The difference is:

```text ExecutionCostError
=
RealizedExecutionCost
-
ExpectedExecutionCost.
```

This is important for validating the execution model.

---

# 29. Trade Outcome

Each completed trade produces:

```text TradeOutcome {
    trade_id

    entry_timestamp
    exit_timestamp

    quantity

    gross_pnl
    net_pnl

    holding_time

    peak_pnl
    max_adverse_excursion
    max_favorable_excursion

    execution_cost

    exit_reason
}
```

---

# 30. Holding Time

The canonical realized holding time is:

```text ActualHoldingTime
=
ExitTimestamp
-
EntryTimestamp.
```

This remains distinct from:

```text ExpectedHoldingTime.
```

The latter is a model output.

---

# 31. Label Horizon

It also remains distinct from:

```text LabelHorizon.
```

Therefore:

```text LabelHorizon
!=
ExpectedHoldingTime
!=
ActualHoldingTime.
```

This distinction is permanent.

---

# 32. Maximum Favorable Excursion

For a trade:

```text MFE
=
maximum favorable unrealized outcome
```

during the trade lifecycle.

It is calculated only from information occurring after entry.

---

# 33. Maximum Adverse Excursion

Similarly:

```text MAE
=
maximum adverse unrealized outcome
```

during the trade lifecycle.

These are outcome statistics.

They cannot influence the original entry decision in historical replay.

---

# 34. Exit Reason

Every completed trade must have exactly one canonical primary exit reason.

Examples:

```text PROTECTION
TRAILING_PROTECTION
PROFIT_FLOOR
CONTINUATION_FAILURE
EMERGENCY_REVERSAL
SESSION_CLOSE
DATA_SAFETY
MANUAL/OPERATIONAL
```

The exact final enumeration belongs to the state-transition contract.

---

# 35. Exit Reason Is Not Outcome

The system must not infer:

```text PROFITABLE
```

from:

```text EXIT_REASON = TRAILING_PROTECTION.
```

Profitability is calculated from actual accounting.

---

# 36. Trade Return

Trade return may be represented as:

```text TradeReturn
=
NetPnL
/
DefinedCapitalBasis.
```

The capital basis must be explicitly defined.

The system must not switch denominators between experiments.

---

# 37. Expectancy

For a population of completed trades:

```text Expectancy
=
Mean(NetPnL per trade).
```

It can also be decomposed:

```text Expectancy
=
P(Win) × AvgWin
-
P(Loss) × AvgLoss
```

subject to the exact treatment of zero outcomes.

---

# 38. Expectancy Is Not Edge Proof

Positive historical expectancy does not establish a genuine edge.

It must survive:

```text out-of-sample evaluation
costs
execution stress
parameter perturbation
multiple-testing controls.
```

---

# 39. Win Rate

The system records:

```text WinRate
=
WinningTrades
/
CompletedTrades.
```

Win rate is descriptive.

It is not an optimization objective by itself.

---

# 40. Average Win

```text AverageWin
=
ΣPositiveNetPnL
/
NumberOfWinningTrades.
```

---

# 41. Average Loss

```text AverageLoss
=
ΣAbsoluteNegativeNetPnL
/
NumberOfLosingTrades.
```

---

# 42. Profit Factor

```text ProfitFactor
=
GrossWinningPnL
/
GrossLosingPnL.
```

The denominator is represented as a positive loss magnitude.

---

# 43. Trade Count

Trade count is reported exactly.

The system must distinguish:

```text Opportunities
Decisions
Orders
Fills
Trades.
```

These are not interchangeable sample counts.

---

# 44. Opportunity Count

```text OpportunityCount
```

is the number of eligible opportunity observations.

It includes:

```text traded opportunities
NO_TRADE opportunities.
```

---

# 45. Decision Count

A decision occurs when the decision engine evaluates an opportunity and produces a canonical action.

Therefore:

```text DecisionCount
```

may exceed:

```text TradeCount.
```

---

# 46. Order Count

One decision may produce:

```text zero orders
one order
multiple order events.
```

Therefore:

```text OrderCount
```

is a separate operational metric.

---

# 47. Fill Count

One order can generate:

```text multiple fills.
```

Therefore:

```text FillCount
```

must not be interpreted as:

```text TradeCount.
```

---

# 48. Strategy Equity Curve

The strategy equity curve is constructed from:

```text initial capital
+
chronologically realized net P&L
+
declared mark-to-market treatment.
```

The exact treatment must be consistent across research.

---

# 49. Equity Curve Causality

At time `t`:

```text Equity_t
```

may use only:

```text realized P&L <= t
```

and, when calculating mark-to-market equity:

```text market information <= t.
```

Future fills cannot alter historical equity.

---

# 50. Daily Performance

Daily performance must be aggregated from:

```text chronological trade outcomes
```

rather than reconstructed from:

```text daily closing price.
```

This preserves actual execution economics.

---

# 51. Session Performance

Each trading session receives:

```text SessionPnL
SessionGrossPnL
SessionNetPnL
SessionCosts
SessionTradeCount
```

and relevant risk metrics.

---

# 52. Intraday Strategy Requirement

Because this is an intraday strategy:

```text end-of-session position
```

must conform to the defined overnight-exposure policy.

The accounting system must explicitly detect any residual position.

---

# 53. Residual Position

If the system reaches session close with:

```text PositionQuantity != 0,
```

this is an operational/accounting exception.

It must not be silently treated as:

```text closed at theoretical closing price.
```

---

# 54. Performance Attribution by Decision Layer

The system should retain enough lineage to answer:

```text Did the strategy lose money because:

1. Direction prediction was wrong?
2. Option selection was poor?
3. Position sizing was excessive?
4. Execution was expensive?
5. Trade management exited too early?
6. Trade management exited too late?
7. Costs consumed the edge?
```

This is the purpose of attribution.

---

# 55. Prediction Attribution

For each trade:

```text PredictedDirection
ActualOutcome
ProbabilityAtEntry
```

are recorded.

The prediction layer can then be evaluated independently from execution.

---

# 56. Option Selection Attribution

Record:

```text SelectedOption
CandidateSet
ExpectedOptionValue
RealizedOptionOutcome.
```

This allows comparison between:

```text underlying prediction quality
```

and:

```text option monetization quality.
```

---

# 57. Execution Attribution

Record:

```text ExpectedEntryPrice
ActualEntryPrice
ExpectedExitPrice
ActualExitPrice
ExpectedExecutionCost
RealizedExecutionCost.
```

This isolates execution degradation.

---

# 58. Risk Attribution

Record:

```text AuthorizedRisk
ActualInitialRisk
PeakRisk
RealizedLoss
MaximumAdverseExcursion.
```

This allows us to determine whether losses resulted from:

```text prediction error
```

or:

```text risk-policy failure.
```

---

# 59. Trade-Management Attribution

Record:

```text EntryState
ManagementModeTransitions
ContinuationValue
ProfitGiveback
ProtectionTransitions
ExitTrigger
```

This allows analysis of:

```text entry correctness
```

separately from:

```text exit quality.
```

---

# 60. Counterfactual Performance

Counterfactual metrics may be calculated for research:

```text What if exit occurred at:
protection
maximum favorable excursion
fixed horizon
alternative management rule.
```

But these are explicitly:

```text COUNTERFACTUAL
```

and never enter realized P&L.

---

# 61. Counterfactual Leakage Rule

Counterfactual optimal exits are future information.

Therefore:

```text MFE-based perfect exit
```

cannot be used to tune the historical decision and then reported as actual strategy performance without a valid walk-forward procedure.

---

# 62. Performance Segmentation

Performance should be segmented by:

```text direction
time of day
volatility regime
market regime
option characteristics
trade-management mode
execution condition.
```

Segmentation is diagnostic first.

It must not automatically become a new optimization layer.

---

# 63. Segment Sample Sufficiency

A segment with:

```text very few trades
```

must not be treated as reliable evidence.

The same statistical discipline used for model estimation applies to performance segmentation.

---

# 64. Performance Uncertainty

Major performance metrics should include uncertainty estimates where statistically meaningful.

For example:

```text expectancy estimate
drawdown distribution
win probability
profit factor uncertainty.
```

The methodology must account for temporal dependence where appropriate.

---

# 65. Bootstrap Restrictions

If bootstrap methods are used, ordinary IID bootstrap may be invalid for temporally dependent trading outcomes.

The research framework may require:

```text block bootstrap
stationary bootstrap
other dependence-aware methods.
```

The exact methodology remains unfrozen.

---

# 66. Risk-Adjusted Performance

The system may report:

```text Sharpe-like metrics
Sortino-like metrics
return-to-drawdown
Calmar-like metrics.
```

But these are secondary diagnostics.

They do not replace:

```text net expectancy
drawdown
cost robustness
out-of-sample stability.
```

---

# 67. Sharpe Caution

Because trading returns may be:

```text non-normal
serially dependent
heteroskedastic
```

a naïve Sharpe ratio must not be treated as definitive statistical evidence.

---

# 68. Drawdown Analysis

The system should record:

```text maximum drawdown
drawdown duration
recovery duration
number of drawdown episodes
distribution of drawdowns.
```

A strategy with positive expectancy but unacceptable drawdown may be operationally unusable.

---

# 69. Consecutive Losses

Record:

```text maximum consecutive losses
distribution of consecutive losses.
```

This is useful for understanding psychological and capital requirements, but it must not become an arbitrary parameter-tuning target.

---

# 70. Tail Loss Analysis

The system should inspect:

```text worst trade
worst session
worst day
worst sequence
tail loss quantiles.
```

This is particularly important for options because loss distributions can be asymmetric.

---

# 71. Cost Attribution

The system should calculate:

```text Cost / GrossPnL
Cost / GrossEdge
Cost / Trade
Cost / UnitRisk.
```

A strategy whose gross edge is largely consumed by costs is considered fragile.

---

# 72. P&L Conservation

The accounting system must satisfy:

```text TotalNetPnL
=
ΣTradeNetPnL
```

subject to explicitly defined:

```text account-level adjustments
fees
corporate/instrument events
```

where applicable.

---

# 73. Reconciliation

The internal ledger must be reconcilable against the authoritative execution/account ledger.

Any unexplained difference produces:

```text ACCOUNTING_RECONCILIATION_FAILURE.
```

---

# 74. P&L Immutability

Once a completed trade is finalized:

```text TradeOutcome
```

is immutable.

A later model update cannot modify:

```text historical P&L.
```

---

# 75. Research Isolation

Historical P&L can be consumed by:

```text performance analysis
model validation
research.
```

but cannot retroactively modify:

```text original feature state
probability
decision
risk authorization
execution event.
```

---

# 76. No Backward P&L Flow

The dependency direction is strictly:

```text id="0dzl7t"
Prediction
    ↓
Decision
    ↓
Execution
    ↓
P&L
```

Never:

```text P&L
    ↓
Prediction
```

for the same historical observation.

---

# 77. Performance Dataset

Every completed trade generates a canonical:

```text TradePerformanceRecord.
```

It contains:

```text trade identity
entry state
decision state
execution state
position state
exit state
P&L
costs
risk
management metadata.
```

---

# 78. Performance Dataset Version

Performance datasets are versioned according to:

```text accounting schema version
execution dataset version
valuation convention
cost convention.
```

Changing accounting rules creates a new performance dataset version.

---

# 79. Experiment Performance

Every experiment must retain:

```text ExperimentID
DatasetVersion
ModelVersion
ParameterVersion
ExecutionModelVersion
RiskPolicyVersion
AccountingVersion
```

Therefore a reported P&L number has complete lineage.

---

# 80. Performance Comparison

Two strategy results may be compared only when their:

```text accounting convention
execution assumptions
risk definitions
evaluation periods
```

are compatible.

Otherwise the comparison must explicitly identify the differences.

---

# 81. Performance Invariants

```text PNL-001 id="e6n9q2"
Realized P&L comes only from actual closing fills.

PNL-002
Unrealized P&L is distinct from realized P&L.

PNL-003
Current P&L is derived, not independently assigned.

PNL-004
Peak P&L is monotonic non-decreasing.

PNL-005
Profit giveback is distinct from realized loss.

PNL-006
Future information cannot alter historical P&L.

PNL-007
Expected P&L is distinct from realized P&L.

PNL-008
Hypothetical/counterfactual P&L is never realized P&L.

PNL-009
Trade count, order count, fill count, and opportunity count are distinct.

PNL-010
Net P&L includes applicable execution costs.

PNL-011
Historical accounting records are immutable.

PNL-012
P&L cannot flow backward into the decision state.

PNL-013
Total strategy P&L reconciles to the underlying trade ledger.

PNL-014
Every trade outcome has complete lineage.

PNL-015
Performance metrics cannot silently change accounting conventions.

PNL-016
Residual positions at session close are explicit exceptions.

PNL-017
Performance segmentation does not imply independent statistical evidence.

PNL-018
Execution cost attribution is separated from predictive performance.
```

---

# 82. Numerical Parameters Still Unfrozen

We have deliberately not selected:

```text exact performance confidence methodology
drawdown acceptance thresholds
minimum expectancy
minimum profit factor
risk-adjusted performance thresholds
minimum trade count
tail-loss acceptance thresholds.
```

These belong to the validation and deployment criteria.

---

# 83. Architecture Status

The complete chain is now:

```text Mathematical Specification              COMPLETE
Variable Registry                          COMPLETE
Event Schema                               COMPLETE
State Schema                               COMPLETE
State Transition Specification              COMPLETE
Research Dataset Specification              COMPLETE
Walk-Forward Specification                  COMPLETE
Statistical Estimation Specification       COMPLETE
Economic Decision Specification             COMPLETE
Option Selection Specification              COMPLETE
Risk Budget Specification                   COMPLETE
Position Sizing Specification               COMPLETE
Execution Specification                     COMPLETE
P&L and Accounting Specification             COMPLETE
Performance Attribution                     COMPLETE
```

The architecture is now very close to implementation-ready.

---

# 84. Next Artifact

The next logical artifact is the:

# CANONICAL MODEL VALIDATION, ACCEPTANCE, AND PROMOTION SPECIFICATION

This is important because we now know how to generate:

```text predictions
decisions
trades
P&L
```

but we have not yet defined the exact mathematical gate that determines:

```text "This model has demonstrated enough genuine out-of-sample evidence
to be allowed into production."
```

That next artifact will define the acceptance hierarchy across:

```text statistical validity
calibration
economic edge
execution robustness
risk behavior
drawdown
parameter stability
regime robustness
multiple-testing correction
adversarial testing
walk-forward consistency
final holdout
```

Most importantly, it will define **what constitutes failure**, not merely what constitutes success.