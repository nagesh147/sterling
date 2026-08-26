# EXIT AND EXECUTION STATE SPECIFICATION

## Canonical Execution Contract — Version 1.0

## 1. Purpose

This specification defines the complete transition from:

```text
POSITION_ACTIVE
```

to:

```text
TRADE_CLOSED
```

while preserving the strategy's risk invariants despite execution uncertainty.

The complete chain is:

```text
LIVE POSITION
      |
      v
EXIT CONDITION DETECTED
      |
      v
EXIT AUTHORIZED
      |
      v
EXIT ORDER CREATED
      |
      v
EXIT ORDER SUBMITTED
      |
      +----> REJECTED
      |
      +----> PARTIALLY FILLED
      |
      +----> FILLED
      |
      v
POSITION REDUCED / CLOSED
      |
      v
TRADE FINALIZED
```

---

# 2. Fundamental Principle

The strategy controls:

```text
decision
risk boundary
order intent
```

The market controls:

```text
actual execution price
execution timing
available liquidity
fill quantity
```

Therefore the strategy must never confuse:

```text intended exit
```

with:

```text actual exit.
```

---

# 3. Exit Decision

At timestamp `t`:

```text
ExitDecision_t
```

is generated when one or more exit conditions become true.

Possible causes:

```text
HARD_RISK_BREACH
THESIS_FAILURE
ECONOMIC_DECAY
SESSION_TERMINATION
DATA_INTEGRITY_FAILURE
EXECUTION_SAFETY_FAILURE
```

---

# 4. Exit Decision Is Immutable

Once the system records:

```text EXIT_AUTHORIZED
```

the historical decision cannot later be rewritten.

Later information may create a new decision, but it cannot erase the fact that the exit condition was previously detected.

---

# 5. Exit Priority

The semantic priority remains:

```text
HARD_RISK
    >
THESIS_FAILURE
    >
ECONOMIC_DECAY
    >
ORDINARY_OPTIMIZATION
```

If several conditions occur simultaneously, the highest-priority reason is retained as the primary reason.

All additional reasons are retained as secondary evidence.

---

# 6. Exit Intent

The system creates:

```text ExitIntent_t
```

containing at minimum:

```text TradeID
exit_reason
trigger_timestamp
position_quantity
current_position_state
protection_boundary
current_mark
execution_state
decision_version
```

---

# 7. Quantity to Exit

The requested exit quantity is:

```text ExitQuantity
=
CurrentFilledPositionQuantity
```

unless the risk engine explicitly defines a partial liquidation.

The baseline strategy does not assume discretionary partial exits.

---

# 8. Exit Order

The execution layer transforms:

```text ExitIntent
```

into:

```text ExitOrder
```

The order must specify:

```text instrument
side
quantity
order_type
price constraints
validity
execution policy
```

according to the broker/exchange contract.

---

# 9. Order Type Is Not Hard-Coded

We should not universally specify:

```text MARKET
```

or:

```text LIMIT
```

as the permanent answer.

The correct execution policy depends on:

```text urgency
liquidity
spread
volatility
risk severity
time remaining
```

---

# 10. Execution Urgency

The exit engine classifies the exit:

```text NORMAL
URGENT
EMERGENCY
```

This classification affects execution policy.

---

# 11. Normal Exit

A normal economic exit occurs when:

```text continuation value has decayed
```

but there is no immediate hard-risk violation.

The system can consider execution quality while still enforcing a bounded exit process.

---

# 12. Urgent Exit

An urgent exit occurs when:

```text thesis failure
```

or another rapidly deteriorating condition exists.

Execution latency becomes more important than optimizing a small amount of price improvement.

---

# 13. Emergency Exit

Emergency exit occurs when:

```text hard risk boundary is breached
```

or another catastrophic execution condition exists.

The primary objective becomes:

```text reduce exposure as quickly as safely possible.
```

---

# 14. Risk Priority

For emergency exits:

```text execution quality
```

is secondary to:

```text exposure reduction.
```

This is essential.

Trying to save a few ticks while a hard risk boundary is being breached can produce a much larger loss.

---

# 15. Exit Authorization

Before submitting an exit order:

```text Position still exists?
```

must be checked.

If:

```text quantity = 0
```

the exit order must not be submitted.

---

# 16. Duplicate Exit Prevention

If an exit order is already actively working:

```text EXIT_PENDING
```

the system must not blindly submit another identical exit order.

It must reconcile:

```text current position
+
working orders
+
actual fills.
```

---

# 17. Execution State Machine

Canonical:

```text
POSITION_ACTIVE
      |
      v
EXIT_AUTHORIZED
      |
      v
EXIT_SUBMITTED
      |
      +----------+
      |          |
      v          v
REJECTED     PARTIALLY_FILLED
      |             |
      |             v
      |        EXIT_REMAINING
      |             |
      |             v
      |          FILLED
      |             |
      +-------------+
                    |
                    v
              POSITION_CLOSED
```

---

# 18. Order Rejection

If the broker rejects the exit order:

```text Position remains active.
```

This is a critical condition.

The system must not record:

```text trade closed
```

until actual fills prove closure.

---

# 19. Exit Rejection Is Not Harmless

If the rejection occurs during:

```text HARD_RISK_EXIT
```

the system enters:

```text EXECUTION_EMERGENCY
```

and immediately follows the validated fallback execution policy.

---

# 20. Fallback Policy

The fallback sequence must be predetermined.

Conceptually:

```text Primary Exit
      |
      v
Failure?
      |
      v
Fallback Execution
      |
      v
Failure?
      |
      v
Emergency Procedure
```

The exact order types and retry rules must be established from actual broker capabilities.

---

# 21. No Infinite Retry

The system must never do:

```text retry
retry
retry
retry
...
```

without a bounded policy.

Every retry consumes:

```text time
+
market opportunity
+
risk capacity.
```

---

# 22. Retry State

Each attempt records:

```text attempt_number
timestamp
order_type
requested_price
requested_quantity
response
fill_quantity
fill_price
```

---

# 23. Partial Fill

Suppose:

```text position = 100 units
```

and the exit order fills:

```text 40 units.
```

Then:

```text remaining_position = 60.
```

The system remains:

```text POSITION_ACTIVE
```

until the remaining quantity is actually closed.

---

# 24. Partial Fill Risk

A partial fill can leave significant exposure.

Therefore the risk state is recalculated using:

```text remaining_quantity
+
current_market_state
+
current_protection.
```

---

# 25. Partial Fill Is a Real State

It must not be represented merely as:

```text exit = true.
```

The actual state is:

```text EXIT_PARTIALLY_FILLED.
```

---

# 26. Remaining Exit Quantity

At any moment:

```text RemainingExitQuantity
=
CurrentPositionQuantity
-
ExitFilledQuantity
```

using the canonical position ledger.

---

# 27. Fill Truth

The only authoritative quantity is:

```text actual broker/exchange fill.
```

The system must never infer:

```text order submitted = order filled.
```

---

# 28. Actual Exit Price

For multiple fills:

```text ExitPrice
=
Σ(exit_fill_price_i × exit_fill_quantity_i)
/
Σ(exit_fill_quantity_i)
```

---

# 29. Realized P&L

After final closure:

```text RealizedPnL
=
ActualExitValue
-
ActualEntryValue
-
AllApplicableCosts
```

using actual fills.

---

# 30. No Mode Influence on Realized P&L

The final realized P&L is an execution fact.

It does not depend on whether the trade was:

```text MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

at exit.

---

# 31. Mode Attribution

However, the trade record retains:

```text EntryMode
ModeTransitionHistory
FinalMode
```

so later research can determine:

```text which modes generated value
```

without changing the accounting.

---

# 32. Slippage

Exit slippage is:

```text ActualExitPrice
-
ReferenceExecutableExitPrice
```

with sign normalized according to the position direction.

For a long option:

worse-than-reference execution reduces realized P&L.

---

# 33. Execution Cost

The final trade cost is:

```text EntryCosts
+
ExitCosts
+
Slippage
+
OtherApplicableCharges
```

where the exact cost definitions come from the execution/data contract.

---

# 34. Exit Decision Price Versus Actual Price

These must remain separate:

```text DecisionMark
ActualExitPrice
```

This distinction allows us to measure:

```text decision quality
```

separately from:

```text execution quality.
```

---

# 35. Execution Attribution

A losing trade can therefore be decomposed into:

```text Forecast error
+
Economic model error
+
Execution cost
+
Slippage
+
Risk-management outcome.
```

This is critical for strategy improvement.

---

# 36. Exit Latency

Define:

```text ExitLatency
=
ActualExitTimestamp
-
ExitDecisionTimestamp
```

This becomes a measurable quantity.

---

# 37. Latency Cost

The system can calculate:

```text OpportunityLostDueToLatency
```

where future market movement after the decision explains part of the difference between:

```text theoretical decision exit
```

and:

```text actual execution.
```

---

# 38. Emergency Latency

For hard-risk exits:

latency itself becomes a risk metric.

The system must record:

```text detection time
authorization time
submission time
exchange acknowledgement
first fill
final fill
```

---

# 39. Execution Timeline

Canonical:

```text MarketEvent
    |
    v
RiskConditionDetected
    |
    v
ExitDecision
    |
    v
ExitAuthorization
    |
    v
OrderSubmission
    |
    v
ExchangeAcknowledgement
    |
    v
FirstFill
    |
    v
FinalFill
```

Every timestamp is retained.

---

# 40. Stale Exit Order

An exit order can become stale when:

```text market conditions materially change
```

while it remains unfilled.

The execution engine must therefore evaluate whether:

```text current order
```

still satisfies the active exit policy.

---

# 41. Cancellation and Replacement

If the execution policy permits:

```text cancel
+
replace
```

the system may update the working order.

But:

```text risk authorization
```

must remain active until exposure is actually reduced.

---

# 42. No Risk Reset During Replacement

A cancelled order does not mean:

```text risk is gone.
```

The position remains exposed until an actual fill occurs.

---

# 43. Protection During Exit Pending

While an exit order is working:

```text Position remains economically active.
```

Therefore:

```text protection logic
```

continues to exist.

---

# 44. Exit Pending Does Not Freeze Market Risk

Suppose:

```text exit order submitted
```

but:

```text no fill yet.
```

The market can still move against the position.

The system must therefore retain emergency execution authority.

---

# 45. Exit Escalation

Conceptually:

```text EXIT_PENDING
      |
      v
Execution progress?
   /          \
 YES           NO
 |              |
 v              v
continue       escalate
```

The exact escalation criteria are empirical/execution-specific.

---

# 46. Hard-Risk Escalation

If a hard risk boundary is breached while an exit order is already working:

the system must prioritize:

```text maximum feasible exposure reduction.
```

It must not wait passively for the original order.

---

# 47. Multiple Exit Orders

The system must prevent accidental over-execution.

Before submitting another order:

```text CurrentPosition
+
WorkingExitOrders
```

must be reconciled.

The total requested exit quantity cannot exceed actual remaining position quantity.

---

# 48. Position Reconciliation

At each execution event:

```text BrokerPosition
```

is compared with:

```text InternalPosition
```

---

# 49. Reconciliation Failure

If:

```text BrokerPosition != InternalPosition
```

the system enters:

```text POSITION_RECONCILIATION_ERROR.
```

This is a high-priority state.

---

# 50. Why

A strategy cannot safely calculate risk if it does not know how many contracts it actually owns.

Therefore:

```text position truth
```

takes precedence over:

```text model optimization.
```

---

# 51. Internal State Cannot Override Broker Truth

If the internal system says:

```text quantity = 100
```

but the broker confirms:

```text quantity = 60
```

then the actual exposure is:

```text 60.
```

The internal state must reconcile to the authoritative execution record.

---

# 52. Unknown Position State

If the system cannot reliably determine the actual position:

```text POSITION_UNKNOWN.
```

It must not continue normal strategy optimization.

---

# 53. Position Unknown Response

The system enters:

```text PROTECTIVE_ONLY
```

or the broker-supported emergency resolution path.

The objective becomes:

```text determine and reduce actual exposure safely.
```

---

# 54. Data Failure During Exit

If market data becomes unavailable during a pending exit:

the system cannot assume:

```text no market movement.
```

Execution-state information remains authoritative.

---

# 55. Broker Connectivity Failure

If broker connectivity is lost:

```text strategy cannot assume order status.
```

The position becomes:

```text EXECUTION_STATE_UNKNOWN.
```

---

# 56. Recovery Procedure

Upon reconnection:

```text Query broker
      |
      v
Retrieve actual orders
      |
      v
Retrieve actual position
      |
      v
Reconcile
      |
      v
Restore internal state
```

---

# 57. No Duplicate Orders After Recovery

Before submitting any new order after reconnect:

the system must first reconcile:

```text positions
+
working orders
+
fills.
```

This prevents duplicate exits.

---

# 58. Market Halt

If trading in the instrument becomes unavailable:

```text execution cannot occur.
```

The strategy cannot mathematically manufacture an exit.

Instead:

```text POSITION_EXECUTION_BLOCKED
```

is recorded.

Risk state continues to be tracked using whatever valid information remains available.

---

# 59. Gap/Reopen

When trading resumes:

the system must immediately reconcile:

```text current market
+
position
+
working orders
+
protection state.
```

It must not assume the previous price relationship still holds.

---

# 60. Expiry Risk

Because the strategy trades options:

the system must explicitly prevent a position from reaching an unintended expiry lifecycle.

The baseline strategy is intraday.

Therefore:

```text no overnight carry
```

is a hard lifecycle requirement.

---

# 61. Session Exit

Before the defined session termination boundary:

```text all active positions
```

must enter the closure process.

The actual closure deadline must allow enough execution time under realistic conditions.

---

# 62. No "Close at Last Tick" Assumption

The system must not assume:

```text final market timestamp
=
successful exit.
```

Execution requires actual confirmation.

---

# 63. Exit Confirmation

A trade becomes:

```text TRADE_CLOSED
```

only when:

```text actual_position_quantity == 0
```

is confirmed.

---

# 64. Closed-State Invariant

Once:

```text TRADE_CLOSED
```

is confirmed:

```text active_quantity = 0
```

and:

```text no working exit quantity remains.
```

---

# 65. Final Trade Snapshot

At closure:

```text FinalTradeSnapshot
```

contains:

```text TradeID
EntrySnapshot
ModeHistory
ProtectionHistory
ExitDecisionHistory
ExecutionHistory
EntryFills
ExitFills
RealizedPnL
TotalCosts
ExecutionLatency
ExitReason
```

---

# 66. Exit Reason Hierarchy

The final trade record must distinguish:

```text PrimaryExitReason
SecondaryExitReasons
```

Example:

```text Primary = PROTECTION_BREACH
Secondary = CONTINUATION_DECAY
```

---

# 67. Exit Reason Must Reflect First Causal Trigger

The primary reason should represent the first validated condition that caused the exit authorization.

This avoids post-hoc storytelling.

---

# 68. No Outcome-Based Exit Attribution

Suppose a trade eventually loses money.

We cannot label the exit:

```text bad_signal
```

unless the signal actually triggered the exit.

The exit record reflects the actual state transition.

---

# 69. Execution Failure Is Separate From Strategy Failure

Suppose:

```text strategy correctly decides EXIT
```

but:

```text order suffers extreme slippage.
```

The strategy decision can still be correct.

The system must separately record:

```text strategy outcome
execution outcome.
```

---

# 70. Counterfactual Exit Price

For research, retain:

```text CounterfactualExitPrice
```

representing the executable price available at the decision moment under the validated execution model.

This allows:

```text decision quality
```

to be compared with:

```text execution quality.
```

---

# 71. Execution Loss Decomposition

Conceptually:

```text TotalRealizedPnL
=
DecisionPnL
+
ExecutionDeviation
```

where the exact decomposition includes:

```text forecast component
economic component
timing component
slippage component
transaction cost component.
```

---

# 72. Why This Matters

Without this separation, continuous improvement can make the wrong change.

For example:

```text poor execution
```

could be mistakenly interpreted as:

```text poor signal.
```

That would corrupt learning.

---

# 73. Exit Learning Boundary

The completed trade is not immediately allowed to train every model.

Different outcomes mature at different horizons.

For example:

```text immediate execution outcome
```

may be known quickly.

But:

```text maximum favorable excursion
```

may require a defined observation horizon.

---

# 74. Outcome Maturity

Each trade therefore has:

```text OutcomeMaturityState.
```

A learning variable becomes eligible only when its required observation window is complete.

---

# 75. No Future Leakage

If a label requires:

```text future thirty-minute outcome
```

the trade cannot influence that model until:

```text thirty minutes
```

have actually elapsed after the relevant timestamp.

---

# 76. Exit Execution Does Not End All Labels

A trade may close after:

```text five minutes.
```

But its historical counterfactual outcomes can still mature for research labels.

This distinction is important.

---

# 77. Trade Closure Versus Label Closure

```text TradeClosed
```

means:

```text financial exposure ended.
```

while:

```text LabelMatured
```

means:

```text all required historical outcome observations became available.
```

These are separate states.

---

# 78. Final Execution State Machine

```text
POSITION_ACTIVE
      |
      v
EXIT_AUTHORIZED
      |
      v
EXIT_ORDER_SUBMITTED
      |
      +--------------------+
      |                    |
      v                    v
FILLED                REJECTED
      |                    |
      v                    v
POSITION_REDUCED      FALLBACK
      |                    |
      |              +-----+-----+
      |              |           |
      |              v           v
      |          FILLED       FAILED
      |              |           |
      +--------------+           v
                                 EXECUTION_EMERGENCY
                                        |
                                        v
                                 EXPOSURE REDUCTION
```

---

# 79. Core Execution Invariants

The execution system must guarantee:

```text id="qxxh3h"
1. No position closure without actual fill.
2. No assumed fill.
3. No exit quantity greater than actual position.
4. No duplicate exit orders.
5. No risk reset while exit is pending.
6. No protection relaxation during execution uncertainty.
7. No hidden reconciliation failure.
8. No overnight carry in baseline strategy.
9. No retrospective modification of execution facts.
10. No future information in the exit decision.
```

---

# 80. Complete Position Lifecycle

We now have:

```text
ENTRY
  |
  v
POSITION_ACTIVE
  |
  +--> UPDATE
  |
  +--> MODE TRANSITION
  |
  +--> PROTECTION TIGHTEN
  |
  +--> CONTINUATION REASSESSMENT
  |
  v
EXIT_AUTHORIZED
  |
  v
EXECUTION
  |
  v
POSITION_CLOSED
  |
  v
OUTCOME_MATURATION
  |
  v
LEARNING ELIGIBILITY
```

---

# 81. Architectural Status

The mathematical strategy and execution boundary are now substantially connected.

We have explicitly separated:

```text Prediction
Economic Decision
Position State
Risk Protection
Exit Decision
Order Execution
Actual Fill
Trade Accounting
Historical Learning
```

The next logical artifact is therefore not another trading rule.

It is the **Historical Learning and Walk-Forward Update Specification**.

That layer will define exactly how closed trades and matured historical observations enter the evolving statistical system, how rolling training/validation/test windows move forward through time, how parameters are recalculated without look-ahead, when a new model version becomes active, and—most importantly—how we prevent the strategy from learning from its own future or contaminating the live state with information that would not have existed at that historical timestamp.