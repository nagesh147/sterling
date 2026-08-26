# CANONICAL STATE TRANSITION SPECIFICATION

Version 1.0

## 1. Purpose

This document defines the exact state transition semantics of the strategy runtime.

The fundamental rule is:

```text
CurrentState + CanonicalEvent
        ↓
Precondition Evaluation
        ↓
State Transition
        ↓
Invariant Validation
        ↓
NextState
```

No component may bypass this transition mechanism to mutate authoritative state.

---

# 2. State Machine Domains

The system contains several related state domains:

```text
OperationalState
SessionState
MarketState
OpportunityState
DecisionState
ExecutionState
PositionState
TradeManagementState
RiskState
LearningState
```

These are logically separate, but their transitions occur within one canonical event-processing cycle.

---

# 3. Global Transition Rule

For event `E_t`:

```text
S_(t+1) = T(S_t, E_t, RuntimeVersion)
```

where:

```text S_t = complete canonical state
E_t = one canonical event
T   = deterministic transition function
```

The transition must not depend on:

```text wall-clock time not represented in the event
random state
future events
unversioned configuration
hidden mutable variables.
```

---

# 4. Transition Atomicity

A transition is atomic.

Either:

```text Event accepted
    ↓
All permitted state mutations committed
    ↓
Invariants pass
```

or:

```text Event rejected/quarantined
    ↓
Authoritative state remains unchanged
```

A partially applied transition is invalid.

---

# 5. Transition Classes

Events are classified as:

```text MARKET_TRANSITION
SESSION_TRANSITION
OPPORTUNITY_TRANSITION
DECISION_TRANSITION
EXECUTION_TRANSITION
POSITION_TRANSITION
RISK_TRANSITION
DATA_QUALITY_TRANSITION
SYSTEM_TRANSITION
LEARNING_TRANSITION
```

---

# 6. MARKET_TICK Transition

Current state:

```text ANY_VALID_OPERATIONAL_STATE
```

Event:

```text MARKET_TICK
```

Preconditions:

```text Event valid
Instrument valid
Timestamp valid
Event not duplicate
```

Transition:

```text MarketState.last_price
    ← Event.price

MarketState.last_event_timestamp
    ← Event.timestamp
```

Potentially:

```text trade quantity
trade metadata
```

may also update.

---

# 7. MARKET_TICK Forbidden Mutations

A market tick cannot directly modify:

```text ProbabilityState
DecisionState
PositionQuantity
RealizedPnL
StrategyRiskBudget
ModelVersion
ParameterVersion.
```

Those can change only through their explicitly defined downstream transitions.

---

# 8. MARKET_QUOTE Transition

Event:

```text MARKET_QUOTE
```

Transition:

```text CurrentBid
CurrentAsk
CurrentBidQuantity
CurrentAskQuantity
QuoteTimestamp
```

are updated.

The quote must pass validation first.

---

# 9. Quote Validation

If:

```text bid > ask
```

and the provider contract does not permit crossed quotes:

```text DataQualityEvent = INVALID_QUOTE
```

The system does not silently swap the values.

---

# 10. MARKET_TRADE Transition

A market trade updates:

```text MarketState.last_trade_price
MarketState.last_trade_quantity
```

It does not update:

```text PositionQuantity
```

because this is external market activity.

---

# 11. MARKET_DEPTH Transition

A valid depth event updates:

```text MarketState.depth
```

according to the provider's snapshot/delta semantics.

Those semantics remain:

```text PENDING_TRUE_DATA_CONTRACT.
```

Until then, no production depth interpretation is permitted.

---

# 12. OPTION_CHAIN_UPDATE Transition

A valid option-chain event updates the canonical option-state cache.

It may modify:

```text CandidateOptionState
OptionState
```

but cannot itself generate:

```text BUY_CE
BUY_PE
```

---

# 13. SESSION_OPEN Transition

Before session open:

```text SessionState.lifecycle = PRE_OPEN
```

Event:

```text SESSION_OPEN
```

Transition:

```text SessionState.lifecycle = OPEN
```

A new:

```text SessionID
```

is created.

---

# 14. Session Initialization

At session initialization:

```text opening-range high = undefined
opening-range low = undefined
```

The previous session's opening range cannot carry into the new session.

---

# 15. OPENING_RANGE Event

During the opening-range interval:

```text UnderlyingPrice_t
```

updates:

```text OpeningRangeHigh
OpeningRangeLow
```

according to:

```text High_(t+1) = max(High_t, Price_t)
Low_(t+1)  = min(Low_t, Price_t)
```

---

# 16. Opening-Range Completion

At the canonical opening-range boundary:

```text OpeningRangeComplete = TRUE
```

and:

```text OpeningRangeWidth
=
OpeningRangeHigh - OpeningRangeLow
```

becomes immutable for that session.

---

# 17. Opening-Range Immutability

After completion:

```text OpeningRangeHigh
OpeningRangeLow
OpeningRangeWidth
```

cannot change.

Later market events cannot modify them.

This is an explicit anti-lookahead invariant.

---

# 18. POST_OPENING_RANGE Transition

After the opening range completes:

```text SessionState.lifecycle
=
POST_OPENING_RANGE
```

The strategy may now evaluate breakout/opportunity conditions according to the mathematical specification.

---

# 19. Opportunity Creation

A market event may create an opportunity when:

```text OpportunityEligibility = TRUE
```

The system creates:

```text OpportunityID
OpportunityTimestamp
FeatureSnapshot
```

using only information available at that timestamp.

---

# 20. Opportunity Immutability

Once an opportunity snapshot is created:

```text OpportunityTimestamp
FeatureSnapshot
MarketSnapshot
```

cannot be retroactively modified by future market events.

---

# 21. Opportunity Evaluation

The Probability Engine may evaluate:

```text Opportunity
+
FeatureSnapshot
+
eligible historical distribution
```

to produce:

```text ProbabilityState.
```

---

# 22. Probability Transition

Input:

```text OPPORTUNITY_EVALUATION
```

Preconditions:

```text FeatureSnapshot valid
Training distribution valid
ModelVersion valid
ParameterVersion valid
No future information.
```

Transition:

```text ProbabilityState
=
ProbabilityModel(
    FeatureSnapshot,
    HistoricalEvidence,
    ModelVersion,
    ParameterVersion
)
```

---

# 23. Probability Invariants

After transition:

```text 0 <= Probability <= 1
```

and:

```text ProbabilityTimestamp
<=
DecisionTimestamp
```

for any decision consuming it.

---

# 24. Economic Evaluation

Once probability and eligible option state exist:

```text EconomicEvaluation
```

may occur.

Inputs:

```text ProbabilityState
OptionState
ExecutionCostEstimate
RiskConstraints
```

Output:

```text EconomicState.
```

---

# 25. Economic Transition

The Economic Engine calculates:

```text ExpectedGrossValue
ExpectedExecutionCost
ExpectedNetValue
EconomicMargin
```

No execution occurs here.

---

# 26. Economic Invariant

If:

```text ExpectedNetValue <= required economic threshold
```

the candidate cannot become an authorized trade.

The exact threshold remains learned/configured.

---

# 27. Option Selection Transition

Candidate options are evaluated against:

```text directional expectation
option economics
liquidity
execution feasibility
risk
```

Output:

```text SelectedOption
```

or:

```text NO_VALID_OPTION.
```

---

# 28. Option Selection Invariant

The selected option must exist in the candidate set observed at or before:

```text DecisionTimestamp.
```

It cannot be selected retrospectively because it later produced a superior outcome.

---

# 29. Decision Authorization

A candidate can proceed to decision generation only if:

```text DataQuality = acceptable
Probability = valid
EconomicState = valid
OptionSelection = valid
RiskAuthorization = available
OperationalState = NORMAL
```

---

# 30. NO_TRADE Transition

If any mandatory entry condition fails:

```text DecisionAction = NO_TRADE
```

A structured:

```text NoTradeReason
```

must be recorded.

No order is generated.

---

# 31. BUY_CE Transition

If all conditions pass and:

```text SelectedOption.OptionType = CE
```

then:

```text DecisionAction = BUY_CE
```

is generated.

The decision records:

```text DecisionID
SelectedOption
ProbabilitySnapshot
EconomicSnapshot
RiskAuthorization
RuntimeVersion.
```

---

# 32. BUY_PE Transition

Identical structure:

```text SelectedOption.OptionType = PE
```

produces:

```text DecisionAction = BUY_PE.
```

---

# 33. Decision Immutability

Once generated:

```text DecisionID
Action
SelectedOption
Probability
EconomicValue
RiskAuthorization
RuntimeVersion
```

cannot be modified.

A later event can invalidate the decision's execution eligibility, but cannot rewrite history.

---

# 34. Decision Expiration

A decision may become:

```text EXPIRED
```

if the execution-validity conditions cease to hold before execution.

The original decision remains immutable.

A new decision must be generated if another trade is warranted.

---

# 35. Order Intent Transition

A valid non-expired decision produces:

```text OrderIntent.
```

The order intent contains:

```text DecisionID
InstrumentID
Side
RequestedQuantity
ExecutionPolicyVersion
```

---

# 36. Decision-to-Order Rule

The following is prohibited:

```text Decision
    ↓
direct PositionState mutation
```

The only valid path is:

```text Decision
    ↓
OrderIntent
    ↓
OrderEvent
    ↓
FillEvent
    ↓
PositionState.
```

---

# 37. ORDER_SUBMITTED Transition

When an order is submitted:

```text ExecutionState
```

records:

```text OrderID
OrderStatus = SUBMITTED
```

Position remains:

```text unchanged.
```

---

# 38. ORDER_ACCEPTED Transition

An accepted order becomes:

```text OrderStatus = ACCEPTED
```

Still:

```text PositionQuantity = unchanged.
```

Acceptance is not execution.

---

# 39. PARTIAL_FILL Transition

If:

```text ExecutedQuantity = q
```

then:

```text PositionQuantity_(t+1)
=
PositionQuantity_t + signed(q)
```

for an entry fill.

The remaining order quantity remains pending.

---

# 40. FULL_FILL Transition

A full entry fill produces:

```text PositionState.status = OPEN
```

and:

```text PositionQuantity = ExecutedQuantity.
```

The trade lifecycle becomes:

```text ACTIVE.
```

---

# 41. Average Entry Price

For multiple entry fills:

```text AverageEntryPrice
=
Σ(price_i × quantity_i)
/
Σ(quantity_i)
```

subject to the canonical accounting convention.

---

# 42. Duplicate Fill Transition

If:

```text FillID
```

has already been applied:

```text no position mutation.
```

The event is recorded as duplicate/idempotently handled.

---

# 43. Exit Order Transition

When an exit obligation exists:

```text ExitObligation = TRUE
```

the Trade Manager may generate:

```text ExitOrderIntent.
```

The position remains open until actual execution.

---

# 44. EXIT_PENDING

Once an exit order is submitted:

```text PositionState.status = EXIT_PENDING
```

but:

```text PositionQuantity > 0
```

may remain true.

---

# 45. Exit Fill

When an exit fill occurs:

```text PositionQuantity
```

decreases by:

```text ExecutedQuantity.
```

Realized P&L is updated according to the accounting contract.

---

# 46. Complete Exit

When:

```text PositionQuantity = 0
```

and execution reconciliation succeeds:

```text PositionState.status = CLOSED
TradeLifecycle = CLOSED.
```

---

# 47. Exit Obligation Persistence

Once:

```text ExitObligation = TRUE
```

it cannot revert to:

```text FALSE
```

merely because a later probability estimate improves.

It remains until:

```text position closed
```

or a specifically defined operational resolution occurs.

---

# 48. Active Trade Market Event

During an active trade, every relevant market event may update:

```text CurrentPnL
PeakPnL
ProfitGiveback
FeatureState
ProbabilityState
ContinuationValue
ModeTransitionEvidence
```

according to their respective contracts.

---

# 49. Current P&L Transition

Current P&L is recalculated from:

```text actual position
+
current permitted valuation information
+
declared cost convention.
```

It is never taken from the original prediction.

---

# 50. Peak P&L Transition

After CurrentPnL changes:

```text PeakPnL_new
=
max(PeakPnL_old, CurrentPnL_new)
```

Therefore:

```text PeakPnL_new >= PeakPnL_old.
```

---

# 51. Profit Giveback Transition

```text ProfitGiveback
=
max(0, PeakPnL - CurrentPnL)
```

It is a derived quantity.

It does not independently trigger an exit unless the exit specification says so.

---

# 52. Mode Transition

A mode transition occurs only when its validated transition condition is satisfied.

Conceptually:

```text CurrentMode
+
ModeTransitionEvidence
+
TransitionParameter
        ↓
NewMode
```

---

# 53. Mode/Risk Separation

A mode transition cannot directly decrease:

```text ProtectionLevel
```

or increase:

```text StrategyRiskBudget
```

unless an independently authorized risk transition permits it.

This invariant is permanent.

---

# 54. Continuation Evaluation

For an active trade:

```text ContinuationValue
```

is evaluated from current causal evidence.

If continuation remains justified:

```text maintain position
```

may remain valid.

If continuation fails:

```text ExitObligation
```

may become true.

---

# 55. Emergency Reversal Transition

If the validated emergency-reversal condition is satisfied:

```text ExitObligation = TRUE
```

for the current position.

The baseline system does not automatically open the opposite position.

Therefore:

```text Long CE
    ↓
Emergency reversal
    ↓
Exit
```

not:

```text Long CE
    ↓
Short/PE
```

---

# 56. Dynamic Mode Does Not Recover Lost Protection

Suppose:

```text Mode = SCALP
Protection = P
```

and later:

```text Mode = INTRADAY.
```

The transition cannot produce:

```text Protection < P.
```

The strategy may allow continued holding.

It may not use a longer horizon as justification to erase previously established protection.

---

# 57. Session Close Transition

At the canonical session close:

```text if PositionQuantity > 0
```

the system follows the explicit intraday-close policy.

For the baseline intraday strategy, the intended contract is:

```text no overnight exposure.
```

Therefore an exit obligation is generated.

The exact exchange/session timing remains externally validated.

---

# 58. Data Degradation Transition

If a critical required input becomes unavailable:

```text OperationalState
=
DATA_DEGRADED.
```

New entries are prohibited.

Existing positions follow their existing protection and safety policy.

---

# 59. Reconciliation Failure Transition

If:

```text InternalPosition != AuthoritativeExternalPosition
```

then:

```text OperationalState
=
RECONCILIATION_REQUIRED.
```

No new exposure may be created.

---

# 60. System Halt Transition

Critical invariant violation:

```text OperationalState
=
SYSTEM_HALTED.
```

The system fails closed.

It does not attempt to continue trading through known state corruption.

---

# 61. Data Recovery Transition

When data quality returns to acceptable state:

```text DATA_DEGRADED
```

does not automatically mean:

```text NORMAL.
```

The system must satisfy the recovery conditions defined by the operational policy.

This prevents a transient data restoration from immediately enabling trading without state validation.

---

# 62. Learning Transition

A historical label becomes eligible only when:

```text CurrentTime >= LabelMaturityTime
```

and:

```text LabelStatus = MATURED.
```

Only then may it enter the learning dataset.

---

# 63. Learning Cannot Mutate Historical State

A newly learned model:

```text ModelVersion B
```

may affect future decisions.

It cannot alter:

```text historical decisions
historical trades
historical labels
historical P&L.
```

---

# 64. Model Promotion Transition

The model lifecycle is:

```text CANDIDATE
    ↓
VALIDATION
    ↓
PROMOTION_ELIGIBLE
    ↓
PROMOTED
```

A failed candidate becomes:

```text REJECTED.
```

---

# 65. Production Model Replacement

When Model B replaces Model A:

```text future decision boundary
```

uses B.

Existing decisions retain:

```text ModelVersion A.
```

Active trades follow the explicitly declared active-trade model policy and do not silently change model identity.

---

# 66. Parameter Update

A new parameter set:

```text ParameterVersion B
```

is immutable after creation.

It becomes effective only at a declared:

```text EffectiveTime.
```

There is no retroactive parameter mutation.

---

# 67. Event-Type Transition Matrix

The high-level ownership matrix is:

```text Event                  Primary State Mutation
------------------------------------------------------------
MARKET_TICK                MarketState
MARKET_QUOTE               MarketState
MARKET_TRADE               MarketState
MARKET_DEPTH               MarketState
OPTION_CHAIN_UPDATE        OptionState
SESSION_OPEN               SessionState
OPENING_RANGE_EVENT        OpeningRangeState
SESSION_CLOSE              SessionState / TradeManagement
DATA_QUALITY_EVENT         OperationalState
ORDER_EVENT                ExecutionState
FILL_EVENT                 PositionState / P&L
POSITION_EVENT             ReconciliationState
LABEL_EVENT                LearningState
MODEL_EVENT                Research/ModelState
PARAMETER_EVENT            ParameterState
```

No event is allowed to mutate arbitrary state outside its declared transition contract.

---

# 68. Forbidden Transition Matrix

The following transitions are categorically forbidden:

```text Signal → Position
MarketTrade → Position
Prediction → RealizedPnL
Probability increase → Risk increase
Mode extension → Protection decrease
Future label → Current decision
Future P&L → Current feature
Model update → Historical trade mutation
Missing data → Zero value
Unknown fill status → Assumed cancellation.
```

---

# 69. Transition Preconditions

Before every state mutation:

```text Event valid
Event causally admissible
Event not duplicate
Required state exists
Required external semantics known
Transition allowed
```

must be satisfied.

---

# 70. Post-Transition Validation

After every transition:

```text State schema valid
All invariants valid
No forbidden mutation occurred
State version incremented
Event recorded
Audit record created
```

must be verified.

---

# 71. Transition Audit Record

Every transition should produce:

```text TransitionAudit {
    event_id
    previous_state_version
    next_state_version

    changed_variables[]
    unchanged_protected_variables[]

    runtime_version
    timestamp

    invariant_results[]
}
```

This makes state mutations auditable.

---

# 72. Changed-Variable Contract

A transition must declare which variables it is allowed to modify.

For example:

```text FILL_EVENT
```

may modify:

```text PositionQuantity
AverageEntryPrice
RealizedPnL
ExecutionState
TradeLifecycle
```

but cannot modify:

```text ProbabilityModelVersion
TrainingCutoff
HistoricalFeatureSnapshot.
```

---

# 73. No Hidden Mutation

If a variable changes but is not listed in the transition's permitted mutation set:

```text STATE_CONTRACT_VIOLATION.
```

The transition fails.

This is one of the strongest implementation safeguards in the architecture.

---

# 74. Temporal Causality Test

For every decision at time:

```text T
```

the complete dependency graph must satisfy:

```text source_timestamp <= T.
```

The only exception is future information explicitly used later for:

```text outcome labeling
```

and that information must never enter the original decision state.

---

# 75. Transition Determinism

Given:

```text same initial state
same event
same runtime version
```

the transition must produce:

```text identical next state.
```

---

# 76. State Machine Property

The entire runtime can therefore be represented as:

```text id="clyu3x"
S0
 |
 E1
 v
S1
 |
 E2
 v
S2
 |
 ...
 v
Sn
```

where every edge is:

```text explicitly defined
causal
auditable
testable.
```

---

# 77. State Machine Completion Criteria

The state machine is considered structurally complete when:

```text every authoritative event has a transition
every transition has preconditions
every transition has postconditions
every mutation has an owner
every forbidden mutation is identified
every critical invariant has a test
every terminal state is defined.
```

---

# 78. Remaining Unknowns

The state machine does not depend on exact TrueData field names.

However, these external semantics remain pending:

```text TBT event classification
TBT sequence ordering
depth snapshot/delta semantics
quote update semantics
historical timestamp semantics
instrument-master mapping
session calendar source.
```

They will populate the adapter contract later.

---

# 79. Remaining Numerical Unknowns

Still deliberately unfrozen:

```text probability thresholds
profit-floor quantile
continuation threshold
emergency-reversal threshold
mode-transition sensitivity
feature lookbacks
risk parameters
execution-cost parameters
slippage parameters.
```

The state machine does not choose these values.

---

# 80. Formal Status

```text Mathematical specification       COMPLETE
Variable registry                   COMPLETE
Event schema                        COMPLETE
State schema                        COMPLETE
State transition semantics          COMPLETE
Forbidden transition rules          COMPLETE
Transition invariants               COMPLETE
Numerical calibration               NOT STARTED
Provider mapping                    PENDING
Historical validation               NOT STARTED
```

---

# 81. Next Artifact

The next artifact should now be the:

# CANONICAL RESEARCH DATASET AND WALK-FORWARD CONSTRUCTION SPECIFICATION

This is an important transition.

We have now specified how the live/replay system behaves.

Next we must define exactly how historical data becomes the datasets used to estimate:

```text probability distributions
expected outcomes
profit floors
continuation values
risk parameters
execution-cost parameters.
```

Most importantly, we will specify the exact chronology:

```text Raw Historical Data
        ↓
Canonical Event Dataset
        ↓
Causal State Reconstruction
        ↓
Opportunity Dataset
        ↓
Matured Labels
        ↓
Training Dataset
        ↓
Validation Dataset
        ↓
Forward/Test Dataset
        ↓
Walk-Forward Model Update
```

That specification is where we formally lock down the remaining look-ahead and overfitting defenses before any parameter is estimated.