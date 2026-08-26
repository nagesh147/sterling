# CANONICAL DOMAIN TYPE AND EVENT SCHEMA SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the semantic objects that move through the system.

It establishes:

```text
identity
ownership
types
timestamps
immutability
invariants
serialization
versioning
causal availability
```

The objective is to prevent the implementation from inventing its own interpretation of the mathematical specification.

---

# 2. Domain Model

The canonical runtime flow is:

```text
MarketEvent
    ↓
MarketState
    ↓
FeatureSnapshot
    ↓
Prediction
    ↓
EconomicEvaluation
    ↓
OptionSelection
    ↓
RiskAuthorization
    ↓
PositionSizing
    ↓
OrderIntent
    ↓
Order
    ↓
FillEvent
    ↓
Position
    ↓
AccountingSnapshot
    ↓
TradeOutcome
```

Each object has one authoritative owner.

---

# 3. Identity Principle

Every persistent or economically meaningful object has a stable identity.

Examples:

```text
InstrumentID
EventID
OpportunityID
DecisionID
RiskAuthorizationID
OrderID
FillID
PositionID
TradeID
ExperimentID
RunID
ModelVersion
```

Identifiers are not business values.

They are references to immutable or versioned entities.

---

# 4. Timestamp Principle

Where relevant, an object may have multiple timestamps:

```text EventTime
ReceivedTime
EffectiveTime
DecisionTime
ExecutionTime
PersistenceTime
```

These must never be collapsed merely because they currently happen to be equal.

---

# 5. MarketEvent

Canonical representation:

```text
MarketEvent {
    eventId
    eventType
    instrumentId
    eventTime
    receivedTime
    sequence
    payload
    source
    schemaVersion
}
```

---

# 6. MarketEvent Invariants

```text eventId is unique
eventTime is valid
instrumentId is valid
schemaVersion is known
payload conforms to eventType
```

Events are immutable.

---

# 7. Event Types

The initial event taxonomy is:

```text
QUOTE
TRADE
DEPTH
INSTRUMENT
SESSION
CORPORATE
SYSTEM
```

Additional event types require specification revision.

---

# 8. QuoteEvent

Conceptually:

```text
QuoteEvent {
    eventId
    instrumentId
    eventTime
    bidPrice
    askPrice
    bidQuantity
    askQuantity
    sequence
}
```

The exact provider-to-canonical mapping remains dependent on the external data contract.

---

# 9. Quote Invariants

For instruments where the market contract requires positive prices:

```text bidPrice > 0
askPrice > 0
```

and:

```text bidPrice <= askPrice
```

unless the data contract explicitly defines another valid market state.

---

# 10. TradeEvent

```text
TradeEvent {
    eventId
    instrumentId
    eventTime
    price
    quantity
    sequence
}
```

The event represents an observed market transaction.

It does not represent a strategy execution.

---

# 11. DepthEvent

```text
DepthEvent {
    eventId
    instrumentId
    eventTime
    levels
    sequence
}
```

Each depth level contains:

```text price
quantity
side
level
```

The exact depth representation remains subject to the provider contract.

---

# 12. Instrument

The canonical instrument object represents the identity and trading characteristics of an instrument.

```text
Instrument {
    instrumentId
    symbol
    instrumentType
    exchange
    currency
    expiry
    strike
    optionType
    lotSize
    tickSize
    tradingStatus
    version
}
```

---

# 13. Instrument Identity

Instrument identity must be stable across the historical dataset.

A symbol string alone is not necessarily sufficient.

The identity must distinguish contracts with different:

```text expiry
strike
option type
exchange
contract specification.
```

---

# 14. OptionType

Where applicable:

```text CALL
PUT
NONE
```

An equity or index instrument may use:

```text NONE.
```

---

# 15. Instrument Lifecycle

An instrument may transition through:

```text NOT_ACTIVE
ACTIVE
SUSPENDED
EXPIRED
DELISTED
```

The permitted transitions are explicit.

---

# 16. SessionState

```text SessionState {
    sessionId
    sessionPhase
    sessionOpenTime
    sessionCloseTime
    currentTime
    openingRange
    sessionVersion
}
```

---

# 17. SessionPhase

The canonical phase enumeration is conceptually:

```text PRE_OPEN
OPENING_RANGE
ACTIVE
CLOSING
CLOSED
HALTED
```

Exact exchange-specific semantics remain external-contract dependent.

---

# 18. OpeningRange

```text OpeningRange {
    startTime
    endTime
    high
    low
    width
    complete
}
```

The range is immutable once the canonical completion condition is satisfied.

---

# 19. MarketState

The MarketState represents the causally reconstructable market condition at a specific point.

```text MarketState {
    stateId
    asOfTime
    sessionState
    instrumentStates
    marketRegime
    volatilityState
    directionalState
    liquidityState
    openingRange
    stateVersion
}
```

---

# 20. State Immutability

Historical states are immutable.

A new event creates:

```text State_(t+1)
```

rather than mutating:

```text State_t.
```

---

# 21. State Transition

Canonical form:

```text
transition(
    State_t,
    Event_t
)
→
State_(t+1)
```

The transition must be deterministic.

---

# 22. State Transition Record

For auditability:

```text StateTransition {
    transitionId
    previousStateId
    resultingStateId
    eventId
    transitionType
    transitionTime
    stateVersion
}
```

---

# 23. State Transition Invariants

A transition must have:

```text valid predecessor
valid event
valid transition type
valid resulting state
```

An impossible transition is a hard failure.

---

# 24. FeatureSnapshot

```text FeatureSnapshot {
    featureSnapshotId
    asOfTime
    sourceStateId
    features
    featureVersion
    validity
}
```

---

# 25. FeatureSnapshot Causality

A FeatureSnapshot at time `t` may depend only on:

```text events <= t
states <= t
```

under the canonical availability rules.

---

# 26. Feature Validity

Possible states:

```text VALID
PARTIAL
INVALID
UNAVAILABLE
```

An invalid feature set cannot silently become a valid prediction input.

---

# 27. Prediction

```text Prediction {
    predictionId
    opportunityId
    predictionTime
    featureSnapshotId
    modelVersion
    outputs
    uncertainty
    validity
}
```

---

# 28. Prediction Immutability

A prediction is immutable once produced.

If a model produces a revised prediction later:

```text new PredictionID.
```

The original prediction remains part of the historical record.

---

# 29. Prediction Causality

Prediction at:

```text PredictionTime = t
```

must not depend on:

```text information with availability time > t.
```

---

# 30. EconomicEvaluation

```text EconomicEvaluation {
    evaluationId
    opportunityId
    evaluationTime
    predictionId
    instrumentId
    expectedGrossValue
    expectedExecutionCost
    expectedNetValue
    eligibility
    economicModelVersion
}
```

---

# 31. Economic Invariants

If:

```text ExpectedNetValue
=
ExpectedGrossValue
-
ExpectedExecutionCost
```

then this relationship must hold exactly according to the canonical numerical convention.

---

# 32. EconomicEligibility

The object explicitly records:

```text ELIGIBLE
INELIGIBLE
UNKNOWN
```

`UNKNOWN` must not silently become `ELIGIBLE`.

---

# 33. OptionSelection

```text OptionSelection {
    selectionId
    opportunityId
    selectionTime
    candidateInstruments
    selectedInstrumentId
    selectionScore
    selectionReason
    selectionVersion
}
```

---

# 34. OptionSelection Invariants

The selected instrument must:

```text belong to candidate set
be active
satisfy instrument constraints
```

and must not be expired.

---

# 35. RiskAuthorization

```text RiskAuthorization {
    authorizationId
    opportunityId
    authorizationTime
    authorizedRisk
    riskPerUnit
    riskStatus
    riskPolicyVersion
    expiry
}
```

---

# 36. RiskAuthorization Invariants

```text authorizedRisk >= 0
riskPerUnit >= 0
```

where applicable.

The authorization cannot exceed the applicable risk budget.

---

# 37. Risk Immutability

Once issued:

```text RiskAuthorization
```

is immutable.

A changed authorization creates:

```text new authorization.
```

No downstream component may mutate it.

---

# 38. AuthorizedQuantity

```text AuthorizedQuantity {
    sizingId
    authorizationId
    instrumentId
    rawQuantity
    executableQuantity
    lotSize
    sizingTime
    sizingVersion
}
```

---

# 39. Quantity Invariants

For a long-only whole-lot strategy:

```text executableQuantity >= 0
executableQuantity % lotSize = 0
```

and:

```text executableRisk <= authorizedRisk.
```

---

# 40. OrderIntent

An OrderIntent represents a requested execution action.

```text OrderIntent {
    orderIntentId
    opportunityId
    decisionId
    instrumentId
    side
    quantity
    orderType
    limitPrice
    authorizationId
    intentTime
    expiry
}
```

---

# 41. OrderIntent Invariants

An OrderIntent must reference:

```text valid decision
valid risk authorization
valid instrument
valid quantity.
```

An OrderIntent does not prove execution occurred.

---

# 42. Order

An Order represents an accepted execution request.

```text Order {
    orderId
    orderIntentId
    instrumentId
    side
    requestedQuantity
    orderType
    submittedTime
    status
    executionVersion
}
```

---

# 43. Order Status

Conceptually:

```text CREATED
SUBMITTED
ACKNOWLEDGED
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
REJECTED
EXPIRED
FAILED
```

Only explicitly permitted transitions are valid.

---

# 44. Order/Fills Separation

The following implication is prohibited:

```text Order.status = FILLED
```

without authoritative fill evidence.

Where the external execution contract uses an authoritative status event, that event must still satisfy the canonical fill/accounting rules.

---

# 45. FillEvent

```text FillEvent {
    fillId
    orderId
    instrumentId
    executionTime
    quantity
    price
    fees
    externalExecutionId
    sequence
}
```

---

# 46. Fill Invariants

A fill must reference:

```text valid order
valid instrument
positive quantity
valid execution price.
```

Duplicate authoritative fills must be detected.

---

# 47. Position

```text Position {
    positionId
    instrumentId
    side
    quantity
    averageEntryPrice
    openedAt
    lastUpdatedAt
    status
}
```

---

# 48. Position Status

Conceptually:

```text FLAT
OPEN
PARTIALLY_CLOSED
CLOSED
RECONCILIATION_REQUIRED
```

---

# 49. Position Ownership

The Position Ledger is authoritative.

A position cannot be created merely because:

```text OrderIntent
```

exists.

It requires authoritative execution evidence.

---

# 50. Position Conservation

For a long-only position:

```text PositionQuantity
=
Σ EntryFills
-
Σ ExitFills.
```

---

# 51. Average Entry Price

Average entry price is derived from authoritative entry fills according to the canonical accounting method.

It must not be manually supplied by the signal engine.

---

# 52. Trade

A Trade represents the lifecycle of an economically distinct strategy position.

```text Trade {
    tradeId
    opportunityId
    positionId
    instrumentId
    entryTime
    exitTime
    entrySummary
    exitSummary
    status
}
```

---

# 53. Trade Status

```text OPEN
CLOSED
ABORTED
INVALIDATED
```

---

# 54. AccountingSnapshot

```text AccountingSnapshot {
    snapshotId
    asOfTime
    positionId
    realizedPnL
    unrealizedPnL
    currentPnL
    peakPnL
    profitGiveback
    drawdown
    costs
    accountingVersion
}
```

---

# 55. Accounting Invariants

The canonical relationship between:

```text realized
unrealized
current
peak
giveback
drawdown
```

must be preserved exactly according to the mathematical accounting specification.

---

# 56. Current P&L

The canonical variable is:

```text CurrentPnL.
```

There is no independent:

```text CurrentProfit.
```

Synonymous variables are prohibited.

---

# 57. Peak P&L

At time `t`:

```text PeakPnL(t)
=
max(CurrentPnL(τ))
```

for all valid `τ <= t`.

Therefore:

```text PeakPnL(t+1) >= PeakPnL(t).
```

---

# 58. Profit Giveback

Conceptually:

```text ProfitGiveback
=
PeakPnL - CurrentPnL
```

subject to the exact accounting convention.

---

# 59. TradeOutcome

```text TradeOutcome {
    tradeId
    entryTime
    exitTime
    entryPrice
    exitPrice
    quantity
    grossPnL
    costs
    netPnL
    maximumFavorableExcursion
    maximumAdverseExcursion
    holdingTime
    outcomeStatus
}
```

---

# 60. Future-Derived Fields

The following are post-entry/post-exit information:

```text MFE
MAE
final NetPnL
actual HoldingTime
```

They are prohibited from the causal decision path for the trade that generated them.

---

# 61. HistoricalLabel

```text HistoricalLabel {
    labelId
    opportunityId
    decisionTime
    horizon
    observationWindow
    outcome
    labelClass
    availabilityTime
    labelVersion
}
```

---

# 62. Label Availability

A label becomes available only after its required future observation has occurred.

Therefore:

```text LabelAvailabilityTime > DecisionTime
```

for genuinely future-derived labels.

---

# 63. Label Isolation

Historical labels may be consumed by:

```text training
validation
research analysis.
```

They cannot be consumed by:

```text live decision logic.
```

---

# 64. Experiment

```text Experiment {
    experimentId
    hypothesis
    parentExperimentId
    modelVersion
    datasetVersion
    parameterVersion
    protocolVersion
    status
}
```

---

# 65. Run

```text ExperimentRun {
    runId
    experimentId
    codeVersion
    environmentVersion
    randomSeed
    startedAt
    completedAt
    status
}
```

---

# 66. ValidationReport

```text ValidationReport {
    reportId
    candidateId
    protocolVersion
    datasetVersion
    results
    failures
    warnings
    disposition
}
```

---

# 67. ModelVersion

```text ModelVersion {
    modelId
    version
    specificationVersion
    modelFamily
    parameterVersion
    createdAt
    status
}
```

---

# 68. Version Compatibility

A runtime component may consume an artifact only when its compatibility contract permits:

```text ModelVersion
+
FeatureVersion
+
RiskPolicyVersion
+
ExecutionVersion
```

---

# 69. Canonical Event Envelope

All events should use a common envelope:

```text EventEnvelope {
    eventId
    eventType
    eventTime
    source
    schemaVersion
    correlationId
    causationId
    sequence
    payload
}
```

---

# 70. Correlation ID

`correlationId` connects events belonging to one logical workflow.

Example:

```text Opportunity
    ↓
Decision
    ↓
Risk
    ↓
Order
    ↓
Fill
```

---

# 71. Causation ID

`causationId` identifies the immediate event or command that caused the current event.

This allows causal reconstruction.

---

# 72. Event Ordering

The system must use the canonical ordering contract:

```text sequence
+
eventTime
+
source ordering rules
```

as defined by the data contract.

It must not invent ordering from favorable trading outcomes.

---

# 73. Serialization

Each canonical domain object must have a deterministic serialization representation.

The representation must preserve:

```text identity
numeric precision
timestamps
enumerations
version information.
```

---

# 74. Serialization Is Not Domain Logic

Serialization code must not:

```text calculate P&L
change risk
select options
change state.
```

It only converts representations.

---

# 75. Immutability Classes

Objects are classified as:

```text IMMUTABLE_EVENT
IMMUTABLE_DECISION
IMMUTABLE_AUTHORIZATION
MUTABLE_RUNTIME_STATE
DERIVED_SNAPSHOT
PERSISTED_LEDGER.
```

---

# 76. Immutable Events

Examples:

```text MarketEvent
FillEvent
OrderAcceptedEvent
PositionTransitionEvent
```

cannot be modified after creation.

---

# 77. Mutable Runtime State

Runtime state may change through:

```text canonical state transition
```

only.

---

# 78. Ledger Objects

Ledgers are append-oriented.

Corrections should create:

```text correction event
```

rather than destructive mutation.

---

# 79. Schema Evolution

A schema change requires:

```text SchemaVersion increment.
```

Backward compatibility must be explicitly classified:

```text compatible
conditionally compatible
incompatible.
```

---

# 80. Unknown Fields

Unknown external fields must not automatically enter canonical objects.

Provider-specific information remains at the adapter boundary unless explicitly promoted into the canonical schema.

---

# 81. Null Semantics

`null`, `unknown`, and `unavailable` are not automatically equivalent.

Where the distinction affects strategy behavior, the domain schema must represent them separately.

---

# 82. Invalid State Representation

The schema must make it possible to represent:

```text INVALID
UNAVAILABLE
RECONCILIATION_REQUIRED
```

rather than forcing invalid data into ordinary numeric fields.

---

# 83. Numeric Precision

Prices, quantities, fees, and monetary values require explicit precision semantics.

Floating-point representation must not silently determine financial correctness.

The exact implementation representation remains to be selected.

---

# 84. Domain Invariants

```text DOM-001 id="3p9u4r"
Events are immutable.

DOM-002
Event IDs are unique.

DOM-003
Orders do not create positions.

DOM-004
Only authoritative fills change positions.

DOM-005
Position quantity is conserved.

DOM-006
CurrentPnL has one canonical definition.

DOM-007
PeakPnL is monotonic non-decreasing.

DOM-008
Future-derived labels cannot enter live causal paths.

DOM-009
Every prediction identifies its model version.

DOM-010
Every risk authorization identifies its policy version.

DOM-011
Every order references valid authorization.

DOM-012
Every fill references a valid order.

DOM-013
Every position references authoritative fills.

DOM-014
Every trade is traceable to an opportunity.

DOM-015
Every experiment is versioned.

DOM-016
Every validation result identifies its protocol.

DOM-017
Unknown data cannot silently become valid data.

DOM-018
Schema changes are versioned.

DOM-019
Causal timestamps are preserved.

DOM-020
Domain objects cannot bypass their owning module.
```

---

# 85. Canonical End-to-End Trace

A complete valid trade must be reconstructable as:

```text
MarketEvent
    ↓
StateTransition
    ↓
FeatureSnapshot
    ↓
Prediction
    ↓
EconomicEvaluation
    ↓
OptionSelection
    ↓
RiskAuthorization
    ↓
AuthorizedQuantity
    ↓
OrderIntent
    ↓
Order
    ↓
FillEvent
    ↓
PositionTransition
    ↓
AccountingSnapshot
    ↓
TradeOutcome
```

If any link is missing, the system must expose the break rather than infer it silently.

---

# 86. Decision Lineage

Every executed trade must answer:

```text What market state existed?
What features were available?
What prediction was produced?
What economic value was calculated?
Why was the instrument selected?
Why was risk authorized?
Why was this quantity selected?
What order was submitted?
What actually filled?
What P&L resulted?
```

The schema is designed to make every answer reconstructable.

---

# 87. Implementation Readiness

At this point we have specified:

```text variables
ownership
dependencies
interfaces
domain objects
events
state
risk
execution
accounting
research
validation
```

The next step is therefore no longer another conceptual specification.

We can now define the concrete:

# CANONICAL REPOSITORY AND PACKAGE ARCHITECTURE

That artifact will map these contracts into the actual project structure, including:

```text domain/
application/
infrastructure/
research/
validation/
simulation/
execution/
accounting/
tests/
schemas/
```

and, critically, define which modules are allowed to import which other modules.

Only after that should we begin implementation scaffolding.