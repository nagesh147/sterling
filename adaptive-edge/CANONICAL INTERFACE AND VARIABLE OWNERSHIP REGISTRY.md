# CANONICAL INTERFACE AND VARIABLE OWNERSHIP REGISTRY

Version 1.0

## 1. Purpose

This registry is the authoritative mapping between the mathematical specification and the eventual implementation.

It answers one question for every important variable:

```text
Who owns this value,
where does it come from,
when does it become available,
who may consume it,
and how is it validated?
```

No implementation variable may exist independently of this registry if it represents a canonical strategy concept.

---

# 2. Registry Principle

Every canonical variable has exactly one:

```text
VariableID
CanonicalName
Definition
Owner
Producer
```

It may have many consumers.

Conceptually:

```text
                    ┌── Consumer A
                    ├── Consumer B
Producer ─ Variable ─┤
                    └── Consumer C
```

Never:

```text
Producer A ─┐
            ├── "same variable"
Producer B ─┘
```

unless the implementations are explicitly declared equivalent.

---

# 3. Variable Identity

Every variable receives an immutable identifier.

Example:

```text
VAR-MKT-001
VAR-STATE-001
VAR-PRED-001
VAR-RISK-001
VAR-POS-001
VAR-PNL-001
```

The identifier remains stable even if implementation names change.

---

# 4. Canonical Variable Record

Each registry entry contains:

```text
VariableID
CanonicalName
Definition
Domain
Type
Unit
OwnerModule
Producer
Consumers
SourceData
CausalAvailability
UpdateTrigger
PersistencePolicy
Version
ValidationTests
Status
```

---

# 5. Status Values

A variable can be:

```text
DEFINED
IMPLEMENTED
VALIDATED
DEPRECATED
BLOCKED
TODO
```

`TODO` is a legitimate architectural state.

It does not mean the variable may be guessed.

---

# 6. Domain Classification

Variables belong to one of:

```text
MARKET
INSTRUMENT
SESSION
STATE
FEATURE
PREDICTION
ECONOMIC
OPTION_SELECTION
RISK
POSITION
EXECUTION
ACCOUNTING
PERFORMANCE
RESEARCH
OPERATIONAL
```

---

# 7. Type Classification

The registry distinguishes:

```text scalar
boolean
enumeration
timestamp
identifier
quantity
price
currency
probability
distribution
vector
state object
event object
```

The implementation must preserve semantic types.

---

# 8. Time Semantics

Every time-sensitive variable defines:

```text EventTime
EffectiveTime
AvailabilityTime
```

where applicable.

These are not automatically identical.

---

# 9. Causal Availability

Each variable must answer:

```text Can this value be known at decision time t?
```

The registry therefore contains:

```text AvailabilityRule.
```

Example:

```text VAR-PRED-001
AvailabilityRule:
available only after FeatureSnapshot(t) is complete.
```

---

# 10. Market Variables

The initial canonical market variables include:

```text VAR-MKT-001  InstrumentID
VAR-MKT-002  EventTimestamp
VAR-MKT-003  BidPrice
VAR-MKT-004  AskPrice
VAR-MKT-005  LastPrice
VAR-MKT-006  BidQuantity
VAR-MKT-007  AskQuantity
VAR-MKT-008  TradeQuantity
VAR-MKT-009  MarketSequence
```

The exact universe remains dependent on the final data contract.

---

# 11. Instrument Variables

Canonical instrument information includes:

```text VAR-INS-001  InstrumentIdentity
VAR-INS-002  InstrumentType
VAR-INS-003  Expiry
VAR-INS-004  Strike
VAR-INS-005  OptionType
VAR-INS-006  LotSize
VAR-INS-007  TickSize
VAR-INS-008  TradingStatus
```

---

# 12. Provider Status

The following remain:

```text TRUE_DATA_CONTRACT = TODO
```

until the exact provider documentation is verified.

Therefore the registry does not assert that a specific TrueData endpoint supplies any particular field.

---

# 13. Session Variables

Examples:

```text VAR-SES-001  SessionID
VAR-SES-002  SessionState
VAR-SES-003  SessionOpenTime
VAR-SES-004  SessionCloseTime
VAR-SES-005  SessionElapsedTime
VAR-SES-006  SessionRemainingTime
```

---

# 14. Session State Ownership

Owner:

```text SessionStateEngine
```

Consumers may read session state.

They cannot independently redefine it.

---

# 15. Opening Range Variables

Canonical variables include:

```text VAR-OR-001  OpeningRangeHigh
VAR-OR-002  OpeningRangeLow
VAR-OR-003  OpeningRangeWidth
VAR-OR-004  OpeningRangeComplete
```

The opening-range definition belongs to the State/Feature specification.

---

# 16. Market-State Variables

Examples:

```text VAR-ST-001  MarketRegime
VAR-ST-002  VolatilityState
VAR-ST-003  DirectionalState
VAR-ST-004  TrendState
VAR-ST-005  LiquidityState
VAR-ST-006  SessionPhase
```

Each state must have a canonical state-transition definition.

---

# 17. State Ownership

State variables are owned by:

```text StateEngine
```

Feature calculations may derive observations from state.

They do not mutate state.

---

# 18. Feature Variables

Every feature receives its own registry entry.

Examples:

```text VAR-FTR-001  VolatilityFeature
VAR-FTR-002  MomentumFeature
VAR-FTR-003  RangeFeature
VAR-FTR-004  LiquidityFeature
```

These names are placeholders until the final feature set is frozen.

---

# 19. Feature Definition Requirement

A feature entry must specify:

```text mathematical definition
lookback
sampling frequency
source variables
availability timestamp
normalization
missing-data behavior.
```

---

# 20. Prediction Variables

Canonical prediction outputs include only explicitly specified quantities.

Examples:

```text VAR-PRED-001  DirectionProbability
VAR-PRED-002  ExpectedMove
VAR-PRED-003  ContinuationProbability
VAR-PRED-004  ReversalProbability
VAR-PRED-005  PredictionUncertainty
```

Not all of these necessarily survive final model reduction.

Unused variables should be removed.

---

# 21. Prediction Ownership

Owner:

```text PredictionEngine
```

The prediction engine does not own:

```text ExpectedNetEconomicValue
AuthorizedRisk
PositionQuantity
```

Those belong to downstream modules.

---

# 22. Economic Variables

Canonical economic outputs include:

```text VAR-ECO-001  ExpectedGrossValue
VAR-ECO-002  ExpectedExecutionCost
VAR-ECO-003  ExpectedNetValue
VAR-ECO-004  EconomicEligibility
```

---

# 23. Economic Ownership

Owner:

```text EconomicEngine
```

Economic calculations must use only causally available inputs.

---

# 24. Option Selection Variables

Examples:

```text VAR-OPT-001  CandidateInstrumentSet
VAR-OPT-002  InstrumentScore
VAR-OPT-003  SelectedInstrument
VAR-OPT-004  SelectionReason
```

---

# 25. Option Selection Ownership

Owner:

```text OptionSelectionEngine
```

It does not own:

```text AuthorizedRisk
```

or:

```text ActualPosition.
```

---

# 26. Risk Variables

Canonical risk variables include:

```text VAR-RSK-001  AvailableRiskBudget
VAR-RSK-002  AuthorizedRisk
VAR-RSK-003  RiskPerUnit
VAR-RSK-004  RiskStatus
VAR-RSK-005  RiskPolicyVersion
```

---

# 27. Risk Ownership

Owner:

```text RiskEngine
```

---

# 28. Risk Independence

The registry explicitly prohibits:

```text Prediction → AuthorizedRisk
```

unless a separately validated risk policy defines such a dependency.

Even then:

```text prediction
```

does not directly mutate risk.

It is an input to a risk-policy function.

---

# 29. Position Variables

Canonical position variables:

```text VAR-POS-001  PositionID
VAR-POS-002  PositionStatus
VAR-POS-003  PositionQuantity
VAR-POS-004  AverageEntryPrice
VAR-POS-005  PositionSide
VAR-POS-006  PositionInstrument
```

---

# 30. Position Ownership

Owner:

```text PositionLedger
```

The ledger is updated from authoritative fills.

---

# 31. Execution Variables

Canonical execution variables:

```text VAR-EXE-001  OrderID
VAR-EXE-002  OrderIntent
VAR-EXE-003  OrderStatus
VAR-EXE-004  RequestedQuantity
VAR-EXE-005  FilledQuantity
VAR-EXE-006  RemainingQuantity
VAR-EXE-007  AverageFillPrice
VAR-EXE-008  ExecutionCost
VAR-EXE-009  Slippage
```

---

# 32. Execution Ownership

Owner:

```text ExecutionEngine
```

---

# 33. Order Versus Fill

The registry explicitly distinguishes:

```text RequestedQuantity
```

from:

```text FilledQuantity.
```

Likewise:

```text OrderPrice
```

is distinct from:

```text AverageFillPrice.
```

This prevents theoretical intent from becoming accounting reality.

---

# 34. Accounting Variables

Canonical variables include:

```text VAR-PNL-001  RealizedPnL
VAR-PNL-002  UnrealizedPnL
VAR-PNL-003  CurrentPnL
VAR-PNL-004  PeakPnL
VAR-PNL-005  ProfitGiveback
VAR-PNL-006  Drawdown
VAR-PNL-007  TradeNetPnL
```

---

# 35. Duplicate P&L Prevention

The registry explicitly defines:

```text CurrentPnL
```

as the canonical current-profit measure.

A separate synonymous variable such as:

```text CurrentProfit
```

is prohibited.

Likewise, the system retains one canonical concept for:

```text ExpectedHorizon
```

and does not create a second synonymous field merely for naming convenience.

---

# 36. Peak P&L

Definition:

```text PeakPnL(t)
=
max(PnL(τ))
for all τ ≤ t.
```

Owner:

```text AccountingEngine.
```

---

# 37. Profit Giveback

Definition:

```text ProfitGiveback(t)
=
PeakPnL(t) - CurrentPnL(t)
```

subject to the canonical accounting convention.

Owner:

```text AccountingEngine.
```

---

# 38. Drawdown

Drawdown remains distinct from:

```text ProfitGiveback
```

where their definitions differ.

No reporting layer may silently substitute one for the other.

---

# 39. Label Variables

Historical labels are separate from live trading state.

Examples:

```text VAR-LBL-001  OutcomeLabel
VAR-LBL-002  LabelHorizon
VAR-LBL-003  LabelAvailabilityTime
VAR-LBL-004  LabelStatus
```

---

# 40. Label Ownership

Owner:

```text HistoricalLabelEngine
```

Labels are created during research.

They are not available to the live decision engine.

---

# 41. Future Outcome Isolation

The registry explicitly marks:

```text OutcomeLabel
```

as:

```text FUTURE_DERIVED.
```

Therefore:

```text LiveFeatureEngine
LivePredictionEngine
LiveDecisionEngine
```

cannot consume it.

---

# 42. Research Variables

Examples:

```text VAR-RES-001  ExperimentID
VAR-RES-002  RunID
VAR-RES-003  DatasetVersion
VAR-RES-004  ModelVersion
VAR-RES-005  ParameterVersion
VAR-RES-006  PrimaryMetric
VAR-RES-007  ValidationStatus
```

These belong to research infrastructure.

---

# 43. Operational Variables

Examples:

```text VAR-OPS-001  DataConnectionStatus
VAR-OPS-002  ReconciliationStatus
VAR-OPS-003  SystemHealth
VAR-OPS-004  SafetyStatus
VAR-OPS-005  LastProcessedEvent
```

These belong to the operational layer.

---

# 44. Variable Dependency Record

Each variable has:

```text Inputs
```

and:

```text Outputs/Consumers.
```

For example:

```text ExpectedNetValue
    Inputs:
        DirectionProbability
        PayoffDistribution
        ExpectedExecutionCost

    Consumers:
        EconomicDecisionEngine
```

---

# 45. Dependency Direction

The registry must enforce:

```text Market
 ↓
State
 ↓
Feature
 ↓
Prediction
 ↓
Economic
 ↓
Risk
 ↓
Sizing
 ↓
Execution
 ↓
Position
 ↓
Accounting
 ↓
Performance
```

Backward dependencies require explicit architectural justification.

---

# 46. Temporal Dependency

A dependency must specify:

```text same-event
previous-state
historical-window
future-label
```

Example:

```text PeakPnL(t)
```

depends on:

```text PnL(τ), τ <= t.
```

It does not depend on:

```text PnL(t+1).
```

---

# 47. Update Frequency

Each variable defines its update trigger:

```text event-driven
tick-driven
bar-driven
state-transition
trade-driven
session-driven
batch/research-only.
```

---

# 48. Persistence Policy

Each variable is classified:

```text EPHEMERAL
SNAPSHOTTED
EVENT_SOURCED
LEDGER_PERSISTED
RESEARCH_PERSISTED
```

---

# 49. Source of Truth

Each important value has one authoritative source.

Examples:

```text FilledQuantity
→ FillLedger

PositionQuantity
→ PositionLedger

RealizedPnL
→ AccountingLedger

ModelVersion
→ ModelRegistry.
```

Derived copies are not authoritative.

---

# 50. Derived Values

A derived variable must identify its source.

For example:

```text ProfitGiveback
```

is derived from:

```text PeakPnL
+
CurrentPnL.
```

It should not be independently persisted as an independently mutable fact unless required for audit/performance.

---

# 51. Event-Sourced Values

Authoritative economic facts should be reconstructable from:

```text immutable events.
```

For example:

```text FillEvents
```

should allow reconstruction of:

```text Position
```

and:

```text Trade accounting.
```

---

# 52. Interface Registry

Each module interface is assigned:

```text InterfaceID.
```

Examples:

```text IF-DATA-001
IF-STATE-001
IF-FEATURE-001
IF-PRED-001
IF-ECO-001
IF-RISK-001
IF-SIZE-001
IF-EXEC-001
IF-POS-001
IF-PNL-001
```

---

# 53. Data Interface

Conceptually:

```text MarketDataSource
    → CanonicalEventStream
```

Input:

```text provider messages.
```

Output:

```text canonical events.
```

---

# 54. State Interface

Conceptually:

```text StateEngine.transition(
    State,
    Event
)
→
StateTransitionResult
```

The result includes:

```text previous state
new state
transition identity
transition validity
```

---

# 55. Feature Interface

```text FeatureEngine.compute(
    StateSnapshot
)
→
FeatureSnapshot
```

The feature snapshot contains:

```text values
timestamp
version
validity.
```

---

# 56. Prediction Interface

```text PredictionEngine.predict(
    FeatureSnapshot,
    ModelVersion
)
→
Prediction
```

---

# 57. Economic Interface

```text EconomicEngine.evaluate(
    Prediction,
    MarketState,
    InstrumentCandidate,
    ExecutionEstimate
)
→
EconomicEvaluation
```

---

# 58. Risk Interface

```text RiskEngine.authorize(
    EconomicEvaluation,
    PortfolioState,
    RiskState
)
→
RiskAuthorization
```

---

# 59. Sizing Interface

```text PositionSizingEngine.size(
    RiskAuthorization,
    InstrumentState,
    ExecutionConstraints
)
→
AuthorizedQuantity
```

---

# 60. Execution Interface

```text ExecutionEngine.submit(
    OrderIntent
)
→
OrderLifecycle
```

The actual fill arrives asynchronously as:

```text FillEvent.
```

---

# 61. Position Interface

```text PositionLedger.apply(
    FillEvent
)
→
PositionTransition
```

---

# 62. Accounting Interface

```text AccountingEngine.calculate(
    PositionState,
    FillLedger,
    MarketState
)
→
AccountingSnapshot
```

---

# 63. Performance Interface

```text PerformanceEngine.aggregate(
    TradeOutcomes
)
→
PerformanceSnapshot
```

---

# 64. Validation Interface

```text ValidationEngine.evaluate(
    Candidate,
    Dataset,
    Protocol
)
→
ValidationReport
```

---

# 65. Research Interface

```text ResearchEngine.register(
    ExperimentDefinition
)
→
ExperimentID
```

and:

```text ResearchEngine.record(
    RunResult
)
```

---

# 66. Error Ownership

Errors belong to the module that detects the violated contract.

For example:

```text invalid quote
→ DataError

invalid state transition
→ StateError

risk exceeded
→ RiskError

unreconciled position
→ Accounting/OperationalError.
```

---

# 67. Version Ownership

Version types are distinct:

```text DataVersion
ModelVersion
ParameterVersion
RiskPolicyVersion
ExecutionModelVersion
AccountingVersion
SpecificationVersion.
```

A generic:

```text version = "1.2"
```

is insufficient.

---

# 68. Compatibility Matrix

A production candidate must have a compatible combination:

```text SpecificationVersion
+
DataSchemaVersion
+
ModelVersion
+
ParameterVersion
+
RiskPolicyVersion
+
ExecutionVersion
+
AccountingVersion.
```

---

# 69. TrueData Status Matrix

At this point:

```text Canonical market concepts      DEFINED
Provider mapping                  TODO
Exact field names                 TODO
Exact API semantics               TODO
Historical data contract          TODO
Tick entitlement                  TODO
Depth contract                    TODO
Timestamp precision               TODO
Reconnect behavior                TODO
```

This is intentional.

---

# 70. Registry Invariants

```text REG-001 id="h08jvp"
Every canonical variable has one owner.

REG-002
Every canonical variable has one definition.

REG-003
Synonymous variables are consolidated.

REG-004
Future-derived variables cannot enter live causal paths.

REG-005
Every derived variable declares its inputs.

REG-006
Every time-sensitive variable declares availability semantics.

REG-007
Every authoritative value declares its source of truth.

REG-008
Every material variable has validation coverage.

REG-009
Every interface declares input/output contracts.

REG-010
Provider-specific concepts terminate at the provider adapter.

REG-011
Version types cannot be silently conflated.

REG-012
A variable cannot have two incompatible owners.

REG-013
A material mathematical change requires versioning.

REG-014
Persistence does not imply authority.

REG-015
Derived values cannot overwrite authoritative facts.
```

---

# 71. Canonical Ownership Map

The core ownership chain is now:

```text
External Provider
      ↓
Data Adapter
      ↓
Canonical Events
      ↓
State Engine
      ↓
Feature Engine
      ↓
Prediction Engine
      ↓
Economic Engine
      ↓
Option Selection Engine
      ↓
Risk Engine
      ↓
Position Sizing
      ↓
Execution Engine
      ↓
Fill Ledger
      ↓
Position Ledger
      ↓
Accounting Engine
      ↓
Performance Engine
```

Research and validation remain parallel governance systems.

---

# 72. Implementation Consequence

This registry means the eventual codebase cannot casually contain:

```text calculatePnL()
```

in five places.

Instead there is one canonical owner.

Likewise:

```text calculateRisk()
selectOption()
calculateExpectedValue()
calculateOpeningRange()
```

must each have an authoritative implementation.

---

# 73. Duplicate Semantic Detection

Before implementation is considered complete, the codebase must be audited for:

```text duplicate formulas
duplicate state
duplicate variables
duplicate transformations
duplicate provider mappings.
```

The registry becomes the comparison reference.

---

# 74. Current Status

```text Mathematical Model                  COMPLETE
Temporal State Model                    COMPLETE
Historical Label Model                  COMPLETE
Validation Model                        COMPLETE
Research Governance                     COMPLETE
Adversarial Test Specification           COMPLETE
Implementation Architecture             COMPLETE
Variable Ownership Registry              COMPLETE
Interface Registry                      COMPLETE
Provider Contract                       BLOCKED / TODO
```

The provider contract is the only major external-data boundary still deliberately unresolved.

---

# 75. Next Artifact

The next artifact is now the:

# CANONICAL DOMAIN TYPE AND EVENT SCHEMA SPECIFICATION

We will define the actual semantic objects that move through the system:

```text MarketEvent
Instrument
MarketState
FeatureSnapshot
Prediction
EconomicEvaluation
RiskAuthorization
OrderIntent
Order
Fill
Position
AccountingSnapshot
TradeOutcome
```

For each one, we will specify:

```text fields
types
invariants
ownership
timestamps
identity
immutability
serialization requirements
versioning
```

After that, we can finally define the concrete repository structure and implementation sequence without inventing architecture while coding.