# CANONICAL EVENT SCHEMA AND STATE SCHEMA

Version 1.0

## 1. Purpose

This document defines the runtime representation of the strategy's canonical events and state.

The system follows:

```text
External Data
    ↓
Canonical Event
    ↓
State Transition
    ↓
New State
    ↓
Feature / Probability / Economics
    ↓
Decision
```

The schemas below are the contracts between those stages.

---

# 2. Fundamental Runtime Rule

The system is event-driven.

Conceptually:

```text
State_t + Event_t
        ↓
Transition Function
        ↓
State_(t+1)
```

The transition function must be deterministic given:

```text current state
incoming event
active runtime version.
```

No hidden external state may influence the transition.

---

# 3. Canonical Event Envelope

Every event uses a common envelope:

```text
CanonicalEvent {
    event_id
    event_type

    instrument_id

    event_timestamp
    source_timestamp
    receipt_timestamp

    sequence_id

    source
    source_version

    payload

    schema_version
}
```

The payload varies by event type.

---

# 4. Event Identity

`event_id` uniquely identifies the canonical event.

Invariant:

```text
event_id must be unique.
```

If the provider does not provide a suitable identifier, the adapter must construct one deterministically.

It must never use a random identifier for historical replay.

---

# 5. Event Type

`event_type` is an enum.

Initial domain:

```text
MARKET_TICK
MARKET_QUOTE
MARKET_TRADE
MARKET_DEPTH
OPTION_CHAIN_UPDATE

SESSION_EVENT
DATA_QUALITY_EVENT

ORDER_EVENT
FILL_EVENT
POSITION_EVENT
```

Research-only events are kept outside the market event stream:

```text
LABEL_EVENT
MODEL_EVENT
PARAMETER_EVENT
```

---

# 6. Event Timestamp

The canonical event timestamp determines causal availability.

Invariant:

```text
event_timestamp <= decision_timestamp
```

for every event used by that decision.

An event received late does not become a future event merely because it arrived after the decision.

---

# 7. Receipt Timestamp

`receipt_timestamp` records local arrival time.

It exists primarily for:

```text latency analysis
data-quality analysis
operational monitoring.
```

It does not replace `event_timestamp` for historical causality.

---

# 8. Sequence ID

`sequence_id` provides deterministic ordering where the provider supplies authoritative sequencing.

Status:

```text PENDING_TRUE_DATA_CONTRACT
```

Until the provider semantics are confirmed.

---

# 9. Market Tick Event

Conceptually:

```text
MarketTickEvent {
    instrument_id

    price
    quantity

    trade_id

    event_timestamp
}
```

The exact meaning of `price`, `quantity`, and `trade_id` remains subject to the provider contract.

---

# 10. Market Quote Event

```text
MarketQuoteEvent {
    instrument_id

    bid_price
    bid_quantity

    ask_price
    ask_quantity

    event_timestamp
}
```

Invariant:

```text bid_price <= ask_price
```

when both are valid and the instrument's market structure requires this relationship.

Invalid crossed or malformed quotes are handled by the data-quality layer rather than silently corrected.

---

# 11. Market Trade Event

```text
MarketTradeEvent {
    instrument_id

    trade_price
    trade_quantity

    trade_id

    event_timestamp
}
```

This represents an observed market transaction.

It does not represent our execution.

```text
MarketTradeEvent
        !=
FillEvent
```

---

# 12. Market Depth Event

```text
MarketDepthEvent {
    instrument_id

    bid_levels[]
    ask_levels[]

    event_timestamp
}
```

Each level conceptually contains:

```text
DepthLevel {
    price
    quantity
    level
}
```

The number of levels and whether updates are snapshots or deltas remain:

```text UNKNOWN
```

until TrueData documentation is verified.

---

# 13. Option Chain Event

The canonical option-chain event must preserve contract identity.

Conceptually:

```text
OptionChainEvent {
    underlying_id
    observation_timestamp

    contracts[]
}
```

Each contract references:

```text
instrument_id
expiry
strike
option_type

bid
ask
bid_quantity
ask_quantity
```

The exact provider representation remains external.

---

# 14. Session Event

```text
SessionEvent {
    session_id
    session_action
    effective_timestamp
}
```

Possible actions:

```text SESSION_OPEN
OPENING_RANGE_COMPLETE
SESSION_CLOSE
```

The final exchange/session calendar remains an external contract.

---

# 15. Data Quality Event

```text
DataQualityEvent {
    severity
    category
    affected_instrument
    affected_time_range
    description
}
```

Possible categories:

```text MISSING_DATA
DUPLICATE
OUT_OF_ORDER
INVALID_VALUE
STALE_DATA
SOURCE_DISCONNECT
INSTRUMENT_ERROR
SEQUENCE_ERROR
```

---

# 16. Order Event

```text OrderEvent {
    order_id
    instrument_id

    side
    requested_quantity

    order_status

    event_timestamp
}
```

The strategy does not infer an execution merely because an order event exists.

---

# 17. Fill Event

```text FillEvent {
    order_id
    fill_id

    instrument_id

    side
    executed_quantity
    fill_price

    execution_cost

    event_timestamp
}
```

The fill event is authoritative for position changes.

---

# 18. Position Event

A position event is primarily an external reconciliation event.

```text PositionEvent {
    instrument_id
    external_quantity

    valuation_timestamp
}
```

It must not be confused with the internally derived position ledger.

---

# 19. Event Immutability

Once canonicalized:

```text EventPayload
EventTimestamp
EventType
InstrumentID
EventID
```

are immutable.

Corrections are represented by new events.

---

# 20. Event Validation Pipeline

Incoming provider data passes through:

```text Provider Data
    ↓
Structural Validation
    ↓
Semantic Validation
    ↓
Normalization
    ↓
Canonicalization
    ↓
Event Validation
    ↓
Event Store
    ↓
State Transition
```

Invalid events do not enter the normal state-transition path.

---

# 21. State Root

The runtime maintains one authoritative state root:

```text StrategyState
```

Conceptually:

```text
StrategyState {
    market
    session
    features
    probability
    economics
    decision
    risk
    execution
    position
    trade_management
    operations
}
```

The exact state sections are defined below.

---

# 22. Market State

```text
MarketState {
    underlying
    instruments
    current_quotes
    current_trades
    depth
    last_event_timestamp
}
```

MarketState represents information currently known from market events.

---

# 23. Underlying State

```text
UnderlyingState {
    instrument_id

    last_price
    last_trade_quantity

    bid_price
    ask_price
    bid_quantity
    ask_quantity

    observation_timestamp
}
```

Unavailable fields remain explicitly unavailable.

They are not converted into zero.

---

# 24. Option State

```text
OptionState {
    instrument_id
    underlying_id

    expiry
    strike
    option_type

    bid_price
    ask_price
    bid_quantity
    ask_quantity

    observation_timestamp
}
```

Option state is maintained per instrument.

---

# 25. Session State

```text
SessionState {
    session_id

    lifecycle
    session_start
    session_end

    opening_range
}
```

Lifecycle:

```text
PRE_OPEN
OPEN
OPENING_RANGE
POST_OPENING_RANGE
CLOSING
CLOSED
```

Exact applicable session semantics remain subject to the exchange contract.

---

# 26. Opening Range State

```text
OpeningRangeState {
    status

    start_timestamp
    end_timestamp

    high
    low
    width
}
```

Invariant after completion:

```text high >= low
width = high - low
```

---

# 27. Feature State

```text
FeatureState {
    directional_evidence
    volatility_state
    momentum_state
    market_structure_state
    time_of_day_state

    feature_timestamp
    feature_version
}
```

Each feature must carry enough lineage to reconstruct its inputs.

---

# 28. Feature Snapshot

A feature snapshot represents the feature values available at a specific causal point.

```text
FeatureSnapshot {
    timestamp
    feature_version

    values

    source_state_version
}
```

A decision consumes a specific feature snapshot.

It must not dynamically read mutable feature values after the decision.

---

# 29. Probability State

```text
ProbabilityState {
    direction
    directional_probability

    evidence_strength

    model_version
    parameter_version

    timestamp
}
```

Invariant:

```text 0 <= directional_probability <= 1
```

---

# 30. Economic State

```text
EconomicState {
    expected_gross_value
    expected_execution_cost
    expected_net_value

    economic_margin

    timestamp
}
```

The economic state must reference the probability/model version used to generate it.

---

# 31. Candidate Option State

```text
CandidateOptionState {
    candidates[]

    evaluation_timestamp
    option_data_timestamp
}
```

Each candidate must retain:

```text instrument identity
market state
economic state
eligibility status.
```

---

# 32. Decision State

```text
DecisionState {
    decision_id
    decision_timestamp

    action

    selected_option

    probability_snapshot
    economic_snapshot
    risk_authorization

    reason_code

    runtime_version
}
```

The decision is immutable after creation.

---

# 33. Decision Actions

The baseline action domain is:

```text NO_TRADE
BUY_CE
BUY_PE
```

There is deliberately no:

```text SELL
REVERSE
AVERAGE
PYRAMID
```

in the baseline decision domain.

Those would require explicit architectural additions.

---

# 34. Risk State

```text RiskState {
    strategy_risk_budget

    authorized_risk
    authorized_quantity

    protection_level

    risk_status
}
```

Risk state is independent of directional probability.

---

# 35. Risk Status

Possible states:

```text NOT_AUTHORIZED
AUTHORIZED
PROTECTION_ACTIVE
RISK_BREACH
HALTED
```

A risk breach cannot automatically increase permitted exposure.

---

# 36. Execution State

```text ExecutionState {
    orders[]
    fills[]

    pending_orders
    unresolved_orders

    execution_policy_version
}
```

This state represents execution lifecycle, not strategy belief.

---

# 37. Position State

```text PositionState {
    instrument_id

    quantity
    average_entry_price

    exposure_value

    realized_pnl
    current_pnl

    position_status
}
```

Position quantity is derived from authoritative fills.

---

# 38. Position Status

```text FLAT
OPEN
EXIT_PENDING
RECONCILIATION_REQUIRED
CLOSED
```

`CLOSED` means the position lifecycle has been completed and reconciled.

---

# 39. Position Conservation Invariant

The system must satisfy:

```text
PositionQuantity
=
TotalEntryExecutedQuantity
-
TotalExitExecutedQuantity
```

within the defined accounting precision.

---

# 40. Trade Management State

```text TradeManagementState {
    trade_id

    mode

    peak_pnl
    profit_giveback

    expected_horizon
    continuation_value

    emergency_reversal_probability

    exit_obligation

    trade_management_version
}
```

---

# 41. Peak P&L Invariant

```text
PeakPnL_(t+1)
=
max(PeakPnL_t, CurrentPnL_(t+1))
```

Therefore:

```text PeakPnL_(t+1) >= PeakPnL_t
```

---

# 42. Protection Invariant

For an active position:

```text Protection_(t+1) >= Protection_t
```

unless the strategy specification explicitly defines a different protective representation.

A dynamic management mode cannot weaken established protection.

---

# 43. Operational State

```text OperationalState {
    system_status
    data_quality
    reconciliation_status

    halt_reason
}
```

System status:

```text NORMAL
DATA_DEGRADED
RECONCILIATION_REQUIRED
SYSTEM_HALTED
```

---

# 44. State Version

Every authoritative state snapshot receives:

```text state_version
```

This allows a decision to reference exactly which state produced it.

Conceptually:

```text Decision
    ↓
StateVersion = S12345
```

The system can therefore reconstruct the decision context.

---

# 45. State Timestamp

Every state snapshot has:

```text state_timestamp
```

which represents the latest canonical event incorporated into that state.

Invariant:

```text state_timestamp
>=
timestamp of every incorporated event.
```

---

# 46. State Transition Contract

The state engine behaves as:

```text
Transition(
    previous_state,
    canonical_event,
    runtime_version
)
→
next_state
```

It must not directly consume:

```text provider API response
database query
future event
random mutable global state.
```

---

# 47. State Transition Atomicity

One event must produce one logically atomic transition.

Conceptually:

```text
State_t
+
Event_t
=
State_(t+1)
```

The system must not expose a partially updated state to downstream decision components.

---

# 48. Event Processing Order

For each event:

```text validate
    ↓
deduplicate
    ↓
order
    ↓
transition state
    ↓
derive permitted state variables
    ↓
evaluate decision boundary
```

The ordering is intentional.

---

# 49. Decision Boundary

Not every event must produce a trading decision.

The system distinguishes:

```text state update event
```

from:

```text decision-evaluation event.
```

This prevents unnecessary recomputation and, more importantly, prevents accidental changes to the decision cadence.

---

# 50. Decision Snapshot

When a decision is generated, the system captures:

```text MarketState snapshot
FeatureState snapshot
ProbabilityState snapshot
EconomicState snapshot
RiskState snapshot
RuntimeVersion
```

The decision therefore becomes reproducible.

---

# 51. No Mutable Decision Dependencies

After creation:

```text Decision
```

cannot dynamically point to:

```text current_probability
current_price
current_risk
```

because those values may subsequently change.

It stores immutable references/snapshots.

---

# 52. Trade Lifecycle State

A trade lifecycle is:

```text NO_TRADE
    ↓
OPPORTUNITY
    ↓
ENTRY_AUTHORIZED
    ↓
ORDER_PENDING
    ↓
ACTIVE
    ↓
EXIT_REQUIRED
    ↓
EXIT_PENDING
    ↓
CLOSED
```

Not every opportunity reaches `ACTIVE`.

---

# 53. No-Trade Path

The system explicitly supports:

```text OPPORTUNITY
    ↓
NO_TRADE
```

Reasons may include:

```text insufficient probability
insufficient expected value
invalid option
poor liquidity
excessive execution cost
risk unavailable
stale data
operational restriction.
```

---

# 54. Entry Authorization

Entry authorization requires all applicable conditions:

```text opportunity valid
probability valid
economic value valid
option valid
risk authorized
data valid
operational state normal
```

Failure of any mandatory condition results in:

```text NO_TRADE.
```

---

# 55. Order Creation

An authorized decision produces:

```text OrderIntent
```

not an assumed fill.

```text Decision
    ↓
OrderIntent
    ↓
Execution Adapter
    ↓
Order Event
```

---

# 56. Fill Creation

Only a `FillEvent` changes:

```text PositionState.quantity.
```

This is one of the strongest runtime invariants.

---

# 57. Active Trade Transition

The first authoritative fill creates or increases:

```text ACTIVE position.
```

The strategy must calculate:

```text entry timestamp
entry quantity
average entry price
initial protection
```

according to the frozen contracts.

---

# 58. Active Trade Event Processing

While active:

```text MarketEvent
    ↓
MarketState update
    ↓
Feature update
    ↓
Probability update where permitted
    ↓
Trade-management evaluation
    ↓
Risk evaluation
    ↓
Possible exit obligation
```

The system must not reinterpret historical entry information using current information.

---

# 59. Exit Transition

An exit obligation is generated when the mathematical exit condition is satisfied.

Then:

```text EXIT_REQUIRED
    ↓
EXIT_PENDING
    ↓
FillEvent
    ↓
CLOSED
```

The exit obligation remains active until resolved.

---

# 60. Learning State

Learning state is intentionally separate from live decision state.

```text LearningState {
    matured_labels
    dataset_version
    model_version
    parameter_version
}
```

Live state cannot mutate the production model implicitly.

---

# 61. Research State

Research state is not part of live trading state.

It contains:

```text ExperimentID
DatasetVersion
TrainingBoundary
ValidationBoundary
TestBoundary
CandidateModel
EvaluationResult
PromotionDecision
```

This prevents research state from contaminating runtime state.

---

# 62. State Persistence

The implementation should support:

```text EventLog
+
StateCheckpoint
```

rather than relying solely on mutable database rows.

This permits:

```text event replay
recovery
audit
deterministic reconstruction.
```

---

# 63. State Checkpoint

A checkpoint contains:

```text state_version
state_timestamp
runtime_version
complete_strategy_state
```

A checkpoint cannot omit authoritative variables required to reconstruct behavior.

---

# 64. Recovery

Recovery proceeds:

```text latest valid checkpoint
        ↓
replay subsequent events
        ↓
reconstructed state.
```

The reconstructed state must match the state before failure.

---

# 65. State Hash

For reproducibility, the implementation should produce a deterministic state representation that can be hashed.

Conceptually:

```text StateHash = Hash(CanonicalState)
```

This allows two replay runs to verify that they reached identical states.

---

# 66. Event-to-State Audit

Every state mutation must be attributable to:

```text EventID
```

Therefore an audit record can answer:

```text Which event changed this variable?
```

This is particularly important for:

```text PositionQuantity
ProtectionLevel
PeakPnL
Mode
OperationalState.
```

---

# 67. Variable Mutation Rule

A state variable can change only if:

```text an allowed event
```

or:

```text an explicitly defined deterministic transition
```

authorizes the change.

No arbitrary component may mutate shared state.

---

# 68. Circular State Prevention

The state graph must remain acyclic within one event transition.

For example:

```text Probability
    ↓
Decision
    ↓
Risk
```

is valid.

But:

```text Probability
    ↓
Risk
    ↓
Probability
```

within the same transition is prohibited.

---

# 69. Temporal DAG

The overall architecture remains a temporal DAG:

```text
t-1
 |
 v
State_t
 |
 +--> Features_t
 |       |
 |       v
 |   Probability_t
 |       |
 |       v
 |   Economics_t
 |       |
 |       v
 |    Decision_t
 |       |
 |       v
 |    Execution
 |       |
 |       v
 |   Outcome_(t+n)
 |       |
 |       v
 |     Label
 |       |
 |       v
 |   Learning
 |       |
 |       v
 Model_(future)
```

The apparent cycle from learning back to future decisions occurs across time.

It is not a same-timestamp circular dependency.

---

# 70. Schema Versioning

Every event and state schema receives:

```text schema_version
```

Breaking changes require a new schema version.

Historical records must remain interpretable under the schema version under which they were created.

---

# 71. Unknown External Fields

The schemas deliberately do not yet contain provider-specific fields such as:

```text exact TrueData tick field
exact TBT sequence field
exact depth representation
exact option-chain structure.
```

Those belong in the adapter mapping.

They must not contaminate the canonical domain schema.

---

# 72. Critical Schema Invariants

```text SCH-001
Every event has an immutable identity.

SCH-002
Every event has a causal timestamp.

SCH-003
Market trades are distinct from our fills.

SCH-004
Only authoritative fills change position quantity.

SCH-005
One event produces one atomic state transition.

SCH-006
State snapshots are versioned.

SCH-007
Decisions use immutable snapshots.

SCH-008
Future events cannot modify historical decision state.

SCH-009
PeakPnL cannot decrease.

SCH-010
Protection cannot loosen.

SCH-011
Research state cannot silently mutate production state.

SCH-012
Provider-specific semantics remain inside adapters.

SCH-013
Missing data is distinct from zero.

SCH-014
Unknown provider semantics are never guessed.

SCH-015
The state transition graph contains no same-time circular dependency.
```

---

# 73. Architecture Status

At this point:

```text
Mathematical Specification       COMPLETE
State Transition Specification   COMPLETE
Implementation Contract          COMPLETE
Verification Plan                COMPLETE
Data-to-Event Contract           COMPLETE
Variable Registry                COMPLETE
Event Schema                     COMPLETE
State Schema                     COMPLETE
```

The remaining external dependencies are:

```text TrueData field semantics
TrueData historical coverage
TrueData TBT/depth semantics
Broker execution semantics
```

The remaining numerical dependencies are:

```text learned statistical parameters
execution-cost parameters
risk parameters
management thresholds.
```

Neither category should be invented.

---

# 74. Next Artifact

The next artifact should be the **Canonical State Transition Table**.

We have defined the schemas. Now we need to make the state machine completely explicit.

For every meaningful event, we will specify:

```text Current State
+
Incoming Event
+
Preconditions
        ↓
Transition
        ↓
New State
        ↓
Variables Allowed to Change
        ↓
Variables Forbidden to Change
        ↓
Side Effects
        ↓
Invariant Checks
```

That will give us the final bridge between the mathematical state model and actual event-driven implementation.

After that, we can move into the research/data pipeline specification rather than continuing to invent architecture.