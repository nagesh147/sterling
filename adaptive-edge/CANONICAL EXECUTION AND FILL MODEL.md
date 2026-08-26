# CANONICAL EXECUTION AND FILL MODEL

Version 1.0

## 1. Purpose

This specification defines the exact conceptual boundary between:

```text
TRADING DECISION
        |
        v
ORDER INTENT
        |
        v
ORDER SUBMISSION
        |
        v
BROKER ACKNOWLEDGEMENT
        |
        v
ACTUAL FILL
        |
        v
POSITION
```

The objective is to prevent the backtest from assuming that a desired transaction automatically occurred.

The system must model the difference between:

```text what the strategy wanted
```

and:

```text what the market actually executed.
```

---

# 2. Fundamental Execution Invariant

The strategy must never infer:

```text PositionExists = TRUE
```

from:

```text BUY_SIGNAL = TRUE
```

Nor from:

```text ORDER_SUBMITTED = TRUE
```

Nor from:

```text ORDER_ACCEPTED = TRUE
```

The only authoritative basis for exposure is:

```text ACTUAL_EXECUTED_QUANTITY > 0
```

---

# 3. Execution Event Hierarchy

The canonical sequence is:

```text DECISION
    |
    v
ORDER_INTENT
    |
    v
ORDER_SUBMITTED
    |
    v
ORDER_ACKNOWLEDGED
    |
    +------> REJECTED
    |
    +------> CANCELLED
    |
    +------> PARTIALLY_FILLED
    |
    +------> FILLED
```

Not every order necessarily passes through every state.

But every actual fill must originate from an identifiable order lifecycle.

---

# 4. Decision

A trading decision produces:

```text DecisionID
TradeID
Action
Instrument
DesiredQuantity
DecisionTimestamp
ModelVersion
ParameterVersion
DecisionStateSnapshot
```

The decision means:

```text "Under the information available at this moment,
the strategy wants this transaction."
```

It does not mean:

```text "The transaction happened."
```

---

# 5. Order Intent

The order-intent layer converts the decision into an executable request.

Conceptually:

```text ORDER_INTENT
=
Decision
+
ExecutionPolicy
```

It specifies:

```text Instrument
Side
DesiredQuantity
OrderType
PriceConstraint
Validity
ExecutionPolicy
TradeID
```

The exact broker-specific fields remain pending.

---

# 6. Desired Quantity

The desired quantity is determined before execution.

For example:

```text DesiredQuantity = Q
```

But:

```text ActualFilledQuantity <= Q
```

unless an explicit order modification increases the requested quantity.

The system never assumes:

```text ActualFilledQuantity = DesiredQuantity.
```

---

# 7. Order Identity

Every submitted order receives:

```text OrderID
```

The OrderID is distinct from:

```text TradeID
DecisionID
FillID
```

These identities must never be conflated.

---

# 8. Identity Relationship

The canonical relationship is:

```text DecisionID
     |
     v
TradeID
     |
     +------ OrderID_1
     |
     +------ OrderID_2
     |
     +------ OrderID_3
              |
              +------ FillID_1
              +------ FillID_2
```

One trade can therefore contain:

```text multiple orders
multiple fills
partial executions
cancellations
replacement orders
```

---

# 9. Order Submission

Once the execution policy accepts the order intent:

```text ORDER_SUBMITTED
```

is recorded.

At this instant:

```text PositionQuantity
```

does not change.

---

# 10. Order Acknowledgement

A broker acknowledgement establishes:

```text the order was received/accepted according to broker semantics.
```

It does not establish:

```text execution.
```

Therefore:

```text ACKNOWLEDGED
```

does not imply:

```text ACTIVE_POSITION.
```

---

# 11. Rejection

If the broker rejects the order:

```text ORDER_REJECTED
```

then:

```text ActualFilledQuantity = 0
```

unless there are already independently confirmed fills associated with the order.

The strategy must reconcile actual execution rather than assume zero merely because the final status says rejected.

---

# 12. Partial Fill

Suppose:

```text DesiredQuantity = 100
```

and:

```text Fill_1 = 30
```

Then:

```text ActualPositionQuantity = 30
RemainingOrderQuantity = 70
```

The strategy now has genuine exposure.

The trade lifecycle becomes active.

---

# 13. Multiple Fills

Suppose:

```text Fill_1 = 30
Fill_2 = 20
Fill_3 = 50
```

Then:

```text TotalExecutedQuantity = 100
```

The position is fully established.

The execution engine must retain all individual fills.

It must not retain only:

```text "100 filled"
```

because individual fill timestamps and prices matter for execution analysis.

---

# 14. Average Entry Price

For fills:

```text q1 at p1
q2 at p2
...
qn at pn
```

the execution-weighted average entry price is:

```text
P_entry
=
Σ(q_i × p_i) / Σq_i
```

subject to the final accounting convention.

This is an execution-derived quantity.

---

# 15. Entry Price Is Not Signal Price

The system must distinguish:

```text SignalPrice
DecisionPrice
OrderPrice
FillPrice
MarkPrice
```

These can all differ.

That distinction is mandatory for realistic P&L.

---

# 16. Execution Latency

There are multiple temporal points:

```text T_decision
T_order_creation
T_submission
T_acknowledgement
T_fill
```

The differences between them define execution latency.

At minimum:

```text DecisionToFillLatency
=
T_fill - T_decision
```

must be observable or modeled.

---

# 17. Historical Execution Limitation

If historical data does not provide sufficient information to reconstruct actual execution latency, the backtest must not pretend that it does.

Instead, the execution model must explicitly state:

```text observed
estimated
assumed
unavailable
```

for every execution quantity.

---

# 18. Last Price Is Not Automatically Executable Price

This is one of the most important rules.

Suppose:

```text LastPrice = 100
```

That does not prove that a marketable buy order could execute at:

```text 100.
```

The executable price depends on:

```text bid
ask
available liquidity
order type
queue/market mechanics
latency
```

subject to what the historical dataset can actually establish.

---

# 19. Bid/Ask

For an immediately executable long entry:

the relevant side of the market is generally the offer/ask rather than an arbitrary last traded price.

For liquidation of a long position:

the relevant executable side is generally the bid.

The exact execution convention must follow the available historical quote semantics.

---

# 20. Mid-Price

The midpoint:

```text Mid = (Bid + Ask) / 2
```

may be useful for valuation.

But:

```text Mid != guaranteed execution price.
```

Therefore the system must distinguish:

```text MarkPrice
```

from:

```text ExecutablePrice.
```

---

# 21. Option Execution

This distinction becomes especially important for options.

An option can have:

```text underlying movement
+
favorable theoretical valuation
```

while simultaneously having:

```text poor liquidity
+
wide spread
+
insufficient executable quantity.
```

Therefore the strategy cannot treat underlying directional correctness as equivalent to option trade profitability.

---

# 22. Entry Cost

The actual entry economic cost is:

```text EntryCost
=
ExecutedQuantity
×
ActualFillPrice
+
ApplicableTransactionCosts
```

The exact transaction-cost components remain a data/broker contract.

---

# 23. Exit Cost

Similarly:

```text ExitProceeds
=
ExecutedQuantity
×
ActualExitFillPrice
-
ApplicableExitCosts
```

The exact accounting treatment will be finalized with the broker contract.

---

# 24. Realized P&L

For a completed long option trade:

```text RealizedPnL
=
NetExitProceeds
-
NetEntryCost
```

subject to the final fee/tax/accounting specification.

This is based on actual fills.

---

# 25. Mark-to-Market P&L

Before exit:

```text CurrentPnL
```

is based on the chosen current valuation convention.

The valuation convention must be explicit.

Possible choices include:

```text last traded price
mid
bid
estimated liquidation value
```

The production risk engine should use the economically conservative convention appropriate to the intended action.

The exact choice remains a contract to finalize.

---

# 26. Theoretical Stop Versus Executed Stop

This is critical.

Suppose:

```text ProtectionBoundary = 100
```

and the market moves rapidly from:

```text 100.20
```

to:

```text 98.80.
```

The fact that the protection condition was crossed at:

```text 100
```

does not guarantee an execution at:

```text 100.
```

The strategy records:

```text TriggerPrice
```

and separately:

```text ActualFillPrice.
```

---

# 27. Gap Through Protection

If:

```text TriggerPrice = 100
```

but the first executable price is:

```text 98.80,
```

then:

```text ActualExitPrice = 98.80.
```

The system does not manufacture:

```text 100.
```

---

# 28. Protection Slippage

Define:

```text ProtectionSlippage
=
ActualExitPrice
-
ExpectedProtectionExecutionPrice
```

with the sign convention determined by the position direction.

This becomes an execution-quality measurement.

---

# 29. Stop Triggering and Stop Execution Are Separate

The lifecycle is:

```text MARKET EVENT
     |
     v
PROTECTION CONDITION SATISFIED
     |
     v
EXIT OBLIGATION
     |
     v
ORDER SUBMITTED
     |
     v
ACTUAL EXECUTION
```

These are four distinct causal stages.

---

# 30. No Instantaneous Exit Assumption

The backtest must not collapse:

```text trigger
```

and:

```text fill
```

into the same timestamp unless the available data genuinely supports that assumption.

This prevents artificially favorable exits.

---

# 31. Intrabar Ambiguity

If historical data is bar-based and a bar contains both:

```text protection trigger
```

and:

```text favorable target
```

but the ordering of those events is unknown, the system cannot simply select whichever produces the better result.

It must use a conservative or explicitly defined intrabar-resolution rule.

---

# 32. Tick Data Advantage

Because we possess higher-resolution data, the intended model can potentially reconstruct event ordering more accurately.

But:

```text higher resolution != perfect execution knowledge.
```

If the underlying feed still lacks order-book/execution information, uncertainty remains.

---

# 33. Execution Uncertainty

Every historical execution quantity should conceptually have a status:

```text OBSERVED
RECONSTRUCTED
MODELED
ASSUMED
UNKNOWN
```

Production-grade validation should distinguish them.

---

# 34. Unknown Execution

If a critical execution quantity is unknowable from the historical data:

the backtest must not silently assign an optimistic value.

The trade may instead be:

```text excluded
conservatively modeled
stress-tested
```

according to the validation contract.

---

# 35. Execution Cost Distribution

Instead of assuming one fixed slippage value, historical analysis can eventually estimate:

```text SlippageDistribution
```

conditioned on:

```text time of day
spread
volatility
option liquidity
order size
market state
```

But the conditional model must itself survive out-of-sample validation.

---

# 36. Slippage Cannot Use Future Information

For a historical order at:

```text t
```

the execution-cost estimate available at `t` cannot depend on:

```text future spread
future volatility
future fill outcome.
```

Actual historical fill outcomes may later be used for learning future execution models, but not for reconstructing the original decision.

---

# 37. Execution Model Learning

The system can eventually learn:

```text ExpectedSlippage_t
```

from historical execution observations.

This follows the same walk-forward framework as the predictive model.

It does not become an oracle.

---

# 38. Order Size Dependence

Execution quality may depend on:

```text OrderQuantity / AvailableLiquidity.
```

Therefore:

```text larger order
```

cannot automatically be assumed to have the same slippage distribution as:

```text smaller order.
```

This is another reason position sizing and execution cannot be treated as independent.

---

# 39. Position Sizing Feedback

At entry:

```text PositionSize
```

is selected using risk and economics.

But the selected size must also pass:

```text ExecutionFeasibility.
```

Therefore:

```text theoretical size
```

and:

```text executable size
```

are distinct.

---

# 40. Insufficient Liquidity

If the desired size cannot be executed under the admissibility contract:

the system may:

```text reduce quantity
```

only if partial-sizing behavior was explicitly authorized.

Otherwise:

```text NO_TRADE.
```

The system cannot silently choose a different size after seeing the outcome.

---

# 41. Partial Entry and Risk

If only part of the intended order fills:

```text ActualQuantity < DesiredQuantity.
```

Risk calculations immediately use:

```text ActualQuantity.
```

not:

```text DesiredQuantity.
```

---

# 42. Partial Entry Protection

Once exposure exists, the active position requires protection.

Protection must therefore be based on:

```text actual exposure
```

rather than requested exposure.

---

# 43. Remaining Entry Order

If:

```text DesiredQuantity = 100
Filled = 40
Remaining = 60
```

the strategy must separately manage:

```text existing exposure = 40
```

and:

```text pending order = 60.
```

These are different objects.

---

# 44. Entry Order Cancellation

If continuation collapses while:

```text 40 units are filled
60 remain pending,
```

the system cannot treat cancellation of the remaining 60 as an exit of the existing 40.

The 40-unit position remains independently active.

---

# 45. Partial Exit

Likewise, if:

```text 100 units active
40 exit-filled,
```

then:

```text 60 units remain active.
```

The trade is not closed.

---

# 46. Exit Replacement

If an exit order is cancelled and replaced:

```text OrderID_1
```

and:

```text OrderID_2
```

remain separate order objects.

Both must reference the same:

```text TradeID.
```

The execution ledger must prevent double-counting.

---

# 47. Cancellation Race

A cancellation request does not necessarily mean:

```text order is cancelled.
```

The market may fill the order before cancellation is confirmed.

Therefore:

```text CANCEL_REQUESTED
```

is not:

```text CANCELLED.
```

The system waits for authoritative status or reconciles actual fills.

---

# 48. Fill Race

If the system simultaneously receives:

```text cancellation acknowledgement
```

and:

```text fill event,
```

the final exposure is determined from authoritative execution facts and reconciliation.

The strategy cannot simply assume:

```text cancellation won.
```

---

# 49. Duplicate Fill

If the same fill is delivered twice:

```text FillID
```

must make processing idempotent.

The quantity cannot be added twice.

---

# 50. Corrected Fill

If the broker/source later corrects:

```text fill quantity
fill price
fill identity
```

the system must process an explicit correction event.

It must not silently mutate the historical fill.

---

# 51. Execution Ledger

The canonical execution ledger contains:

```text OrderID
TradeID
FillID
OrderTimestamp
SubmissionTimestamp
AcknowledgementTimestamp
FillTimestamp
RequestedQuantity
ExecutedQuantity
RemainingQuantity
RequestedPrice
ActualFillPrice
OrderStatus
ExecutionStatus
SourceEventID
```

Exact fields remain subject to broker/TrueData documentation.

---

# 52. Position Ledger

The position ledger is derived from authoritative fills.

Conceptually:

```text PositionQuantity_t
=
Σ BuyFills_t
-
Σ SellFills_t
```

for the relevant instrument and trade context.

The position is therefore an accounting consequence of execution.

---

# 53. Position Reconciliation

At any point:

```text InternalPositionQuantity
```

must be compared with:

```text AuthoritativeBrokerPositionQuantity.
```

If they disagree:

```text RECONCILIATION_REQUIRED.
```

---

# 54. No Synthetic Position

The system cannot create:

```text PositionQuantity = DesiredQuantity
```

simply because an order exists.

This is forbidden.

---

# 55. Execution and Strategy Separation

The strategy decides:

```text WHAT it wants to do.
```

The execution layer decides:

```text HOW the requested transaction is attempted.
```

The broker determines:

```text WHAT actually happened.
```

The accounting layer determines:

```text WHAT exposure actually exists.
```

These layers must remain separate.

---

# 56. Execution Cannot Change Directional Prediction

A poor fill does not mean:

```text bearish prediction.
```

An excellent fill does not mean:

```text bullish prediction.
```

Execution outcome and predictive outcome are separate analytical dimensions.

---

# 57. Execution Cost Does Affect Economic Decision

Although execution does not determine direction:

```text ExpectedExecutionCost
```

does affect:

```text ExpectedNetValue.
```

Therefore a valid prediction can still result in:

```text NO_TRADE
```

because execution economics are unfavorable.

---

# 58. Entry Cost Gate

Conceptually:

```text ExpectedNetValue
=
ExpectedGrossValue
-
ExpectedExecutionCost.
```

The trade is admissible only if the resulting economic value satisfies the validated decision rule.

---

# 59. Exit Cost

Similarly, an apparently attractive continuation can become unattractive after considering:

```text expected exit cost
```

especially for short-horizon trades.

This is one reason the system must distinguish:

```text micro-scalp
```

from:

```text intraday.
```

The shorter the expected opportunity, the more execution friction can dominate the expected edge.

---

# 60. Dynamic Mode and Execution

Mode transitions therefore do not merely represent price behavior.

They also affect the relevance of:

```text expected holding duration
execution friction
expected opportunity
```

But they still cannot alter established risk boundaries.

---

# 61. Emergency Exit Execution

An emergency reversal generates:

```text ExitObligation
```

not:

```text guaranteed fill.
```

The execution layer then attempts the exit according to the emergency execution policy.

---

# 62. Execution Failure During Emergency

If the emergency exit cannot execute:

```text position remains exposed.
```

The state remains:

```text ACTIVE_EXIT_REQUIRED.
```

The system may escalate according to the operational execution policy.

The analytical model cannot simply declare:

```text trade closed.
```

---

# 63. Session-End Execution

Session-end closure follows the same principle.

The strategy may require:

```text exit.
```

But the position is not considered closed until:

```text actual exit execution
+
reconciliation.
```

---

# 64. Execution Priority

When multiple orders compete for the same exposure, the system must prevent contradictory execution instructions.

For example:

```text normal exit order
+
emergency exit order
```

cannot both independently create double-selling.

The execution coordinator must reconcile the outstanding orders against actual exposure.

---

# 65. Maximum Exit Quantity

At all times:

```text TotalOutstandingExitQuantity
+
ActualExitFilledQuantity
<=
CurrentPositionQuantity
```

unless the broker explicitly supports another mechanism and the accounting model handles it.

This protects against accidental over-exit.

---

# 66. No Negative Position

For the baseline long-option architecture:

```text PositionQuantity >= 0.
```

An execution event that would produce:

```text PositionQuantity < 0
```

is an invariant violation requiring reconciliation.

---

# 67. Entry and Exit Race

A particularly dangerous case:

```text exit obligation established
```

while:

```text an entry order remains partially pending.
```

The system must cancel or otherwise resolve the outstanding entry exposure according to the execution contract before treating the trade as cleanly exiting.

The system must never accidentally:

```text add exposure
```

while trying to reduce it.

---

# 68. Execution State Machine

The canonical order lifecycle is:

```text ORDER_INTENT
      |
      v
SUBMISSION_REQUESTED
      |
      v
SUBMITTED
      |
      v
ACKNOWLEDGED
      |
      +-----------> REJECTED
      |
      +-----------> CANCEL_REQUESTED
      |                    |
      |                    +--> CANCELLED
      |                    |
      |                    +--> FILLED/PARTIAL
      |
      +-----------> PARTIALLY_FILLED
      |                    |
      |                    +--> FILLED
      |                    +--> CANCELLED
      |
      +-----------> FILLED
```

Unknown or contradictory status:

```text RECONCILIATION_REQUIRED.
```

---

# 69. Execution State Versus Position State

These remain separate.

For example:

```text OrderState = PARTIALLY_FILLED
PositionState = ACTIVE
```

is valid.

Similarly:

```text OrderState = CANCELLED
PositionState = ACTIVE
```

is valid if a previous partial fill created exposure.

This distinction is critical.

---

# 70. Execution Model in Historical Replay

The historical engine must reconstruct:

```text decision
    ↓
execution attempt
    ↓
estimated/observed execution
    ↓
position
```

with every assumption explicitly recorded.

If exact execution cannot be reconstructed, the uncertainty must be represented rather than hidden.

---

# 71. Execution Stress Testing

The backtest should eventually test:

```text normal slippage
moderate slippage
high slippage
spread widening
latency
partial fills
fill rejection
gap-through-stop
liquidity collapse
```

The strategy should not be considered robust merely because its idealized execution backtest is profitable.

---

# 72. Execution Robustness Criterion

The strategy's edge must survive plausible execution deterioration.

Conceptually:

```text Edge_after_cost
>
0
```

under the validated range of execution conditions.

The exact stress ranges will be determined from actual historical execution data.

---

# 73. Theoretical Versus Executable Profit

We now formally distinguish:

```text TheoreticalPnL
```

from:

```text ExecutedPnL.
```

Theoretical P&L answers:

```text What would valuation indicate?
```

Executed P&L answers:

```text What did actual fills produce?
```

Production performance is based on the latter.

---

# 74. Execution Attribution

After a trade closes, P&L can conceptually be decomposed into:

```text DirectionalEdge
+
OptionTranslation
+
ExecutionImpact
+
Costs
+
TimingImpact
```

The exact decomposition will be defined later.

This is important because a profitable trade does not necessarily prove that the predictive model was correct.

---

# 75. Execution Quality Metrics

The execution subsystem should eventually calculate:

```text FillRate
AverageSlippage
WorstSlippage
DecisionToFillLatency
SpreadAtDecision
SpreadAtFill
PartialFillRate
RejectionRate
CancellationRate
```

These are diagnostic and may later become learning inputs.

They are not automatically strategy features.

---

# 76. No Retrospective Execution Optimization

After seeing historical fills, we cannot change:

```text historical fill price
```

to make the backtest better.

Instead, execution improvements become:

```text candidate execution policy
```

for future walk-forward periods.

---

# 77. Execution Policy Versioning

The execution policy itself receives:

```text ExecutionPolicyVersion.
```

A trade retains the version used when its order was generated.

This provides complete provenance.

---

# 78. Data Boundary

The exact execution model depends heavily on what the authoritative data actually provides.

Therefore these remain explicit TODOs:

```text Exact quote semantics
Exact bid/ask availability
Exact depth availability
Exact tick sequencing
Exact historical option quote coverage
Exact order-book reconstruction capability
Exact broker execution events
Exact fill timestamps
Exact cancellation semantics
Exact correction semantics
```

We will not invent them.

---

# 79. Critical Backtest Rule

If the data cannot establish that an execution occurred at a particular price:

```text that price cannot be treated as observed fact.
```

It must be classified as:

```text modeled
```

or:

```text assumed.
```

This distinction must survive into the final performance report.

---

# 80. Canonical Execution Contract

The complete causal chain is therefore:

```text SIGNAL
   |
   v
DECISION
   |
   v
ORDER INTENT
   |
   v
ORDER
   |
   v
BROKER STATUS
   |
   v
FILL(S)
   |
   v
POSITION
   |
   v
MARK-TO-MARKET
   |
   v
EXIT OBLIGATION
   |
   v
EXIT ORDER
   |
   v
EXIT FILL(S)
   |
   v
ZERO EXPOSURE
   |
   v
RECONCILIATION
   |
   v
REALIZED P&L
```

No stage may be skipped conceptually.

---

# 81. Formal Execution Invariants

The following are now canonical:

```text EXEC-001
No position without actual fill.

EXEC-002
Order acknowledgement does not imply execution.

EXEC-003
Requested quantity does not imply executed quantity.

EXEC-004
Signal price does not imply fill price.

EXEC-005
Trigger price does not imply exit price.

EXEC-006
Cancellation request does not imply cancellation.

EXEC-007
Partial fill creates partial exposure.

EXEC-008
Partial exit does not close the trade.

EXEC-009
Duplicate fill events are idempotent.

EXEC-010
Contradictory execution state requires reconciliation.

EXEC-011
Actual position quantity derives from authoritative fills.

EXEC-012
Realized P&L derives from actual exit execution.

EXEC-013
Execution uncertainty cannot be silently converted into favorable assumptions.

EXEC-014
Outstanding orders cannot collectively create exposure greater than permitted quantity.

EXEC-015
A trade cannot be declared closed while authoritative exposure remains non-zero.
```

---

# 82. Architecture Status

The execution boundary is now substantially specified.

We have:

```text Decision model                 COMPLETE
Trade lifecycle                   COMPLETE
Execution conceptual model        COMPLETE
Order lifecycle                   COMPLETE
Fill accounting                   COMPLETE
Partial-fill semantics            COMPLETE
Protection-trigger semantics      COMPLETE
Reconciliation semantics          COMPLETE
Execution invariants              COMPLETE
```

Remaining external contracts:

```text TrueData quote semantics
TrueData depth semantics
TrueData historical execution data
Broker order semantics
Broker fill semantics
Broker cancellation semantics
Transaction-cost schedule
```

---

# 83. Next Artifact

We have now defined:

```text WHAT the strategy predicts
HOW it decides
HOW one trade lives
HOW orders become fills
HOW fills become positions
HOW positions become P&L
HOW trades become learning observations
```

The next missing mathematical layer is therefore **not another trading rule**.

It is the:

# CANONICAL PERFORMANCE, RISK, AND ATTRIBUTION SPECIFICATION

That will define precisely how we judge whether the entire system actually has an edge.

It will separate:

```text prediction quality
from
trade quality
from
execution quality
from
risk-adjusted profitability
from
statistical significance
```

and, critically, prevent us from declaring the strategy "elite" merely because one backtest produced a high return.

That is the next artifact.