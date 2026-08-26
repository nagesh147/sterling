# CANONICAL REPOSITORY AND PACKAGE ARCHITECTURE

Version 1.0

## 1. Purpose

This specification defines the physical software architecture that implements the canonical trading-system specification.

It establishes:

```text
repository structure
package boundaries
module ownership
dependency direction
import restrictions
test placement
schema ownership
research separation
runtime separation
simulation separation
infrastructure isolation
```

The architecture must make invalid dependencies difficult to create.

---

# 2. Primary Architectural Principle

The repository is organized around domain ownership, not around technical convenience.

The top-level structure is:

```text
project/
│
├── src/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── simulation/
│   ├── research/
│   ├── validation/
│   └── interfaces/
│
├── schemas/
├── tests/
├── configs/
├── scripts/
├── docs/
└── data/
```

The exact language-specific naming may change, but the architectural boundaries do not.

---

# 3. Domain Layer

The Domain layer contains the canonical business and mathematical semantics.

```text
src/domain/
│
├── events/
├── instruments/
├── market/
├── state/
├── features/
├── prediction/
├── economics/
├── options/
├── risk/
├── positions/
├── execution/
├── accounting/
├── performance/
├── research/
└── common/
```

---

# 4. Domain Rule

The Domain layer must not depend on:

```text broker APIs
database drivers
HTTP clients
filesystem APIs
CLI frameworks
environment variables
provider SDKs.
```

The domain should remain executable independently of infrastructure.

---

# 5. Domain Common

```text
domain/common/
```

contains only genuinely shared primitives.

Examples:

```text IDs
timestamps
money
price
quantity
probability
version identifiers
result/error primitives.
```

It must not become a miscellaneous utility dumping ground.

---

# 6. Domain Events

```text
domain/events/
```

owns:

```text EventEnvelope
MarketEvent
QuoteEvent
TradeEvent
DepthEvent
FillEvent
Order events
State transition events
```

Event definitions are canonical.

---

# 7. Event Ownership

No other package may redefine a canonical event.

For example:

```text
QuoteEvent
```

must not separately exist in:

```text backtester/
broker/
research/
```

with subtly different semantics.

---

# 8. Instrument Domain

```text
domain/instruments/
```

owns:

```text Instrument
OptionContract
InstrumentIdentity
InstrumentStatus
ContractSpecification
```

It owns instrument semantics, not provider mappings.

---

# 9. Market Domain

```text
domain/market/
```

owns:

```text MarketSnapshot
Quote
TradeObservation
DepthSnapshot
MarketMeasurements
```

These are canonical representations.

---

# 10. State Domain

```text
domain/state/
```

owns:

```text MarketState
SessionState
OpeningRange
StateTransition
StateMachine
StateInvariant
```

This is the authoritative state-transition layer.

---

# 11. State Boundary

The State layer may consume:

```text canonical events
instrument definitions
previous state
```

It may not consume:

```text prediction
P&L
future labels
research results.
```

---

# 12. Feature Domain

```text
domain/features/
```

owns:

```text FeatureDefinition
FeatureSnapshot
FeatureCalculator
FeatureValidity
FeatureVersion
```

Each feature must have one canonical implementation.

---

# 13. Prediction Domain

```text
domain/prediction/
```

owns:

```text Prediction
PredictionOutput
PredictionModel
PredictionVersion
PredictionUncertainty
```

The prediction domain does not decide whether to trade.

---

# 14. Economics Domain

```text
domain/economics/
```

owns:

```text EconomicEvaluation
ExpectedGrossValue
ExpectedExecutionCost
ExpectedNetValue
EconomicEligibility
```

This package owns economic mathematics.

---

# 15. Options Domain

```text
domain/options/
```

owns:

```text OptionCandidate
OptionSelection
OptionSelectionScore
OptionEligibility
```

It must use canonical instrument definitions.

---

# 16. Risk Domain

```text
domain/risk/
```

owns:

```text RiskState
RiskPolicy
RiskAuthorization
RiskConstraint
RiskViolation
```

Risk is deliberately isolated from prediction.

---

# 17. Risk Boundary

The Risk package may consume:

```text economic evaluation
portfolio state
account state
risk configuration
```

It may not modify:

```text prediction
market state
historical labels.
```

---

# 18. Position Domain

```text
domain/positions/
```

owns:

```text Position
PositionState
PositionTransition
PositionLedger
Trade
TradeLifecycle
```

Position state is derived from authoritative execution evidence.

---

# 19. Execution Domain

```text
domain/execution/
```

owns canonical execution concepts:

```text OrderIntent
Order
Fill
ExecutionCost
Slippage
OrderLifecycle
```

It does not contain broker-specific implementation.

---

# 20. Accounting Domain

```text
domain/accounting/
```

owns:

```text AccountingSnapshot
RealizedPnL
UnrealizedPnL
CurrentPnL
PeakPnL
ProfitGiveback
Drawdown
TradeOutcome
```

There must be exactly one authoritative implementation of these calculations.

---

# 21. Performance Domain

```text
domain/performance/
```

owns:

```text EquityCurve
PerformanceSnapshot
ReturnMetrics
DrawdownMetrics
ExecutionMetrics
TradeStatistics
```

Performance is downstream of accounting.

---

# 22. Research Domain

```text
domain/research/
```

owns the semantic definitions of:

```text Experiment
ExperimentRun
DatasetVersion
ParameterVersion
ModelVersion
ValidationProtocol
ResearchResult
```

Research storage and orchestration remain outside the Domain layer.

---

# 23. Application Layer

```text
src/application/
```

contains use cases and orchestration.

Examples:

```text process_market_event
evaluate_opportunity
authorize_trade
submit_order
process_fill
close_trade
run_backtest
run_validation
register_experiment
promote_model
```

Application services coordinate domain objects.

They do not redefine domain mathematics.

---

# 24. Application Rule

Application code may call:

```text Domain
Interfaces
Infrastructure through abstractions
```

but domain objects must not call application services.

---

# 25. Application Services

Conceptually:

```text
MarketEventProcessor
OpportunityEvaluator
TradeAuthorizationService
OrderSubmissionService
FillProcessingService
BacktestService
ValidationService
PromotionService
```

---

# 26. Market Event Processor

The runtime entry point is conceptually:

```text
process(event)
```

Its responsibility is orchestration:

```text Event
 ↓
State
 ↓
Features
 ↓
Prediction
 ↓
Economics
 ↓
Selection
 ↓
Risk
 ↓
Sizing
 ↓
OrderIntent
```

It does not implement those calculations itself.

---

# 27. Fill Processor

A fill enters through:

```text
FillEvent
```

and flows through:

```text
Fill
 ↓
PositionLedger
 ↓
Accounting
 ↓
Performance
```

No signal calculation is performed because of a historical fill.

---

# 28. Infrastructure Layer

```text
src/infrastructure/
```

contains external systems.

```text
infrastructure/
├── market_data/
├── execution/
├── persistence/
├── clock/
├── randomness/
├── logging/
├── configuration/
└── serialization/
```

---

# 29. Market Data Infrastructure

```text
infrastructure/market_data/
```

contains:

```text TrueDataAdapter
HistoricalDataAdapter
MarketDataConnection
ProviderMessageDecoder
ProviderFieldMapper
```

The exact TrueData implementation remains blocked until the provider contract is verified.

---

# 30. Provider Isolation

Only:

```text infrastructure/market_data/
```

may import the TrueData SDK or provider-specific protocol.

No domain package may import it.

---

# 31. Execution Infrastructure

```text
infrastructure/execution/
```

contains:

```text BrokerExecutionAdapter
PaperExecutionAdapter
LiveExecutionAdapter
ExecutionGateway
```

The domain sees only the canonical execution interface.

---

# 32. Simulation Infrastructure

The simulation system is separate from production infrastructure.

```text
src/simulation/
├── market/
├── execution/
├── clock/
├── scenarios/
├── replay/
└── fixtures/
```

---

# 33. Simulation Market

The simulation market produces canonical:

```text MarketEvents
```

rather than directly manipulating strategy state.

This ensures simulation passes through the same event boundary as live operation.

---

# 34. Simulation Execution

The simulated execution engine models:

```text spread
slippage
latency
partial fills
depth
rejections
gaps
execution failures.
```

It emits canonical:

```text FillEvents
```

---

# 35. Critical Backtest Rule

The backtester must not contain an alternate implementation of:

```text signal logic
risk logic
position logic
accounting logic.
```

It uses the same domain components.

Only market/execution environment differs.

---

# 36. Replay Engine

```text simulation/replay/
```

replays:

```text historical canonical events
```

through the same state machine.

---

# 37. Synthetic Scenario Engine

```text simulation/scenarios/
```

contains the adversarial scenarios defined in the previous specification.

Examples:

```text false_breakout
whipsaw
gap
spread_explosion
stale_quote
future_leak
partial_fill
risk_attack
state_corruption.
```

---

# 38. Research Layer

```text src/research/
```

contains research orchestration.

```text research/
├── experiments/
├── datasets/
├── parameters/
├── models/
├── runners/
├── reports/
└── lineage/
```

---

# 39. Research Experiment Manager

Owns:

```text experiment registration
experiment execution
experiment lineage
result storage
candidate comparison.
```

It must not directly mutate production models.

---

# 40. Dataset Manager

Owns:

```text DatasetVersion
DatasetSnapshot
DatasetManifest
DatasetChecksum
```

Historical datasets are immutable.

---

# 41. Parameter Manager

Owns:

```text ParameterVersion
ParameterProvenance
ParameterSearch
ParameterRegistry
```

Optimized parameters must retain their provenance.

---

# 42. Model Registry

Owns:

```text ModelVersion
ModelArtifact
ModelStatus
ModelCompatibility
PromotionState
```

Production can consume only approved model versions.

---

# 43. Validation Layer

```text src/validation/
```

contains formal verification and research validation.

```text validation/
├── statistical/
├── economic/
├── execution/
├── risk/
├── causality/
├── state_machine/
├── adversarial/
├── regression/
└── promotion/
```

---

# 44. Causality Validator

Responsible for detecting:

```text future dependencies
look-ahead
label leakage
calibration leakage
execution leakage
temporal violations.
```

---

# 45. State-Machine Validator

Responsible for:

```text transition validity
state reachability
impossible-state detection
invariant checking
transition coverage.
```

---

# 46. Adversarial Validator

Executes:

```text synthetic scenarios
metamorphic tests
parameter attacks
execution attacks
risk attacks
data attacks.
```

---

# 47. Statistical Validator

Evaluates:

```text calibration
sampling behavior
walk-forward performance
uncertainty
multiple-testing context.
```

---

# 48. Economic Validator

Evaluates:

```text net economic value
cost sensitivity
baseline comparison
ablation
economic monotonicity.
```

---

# 49. Promotion Validator

Combines the required validation evidence.

It does not decide based on a single metric.

Conceptually:

```text
Data
AND
Causality
AND
Statistics
AND
Economics
AND
Execution
AND
Risk
AND
Adversarial
AND
Operations
```

---

# 50. Interfaces Package

```text
src/interfaces/
```

contains contracts between domain/application and infrastructure.

Examples:

```text MarketDataSource
ExecutionGateway
Clock
RandomSource
Repositories
ModelArtifactStore
EventStore
```

---

# 51. Dependency Rule

Interfaces belong on the side that owns the abstraction.

For example:

```text domain/application
        ↓
ExecutionGateway interface
        ↑
BrokerExecutionAdapter
```

The domain does not depend on the broker adapter.

---

# 52. Repository Interfaces

Canonical interfaces include:

```text MarketEventRepository
OrderRepository
FillRepository
PositionRepository
AccountingRepository
ExperimentRepository
ModelRepository
DatasetRepository
```

---

# 53. Persistence Implementations

Concrete implementations reside in:

```text
infrastructure/persistence/
```

Examples:

```text SQLiteEventStore
SQLitePositionRepository
SQLiteExperimentRepository
```

A later migration to another database should not require rewriting domain logic.

---

# 54. Schemas Directory

```text
schemas/
```

contains externally serializable contracts.

Examples:

```text event schemas
configuration schemas
research schemas
experiment schemas
model manifests.
```

---

# 55. Schema Versus Domain Type

Schema:

```text transport/persistence representation. id="3b3shf"
```

Domain type:

```text semantic representation.
```

They must not automatically be treated as identical.

---

# 56. Schema Mapping

Conceptually:

```text External Schema
        ↓
Adapter
        ↓
Domain Object
```

and:

```text Domain Object
        ↓
Serializer
        ↓
Persistence Schema.
```

---

# 57. Tests Directory

Tests mirror architectural ownership:

```text
tests/
├── unit/
├── contract/
├── integration/
├── simulation/
├── adversarial/
├── regression/
├── property/
└── end_to_end/
```

---

# 58. Unit Tests

Unit tests verify:

```text pure formulas
state transitions
feature calculations
economic calculations
risk calculations
sizing
accounting.
```

---

# 59. Contract Tests

Contract tests verify boundaries:

```text Data → Domain
Execution → Domain
Persistence → Domain
Model → Prediction
```

---

# 60. Integration Tests

Integration tests verify multiple modules operating together.

Example:

```text MarketEvent
→ State
→ Feature
→ Prediction
→ EconomicEvaluation.
```

---

# 61. End-to-End Tests

End-to-end tests exercise:

```text MarketEvent
→ Order
→ Fill
→ Position
→ Accounting
→ TradeOutcome.
```

---

# 62. Property Tests

Property tests verify invariant classes such as:

```text conservation
monotonicity
idempotency
causality
risk bounds
```

rather than only fixed examples.

---

# 63. Regression Tests

Every previously discovered defect creates a permanent regression test.

This suite is cumulative.

---

# 64. Adversarial Tests

The synthetic scenarios defined previously live under:

```text tests/adversarial/
```

and use:

```text simulation/scenarios/
```

as scenario definitions.

---

# 65. Configuration Architecture

```text configs/
├── base/
├── research/
├── paper/
├── live/
└── test/
```

Configurations are environment-specific.

---

# 66. Configuration Rule

Production configuration must not be derived implicitly from:

```text research configuration.
```

Production requires an explicit approved configuration.

---

# 67. Documentation

```text docs/
```

contains the canonical specifications.

Recommended structure:

```text docs/
├── 01-mathematical/
├── 02-state/
├── 03-labels/
├── 04-validation/
├── 05-research/
├── 06-adversarial/
├── 07-implementation/
├── 08-domain/
└── 09-operations/
```

---

# 68. Specification Numbering

Every canonical specification should have:

```text SpecificationID
Version
Status
Dependencies
```

Example:

```text SPEC-STATE-001
Version: 1.0
Status: APPROVED
```

---

# 69. Import Architecture

The intended dependency graph is:

```text
                    ┌───────────────┐
                    │ Infrastructure│
                    └───────┬───────┘
                            ↓
                       Interfaces
                            ↓
                    Application Layer
                            ↓
                         Domain
```

However, in dependency-inversion terms, concrete infrastructure implements interfaces owned by the application/domain boundary.

---

# 70. More Precise Dependency Graph

```text
Domain
  ↑
Application
  ↑
Infrastructure
```

where arrows represent:

```text "implements/depends through abstraction"
```

not direct domain dependency on infrastructure.

---

# 71. Domain Import Restrictions

Domain cannot import:

```text infrastructure.*
research.runners
simulation.execution
CLI
database
provider SDK
```

---

# 72. Application Import Restrictions

Application may import:

```text domain.*
interfaces.*
```

It should not directly depend on:

```text provider SDK
database driver
```

---

# 73. Research Restrictions

Research may import:

```text domain.*
simulation.*
validation.*
interfaces.*
```

but cannot mutate:

```text production state.
```

---

# 74. Validation Restrictions

Validation may inspect:

```text domain
simulation
research artifacts
```

but cannot modify the candidate being evaluated.

---

# 75. Simulation Restrictions

Simulation may implement:

```text simulated infrastructure
```

but must emit canonical domain events.

It cannot introduce simulation-only domain semantics.

---

# 76. Production Runtime

The production runtime should conceptually be:

```text
src/application/runtime/
```

with composition:

```text DataAdapter
    ↓
EventProcessor
    ↓
Domain
    ↓
ExecutionGateway
```

---

# 77. Composition Root

There must be one explicit composition boundary where concrete implementations are wired together.

Conceptually:

```text application/bootstrap/
```

This is where:

```text TrueDataAdapter
SQLiteRepository
BrokerAdapter
Clock
Logger
ModelRegistry
```

are assembled.

---

# 78. No Hidden Dependencies

Domain objects must not instantiate:

```text database clients
HTTP clients
broker clients
global clocks.
```

Dependencies are supplied explicitly.

---

# 79. CLI

CLI commands should be thin wrappers around application services.

Examples:

```text run-backtest
run-validation
run-paper
inspect-model
inspect-experiment
replay-event-stream
run-adversarial-suite
```

The CLI must not contain strategy mathematics.

---

# 80. Scripts

Scripts are for:

```text data preparation
environment setup
migration
benchmarking
research utilities.
```

They are not authoritative implementations of domain calculations.

---

# 81. Data Directory

The repository should not treat mutable raw market data as source code.

Conceptually:

```text data/
├── raw/
├── normalized/
├── snapshots/
├── synthetic/
└── manifests/
```

Large datasets should normally remain outside Git.

---

# 82. Artifact Integrity

Every important dataset/model artifact should have:

```text version
checksum
creation metadata
source metadata.
```

---

# 83. Repository-Level Invariants

```text REPO-001 id="h2oj6n"
Domain contains no provider dependencies.

REPO-002
Domain contains no database dependencies.

REPO-003
Provider-specific types do not cross infrastructure boundaries.

REPO-004
Backtesting does not duplicate strategy mathematics.

REPO-005
Simulation emits canonical events.

REPO-006
Research cannot mutate production.

REPO-007
Validation cannot mutate candidates.

REPO-008
Every canonical formula has one implementation owner.

REPO-009
Every canonical event has one definition.

REPO-010
Production composition is explicit.

REPO-011
CLI contains no business logic.

REPO-012
Tests mirror architectural boundaries.

REPO-013
Large mutable datasets are not treated as source code.

REPO-014
Specification changes are versioned.

REPO-015
Provider contracts remain isolated.
```

---

# 84. Proposed Repository Tree

The concrete target is:

```text
project/
│
├── src/
│   ├── domain/
│   │   ├── common/
│   │   ├── events/
│   │   ├── instruments/
│   │   ├── market/
│   │   ├── state/
│   │   ├── features/
│   │   ├── prediction/
│   │   ├── economics/
│   │   ├── options/
│   │   ├── risk/
│   │   ├── positions/
│   │   ├── execution/
│   │   ├── accounting/
│   │   ├── performance/
│   │   └── research/
│   │
│   ├── application/
│   │   ├── runtime/
│   │   ├── backtest/
│   │   ├── paper/
│   │   ├── live/
│   │   ├── research/
│   │   └── promotion/
│   │
│   ├── interfaces/
│   │   ├── market_data/
│   │   ├── execution/
│   │   ├── persistence/
│   │   ├── models/
│   │   └── system/
│   │
│   ├── infrastructure/
│   │   ├── market_data/
│   │   ├── execution/
│   │   ├── persistence/
│   │   ├── clock/
│   │   ├── randomness/
│   │   ├── serialization/
│   │   ├── configuration/
│   │   └── observability/
│   │
│   ├── simulation/
│   │   ├── market/
│   │   ├── execution/
│   │   ├── replay/
│   │   ├── scenarios/
│   │   └── fixtures/
│   │
│   ├── research/
│   │   ├── experiments/
│   │   ├── datasets/
│   │   ├── parameters/
│   │   ├── models/
│   │   ├── runners/
│   │   ├── reports/
│   │   └── lineage/
│   │
│   └── validation/
│       ├── causality/
│       ├── statistical/
│       ├── economic/
│       ├── execution/
│       ├── risk/
│       ├── state_machine/
│       ├── adversarial/
│       ├── regression/
│       └── promotion/
│
├── schemas/
│   ├── events/
│   ├── domain/
│   ├── research/
│   └── configuration/
│
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── property/
│   ├── simulation/
│   ├── adversarial/
│   ├── regression/
│   └── end_to_end/
│
├── configs/
│   ├── base/
│   ├── research/
│   ├── paper/
│   ├── live/
│   └── test/
│
├── docs/
│
├── scripts/
│
├── data/
│
├── README.md
└── VERSION
```

---

# 85. Important Correction

We should not create this repository tree blindly and then force every concept into a directory.

The next step is an architectural dependency audit of this proposed tree.

Specifically, we must verify:

```text Can every required calculation live in exactly one place?
Can every dependency flow in one direction?
Can research use production semantics without mutating production?
Can backtest and live share the same domain logic?
Can TrueData remain replaceable?
Can every state transition be replayed?
Can every financial fact be reconstructed from authoritative events?
```

If any answer is "no", we fix the architecture before scaffolding.

---

# 86. Current Status

```text Mathematical Specification              COMPLETE
Temporal State Model                         COMPLETE
Historical Label Model                       COMPLETE
Validation Model                             COMPLETE
Research Governance                          COMPLETE
Adversarial Verification                     COMPLETE
Implementation Contracts                     COMPLETE
Variable Ownership                           COMPLETE
Domain/Event Schemas                         COMPLETE
Repository Architecture                      COMPLETE
```

The architecture is now ready for the final pre-coding audit.

---

# 87. Next Artifact

The next artifact should be:

# CANONICAL ARCHITECTURAL DEPENDENCY AND IMPORT AUDIT

This will be a deliberately hostile review of the repository design.

We will try to break it by constructing illegal dependencies such as:

```text Prediction → P&L
Risk → Future Outcome
Backtester → Future Candle
Domain → TrueData
Execution → Risk Expansion
Research → Production Mutation
Accounting → Decision
Feature → Future Label
```

and verify that the package architecture makes each one impossible or explicitly rejected.

Only after that audit passes should we scaffold the repository.