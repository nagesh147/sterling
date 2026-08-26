# CANONICAL IMPLEMENTATION CONTRACT

Version 1.0

## 1. Purpose

This document translates the mathematical strategy specification into implementation-level contracts.

It defines:

```text
what each component receives
what each component produces
who owns each state variable
when each variable may change
what invariants must hold
what information is forbidden
what must be tested
```

It does not yet define numerical trading parameters.

---

# 2. Core Architectural Principle

The implementation is an event-driven state machine.

The fundamental operation is:

```text
State_t + Event_t
        |
        v
Transition
        |
        v
State_(t+1)
```

Every meaningful state change must therefore be attributable to an event.

There should be no hidden background mutation of trading state.

---

# 3. Layer Architecture

The implementation boundary is:

```text
Data Adapter
     |
     v
Canonical Event Layer
     |
     v
State Store
     |
     +--> Feature Engine
     |       |
     |       v
     |   Probability Engine
     |       |
     |       v
     |   Economic Engine
     |       |
     |       v
     |   Decision Engine
     |
     +--> Execution Engine
             |
             v
        Position Ledger
             |
             v
        Trade Manager
             |
             v
        Outcome/Label Engine
             |
             v
        Learning Engine
```

Research and validation operate around this system rather than inside the trading decision path.

---

# 4. Data Adapter Contract

The Data Adapter converts provider-specific data into canonical events.

Its responsibility is:

```text external data
      ↓
validation
      ↓
normalization
      ↓
CanonicalEvent
```

It must not:

```text generate signals
calculate probability
choose options
calculate position size
modify trading state.
```

---

# 5. Provider Isolation

TrueData-specific semantics must remain outside the core strategy.

The core system must not contain logic such as:

```text if TrueDataFieldX == ...
```

Instead:

```text ProviderAdapter
      ↓
CanonicalEvent
```

This allows the same strategy engine to operate on:

```text historical data
replay data
paper data
live data
synthetic test data.
```

---

# 6. Canonical Event

Every event must have a canonical representation.

Conceptually:

```text
CanonicalEvent {
    EventID
    EventType
    EventTimestamp
    SourceTimestamp
    ReceiptTimestamp
    InstrumentID
    Payload
    SourceVersion
}
```

The exact schema remains subject to the data contract.

---

# 7. Event Types

The initial event taxonomy should distinguish at least:

```text MARKET_EVENT
SESSION_EVENT
ORDER_EVENT
FILL_EVENT
DATA_QUALITY_EVENT
MODEL_EVENT
SYSTEM_EVENT
```

Additional event types may be introduced only when required by an actual state transition.

---

# 8. Event Immutability

Once a canonical event enters the event stream:

```text EventID
EventTimestamp
EventType
Payload
```

are immutable.

Corrections are represented as new events or versioned corrections.

Historical events are never silently overwritten.

---

# 9. Event Ordering

The event processor must consume events according to the canonical ordering contract.

The implementation must explicitly handle:

```text duplicate events
out-of-order events
same-timestamp events
missing events
late events.
```

No implicit behavior is permitted.

---

# 10. Event Idempotency

Every event type must declare whether it is idempotent.

For execution events:

```text FillID
OrderID
```

must prevent duplicate application.

A duplicate event must never duplicate:

```text position
cost
P&L
trade quantity.
```

---

# 11. State Store

The State Store owns the current canonical strategy state.

It is the only authoritative location for mutable trading state.

Components may read state according to their contracts.

They may not independently maintain competing copies of authoritative state.

---

# 12. State Categories

The state store is conceptually divided into:

```text MarketState
FeatureState
ProbabilityState
EconomicState
DecisionState
ExecutionState
PositionState
TradeManagementState
OperationalState
LearningState
```

Not every state category needs to be updated on every event.

---

# 13. Market State

MarketState contains only information derived from currently available market events.

Examples:

```text current underlying price
current option quote state
volume observations
market timestamp
session state
opening-range state
```

It cannot contain future-derived information.

---

# 14. Feature State

FeatureState contains derived variables.

Every feature must declare:

```text FeatureID
SourceVariables
Lookback
UpdateTrigger
Timestamp
MissingDataPolicy
Unit
```

---

# 15. Feature Function

A feature is conceptually:

```text Feature_t = f(AvailableState_t)
```

It must not access:

```text future events
future labels
future outcomes
future aggregated statistics.
```

---

# 16. Probability Engine

The Probability Engine converts eligible features into a probability state.

Conceptually:

```text ProbabilityState_t
=
P(Direction | Evidence_t)
```

where:

```text Evidence_t ⊆ F_t
```

The engine does not execute trades.

---

# 17. Probability Output

The probability engine produces a versioned probability object containing conceptually:

```text Direction
Probability
EvidenceStrength
ModelVersion
ParameterVersion
Timestamp
```

The exact representation is finalized in the canonical variable registry.

---

# 18. Probability Invariants

The implementation must enforce:

```text 0 <= Probability <= 1
```

and:

```text ModelVersion != NULL
ParameterVersion != NULL
```

for every production decision.

---

# 19. Economic Engine

The Economic Engine translates probability and market/option information into expected economic value.

Conceptually:

```text Probability
+
OutcomeDistribution
+
OptionState
+
ExpectedCosts
+
RiskConstraints
        |
        v
ExpectedNetValue
```

It must distinguish:

```text expected value
```

from:

```text realized value.
```

---

# 20. Economic Engine Cannot See the Future

The Economic Engine may use historical distributions, but only those eligible under the current walk-forward boundary.

It cannot use:

```text future option outcome
future realized slippage
future price path
future trade result.
```

---

# 21. Option Selection Contract

The Option Selection component receives:

```text underlying state
directional probability
expected underlying distribution
option candidates
option economic state
execution constraints
```

and produces:

```text selected option
or
NO_VALID_OPTION.
```

It must select the option before execution.

---

# 22. No Retrospective Option Selection

Historical simulation must never select:

```text the option that subsequently generated the best P&L.
```

The candidate selection must be reproducible from information available at the selection timestamp.

---

# 23. Decision Engine

The Decision Engine is the only component authorized to produce:

```text BUY_CE
BUY_PE
NO_TRADE
```

for the baseline architecture.

It receives:

```text ProbabilityState
EconomicState
OptionSelection
RiskState
OperationalState
```

and produces an immutable:

```text Decision.
```

---

# 24. Decision Contract

Conceptually:

```text Decision {
    DecisionID
    Timestamp
    Action
    InstrumentID
    ExpectedValue
    Probability
    RiskAuthorization
    StrategyRuntimeVersion
    ReasonCode
}
```

The exact schema will be finalized later.

---

# 25. Decision Immutability

Once generated:

```text DecisionID
```

and its contents cannot be modified.

A subsequent event may invalidate the decision, but cannot rewrite what the original decision was.

---

# 26. Decision Freshness

Every decision has an explicit validity boundary.

If the market changes sufficiently before execution:

```text old decision
```

may become:

```text EXPIRED.
```

The system must not silently execute stale decisions.

---

# 27. Risk Engine

Risk is an independent subsystem.

Its responsibility is:

```text determine permitted exposure
determine permitted loss
maintain protection
enforce risk invariants.
```

It does not determine whether the underlying is bullish or bearish.

---

# 28. Risk Input

Risk may consume:

```text AccountState
StrategyRiskBudget
OptionPrice
PositionState
CurrentPnL
ProtectionState
```

and other explicitly authorized quantities.

It must not use:

```text future trade outcome.
```

---

# 29. Risk Output

The Risk Engine produces:

```text AuthorizedQuantity
AuthorizedRisk
ProtectionLevel
RiskStatus
```

subject to the learned/configured parameters.

---

# 30. Risk Monotonicity

For an active trade:

```text Protection_(t+1) >= Protection_t
```

whenever both are defined.

Any attempted decrease is rejected.

---

# 31. Mode Engine

The Mode Engine determines the current continuation regime.

Conceptually:

```text Mode_t
=
f(CurrentState_t, HistoricalEvidence_t)
```

Possible states remain:

```text MICRO
SCALP
EXTENDED_SCALP
INTRADAY
```

subject to final validation.

---

# 32. Mode Does Not Own Risk

The Mode Engine cannot directly mutate:

```text RiskBudget
Protection
AuthorizedQuantity.
```

It may produce a mode-transition recommendation consumed by the Trade Manager.

---

# 33. Trade Manager

The Trade Manager coordinates an active position.

It owns:

```text Mode
PeakPnL
ProfitGiveback
ContinuationState
ExitObligation
ExpectedHorizon
```

where each variable has its canonical definition.

---

# 34. Trade Manager Inputs

It consumes:

```text market events
position state
probability state
economic state
mode evidence
risk state
execution events.
```

It may not consume:

```text future labels
future outcomes.
```

---

# 35. Exit Engine

The Exit Engine determines whether the current position must exit.

Potential exit causes include:

```text HARD_RISK
PROFIT_PROTECTION
EMERGENCY_REVERSAL
CONTINUATION_FAILURE
SESSION_CLOSE
SYSTEM_SAFETY
```

Exact conditions are governed by the mathematical specification and learned parameters.

---

# 36. Exit Obligation

Once an exit obligation is generated:

```text ExitObligation = TRUE
```

it persists until:

```text position is actually closed
```

or a formally defined operational resolution occurs.

---

# 37. Execution Engine

The Execution Engine converts authorized decisions into simulated or actual execution events.

It must distinguish:

```text order requested
order accepted
order rejected
order partially filled
order fully filled
order cancelled
fill confirmed.
```

---

# 38. No Synthetic Fill

The Execution Engine cannot assume:

```text order submission = fill.
```

A position changes only from execution evidence.

---

# 39. Execution Modes

The architecture should support:

```text REPLAY_EXECUTION
SIMULATED_EXECUTION
PAPER_EXECUTION
LIVE_EXECUTION
```

through the same conceptual interface.

Only the adapter changes.

---

# 40. Execution Model

For historical simulation:

```text MarketData
+
ExecutionPolicy
+
ExecutionAssumptions
        |
        v
SimulatedFill.
```

The assumptions must be explicitly versioned.

---

# 41. Position Ledger

The Position Ledger is the authoritative accounting layer.

It derives:

```text PositionQuantity
AverageEntryPrice
Exposure
RealizedPnL
```

from execution events.

It must never infer position from:

```text strategy signal.
```

---

# 42. Position Conservation

The ledger must continuously satisfy:

```text PositionQuantity
=
EntryExecutedQuantity
-
ExitExecutedQuantity.
```

Violations cause:

```text RECONCILIATION_REQUIRED.
```

---

# 43. P&L Ledger

P&L is divided into:

```text RealizedPnL
UnrealizedPnL
TotalTradePnL
```

with explicit accounting semantics.

---

# 44. Current P&L

CurrentPnL is a derived state variable.

It must use:

```text actual position
+
declared valuation convention.
```

The valuation convention remains a TODO until the execution/data contract is finalized.

---

# 45. Trade Ledger

Every trade receives:

```text TradeID.
```

The ledger records:

```text entry decision
entry execution
position evolution
management transitions
exit decision
exit execution
final outcome
```

---

# 46. Opportunity Ledger

Every eligible opportunity receives:

```text OpportunityID.
```

It records:

```text opportunity timestamp
available evidence
decision
NO_TRADE reason where applicable
eventual outcome.
```

This is separate from the Trade Ledger.

---

# 47. Label Engine

The Label Engine observes historical outcomes and determines when they become eligible for learning.

It receives:

```text OpportunityRecord
TradeRecord where applicable
FutureMarketEvents
```

but operates only after the predefined observation horizon has matured.

---

# 48. Label Maturity

A label becomes:

```text MATURED
```

only when all information required by its definition is available.

Before that:

```text IMMATURE.
```

---

# 49. Label Isolation

Labels are not fed back into:

```text historical decisions
```

that occurred before label maturity.

They are only eligible for later learning according to the research protocol.

---

# 50. Learning Engine

The Learning Engine consumes:

```text matured labels
historical eligible features
training boundary
current model version
parameter policy
```

and produces:

```text CandidateModel
CandidateParameters.
```

It does not directly replace the production model.

---

# 51. Model Promotion

The sequence is:

```text CandidateModel
      |
      v
Validation
      |
      v
PromotionDecision
      |
      v
ProductionModelVersion
```

The Learning Engine itself does not bypass validation.

---

# 52. Parameter Registry

Every learned parameter must have:

```text ParameterID
Definition
Unit
Domain
TrainingPopulation
Label
EstimationMethod
UpdateFrequency
Version
EffectiveTime
```

---

# 53. Parameter Categories

Parameters are classified as:

```text STRUCTURAL
LEARNED
CONFIGURATION
EXTERNAL-CONTRACT.
```

Structural parameters are architectural.

Learned parameters come from historical evidence.

Configuration parameters are explicitly selected operational values.

External-contract values come from the exchange/provider/broker.

---

# 54. Numerical Parameters Remain Unfrozen

The following remain explicitly unassigned:

```text profit-floor quantile
emergency-reversal probability
continuation threshold
state-transition sensitivity
lookback lengths
risk coefficients
cost assumptions.
```

The implementation must therefore load these from a versioned parameter registry rather than hardcoding them.

---

# 55. Runtime Version

Every decision must resolve to one immutable runtime bundle:

```text StrategyRuntimeVersion
```

which references:

```text FeatureVersion
ProbabilityModelVersion
ParameterVersion
RiskPolicyVersion
ExecutionPolicyVersion
```

This becomes the principal reproducibility identifier.

---

# 56. Operational State

The operational overlay contains:

```text NORMAL
DATA_DEGRADED
RECONCILIATION_REQUIRED
SYSTEM_HALTED
```

This state is independent of whether the trading lifecycle is:

```text NO_POSITION
ACTIVE
EXIT_PENDING
CLOSED.
```

---

# 57. Data-Degraded Behavior

When required market data becomes unavailable:

```text new entries = prohibited
```

unless a future validated policy explicitly permits degraded operation.

Existing exposure remains governed by:

```text existing protection
```

and the operational safety policy.

---

# 58. Reconciliation Behavior

When exposure is uncertain:

```text new entries = prohibited
```

and the system enters:

```text RECONCILIATION_REQUIRED.
```

The system cannot infer that the position disappeared merely because an API response failed.

---

# 59. System Halt

A critical invariant violation produces:

```text SYSTEM_HALTED.
```

The system does not continue trading through known state corruption.

---

# 60. Research Interface

Research must interact with the strategy through versioned interfaces.

It may provide:

```text DatasetVersion
FeatureVersion
ModelVersion
ParameterVersion
ExecutionPolicyVersion
```

It may not mutate live state directly.

---

# 61. Historical Replay Interface

The entire system must support:

```text replay(
    DatasetVersion,
    RuntimeVersion,
    StartTime,
    EndTime
)
```

conceptually.

The replay must generate:

```text event trace
state trace
decision trace
execution trace
P&L trace
```

---

# 62. Deterministic Replay

Given identical:

```text dataset
runtime
initial state
```

the result must be deterministic.

If randomness is intentionally used:

```text RandomSeed
```

must be part of the experiment version.

---

# 63. Test Contract

Every implementation component receives tests at four levels:

```text UNIT
PROPERTY
INTEGRATION
END-TO-END.
```

---

# 64. Unit Tests

Unit tests verify individual mathematical functions.

Examples:

```text probability transformation
expected value
position sizing
protection update
profit giveback
label maturity.
```

---

# 65. Property Tests

Property tests verify invariants across many generated inputs.

Examples:

```text Probability always ∈ [0,1]

Protection never decreases

Position never becomes negative

Duplicate fills never duplicate quantity

PeakPnL never decreases

Giveback never becomes negative.
```

---

# 66. State-Machine Tests

Generated event sequences should attempt to violate:

```text state transition rules
position accounting
execution ordering
reconciliation rules.
```

The expected result must be defined before the test runs.

---

# 67. Integration Tests

Integration tests verify:

```text Event
→ State
→ Feature
→ Probability
→ EconomicValue
→ Decision
```

and:

```text Decision
→ Order
→ Fill
→ Position
→ P&L.
```

---

# 68. Replay Tests

Known historical event sequences should have expected checkpoints.

For example:

```text after event N:
PositionQuantity = expected
Protection = expected
Mode = expected
```

This makes regressions detectable.

---

# 69. Leakage Tests

The implementation must include explicit tests attempting to introduce:

```text future price
future volume
future label
future option state
future aggregate statistics
```

into historical decisions.

The expected result is rejection.

---

# 70. Duplicate Event Tests

Feed:

```text Event A
Event A
```

and verify that the final state equals:

```text Event A
```

processed once.

---

# 71. Out-of-Order Tests

Feed:

```text Event_2
Event_1
```

and verify that the system either:

```text reorders according to the canonical contract
```

or:

```text quarantines/rejects the invalid sequence.
```

It must not silently produce an inconsistent state.

---

# 72. Partial Fill Tests

Test:

```text requested = Q
fill = q1
remaining = Q-q1
```

and verify:

```text Position = q1.
```

A subsequent fill must increase exposure only by the newly executed quantity.

---

# 73. Stop-Gap Tests

A market event crosses protection.

The system must verify:

```text ProtectionTriggered
```

and then simulate:

```text ActualFillPrice
```

according to the execution policy.

It must not assume:

```text fill = protection price.
```

---

# 74. Mode/Risk Test

Create:

```text SCALP -> INTRADAY.
```

Then verify:

```text Protection_new >= Protection_old.
```

The test must fail if the implementation loosens protection.

---

# 75. Learning-Maturity Test

Create an observation whose future horizon has not yet completed.

Verify:

```text LearningEligible = FALSE.
```

Then advance time beyond the required maturity point.

Verify:

```text LearningEligible = TRUE.
```

---

# 76. Holdout Test

Attempt to use final-holdout information to modify parameters.

The research framework must reject the operation.

---

# 77. Version Test

Create:

```text RuntimeVersion A
RuntimeVersion B.
```

Replay the same historical data.

Verify that each result remains attributable to its corresponding version.

Historical A results must not mutate after B is introduced.

---

# 78. Recovery Test

Simulate:

```text process failure
```

then reconstruct from:

```text event log
+
authoritative execution state.
```

The resulting state must match the pre-failure state.

---

# 79. Reconciliation Test

Simulate:

```text internal position = Q
external authoritative position = 0.
```

The system must enter:

```text RECONCILIATION_REQUIRED.
```

It must not silently continue trading.

---

# 80. Performance Test Contract

Performance calculations must consume only:

```text completed/reconciled records
```

and use the declared:

```text performance population
```

and:

```text valuation convention.
```

---

# 81. Research Reproducibility Test

Given the same:

```text ExperimentID
DatasetVersion
RuntimeVersion
ParameterVersion
```

the experiment must reproduce its stored result within the documented numerical tolerance.

---

# 82. Implementation Restrictions

The implementation must not contain:

```text magic constants
hidden state
global mutable trading variables
implicit future-data access
silent fallback values
unversioned learned parameters
automatic parameter mutation
unlogged execution assumptions.
```

---

# 83. Configuration Restrictions

Numerical parameters must be loaded from configuration or the learned-parameter registry.

For example:

```text CONTINUATION_THRESHOLD
```

must not appear as:

```text if x > 0.73:
```

inside arbitrary business logic.

Instead:

```text continuationThreshold = parameterRegistry.get(...)
```

This makes parameter provenance auditable.

---

# 84. Error Handling

Errors are classified as:

```text DATA_ERROR
MODEL_ERROR
EXECUTION_ERROR
ACCOUNTING_ERROR
STATE_ERROR
CONFIGURATION_ERROR
RECONCILIATION_ERROR
SYSTEM_ERROR.
```

Critical errors must fail closed.

---

# 85. Logging Contract

Every important decision should produce structured audit information.

Conceptually:

```text timestamp
event_id
state_version
runtime_version
decision_id
action
probability
expected_value
risk
instrument
reason
```

Sensitive operational information must be handled separately from strategy research data.

---

# 86. No Hidden Logging Dependency

The strategy must not depend on logs for correctness.

Logs provide:

```text observability
```

not:

```text authoritative state.
```

The event/state ledger remains authoritative.

---

# 87. Persistence Contract

The system must be able to persist:

```text event stream
state checkpoints
orders
fills
trades
labels
model versions
parameter versions
experiments.
```

The exact storage technology is an implementation choice.

The semantics are not.

---

# 88. Database Independence

The mathematical specification should not depend on:

```text SQLite
PostgreSQL
files
memory
```

as a conceptual requirement.

Storage adapters may vary.

The domain contracts must not.

---

# 89. Simulation and Live Equivalence

The strategy core should receive the same canonical event semantics in:

```text historical replay
paper trading
live trading.
```

Only:

```text data adapter
execution adapter
```

should differ.

This minimizes simulation/live divergence.

---

# 90. Critical Boundary

The implementation is now divided into:

```text DOMAIN
    |
    +-- mathematical state
    +-- decisions
    +-- risk
    +-- labels
    +-- learning contracts

INFRASTRUCTURE
    |
    +-- TrueData adapter
    +-- broker adapter
    +-- persistence
    +-- clock
    +-- logging

RESEARCH
    |
    +-- experiments
    +-- validation
    +-- walk-forward
    +-- reporting.
```

Domain logic must not depend directly on infrastructure implementations.

---

# 91. First Implementation Scope

The first implementation should not immediately connect to live trading.

Phase one should implement:

```text canonical event model
state machine
feature framework
statistical probability engine
economic engine
option selection
risk engine
execution simulator
position ledger
trade manager
label engine
walk-forward framework
verification suite.
```

---

# 92. No Live Execution Yet

Live execution remains disabled until:

```text structural tests pass
historical replay works
walk-forward validation works
execution assumptions are verified
TrueData contract is mapped
broker contract is mapped
```

---

# 93. External Data Boundary

The following remain intentionally unresolved:

```text TrueData field names
TrueData event semantics
TrueData historical availability
TrueData option-chain semantics
TrueData TBT sequencing
TrueData depth semantics
```

These become adapter-specific implementation TODOs.

---

# 94. External Broker Boundary

The following remain unresolved until the broker contract is supplied:

```text order API semantics
fill semantics
partial-fill behavior
cancellation behavior
latency
transaction costs
actual executable pricing
position reconciliation.
```

---

# 95. Implementation Readiness

The architecture is now:

```text MATHEMATICALLY SPECIFIED       YES
STATE-MACHINE SPECIFIED           YES
RESEARCH PROTOCOL SPECIFIED       YES
FORMAL INVARIANTS SPECIFIED       YES
IMPLEMENTATION CONTRACT           YES
NUMERICAL PARAMETERS              NO
TRUE DATA CONTRACT                PENDING
BROKER CONTRACT                   PENDING
HISTORICAL VALIDATION             NOT YET
LIVE VALIDATION                   NOT YET
```

This is exactly where we should be.

---

# 96. Next Artifact

The next artifact should be the:

# CANONICAL TEST MATRIX AND VERIFICATION PLAN

This will convert the invariants into an executable testing strategy.

For every invariant, we will define:

```text invariant
input condition
event sequence
expected state
expected rejection
expected accounting
expected audit record
severity
```

Then we will construct the **synthetic market scenarios** we previously agreed to use for the brutal attack:

```text false breakout
violent reversal
gap
volatility explosion
volatility collapse
rapid trend continuation
chop
liquidity disappearance
duplicate ticks
out-of-order events
missing data
late fills
partial fills
stop gaps
model updates during active trades
immature labels
```

Only after that test matrix passes should we touch the actual historical TrueData stream.

# END OF IMPLEMENTATION CONTRACT