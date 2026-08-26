# CANONICAL DATA-TO-EVENT CONTRACT

Version 1.0

## 1. Purpose

This contract defines the boundary between external market data and the mathematical trading system.

Its purpose is to ensure that:

```text
provider-specific data
        ↓
canonical event
        ↓
canonical state
        ↓
mathematical model
```

is deterministic, auditable, causal, and independent of the specific data vendor.

The TrueData documentation will populate the provider-specific fields later.

No unknown field will be guessed.

---

# 2. Fundamental Rule

The mathematical system consumes only:

```text
CanonicalEvent
```

It must never consume:

```text
TrueDataField
```

directly.

Therefore:

```text
TrueData Adapter
        |
        v
Canonical Event Contract
        |
        v
Domain
```

The provider adapter is the only place where vendor-specific semantics are interpreted.

---

# 3. Data Boundary

The external boundary is:

```text
EXTERNAL DATA
    |
    |  provider-specific
    v
PROVIDER ADAPTER
    |
    |  canonical
    v
EVENT STREAM
    |
    v
STATE ENGINE
```

The strategy does not know whether the underlying event originated from:

```text TrueData
historical file
replay fixture
paper feed
live feed
synthetic generator.
```

---

# 4. Canonical Data Record

Every incoming observation must ultimately resolve to a canonical record containing conceptually:

```text
CanonicalRecord {
    RecordID
    EventType
    InstrumentID
    EventTimestamp
    SourceTimestamp
    ReceiptTimestamp
    Sequence
    Payload
    Source
    SourceVersion
}
```

Some fields may remain optional depending on event type.

---

# 5. Record Identity

Every record must have a deterministic identity.

Conceptually:

```text RecordID id="6z7xq2"
=
Source
+
SourceRecordIdentity
+
SourceVersion
```

The exact construction depends on the provider contract.

The identity must support duplicate detection.

---

# 6. Timestamp Contract

The system distinguishes:

```text EventTimestamp
SourceTimestamp
ReceiptTimestamp
ProcessingTimestamp
```

These must never be conflated.

Their semantics are:

```text EventTimestamp
=
time at which the market event occurred.

SourceTimestamp
=
timestamp supplied by the provider.

ReceiptTimestamp
=
time our system received the event.

ProcessingTimestamp
=
time our system processed the event.
```

The exact provider semantics remain:

```text UNKNOWN
```

until the documentation confirms them.

---

# 7. Causal Timestamp

The trading model uses the canonical market/event timestamp for causal ordering.

Receipt time cannot silently replace event time.

For example:

```text market event occurred at 09:31:00
received at 09:31:02
```

The event belongs to:

```text 09:31:00
```

not:

```text 09:31:02.
```

Latency is separately recorded.

---

# 8. Event Ordering

The canonical ordering contract is:

```text EventTimestamp
    ↓
ProviderSequence, if authoritative
    ↓
RecordID
```

The exact secondary ordering mechanism remains:

```text TODO — TrueData documentation.
```

This is particularly important for TBT data.

---

# 9. Event Types

The canonical event taxonomy begins with:

```text MARKET_TICK
MARKET_QUOTE
MARKET_TRADE
MARKET_DEPTH
OPTION_CHAIN_UPDATE
SESSION_EVENT
DATA_QUALITY_EVENT
```

Execution-related events are separate:

```text ORDER_EVENT
FILL_EVENT
BROKER_POSITION_EVENT
```

Research events are separate again:

```text LABEL_EVENT
MODEL_EVENT
PARAMETER_EVENT
```

Not every provider will supply every category.

---

# 10. Market Tick

A market tick represents an authoritative market observation at a specific event time.

Conceptually:

```text MarketTick {
    InstrumentID
    Timestamp
    Price
    Quantity
    TradeIdentifier
}
```

Exact field availability:

```text UNKNOWN
```

until the TrueData documentation is supplied.

---

# 11. Quote Event

A quote event represents bid/ask information.

Conceptually:

```text QuoteEvent {
    InstrumentID
    Timestamp
    BidPrice
    BidQuantity
    AskPrice
    AskQuantity
}
```

The system must preserve the distinction:

```text bid != ask != last trade.
```

This distinction is essential for execution modeling.

---

# 12. Trade Event

A trade event represents an observed market transaction.

It must not automatically be interpreted as:

```text our execution.
```

This is a critical boundary.

```text MARKET_TRADE
    !=
OUR_FILL
```

---

# 13. Market Depth Event

If depth is available, it must be represented independently.

Conceptually:

```text DepthEvent {
    InstrumentID
    Timestamp
    BidLevels
    AskLevels
}
```

The exact number of levels and update semantics remain:

```text UNKNOWN.
```

---

# 14. TBT Event

If TrueData provides tick-by-tick/TBT information, the provider adapter must establish whether each record represents:

```text new observation
trade
quote update
depth update
snapshot
incremental update
```

This distinction is mandatory.

A TBT stream cannot be treated as a homogeneous sequence of prices without understanding its semantics.

---

# 15. Snapshot Versus Incremental Update

The adapter must distinguish:

```text SNAPSHOT
```

from:

```text DELTA/INCREMENTAL UPDATE.
```

If the source provides only snapshots:

```text state reconstruction
```

must not assume intermediate events existed.

If the source provides deltas:

```text previous state
+
delta
=
new state.
```

The exact semantics remain:

```text TODO — TrueData documentation.
```

---

# 16. Instrument Identity

Every market event must identify its instrument canonically.

For an option:

```text InstrumentID
Underlying
Expiry
Strike
OptionType
ContractSpecification
```

must ultimately be resolvable.

The exact provider identifier and contract metadata remain:

```text UNKNOWN.
```

---

# 17. Underlying Identity

For the baseline NIFTY strategy:

```text UnderlyingInstrument
```

must be explicitly identified.

The system must not infer the underlying solely from:

```text symbol text
```

if the provider supplies a stronger identifier.

---

# 18. Option Identity

An option is uniquely identified by its contract attributes.

At minimum:

```text Underlying
Expiry
Strike
CE/PE
```

must be distinguishable.

Two contracts with identical strikes but different expiries are different instruments.

---

# 19. Instrument Master

The eventual system needs an immutable instrument master containing:

```text InstrumentID
Underlying
InstrumentType
Expiry
Strike
OptionType
LotSize
TickSize
TradingStatus
EffectiveDates
```

The exact provider fields are:

```text TODO.
```

---

# 20. Price Contract

Every price must have:

```text value
unit
precision
timestamp
source
```

A price cannot be stored as an unqualified floating-point number in the conceptual model.

---

# 21. Quantity Contract

Every quantity must specify:

```text semantic meaning
unit
precision
```

For example:

```text market trade quantity
quote quantity
contract quantity
lot quantity
```

must remain distinguishable.

---

# 22. Volume Contract

Volume must not be assumed to mean:

```text number of trades.
```

The provider documentation must establish whether the field represents:

```text traded quantity
number of trades
cumulative volume
other.
```

Status:

```text UNKNOWN.
```

---

# 23. Cumulative Fields

If a provider supplies cumulative quantities:

```text cumulative_t
```

the adapter may derive:

```text incremental_t
=
cumulative_t
-
cumulative_(t-1)
```

only if the provider semantics guarantee that such subtraction is valid.

Resets must be explicitly handled.

---

# 24. Reset Detection

A cumulative field may reset at:

```text session boundary
instrument reset
provider restart
other documented boundary.
```

A negative delta must not automatically be interpreted as:

```text negative volume.
```

It must trigger reset handling or data-quality classification.

---

# 25. Missing Data

Missing data is represented explicitly.

Conceptually:

```text MISSING
UNKNOWN
INVALID
NOT_APPLICABLE
```

are distinct states.

They must not collapse into:

```text 0
```

---

# 26. Zero Versus Missing

For example:

```text BidQuantity = 0
```

may be valid.

Whereas:

```text BidQuantity = MISSING
```

means no valid observation exists.

The mathematical system must preserve that distinction.

---

# 27. Data Quality Event

A data-quality problem becomes a canonical event.

Examples:

```text DATA_GAP
DUPLICATE
OUT_OF_ORDER
INVALID_VALUE
SOURCE_DISCONNECT
TIMESTAMP_ERROR
INSTRUMENT_MISMATCH
```

The exact severity policy is defined separately.

---

# 28. Data Quality Does Not Become Market Data

A data-quality event cannot accidentally become:

```text price
volume
signal
feature.
```

It modifies:

```text OperationalState
```

and potentially:

```text FeatureAvailability.
```

---

# 29. Market State Construction

The State Engine consumes canonical market events:

```text Event_t
```

and updates:

```text MarketState_t.
```

Conceptually:

```text MarketState_(t+1)
=
Transition(MarketState_t, Event_t)
```

---

# 30. State Ownership

MarketState owns observations such as:

```text current price
current quote
current depth
session state
opening-range state
recent market observations
```

It does not own:

```text probability
risk
position
P&L.
```

---

# 31. Opening Range

The opening-range state is derived from canonical market events.

Conceptually:

```text OpeningRange =
events within predefined session interval.
```

The exact session boundaries remain dependent on the exchange/data contract.

---

# 32. Opening Range Information Boundary

After the opening range is completed:

```text OpeningRangeState
```

becomes available to the strategy.

It must contain only information observed during the defined interval.

No later event may retroactively alter the opening range used by an earlier decision.

---

# 33. Feature Construction

Features consume:

```text MarketState
```

and previously defined canonical state.

They cannot access:

```text raw provider fields
future market events
future labels.
```

---

# 34. Feature Timestamp

Every feature has a timestamp:

```text FeatureTimestamp.
```

It represents the latest information used to construct the feature.

Therefore:

```text FeatureTimestamp <= DecisionTimestamp.
```

---

# 35. Lookback Contract

Every historical feature must explicitly define:

```text LookbackStart
LookbackEnd
```

and:

```text LookbackEnd <= DecisionTimestamp.
```

---

# 36. Rolling Statistics

Rolling quantities such as:

```text mean
standard deviation
percentile
rank
volatility
```

must use only observations within their declared historical window.

No full-dataset precomputation is permitted.

---

# 37. Historical Distribution Contract

Every empirical distribution must have:

```text PopulationDefinition
EligibilityRule
TrainingEndTime
ObservationTimestamp
OutcomeDefinition
```

This makes the distribution auditable.

---

# 38. Distribution Update

At decision time `t`:

```text Distribution_t
```

may use only eligible historical observations:

```text observation_time < t
```

and whose required labels are already mature.

---

# 39. Probability Input

The Probability Engine consumes only:

```text canonical features
historical distribution state
versioned model parameters.
```

It does not consume raw provider data.

---

# 40. Economic Input

The Economic Engine additionally consumes:

```text option state
expected execution cost
risk constraints
probability distribution.
```

All of these must have valid timestamps.

---

# 41. Option Data Boundary

The option-selection engine requires enough information to evaluate:

```text option price
liquidity
contract identity
time to expiry
execution cost
risk.
```

Which exact TrueData fields provide these remains:

```text UNKNOWN.
```

---

# 42. Quote Freshness

Option quotes used for a decision must satisfy an explicit freshness rule.

Conceptually:

```text DecisionTime - QuoteTimestamp <= MaxQuoteAge.
```

The numerical maximum is:

```text UNFROZEN.
```

It must be determined by historical evidence and execution requirements.

---

# 43. Stale Quote Handling

A quote older than the allowed freshness boundary becomes:

```text STALE.
```

A stale quote cannot silently be treated as current.

It may result in:

```text NO_TRADE
```

or:

```text DATA_DEGRADED.
```

depending on the final policy.

---

# 44. Bid/Ask Execution Boundary

For a long option entry:

```text ask
```

is generally the relevant immediately executable side.

For liquidation:

```text bid
```

is generally relevant.

However, the final historical execution model must establish exactly how this is simulated.

---

# 45. No Mid-Price Assumption

The system must not use:

```text mid-price
```

as an executable fill merely because it is mathematically convenient.

If mid-price is used for valuation:

```text valuation price
```

and:

```text executable price
```

remain separate concepts.

---

# 46. TBT Does Not Equal Executable Price

A last-traded price event does not establish that our strategy could transact at that price.

This distinction is mandatory.

```text MarketTradePrice
    !=
ExecutableFillPrice
```

unless the execution contract explicitly establishes equivalence.

---

# 47. Execution Cost

Expected execution cost must be a separate canonical variable.

Conceptually:

```text ExpectedExecutionCost_t
```

is estimated using only information available at `t`.

Actual execution cost is:

```text ActualExecutionCost.
```

These must never be conflated.

---

# 48. Slippage

Slippage must be represented explicitly.

Conceptually:

```text Slippage
=
ActualFillPrice
-
ReferenceExecutionPrice.
```

The exact reference price is part of the execution-policy contract.

---

# 49. Latency

Where available, the system records:

```text DecisionTimestamp
OrderTimestamp
FillTimestamp.
```

This permits:

```text decision-to-order latency
order-to-fill latency
```

to be analyzed.

If historical latency is unavailable, the simulator must explicitly model it.

---

# 50. Historical Execution Model

The historical simulator consumes:

```text CanonicalMarketEvents
+
ExecutionPolicyVersion.
```

It produces:

```text SimulatedOrder
SimulatedFill.
```

The simulation must disclose that these are modeled executions.

---

# 51. Observed Versus Modeled

Every execution record must distinguish:

```text OBSERVED
```

from:

```text MODELED.
```

This prevents simulated fills from being mistaken for actual historical broker fills.

---

# 52. Broker Boundary

The broker adapter will eventually transform:

```text OrderIntent
```

into:

```text BrokerOrder
```

and broker responses into:

```text CanonicalOrderEvent
CanonicalFillEvent.
```

Broker-specific semantics remain outside the strategy domain.

---

# 53. State Transition Boundary

Only canonical events may mutate canonical state.

Therefore:

```text raw provider response
```

cannot directly modify:

```text PositionState.
```

---

# 54. Data-to-State Dependency Example

A simplified dependency chain is:

```text TrueData tick
      ↓
Canonical MARKET_TICK
      ↓
MarketState.current_price
      ↓
FeatureState
      ↓
ProbabilityState
      ↓
EconomicState
      ↓
Decision
```

Each arrow represents an explicit transformation.

---

# 55. Option Dependency Example

For an option decision:

```text UnderlyingMarketEvents
        ↓
UnderlyingState
        ↓
DirectionalDistribution
        ↓
Probability
        +
OptionMarketEvents
        ↓
OptionState
        ↓
ExpectedOptionEconomics
        ↓
OptionSelection
        ↓
Decision
```

The option does not become selected simply because the underlying direction is predicted correctly.

---

# 56. Execution Dependency Example

```text Decision
   ↓
RiskAuthorization
   ↓
OrderIntent
   ↓
ExecutionPolicy
   ↓
OrderEvent
   ↓
FillEvent
   ↓
PositionState
   ↓
P&L.
```

---

# 57. Learning Dependency Example

```text Decision_t
   ↓
FutureMarketEvents
   ↓
Outcome
   ↓
Label
   ↓
Maturity
   ↓
Learning Eligibility
   ↓
Training Dataset
   ↓
Model Update
```

The temporal ordering is mandatory.

---

# 58. Canonical Field Registry

Every provider field will eventually be registered using:

```text FieldID
CanonicalVariable
Provider
ProviderField
EventType
DataType
Unit
Precision
TimestampSemantics
UpdateFrequency
HistoricalAvailability
Entitlement
MissingValueSemantics
Transformation
Owner
Dependency
Status
```

---

# 59. Example Registry Entry

Before documentation:

```text CanonicalVariable:
UnderlyingPrice

Provider:
TrueData

ProviderField:
UNKNOWN

EventType:
MARKET_TICK

Unit:
PRICE

Timestamp:
UNKNOWN

UpdateFrequency:
EVENT_DRIVEN

HistoricalAvailability:
UNKNOWN

Entitlement:
UNKNOWN

Status:
PENDING_DOCUMENTATION
```

No assumption is made.

---

# 60. Canonical Variable to Provider Mapping

The final mapping will look conceptually like:

```text UnderlyingPrice
       |
       +-- TrueData field X
       |
       +-- transformation: identity
       |
       +-- timestamp: provider event timestamp
       |
       +-- precision: provider-defined
       |
       +-- historical: confirmed
```

Only the documentation can populate the unknown fields.

---

# 61. Provider Field to Canonical Event Mapping

The adapter contract becomes:

```text ProviderField
      ↓
Validation
      ↓
Normalization
      ↓
CanonicalEventField.
```

No business logic belongs here.

---

# 62. Validation Before Normalization

The adapter first determines whether the source value is valid.

For example:

```text malformed price
```

must not be normalized into:

```text 0.
```

It becomes:

```text INVALID_VALUE.
```

---

# 63. Normalization

Normalization may include:

```text type conversion
unit conversion
symbol mapping
timestamp normalization
precision normalization.
```

Normalization must preserve economic meaning.

---

# 64. No Semantic Normalization Without Evidence

The adapter may not infer semantics.

For example, if a field is named:

```text volume
```

the system cannot assume its meaning without documentation.

It remains:

```text UNKNOWN_SEMANTICS.
```

until verified.

---

# 65. Data Entitlement

Every required field must eventually be classified:

```text AVAILABLE
AVAILABLE_WITH_SUBSCRIPTION
NOT_AVAILABLE
UNKNOWN.
```

A mathematically useful variable that cannot actually be obtained becomes:

```text implementation blocker
```

only when the relevant component is reached.

---

# 66. Historical Availability

Historical availability must distinguish:

```text field exists now
```

from:

```text field existed historically.
```

A live field is not automatically a historical field.

---

# 67. Historical Granularity

Availability must record:

```text tick
TBT
second
minute
daily
```

separately.

A field available at minute resolution cannot automatically satisfy a tick-level dependency.

---

# 68. Data Frequency Versus Model Frequency

The architecture explicitly separates:

```text Data Update Frequency
```

from:

```text Model Update Frequency.
```

Example:

```text TBT data
   ↓
state updates every event
   ↓
probability recalculated at validated decision boundaries
```

There is no requirement that every tick trigger a complete model recalculation.

---

# 69. Event Coalescing

If the system eventually coalesces events:

```text many ticks
   ↓
one state update
```

the transformation must be explicitly defined.

Otherwise event coalescing can change strategy behavior.

---

# 70. No Silent Downsampling

Converting:

```text TBT
```

to:

```text minute bars
```

must be an explicit transformation.

The resulting data source is then:

```text derived-minute-data.
```

It cannot be treated as original minute data.

---

# 71. Minute Data Versus TBT

Both may coexist:

```text TBT
 |
 +--> event state
 |
 +--> reconstructed minute features
```

The system must record which representation produced each feature.

This allows us to test whether tick-level information actually adds incremental predictive value.

---

# 72. Incremental-Information Experiment

Eventually we should compare:

```text Model_A:
minute information only

Model_B:
minute + TBT information.
```

The evaluation must use identical:

```text walk-forward periods
cost assumptions
labels
validation methodology.
```

This determines whether TBT adds genuine edge.

---

# 73. Important Principle

TBT is therefore treated as:

```text additional information
```

not:

```text automatic predictive advantage.
```

If Model B does not improve robust out-of-sample performance, the additional complexity is not justified.

---

# 74. Data Quality Score

A future implementation may maintain:

```text DataQualityState.
```

It should summarize whether required inputs are:

```text complete
fresh
ordered
consistent.
```

The exact mathematical scoring mechanism is not yet required.

The critical requirement is that degraded data cannot silently appear normal.

---

# 75. Canonical Event Provenance

Every event must retain provenance:

```text Source
SourceRecordID
SourceVersion
ReceivedAt
```

This allows a historical decision to be traced back to its originating record.

---

# 76. Provenance Chain

Eventually we must be able to trace:

```text Decision
 ↓
Feature
 ↓
Canonical Event
 ↓
Provider Record
```

This is necessary for auditability.

---

# 77. Decision Provenance

A production decision must be able to answer:

```text Which market events produced this state?

Which features were calculated?

Which model version was used?

Which parameter version was used?

Which option quote was used?

Which execution assumptions were used?
```

---

# 78. No Untracked Derived Data

Any derived quantity that influences a decision must have:

```text definition
source
timestamp
version
```

It cannot exist merely as an undocumented variable inside code.

---

# 79. Data Lineage

The complete lineage is:

```text Provider Record
      ↓
Canonical Event
      ↓
State Variable
      ↓
Feature
      ↓
Probability
      ↓
Economic Quantity
      ↓
Decision
```

This becomes the canonical audit chain.

---

# 80. TrueData Documentation TODO

When the authoritative documentation is supplied, we will populate:

```text exact field names
exact event types
timestamp semantics
TBT semantics
quote semantics
depth semantics
option-chain fields
historical coverage
precision
update behavior
subscription entitlement
instrument identifiers.
```

These are the only parts deliberately left unresolved here.

---

# 81. Data Contract Invariants

The following become canonical:

```text DATA-001
Every consumed field has a canonical definition.

DATA-002
Every canonical event has a timestamp.

DATA-003
Event ordering is deterministic.

DATA-004
Missing values are not silently converted to zero.

DATA-005
Market trades are not treated as our fills.

DATA-006
Provider fields never directly enter domain logic.

DATA-007
Future data cannot enter historical state.

DATA-008
Derived data records its source and transformation.

DATA-009
Historical availability is explicitly verified.

DATA-010
Data entitlement is explicitly verified.

DATA-011
TBT semantics are documented before TBT-dependent logic is implemented.

DATA-012
Observed execution and modeled execution are distinct.

DATA-013
Instrument identity is unambiguous.

DATA-014
Price, quantity, and volume semantics are explicitly defined.

DATA-015
Dataset versions are immutable.
```

---

# 82. Current Status

The data boundary is now structurally complete.

```text EVENT MODEL                  COMPLETE
TIMESTAMP MODEL                 DEFINED
PROVENANCE MODEL                DEFINED
DATA QUALITY MODEL              DEFINED
INSTRUMENT MODEL                DEFINED
STATE TRANSFORMATION            DEFINED
FEATURE BOUNDARY                DEFINED
EXECUTION BOUNDARY              DEFINED
LEARNING BOUNDARY               DEFINED
TRUE DATA FIELD MAPPING         PENDING DOCUMENTATION
BROKER FIELD MAPPING            PENDING DOCUMENTATION
```

---

# 83. Next Step

The next artifact is now substantially different from the previous ones.

We should construct the:

# CANONICAL VARIABLE REGISTRY

This becomes the single source of truth connecting:

```text Mathematical specification
        ↕
Data-to-event contract
        ↕
State machine
        ↕
Feature engine
        ↕
Probability engine
        ↕
Economic engine
        ↕
Risk engine
        ↕
Execution engine
        ↕
Learning engine
        ↕
Implementation.
```

For every variable, we will record its exact:

```text ID
name
definition
type
unit
owner
source
event dependency
update frequency
causal availability
formula
allowed consumers
invariants
learned/configured status
version
TrueData mapping
status.
```

That registry is important because from that point onward, **a variable is not allowed to exist unless it appears in the registry**.

That gives us a single source of truth before we write the first line of strategy implementation code.