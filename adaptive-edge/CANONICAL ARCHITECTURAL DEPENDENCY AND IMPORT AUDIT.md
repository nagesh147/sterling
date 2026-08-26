# CANONICAL ARCHITECTURAL DEPENDENCY AND IMPORT AUDIT

Version 1.0

## 1. Purpose

This audit attempts to violate the architecture deliberately.

The objective is not to confirm that the repository looks clean.

The objective is to determine whether the architecture prevents these failures:

```text
future information entering past decisions
risk being modified downstream
provider details leaking into domain logic
backtest semantics diverging from live semantics
accounting influencing decisions
research mutating production
execution inventing financial state
multiple modules owning the same concept
```

A clean directory tree is insufficient.

The dependency graph must enforce the specification.

---

# 2. Audit Principle

For every dependency, ask:

```text
Who owns this concept?
Why does the consumer need it?
When does the information become available?
Can the dependency create a causal violation?
Can the dependency mutate authoritative state?
Can the dependency be replaced?
```

If the answer is unclear, the dependency is rejected.

---

# 3. Canonical Dependency Graph

The intended high-level graph is:

```text
                    ┌─────────────────────┐
                    │   Infrastructure    │
                    └──────────┬──────────┘
                               │ implements
                               ↓
                    ┌─────────────────────┐
                    │     Interfaces      │
                    └──────────┬──────────┘
                               │
                               ↓
                    ┌─────────────────────┐
                    │    Application      │
                    └──────────┬──────────┘
                               │
                               ↓
                    ┌─────────────────────┐
                    │       Domain        │
                    └─────────────────────┘
```

Research and simulation operate through the same domain contracts rather than creating alternate semantics.

---

# 4. More Precise Direction

The practical dependency direction is:

```text
Infrastructure
      ↓
Application
      ↓
Domain
```

with dependency inversion:

```text Application/Domain
       ↑
   Interfaces
       ↑
Infrastructure
```

The concrete infrastructure implementation depends on the abstraction.

The domain does not depend on the concrete infrastructure.

---

# 5. Attack One: Domain → TrueData

Attempt:

```text domain/market/
    import TrueDataQuote
```

Result:

```text REJECTED.
```

Reason:

The domain must represent canonical market information, not provider-specific information.

Required dependency:

```text TrueData
    ↓
TrueDataAdapter
    ↓
CanonicalQuoteEvent
    ↓
Domain
```

---

# 6. Attack Two: Domain → SQLite

Attempt:

```text domain/accounting/
    import sqlite3
```

Result:

```text REJECTED.
```

Accounting semantics must remain independent of persistence technology.

Required:

```text AccountingDomain
       ↓
Repository Interface
       ↑
SQLiteRepository
```

---

# 7. Attack Three: Feature → Future Label

Attempt:

```text FeatureEngine
    ↓
HistoricalLabel
```

Result:

```text HARD REJECTION.
```

A historical label contains future-derived information.

It may flow:

```text HistoricalLabel
    ↓
Training / Validation
```

but never:

```text HistoricalLabel
    ↓
LiveFeature
```

---

# 8. Attack Four: Prediction → P&L

Attempt:

```text PredictionEngine
    ↓
AccountingSnapshot
```

Result:

```text REJECTED.
```

Prediction must occur before the resulting trade outcome.

Correct direction:

```text Prediction
    ↓
EconomicEvaluation
    ↓
Risk
    ↓
Execution
    ↓
Accounting
```

---

# 9. Attack Five: Accounting → Decision

Attempt:

```text DecisionEngine
    ↑
CurrentPnL
```

Result:

```text REJECTED for same-event causal execution.
```

Historical performance may be consumed by research under explicit temporal controls.

The live decision path cannot inspect its own future outcome.

---

# 10. Attack Six: Performance → Risk Expansion

Attempt:

```text PerformanceEngine
    ↓
RiskEngine
```

Result:

```text REJECTED by baseline architecture.
```

Performance is downstream evidence.

It cannot autonomously increase risk authorization.

---

# 11. Attack Seven: Risk → Prediction

Attempt:

```text PredictionEngine
    ↑
RiskState
```

Result:

```text REJECTED.
```

The predictor should not know whether the trade is currently allowed.

Otherwise the predictive model can become contaminated by portfolio state.

The correct architecture is:

```text Prediction
    ↓
Economic Evaluation
    ↓
Risk Authorization
```

---

# 12. Attack Eight: Execution → Risk Authorization

Attempt:

```text ExecutionEngine
    ↓
increase AuthorizedRisk
```

Result:

```text HARD REJECTION.
```

Execution may report:

```text actual fill
partial fill
slippage
rejection
failure.
```

It cannot manufacture additional authorization.

---

# 13. Attack Nine: Position → New Risk

Attempt:

```text PositionLedger
    ↓
increase RiskAuthorization
```

Result:

```text REJECTED.
```

Position state is an observed consequence of execution.

Risk authorization precedes exposure.

---

# 14. Attack Ten: Order → Position

Attempt:

```text OrderSubmitted
    ↓
PositionCreated
```

Result:

```text REJECTED.
```

Correct:

```text Order
    ↓
FillEvent
    ↓
PositionTransition
```

---

# 15. Attack Eleven: Order Status → Accounting

Attempt:

```text Order.status = FILLED
    ↓
RealizedPnL
```

Result:

```text REJECTED.
```

Accounting must use authoritative fills.

Order status is not sufficient financial evidence.

---

# 16. Attack Twelve: Fill → Prediction

Attempt:

```text FillEvent
    ↓
modify prediction
```

Result:

```text REJECTED.
```

The fill is downstream of the prediction.

A completed fill cannot retroactively alter the prediction that caused it.

---

# 17. Attack Thirteen: Backtester → Special Strategy Logic

Attempt:

```text Backtester
    ↓
BacktestOnlySignalCalculator
```

Result:

```text REJECTED.
```

The backtester must reuse the canonical strategy semantics.

It may provide:

```text historical event source
simulated clock
simulated execution.
```

It must not provide a second strategy implementation.

---

# 18. Attack Fourteen: Live Runtime → Backtester

Attempt:

```text LiveRuntime
    ↓
BacktestService
```

Result:

```text REJECTED.
```

Production execution should not depend on research infrastructure.

---

# 19. Attack Fifteen: Domain → Simulation

Attempt:

```text domain/execution/
    import SimulatedBroker
```

Result:

```text REJECTED.
```

Simulation is infrastructure/environment behavior.

Domain execution semantics remain canonical.

---

# 20. Attack Sixteen: Simulation → Alternate Domain Types

Attempt:

```text simulation/
    define SimulatedPosition
```

where `SimulatedPosition` duplicates the canonical `Position`.

Result:

```text REJECTED.
```

Simulation must use the canonical position model.

---

# 21. Attack Seventeen: Research → Production Mutation

Attempt:

```text ResearchRunner
    ↓
ProductionModelRegistry.update()
```

Result:

```text REJECTED.
```

Research produces a candidate.

Promotion is an explicit governed operation.

Correct:

```text Research
    ↓
Validation
    ↓
PromotionDecision
    ↓
ApprovedModel
    ↓
ProductionRegistry
```

---

# 22. Attack Eighteen: Validation → Candidate Mutation

Attempt:

```text ValidationEngine
    ↓
CandidateModel.setParameters(...)
```

Result:

```text REJECTED.
```

Validation must be observational.

The object being evaluated must remain unchanged.

---

# 23. Attack Nineteen: Validation → Production

Attempt:

```text ValidationEngine
    ↓
deploy()
```

Result:

```text REJECTED.
```

Validation produces evidence.

Promotion is a separate controlled operation.

---

# 24. Attack Twenty: Model → Risk Policy

Attempt:

```text Model
    ↓
modify RiskPolicy
```

Result:

```text REJECTED.
```

A model can be an input to a risk policy.

It cannot mutate the policy itself.

---

# 25. Attack Twenty-One: Prediction → Position Size

Attempt:

```text PredictionProbability
    ↓
quantity = probability × constant
```

Result:

```text REJECTED unless explicitly defined by the approved sizing specification.
```

The architecture intentionally prevents:

```text prediction quality
    =
risk authorization.
```

This preserves the previously established separation between predictive state and dynamic risk.

---

# 26. Attack Twenty-Two: Mode → Risk Expansion

Attempt:

```text MarketMode = INTRADAY
    ↓
AuthorizedRisk *= 2
```

Result:

```text REJECTED.
```

Mode classification and risk authorization are separate concepts.

---

# 27. Attack Twenty-Three: Profit → Risk Expansion

Attempt:

```text PeakPnL increased
    ↓
AuthorizedRisk increased
```

Result:

```text REJECTED.
```

This is a direct architectural enforcement of the critical invariant:

```text predictive profit
!=
risk capacity.
```

---

# 28. Attack Twenty-Four: Dynamic Mode → Dynamic Risk

Attempt:

```text ModeTransition
    ↓
RiskPolicyMutation
```

Result:

```text REJECTED.
```

A mode transition may change strategy behavior only where explicitly authorized.

It cannot implicitly grant additional risk.

---

# 29. Attack Twenty-Five: Feature → Order

Attempt:

```text FeatureSnapshot
    ↓
OrderIntent
```

Result:

```text REJECTED.
```

Required intermediate decision chain:

```text Features
    ↓
Prediction
    ↓
Economics
    ↓
OptionSelection
    ↓
Risk
    ↓
Sizing
    ↓
OrderIntent
```

---

# 30. Attack Twenty-Six: Prediction → Order

Attempt:

```text Prediction
    ↓
OrderIntent
```

Result:

```text REJECTED.
```

Prediction is not authorization.

---

# 31. Attack Twenty-Seven: Economic Evaluation → Order

Attempt:

```text ExpectedNetValue > threshold
    ↓
OrderIntent
```

Result:

```text REJECTED.
```

Risk authorization must still occur.

---

# 32. Attack Twenty-Eight: Risk Authorization → Direct Broker Call

Attempt:

```text RiskEngine
    ↓
BrokerSDK.placeOrder()
```

Result:

```text REJECTED.
```

Risk authorizes.

Execution submits.

Correct:

```text RiskAuthorization
    ↓
PositionSizing
    ↓
OrderIntent
    ↓
ExecutionGateway
```

---

# 33. Attack Twenty-Nine: Repository → Domain Mutation

Attempt:

```text PositionRepository
    ↓
Position.changeQuantity(...)
```

Result:

```text REJECTED.
```

Repositories persist and retrieve authoritative state.

They do not decide domain transitions.

---

# 34. Attack Thirty: Reporting → State Mutation

Attempt:

```text PerformanceReport
    ↓
MarketState.update()
```

Result:

```text REJECTED.
```

Reporting is read-only.

---

# 35. Attack Thirty-One: Logging → Strategy Mutation

Attempt:

```text Logger
    ↓
RiskState
```

Result:

```text REJECTED.
```

Observability must be side-effect-free with respect to domain state.

---

# 36. Attack Thirty-Two: Configuration → Arbitrary Domain Mutation

Attempt:

```text config["risk"] = 1000000
    ↓
runtime silently accepts.
```

Result:

```text REJECTED.
```

Configuration must pass through:

```text schema validation
policy validation
version validation
environment validation.
```

---

# 37. Attack Thirty-Three: Environment Variable → Mathematical Constant

Attempt:

```text process.env.SOME_THRESHOLD
```

directly inside a formula.

Result:

```text REJECTED.
```

Canonical parameters must come through versioned configuration or model artifacts.

---

# 38. Attack Thirty-Four: Clock → Historical State Mutation

Attempt:

```text system clock
    ↓
historical replay timestamp
```

Result:

```text REJECTED.
```

Historical replay uses:

```text deterministic simulation clock.
```

---

# 39. Attack Thirty-Five: Randomness → Untracked Decision

Attempt:

```text Math.random()
```

inside a strategy calculation.

Result:

```text REJECTED.
```

Randomness must be injected and seeded.

---

# 40. Attack Thirty-Six: Data Correction → Historical Mutation

Attempt:

```text corrected market data
    ↓
overwrite original dataset.
```

Result:

```text REJECTED.
```

Correct behavior:

```text DatasetVersion N
DatasetVersion N+1
```

with lineage preserved.

---

# 41. Attack Thirty-Seven: New Model → Historical Result Mutation

Attempt:

```text ModelVersion 2
    ↓
rewrite ModelVersion 1 results.
```

Result:

```text REJECTED.
```

Historical research artifacts are immutable.

---

# 42. Attack Thirty-Eight: Parameter Optimization → Test Set

Attempt:

```text test-set performance
    ↓
parameter optimizer
```

Result:

```text REJECTED.
```

The holdout remains untouched.

---

# 43. Attack Thirty-Nine: Test Result → Parameter Search

Attempt:

```text final holdout result
    ↓
change parameters
```

Result:

```text RESEARCH PROTOCOL VIOLATION.
```

A new experiment must be created.

---

# 44. Attack Forty: Future Candle → Historical Feature

Attempt:

```text candle[t+1]
    ↓
feature[t]
```

Result:

```text HARD REJECTION.
```

The causality validator must detect:

```text source availability time > feature time.
```

---

# 45. Attack Forty-One: Future High/Low → Entry

Attempt:

```text futureHigh
futureLow
    ↓
entry decision.
```

Result:

```text HARD REJECTION.
```

---

# 46. Attack Forty-Two: MFE → Entry

Attempt:

```text MaximumFavorableExcursion
    ↓
entry rule.
```

Result:

```text HARD REJECTION.
```

MFE is a post-entry diagnostic.

---

# 47. Attack Forty-Three: Realized P&L → Historical Feature

Attempt:

```text completed trade P&L
    ↓
feature used to predict that trade.
```

Result:

```text HARD REJECTION.
```

---

# 48. Attack Forty-Four: Future Spread → Execution

Attempt:

```text future spread
    ↓
historical execution price.
```

Result:

```text HARD REJECTION.
```

Execution simulation can use only information available at the modeled execution point.

---

# 49. Attack Forty-Five: Future Liquidity → Position Size

Attempt:

```text future depth
    ↓
historical quantity selection.
```

Result:

```text HARD REJECTION.
```

---

# 50. Attack Forty-Six: Future Exit Price → Entry Risk

Attempt:

```text actual exit price
    ↓
initial risk.
```

Result:

```text HARD REJECTION.
```

Initial risk must be defined from information available when risk was authorized.

---

# 51. Attack Forty-Seven: Broker Fill → Historical Market State

Attempt:

```text actual fill
    ↓
modify market state retroactively.
```

Result:

```text REJECTED.
```

A strategy execution is an observation about execution, not a correction to historical market truth.

---

# 52. Attack Forty-Eight: Accounting → Market State

Attempt:

```text P&L
    ↓
MarketState
```

Result:

```text REJECTED.
```

Market state is externally observed/reconstructed.

Accounting is downstream.

---

# 53. Attack Forty-Nine: Position → Market State

Attempt:

```text current position
    ↓
rewrite market state.
```

Result:

```text REJECTED.
```

Portfolio state and market state are separate domains.

---

# 54. Attack Fifty: Multiple Owners

Attempt to define:

```text CurrentPnL
```

in:

```text accounting/
performance/
reporting/
```

as three independent calculations.

Result:

```text REJECTED.
```

Only Accounting owns the canonical calculation.

Performance and reporting consume it.

---

# 55. Attack Fifty-One: Duplicate Opening Range

Attempt:

```text StateEngine.OpeningRange
FeatureEngine.OpeningRange
Backtester.OpeningRange
```

with independent implementations.

Result:

```text REJECTED.
```

There is one canonical opening-range definition.

---

# 56. Attack Fifty-Two: Duplicate Risk Calculation

Attempt:

```text RiskEngine.calculateRisk()
ExecutionEngine.calculateRisk()
Backtester.calculateRisk()
```

as independent implementations.

Result:

```text REJECTED.
```

The Risk domain owns the canonical risk calculation.

---

# 57. Attack Fifty-Three: Duplicate Option Selection

Attempt:

```text live option selector
backtest option selector
research option selector
```

with subtly different rules.

Result:

```text REJECTED.
```

The same domain selection semantics must be reused.

---

# 58. Attack Fifty-Four: Research Shortcut

Attempt:

```text research script
    ↓
direct database SQL
    ↓
manually reconstruct P&L.
```

Result:

```text REJECTED as authoritative implementation.
```

Research may analyze stored results.

It cannot silently redefine accounting.

---

# 59. Attack Fifty-Five: Reporting Shortcut

Attempt:

```text report.calculatePnL()
```

independently of the Accounting domain.

Result:

```text REJECTED.
```

Reporting consumes canonical accounting results.

---

# 60. Attack Fifty-Six: Broker Shortcut

Attempt:

```text strategy
    ↓
broker.placeOrder()
```

Result:

```text REJECTED.
```

The strategy emits an `OrderIntent`.

The execution infrastructure decides how that intent is submitted.

---

# 61. Attack Fifty-Seven: Data Shortcut

Attempt:

```text strategy
    ↓
HTTP request to market-data API.
```

Result:

```text REJECTED.
```

All market data enters through the canonical event boundary.

---

# 62. Attack Fifty-Eight: Persistence Shortcut

Attempt:

```text risk engine
    ↓
database.update("risk", ...)
```

Result:

```text REJECTED.
```

Risk state changes through domain/application transitions.

Persistence observes/stores the result.

---

# 63. Attack Fifty-Nine: Global Mutable State

Attempt:

```text global currentPosition
global currentRisk
global currentPnL
```

Result:

```text REJECTED.
```

Authoritative state must have explicit ownership and lifecycle.

---

# 64. Attack Sixty: Hidden Singleton

Attempt:

```text global TradingEngine.instance
```

with mutable state shared across tests and runtime contexts.

Result:

```text REJECTED.
```

This would compromise:

```text determinism
test isolation
replayability
multi-session behavior.
```

---

# 65. Attack Sixty-One: Mutable Domain Event

Attempt:

```text FillEvent.price = modifiedPrice
```

after accounting.

Result:

```text REJECTED.
```

Events are immutable.

---

# 66. Attack Sixty-Two: Mutable Historical State

Attempt:

```text historical MarketState
```

modified after a later event.

Result:

```text REJECTED.
```

New state replaces it in the temporal chain.

The old state remains historical truth for its timestamp.

---

# 67. Attack Sixty-Three: Event Reordering for Profit

Attempt to reorder events because a different ordering produces better strategy results.

Result:

```text HARD REJECTION.
```

Ordering follows the canonical event contract.

---

# 68. Attack Sixty-Four: Missing Event Fabrication

Attempt:

```text missing quote
    ↓
invented quote
```

Result:

```text REJECTED.
```

Missing information must remain:

```text missing
unknown
invalid
```

according to the data policy.

---

# 69. Attack Sixty-Five: Stale Data Acceptance

Attempt:

```text stale quote
    ↓
new decision
```

Result:

```text REJECTED if beyond the configured validity window.
```

The data contract determines the exact threshold.

---

# 70. Attack Sixty-Six: Duplicate Event

Attempt to process the same event twice.

Expected:

```text no duplicate economic effect.
```

This must be enforced through event identity/idempotency.

---

# 71. Attack Sixty-Seven: Duplicate Fill

Attempt to process the same fill twice.

Expected:

```text Position changes once.
Accounting changes once.
```

---

# 72. Attack Sixty-Eight: Invalid Fill

Inject a fill referencing an unknown order.

Expected:

```text execution integrity failure.
```

The system must not silently create the order.

---

# 73. Attack Sixty-Nine: Impossible Position

Attempt:

```text CLOSED position
+
positive quantity.
```

Expected:

```text invariant failure.
```

---

# 74. Attack Seventy: Unauthorized Exit

Attempt to close a position using an invalid order intent.

Expected:

```text execution rejection.
```

---

# 75. Attack Seventy-One: Unauthorized Re-Entry

After:

```text session risk status = HALTED
```

inject a valid signal.

Expected:

```text no new order.
```

---

# 76. Attack Seventy-Two: Risk Reset Through Profit

Attempt:

```text large profit
    ↓
HALTED → ACTIVE.
```

Expected:

```text REJECTED.
```

A reset requires its explicit reset condition.

---

# 77. Attack Seventy-Three: Risk Reset Through Mode

Attempt:

```text mode change
    ↓
HALTED → ACTIVE.
```

Expected:

```text REJECTED.
```

---

# 78. Attack Seventy-Four: Risk Reset Through Time Alone

Attempt:

```text time advanced
    ↓
HALTED → ACTIVE
```

This is permitted only if the canonical risk policy explicitly defines time-based reset.

Otherwise:

```text REJECTED.
```

---

# 79. Attack Seventy-Five: Partial Fill Overrun

Request:

```text 10 lots.
```

Receive:

```text 4 lots.
```

Attempt to construct:

```text Position = 10 lots.
```

Expected:

```text REJECTED.
```

Position equals authoritative filled quantity.

---

# 80. Attack Seventy-Six: Slippage Erasure

Execution model reports:

```text expected price = 100
actual fill = 102.
```

Attempt:

```text accounting price = 100.
```

Expected:

```text REJECTED.
```

Accounting uses actual fill information.

---

# 81. Attack Seventy-Seven: Favorable Fill Fabrication

Simulation receives:

```text market ask = 102.
```

and creates:

```text fill = 100.
```

without a valid mechanism.

Expected:

```text execution-model invariant failure.
```

---

# 82. Attack Seventy-Eight: Cost Erasure

Actual fee:

```text 50.
```

Attempt:

```text netPnL = grossPnL.
```

Expected:

```text accounting invariant failure.
```

---

# 83. Attack Seventy-Nine: Peak P&L Decrease

Inject:

```text PeakPnL(t) = 100
PeakPnL(t+1) = 90.
```

Expected:

```text invariant failure.
```

---

# 84. Attack Eighty: Profit Giveback Manipulation

Inject:

```text PeakPnL = 100
CurrentPnL = 60
```

Attempt:

```text Giveback = 20.
```

Expected:

```text invariant failure.
```

---

# 85. Attack Eighty-One: Risk Increase Through Partial Exit

Attempt:

```text quantity decreases
risk authorization increases.
```

Expected:

```text REJECTED.
```

A reduction in exposure cannot implicitly create a larger authorization.

---

# 86. Attack Eighty-Two: Risk Increase Through Better Execution

Attempt:

```text favorable fill
    ↓
increase authorized risk.
```

Expected:

```text REJECTED.
```

Execution quality does not mutate policy.

---

# 87. Attack Eighty-Three: Risk Increase Through Higher Probability

Attempt:

```text probability 0.60 → 0.90
    ↓
risk 1R → 2R.
```

Expected:

```text REJECTED unless explicitly defined in the risk policy.
```

The baseline policy does not allow implicit scaling.

---

# 88. Attack Eighty-Four: Model Version Swap Mid-Trade

Attempt to change:

```text ModelVersion A
```

to:

```text ModelVersion B
```

without a new authorized decision.

Expected:

```text REJECTED.
```

The trade lineage retains the model version that generated the decision.

---

# 89. Attack Eighty-Five: Risk Policy Swap Mid-Authorization

Attempt to reinterpret an existing authorization under a newer risk policy.

Expected:

```text REJECTED.
```

The authorization records its governing policy version.

---

# 90. Attack Eighty-Six: Execution Model Swap Mid-Order

Attempt to change execution assumptions after order submission.

Expected:

```text REJECTED for historical execution reconstruction.
```

---

# 91. Attack Eighty-Seven: Accounting Version Swap

Attempt to calculate the same historical trade under a new accounting formula without versioning.

Expected:

```text REJECTED.
```

---

# 92. Attack Eighty-Eight: Research Result Without Dataset Version

Attempt to store:

```text Sharpe = X
```

without identifying the dataset.

Expected:

```text REJECTED.
```

Research results require lineage.

---

# 93. Attack Eighty-Nine: Model Without Training Dataset

Attempt to register a model without dataset lineage.

Expected:

```text REJECTED.
```

---

# 94. Attack Ninety: Promotion Without Validation

Attempt:

```text candidate model
    ↓
production.
```

without an approved validation report.

Expected:

```text REJECTED.
```

---

# 95. Attack Ninety-One: Validation Without Protocol

Attempt to claim:

```text validated = true
```

without identifying the validation protocol.

Expected:

```text REJECTED.
```

---

# 96. Attack Ninety-Two: Validation Result Without Code Version

Attempt to store a result without identifying the implementation/code version.

Expected:

```text REJECTED.
```

---

# 97. Attack Ninety-Three: Production Model Without Specification Version

Attempt to deploy a model without identifying the specification it implements.

Expected:

```text REJECTED.
```

---

# 98. Attack Ninety-Four: Incompatible Artifacts

Attempt:

```text ModelVersion A
FeatureVersion B
RiskPolicyVersion C
```

where the compatibility matrix rejects the combination.

Expected:

```text REJECTED.
```

---

# 99. Attack Ninety-Five: Hidden Parameter Mutation

Modify a parameter file after model approval without changing:

```text ParameterVersion.
```

Expected:

```text INTEGRITY FAILURE.
```

---

# 100. Attack Ninety-Six: Environment Drift

Production code version is correct but runtime dependencies differ from the approved environment.

Expected:

```text deployment validation failure.
```

---

# 101. Attack Ninety-Seven: Silent Provider Contract Change

Provider changes a field interpretation while keeping the same external field name.

Expected:

```text provider-contract validation or integration test failure.
```

The domain must remain unaffected.

---

# 102. Attack Ninety-Eight: Provider Replacement

Replace:

```text TrueDataAdapter
```

with:

```text AnotherMarketDataAdapter.
```

Expected:

```text domain code remains unchanged.
```

Only infrastructure composition and provider mapping should change.

---

# 103. Attack Ninety-Nine: Broker Replacement

Replace the execution provider.

Expected:

```text domain and strategy semantics remain unchanged.
```

Only execution infrastructure changes.

---

# 104. Attack One Hundred: Database Replacement

Replace:

```text SQLite
```

with another persistence implementation.

Expected:

```text domain semantics remain unchanged.
```

This verifies persistence isolation.

---

# 105. Architectural Verdict

After applying the attacks above, the architecture passes only if:

```text no forbidden dependency exists
no duplicated canonical calculation exists
no future-derived value crosses into live causal logic
no downstream module can increase risk
no external provider leaks into domain logic
no simulation-only semantics replace domain semantics
no research artifact can mutate production
no authoritative financial fact can be fabricated downstream.
```

---

# 106. Enforcement Mechanisms

Documentation alone is insufficient.

The following must be enforced mechanically where possible:

```text Type checking
Import rules
Dependency linting
Architecture tests
Schema validation
Runtime invariants
Property tests
Contract tests
CI checks
```

---

# 107. Architecture Tests

The repository must contain tests that fail if forbidden imports are introduced.

Examples:

```text domain → infrastructure       FAIL
domain → provider SDK             FAIL
domain → database                 FAIL
production → research             FAIL
strategy → broker SDK             FAIL
accounting → prediction           FAIL
```

---

# 108. Dependency Rule

The architecture test should operate on actual source dependencies, not developer intention.

If the code imports a forbidden module:

```text CI FAILURE.
```

---

# 109. Ownership Rule

The registry should be machine-checkable.

If two modules claim:

```text VariableID = VAR-PNL-003
```

then:

```text CI FAILURE.
```

---

# 110. Formula Rule

Canonical formulas should have identifiable owners.

If another module implements an equivalent formula independently:

```text architecture review required.
```

---

# 111. Causality Rule

Every feature and prediction must expose sufficient metadata for the causality validator to determine:

```text source timestamp
availability timestamp
decision timestamp.
```

---

# 112. Research Lineage Rule

Every research result must be traceable to:

```text code version
dataset version
parameter version
model version
protocol version.
```

---

# 113. Execution Lineage Rule

Every completed trade must be traceable:

```text Opportunity
    ↓
Decision
    ↓
RiskAuthorization
    ↓
OrderIntent
    ↓
Order
    ↓
Fill
    ↓
Position
    ↓
Accounting
    ↓
TradeOutcome
```

---

# 114. Architectural Safety Invariant

The most important dependency constraint is:

```text Future
  X
  |
  X
  ↓
Past Decision
```

The dependency graph must make this impossible.

---

# 115. Architectural Risk Invariant

The second critical constraint is:

```text Prediction
     ↓
Economic Value
     ↓
Risk Authorization
```

not:

```text Prediction
     ↓
Risk Increase
```

and never:

```text Profit
     ↓
Risk Increase
```

without an independently defined and approved risk-policy mechanism.

---

# 116. Architectural Accounting Invariant

Financial reality flows:

```text Order
    ↓
Fill
    ↓
Position
    ↓
Accounting
```

not:

```text Order
    ↓
Assumed Position
    ↓
Assumed P&L.
```

---

# 117. Architectural Research Invariant

Research flows:

```text Experiment
    ↓
Candidate
    ↓
Validation
    ↓
Promotion
    ↓
Production
```

Never:

```text Experiment
    ↓
Production.
```

---

# 118. Architectural Replay Invariant

A historical run must be reconstructable from:

```text DatasetVersion
+
EventSequence
+
ConfigurationVersion
+
ModelVersion
+
ExecutionModelVersion.
```

The result must not depend on:

```text current wall clock
current mutable configuration
current production model
unseeded randomness.
```

---

# 119. Final Audit Result

The architecture is now sufficiently constrained to proceed to implementation.

The remaining unknowns are implementation details, not architectural gaps.

The principal external-data unknown remains:

```text TrueData Provider Contract.
```

That affects the adapter implementation, not the domain architecture.

---

# 120. Architecture Freeze

At this point the following should be considered frozen:

```text Domain boundaries
Dependency direction
Variable ownership
Event ownership
State ownership
Risk separation
Accounting ownership
Research/production separation
Simulation boundary
Provider isolation
Repository architecture
```

Changes from this point onward require an explicit architecture revision.

---

# 121. Next Artifact

We can now move into the first actual engineering artifact:

# CANONICAL IMPLEMENTATION PLAN AND SCAFFOLDING ORDER

It will define exactly what gets built first, second, third, and so on.

The order will deliberately start with:

```text foundational types
        ↓
events
        ↓
state machine
        ↓
invariants
        ↓
feature contracts
        ↓
economic/risk contracts
        ↓
execution simulation
        ↓
accounting
        ↓
research/validation
        ↓
external-data adapter
        ↓
runtime composition
```

We will not start by writing the strategy loop. The strategy loop is one of the final orchestration pieces, not the foundation.