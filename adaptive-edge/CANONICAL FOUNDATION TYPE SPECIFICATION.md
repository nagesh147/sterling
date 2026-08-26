# CANONICAL FOUNDATION TYPE SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the foundational semantic types used by every higher-level component.

The types covered are:

```text
Identifier
Timestamp
Price
Quantity
Money
Probability
Duration
Version
EventEnvelope
```

These are not convenience wrappers.

They establish the numerical, temporal, identity, and serialization rules of the entire system.

---

# 2. Foundation Principle

A primitive domain value must carry its semantic meaning.

The system must avoid treating all values as:

```text
number
string
Date
boolean
```

when their meanings differ.

For example:

```text
Price != Quantity
OrderID != InstrumentID
Money != Probability
EventTime != Duration
```

---

# 3. Identifier

An `Identifier` uniquely identifies a domain object.

Conceptually:

```text
Identifier<T>
```

where `T` represents the semantic identity.

Examples:

```text
InstrumentID
EventID
OrderID
FillID
PositionID
TradeID
DecisionID
OpportunityID
ExperimentID
RunID
```

---

# 4. Identifier Invariants

An identifier must:

```text
be non-empty
have a valid encoding
be immutable
support equality
support deterministic serialization.
```

Whitespace-only identifiers are invalid.

---

# 5. Identifier Equality

Identifiers are equal only when both:

```text semantic type
+
identifier value
```

are equal.

Therefore:

```text InstrumentID("ABC")
```

must not equal:

```text OrderID("ABC")
```

even if their serialized strings are identical.

---

# 6. Identifier Generation

Identifiers may be generated using:

```text UUID
ULID
deterministic test identifiers
provider identifiers
```

depending on context.

The generation mechanism must not alter semantic identity.

---

# 7. Provider IDs

External identifiers may be retained as separate fields.

Example:

```text internalOrderID
externalOrderID
```

They must not be silently conflated.

---

# 8. Timestamp

A `Timestamp` represents an absolute point in time.

It is not:

```text duration
elapsed time
market session time
bar index.
```

---

# 9. Timestamp Requirements

A canonical timestamp must contain enough information to identify:

```text date
time
timezone/offset
precision.
```

Internally, UTC normalization is recommended.

---

# 10. Timestamp Precision

The canonical system must define one minimum precision.

The implementation must not silently discard provider precision.

For example:

```text provider precision = milliseconds
canonical precision = seconds
```

would be a lossy transformation and requires explicit approval.

---

# 11. Timestamp Ordering

Timestamps support:

```text equality
less-than
greater-than
ordering.
```

Ordering must be deterministic.

---

# 12. Event Time Versus Receipt Time

These remain separate:

```text eventTime
receivedTime
```

Example:

```text Event occurred: 09:30:01.120
System received:   09:30:01.175
```

The difference is meaningful.

---

# 13. Availability Time

For causal validation, a value may additionally carry:

```text availabilityTime
```

This answers:

```text When was this information actually available to the decision engine?
```

It is distinct from event time.

---

# 14. Timestamp Causality

For a decision at:

```text DecisionTime = t
```

an input is causally valid only if:

```text AvailabilityTime <= t
```

subject to the system's explicit ordering convention.

---

# 15. Price

`Price` represents the monetary value of one unit of an instrument.

It is distinct from:

```text Money
Quantity
```

---

# 16. Price Invariants

A valid price must:

```text be finite
not be NaN
not be infinite
satisfy the instrument's permitted price domain.
```

Whether zero is valid depends on the instrument and market representation.

---

# 17. Price Precision

Price precision is determined by:

```text instrument tick size
```

where applicable.

A price that cannot be represented on the valid price grid must be rejected or explicitly normalized according to the instrument contract.

---

# 18. Price Arithmetic

Price arithmetic must not rely on uncontrolled binary floating-point behavior for financial equality.

The implementation must use an explicitly selected representation.

---

# 19. Quantity

`Quantity` represents an amount of an instrument.

Examples:

```text shares
contracts
lots
units.
```

---

# 20. Quantity Invariants

A quantity must:

```text be finite
not be NaN
not be infinite.
```

Whether fractional quantity is permitted is determined by the instrument.

---

# 21. Lot-Constrained Quantity

For a contract with:

```text lotSize = L
```

an executable whole-lot quantity must satisfy:

```text quantity % L = 0
```

where `%` represents the canonical lot-grid operation, not necessarily native floating-point remainder.

---

# 22. Quantity Sign

The domain must distinguish:

```text absolute quantity
signed quantity
```

rather than relying on implicit conventions.

For example:

```text Quantity = 10
Side = BUY
```

is preferable to:

```text Quantity = +10
```

when the domain object already contains an explicit side.

---

# 23. Money

`Money` represents a monetary amount.

It must contain:

```text amount
currency.
```

Conceptually:

```text Money {
    amount
    currency
}
```

---

# 24. Money Currency

Currency is part of semantic identity.

Therefore:

```text INR 100
```

is not equal to:

```text USD 100
```

---

# 25. Money Arithmetic

Addition and subtraction are valid only for compatible currencies unless an explicit conversion operation is supplied.

---

# 26. Currency Conversion

Currency conversion is not implicit.

The system must not perform:

```text USD + INR
```

or silently convert one currency into another.

A conversion requires:

```text exchange rate
rate timestamp
rate source
conversion version.
```

---

# 27. Money Precision

The implementation must use an exact or appropriately controlled decimal representation.

Binary floating-point must not determine financial equality.

---

# 28. Probability

`Probability` represents a value in the closed interval:

```text 0 <= p <= 1
```

---

# 29. Probability Invariants

The following are invalid:

```text NaN
Infinity
-0.1
1.1
```

Valid examples:

```text 0
0.25
0.5
0.95
1
```

---

# 30. Probability Equality

Probability equality must follow the canonical numerical representation.

The system must not arbitrarily apply an epsilon unless the specification explicitly defines one.

---

# 31. Probability Versus Confidence

These are not automatically equivalent.

For example:

```text DirectionProbability
```

does not necessarily mean:

```text ModelConfidence.
```

They require separate types if both exist.

---

# 32. Duration

`Duration` represents elapsed time.

Examples:

```text holding duration
lookback duration
latency
session duration.
```

It is not an absolute timestamp.

---

# 33. Duration Invariants

Duration must be:

```text finite
explicitly represented
non-negative
```

unless a signed duration is specifically required for a domain operation.

---

# 34. Duration Precision

Duration precision must be sufficient for:

```text market-event ordering
execution latency
simulation
causal validation.
```

The precision must not be silently reduced.

---

# 35. Version

A `Version` identifies the exact definition of an artifact.

Version types must remain semantically distinct.

Examples:

```text SpecificationVersion
SchemaVersion
ModelVersion
ParameterVersion
RiskPolicyVersion
ExecutionVersion
AccountingVersion
FeatureVersion
```

---

# 36. Version Structure

A version may use semantic versioning or another explicit scheme.

For example:

```text major.minor.patch
```

The chosen scheme must be defined globally.

---

# 37. Version Compatibility

Version equality does not imply compatibility.

For example:

```text FeatureVersion 2.0
```

may be incompatible with:

```text ModelVersion 1.0.
```

Compatibility must be checked explicitly.

---

# 38. Version Immutability

Once an artifact version is published:

```text VersionID
```

must never be reused for different content.

---

# 39. Content Integrity

Versioned artifacts should additionally carry:

```text content hash
```

where practical.

This prevents:

```text same version
+
different bytes
```

from silently becoming valid.

---

# 40. EventEnvelope

Every canonical event uses:

```text EventEnvelope {
    eventId
    eventType
    eventTime
    receivedTime
    source
    schemaVersion
    correlationId
    causationId
    sequence
    payload
}
```

---

# 41. EventID

`eventId` uniquely identifies the event.

Duplicate processing of the same `eventId` must be detectable.

---

# 42. EventType

`eventType` identifies the semantic payload.

Examples:

```text QUOTE
TRADE
DEPTH
INSTRUMENT
SESSION
ORDER
FILL
```

An event's type determines how its payload is interpreted.

---

# 43. Source

`source` identifies the system that produced the event.

Examples:

```text truedata
historical-replay
simulation
broker
internal
```

Provider source names remain infrastructure metadata.

---

# 44. CorrelationID

`correlationId` groups events belonging to one logical workflow.

Example:

```text Opportunity
    ↓
Decision
    ↓
RiskAuthorization
    ↓
Order
    ↓
Fill
```

All may share the same correlation ID.

---

# 45. CausationID

`causationId` identifies the immediate predecessor that caused the current event.

For example:

```text OrderAccepted
causationId = OrderSubmittedEventID
```

This differs from correlation.

---

# 46. Sequence

`sequence` provides ordering information within the relevant event stream.

It is not globally meaningful unless the source contract guarantees global ordering.

---

# 47. Event Immutability

Once an event is accepted:

```text eventId
eventType
eventTime
payload
sequence
```

must not be modified.

Corrections are represented by new events.

---

# 48. Event Serialization

Serialization must preserve:

```text semantic identity
numeric precision
timestamp precision
version
null/unknown semantics
event ordering metadata.
```

---

# 49. Serialization Round Trip

For supported canonical objects:

```text serialize(x)
    ↓
deserialize(...)
    ↓
x'
```

must satisfy:

```text x' == x
```

according to the object's semantic equality rules.

---

# 50. Unknown Fields

When decoding external data:

```text unknown provider field
```

must not automatically become a canonical domain field.

Provider data is promoted into the domain only through an explicit schema decision.

---

# 51. Missing Values

The system must distinguish where necessary:

```text absent
unknown
unavailable
invalid
not-applicable.
```

These must not automatically become:

```text 0.
```

---

# 52. Zero Semantics

Zero must never be used as a generic substitute for missing data.

For example:

```text missing bid price
```

must not become:

```text bidPrice = 0
```

unless zero is explicitly the correct market value.

---

# 53. NaN Policy

`NaN` must not enter canonical financial or decision-domain types.

Invalid numerical results must become explicit errors or invalid-state representations.

---

# 54. Infinity Policy

Positive or negative infinity must not enter canonical financial or decision-domain types.

---

# 55. Negative Zero

The implementation must normalize or explicitly define the behavior of:

```text -0
```

so that semantically equal values do not produce inconsistent serialization.

---

# 56. Equality Categories

The system distinguishes:

```text identity equality
value equality
structural equality
reference equality.
```

Domain logic should use semantic equality, not object-reference equality.

---

# 57. Ordering Categories

Not every domain object is naturally ordered.

Ordering must be defined explicitly for:

```text Timestamp
Sequence
Price
Quantity
Duration
Version
```

where appropriate.

---

# 58. Immutability

Foundation values are immutable.

For example:

```text Price(100)
```

cannot later become:

```text Price(105).
```

A new value is created.

---

# 59. Thread Safety

Immutable foundation values are inherently safe to share across execution contexts.

Mutable global primitives are prohibited.

---

# 60. Error Model

Invalid foundation values must fail at construction or validation boundaries.

Examples:

```text InvalidProbability
InvalidPrice
InvalidQuantity
InvalidMoney
InvalidTimestamp
InvalidVersion
InvalidEvent
```

---

# 61. Error Requirements

Errors must identify:

```text type
field
invalid value or reason
validation rule
```

Sensitive credentials must never be included.

---

# 62. Financial Precision Rule

The system must explicitly choose its numerical representation before implementing:

```text Price
Money
Quantity
PnL
Fees
ExecutionCost.
```

The choice cannot be left to whichever language primitive happens to be convenient.

---

# 63. Recommended Numerical Model

For monetary and price values:

```text decimal/fixed-point representation
```

is preferred.

For probabilities and statistical calculations:

```text controlled floating-point representation
```

may be appropriate, provided numerical tolerances are explicitly specified.

---

# 64. Conversion Rule

Conversions between representations must occur explicitly.

For example:

```text DecimalPrice
    ↓
ProviderPrice
```

requires a documented conversion rule.

---

# 65. Domain Primitive Conversion

A primitive should not expose arbitrary conversion such as:

```text Price → number
```

through unrestricted implicit coercion.

The caller should explicitly request the representation required by the boundary.

---

# 66. Serialization Boundary

The canonical architecture is:

```text External Data
    ↓
Provider Schema
    ↓
Mapper
    ↓
Domain Primitive
```

and:

```text Domain Primitive
    ↓
Serializer
    ↓
External/Persistence Schema
```

---

# 67. Foundation Test Matrix

Every foundation type requires tests for:

```text valid construction
invalid construction
boundary values
equality
ordering
serialization
deserialization
immutability
version compatibility
error behavior.
```

---

# 68. Property Tests

The following properties should be tested:

```text serialize/deserialize round-trip
equality symmetry
equality transitivity
ordering consistency
immutability
deterministic serialization.
```

---

# 69. Critical Financial Property

For valid monetary values:

```text a + b - b = a
```

within the exact arithmetic model defined by the implementation.

The test must not simply hide rounding defects behind a broad tolerance.

---

# 70. Critical Probability Property

For every valid probability:

```text 0 <= p <= 1
```

must always hold.

---

# 71. Critical Quantity Property

For lot-constrained instruments:

```text executableQuantity % lotSize = 0
```

must always hold.

---

# 72. Critical Timestamp Property

For causally ordered events:

```text availabilityTime <= decisionTime
```

must hold before an input can enter the decision path.

---

# 73. Critical Event Property

Processing the same immutable event twice must not create two economic effects.

This establishes the foundation for idempotent event processing.

---

# 74. Foundation Dependency Rule

Foundation types may depend only on:

```text language primitives
standard-library functionality
approved low-level numerical/time libraries.
```

They must not depend on:

```text strategy
risk
accounting
broker
database
research
simulation.
```

---

# 75. Foundation Layer Diagram

```text
              Foundation Types
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
      Events      Instruments    State
        │            │            │
        └────────────┼────────────┘
                     ↓
              Higher Domains
```

Everything above depends on these primitives.

Nothing below them should depend on higher domains.

---

# 76. Implementation Freeze

The following semantics are now frozen:

```text Identifier semantics
Timestamp semantics
Causal availability
Price semantics
Quantity semantics
Money semantics
Probability range
Duration semantics
Version identity
Event envelope
Serialization principles
Missing-value semantics
Numerical precision policy
```

Any change requires a specification revision.

---

# 77. Immediate Coding Target

The first actual source files should implement only:

```text domain/common/
domain/events/
domain/instruments/
```

and their tests.

Nothing involving:

```text prediction
risk
strategy
broker
P&L
```

should be implemented yet.

---

# 78. First Foundation Milestone

The milestone passes when the repository can:

```text construct canonical identifiers
construct timestamps
construct valid financial primitives
construct canonical events
serialize/deserialize them
reject invalid values
detect duplicate event identities
```

deterministically.

---

# 79. Next Artifact

Once these primitives are specified, the next artifact should define the first executable subsystem:

# CANONICAL EVENT MODEL AND DETERMINISTIC STATE MACHINE SPECIFICATION

That document will turn the event and state contracts into an executable transition system.

The key function will become:

```text
State_t + Event_t
        ↓
State_(t+1)
```

with explicit transition tables, idempotency rules, ordering rules, opening-range construction, session transitions, and adversarial failure behavior.

That is the first point where the system will begin behaving like an actual engine rather than a collection of types.