# POSITION INITIATION AND ENTRY STATE SPECIFICATION

## Canonical Entry Contract — Version 1.0

## 1. Objective

This layer converts an economically approved trade candidate into an actual position.

The complete transition is:

```text
NO_POSITION
     |
     v
OPPORTUNITY_DETECTED
     |
     v
ECONOMICALLY_ELIGIBLE
     |
     v
ENTRY_AUTHORIZED
     |
     v
ORDER_PENDING
     |
     v
ORDER_FILLED
     |
     v
POSITION_ACTIVE
```

A failed entry does not become a position.

---

# 2. Fundamental Principle

There are three different things:

```text
SIGNAL
TRADE DECISION
POSITION
```

They must never be treated as the same object.

A signal says:

```text "conditions may be favorable."
```

A trade decision says:

```text "this candidate currently satisfies the economic contract."
```

A position says:

```text "capital is currently exposed to this instrument."
```

---

# 3. Flat-State Invariant

When:

```text
PositionState = NO_POSITION
```

there must be:

```text
position_quantity = 0
```

and:

```text
unrealized_PnL = 0
```

for the strategy's position ledger.

---

# 4. Opportunity Detection

At event `t`:

```text
MarketState_t
      |
      v
FeatureState_t
      |
      v
ProbabilityState_t
      |
      v
EconomicDecision_t
```

The system first determines whether a candidate exists.

---

# 5. Candidate Requirement

An entry candidate must contain:

```text
direction
option_id
expected_net_value
economic_evidence
execution_state
risk_eligibility
```

and all mandatory fields must be valid.

---

# 6. Entry Authorization

A candidate becomes:

```text
ENTRY_AUTHORIZED
```

only when all entry gates are simultaneously satisfied.

Conceptually:

```text
DataValid
AND
ModelValid
AND
EconomicDecisionValid
AND
ExecutionValid
AND
RiskValid
AND
CapitalValid
AND
SessionValid
```

---

# 7. Authorization Is Time-Bounded

An authorization belongs to a specific information state:

```text
Authorization_t
```

It cannot remain valid indefinitely.

If material market information changes before execution:

```text
Authorization_t
```

must be reevaluated.

---

# 8. No Stale Signal Execution

Suppose:

```text t0 = signal
t1 = order decision
t2 = actual fill
```

The system cannot assume:

```text Candidate_t0 == Candidate_t2
```

without checking.

---

# 9. Pre-Execution Revalidation

Immediately before order submission:

```text
CurrentState
```

must still satisfy the entry contract.

If not:

```text CANCEL / DO_NOT_SUBMIT
```

---

# 10. Entry Race Condition

This is especially important for tick-driven trading.

Between:

```text decision
```

and:

```text order submission
```

the market may change.

Therefore the system treats:

```text authorization
```

and:

```text execution
```

as separate states.

---

# 11. Order State

The order state machine is:

```text
ENTRY_AUTHORIZED
      |
      v
ORDER_SUBMITTED
      |
      +------> ORDER_REJECTED
      |
      +------> ORDER_CANCELLED
      |
      +------> PARTIALLY_FILLED
      |
      v
ORDER_FILLED
```

---

# 12. Order Rejection

If the broker/exchange rejects the order:

```text PositionState remains NO_POSITION.
```

No P&L state is created.

---

# 13. Order Cancellation

If an order is cancelled before any fill:

```text PositionState remains NO_POSITION.
```

The original authorization becomes invalid.

A new decision must be generated if another entry is desired.

---

# 14. Partial Fill

Partial execution is not equivalent to full execution.

Suppose:

```text requested_quantity = 150
filled_quantity = 50
```

then:

```text position_quantity = 50
```

not:

```text 150.
```

---

# 15. Partial Fill Risk

Once even one unit is filled:

```text PositionState = POSITION_ACTIVE
```

because actual financial exposure exists.

The risk engine must immediately protect the filled quantity.

---

# 16. Partial Fill Remainder

The remaining quantity:

```text requested_quantity - filled_quantity
```

must be separately managed.

The system must decide whether the remainder remains authorized based on the current market state.

---

# 17. Entry Price

The canonical entry price is the actual execution price.

For multiple fills:

```text EntryPrice
=
Σ(fill_price_i × fill_quantity_i)
/
Σ(fill_quantity_i)
```

---

# 18. Entry Timestamp

The canonical position timestamp is the actual fill timestamp:

```text PositionEntryTime
=
timestamp_of_first_fill
```

A separate:

```text DecisionTimestamp
```

is retained.

---

# 19. Decision Time Versus Fill Time

These are distinct:

```text DecisionTime != FillTime
```

unless they actually coincide.

This distinction is essential for latency analysis.

---

# 20. Entry Slippage

Define:

```text EntrySlippage
=
ActualFillPrice
-
ReferenceExecutablePrice
```

with the sign normalized according to trade direction.

For a long option purchase, adverse slippage increases the effective entry cost.

---

# 21. Entry Cost Basis

The position's effective cost basis becomes:

```text EffectiveEntryCost
=
ActualFillValue
+
EntryTransactionCosts
```

---

# 22. Entry Facts

Once a position exists, the following are historical facts:

```text entry_timestamp
entry_price
filled_quantity
option_id
expiry
strike
direction
actual_execution_cost
model_version
feature_version
decision_version
```

They cannot be rewritten.

---

# 23. Entry Snapshot

At entry, retain:

```text EntrySnapshot_t
```

containing:

```text market_state
feature_state
probability_state
economic_decision
execution_state
risk_state
```

This is an audit snapshot.

---

# 24. Entry Snapshot Is Immutable

The entry snapshot never changes.

Later states are separate:

```text State_t0
State_t1
State_t2
...
```

This allows us to answer:

```text What did the system know when it entered?
```

---

# 25. Dynamic State

Immediately after entry, the system begins producing:

```text LivePositionState_t
```

which is continuously updated.

---

# 26. Static Versus Dynamic Position Variables

The position contains two fundamentally different categories.

Static:

```text entry_price
entry_time
instrument
quantity_filled
entry_cost
```

Dynamic:

```text current_price
current_PnL
current_probability
current_volatility
current_liquidity
current_mode
current_continuation_value
current_protection_boundary
```

---

# 27. Current P&L

There is exactly one canonical current P&L variable.

```text CurrentPnL_t
```

We do not create:

```text current_profit
current_PnL
floating_profit
unrealized_profit
```

as separate mathematical concepts.

They would duplicate the same state.

---

# 28. P&L Definition

For a long option position:

```text GrossPnL_t
=
(CurrentOptionPrice_t - EntryPrice)
×
FilledQuantity
```

with appropriate contract multiplier.

Net P&L additionally incorporates applicable transaction costs.

---

# 29. Profit Is State-Derived

Current P&L is not independently stored as an arbitrary value.

It is derived from:

```text current_mark
entry_price
quantity
contract_multiplier
cost_basis
```

This prevents inconsistent duplicated variables.

---

# 30. Maximum Favorable Excursion

After entry:

```text MFE_t
=
max(
CurrentPnL_since_entry
)
```

This is cumulative historical state.

It can only move:

```text upward
```

for a long position's favorable excursion.

It cannot decrease.

---

# 31. Maximum Adverse Excursion

Likewise:

```text MAE_t
=
min(
CurrentPnL_since_entry
)
```

for the position's adverse excursion.

It can only become more adverse historically.

---

# 32. Peak Profit

Define:

```text PeakPnL_t
=
max(
CurrentPnL_s
for s <= t
)
```

This is the canonical historical profit peak.

---

# 33. Protection Boundary

The current protective exit boundary is:

```text ProtectionBoundary_t
```

This is dynamic.

But it has an important invariant:

```text For a long position:
ProtectionBoundary_t
must never move downward
once it has moved upward.
```

---

# 34. Why

Suppose:

```text Entry = 100
Initial protection = 80
```

and price reaches:

```text 145.
```

The system may move protection to:

```text 125
```

or higher.

It may not later decide:

```text protection = 95
```

merely because the trade has been reclassified as intraday.

---

# 35. Dynamic Mode Is Not Dynamic Risk

This is one of our most important architectural invariants.

```text Mode:
MICRO -> SCALP -> EXTENDED_SCALP -> INTRADAY
```

does not authorize:

```text Protection:
125 -> 95
```

---

# 36. Mode

The position has:

```text Mode_t
```

which represents the current estimated opportunity horizon.

Possible conceptual states:

```text MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

---

# 37. Mode Is Derived

Mode is not manually assigned by the user.

It is inferred from current:

```text continuation value
horizon distribution
state persistence
economic value
```

---

# 38. Mode Can Move Forward

For example:

```text MICRO
  ->
SCALP
  ->
EXTENDED_SCALP
  ->
INTRADAY
```

if continuation evidence strengthens.

---

# 39. Mode Can Move Backward

Likewise:

```text INTRADAY
  ->
EXTENDED_SCALP
  ->
SCALP
  ->
MICRO
```

if continuation evidence deteriorates.

---

# 40. Mode Transition Does Not Rewrite History

If a position entered as:

```text MICRO
```

and later becomes:

```text INTRADAY
```

the original entry mode remains:

```text EntryMode = MICRO
```

while:

```text CurrentMode = INTRADAY
```

---

# 41. Mode Transition Timestamp

Every transition records:

```text previous_mode
new_mode
timestamp
trigger_state
```

---

# 42. Mode Transition Hysteresis

Tiny probability fluctuations must not produce:

```text MICRO
SCALP
MICRO
SCALP
MICRO
```

on successive ticks.

Therefore transitions require validated persistence or hysteresis conditions.

Exact sensitivity remains empirical.

---

# 43. Initial Protection

Immediately after a valid fill:

```text InitialProtection
```

must be established.

It is based on the validated entry-risk model.

It cannot simply be:

```text entry_price - fixed_amount.
```

---

# 44. Initial Risk

Define:

```text InitialRiskPerUnit
=
EntryPrice - InitialProtection
```

for a long option position, with the appropriate sign convention.

---

# 45. Initial Risk Is Historical

Once the position is established:

```text InitialRiskPerUnit
```

does not change.

Later protection changes do not rewrite the initial risk.

---

# 46. Current Risk

Separately:

```text CurrentRiskPerUnit_t
=
CurrentPrice_t - ProtectionBoundary_t
```

for the long-position representation.

This is dynamic.

---

# 47. Initial Risk Versus Current Risk

These must never be conflated.

```text InitialRisk
```

answers:

```text How much did we initially expose?
```

while:

```text CurrentRisk
```

answers:

```text How much downside remains before the current protection boundary?
```

---

# 48. Profit Locking

When:

```text PeakPnL_t
```

becomes sufficiently favorable, the protection boundary may advance.

Conceptually:

```text PeakPnL
    |
    v
Validated Profit Floor
    |
    v
ProtectionBoundary
```

---

# 49. Profit Floor

The profit floor is not a fixed percentage.

It is determined by a validated function of:

```text current_state
profit_distribution
execution conditions
historical MFE/MAE
uncertainty
```

---

# 50. Protection Update

At each relevant event:

```text CandidateProtection_t
```

is calculated.

Then:

```text ProtectionBoundary_t
=
max(
PreviousProtectionBoundary,
CandidateProtection_t
)
```

for the long-position case.

---

# 51. Critical Protection Invariant

Protection can:

```text remain unchanged
or
move toward greater profit
```

but cannot:

```text move backward
```

for the long position.

---

# 52. Profit Cannot Be Given Back Through Reclassification

Suppose:

```text Entry = 100
Peak = 145
Protection = 125
```

and the system changes:

```text INTRADAY -> SCALP.
```

It may tighten protection.

It cannot widen protection to:

```text 115.
```

---

# 53. This Solves the Earlier Problem

Our earlier conceptual mistake was:

```text new mode
    ->
new risk tolerance.
```

The correct relationship is:

```text new mode
    ->
new continuation assessment
    ->
possibly tighter protection
```

never:

```text new mode
    ->
permission to increase historical risk.
```

---

# 54. Probability Update

After entry:

```text ProbabilityState_t
```

continues to update from new causal information.

The entry probability remains immutable:

```text EntryProbability
```

while:

```text CurrentProbability_t
```

changes.

---

# 55. Economic Value Update

Similarly:

```text EntryNetEV
```

is historical.

The current opportunity value:

```text CurrentContinuationValue_t
```

is dynamic.

---

# 56. Continuation Value

The position does not ask:

```text "Was entering correct?"
```

It asks:

```text "Given that we already own the position,
is continuing to own it still economically superior
to exiting?"
```

---

# 57. Sunk-Cost Principle

The original entry cost must not distort the future decision.

Once the position exists:

```text EntryPrice
```

is historical.

The continuation decision is based on:

```text CurrentMark
+
FutureDistribution
+
CurrentExecution
+
CurrentRisk
```

not emotional attachment to the entry price.

---

# 58. Hold Versus Exit

For an existing position:

```text HOLD
```

means:

```text continuation value remains sufficiently positive
and all protective invariants remain satisfied.
```

---

# 59. Exit

```text EXIT
```

occurs when:

```text continuation economics fail
OR
protection boundary is breached
OR
hard risk invariant is violated
OR
session termination condition occurs
OR
execution/data integrity requires liquidation.
```

---

# 60. Entry Does Not Guarantee Holding

A valid entry at:

```text t0
```

does not imply:

```text HOLD
```

at:

```text t1.
```

Every new event can alter the state.

---

# 61. Immediate Post-Entry Reassessment

After a fill:

```text FillEvent
   |
   v
PositionEstablished
   |
   v
ImmediateRiskInitialization
   |
   v
CurrentStateRecalculation
```

This prevents the system from assuming the entry state remains valid after execution.

---

# 62. Fill Price Shock

Suppose intended entry:

```text 100
```

but actual fill:

```text 103.
```

The system does not pretend the entry was:

```text 100.
```

The position is initialized from:

```text 103.
```

---

# 63. Economic Revalidation After Fill

The trade can immediately become economically unattractive because of slippage.

Therefore:

```text post-fill continuation economics
```

are recalculated.

This does not mean we instantly exit on every small adverse mark.

The exit logic still follows the validated position state machine.

---

# 64. Entry Failure Due to Slippage

If the system is unable to obtain a valid fill within the permitted execution conditions:

```text no position
```

and:

```text stale authorization
```

must not be reused indefinitely.

---

# 65. Duplicate Entry Prevention

If:

```text PositionState != NO_POSITION
```

then the flat-state entry engine cannot create another independent entry unless pyramiding is explicitly supported.

Our baseline strategy does not assume pyramiding.

---

# 66. One Position Contract

Baseline invariant:

```text At most one active directional option position
```

for the strategy instance.

This keeps attribution and risk accounting unambiguous.

---

# 67. Opposite Direction

If holding:

```text CE
```

and current probability shifts strongly toward:

```text DOWN
```

the system first evaluates:

```text EXIT CE
```

Then, only after becoming flat, a separate entry evaluation can consider:

```text BUY PE.
```

---

# 68. No Implicit Flip

We do not allow:

```text CE -> PE
```

as one atomic decision.

This prevents hidden overlapping risk.

---

# 69. Entry Cooldown

After an exit, the strategy may require a validated re-entry condition to prevent immediate churn.

This is not a fixed time delay by default.

It may instead depend on:

```text state reset
signal independence
execution cost
probability separation
```

---

# 70. Re-Entry

A new position requires a new:

```text DecisionTimestamp
ProbabilitySnapshot
EconomicEvaluation
RiskEvaluation
Authorization
```

It cannot reuse the previous trade's authorization.

---

# 71. Trade Identity

Every position receives:

```text TradeID
```

which uniquely identifies the lifecycle:

```text entry
-> active state
-> transitions
-> exit.
```

---

# 72. Position Lifecycle

Canonical lifecycle:

```text
NO_POSITION
     |
     v
ENTRY_AUTHORIZED
     |
     v
ORDER_PENDING
     |
     v
POSITION_ACTIVE
     |
     +------------------+
     |                  |
     v                  v
PROTECTED          EXIT_PENDING
     |                  |
     +--------+---------+
              |
              v
          EXIT_FILLED
              |
              v
          TRADE_CLOSED
```

---

# 73. Protected State

`PROTECTED` does not mean:

```text guaranteed profit.
```

It means the position currently has a valid protective boundary according to the risk contract.

---

# 74. Trade Closure

At final exit:

```text ExitPrice
ExitTimestamp
ExitCosts
RealizedPnL
```

become immutable historical facts.

---

# 75. Realized P&L

The final realized result is:

```text RealizedPnL
=
GrossTradePnL
-
TotalTransactionCosts
```

using actual fills.

---

# 76. Trade Record

The completed trade must retain:

```text TradeID
EntrySnapshot
AllModeTransitions
AllProtectionTransitions
AllExitTriggers
AllActualFills
FinalExit
RealizedPnL
```

This creates complete causal attribution.

---

# 77. Decision Attribution

After the trade closes, we can reconstruct:

```text What did the system know?
What did it believe?
What did it authorize?
What actually happened?
Which transition caused the exit?
```

This is essential for later learning.

---

# 78. No Retrospective Rewrite

A losing trade cannot cause the system to rewrite:

```text EntryProbability
EntryEV
EntryRisk
EntryMode
```

after the fact.

That would contaminate historical learning.

---

# 79. Learning Boundary

The completed trade becomes eligible for research learning only after:

```text all required outcome horizons
```

have matured.

A trade cannot train a model on an outcome that has not yet fully occurred.

---

# 80. Position State Vector

The canonical live position state can therefore be represented as:

```text
PositionState_t =
{
    TradeID,
    instrument,
    direction,
    quantity,
    entry_price,
    entry_time,
    current_price,
    CurrentPnL,
    PeakPnL,
    MAE,
    MFE,
    CurrentMode,
    EntryMode,
    CurrentProbability,
    EntryProbability,
    CurrentContinuationValue,
    EntryNetEV,
    InitialProtection,
    ProtectionBoundary,
    CurrentRisk,
    model_version,
    state_version
}
```

---

# 81. No Duplicate P&L Variables

There is exactly one:

```text CurrentPnL
```

and one:

```text RealizedPnL
```

for the lifecycle.

Historical peak and excursion values are separate state variables because they represent different mathematical quantities.

---

# 82. No Duplicate Horizon Variables

There is not:

```text expected_holding_time
expected_horizon
```

representing the same concept.

The canonical object is:

```text HorizonDistribution_t
```

from which expected horizon can be derived when needed.

---

# 83. No Duplicate Profit Variables

There is not:

```text current_profit
current_PnL
profit_now
```

as separate concepts.

All current economic profit is derived through:

```text CurrentPnL.
```

---

# 84. Entry Invariants

Immediately after fill:

```text quantity > 0
```

and:

```text entry_price > 0
```

and:

```text instrument is valid
```

and:

```text protection_boundary is valid
```

and:

```text TradeID exists.
```

---

# 85. Position Invariants

While active:

```text quantity > 0
```

and:

```text EntryPrice remains unchanged
```

and:

```text EntryTime remains unchanged
```

and:

```text EntrySnapshot remains unchanged.
```

---

# 86. Protection Invariant

For a long position:

```text ProtectionBoundary_(t+1)
>=
ProtectionBoundary_t
```

whenever both are valid protection levels.

---

# 87. Quantity Invariant

The active quantity can only change through:

```text actual execution event.
```

The strategy cannot mathematically "assume" that an order filled.

---

# 88. P&L Invariant

Current P&L must always be reconstructable from:

```text actual fills
+
current executable/mark price
+
cost model.
```

---

# 89. State Transition Invariant

Every transition must have:

```text previous_state
event
new_state
timestamp
```

No state may appear spontaneously.

---

# 90. Impossible State

Examples of invalid states:

```text POSITION_ACTIVE
with quantity = 0
```

or:

```text TRADE_CLOSED
with no exit execution
```

or:

```text protection boundary
outside mathematically valid price domain
```

or:

```text current mode exists
without an active position
```

where the mode is specifically defined as a position mode.

---

# 91. Entry Decision Flow

```text
MARKET EVENT
      |
      v
UPDATE CANONICAL STATE
      |
      v
UPDATE FEATURES
      |
      v
UPDATE PROBABILITY
      |
      v
UPDATE ECONOMIC EVALUATION
      |
      v
ENTRY ELIGIBLE?
   /          \
 NO            YES
 |              |
 v              v
WAIT       RISK CHECK
                |
                v
          ENTRY AUTHORIZATION
                |
                v
          EXECUTION VALID?
            /       \
          NO         YES
          |           |
          v           v
       NO TRADE   SUBMIT ORDER
                       |
                       v
                    FILL?
                  /       \
                NO         YES
                |           |
                v           v
          NO POSITION   POSITION ACTIVE
```

---

# 92. Entry-to-Position Bridge

The most important transition is:

```text ORDER_FILLED
      |
      v
POSITION_ACTIVE
```

At this exact point:

```text historical entry facts freeze
```

and:

```text dynamic position management begins.
```

---

# 93. Dynamic Management Begins Immediately

The first post-entry event may already produce:

```text probability change
mode change
continuation change
protection adjustment
```

That is allowed.

What is not allowed is changing historical entry facts.

---

# 94. Fundamental Separation

The architecture is therefore:

```text HISTORY
immutable facts
      |
      v
CURRENT STATE
dynamic estimates
      |
      v
FUTURE DECISION
dynamic action
```

This distinction will remain throughout the rest of the system.

---

# 95. Final Canonical Entry Contract

A trade enters only if:

```text Candidate
AND
CurrentAuthorizationValid
AND
RiskEligible
AND
ExecutionFeasible
AND
ActualFillOccurs
```

Then:

```text PositionActive
```

is created from actual execution facts.

---

# 96. Next Artifact

The next layer should now be the **Live Position State Transition and Dynamic Mode/Risk Engine**.

That is where we will specify, event by event, the exact mechanics you originally cared about:

```text every incoming tick
      |
      v
recompute state
      |
      v
recompute probability
      |
      v
recompute continuation value
      |
      v
detect MICRO / SCALP / EXTENDED_SCALP / INTRADAY transition
      |
      v
recompute candidate protection
      |
      v
apply monotonic protection invariant
      |
      v
HOLD / TIGHTEN / EXIT
```

That will be the point where the previously separate mathematical pieces finally become one **live position state machine**, including forward continuation and backward profit protection without ever allowing mode reclassification to increase previously accepted risk.