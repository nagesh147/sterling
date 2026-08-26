# CANONICAL TRADE LIFECYCLE SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the complete mathematical and operational lifecycle of exactly one trade.

The lifecycle begins when the system has no position and observes a potential opportunity.

It ends only when:

```text
ActualPositionQuantity = 0
+
execution reconciled
+
trade accounting finalized.
```

Only after that does the trade become an eligible historical observation for the learning system, subject to label maturity.

The lifecycle is:

```text
NO_POSITION
    |
    v
OPPORTUNITY_DETECTED
    |
    v
ENTRY_EVALUATION
    |
    v
ENTRY_AUTHORIZED
    |
    v
ORDER_PENDING
    |
    v
PARTIAL/FULL FILL
    |
    v
ACTIVE_POSITION
    |
    v
DYNAMIC_MANAGEMENT
    |
    +--> MODE TRANSITIONS
    +--> PROTECTION TIGHTENING
    +--> PROFIT LOCKING
    +--> CONTINUATION REASSESSMENT
    |
    v
EXIT_OBLIGATION
    |
    v
EXIT_EXECUTION
    |
    v
RECONCILIATION
    |
    v
TRADE_CLOSED
    |
    v
LABEL_MATURATION
    |
    v
LEARNING_ELIGIBILITY
```

---

# 2. Trade Identity

Every trade receives a unique:

```text
TradeID
```

The TradeID is created when the system establishes a new entry lifecycle.

A trade must never reuse the identity of a previous trade.

---

# 3. Trade-Level Immutable Facts

Once established, these become immutable:

```text
TradeID
EntryDirection
EntryInstrument
EntryModelVersion
EntryParameterVersion
EntryAuthorizationTimestamp
ActualEntryFillTimestamp(s)
ActualEntryQuantity
ActualEntryFillPrice(s)
```

Corrections may occur only through an explicit execution-correction mechanism.

Normal market events cannot rewrite them.

---

# 4. Trade-Level Mutable State

The following evolve during the trade:

```text
CurrentQuantity
CurrentPnL
PeakPnL
ProfitGiveback
ProtectionBoundary
CurrentMode
ContinuationState
ProbabilityState
EconomicState
ExecutionState
ExitObligation
```

These are snapshots of the current trade state.

---

# 5. Trade Start Condition

A trade lifecycle can begin only when:

```text CurrentPositionQuantity = 0
```

and:

```text No unresolved previous trade
No reconciliation issue
No system halt
No prohibited session state.
```

---

# 6. Opportunity Detection

An opportunity is not yet a trade.

A market event updates the canonical state.

The system then evaluates whether the current state satisfies the conditions required to evaluate an entry.

Conceptually:

```text MARKET EVENT
     |
     v
STATE UPDATE
     |
     v
ENTRY OPPORTUNITY?
```

If no:

```text remain NO_POSITION.
```

If yes:

```text proceed to ENTRY_EVALUATION.
```

---

# 7. Entry Evaluation

The entry evaluator receives:

```text CurrentMarketState
ProbabilityState
EconomicState
OptionState
RiskCapacity
ExecutionState
SessionState
ActiveModelVersion
ActiveParameterVersion
```

It produces one of:

```text NO_TRADE
BUY_CE_CANDIDATE
BUY_PE_CANDIDATE
```

This is still a decision candidate.

It is not yet an order.

---

# 8. Entry Eligibility

The candidate must pass every mandatory gate:

```text Data valid
Probability valid
Evidence sufficient
Expected value sufficient
Option valid
Liquidity sufficient
Execution conditions acceptable
Risk capacity sufficient
Session valid
No existing exposure
```

If any mandatory gate fails:

```text NO_TRADE.
```

---

# 9. Entry Decision

If a CE candidate passes:

```text ENTRY_DIRECTION = CE
```

If a PE candidate passes:

```text ENTRY_DIRECTION = PE
```

If neither passes:

```text NO_TRADE.
```

The system never creates a trade merely because directional probability is high.

---

# 10. Entry Snapshot

Immediately before order creation, the system records an immutable decision snapshot:

```text DecisionTimestamp
UnderlyingState
ProbabilityState
ExpectedValue
SelectedOption
RiskCapacity
InitialProtectionCandidate
ModelVersion
ParameterVersion
```

This is the historical record of what the system knew when it authorized the trade.

---

# 11. Entry Authorization

The state becomes:

```text ENTRY_AUTHORIZED
```

Authorization is not execution.

The market may change before the order is actually submitted or filled.

---

# 12. Authorization Expiration

An entry authorization must have a validity contract.

If material conditions change before submission:

```text authorization invalidated.
```

The system returns to:

```text NO_POSITION
```

rather than submitting a stale order.

The exact invalidation thresholds remain a calibration/parameter boundary.

---

# 13. Order Intent

Once authorization remains valid:

```text ORDER_INTENT
```

is created.

The order intent specifies:

```text Instrument
Direction
Quantity
Order Type
Price constraints
Execution constraints
TradeID
Decision reference
```

The exact order mechanics remain dependent on the eventual execution contract.

---

# 14. Position Does Not Exist Yet

At this point:

```text ActualPositionQuantity = 0
```

even though an order may exist.

Therefore:

```text ORDER_PENDING != ACTIVE_POSITION.
```

This invariant is absolute.

---

# 15. Order Submission

The order is submitted.

The lifecycle becomes:

```text ENTRY_PENDING.
```

The system now waits for authoritative execution events.

---

# 16. Market Events During Entry Pending

Market events may continue arriving.

They update market state.

However, they cannot pretend that an order was filled.

If the opportunity becomes invalid:

the order-management contract may cancel or modify the pending order where permitted.

Actual exposure remains:

```text based only on actual fills.
```

---

# 17. Zero-Fill Rejection

If the order is rejected or cancelled with:

```text ActualFilledQuantity = 0
```

then:

```text ENTRY_PENDING
    ->
NO_POSITION
```

No trade lifecycle reaches ACTIVE.

---

# 18. Partial Entry Fill

Suppose:

```text RequestedQuantity = Q
FilledQuantity = q
```

where:

```text 0 < q < Q.
```

The strategy now has actual exposure.

Therefore:

```text ActualPositionQuantity = q.
```

The lifecycle becomes:

```text ACTIVE
```

with partial-fill metadata retained.

---

# 19. Full Entry Fill

If:

```text FilledQuantity = RequestedQuantity
```

the position becomes:

```text ACTIVE.
```

The actual entry quantity is the executed quantity.

---

# 20. Entry Price

For multiple entry fills:

```text ActualEntryPrice
```

is the execution-weighted average according to the accounting contract.

It is not:

```text requested price
```

and not:

```text last market price.
```

---

# 21. Entry Time

The trade's actual entry time is determined from execution facts.

It is not:

```text signal timestamp
```

unless those happen to coincide.

This distinction is necessary for:

```text holding time
profit calculation
label construction
execution analysis.
```

---

# 22. Initial Trade State

Once actual exposure exists:

```text CurrentQuantity = ActualFilledQuantity

EntryPrice = execution-derived price

CurrentPnL = initial mark-to-market result

PeakPnL = CurrentPnL

ProfitGiveback = 0

CurrentMode = initial validated mode

ProtectionBoundary = InitialProtection
```

The exact numerical initial protection remains unfrozen.

---

# 23. First Protection Boundary

Initial protection is established from the entry-state contract.

Conceptually:

```text InitialProtection
=
f(
EntryPrice,
VolatilityState,
RiskParameters,
MarketStructure
)
```

For a long option position, the boundary must represent the maximum tolerated adverse movement according to the defined risk contract.

---

# 24. Important Distinction

Initial protection is not necessarily a fixed stop forever.

It is:

```text starting risk boundary.
```

The dynamic management system may subsequently tighten it.

It may never widen it.

---

# 25. First Active Tick

Once the position is active, every subsequent valid event causes:

```text TradeState_(t+1)
=
F(
TradeState_t,
CanonicalEvent_t,
ActiveModel_t
)
```

This is the core tick-by-tick transformation.

---

# 26. Every Tick Does Not Mean Every Variable Changes

An event may update:

```text price
```

while leaving:

```text mode
```

unchanged.

Another may update:

```text probability
```

without changing:

```text protection.
```

Another may trigger:

```text exit.
```

The state transition is therefore component-wise.

---

# 27. Tick Processing Order

For an active position, the conceptual order is:

```text 1. Validate event
2. Update market state
3. Update derived features
4. Update probability
5. Update economic state
6. Update current mark/P&L
7. Update peak P&L
8. Calculate candidate protection
9. Apply protection monotonicity
10. Evaluate hard exit
11. Evaluate emergency exit
12. Evaluate normal exit
13. If no exit, evaluate continuation
14. Evaluate mode
15. Record state transition
```

The exact implementation may optimize computation, but it cannot violate causal dependencies.

---

# 28. Current P&L Update

For a long option position:

```text CurrentPnL_t
=
EconomicValueAt_t
-
ActualEntryCost
```

under the final accounting convention.

The exact marking convention must eventually distinguish:

```text mid-price
bid
last traded price
executable liquidation price
```

This remains an execution/data contract item.

---

# 29. Realized P&L

Realized P&L changes only when an actual exit fill occurs.

A market tick cannot realize profit.

Therefore:

```text MarketMovement
    ->
CurrentPnL

ActualExitFill
    ->
RealizedPnL
```

---

# 30. Peak P&L

After each valid mark:

```text PeakPnL_t
=
max(
PeakPnL_(t-1),
CurrentPnL_t
)
```

This is monotonic.

---

# 31. Profit Giveback

If:

```text CurrentPnL_t < PeakPnL_t
```

then:

```text ProfitGiveback_t
=
PeakPnL_t - CurrentPnL_t
```

This measures deterioration from the best observed trade state.

---

# 32. Protection Candidate

Every active event may produce:

```text CandidateProtection_t.
```

It can depend on:

```text CurrentPrice
Volatility
ATR
CurrentPnL
PeakPnL
ProfitGiveback
Continuation
Mode
Time
LearnedParameters
```

provided every input is causally valid.

---

# 33. Protection Update

The canonical protection rule remains:

```text Protection_t
=
max(
Protection_(t-1),
CandidateProtection_t
)
```

for the long-position baseline.

Therefore:

```text Candidate < Existing
```

does not weaken protection.

---

# 34. Protection Tightening

If:

```text CandidateProtection > ExistingProtection
```

then:

```text Protection = CandidateProtection.
```

The new boundary becomes part of the persistent trade state.

---

# 35. Profit Lock

Suppose:

```text EntryPrice = 100
```

and the protection boundary eventually becomes:

```text 104.
```

Then the trade has established a positive protection boundary.

If subsequent volatility rises:

```text CandidateProtection = 101
```

the actual protection remains:

```text 104.
```

The previously established protection cannot be surrendered.

---

# 36. Mode Evaluation

Only after risk obligations have been evaluated does the strategy reassess mode.

Possible states:

```text MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

The mode represents the currently justified continuation horizon.

---

# 37. Mode Upgrade

A transition such as:

```text SCALP -> INTRADAY
```

requires:

```text continuation evidence
+
validated persistence
+
hysteresis condition
+
no exit obligation.
```

It does not increase position size.

---

# 38. Mode Downgrade

A transition such as:

```text INTRADAY -> SCALP
```

can occur when continuation weakens.

But:

```text Protection_new >= Protection_old.
```

The shorter horizon cannot increase allowable giveback.

---

# 39. Micro-Scalping State

MICRO represents a very short continuation horizon.

It does not mean:

```text smaller risk.
```

It means:

```text shorter expected opportunity horizon.
```

Risk remains governed independently.

---

# 40. Intraday State

INTRADAY means the current statistical evidence supports holding over a broader intraday horizon.

It does not authorize:

```text wider existing protection.
```

Nor does it authorize:

```text additional quantity.
```

---

# 41. Continuation Evaluation

The forward component evaluates:

```text RemainingExpectedOpportunity
```

based on the current state.

Conceptually:

```text ForwardValue_t
=
f(
Probability_t,
ExpectedMagnitude_t,
ExpectedHorizon_t,
Cost_t,
State_t
)
```

The exact learned parameters remain unfrozen.

---

# 42. Backward Protection Evaluation

The backward component evaluates:

```text already-earned value
+
current deterioration
+
protected profit
```

Conceptually:

```text BackwardRisk_t
=
f(
PeakPnL_t,
CurrentPnL_t,
ProfitGiveback_t,
Protection_t
)
```

---

# 43. Forward/Backward Conflict

If:

```text ForwardValue = strong
```

but:

```text protection condition = exit,
```

then:

```text EXIT.
```

Forward opportunity cannot erase backward protection.

---

# 44. Continuation Decision

If:

```text ForwardValue
>
ContinuationThreshold
```

and no higher-priority exit exists:

```text HOLD.
```

If continuation falls below its validated threshold:

```text NORMAL_EXIT_REQUIRED.
```

The threshold is learned.

---

# 45. Emergency Reversal

An emergency reversal occurs when the statistical state indicates a sufficiently strong deterioration inconsistent with the existing directional thesis.

If the validated emergency condition is satisfied:

```text ACTIVE
    ->
ACTIVE_EXIT_REQUIRED
```

It is independent of whether the hard protection boundary has physically been reached.

---

# 46. Hard Protection

If the market reaches or crosses the defined protection condition:

```text ACTIVE
    ->
ACTIVE_EXIT_REQUIRED
```

This has highest trading priority.

No probability improvement can cancel it.

---

# 47. Exit Obligation

Once:

```text ACTIVE_EXIT_REQUIRED
```

the trade cannot return to normal ACTIVE management merely because the next tick improves.

The exit obligation persists until resolved.

---

# 48. Exit Order

An exit order is generated according to the execution contract.

The lifecycle becomes:

```text EXIT_PENDING.
```

Actual exposure remains until fills occur.

---

# 49. Exit Partial Fill

Suppose:

```text CurrentQuantity = 100
ExitFilled = 40.
```

Then:

```text RemainingQuantity = 60.
```

The trade remains exposed.

The remaining quantity retains:

```text protection
exit obligation
mode/risk context
trade identity.
```

---

# 50. Exit Full Fill

If:

```text RemainingQuantity = 0
```

then the position is economically closed.

The lifecycle enters:

```text CLOSED_PENDING_RECONCILIATION.
```

---

# 51. Exit Price

Realized P&L uses actual exit fills.

It does not use:

```text protection price
```

as though that were guaranteed execution.

This distinction is essential for realistic backtesting.

---

# 52. Slippage at Exit

If the intended protection was:

```text 104
```

but actual execution occurred at:

```text 103.60,
```

realized P&L reflects:

```text 103.60.
```

The protection boundary describes the obligation/trigger, not guaranteed execution.

---

# 53. Trade Closure

A trade becomes formally closed only after:

```text ActualPositionQuantity = 0
+
execution reconciliation complete.
```

Then:

```text TRADE_CLOSED.
```

---

# 54. Final Trade Snapshot

The system freezes:

```text TradeID
EntryDirection
EntryInstrument
EntryModelVersion
EntryParameterVersion
EntryTimestamp
EntryQuantity
EntryPrice
ExitTimestamp
ExitQuantity
ExitPrice(s)
RealizedPnL
MaximumObservedPnL
MaximumAdverseExcursion
MaximumFavorableExcursion
FinalMode
ExitReason
ProtectionHistory
ModeHistory
ExecutionCosts
```

Some of these names remain registry-level concepts and will be normalized before implementation.

---

# 55. Maximum Favorable Excursion

The trade's maximum favorable excursion records the maximum observed favorable movement from entry.

Conceptually:

```text MFE
=
max favorable excursion observed during trade.
```

It is historical.

It cannot change after closure.

---

# 56. Maximum Adverse Excursion

Similarly:

```text MAE
=
maximum adverse excursion observed during trade.
```

This becomes particularly important for learning future protection behavior.

---

# 57. Holding Time

Actual holding time is:

```text ExitTimestamp - ActualEntryTimestamp.
```

It is an observed trade outcome.

It is not the same as:

```text ExpectedHorizon.
```

---

# 58. Exit Classification

The trade receives one canonical primary exit reason:

```text HARD_RISK
SESSION_CLOSE
EMERGENCY_REVERSAL
NORMAL_EXIT
EXECUTION_FAILURE
OPERATIONAL_CLOSE
```

The exact taxonomy will be normalized with the decision-priority registry.

Secondary simultaneously triggered conditions remain recorded.

---

# 59. Post-Trade State

After reconciliation:

```text NO_POSITION.
```

The trade itself is frozen.

The strategy is now free to evaluate a new opportunity.

---

# 60. No Immediate Reuse of Trade State

The next trade receives a new:

```text TradeID.
```

and initializes:

```text PeakPnL
Protection
Mode
EntryState
```

from its own entry.

No previous trade state leaks into the new lifecycle.

---

# 61. Trade Outcome Versus Learning Label

The completed trade outcome is not automatically the learning label.

For example:

```text realized profit
```

may be useful for one model.

But another model may require:

```text future maximum favorable excursion
```

or:

```text future adverse excursion
```

or:

```text continuation success within horizon H.
```

Therefore:

```text TradeOutcome
```

and:

```text LearningLabel
```

are distinct concepts.

---

# 62. Label Construction

After closure, the historical system may construct labels from the appropriate future windows.

A label becomes eligible only when:

```text LabelMaturityTime <= LearningTime.
```

The trade's closure does not necessarily mean every possible label has matured.

---

# 63. Example

A trade closes at:

```text 11:30.
```

A future-state label might require information until:

```text 12:00.
```

Therefore:

```text TradeClosed = 11:30
LabelMatured = 12:00.
```

The learning system cannot use that label before 12:00.

---

# 64. Counterfactual Opportunity Labels

The learning system may also retain opportunities that were never traded because:

```text NO_TRADE.
```

This is important.

Otherwise the learner only sees:

```text trades we decided to take.
```

and cannot properly estimate:

```text what happened to opportunities we rejected.
```

---

# 65. Executed Trade Versus Opportunity

The research dataset therefore contains two distinct populations:

```text ALL ELIGIBLE OPPORTUNITIES
```

and:

```text EXECUTED TRADES.
```

This prevents selection bias in probability estimation.

---

# 66. Trade Lifecycle Event Log

Every lifecycle transition should eventually have an immutable event record:

```text timestamp
TradeID
state_before
event
conditions
canonical_action
state_after
model_version
parameter_version
```

This becomes the audit trail.

---

# 67. Tick-Level Reconstruction

For every active trade, we should conceptually be able to reconstruct:

```text t0 Entry
t1 Tick
t2 Tick
t3 Tick
...
tn Exit
```

with:

```text CurrentPnL_t
PeakPnL_t
Protection_t
Mode_t
Probability_t
Continuation_t
```

at each relevant event.

This is the exact tick-by-tick transformation requirement we identified much earlier.

---

# 68. No Retrospective Optimization

After a trade closes, we cannot go back and say:

```text "The stop should have been wider here."
```

and alter the historical trade.

Instead:

```text observed historical behavior
```

is retained.

A new candidate parameter may be tested counterfactually.

---

# 69. Counterfactual Trade

A candidate strategy may simulate:

```text What if protection quantile = q2?
```

But that result is:

```text COUNTERFACTUAL.
```

It does not replace:

```text ACTUAL historical lifecycle.
```

---

# 70. Trade-Level Model Versioning

Every trade retains:

```text EntryModelVersion.
```

If management is allowed to use a newer model, the system additionally records:

```text ManagementModelVersionHistory.
```

This is the exact reason the model-management policy identified earlier must eventually be frozen.

---

# 71. Open Trade During Model Promotion

If a new model is promoted while a trade is active:

the trade does not automatically change historical identity.

The system must follow the explicit management-model policy.

Until that policy is finalized:

```text TODO.
```

---

# 72. Open Trade During Parameter Promotion

The same principle applies to parameter sets.

A new parameter set cannot rewrite:

```text initial protection
entry economics
entry decision
historical state.
```

Its influence on active management must be explicitly authorized.

---

# 73. Risk Continuity

Regardless of model or parameter promotion:

```text ExistingProtection_new >= ExistingProtection_old.
```

The trade never loses previously established protection merely because the analytical regime changed.

---

# 74. Data Failure During Trade

If critical data becomes unavailable:

the trade does not disappear.

The system preserves:

```text actual quantity
last valid protection
entry facts
execution state
```

and enters the defined degraded-data state.

---

# 75. Execution Failure During Trade

If an exit order fails:

```text Position remains active.
```

The system returns to:

```text ACTIVE_EXIT_REQUIRED.
```

It does not return to:

```text ACTIVE_NORMAL.
```

unless the exit obligation itself has been explicitly resolved by the governing contract.

---

# 76. Broker Discrepancy

If internal state says:

```text zero quantity
```

but broker state says:

```text non-zero quantity,
```

the trade is not considered closed.

It enters:

```text RECONCILIATION_REQUIRED.
```

Actual exposure wins over internal assumptions.

---

# 77. Session Close During Exit

If session termination occurs while an exit is already pending:

the exit obligation remains.

The system does not cancel the obligation simply because the session boundary has arrived.

Session closure becomes another operational constraint.

---

# 78. New Trade After Closure

A new trade may be evaluated only after:

```text previous exposure = zero
+
previous execution reconciled
+
session permits entry
+
new entry conditions independently pass.
```

There is no implicit chaining from one trade to another.

---

# 79. Complete Lifecycle State Diagram

The canonical lifecycle is:

```text
                         +----------------+
                         |  NO_POSITION   |
                         +-------+--------+
                                 |
                         valid opportunity
                                 |
                                 v
                     +----------------------+
                     | ENTRY_EVALUATION     |
                     +----------+-----------+
                                |
                         entry qualifies
                                |
                                v
                     +----------------------+
                     | ENTRY_AUTHORIZED     |
                     +----------+-----------+
                                |
                          order submitted
                                |
                                v
                     +----------------------+
                     | ENTRY_PENDING        |
                     +----+------------+----+
                          |            |
                    rejected/cancel    fill
                          |            |
                          v            v
                    NO_POSITION      ACTIVE
                                        |
                                        |
                         +--------------+--------------+
                         |                             |
                     continue                     exit condition
                         |                             |
                         v                             v
                      ACTIVE                 ACTIVE_EXIT_REQUIRED
                                                       |
                                                 exit submitted
                                                       |
                                                       v
                                                 EXIT_PENDING
                                                       |
                                          +------------+------------+
                                          |                         |
                                       partial                    full
                                          |                         |
                                          v                         v
                                  PARTIALLY_EXITED       CLOSED_PENDING_
                                          |              RECONCILIATION
                                          |                         |
                                          +---- exit again          |
                                                                    |
                                                              reconciled
                                                                    |
                                                                    v
                                                               NO_POSITION
```

Reconciliation and degraded-data states can interrupt the relevant paths without destroying actual exposure state.

---

# 80. Lifecycle Completeness Rule

A trade lifecycle is complete only if every path eventually reaches one of:

```text NO_POSITION
```

or:

```text SYSTEM_HALTED
```

There must be no normal path that leaves exposure without a defined management state.

---

# 81. Lifecycle Safety Rule

At every point:

```text ActualPositionQuantity > 0
```

requires an active lifecycle state.

Therefore there is no valid state:

```text quantity > 0
+
NO_POSITION.
```

---

# 82. Lifecycle Accounting Rule

At closure:

```text EntryQuantity
-
ExecutedExitQuantity
=
0
```

subject to the exact treatment of adjustments/corrections.

---

# 83. Lifecycle Learning Rule

A completed trade becomes learning material only after:

```text trade accounting finalized
+
required labels matured
+
training cutoff permits inclusion.
```

This creates a clean separation between:

```text TRADING
```

and:

```text LEARNING.
```

---

# 84. Final Trade Lifecycle Contract

The entire lifecycle can now be summarized as:

```text MARKET INFORMATION
        |
        v
OPPORTUNITY
        |
        v
STATISTICAL EVIDENCE
        |
        v
ECONOMIC VALIDATION
        |
        v
ENTRY AUTHORIZATION
        |
        v
ACTUAL EXECUTION
        |
        v
ACTIVE TRADE
        |
        +--> every event updates state
        |
        +--> probability evolves
        |
        +--> continuation evolves
        |
        +--> mode evolves
        |
        +--> protection can tighten
        |
        +--> protection cannot widen
        |
        +--> profit peak persists
        |
        v
EXIT OBLIGATION
        |
        v
ACTUAL EXIT EXECUTION
        |
        v
RECONCILIATION
        |
        v
FINAL TRADE OUTCOME
        |
        v
LABEL MATURATION
        |
        v
LEARNING DATA
```

This is the complete atomic lifecycle around which the entire strategy is organized.

---

# 85. Remaining Explicit TODOs

The lifecycle architecture itself is substantially complete.

The remaining unresolved items are:

```text Exact TrueData field mapping

Exact event sequencing semantics

Exact executable-price/marking convention

Exact broker fill semantics

Exact order-type semantics

Exact option liquidity fields

Exact model behavior after model promotion during an active trade

Exact treatment of execution corrections

Exact session-close execution contract

Numerical protection parameters

Numerical continuation parameters

Numerical mode-transition parameters
```

These are deliberately not invented.

---

# 86. Architecture Status

At this point we have formally connected:

```text DATA
  ↓
STATE
  ↓
PROBABILITY
  ↓
ECONOMICS
  ↓
ENTRY
  ↓
EXECUTION
  ↓
ACTIVE TRADE
  ↓
DYNAMIC RISK
  ↓
MODE
  ↓
EXIT
  ↓
RECONCILIATION
  ↓
LABEL
  ↓
LEARNING
```

The next artifact should therefore move one level deeper into the thing we have deliberately kept abstract:

# CANONICAL EXECUTION AND FILL MODEL

That specification will answer exactly what happens between:

```text "BUY CE"
```

and:

```text "I actually own this option."
```

including order creation, submission, acknowledgement, partial fills, multiple fills, rejected orders, cancellation races, stale quotes, slippage, fill price construction, execution latency, exit execution, and the distinction between theoretical stop triggering and actual executable liquidation.

That is the remaining bridge between our mathematical strategy and the physical market transaction.