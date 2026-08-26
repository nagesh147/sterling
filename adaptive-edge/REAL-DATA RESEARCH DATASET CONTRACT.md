# REAL-DATA RESEARCH DATASET CONTRACT

## Canonical Data Architecture — Version 1.0

## 1. Purpose

This specification defines the exact transformation:

```text
RAW TRUE DATA
     |
     v
RAW EVENT STORE
     |
     v
NORMALIZED EVENT STORE
     |
     v
CANONICAL MARKET STATE
     |
     v
DERIVED FEATURES
     |
     v
DECISION DATASET
     |
     v
HISTORICAL LABELS
```

The central rule is:

```text
Raw data is immutable.
Derived data is reproducible.
Labels are generated separately.
Trading decisions never modify historical data.
```

---

# 2. Three Data Layers

The research system has three fundamentally different data classes.

```text
OBSERVED
DERIVED
LABEL
```

They must never be conflated.

---

# 3. OBSERVED DATA

Observed data is information that actually came from the market feed.

Examples:

`timestamp`

`instrument`

`price`

`bid`

`ask`

`volume`

`trade`

`depth`

`option contract information`.

Observed data is immutable.

---

# 4. DERIVED DATA

Derived data is calculated exclusively from observed information.

Examples:

`returns`

`volatility`

`imbalance`

`range`

`rolling statistics`

`state variables`

`regime indicators`.

Derived data may be recalculated.

---

# 5. LABEL DATA

Labels contain future information relative to the decision timestamp.

Examples:

`future return`

`MFE`

`MAE`

`future maximum drawdown`

`opportunity persistence`

`future option return`.

Labels are explicitly prohibited from entering runtime state.

---

# 6. Information Boundary

The architecture must enforce:

```text
OBSERVED
   |
   v
DERIVED
   |
   v
DECISION
```

while:

```text
FUTURE EVENTS
   |
   v
LABEL
```

The two paths must never merge before model training.

---

# 7. Canonical Event

Every raw event becomes a canonical event:

```text
Event =
{
    event_id,
    timestamp,
    instrument_id,
    event_type,
    observed_fields,
    source_metadata
}
```

The exact source field mapping remains a TODO until TrueData documentation is supplied.

---

# 8. Event Identity

Every event requires a deterministic identity.

Conceptually:

```text
EventID =
hash(
    source,
    instrument,
    timestamp,
    event_type,
    sequence,
    observed_content
)
```

The exact identity algorithm will depend on what the source actually provides.

---

# 9. Why Event Identity Matters

Without event identity we cannot reliably detect:

`duplicates`

`retransmissions`

`missing events`

`out-of-order events`.

---

# 10. Timestamp Contract

Every event must contain:

`source timestamp`

and:

`canonical timestamp`.

The canonical timestamp must use one standard timezone representation.

For Indian-market research:

`Asia/Kolkata`

is the semantic session timezone.

Internally, a monotonic absolute timestamp representation may also be maintained.

---

# 11. Timestamp Precision

The system must preserve the highest precision supplied by the source.

We do not round:

```text
12:30:01.123
```

to:

```text
12:30:01
```

before event ordering.

Precision reduction, if required later, occurs only in a derived layer.

---

# 12. Event Ordering

Canonical events must satisfy:

```text
timestamp_(n+1) >= timestamp_n
```

within the canonical event stream.

If the source supplies sequence information, it must participate in ordering.

---

# 13. Out-of-Order Events

An out-of-order event is not silently discarded.

It receives:

```text
DataQualityFlag = OUT_OF_ORDER
```

and is handled according to the validated reconstruction policy.

---

# 14. Duplicate Events

A duplicate must be classified as:

`EXACT_DUPLICATE`

or:

`POSSIBLE_DUPLICATE`

or:

`VALID_REPEAT`.

Repeated market events are not automatically duplicates.

---

# 15. Missing Events

Missing data is explicitly represented as:

`MISSING`.

Never convert:

`MISSING`

into:

`ZERO`.

This is a hard invariant.

---

# 16. Instrument Identity

Every event must resolve to a canonical:

`InstrumentID`.

The identity must distinguish:

`underlying`

`equity`

`future`

`CE`

`PE`

and individual option contracts.

---

# 17. Option Identity

An option contract requires at minimum conceptual identity:

```text
Underlying
Expiry
Strike
OptionType
```

Additional source-specific identifiers will be mapped later.

---

# 18. Contract Lifecycle

Each option contract has:

```text
Listing
   |
   v
Tradable
   |
   v
Expiry
```

Historical research must never use information from an option contract outside its actual tradable lifecycle.

---

# 19. No Survivorship

The historical option universe must represent the contracts that actually existed at that historical timestamp.

We cannot construct history from:

"options that exist today."

---

# 20. Underlying-Option Link

At timestamp `t`:

```text
UnderlyingState_t
        |
        v
OptionUniverse_t
```

The option universe must be the universe available at that timestamp.

---

# 21. Market Session

The dataset must explicitly encode:

`session_date`

`market_open`

`market_close`

`pre-open if applicable`

`trading_holiday`

`special session`.

The exact exchange calendar becomes a data dependency.

---

# 22. Session Boundary

Events cannot accidentally bleed between sessions.

For example:

```text
PreviousSession
      X
CurrentSession
```

must remain separate unless a feature explicitly uses overnight information.

---

# 23. Overnight Information

If a feature uses previous-session information, that dependency must be explicit.

For example:

```text
PreviousClose
```

is legitimate.

But:

```text
CurrentSessionFutureClose
```

is forbidden.

---

# 24. Corporate Actions

For equity instruments, the research dataset must preserve whether historical prices are:

`raw`

or:

`corporate-action adjusted`.

The strategy must use one explicitly defined representation.

---

# 25. Index Data

For index instruments, corporate-action treatment is different.

The dataset must not blindly apply equity adjustment logic to indices.

---

# 26. Price Fields

The canonical price layer distinguishes:

`LastTradedPrice`

`BidPrice`

`AskPrice`

`MidPrice`

where available.

We do not substitute one for another without an explicit rule.

---

# 27. Mid Price

If valid bid and ask exist:

```text
Mid_t = (Bid_t + Ask_t) / 2
```

This is a derived quantity.

It is not an observed market field unless the source explicitly supplies it.

---

# 28. Spread

If valid:

```text
Spread_t = Ask_t - Bid_t
```

If either side is unavailable:

```text
Spread_t = MISSING
```

not zero.

---

# 29. Relative Spread

When meaningful:

```text
RelativeSpread_t
=
(Ask_t - Bid_t) / Mid_t
```

This allows comparisons across price levels.

---

# 30. Trade Data

A trade event conceptually contains:

`timestamp`

`price`

`quantity`

and any available trade metadata.

The exact field availability remains a TrueData mapping TODO.

---

# 31. Volume

Volume is an observed quantity only when supplied by the source.

Derived volume measures must be clearly distinguished from:

`source-reported volume`.

---

# 32. Depth

If order-book data is available:

the canonical structure must preserve:

`bid levels`

`ask levels`

`price`

`quantity`

`depth level`.

No aggregation should destroy information before the raw layer is persisted.

---

# 33. Depth Snapshot Versus Increment

The dataset must distinguish:

`full snapshot`

from:

`incremental update`.

These cannot be treated identically.

---

# 34. Order-Book Reconstruction

If the source supplies incremental depth updates:

the research engine must reconstruct:

```text
Book_t
=
Book_(t-1)
+
ValidUpdates_t
```

The reconstructed book must be reproducible.

---

# 35. Book Validity

Every reconstructed book receives a validity state:

`VALID`

`PARTIAL`

`INVALID`

`UNKNOWN`.

---

# 36. Partial Book

A partial book must not automatically be interpreted as:

"the rest of the book has zero quantity."

Missing depth remains:

`UNKNOWN`.

---

# 37. Option Chain Snapshot

At a decision timestamp:

the canonical option chain should conceptually contain:

```text
Expiry
Strike
Type
Bid
Ask
LTP
Volume
OpenInterest
IV
Greeks
```

only where the source genuinely provides the quantity.

Unavailable fields remain:

`UNAVAILABLE`.

---

# 38. No Synthetic Greeks Yet

If IV or Greeks are not directly supplied, we do not silently invent them.

We first determine whether:

`reconstruction`

is mathematically justified from available fields.

---

# 39. Source Semantics

Every observed field ultimately requires:

```text
SourceField
CanonicalField
Unit
Precision
TimestampSemantics
UpdateFrequency
HistoricalAvailability
Entitlement
MissingValueSemantics
```

These remain TODO until the actual TrueData documentation is mapped.

---

# 40. Raw Data Immutability

Once ingested:

```text
RAW_EVENT
```

cannot be modified.

If normalization rules change:

we generate a new derived dataset.

We do not rewrite the raw evidence.

---

# 41. Data Version

Every dataset receives:

`DATA_VERSION`.

Example:

```text
TD_RAW_V1
TD_NORMALIZED_V1
TD_FEATURE_V1
```

The exact naming convention can be finalized later.

---

# 42. Reproducibility

Given:

`DATA_VERSION`

and:

`event range`

we must reproduce the same normalized events.

---

# 43. Data Quality Score

Each event can carry quality metadata such as:

`timestamp_valid`

`instrument_valid`

`price_valid`

`quote_valid`

`sequence_valid`.

The quality score is metadata.

It must not silently alter the raw observation.

---

# 44. Quality State

A canonical event can therefore have:

```text
QUALITY =
VALID
PARTIAL
INVALID
```

and detailed flags explaining why.

---

# 45. Data Quarantine

Events failing critical integrity checks should enter:

`QUARANTINE`.

They are not silently deleted.

---

# 46. Why Quarantine Matters

Deleting bad data can create:

`selection bias`.

The research report must know:

"this period contained unusable data."

---

# 47. Canonical State

After normalization:

```text
Events_<=t
      |
      v
CanonicalState_t
```

The state contains only information that legitimately exists at `t`.

---

# 48. State Is Not Historical Data

This distinction is important.

Raw events represent:

`what happened`.

State represents:

`what the strategy currently knows`.

---

# 49. State Update

Conceptually:

```text
State_(t+1)
=
Transition(
    State_t,
    Event_(t+1)
)
```

No future event may participate.

---

# 50. Feature Update

Features are derived from state:

```text
Feature_t
=
F(State_<=t)
```

or directly:

```text
Feature_t
=
F(Events_<=t)
```

provided the dependency is causal.

---

# 51. Rolling Features

For a rolling quantity:

```text
Window_t
=
[t - L, t]
```

where:

`L`

is the feature lookback.

---

# 52. Window Boundary

The current event is included only if the mathematical definition explicitly says so.

We must avoid ambiguous definitions such as:

"last one minute."

Instead define exact interval semantics.

---

# 53. Example

A left-closed/right-closed interval might be:

```text
(t - 60 seconds, t]
```

Another feature may use:

```text
[t - 60 seconds, t)
```

These are not equivalent.

Every feature definition must specify its interval convention.

---

# 54. Aggregation

Minute bars are derived representations.

For a minute interval:

```text
Open
High
Low
Close
Volume
```

must be generated from the event stream using explicitly defined boundaries.

---

# 55. Tick-to-Minute Consistency

If both tick and minute data are available:

the derived minute representation should be independently compared against the source minute representation.

Differences must be recorded.

---

# 56. No Mixing Without Verification

We cannot use:

`source minute close`

for one feature

and:

`locally reconstructed minute close`

for another

without documenting the semantic difference.

---

# 57. Event-to-Bar Aggregation

For each bar:

```text
OPEN  = first valid event
HIGH  = maximum valid event
LOW   = minimum valid event
CLOSE = final valid event
VOLUME = defined volume aggregation
```

Exact treatment of missing events must be specified.

---

# 58. Bar Completion

A bar is not considered complete until its interval has ended.

This matters for historical replay.

At:

`10:05:30`

the complete:

`10:05–10:06`

bar does not yet exist.

---

# 59. Lookahead Through Bars

Using a completed bar during an event occurring inside that same bar is prohibited.

This is a common backtesting error.

---

# 60. Decision Timestamp

Every strategy decision has a precise:

`DecisionTimestamp`.

All feature values used by that decision must be valid at exactly that timestamp.

---

# 61. Decision Snapshot

At `t` we construct:

```text
DecisionSnapshot_t =
{
    MarketState_t,
    FeatureState_t,
    OptionUniverse_t,
    ExecutionState_t,
    CapabilityState_t
}
```

This is the complete information set available to the strategy.

---

# 62. Snapshot Immutability

Once:

`DecisionSnapshot_t`

is created:

it is immutable.

This makes historical decisions reproducible.

---

# 63. Label Dataset

After the future becomes available:

```text
DecisionSnapshot_t
        +
FutureEvents_(>t)
        |
        v
Labels_t
```

The resulting label record is stored separately.

---

# 64. Label Separation

A label record may contain:

`future_return`

`future_MFE`

`future_MAE`

`future_horizon`

`future_option_return`

but none of these fields may be available to runtime feature generation.

---

# 65. Label Maturity

Every label has:

`LabelMaturityTimestamp`.

Before that timestamp:

```text
LabelStatus = IMMATURE
```

After it:

```text
LabelStatus = MATURE
```

---

# 66. Training Eligibility

Only:

```text
LabelStatus = MATURE
```

observations may enter supervised historical estimation.

---

# 67. Training Data Version

Every training dataset records:

`RAW_DATA_VERSION`

`FEATURE_VERSION`

`LABEL_VERSION`.

Therefore the model can be reconstructed.

---

# 68. Feature Version

If a feature formula changes:

the feature version changes.

Example:

```text
FEATURE_V1
FEATURE_V2
```

Historical models remain associated with their original feature definition.

---

# 69. Label Version

If a label definition changes:

the label version changes.

We never silently reinterpret an old model's training labels.

---

# 70. Decision Dataset Schema

Conceptually:

```text
DecisionRecord =
{
    decision_id,
    timestamp,
    instrument_state,
    option_state,
    feature_vector,
    capability_state,
    model_version,
    decision
}
```

---

# 71. Outcome Dataset Schema

Conceptually:

```text
OutcomeRecord =
{
    decision_id,
    label_version,
    maturity_timestamp,
    direction_outcome,
    net_return,
    MFE,
    MAE,
    horizon,
    execution_outcome
}
```

---

# 72. Join Key

The decision and outcome datasets join through:

`decision_id`.

This prevents accidental temporal joins based merely on timestamps.

---

# 73. Why Decision ID Matters

Two decisions can occur at nearly identical timestamps.

A deterministic identifier ensures:

```text
Decision
      <-->
Outcome
```

is exact.

---

# 74. Instrument-Time Uniqueness

A decision record should also retain:

`instrument_id`

and:

`timestamp`.

This provides additional auditability.

---

# 75. Data Lineage

Every derived quantity should have a lineage:

```text
Feature
  |
  +-- source fields
  +-- transformations
  +-- lookback
  +-- missing-data rules
  +-- version
```

---

# 76. Feature Lineage Example

Conceptually:

```text
RealizedVolatility
    |
    +-- LastTradedPrice
    +-- timestamp
    +-- 60-second window
    +-- return formula
    +-- variance formula
```

This is much stronger than merely storing:

`volatility = 0.0031`.

---

# 77. Dependency Boundary

The data architecture becomes:

```text
RAW
 |
 +--> NORMALIZATION
       |
       +--> STATE
       |     |
       |     +--> FEATURES
       |
       +--> EXECUTION STATE
       |
       +--> OPTION STATE
       
FUTURE EVENTS
 |
 +--> LABELS
```

---

# 78. No Feature-to-Label Feedback

A feature cannot be recalculated using labels.

For example:

```text
Volatility
```

cannot depend on:

`future trade outcome`.

That would destroy causal validity.

---

# 79. No Label-to-State Feedback

Likewise:

```text
State_t
```

cannot depend on:

`Label_(t-1)`

unless that label genuinely became known in real time and is explicitly part of the strategy's information set.

---

# 80. Historical Learning Exception

A model may legitimately use previously matured outcomes during offline training.

For example:

```text
Model_(2026-01-01)
```

may use outcomes from:

`2025`.

But not outcomes from:

`2026-01-02`.

---

# 81. Data Boundary by Model Version

For model version `V`:

```text
TrainingDataTime < ModelFreezeTime
```

always.

---

# 82. Option Historical Reconstruction

For each historical decision:

we need to reconstruct:

```text
AvailableOptions_t
```

not:

```text
AllOptionsEverObserved
```

---

# 83. Strike Availability

An option candidate is eligible only if it was:

`listed`

and:

`tradable`

at timestamp `t`.

---

# 84. Expiry Awareness

The option state must know:

`time_to_expiry`.

This is calculated from:

`current timestamp`

and:

`actual expiry timestamp`.

---

# 85. Expiry Is Not a Future Feature

At time `t`, the expiry timestamp is already known.

Therefore:

`time_to_expiry`

is causal.

But:

`future price at expiry`

is not.

---

# 86. Execution Snapshot

At decision time:

the strategy requires an execution representation:

```text
ExecutionState_t =
{
    bid,
    ask,
    spread,
    liquidity,
    estimated_slippage,
    execution_capability
}
```

where available.

---

# 87. Entry Price

The research engine must distinguish:

`signal price`

from:

`assumed executable price`.

These are not necessarily identical.

---

# 88. Exit Price

Likewise:

`theoretical exit`

and:

`executable exit`

must remain separate.

---

# 89. Market Orders

For simulated market execution:

the price assumption must incorporate:

`available liquidity`

and:

`slippage`.

It cannot simply equal:

`LTP`.

---

# 90. Limit Orders

If limit execution is eventually modeled:

the dataset must model:

`fill`

`partial fill`

`no fill`.

We cannot assume every limit order fills merely because the market touched the price.

---

# 91. Execution Model Version

Execution assumptions receive:

`EXECUTION_MODEL_VERSION`.

A historical backtest must record which execution model generated its results.

---

# 92. Cost Layer

Costs are represented separately:

`brokerage`

`exchange charges`

`taxes`

`slippage`

`spread`

`other transaction costs`.

Exact applicable charges remain a separate configuration/data dependency.

---

# 93. Cost Versioning

If transaction-cost assumptions change:

the execution model version changes.

Historical results are not silently recalculated.

---

# 94. Data Quality and Strategy Behavior

Poor data must not automatically become:

`NO_TRADE`.

First determine whether the missing information affects:

`decision validity`.

If it does:

the capability state changes.

---

# 95. Capability State

Conceptually:

```text
FULL
PARTIAL
DEGRADED
UNUSABLE
```

The strategy has validated behavior for each state.

---

# 96. Unusable Data

If critical information required for safe execution is unavailable:

```text
Capability = UNUSABLE
```

and:

`NO_TRADE`

is mandatory.

---

# 97. Historical Data Gaps

A gap must record:

`start`

`end`

`affected instruments`

`affected fields`

`quality impact`.

---

# 98. Gap Does Not Equal Flat Market

This is another hard invariant.

No events for thirty seconds does not mean:

`price remained unchanged`.

It means:

`no valid observation was received`.

---

# 99. Resampling

When transforming tick data into minute data:

missing intervals must remain explicitly identifiable.

Do not forward-fill prices unless the specific feature definition permits it.

---

# 100. Forward Filling

If forward filling is ever used:

it must be declared:

`Feature-specific`.

It cannot be applied globally.

---

# 101. Historical Dataset Manifest

Every research dataset should contain:

```text
DatasetID
Source
SourceVersion
DateRange
Instruments
EventTypes
Timezone
TimestampPrecision
MissingDataPolicy
NormalizationVersion
FeatureVersion
LabelVersion
QualitySummary
```

---

# 102. Dataset Integrity Hash

The dataset should have a reproducibility identifier such as:

`DatasetHash`.

If source data changes:

the hash changes.

---

# 103. Research Reproducibility

A model result should therefore be traceable:

```text
RESULT
 |
 +-- MODEL_VERSION
 +-- DATASET_VERSION
 +-- FEATURE_VERSION
 +-- LABEL_VERSION
 +-- EXECUTION_VERSION
 +-- EXPERIMENT_ID
```

---

# 104. No Silent Data Replacement

If TrueData later revises or supplies a corrected historical field:

we create a new dataset version.

We do not silently replace the old dataset.

---

# 105. Historical Data Corrections

A correction creates:

`DATA_VERSION_N+1`.

Experiments using the previous version remain reproducible.

---

# 106. Cross-Source Validation

If another independent source becomes available:

we can compare:

`timestamp`

`price`

`volume`

`option data`.

This is useful for detecting source-specific anomalies.

It is not required for the first version.

---

# 107. Data Dictionary Boundary

The abstract contract is now defined.

The following remain explicit TODOs:

```text
TrueData field name
TrueData endpoint
TrueData entitlement
TrueData precision
TrueData timestamp semantics
TrueData historical depth
TrueData historical option availability
TrueData historical tick availability
TrueData rate limits
TrueData missing-value semantics
TrueData sequence semantics
TrueData option-chain reconstruction capability
```

These are deliberately not guessed.

---

# 108. Data Source Mapping Rule

When TrueData documentation becomes available:

```text
TRUE DATA FIELD
       |
       v
CANONICAL FIELD
       |
       v
SEMANTIC VALIDATION
       |
       v
DATA CONTRACT
```

A field is not admitted merely because its name looks correct.

Its semantics must be verified.

---

# 109. Example Mapping

Eventually we will have something like:

```text
Canonical:
BidPrice

Source:
<actual TrueData field>

Unit:
INR

Precision:
<documented>

Timestamp:
<documented semantics>

Historical:
<YES/NO>

Entitlement:
<subscription requirement>
```

The placeholders remain intentionally unresolved.

---

# 110. Data-to-Feature Boundary

This is the most important architectural boundary in this artifact.

Raw data answers:

`WHAT WAS OBSERVED?`

Derived features answer:

`WHAT CAN WE COMPUTE FROM WHAT WAS OBSERVED?`

Labels answer:

`WHAT HAPPENED AFTERWARD?`

The three questions remain separate.

---

# 111. Complete Pipeline

```text
                 TRUE DATA
                     |
                     v
              RAW EVENT STORE
                     |
             +-------+-------+
             |               |
             v               v
       DATA QUALITY      RAW ARCHIVE
             |
             v
       NORMALIZATION
             |
             v
       CANONICAL EVENTS
             |
             v
      CANONICAL STATE
             |
             v
      FEATURE ENGINE
             |
             v
     DECISION SNAPSHOT
             |
             v
       MODEL / STATE
             |
             v
         DECISION
             
Future Events
     |
     v
LABEL ENGINE
     |
     v
OUTCOME DATASET
```

---

# 112. Critical Architectural Invariant

The production decision path is:

```text
Events_<=t
    ->
State_t
    ->
Features_t
    ->
Decision_t
```

The research outcome path is:

```text
Events_>t
    ->
Labels_t
```

These paths meet only inside controlled historical training/validation.

---

# 113. Current Status

We now have a canonical contract for:

`raw events`

`normalization`

`timestamps`

`instrument identity`

`options`

`market state`

`features`

`decision snapshots`

`labels`

`execution`

`data quality`

`versioning`

`lineage`

`reproducibility`.

---

# 114. What We Should NOT Do Yet

We should not start implementing the TrueData connector.

We first need to map the actual source documentation against this contract.

Otherwise we risk designing around fields that:

`do not exist`

or:

`have different semantics`

or:

`lack sufficient historical availability`.

---

# 115. Next Artifact

The next logical artifact is:

# CANONICAL RESEARCH SCHEMA AND DATA DICTIONARY

This will turn the conceptual contract into a **field-by-field registry**.

For every field we will define:

```text
Field ID
Canonical Name
Domain
Observed / Derived / Label
Mathematical Definition
Unit
Type
Precision
Timestamp Semantics
Update Frequency
Lookback
Dependencies
Causal Availability
Historical Requirement
TrueData Mapping
Missing Semantics
Quality Rules
Version
```

The TrueData-specific columns will remain:

`TODO`

until you provide the documentation.

After that, we will have a precise map from:

```text
TRUE DATA
   ->
CANONICAL DATA
   ->
STATE
   ->
FEATURES
   ->
MODEL
   ->
DECISION
```

At that point, the architecture will no longer have an undefined data boundary; only the source-specific mapping will remain to be filled.