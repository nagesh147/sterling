# CANONICAL REPOSITORY SCAFFOLD SPECIFICATION

Version 1.0

## 1. Purpose

This document defines the exact initial repository scaffold.

The scaffold must establish:

```text
file ownership
module boundaries
dependency boundaries
type boundaries
test boundaries
configuration boundaries
documentation boundaries
CI enforcement
```

No trading strategy is implemented at this stage.

---

# 2. Repository Root

The initial repository is:

```text
project/
├── src/
├── schemas/
├── tests/
├── configs/
├── scripts/
├── docs/
├── data/
├── .github/
├── README.md
├── VERSION
├── .gitignore
├── .editorconfig
└── project configuration files
```

The exact project configuration files depend on the selected implementation language.

---

# 3. Source Tree

The source tree is:

```text
src/
├── domain/
├── application/
├── interfaces/
├── infrastructure/
├── simulation/
├── research/
└── validation/
```

No top-level:

```text
strategy/
utils/
helpers/
common/
misc/
```

directories are permitted.

Those names create ownership ambiguity.

---

# 4. Domain Tree

```text
src/domain/
├── common/
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
└── research/
```

Each directory represents a semantic owner.

---

# 5. Common Domain Files

```text
src/domain/common/
├── identifiers
├── timestamps
├── money
├── price
├── quantity
├── probability
├── versions
└── errors
```

These contain only reusable semantic primitives.

They must not contain business logic.

---

# 6. Event Files

```text
src/domain/events/
├── event-envelope
├── market-event
├── quote-event
├── trade-event
├── depth-event
├── instrument-event
├── session-event
├── order-events
├── fill-event
└── index
```

---

# 7. Instrument Files

```text
src/domain/instruments/
├── instrument
├── option-contract
├── contract-specification
├── instrument-status
└── instrument-rules
```

---

# 8. Market Files

```text
src/domain/market/
├── quote
├── trade-observation
├── depth-snapshot
├── market-snapshot
└── market-rules
```

---

# 9. State Files

```text
src/domain/state/
├── market-state
├── session-state
├── opening-range
├── state-transition
├── state-machine
├── state-invariants
└── state-errors
```

This is the authoritative state implementation.

---

# 10. Feature Files

```text
src/domain/features/
├── feature-definition
├── feature-snapshot
├── feature-calculator
├── feature-validity
├── feature-version
└── feature-errors
```

Individual features should be added later.

Do not create dozens of feature files before the feature specification is frozen.

---

# 11. Prediction Files

```text
src/domain/prediction/
├── prediction
├── prediction-output
├── prediction-model
├── prediction-version
├── prediction-uncertainty
└── prediction-errors
```

The first implementation can use a deterministic test model.

---

# 12. Economics Files

```text
src/domain/economics/
├── economic-evaluation
├── expected-value
├── execution-cost
├── net-value
├── economic-eligibility
└── economic-errors
```

---

# 13. Options Files

```text
src/domain/options/
├── option-candidate
├── option-selection
├── option-score
├── option-eligibility
└── option-errors
```

---

# 14. Risk Files

```text
src/domain/risk/
├── risk-state
├── risk-policy
├── risk-authorization
├── risk-constraint
├── risk-violation
└── risk-errors
```

Risk is isolated intentionally.

---

# 15. Position Files

```text
src/domain/positions/
├── position
├── position-transition
├── position-ledger
├── trade
├── trade-lifecycle
└── position-errors
```

---

# 16. Execution Files

```text
src/domain/execution/
├── order-intent
├── order
├── fill
├── execution-cost
├── slippage
├── order-lifecycle
└── execution-errors
```

These are canonical execution concepts, not broker implementations.

---

# 17. Accounting Files

```text
src/domain/accounting/
├── accounting-snapshot
├── realized-pnl
├── unrealized-pnl
├── current-pnl
├── peak-pnl
├── profit-giveback
├── drawdown
├── trade-outcome
└── accounting-errors
```

There must be one authoritative implementation of P&L.

---

# 18. Performance Files

```text
src/domain/performance/
├── equity-curve
├── performance-snapshot
├── return-metrics
├── drawdown-metrics
├── execution-metrics
└── trade-statistics
```

Performance consumes accounting.

It does not redefine accounting.

---

# 19. Research Domain Files

```text
src/domain/research/
├── experiment
├── experiment-run
├── dataset-version
├── parameter-version
├── model-version
├── validation-protocol
└── research-result
```

These are semantic objects.

Research execution belongs elsewhere.

---

# 20. Application Tree

```text
src/application/
├── runtime/
├── backtest/
├── paper/
├── live/
├── research/
└── promotion/
```

---

# 21. Runtime Application

```text
src/application/runtime/
├── market-event-processor
├── opportunity-evaluator
├── trade-authorization-service
├── order-submission-service
├── fill-processing-service
└── runtime-errors
```

These orchestrate.

They do not implement canonical formulas.

---

# 22. Backtest Application

```text
src/application/backtest/
├── backtest-service
├── backtest-runner
├── backtest-result
└── backtest-errors
```

The backtest application invokes the same domain services used by runtime execution.

---

# 23. Paper Application

```text
src/application/paper/
├── paper-runtime
├── paper-runner
└── paper-errors
```

---

# 24. Live Application

```text
src/application/live/
├── live-runtime
├── live-runner
├── live-safety-gate
└── live-errors
```

The live safety gate is separate from strategy logic.

---

# 25. Research Application

```text
src/application/research/
├── experiment-service
├── dataset-service
├── parameter-service
├── model-service
└── research-runner
```

---

# 26. Promotion Application

```text
src/application/promotion/
├── promotion-service
├── promotion-policy
├── promotion-gate
└── promotion-errors
```

Promotion is an explicit state transition.

---

# 27. Interface Tree

```text
src/interfaces/
├── market-data/
├── execution/
├── persistence/
├── models/
└── system/
```

---

# 28. Market Data Interfaces

```text
src/interfaces/market-data/
├── market-data-source
├── market-data-health
└── market-data-errors
```

The interface emits canonical events.

---

# 29. Execution Interfaces

```text
src/interfaces/execution/
├── execution-gateway
├── execution-status-source
└── execution-errors
```

---

# 30. Persistence Interfaces

```text
src/interfaces/persistence/
├── event-store
├── order-repository
├── fill-repository
├── position-repository
├── accounting-repository
├── experiment-repository
├── model-repository
└── repository-errors
```

---

# 31. Model Interfaces

```text
src/interfaces/models/
├── model-provider
├── model-artifact-store
└── model-errors
```

---

# 32. System Interfaces

```text
src/interfaces/system/
├── clock
├── random-source
├── configuration
├── logger
└── system-errors
```

The clock is injected.

No domain code calls the system clock directly.

---

# 33. Infrastructure Tree

```text
src/infrastructure/
├── market-data/
├── execution/
├── persistence/
├── clock/
├── randomness/
├── serialization/
├── configuration/
└── observability/
```

---

# 34. Market Data Infrastructure

Initially:

```text
src/infrastructure/market-data/
├── truedata/
│   ├── truedata-connection
│   ├── truedata-decoder
│   ├── truedata-mapper
│   ├── truedata-health
│   └── truedata-errors
└── historical/
    ├── historical-data-source
    └── historical-data-reader
```

The TrueData directory must remain isolated.

---

# 35. Execution Infrastructure

```text
src/infrastructure/execution/
├── paper/
├── live/
└── common/
```

Broker-specific implementations belong under `live/`.

---

# 36. Persistence Infrastructure

```text
src/infrastructure/persistence/
├── sqlite/
├── files/
└── migrations/
```

SQLite is an implementation choice.

It is not a domain dependency.

---

# 37. Clock Infrastructure

```text
src/infrastructure/clock/
├── system-clock
└── simulated-clock
```

---

# 38. Randomness Infrastructure

```text
src/infrastructure/randomness/
└── seeded-random-source
```

Unseeded randomness is prohibited in deterministic research execution.

---

# 39. Serialization Infrastructure

```text
src/infrastructure/serialization/
├── event-serializer
├── domain-serializer
└── schema-mapper
```

---

# 40. Configuration Infrastructure

```text
src/infrastructure/configuration/
├── config-loader
├── config-validator
└── config-errors
```

---

# 41. Observability Infrastructure

```text
src/infrastructure/observability/
├── logging/
├── metrics/
├── tracing/
└── health/
```

Observability is read-only with respect to domain state.

---

# 42. Simulation Tree

```text
src/simulation/
├── market/
├── execution/
├── replay/
├── scenarios/
└── fixtures/
```

---

# 43. Simulation Market

```text
src/simulation/market/
├── historical-market-source
├── synthetic-market-source
└── market-replay
```

All outputs must be canonical market events.

---

# 44. Simulation Execution

```text
src/simulation/execution/
├── simulated-execution-gateway
├── slippage-model
├── latency-model
├── partial-fill-model
├── spread-model
└── execution-scenarios
```

---

# 45. Replay

```text
src/simulation/replay/
├── event-replayer
├── replay-clock
└── replay-errors
```

---

# 46. Scenarios

```text
src/simulation/scenarios/
├── false-breakout
├── whipsaw
├── gap
├── spread-expansion
├── stale-data
├── duplicate-event
├── partial-fill
├── risk-attack
└── future-leak
```

These are deterministic test scenarios.

---

# 47. Research Tree

```text
src/research/
├── experiments/
├── datasets/
├── parameters/
├── models/
├── runners/
├── reports/
└── lineage/
```

---

# 48. Research Dataset Files

```text
src/research/datasets/
├── dataset-registry
├── dataset-manifest
├── dataset-checksum
└── dataset-loader
```

---

# 49. Research Model Files

```text
src/research/models/
├── model-registry
├── model-artifact
├── model-compatibility
└── model-promotion-state
```

---

# 50. Validation Tree

```text
src/validation/
├── causality/
├── statistical/
├── economic/
├── execution/
├── risk/
├── state-machine/
├── adversarial/
├── regression/
└── promotion/
```

---

# 51. Causality Validator

```text
src/validation/causality/
├── availability-checker
├── dependency-tracer
├── lookahead-detector
└── causality-report
```

---

# 52. State Validator

```text
src/validation/state-machine/
├── transition-validator
├── reachability-validator
├── invariant-validator
└── state-report
```

---

# 53. Adversarial Validator

```text
src/validation/adversarial/
├── scenario-runner
├── metamorphic-runner
├── attack-suite
└── adversarial-report
```

---

# 54. Schemas

```text
schemas/
├── events/
├── domain/
├── research/
└── configuration/
```

Schemas describe transport/persistence contracts.

They do not replace domain types.

---

# 55. Test Tree

```text
tests/
├── unit/
├── contract/
├── integration/
├── property/
├── simulation/
├── adversarial/
├── regression/
└── end-to-end/
```

---

# 56. Unit Test Ownership

Unit tests follow domain ownership:

```text tests/unit/domain/state/
tests/unit/domain/features/
tests/unit/domain/risk/
tests/unit/domain/accounting/
```

---

# 57. Architecture Tests

Create:

```text tests/architecture/
```

This directory is mandatory.

It contains tests such as:

```text domain_cannot_import_infrastructure
domain_cannot_import_provider
strategy_cannot_import_broker
research_cannot_mutate_production
accounting_owns_pnl
```

---

# 58. Contract Tests

```text tests/contract/
├── market-data/
├── execution/
├── persistence/
└── models/
```

---

# 59. Golden Tests

```text tests/regression/golden/
```

contains deterministic end-to-end fixtures.

Each fixture specifies:

```text input events
configuration
versions
expected decisions
expected orders
expected fills
expected positions
expected accounting.
```

---

# 60. Property Tests

```text tests/property/
├── state/
├── risk/
├── accounting/
├── execution/
└── causality/
```

---

# 61. Adversarial Tests

```text tests/adversarial/
├── causality/
├── state/
├── execution/
├── risk/
├── economics/
└── data-integrity/
```

---

# 62. Configuration Tree

```text
configs/
├── base/
├── research/
├── test/
├── paper/
└── live/
```

---

# 63. Configuration Rule

The hierarchy is:

```text base
  ↓
environment-specific configuration
```

but production configuration must be explicitly versioned and validated.

---

# 64. Documentation Tree

```text
docs/
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

The artifacts we have produced belong here.

---

# 65. Documentation Registry

Create:

```text docs/00-index.md
```

It maps:

```text specification ID
document
version
status
dependencies.
```

This becomes the documentation entry point.

---

# 66. Required Root Files

The initial repository must contain:

```text
README.md
VERSION
.gitignore
.editorconfig
```

plus the language/toolchain configuration.

---

# 67. README Structure

The README initially contains:

```text
Project purpose
Architecture summary
Repository structure
Development setup
Testing
Validation
Research workflow
Paper/live status
Documentation index
```

It must not claim live trading capability before that capability exists.

---

# 68. VERSION

The repository starts at:

```text
0.1.0
```

until the first implementation milestone is completed.

Version changes are intentional.

---

# 69. Git Ignore

The repository must exclude:

```text environment secrets
virtual environments
build output
cache
logs
local databases
raw large datasets
credentials
provider tokens.
```

---

# 70. Secret Policy

No secret may appear in:

```text source code
configuration committed to Git
tests
fixtures
documentation
logs.
```

Use environment-specific secret injection.

---

# 71. Initial CI Pipeline

The initial CI pipeline must execute:

```text formatting check
lint
type check
unit tests
architecture tests
schema validation.
```

---

# 72. CI Expansion

As implementation progresses, add:

```text integration tests
contract tests
property tests
adversarial tests
regression tests
causality tests
```

---

# 73. Architecture CI Gate

The architecture tests are not informational.

A forbidden dependency causes:

```text CI FAILURE.
```

---

# 74. Test CI Gate

A failing invariant causes:

```text CI FAILURE.
```

A failing formatting check alone may be treated as lower-level hygiene, but domain/invariant failures must block progression.

---

# 75. Initial Empty Interfaces

The scaffold may contain interface declarations without implementations.

For example:

```text MarketDataSource
ExecutionGateway
Clock
RandomSource
EventStore
```

This is preferable to prematurely choosing concrete infrastructure.

---

# 76. Initial Domain Implementation

The first concrete domain implementation should be:

```text identifiers
timestamps
financial primitives
events
instrument types
```

Then state.

---

# 77. First Test to Write

The first substantive test should establish deterministic identity and event behavior.

Conceptually:

```text
same event
+
same serialization
=
same canonical representation.
```

---

# 78. Second Test

The second test should verify state transition determinism:

```text State_t
+
Event_t
=
State_(t+1)
```

Repeated execution must produce the same state.

---

# 79. Third Test

The third should verify event idempotency.

Processing the same event twice must not create a second economic effect.

---

# 80. Fourth Test

The fourth should verify the accounting ownership boundary.

No order without a fill may create a position.

---

# 81. Fifth Test

The fifth should verify risk immutability.

A downstream event must not increase an already issued risk authorization.

---

# 82. Scaffold Completion Criteria

The scaffold is complete when:

```text every architectural package exists
every major ownership boundary exists
interfaces are defined
initial domain types exist
architecture tests execute
CI executes
documentation index exists
no strategy logic exists.
```

---

# 83. What Must NOT Be Created Yet

Do not yet create:

```text live broker implementation
production strategy
real predictive model
parameter optimizer
automatic model promotion
real-money execution
```

Those belong to later phases.

---

# 84. First Coding Milestone

The first coding milestone is:

```text Repository
    ↓
Primitive Types
    ↓
Canonical Events
    ↓
Instrument Model
    ↓
State Machine
    ↓
Tests
```

At the end of this milestone, we should be able to replay a deterministic event stream and reconstruct market state.

---

# 85. Second Coding Milestone

Then:

```text Features
    ↓
Prediction Contract
    ↓
Economic Engine
    ↓
Option Selection
```

---

# 86. Third Coding Milestone

Then:

```text Risk
    ↓
Sizing
    ↓
Simulated Execution
    ↓
Position Ledger
    ↓
Accounting.
```

---

# 87. Fourth Coding Milestone

Then:

```text End-to-end runtime
    ↓
Adversarial suite
    ↓
Strategy
    ↓
Backtester.
```

---

# 88. Fifth Coding Milestone

Then:

```text Research
    ↓
Validation
    ↓
Promotion
    ↓
External market data
    ↓
Paper trading
    ↓
Live.
```

---

# 89. Final Scaffold Tree

The resulting initial tree is:

```text
project/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── configs/
│   ├── base/
│   ├── research/
│   ├── test/
│   ├── paper/
│   └── live/
│
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── snapshots/
│   ├── synthetic/
│   └── manifests/
│
├── docs/
│   ├── 00-index.md
│   ├── 01-mathematical/
│   ├── 02-state/
│   ├── 03-labels/
│   ├── 04-validation/
│   ├── 05-research/
│   ├── 06-adversarial/
│   ├── 07-implementation/
│   ├── 08-domain/
│   └── 09-operations/
│
├── schemas/
│   ├── events/
│   ├── domain/
│   ├── research/
│   └── configuration/
│
├── scripts/
│
├── src/
│   ├── domain/
│   ├── application/
│   ├── interfaces/
│   ├── infrastructure/
│   ├── simulation/
│   ├── research/
│   └── validation/
│
├── tests/
│   ├── architecture/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── property/
│   ├── simulation/
│   ├── adversarial/
│   ├── regression/
│   └── end-to-end/
│
├── .editorconfig
├── .gitignore
├── README.md
└── VERSION
```

---

# 90. Scaffold Status

```text
Architecture                    FROZEN
Domain ownership               FROZEN
Dependency rules               FROZEN
File ownership                 DEFINED
Test architecture              DEFINED
CI architecture                DEFINED
Initial implementation order   DEFINED
External provider mapping      TODO
```

---

# 91. Next Artifact

The scaffold is now sufficiently specified to create the actual repository.

Before writing the first implementation code, the next artifact should define:

# CANONICAL FOUNDATION TYPE SPECIFICATION

That document will specify the exact semantics of:

```text ID
Timestamp
Price
Quantity
Money
Probability
Duration
Version
EventEnvelope
```

including valid ranges, equality rules, serialization, precision, and failure behavior.

Those primitives are the foundation on which every subsequent object depends.