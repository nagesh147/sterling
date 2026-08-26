# CANONICAL DATA-TO-MATHEMATICS CONTRACT

Version 1.0

## 1. Purpose

This specification defines the boundary between external market data and the mathematical state machine.

The contract answers:

```text
What enters the system?
What does one incoming event mean?
Which timestamp is authoritative?
Which fields are observations?
Which quantities are derived?
How are derived quantities updated?
Which data may influence which decisions?
What happens when data is missing, stale, duplicated, delayed, or contradictory?
```

The exact TrueData field names remain intentionally unresolved until the authoritative API documentation is supplied.

No mathematical rule depends on a vendor-specific field name.

---

# 2. Canonical Data Pipeline

The complete transformation is:

```text
TRUE DATA
   |
   v
RAW EVENT
   |
   v
EVENT VALIDATION
   |
   v
CANONICAL EVENT
   |
   v
OBSERVABLE STATE
   |
   v
DERIVED STATE
   |
   v
STATISTICAL STATE
   |
   v
ECONOMIC STATE
   |
   v
RISK STATE
   |
   v
DECISION STATE
```

The transformation is causal.

No downstream layer may introduce information that was unavailable upstream.

---

# 3. Raw Data Layer

The raw layer represents the data exactly as received.

Conceptually:

```text
RawEvent
{
    source
    source_event_id
    source_timestamp
    receive_timestamp
    instrument_identifier
    raw_fields
}
```

The exact field names remain:

```text TODO — TrueData documentation.
```

The raw event must be preserved sufficiently to reproduce the canonical transformation.

---

# 4. Source Time Versus Receive Time

Two times may exist:

```text SourceEventTime
ReceiveTime
```

They are not interchangeable.

`SourceEventTime` represents when the market event occurred according to the authoritative source.

`ReceiveTime` represents when our system received it.

For historical market-state calculations:

```text SourceEventTime
```

is normally the causal market timestamp.

For latency/execution analysis:

```text ReceiveTime
```

may also be relevant.

The exact semantics must be confirmed from the data documentation.

---

# 5. Event Ordering

The system requires a deterministic ordering key:

```text EventOrderingKey
```

Conceptually:

```text SourceEventTime
+
SourceSequence
```

if the source supplies sequence information.

If no sequence exists, the data contract must define the fallback ordering mechanism.

Current status:

```text TODO — TrueData event-ordering semantics.
```

---

# 6. One Incoming Event

One incoming event does not necessarily mean:

"one trade."

It means:

```text one externally observed information update.
```

For example, one event may change:

```text price
volume
bid
ask
market depth
option quote
```

or another observable.

The state machine consumes the event once.

---

# 7. Event Identity

Every event should have an identity:

```text EventID
```

If TrueData provides an authoritative identifier:

```text EventID = TrueDataEventID
```

Otherwise the canonical identity must be constructed from the available source fields.

Current status:

```text TODO — exact TrueData event identity.
```

---

# 8. Event Deduplication

If:

```text EventID_t = EventID_previous
```

the event must not produce a second state transition.

Formally:

```text Process(EventID) = idempotent
```

This protects against:

```text duplicate tick
duplicate quote
duplicate execution message
duplicate network delivery.
```

---

# 9. Instrument Identity

Every market event must resolve to a canonical:

```text InstrumentID
```

The system must distinguish at minimum:

```text UnderlyingInstrument
OptionInstrument
```

An option instrument must not be treated as the underlying.

---

# 10. Underlying State

The underlying instrument provides the primary directional market state.

Conceptually:

```text UnderlyingState_t
```

may contain:

```text last price
timestamp
volume
OHLC state
returns
volatility
opening-range state
intraday position
momentum
liquidity
```

Only fields actually available from TrueData will be activated.

---

# 11. Option State

Option state is separate.

Conceptually:

```text OptionState_t
```

may contain:

```text option price
bid
ask
volume
open interest
strike
expiry
option type
implied volatility
greeks
```

Availability of each field is currently:

```text TODO — TrueData entitlement/documentation.
```

---

# 12. Underlying Versus Option Information

The directional prediction should primarily derive from the underlying state.

Option data is primarily used for:

```text instrument selection
execution feasibility
economic valuation
position sizing
```

This prevents the system from accidentally allowing option-specific noise to redefine the underlying directional model unless explicitly permitted.

---

# 13. Canonical Observation

A raw field becomes a canonical observation only after validation.

For example:

```text RawPrice
    |
    v
PriceObservation
```

The observation must contain:

```text value
timestamp
instrument
source
quality status
```

---

# 14. Observation Quality

Every observation conceptually carries:

```text VALID
STALE
MISSING
INVALID
CONFLICTED
OUT_OF_ORDER
```

A value without a quality state is insufficient for production use.

---

# 15. Missing Data

Missing is not zero.

If:

```text volume = missing
```

the system cannot transform it into:

```text volume = 0.
```

The correct representation is:

```text VolumeStatus = MISSING
```

unless the source contract explicitly defines zero as the correct semantic value.

---

# 16. Invalid Data

Examples:

```text impossible price
negative price where impossible
invalid timestamp
invalid instrument
invalid option metadata
```

must be rejected from mathematical state.

The raw event may remain recorded for diagnostics.

---

# 17. Stale Data

A field can be valid historically but unusable for the current decision.

Therefore:

```text Valid != Fresh
```

A freshness contract must eventually define:

```text MaximumAge(variable)
```

The numerical maximum age remains a configuration/validation quantity.

---

# 18. Derived Variables

Derived variables are deterministic transformations of canonical observations.

Examples:

```text Return_t
ATR_t
Volatility_t
OpeningRange_t
DistanceFromOR_t
Momentum_t
Spread_t
Profit_t
Drawdown_t
```

A derived variable cannot use future observations.

---

# 19. Dependency Rule

Every derived variable has an explicit dependency set:

```text Variable
    |
    +-- Input A
    +-- Input B
    +-- Input C
```

If one dependency becomes invalid, the variable's validity must be recomputed.

It cannot silently retain an apparently current value.

---

# 20. Recursive State

Some quantities require historical state.

For example:

```text ATR_t
```

depends on previous observations.

Therefore the canonical mathematical definition is not simply:

```text ATR = f(current tick)
```

but:

```text ATR_t
=
f(
previous valid state,
current event
)
```

This is precisely why the system is a temporal state machine.

---

# 21. State Update

For every valid event:

```text S_(t+1)
=
F(S_t, E_t)
```

where:

```text S_t = canonical state before event
E_t = canonical event
S_(t+1) = canonical state after event
```

The function `F` must be deterministic under identical inputs.

---

# 22. No Future Dependency

For every variable `X_t`:

```text Dependencies(X_t) ⊆ InformationAvailableAt(t)
```

This is the core causal constraint.

---

# 23. Feature Timestamp

Every derived feature must have an effective timestamp:

```text FeatureTime(X)
```

and:

```text FeatureTime(X) <= DecisionTime
```

must hold.

---

# 24. Aggregated Timeframes

A major source of hidden leakage is incomplete bars.

Suppose the strategy uses:

```text one-minute state.
```

At:

```text 10:00:30
```

the final one-minute bar ending at:

```text 10:01:00
```

does not yet exist.

Therefore the strategy cannot use the completed `10:00-10:01` bar until its completion.

This rule applies to every aggregation timeframe.

---

# 25. Tick Data Versus Bar Data

Tick data can update:

```text current state
```

continuously.

Bar-derived features become valid only according to their bar-completion semantics.

Therefore:

```text tick availability
!=
completed-bar availability.
```

This must be explicitly encoded.

---

# 26. Opening Range

The opening range is another temporal state.

Before completion:

```text OpeningRange = INCOMPLETE
```

After completion:

```text OpeningRange = FINAL
```

The strategy cannot use the final range before its defining interval has ended.

---

# 27. Volatility State

Volatility estimates such as ATR are derived state.

They have:

```text calculation window
update rule
minimum history requirement
freshness rule
```

The exact ATR period remains a learned/calibrated quantity if we choose not to hard-code it.

---

# 28. Price Return

A return may be defined as:

```text R_t = P_t / P_(t-1) - 1
```

or through another explicitly chosen transformation.

The mathematical definition must remain fixed once selected for a model version.

It cannot change silently between historical periods.

---

# 29. Profit State

For an active trade:

```text CurrentPnL_t
```

is calculated from:

```text actual entry fills
current validated mark
current quantity
applicable cost/accounting convention.
```

Realized P&L remains separate.

---

# 30. Peak State

```text PeakPnL_t
=
max(
PeakPnL_(t-1),
CurrentPnL_t
)
```

subject to the trade lifecycle.

When a new trade begins:

```text PeakPnL = initial trade-state value.
```

Previous trade peak cannot leak into the new trade.

---

# 31. Protection State

The protection boundary is stateful.

For a long position:

```text Protection_t
=
max(
Protection_(t-1),
CandidateProtection_t
)
```

The candidate can be derived from:

```text price
ATR
profit state
mode
continuation
learned risk parameters
```

but cannot weaken the existing protection.

---

# 32. Probability State

Probability is not a raw observation.

It is a model output:

```text P_t
=
Model(
State_t,
ModelVersion_t
)
```

The model version must be known.

The output must satisfy:

```text 0 <= P_t <= 1
```

---

# 33. Probability Freshness

A probability calculated from an earlier state must not automatically be treated as current forever.

The probability has:

```text generation time
input-state version
model version
```

If material state changes invalidate the probability, it must be recomputed.

---

# 34. Economic State

The economic layer combines:

```text predicted movement
probability
option economics
cost
slippage
liquidity
risk
```

and produces quantities such as:

```text ExpectedNetValue
ExpectedLoss
ExpectedGain
```

These are decision quantities, not raw market observations.

---

# 35. Option Selection

The option-selection layer receives:

```text underlying directional state
option universe
option liquidity state
option pricing state
economic estimates
risk constraints
```

and produces:

```text CE candidate
PE candidate
NO_VALID_OPTION
```

It must not choose an option merely because the underlying direction is favorable.

---

# 36. Execution Cost

Execution cost must be modeled separately from prediction.

Conceptually:

```text NetExpectedValue
=
GrossExpectedValue
-
TransactionCost
-
SpreadCost
-
ExpectedSlippage
```

The exact cost components depend on available data.

---

# 37. Slippage

Historical backtesting must not assume:

```text execution_price = observed_last_price
```

unless the execution contract explicitly justifies that assumption.

Actual historical execution modeling will depend on:

```text bid/ask availability
market depth
timestamp resolution
order semantics
```

Current status:

```text TODO — TrueData execution-data availability.
```

---

# 38. Liquidity

Liquidity is not merely:

```text volume.
```

Depending on available data, the contract may include:

```text spread
quote depth
market depth
trade frequency
volume
order-book imbalance
```

Only available, validated variables can enter the production model.

---

# 39. Decision Eligibility

A variable can exist but still be prohibited from decision use.

Therefore each registry entry needs:

```text DecisionAllowed = TRUE/FALSE
```

This prevents accidental use of diagnostic variables.

---

# 40. Variable Usage Classes

Every variable receives one of:

```text OBSERVATION_ONLY
STATE_UPDATE
PREDICTION_INPUT
ECONOMIC_INPUT
RISK_INPUT
EXECUTION_INPUT
AUDIT_ONLY
LEARNING_ONLY
```

This is an important control.

---

# 41. No Hidden Variables

If a variable affects a trading decision:

```text it must exist in the canonical registry.
```

No implementation component may introduce an undocumented feature.

---

# 42. No Duplicate Semantics

Two variables cannot represent the same mathematical quantity under different names.

For example:

```text CurrentProfit
CurrentPnL
```

cannot both exist if they have identical semantics.

We retain:

```text CurrentPnL
RealizedPnL
PeakPnL
ProfitGiveback
```

because these are mathematically distinct.

---

# 43. Historical Availability

Every input must specify:

```text FirstAvailableTimestamp
```

and, where relevant:

```text HistoricalCoverage
```

This matters because a six-year backtest cannot legitimately use a field that only existed for two years.

---

# 44. Entitlement

Each data field must specify:

```text EntitlementRequired
```

and:

```text SubscriptionCoverage
```

A backtest must never silently assume access to data outside the actual subscription.

---

# 45. Precision

Each field requires its authoritative precision:

```text price precision
timestamp precision
quantity precision
volume precision
```

The mathematical model must use the source's actual precision.

We must not invent sub-tick precision.

---

# 46. Update Frequency

Each input must specify whether it is:

```text event-driven
tick-driven
quote-driven
bar-driven
snapshot-driven
session-driven
daily
```

A variable's update frequency determines how often its state can legitimately change.

---

# 47. Example Canonical Registry Entry

Conceptually:

```text
Variable:
UNDERLYING_LAST_PRICE

Type:
OBSERVED

Source:
TODO — TrueData field

Timestamp:
TODO — source timestamp semantics

Precision:
TODO

Update:
TODO

Historical Availability:
TODO

Entitlement:
TODO

Used By:
returns
ATR
momentum
probability
opening-range state
```

The mathematics does not wait for the field name.

Only the source mapping waits.

---

# 48. Dependency Contract

Every variable must expose:

```text Inputs
Transformation
Output
Update Trigger
Validity Conditions
Consumers
```

This creates the complete dependency chain.

---

# 49. Example

```text UNDERLYING_PRICE
       |
       +--> RETURN
       |
       +--> ATR
       |
       +--> MOMENTUM
       |
       +--> OPENING_RANGE_DISTANCE
       |
       +--> PROBABILITY
       |
       +--> ECONOMIC_VALUE
       |
       +--> TRADE_DECISION
```

This makes accidental circular dependencies visible.

---

# 50. Circular Dependency Rule

A variable cannot depend, directly or indirectly, upon itself within the same event transformation unless it is explicitly defined as a recursive state update.

Valid:

```text PeakPnL_t
=
max(PeakPnL_(t-1), CurrentPnL_t)
```

Invalid:

```text Probability_t
=
f(Probability_t)
```

without an explicit recursive mathematical definition.

---

# 51. Decision Dependency Boundary

The final decision may depend on:

```text current observable state
current derived state
current statistical state
current economic state
current risk state
current execution state
active parameter/model version
```

It may not depend on:

```text future labels
future prices
future fills
future volatility
future model performance
future parameter values.
```

---

# 52. Learning Dependency Boundary

Learning may depend on:

```text matured historical labels
historical state snapshots
historical execution outcomes
historical parameter versions
historical model versions
```

but only according to their maturity timestamps.

---

# 53. Historical Snapshot Requirement

For every historical decision opportunity, the system must be able to reconstruct:

```text State_t
Parameters_t
ModelVersion_t
Decision_t
```

using only information available at `t`.

This is a fundamental backtest requirement.

---

# 54. TrueData Does Not Define Our Mathematics

The data provider supplies observations.

It does not define:

```text probability
EV
risk
mode
trade decision
```

Those remain our mathematical layer.

This prevents vendor-specific semantics from silently becoming strategy logic.

---

# 55. Vendor Replacement Property

If another data provider supplied mathematically equivalent observations:

```text equivalent canonical event
```

the strategy should produce equivalent state transitions, subject to execution differences.

This makes the mathematical specification provider-independent.

---

# 56. Data Quality State

The canonical state therefore includes:

```text DataQualityState
```

which summarizes whether the current information is sufficiently trustworthy for normal operation.

Possible values:

```text HEALTHY
DEGRADED
INVALID
RECOVERING
```

---

# 57. Data Quality Does Not Equal Market Regime

These must remain separate.

```text HIGH_VOLATILITY
```

is a market state.

```text DATA_DEGRADED
```

is an information-quality state.

High volatility is not data failure.

---

# 58. Execution Quality Does Not Equal Market Quality

Similarly:

```text wide spread
```

may represent poor execution conditions.

It does not necessarily mean:

```text market data invalid.
```

The two layers remain separate.

---

# 59. Event Transformation Contract

For every event:

```text RawEvent
    |
    v
Validate
    |
    v
CanonicalEvent
    |
    v
UpdateObservableState
    |
    v
UpdateDerivedState
    |
    v
UpdateStatisticalState
    |
    v
UpdateEconomicState
    |
    v
UpdateRiskState
    |
    v
EvaluateDecision
```

Every stage has a defined input and output.

---

# 60. Atomicity

The event transformation must be conceptually atomic.

No subsequent event may observe a partially updated state.

Thus:

```text Event_t
```

produces exactly one:

```text State_(t+1)
```

before:

```text Event_(t+1)
```

is evaluated.

---

# 61. Data-to-Decision Traceability

For every trade decision, we must eventually be able to trace:

```text Decision
  ↓
Decision State
  ↓
Probability
  ↓
Features
  ↓
Canonical Observations
  ↓
Raw Data Events
```

This is the audit chain.

---

# 62. Trade-to-Data Traceability

For every executed trade:

```text TradeID
  ↓
Entry Decision
  ↓
Decision State
  ↓
Model Version
  ↓
Parameter Version
  ↓
Input Features
  ↓
Raw Market Events
  ↓
Execution Events
```

This enables post-trade reconstruction.

---

# 63. Historical Replay Requirement

A historical replay must be able to reproduce the same:

```text state
decision
order intent
risk state
mode
parameter version
model version
```

when supplied with the same canonical event sequence.

---

# 64. Data Contract Failure

If a required source field is unavailable:

```text the dependent mathematical variable becomes unavailable.
```

The system does not substitute an arbitrary value.

The dependency graph determines the consequence.

For example:

```text missing bid/ask
    ↓
execution-cost estimate unavailable
    ↓
option economic validation unavailable
    ↓
NO_TRADE
```

if that dependency is mandatory.

---

# 65. Conservative Failure Principle

When a required input is unavailable, the default behavior for a new trade is:

```text NO_TRADE
```

rather than:

```text assume favorable value.
```

Existing exposure follows the separate protection/recovery policy.

---

# 66. Data Recovery

When data becomes valid again:

```text DATA_DEGRADED
    ↓
reconstruct current canonical state
    ↓
validate freshness
    ↓
recompute affected derived variables
    ↓
revalidate risk
    ↓
resume normal operation
```

We do not blindly continue from stale calculations.

---

# 67. Exact TrueData Mapping

The following fields remain intentionally unresolved:

```text source event identifier
source timestamp
receive timestamp semantics
underlying last price
underlying volume
bid/ask
market depth
option quote fields
option metadata
open interest
historical tick format
historical option availability
rate limits
subscription entitlement
historical retention
timestamp precision
event sequencing
correction semantics
```

These become explicit TODOs rather than assumptions.

---

# 68. Data Contract Completion Rule

When the TrueData documentation is supplied, each TODO must be replaced by:

```text Exact field
Exact API/source
Exact semantics
Exact units
Exact precision
Exact update behavior
Exact historical coverage
Exact entitlement
Exact failure behavior
```

If TrueData does not provide a required quantity, we do not invent it.

Instead we return to the dependency graph and determine whether:

```text another source
derived approximation
or NO_TRADE
```

is appropriate.

---

# 69. Current Status

The mathematical-to-data boundary is now architecturally defined.

Complete:

```text Event contract
Observation contract
State update contract
Derived-variable contract
Data-quality contract
Timestamp contract
Dependency contract
Traceability contract
Failure contract
Historical reconstruction contract
```

Pending:

```text exact TrueData field mapping
exact TrueData historical coverage
exact entitlement
exact event-ordering semantics
exact execution-data availability
```

---

# 70. Next Artifact

The next logical artifact is now the:

# CANONICAL TRADE LIFECYCLE SPECIFICATION

This will take one individual trade and describe its complete existence from:

```text NO_POSITION
    ↓
OPPORTUNITY DETECTED
    ↓
ENTRY ELIGIBILITY
    ↓
CE/PE SELECTION
    ↓
ORDER INTENT
    ↓
ORDER SUBMISSION
    ↓
PARTIAL/FULL FILL
    ↓
INITIAL PROTECTION
    ↓
MICRO/SCALP/INTRADAY MANAGEMENT
    ↓
PROFIT ACCUMULATION
    ↓
PROFIT LOCK
    ↓
MODE TRANSITIONS
    ↓
STOP / EMERGENCY / NORMAL EXIT
    ↓
PARTIAL/FULL EXIT
    ↓
RECONCILIATION
    ↓
FINAL REALIZED P&L
    ↓
HISTORICAL LABEL CREATION
    ↓
LEARNING ELIGIBILITY
```

That artifact will finally connect the entire architecture around the **single atomic unit of the system: one actual trade**, while preserving the tick-by-tick state transitions we originally wanted to make precise.

After that, we will be very close to having the complete pre-implementation specification rather than merely a collection of mathematical components.