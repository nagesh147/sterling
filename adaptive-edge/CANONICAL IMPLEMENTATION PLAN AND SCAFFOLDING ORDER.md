# CANONICAL IMPLEMENTATION PLAN AND SCAFFOLDING ORDER

Version 1.0

## 1. Purpose

This document defines the exact implementation sequence for the system.

The objective is to avoid the common failure mode:

```text
write strategy
→ backtest
→ discover infrastructure problems
→ rewrite everything.
```

Instead:

```text
contracts
→ invariants
→ deterministic engine
→ execution model
→ accounting
→ validation
→ strategy
→ external data
→ live runtime.
```

---

# 2. Implementation Philosophy

The implementation follows:

```text
Specification
    ↓
Types
    ↓
Invariants
    ↓
Pure Domain Logic
    ↓
Simulation
    ↓
Validation
    ↓
Strategy
    ↓
External Integration
    ↓
Production Runtime
```

Each stage must pass its tests before the next stage begins.

---

# 3. Phase Zero — Repository Bootstrap

Create only the structural foundation.

Required:

```text
repository
package manager
language configuration
formatter
linter
type checker
test runner
CI
VERSION
README
docs/
src/
tests/
```

Do not implement trading logic.

---

# 4. Phase Zero Exit Criteria

The repository must demonstrate:

```text clean build
clean type check
clean lint
clean test suite
deterministic test execution
architecture-test execution.
```

The initial test suite may contain only architecture and placeholder contract tests.

---

# 5. Phase One — Canonical Primitive Types

Implement the fundamental types first.

Examples:

```text InstrumentID
EventID
OrderID
FillID
PositionID
TradeID
OpportunityID
DecisionID
ModelVersion
ParameterVersion
SchemaVersion
SpecificationVersion
```

---

# 6. Financial Primitive Types

Implement semantic representations for:

```text Price
Quantity
Money
Probability
Percentage
Duration
Timestamp
```

The implementation must make invalid values difficult to represent.

---

# 7. Why This Comes First

If the system uses primitive:

```text number
string
Date
```

everywhere, semantic errors become invisible.

For example:

```text OrderID accidentally passed as InstrumentID.
```

Strong domain types prevent this class of defect.

---

# 8. Phase One Tests

Test:

```text identity equality
serialization
invalid values
precision behavior
boundary values
version compatibility.
```

---

# 9. Phase Two — Canonical Events

Implement:

```text EventEnvelope
MarketEvent
QuoteEvent
TradeEvent
DepthEvent
InstrumentEvent
SessionEvent
FillEvent
Order events
```

---

# 10. Event Requirements

Every event must support:

```text immutable identity
timestamp
sequence
schema version
source
correlation ID
causation ID.
```

---

# 11. Phase Two Exit Criteria

Verify:

```text events are immutable
duplicate IDs are detectable
serialization is deterministic
invalid events are rejected
event ordering is deterministic.
```

---

# 12. Phase Three — Instrument Model

Implement:

```text Instrument
OptionContract
InstrumentIdentity
ContractSpecification
InstrumentStatus
```

This establishes the canonical contract model before option selection exists.

---

# 13. Instrument Tests

Test:

```text expiry
strike
option type
lot size
tick size
instrument identity
contract lifecycle.
```

---

# 14. Phase Four — State Machine

This is the first major subsystem.

Implement:

```text SessionState
MarketState
OpeningRange
StateTransition
StateMachine
```

---

# 15. State Transition Contract

The central function is conceptually:

```text
State_(t+1)
=
transition(State_t, Event_t)
```

It must be deterministic.

---

# 16. State Machine Tests

Build tests for:

```text normal event sequence
out-of-order events
duplicate events
missing events
session transitions
opening-range completion
market halt
market resume
instrument expiry.
```

---

# 17. Adversarial State Tests

Immediately attack:

```text impossible transition
future event
duplicate transition
time reversal
invalid session phase
negative sequence
unknown instrument.
```

The state machine must reject them.

---

# 18. Phase Four Exit Criteria

Do not continue until:

```text state replay is deterministic
state invariants pass
duplicate events are idempotent
impossible states are rejected.
```

---

# 19. Phase Five — Canonical Feature Engine

Implement the feature infrastructure.

First build:

```text FeatureDefinition
FeatureSnapshot
FeatureCalculator
FeatureVersion
FeatureValidity
```

Then implement individual features.

---

# 20. Feature Implementation Rule

Every feature must specify:

```text source variables
lookback
sampling
availability
formula
missing-data behavior
version.
```

No anonymous calculations are permitted.

---

# 21. Feature Causality Tests

For every feature:

```text remove future event
recalculate feature
```

The historical value must remain unchanged if that future event was unavailable at decision time.

---

# 22. Feature Mutation Test

Attempt:

```text future event injected
```

into the feature engine.

The causality validator must detect it.

---

# 23. Phase Six — Prediction Contract

Implement:

```text Prediction
PredictionModel
ModelVersion
PredictionOutput
PredictionUncertainty
```

Do not optimize a real model yet.

Initially implement:

```text deterministic mock model.
```

---

# 24. Why Mock First

The objective is to verify:

```text prediction interface
lineage
timestamp semantics
versioning
causal isolation
```

before model performance becomes a confounding variable.

---

# 25. Prediction Tests

Verify:

```text same features → same prediction
same model version → reproducible output
different model version → distinct lineage
future features → rejected.
```

---

# 26. Phase Seven — Economic Engine

Implement the economic layer independently from prediction.

Inputs:

```text Prediction
MarketState
Instrument
ExecutionEstimate
```

Output:

```text EconomicEvaluation.
```

---

# 27. Economic Tests

Test:

```text gross value
execution cost
net value
eligibility
threshold boundaries
cost sensitivity.
```

---

# 28. Economic Adversarial Test

Increase costs while holding everything else constant.

Expected behavior:

```text ExpectedNetValue cannot improve.
```

If it improves, the economic model is defective.

---

# 29. Phase Eight — Option Selection

Implement:

```text CandidateGenerator
OptionScorer
OptionSelector
OptionSelection
```

---

# 30. Option Selection Tests

Attack:

```text expired contract
invalid strike
zero liquidity
wide spread
missing quote
duplicate candidate
wrong option type
invalid lot size.
```

---

# 31. Phase Nine — Risk Engine

Implement:

```text RiskState
RiskPolicy
RiskAuthorization
RiskConstraint
RiskViolation.
```

This phase is particularly important because of the previously discovered separation:

```text dynamic mode
≠
dynamic risk.
```

---

# 32. Risk Engine Principle

The risk engine receives an economic opportunity.

It independently determines whether exposure is authorized.

Conceptually:

```text EconomicEvaluation
        +
RiskState
        +
RiskPolicy
        ↓
RiskAuthorization
```

---

# 33. Risk Attack Suite

Attempt:

```text profit → risk increase
mode → risk increase
prediction probability → risk increase
better fill → risk increase
partial exit → risk increase
```

All must fail unless explicitly authorized by the risk policy.

---

# 34. Phase Ten — Position Sizing

Implement:

```text RiskAuthorization
+
Instrument
+
ExecutionConstraints
→
AuthorizedQuantity.
```

---

# 35. Position Sizing Tests

Verify:

```text lot rounding
risk bounds
quantity bounds
zero-risk cases
insufficient capital
maximum position constraints.
```

---

# 36. Phase Eleven — Execution Simulator

This is the first environment capable of producing actual fills.

Implement:

```text SimulatedExecutionGateway
SlippageModel
LatencyModel
PartialFillModel
SpreadModel
ExecutionFailureModel.
```

---

# 37. Execution Principle

The simulator must be adversarial enough to destroy false profitability.

At minimum model:

```text spread
slippage
latency
partial fills
missed fills
rejections
gaps.
```

---

# 38. Execution Tests

Test:

```text full fill
partial fill
zero fill
delayed fill
rejected order
cancelled order
price movement during latency
spread expansion.
```

---

# 39. Phase Twelve — Position Ledger

Implement the authoritative position system.

```text FillEvent
    ↓
PositionLedger
    ↓
PositionTransition
```

---

# 40. Position Tests

Verify:

```text entry
partial entry
additional entry
partial exit
full exit
duplicate fill
invalid fill
over-exit
position closure.
```

---

# 41. Position Conservation Test

For every synthetic scenario:

```text finalPosition
=
Σ entries
-
Σ exits.
```

This must hold exactly under the canonical accounting convention.

---

# 42. Phase Thirteen — Accounting Engine

Implement:

```text RealizedPnL
UnrealizedPnL
CurrentPnL
PeakPnL
ProfitGiveback
Drawdown
Costs
TradeOutcome.
```

---

# 43. Accounting Must Use Actual Execution

Never:

```text theoretical entry price
theoretical exit price
midpoint
signal price
```

unless explicitly defined as a separate analytical metric.

Actual accounting uses authoritative fills.

---

# 44. Accounting Attack Suite

Test:

```text favorable slippage
adverse slippage
partial fills
fees
overnight boundaries
gaps
multiple entries
multiple exits.
```

---

# 45. Phase Fourteen — End-to-End Execution Path

Now connect:

```text MarketEvent
→ State
→ Feature
→ Prediction
→ Economics
→ Selection
→ Risk
→ Sizing
→ Order
→ Fill
→ Position
→ Accounting.
```

This becomes the first complete vertical slice.

---

# 46. Golden Scenario

Create deterministic golden scenarios.

Example:

```text initial capital
known market events
known prediction
known risk policy
known execution model
known fills
known P&L.
```

The final result becomes a regression fixture.

---

# 47. Golden Scenario Purpose

The system must reproduce exactly:

```text decision lineage
quantity
orders
fills
position
P&L.
```

If a refactor changes the result unexpectedly:

```text CI FAILURE.
```

---

# 48. Phase Fifteen — Adversarial Verification

Now attack the complete vertical slice.

Use:

```text future leakage
state corruption
stale data
duplicate events
duplicate fills
execution manipulation
risk manipulation
cost inflation
spread explosion
volatility shock
gap.
```

---

# 49. Metamorphic Tests

These are especially important.

A metamorphic test changes an input in a way that should have a predictable effect.

Examples:

```text costs ↑
→ expected net value should not ↑

slippage ↑
→ net P&L should not systematically improve

risk budget ↓
→ authorized quantity should not ↑

lot size ↑
→ executable quantity should not violate lot constraints.
```

---

# 50. Phase Sixteen — Strategy Implementation

Only now do we implement the actual predictive/trading strategy.

The strategy consumes the already-validated:

```text state
features
prediction
economics
option selection
risk
sizing.
```

It should contain very little infrastructure code.

---

# 51. Strategy Boundary

The strategy's conceptual responsibility is:

```text given canonical state,
produce canonical opportunity evaluation.
```

It does not:

```text talk to broker
write database rows
calculate accounting
mutate risk state.
```

---

# 52. Phase Seventeen — Backtester

Build the backtester using:

```text historical event stream
same StateEngine
same FeatureEngine
same PredictionEngine
same EconomicEngine
same OptionSelector
same RiskEngine
same PositionSizer
same AccountingEngine
```

Only:

```text market source
execution environment
clock
```

are simulation-specific.

---

# 53. Backtest Equivalence Test

Run identical synthetic scenarios through:

```text live-style runtime
simulation runtime.
```

Where the external environment is held equivalent, the domain outputs must match.

---

# 54. Phase Eighteen — Research Infrastructure

Implement:

```text DatasetRegistry
ExperimentRegistry
ParameterRegistry
ModelRegistry
RunRegistry
LineageStore.
```

---

# 55. Research Immutability

Every research run records:

```text code version
dataset version
model version
parameter version
protocol version
environment version
random seed.
```

---

# 56. Phase Nineteen — Statistical Validation

Implement:

```text walk-forward evaluation
calibration
confidence intervals
distribution analysis
baseline comparisons
ablation tests
multiple-testing accounting.
```

---

# 57. Walk-Forward Requirement

The model must be evaluated chronologically.

No future observations may influence training or parameter selection for an earlier test period.

---

# 58. Phase Twenty — Economic Validation

Test:

```text gross edge
net edge
cost sensitivity
slippage sensitivity
spread sensitivity
latency sensitivity
break-even cost.
```

A predictive edge that disappears under realistic costs is rejected.

---

# 59. Phase Twenty-One — Execution Validation

Evaluate:

```text fill assumptions
partial fills
latency
slippage
liquidity
order rejection
market gaps.
```

The purpose is to determine whether the predictive edge survives implementation.

---

# 60. Phase Twenty-Two — Risk Validation

Verify:

```text maximum loss
risk budget
position limits
loss streak behavior
drawdown behavior
risk-state transitions
halt behavior
recovery behavior.
```

---

# 61. Phase Twenty-Three — Adversarial Validation

Run the complete hostile test suite against the candidate.

The candidate must survive:

```text causal attacks
state attacks
execution attacks
economic attacks
risk attacks
data attacks
parameter attacks.
```

---

# 62. Phase Twenty-Four — Model Promotion

Only a validated candidate can enter:

```text APPROVED.
```

Promotion requires:

```text validation report
dataset lineage
code version
model version
parameter version
risk compatibility
execution compatibility
specification compatibility.
```

---

# 63. Phase Twenty-Five — TrueData Adapter

Only after the canonical engine works on deterministic synthetic/historical events should the external provider be connected.

Implement:

```text TrueDataConnection
TrueDataDecoder
TrueDataMapper
TrueDataReconnection
TrueDataHealthMonitor.
```

---

# 64. TrueData Boundary

The adapter converts:

```text TrueData messages
```

into:

```text canonical MarketEvents.
```

Nothing above this layer knows TrueData exists.

---

# 65. TrueData Verification

Before production use, verify:

```text timestamps
sequence semantics
duplicates
disconnects
reconnects
depth behavior
quote updates
trade updates
instrument metadata
market-session behavior.
```

---

# 66. Phase Twenty-Six — Paper Execution

Connect the canonical runtime to a paper execution environment.

The strategy remains unchanged.

Only:

```text ExecutionGateway
```

changes.

---

# 67. Paper Validation

Compare:

```text expected state
actual market state
expected orders
actual orders
expected fills
actual fills
expected accounting
actual accounting.
```

---

# 68. Phase Twenty-Seven — Live Runtime

Only after paper validation passes:

```text live data
+
live execution
```

becomes permitted.

---

# 69. Live Safety Controls

The live runtime requires independent controls for:

```text maximum position
maximum loss
maximum order quantity
maximum daily loss
data staleness
connection failure
execution failure
risk-state failure
reconciliation failure.
```

---

# 70. Live Reconciliation

Before allowing new exposure:

```text broker state
=
internal position state
```

must be reconciled.

If reconciliation fails:

```text no new exposure.
```

---

# 71. Phase Twenty-Eight — Production Monitoring

Monitor:

```text data health
state health
decision frequency
prediction distribution
execution quality
slippage
fill rate
risk usage
P&L
drawdown
reconciliation
system latency.
```

---

# 72. Monitoring Is Not Strategy Adaptation

Monitoring detects abnormal conditions.

It does not silently alter:

```text model
parameters
risk
strategy logic.
```

Adaptive behavior requires a separately validated mechanism.

---

# 73. Implementation Gate Model

Each phase has:

```text implementation
tests
adversarial tests
review
gate.
```

No phase advances merely because the code compiles.

---

# 74. Gate Definition

A phase is complete only when:

```text Functional correctness
+
Invariant correctness
+
Causal correctness
+
Regression coverage
```

pass.

---

# 75. Failure Policy

If a phase fails:

```text STOP.
```

Do not continue to the next layer while compensating for the failure elsewhere.

---

# 76. Critical Build Order

The final sequence is:

```text 01 Repository
02 Primitive Types
03 Events
04 Instruments
05 State Machine
06 Features
07 Prediction Contract
08 Economics
09 Option Selection
10 Risk
11 Position Sizing
12 Execution Simulation
13 Position Ledger
14 Accounting
15 End-to-End Runtime
16 Adversarial Verification
17 Strategy
18 Backtester
19 Research Infrastructure
20 Statistical Validation
21 Economic Validation
22 Execution Validation
23 Risk Validation
24 Adversarial Validation
25 Model Promotion
26 TrueData
27 Paper Trading
28 Live Runtime
29 Monitoring
```

---

# 77. Important Architectural Decision

The actual predictive model is deliberately late in the build sequence.

This is intentional.

If the system cannot correctly answer:

```text What happened?
What was knowable?
What state existed?
What order was requested?
What actually filled?
What risk was authorized?
What P&L resulted?
```

then model sophistication is irrelevant.

---

# 78. First Vertical Slice

The first implementation milestone is not:

```text profitable strategy.
```

It is:

```text deterministic event
→
state transition
→
feature snapshot
→
prediction
→
economic evaluation
→
risk authorization
→
order
→
fill
→
position
→
accounting
```

with a fully reproducible result.

---

# 79. First Production-Quality Invariant

The first critical invariant is:

```text Same canonical inputs
+
Same versions
+
Same configuration
=
Same output.
```

If this fails, research reproducibility is compromised.

---

# 80. Second Critical Invariant

The second is:

```text No information unavailable at time t
can influence a decision at t.
```

This is the fundamental anti-lookahead constraint.

---

# 81. Third Critical Invariant

The third is:

```text Actual position
=
authoritative fills.
```

Not:

```text signals
orders
intent
theoretical fills.
```

---

# 82. Fourth Critical Invariant

The fourth is:

```text AuthorizedRisk
cannot be increased by downstream execution/accounting events.
```

This preserves the separation we identified during adversarial analysis.

---

# 83. Fifth Critical Invariant

The fifth is:

```text Backtest semantics
=
Production strategy semantics.
```

Only the environment differs.

---

# 84. Implementation Readiness

We now have:

```text specification
architecture
variable registry
interfaces
domain schemas
dependency audit
implementation sequence.
```

The system is ready for scaffolding.

---

# 85. Next Artifact

The next artifact is:

# CANONICAL REPOSITORY SCAFFOLD SPECIFICATION

It will specify the actual files to create, including:

```text exact paths
file ownership
initial interfaces
initial types
initial test files
architecture checks
configuration files
CI checks
README structure
VERSION structure
```

The important distinction is that this will still be a **scaffold specification**, not premature strategy implementation.

Once that artifact is approved, the repository can be created deterministically from the specification.