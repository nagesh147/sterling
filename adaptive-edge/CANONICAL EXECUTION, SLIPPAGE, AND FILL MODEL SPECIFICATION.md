# CANONICAL EXECUTION, SLIPPAGE, AND FILL MODEL SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines how an authorized trading decision becomes an actual simulated or live execution.

The canonical path is:

```text
Decision
    ↓
Risk Authorization
    ↓
Order Intent
    ↓
Execution Validation
    ↓
Order Submission
    ↓
Market Interaction
    ↓
Fill / Partial Fill / Reject
    ↓
Position
    ↓
Realized Execution Cost
```

The execution layer is intentionally separated from:

```text probability
economic prediction
risk authorization
trade management.
```

---

# 2. Fundamental Principle

The strategy does not trade at a theoretical price.

It trades at an executable price.

Therefore:

```text
LastPrice != GuaranteedEntryPrice
```

and:

```text
MidPrice != GuaranteedEntryPrice
```

and:

```text
ModelPrice != GuaranteedEntryPrice
```

The execution model must explicitly determine whether and at what price an order could actually have been filled.

---

# 3. Execution Decision

The execution layer receives:

```text OrderIntent
+
CurrentExecutableMarketState
+
ExecutionPolicyVersion
```

and produces:

```text OrderEvent
```

or:

```text ExecutionRejection.
```

---

# 4. Order Intent

An order intent contains:

```text
OrderIntent {
    order_intent_id

    decision_id
    trade_id

    instrument_id

    side
    requested_quantity

    order_type

    creation_timestamp

    maximum_acceptable_price
    minimum_acceptable_price

    execution_policy_version
}
```

The exact price constraints depend on order type.

---

# 5. Baseline Order Type

The baseline system should begin with the simplest execution model that is compatible with the intended trading strategy.

For a long option entry:

```text BUY
```

is the baseline action.

The initial research implementation should not assume sophisticated order-routing behavior that cannot be reconstructed from historical data.

---

# 6. Marketable Order Principle

For a buy:

```text executable reference = ask
```

For a sell:

```text executable reference = bid
```

where the relevant quote is valid and sufficiently fresh.

The midpoint is not assumed to be executable.

---

# 7. Quote Freshness

Every execution decision requires:

```text QuoteTimestamp
```

and:

```text ExecutionTimestamp.
```

Define:

```text QuoteAge
=
ExecutionTimestamp - QuoteTimestamp
```

The quote is executable only if:

```text QuoteAge <= MaximumAllowedQuoteAge.
```

The exact threshold remains:

```text UNFROZEN.
```

---

# 8. Stale Quote

A stale quote must not be used to claim a favorable historical fill.

If no sufficiently fresh executable quote exists:

```text ExecutionStatus = REJECTED
```

or:

```text ExecutionStatus = UNEXECUTABLE.
```

The trade does not receive a synthetic fill.

---

# 9. Spread

At execution time:

```text Spread
=
Ask - Bid
```

must be recorded.

The execution engine records:

```text quoted spread
executed price
spread component
slippage component.
```

These are separate quantities.

---

# 10. Entry Price

For an immediately marketable buy:

```text EntryReferencePrice = Ask
```

subject to:

```text liquidity
quote validity
order size
execution policy.
```

The actual fill may be worse.

---

# 11. Exit Price

For an immediately marketable sell:

```text ExitReferencePrice = Bid.
```

Again, the actual fill may be worse.

---

# 12. Midpoint Prohibition

The following backtest assumption is prohibited:

```text Buy at midpoint
Sell at midpoint
```

unless the execution model has independent evidence that such fills are achievable.

---

# 13. Last-Traded-Price Prohibition

The system must not simulate:

```text BUY at last trade
```

simply because the last trade is available.

The last trade may be:

```text old
below current ask
from insufficient size
```

and therefore non-executable.

---

# 14. Order Size

Execution feasibility depends on:

```text requested quantity
available displayed quantity
available depth
market dynamics.
```

Therefore a one-lot execution cannot automatically be extrapolated to a large position.

---

# 15. Market Depth

Where depth data is available:

```text OrderQuantity
```

is matched against:

```text available ask levels
```

for buys and:

```text available bid levels
```

for sells.

The exact depth semantics remain:

```text PENDING_TRUE_DATA_CONTRACT.
```

---

# 16. Depth-Based Fill Model

Conceptually, for a buy:

```text RequestedQuantity
        ↓
Best Ask Quantity
        ↓
Next Ask Level
        ↓
Next Ask Level
        ↓
Filled Quantity
```

The simulated volume-weighted execution price is:

```text VWAP_fill
=
Σ(price_i × filled_quantity_i)
/
Σ(filled_quantity_i).
```

---

# 17. Partial Fill

If available executable liquidity is less than requested quantity:

```text FilledQuantity < RequestedQuantity.
```

The system records:

```text PARTIAL_FILL.
```

It does not silently assume full execution.

---

# 18. Remaining Quantity

The remaining quantity is:

```text RemainingQuantity
=
RequestedQuantity - FilledQuantity.
```

It remains an order state.

It is not a position.

---

# 19. Fill State Machine

The canonical order lifecycle is:

```text CREATED
   ↓
VALIDATED
   ↓
SUBMITTED
   ↓
ACCEPTED
   ↓
PARTIALLY_FILLED
   ↓
FILLED
```

Alternative terminal paths:

```text REJECTED
CANCELLED
EXPIRED
FAILED
```

---

# 20. Fill Event

A fill event contains:

```text FillID
OrderID
InstrumentID

ExecutedQuantity
ExecutedPrice

ExecutionTimestamp

ExecutionCost

LiquidityContext

ExecutionModelVersion
```

Only this event changes the position.

---

# 21. Fill Idempotency

If the same:

```text FillID
```

is processed twice:

```text PositionState
```

must change only once.

This is a mandatory execution invariant.

---

# 22. Slippage

Define slippage relative to a declared benchmark.

For a buy:

```text Slippage
=
ExecutedPrice - ReferenceExecutionPrice
```

For a sell:

```text Slippage
=
ReferenceExecutionPrice - ExecutedPrice.
```

Positive slippage represents worse execution.

---

# 23. Benchmark Definition

The benchmark must be fixed before evaluating execution performance.

Possible benchmarks include:

```text best ask/bid
midpoint
arrival price
decision-time executable price
```

The baseline should prioritize:

```text executable price
```

rather than midpoint.

---

# 24. Spread Versus Slippage

These must not be conflated.

For example:

```text Mid = 100
Ask = 101
Fill = 101.20
```

Then:

```text spread cost
```

and:

```text additional execution slippage
```

are distinct components.

The accounting layer must preserve both.

---

# 25. Execution Cost Decomposition

For each fill:

```text TotalExecutionCost
=
SpreadComponent
+
SlippageComponent
+
Fees
+
Taxes
+
OtherApplicableCharges.
```

Exact fee/tax semantics remain external-data/broker dependent.

---

# 26. Market Impact

If order size consumes multiple price levels, the additional cost represents:

```text market impact / depth consumption.
```

This is distinct from random slippage.

---

# 27. Latency

Execution may occur after the decision.

Define:

```text DecisionTimestamp
ExecutionTimestamp
```

and:

```text DecisionToExecutionLatency
=
ExecutionTimestamp - DecisionTimestamp.
```

Latency is an execution variable.

---

# 28. Latency Cannot Be Ignored

If the market moves materially during latency:

```text DecisionPrice != ExecutionPrice.
```

The backtest must not use the decision-time quote as the actual fill without a justified latency model.

---

# 29. Historical Replay

During historical simulation:

```text Decision_t
```

creates an order at:

```text T_decision.
```

The execution engine determines the earliest legally executable fill after:

```text T_decision.
```

subject to the execution policy.

---

# 30. No Same-Timestamp Magical Fill

The simulator must not automatically assume:

```text signal detected at T
+
favorable market movement also at T
+
perfect fill at favorable price.
```

If event ordering does not establish that the favorable price was executable after the decision became known, that price cannot be used.

---

# 31. Event Ordering

When multiple events have identical timestamps, execution requires a deterministic ordering rule.

Conceptually:

```text Market event
    ↓
State update
    ↓
Decision
    ↓
Order
    ↓
Subsequent executable market event
```

The exact provider sequencing semantics remain subject to the data contract.

---

# 32. Conservative Ambiguity Rule

If historical data cannot establish whether an order would have filled:

```text Do not assume the favorable outcome.
```

The simulator should either:

```text reject the fill
```

or:

```text apply the predefined conservative execution assumption.
```

---

# 33. Execution Uncertainty

Where the exact fill price cannot be reconstructed:

```text simulated fill uncertainty
```

must be represented explicitly.

The system must not hide uncertainty inside a precise-looking fill price.

---

# 34. Execution Cost Model

The cost model may estimate:

```text ExpectedSpreadCost
ExpectedSlippage
ExpectedMarketImpact
ExpectedFees
```

before entry.

These are forecasts.

Actual costs are recorded from fills.

---

# 35. Forecast Versus Realized Execution Cost

The system therefore maintains:

```text ExpectedExecutionCost
```

and:

```text RealizedExecutionCost.
```

They must never be represented by one variable.

---

# 36. Execution Model Calibration

If historical execution data exists, the execution-cost model can be estimated using:

```text historical order/fill observations.
```

It must follow the same walk-forward protocol as the strategy model.

---

# 37. Execution Model Leakage

The execution model cannot use future:

```text realized fill price
```

to predict the fill for the same historical decision.

The fill is the outcome.

---

# 38. Execution Model Inputs

Potential inputs include:

```text spread
depth
order size
time of day
volatility
quote age
recent price movement
market state
latency.
```

Only variables demonstrably available before execution may be used.

---

# 39. Cost Forecast

For candidate option `o`:

```text C_expected(o,t)
```

represents expected round-trip execution cost.

It enters:

```text ExpectedNetValue.
```

---

# 40. Cost Uncertainty

The execution model should also estimate uncertainty where supported.

A candidate whose edge is smaller than plausible execution-cost uncertainty may be rejected.

---

# 41. Worst-Case Execution

The system should support adversarial execution scenarios:

```text normal
moderate slippage
high slippage
spread expansion
partial fill
delayed fill
```

These are stress tests.

They are not automatically the production execution model.

---

# 42. Execution Robustness

A strategy should not be accepted solely because:

```text base-case execution
```

produces positive P&L.

It should demonstrate reasonable robustness under:

```text worse spread
worse slippage
longer latency
lower fill probability.
```

---

# 43. Fill Probability

If the order is not immediately marketable, the system may need:

```text P(Fill | MarketState, OrderState).
```

The baseline strategy should avoid relying heavily on passive-order fill prediction unless historical data supports it.

---

# 44. Marketable Versus Passive Orders

The execution architecture distinguishes:

```text Marketable execution
```

from:

```text Passive execution.
```

They have different:

```text fill probability
latency
slippage
adverse-selection
```

characteristics.

---

# 45. Baseline Execution Policy

The initial production baseline should prefer a simple execution policy whose behavior is directly observable and reproducible.

Complex adaptive order placement is deferred until the baseline demonstrates sufficient economic edge.

---

# 46. Order Rejection

An order may be rejected because of:

```text stale quote
invalid quantity
risk violation
instrument invalid
market closed
broker rejection
insufficient liquidity
operational failure.
```

The rejection reason must be recorded.

---

# 47. Rejection Is Not a Loss

A rejected order means:

```text no position was created.
```

The system must not assign the hypothetical trade's P&L to the portfolio.

It may, however, record the missed opportunity for execution analysis.

---

# 48. Missed Opportunity

A missed opportunity record contains:

```text Decision
OrderIntent
Reason not filled
Hypothetical subsequent market path.
```

This is useful for diagnosing execution quality.

But hypothetical P&L must remain separate from realized P&L.

---

# 49. Cancellation

Cancellation produces:

```text OrderStatus = CANCELLED.
```

No additional position is created after cancellation.

A later execution after cancellation would require a separate authoritative event.

---

# 50. Expiration

An order may expire when:

```text its validity window ends.
```

The expiration must be explicit.

It cannot later become a fill without a new order lifecycle.

---

# 51. Exit Execution

Exit orders follow the same principles as entry orders.

For a long option:

```text sell at executable bid
```

subject to:

```text liquidity
latency
slippage
depth.
```

---

# 52. Exit Priority

If:

```text ExitObligation = TRUE,
```

the execution system must prioritize reducing the existing position over creating new exposure.

---

# 53. Failed Exit

If an exit cannot be executed:

```text Position remains active.
```

and:

```text ExitObligation remains TRUE.
```

The system enters the defined recovery/safety path.

---

# 54. No Re-entry Through Failed Exit

A failed exit cannot produce:

```text opposite entry
```

automatically.

The baseline response is continued exit/recovery handling.

---

# 55. Execution During Data Degradation

If executable market data becomes invalid:

```text NewEntry = prohibited.
```

Existing positions continue under the safety policy.

---

# 56. Execution During Reconciliation Failure

If internal and broker positions disagree:

```text NewEntry = prohibited.
```

Execution must prioritize reconciliation.

---

# 57. Execution and Risk

The execution layer cannot increase:

```text AuthorizedRisk.
```

If worse execution would cause the planned order to violate the risk constraint:

```text order quantity must be reduced
```

or:

```text order rejected.
```

The execution layer cannot simply exceed risk.

---

# 58. Execution and Economic Validity

If the expected executable price changes enough that:

```text ExpectedNetValue <= RequiredEconomicValue,
```

the order may be rejected before submission.

This is execution revalidation.

---

# 59. Execution Revalidation Does Not Rewrite Probability

The probability state remains:

```text unchanged.
```

Only:

```text economic validity
execution validity
```

are reevaluated.

---

# 60. Fill Accounting

For multiple fills:

```text AverageFillPrice
=
Σ(fill_price_i × quantity_i)
/
Σ(quantity_i).
```

All fill records remain individually available.

---

# 61. Realized Execution Cost

Actual execution cost is calculated from:

```text actual fills
+
actual fees
+
actual transaction charges.
```

The simulated strategy must preserve this accounting structure.

---

# 62. Execution Attribution

Realized P&L should be decomposable into:

```text underlying/option price movement
+
spread cost
+
slippage
+
fees
+
other execution effects.
```

This lets us determine whether an apparent strategy edge is being destroyed by execution.

---

# 63. Execution Quality Metrics

The research system should record:

```text fill rate
partial-fill rate
rejection rate
average slippage
slippage distribution
spread paid
execution latency
market impact
cost per trade
cost as percentage of gross edge.
```

---

# 64. Execution Stress Testing

Every candidate strategy should be evaluated under:

```text Base Execution
+
Moderate Slippage
+
Severe Slippage
+
Spread Expansion
+
Latency Increase
+
Reduced Fill Probability.
```

A strategy that collapses under trivial execution deterioration is fragile.

---

# 65. Execution Model Comparison

At minimum, research should compare:

```text optimistic execution
realistic execution
conservative execution.
```

The production model should not simply select the most profitable one.

It should select the model justified by available evidence.

---

# 66. Optimistic Execution

Examples:

```text midpoint fills
zero latency
full quantity
no spread widening
```

are acceptable only as diagnostic upper bounds.

They must never be presented as realistic production performance without evidence.

---

# 67. Conservative Execution

A conservative model may impose:

```text worse side of spread
additional slippage
partial fills
latency
```

to test robustness.

---

# 68. Execution Floor

A strategy should have a minimum acceptable execution robustness condition:

```text Edge_after_realistic_costs > 0.
```

The exact robustness margin remains:

```text UNFROZEN.
```

---

# 69. Execution Model Versioning

Every execution model receives:

```text ExecutionModelVersion
```

containing:

```text dataset version
cost methodology
slippage methodology
latency assumptions
fill assumptions
parameter version.
```

---

# 70. Historical Execution Reproducibility

Given:

```text same market events
same order intent
same execution model version
```

the simulator must produce the same:

```text fill sequence
fill prices
quantities
execution costs.
```

---

# 71. Execution Invariants

```text EXEC-001
A decision is not a fill.

EXEC-002
An order is not a position.

EXEC-003
Only authoritative FillEvents change position quantity.

EXEC-004
Midpoint is not assumed executable.

EXEC-005
Last traded price is not assumed executable.

EXEC-006
Stale quotes cannot generate favorable fills.

EXEC-007
Requested quantity is not assumed to equal filled quantity.

EXEC-008
Partial fills are represented explicitly.

EXEC-009
Duplicate fills are idempotent.

EXEC-010
Cancelled orders cannot silently become fills.

EXEC-011
Execution cannot increase risk authorization.

EXEC-012
Execution costs are separated into explicit components.

EXEC-013
Expected execution cost is distinct from realized execution cost.

EXEC-014
Historical execution cannot use future fill information.

EXEC-015
Ambiguous historical fills are handled conservatively.

EXEC-016
Execution revalidation cannot rewrite the original decision.

EXEC-017
Failed exits preserve the exit obligation.

EXEC-018
Hypothetical missed-trade P&L is not realized P&L.

EXEC-019
Execution model versions are immutable.

EXEC-020
Execution replay is deterministic.
```

---

# 72. Numerical Parameters Still Unfrozen

We deliberately have not selected:

```text maximum quote age
latency distribution
slippage distribution
fill probability
depth consumption model
maximum spread
execution timeout
partial-fill policy
cost buffers
execution robustness threshold.
```

These require actual market/execution data.

---

# 73. External Data Dependencies

The following cannot be finalized until the TrueData documentation is available:

```text exact tick semantics
quote update semantics
depth semantics
sequence ordering
timestamp precision
historical tick availability
option-chain historical availability.
```

These belong to the data adapter contract, not the mathematical strategy specification.

---

# 74. Current Architecture

The full decision-to-execution chain is now:

```text
Market Data
    ↓
Canonical Events
    ↓
Causal State
    ↓
Features
    ↓
Probability
    ↓
Outcome Distribution
    ↓
Economic Evaluation
    ↓
Option Selection
    ↓
Risk Authorization
    ↓
Position Size
    ↓
Order Intent
    ↓
Execution Validation
    ↓
Order
    ↓
Fill
    ↓
Position
    ↓
Realized P&L
```

Every boundary is explicit.

---

# 75. Architecture Status

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
Slippage Model Contract                     COMPLETE
Fill Model Contract                         COMPLETE
```

Numerical calibration remains intentionally unfrozen.

---

# 76. Next Artifact

The next artifact should be the **Canonical P&L, Accounting, and Performance Attribution Specification**.

That is the logical next step because we now have:

```text decision
→ risk
→ order
→ fill
→ position.
```

We must now define exactly how the system calculates:

```text gross P&L
net P&L
realized P&L
unrealized P&L
peak P&L
drawdown
profit giveback
transaction costs
slippage
trade expectancy
strategy expectancy
risk-adjusted performance
```

Most importantly, we will make sure **P&L is an output of actual fills and accounting rules, never an input that can leak backward into prediction, decision, or risk state**.