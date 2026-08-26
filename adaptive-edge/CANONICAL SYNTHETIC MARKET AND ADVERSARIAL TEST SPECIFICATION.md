# CANONICAL SYNTHETIC MARKET AND ADVERSARIAL TEST SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the formal verification environment for the strategy before implementation against real market data.

The test system must answer:

```text
Can the specification survive hostile inputs?
Can the state machine reach an impossible state?
Can future information leak backward?
Can risk increase unintentionally?
Can accounting become inconsistent?
Can execution create impossible fills?
Can the strategy exploit an artifact of the data?
```

The objective is not to make the strategy look profitable.

The objective is to make it fail safely and expose contradictions.

---

# 2. Formal Verification Principle

A synthetic test is successful when the system behaves exactly according to the canonical specification.

Therefore:

```text
Test Success
=
Expected State
+
Expected Transition
+
Expected Invariants
+
Expected Accounting
```

A scenario producing an unexpected profitable result is not necessarily a success.

A scenario producing an unexpected loss may be a success if the specification requires that loss.

---

# 3. Test Environment

The synthetic environment contains:

```text
SyntheticMarketGenerator
        ↓
CanonicalEventStream
        ↓
StateEngine
        ↓
FeatureEngine
        ↓
DecisionEngine
        ↓
RiskEngine
        ↓
ExecutionEngine
        ↓
PositionLedger
        ↓
AccountingEngine
        ↓
InvariantChecker
```

The test harness must be able to inspect every intermediate state.

---

# 4. Determinism

Every synthetic scenario must be reproducible from:

```text
ScenarioID
ScenarioVersion
InitialState
EventSequence
RandomSeed
ModelVersion
ParameterVersion
```

The same inputs must produce the same state transitions.

---

# 5. Scenario Identity

Every scenario receives:

```text
ScenarioID
```

Example:

```text
ADV-TREND-001
ADV-WHIPSAW-001
ADV-STALE-001
ADV-LEAK-001
```

The identifier is immutable.

---

# 6. Scenario Structure

Every scenario defines:

```text
InitialState
MarketEvents
ExpectedTransitions
ExpectedDecisions
ExpectedRiskState
ExpectedExecutionState
ExpectedPositionState
ExpectedAccountingState
ExpectedInvariantResults
```

---

# 7. Scenario Categories

The canonical adversarial suite contains:

```text
Market Behavior
Data Integrity
Execution
Risk
State Machine
Accounting
Statistical Leakage
Parameter Robustness
Operational Failure
```

---

# 8. Scenario A: Clean Trend

Purpose:

```text Verify normal operation. 
```

Synthetic sequence:

```text Opening Range
    ↓
Breakout
    ↓
Continuation
    ↓
Profit Development
    ↓
Trailing Protection
    ↓
Exit
```

Expected behavior:

```text valid entry
valid risk authorization
valid position
valid management transitions
valid exit
valid P&L.
```

---

# 9. Scenario B: False Breakout

Market behavior:

```text Opening Range
    ↓
Breakout
    ↓
Entry
    ↓
Immediate reversal
    ↓
Protection
    ↓
Exit
```

Expected behavior:

```text trade may lose.
```

This is a legitimate strategy loss.

The test succeeds if:

```text loss <= defined execution/risk behavior
```

and:

```text no impossible state occurs.
```

---

# 10. Scenario C: Whipsaw

Market alternates rapidly:

```text UP
DOWN
UP
DOWN
UP
DOWN
```

Purpose:

```text expose excessive re-entry
mode instability
signal oscillation
risk accumulation.
```

Expected behavior depends on the canonical concurrency and cooldown rules.

The system must never create unintended exposure.

---

# 11. Scenario D: Strong Trend

Market continuously moves in the predicted direction.

Purpose:

```text verify continuation logic
verify trailing behavior
verify profit protection
```

Critical invariant:

```text increasing profit
!=
increasing authorized risk.
```

---

# 12. Scenario E: Strong Trend Followed by Violent Reversal

Sequence:

```text Entry
    ↓
Large profit
    ↓
PeakPnL increases
    ↓
Rapid reversal
    ↓
Trailing/protection
    ↓
Exit
```

Expected:

```text PeakPnL remains monotonic.
```

and:

```text ProfitGiveback increases.
```

But:

```text AuthorizedRisk does not increase.
```

---

# 13. Scenario F: Gap Through Protection

Sequence:

```text Position active
    ↓
Protection = P
    ↓
Market jumps through P
    ↓
Next executable price is materially worse
```

Expected:

```text ActualLoss > nominal protection loss
```

may occur.

This must be classified as:

```text execution/gap risk
```

rather than a mathematical accounting error.

---

# 14. Scenario G: Volatility Explosion

Market volatility suddenly increases.

Purpose:

```text test feature/state transitions
test probability response
test option behavior
test execution costs
test risk separation.
```

Critical requirement:

```text volatility increase
```

must not automatically imply:

```text increased position size.
```

---

# 15. Scenario H: Volatility Collapse

Market becomes extremely quiet.

Expected behavior may be:

```text no entry
or reduced economic attractiveness.
```

The strategy must not manufacture trades merely to maintain activity.

---

# 16. Scenario I: Spread Explosion

Before entry:

```text Bid = B
Ask = A
```

Then:

```text Ask - Bid
```

expands dramatically.

Expected behavior:

```text execution cost increases.
```

If economic value falls below the required threshold:

```text trade must be rejected.
```

The strategy cannot use the old spread to justify the trade.

---

# 17. Scenario J: Liquidity Collapse

Available depth suddenly decreases.

Expected behavior:

```text position size may become infeasible.
```

The execution engine must:

```text reduce quantity
or
reject the order.
```

It must never assume unlimited liquidity.

---

# 18. Scenario K: Partial Fill

Requested:

```text Q = 10 lots
```

Available executable quantity:

```text Q = 4 lots.
```

Expected:

```text FilledQuantity = 4
RemainingQuantity = 6
```

Position quantity must equal:

```text 4
```

not:

```text 10.
```

---

# 19. Scenario L: Multi-Level Fill

Synthetic order book:

```text Ask 1: price P1, quantity Q1
Ask 2: price P2, quantity Q2
Ask 3: price P3, quantity Q3
```

Order quantity exceeds `Q1`.

Expected:

```text multiple fills
```

and:

```text VWAP
```

must be calculated correctly.

---

# 20. Scenario M: Stale Quote

Quote timestamp:

```text T0
```

Decision/execution timestamp:

```text T1
```

where:

```text T1 - T0 > MaximumAllowedQuoteAge.
```

Expected:

```text quote = invalid for execution.
```

The system must not generate a fill from that quote.

---

# 21. Scenario N: Out-of-Order Events

Synthetic stream:

```text Event 1: T=100
Event 2: T=102
Event 3: T=101
```

Expected:

```text deterministic ordering policy
```

must be applied.

If the provider contract requires strict ordering and the stream violates it:

```text DATA_INTEGRITY_FAILURE.
```

The system must not silently reorder events unless the specification explicitly permits it.

---

# 22. Scenario O: Duplicate Event

Input:

```text EventID = X
EventID = X
```

Expected:

```text process X once.
```

The duplicate must not:

```text double update state
double count volume
double count P&L
double trigger a signal.
```

---

# 23. Scenario P: Missing Event

Suppose a required market event disappears.

Expected behavior depends on the state requirement.

If the missing event prevents reliable state reconstruction:

```text StateValidity = INVALID.
```

The system must not fabricate the missing value.

---

# 24. Scenario Q: Timestamp Collision

Multiple events share the same timestamp.

The system must apply the canonical event-ordering rule.

If ordering cannot be established:

```text ambiguity must be explicitly represented.
```

The engine must not select whichever ordering produces the better backtest result.

---

# 25. Scenario R: Future-Leak Injection

Inject a future variable into the environment:

```text FuturePrice
FutureMaximum
FutureOutcome
```

before the decision.

The leakage detector must identify the illegal dependency.

Expected:

```text VALIDATION_FAILURE.
```

---

# 26. Scenario S: Label Leakage

Construct a feature using:

```text outcome after horizon H.
```

The dependency audit must detect:

```text FeatureTime > DecisionTime.
```

Expected:

```text REJECT.
```

---

# 27. Scenario T: Calibration Leakage

Allow a calibration model to observe outcomes from the test period.

Expected:

```text validation failure.
```

Calibration must only consume observations permitted by the temporal training protocol.

---

# 28. Scenario U: Execution Leakage

Provide the execution model with:

```text actual future fill price.
```

before execution.

Expected:

```text execution model rejection.
```

The model cannot know its future fill.

---

# 29. Scenario V: P&L Leakage

Provide:

```text future trade P&L
```

to the decision engine.

Expected:

```text dependency violation.
```

The architecture must prevent:

```text P&L → Decision
```

for the same historical event.

---

# 30. Scenario W: Profit-Driven Risk Expansion

Sequence:

```text InitialRisk = R
Trade becomes profitable
PeakPnL increases significantly
```

Attempt:

```text AuthorizedRisk = 2R.
```

Expected:

```text REJECT.
```

This directly verifies the previously established invariant:

```text profit cannot automatically create risk capacity.
```

---

# 31. Scenario X: Mode-Driven Risk Expansion

Sequence:

```text Mode = INITIAL
Risk = R
```

Then:

```text Mode = INTRADAY
```

Attempt:

```text Risk = 2R.
```

Expected:

```text REJECT.
```

Mode and risk remain independent.

---

# 32. Scenario Y: Probability-Driven Risk Expansion

Sequence:

```text Probability = 0.60
Risk = R
```

Then:

```text Probability = 0.85.
```

Attempt:

```text Risk = 2R.
```

Expected:

```text REJECT.
```

Prediction quality does not directly authorize additional risk.

---

# 33. Scenario Z: Protection Loosening

Current protection:

```text P1.
```

Attempt to replace it with a less favorable:

```text P2.
```

where:

```text P2 < P1
```

under the canonical long-position protection convention.

Expected:

```text transition rejected.
```

---

# 34. Scenario AA: Partial Exit

Initial:

```text Quantity = Q.
```

Exit:

```text Quantity = Q/2.
```

Expected:

```text remaining quantity = Q/2.
```

Risk must be recalculated downward or remain appropriately bounded.

It cannot increase.

---

# 35. Scenario AB: Duplicate Fill

Submit identical:

```text FillID = F.
```

twice.

Expected:

```text Position updated once.
```

Accounting must remain conserved.

---

# 36. Scenario AC: Fill Without Order

Inject:

```text FillEvent
```

with no corresponding valid order.

Expected:

```text execution integrity failure.
```

The position must not silently accept the fill.

---

# 37. Scenario AD: Exit Before Entry

Inject:

```text EXIT
```

before any valid:

```text ENTRY.
```

Expected:

```text impossible state.
```

This is a hard state-machine failure.

---

# 38. Scenario AE: Position Without Fill

Attempt:

```text PositionQuantity > 0
```

without any authoritative fill.

Expected:

```text impossible state.
```

---

# 39. Scenario AF: Negative Quantity

Attempt:

```text Quantity < 0
```

in a long-only position model.

Expected:

```text invariant violation.
```

---

# 40. Scenario AG: Risk Above Authorization

Create:

```text AuthorizedRisk = R
```

then force:

```text ActualModeledRisk > R.
```

Expected:

```text RISK_BREACH.
```

The system must not modify `AuthorizedRisk` to hide the breach.

---

# 41. Scenario AH: Session Lockout Bypass

Set:

```text SessionRiskStatus = HALTED.
```

Then inject a valid-looking entry signal.

Expected:

```text NO_ENTRY.
```

---

# 42. Scenario AI: Lockout Reset Attack

Set:

```text HALTED.
```

Then modify:

```text probability
market regime
profit expectation.
```

Expected:

```text HALTED remains HALTED.
```

until the explicit reset condition occurs.

---

# 43. Scenario AJ: Failed Exit

Active position:

```text Q > 0.
```

Exit order is rejected.

Expected:

```text Position remains active.
ExitObligation remains TRUE.
```

No false closure is recorded.

---

# 44. Scenario AK: Reconciliation Failure

Internal ledger:

```text Q = 2.
```

Broker/external authoritative state:

```text Q = 1.
```

Expected:

```text RECONCILIATION_REQUIRED.
```

New exposure is prohibited.

---

# 45. Scenario AL: Accounting Conservation

Create:

```text Entry fills
Partial exits
Final exit
```

Verify:

```text EntryQuantity - ExitQuantity = FinalPositionQuantity.
```

and:

```text TotalTradePnL
=
sum of accounting components.
```

---

# 46. Scenario AM: P&L Conservation

For all completed trades:

```text StrategyNetPnL
=
Σ TradeNetPnL
```

subject only to explicitly defined account-level adjustments.

Any unexplained difference is:

```text ACCOUNTING_FAILURE.
```

---

# 47. Scenario AN: Peak P&L Monotonicity

Generate:

```text PnL:
0
+10
+20
+15
+25
+5
```

Expected:

```text PeakPnL:
0
10
20
20
25
25
```

Peak P&L can never decrease.

---

# 48. Scenario AO: Giveback

If:

```text PeakPnL = 100
CurrentPnL = 60
```

then:

```text Giveback = 40.
```

Giveback is not:

```text RealizedLoss = 40.
```

The accounting system must preserve this distinction.

---

# 49. Scenario AP: Unrealized-to-Realized Transition

Position reaches:

```text UnrealizedPnL = +100.
```

Then exits at:

```text +60.
```

Expected:

```text PeakPnL = +100
RealizedPnL = +60
Giveback = +40
```

assuming the accounting convention defines these values accordingly.

---

# 50. Scenario AQ: Counterfactual Contamination

Calculate:

```text MFE
```

for a completed trade.

Attempt to feed MFE into the original entry decision.

Expected:

```text dependency violation.
```

MFE is post-entry information.

---

# 51. Scenario AR: Expected Holding Time Confusion

Create:

```text ExpectedHoldingTime
LabelHorizon
ActualHoldingTime.
```

Ensure they remain separate.

No system component may silently substitute one for another.

---

# 52. Scenario AS: Duplicate Variable Definition

Attempt to register:

```text CurrentPnL
```

and:

```text CurrentProfit
```

with identical semantics.

Canonical registry should reject the duplicate semantic definition.

One canonical variable must remain.

---

# 53. Scenario AT: Circular Dependency

Construct:

```text A → B
B → C
C → A
```

The dependency validator must reject the graph.

---

# 54. Temporal DAG Validation

The validator must distinguish:

```text static dependency
```

from:

```text temporal dependency.
```

A variable may legitimately depend on a previous state without creating a circular dependency.

---

# 55. Temporal Causality Rule

For decision time `t`:

```text Any decision input must satisfy:
SourceTime <= t.
```

For a transition:

```text State_(t+1)
```

may depend on:

```text State_t
+
Events occurring between t and t+1.
```

It may not depend on:

```text State_(t+2).
```

---

# 56. Scenario AU: State Replay

Given identical:

```text initial state
event sequence
versions
```

replaying the scenario must produce identical:

```text states
decisions
orders
fills
P&L.
```

---

# 57. Scenario AV: State Snapshot Recovery

Save state at:

```text T = 100.
```

Resume from the snapshot and process remaining events.

The final result must equal:

```text uninterrupted replay.
```

---

# 58. Scenario AW: Restart During Active Position

Restart the system while:

```text PositionQuantity > 0.
```

After recovery:

```text position
risk
protection
P&L
state
```

must be reconstructed consistently.

---

# 59. Scenario AX: Restart During Pending Order

Restart while:

```text OrderStatus = PARTIALLY_FILLED.
```

The system must recover:

```text filled quantity
remaining quantity
order state.
```

No duplicate fill may occur.

---

# 60. Scenario AY: Extreme Price

Inject an extreme but valid market price.

The system must remain numerically stable.

Expected:

```text no overflow
no NaN
no invalid negative price
```

where the instrument contract prohibits negative prices.

---

# 61. Scenario AZ: Zero / Missing Market Fields

Inject missing:

```text bid
ask
volume
depth
```

where each is required.

The system must either:

```text reject the state
```

or:

```text transition according to the explicit missing-data policy.
```

It must not substitute arbitrary values.

---

# 62. Scenario BA: Option Contract Mismatch

Attempt to execute:

```text Option A
```

using market data belonging to:

```text Option B.
```

Expected:

```text instrument identity failure.
```

---

# 63. Scenario BB: Expired Instrument

Attempt to trade an expired option.

Expected:

```text execution rejection.
```

---

# 64. Scenario BC: Contract-Size Change

If contract metadata changes:

```text LotSize_t != LotSize_(t-1)
```

the system must use the applicable historical contract specification.

It must not assume today's lot size for historical data.

---

# 65. Scenario BD: Split / Corporate Adjustment

Where relevant to the instrument:

```text historical adjustment event
```

must not create artificial strategy P&L.

The exact treatment depends on the canonical instrument-data contract.

---

# 66. Scenario BE: Data Backfill

Historical data is corrected after an experiment.

Expected:

```text old DatasetVersion remains immutable.
```

The corrected dataset receives:

```text new DatasetVersion.
```

Old results are not silently overwritten.

---

# 67. Scenario BF: Execution Cost Attack

Increase:

```text spread
slippage
latency
```

incrementally.

The strategy's economic result should degrade in a directionally sensible manner.

Unexpected improvement requires investigation.

---

# 68. Scenario BG: Risk Monotonicity Attack

Increase:

```text AuthorizedRisk
```

while keeping all economic variables constant.

The resulting permitted quantity should not decrease solely because risk authorization increased.

---

# 69. Scenario BH: Economic Monotonicity Attack

Increase:

```text execution cost.
```

while holding all else constant.

Expected:

```text ExpectedNetValue should not improve.
```

If it does, an economic formula is likely incorrect.

---

# 70. Scenario BI: Probability Monotonicity

Increase probability while holding payoff distribution constant.

Expected:

```text ExpectedValue should respond according to the canonical mathematical definition.
```

But:

```text RiskAuthorization
```

must remain unchanged unless explicitly defined otherwise.

---

# 71. Scenario BJ: Payoff Monotonicity

Increase favorable payoff while holding probability constant.

Expected:

```text EconomicValue should not decrease
```

under the canonical value function.

---

# 72. Scenario BK: Cost Boundary

Construct:

```text GrossEdge = ExpectedCost.
```

Expected:

```text NetEconomicValue = boundary condition.
```

The trade must follow the exact acceptance inequality.

No floating-point accident should change the conceptual rule.

---

# 73. Scenario BL: Zero Edge

Set:

```text ExpectedNetValue = 0.
```

The system must follow the predefined economic eligibility rule.

It must not manufacture a positive edge through rounding.

---

# 74. Scenario BM: Negative Edge

Set:

```text ExpectedNetValue < 0.
```

Expected:

```text NO_TRADE.
```

unless the canonical strategy explicitly defines another reason to trade, which the current specification does not.

---

# 75. Scenario BN: Maximum Risk Boundary

Construct:

```text Risk = AuthorizedRisk.
```

Expected:

```text trade remains eligible
```

if the specification uses `<=`.

Then test:

```text Risk > AuthorizedRisk.
```

Expected:

```text rejection.
```

This fixes the exact boundary semantics.

---

# 76. Scenario BO: Lot Boundary

Construct:

```text Q_raw = 1.0 lot
Q_raw = 0.99 lot
Q_raw = 1.01 lot.
```

Verify deterministic rounding behavior.

The result must never exceed the risk authorization.

---

# 77. Scenario BP: Capital Boundary

Construct:

```text RequiredCapital = AvailableCapital.
```

Then:

```text RequiredCapital > AvailableCapital.
```

The second case must reject the trade.

---

# 78. Scenario BQ: Multiple Signal Collision

Generate two valid signals at effectively the same opportunity.

Expected behavior must follow the concurrency contract.

The system must not accidentally double risk because two components independently authorized the same economic thesis.

---

# 79. Scenario BR: Duplicate Strategy Invocation

Invoke the decision engine twice with the same canonical state/event.

Expected:

```text idempotent decision behavior
```

where the architecture requires it.

It must not generate duplicate orders.

---

# 80. Scenario BS: Delayed Event

Deliver an event significantly later than expected.

The system must classify it according to the data-quality contract.

It must not silently pretend the event arrived at its original logical time if that distinction matters to execution.

---

# 81. Scenario BT: Clock Inconsistency

Synthetic components report inconsistent timestamps.

Expected:

```text temporal integrity failure
```

or deterministic normalization according to the timestamp contract.

---

# 82. Scenario BU: Impossible State Injection

Directly construct:

```text PositionState = CLOSED
Quantity > 0
```

The invariant checker must reject it.

---

# 83. Scenario BV: Invalid Transition Injection

Attempt:

```text CLOSED → ACTIVE
```

without the explicitly authorized reopening transition.

Expected:

```text transition rejected.
```

---

# 84. Scenario BW: Exit-After-Session Policy

Force an active position into session close.

Verify the exact overnight/forced-exit policy.

No implicit behavior is permitted.

---

# 85. Scenario BX: Risk-State Corruption

Corrupt:

```text AuthorizedRisk
```

during an active trade.

The system must detect:

```text state integrity violation.
```

It must not silently reconstruct risk from an arbitrary corrupted value.

---

# 86. Scenario BY: Accounting-State Corruption

Corrupt:

```text cost basis
```

and compare against fill ledger.

Expected:

```text reconciliation failure.
```

The ledger remains authoritative.

---

# 87. Scenario BZ: Version Mismatch

Attempt to combine:

```text ModelVersion A
```

with:

```text incompatible RiskPolicyVersion B.
```

Expected:

```text configuration compatibility failure.
```

---

# 88. Scenario CA: Dataset / Model Incompatibility

Run a model requiring fields absent from the dataset.

Expected:

```text capability/contract failure.
```

The system must not silently substitute unrelated fields.

---

# 89. Scenario CB: Parameter Type Violation

Provide:

```text negative threshold
string instead of numeric
invalid enumeration
```

where prohibited.

Expected:

```text validation failure before execution.
```

---

# 90. Scenario CC: Numerical Precision Attack

Use values near:

```text zero
threshold boundaries
lot boundaries
risk boundaries.
```

Verify that numerical rounding cannot create unauthorized trades.

---

# 91. Scenario CD: Floating-Point Consistency

Equivalent mathematical calculations performed through different valid computational paths should not produce contradictory trading decisions near hard boundaries.

Where necessary, canonical tolerances or decimal arithmetic must be specified.

---

# 92. Scenario CE: Randomness Attack

Run the same stochastic scenario with:

```text Seed A
Seed A
```

Expected:

```text identical result.
```

Then run:

```text Seed B.
```

Results may differ, but the distribution should obey the declared stochastic contract.

---

# 93. Scenario CF: Adversarial Parameter Perturbation

Perturb every learned parameter around its selected value.

Verify:

```text no catastrophic discontinuity
```

unless a mathematically explicit boundary exists.

---

# 94. Scenario CG: Label Boundary

Construct observations exactly at:

```text positive label threshold
negative label threshold
```

Verify deterministic labeling.

No ambiguous floating-point classification is permitted.

---

# 95. Scenario CH: Horizon Boundary

Construct future outcome exactly at:

```text H
H - ε
H + ε
```

Verify that the label uses the canonical horizon definition.

---

# 96. Scenario CI: Missing Future Horizon

If the required future observation does not exist:

```text label = UNAVAILABLE.
```

It must not be assigned:

```text negative
```

simply because the future data is missing.

---

# 97. Scenario CJ: Survivorship Bias

Remove instruments that ceased trading from the historical universe.

The dataset validator should identify the possibility of:

```text survivorship bias.
```

The research system must use the canonical historical universe definition.

---

# 98. Scenario CK: Look-Ahead Universe Bias

An instrument that becomes eligible only later must not appear in earlier historical candidate sets.

---

# 99. Scenario CL: Selection Bias

Run:

```text many candidate strategies
```

and verify that the research ledger retains all materially evaluated candidates.

The system must not retain only the winner.

---

# 100. Scenario CM: Holdout Contamination

Attempt to modify parameters after viewing final-holdout results.

Expected:

```text validation protocol violation.
```

A new experiment must be created.

---

# 101. Scenario CN: Production Mutation

Attempt to modify a production model from the research environment.

Expected:

```text prohibited.
```

Production requires explicit promotion.

---

# 102. Scenario CO: Live Learning Injection

Feed a newly completed live trade directly into active model parameters.

Expected:

```text prohibited under baseline architecture.
```

---

# 103. Scenario CP: Recovery

Inject a recoverable operational failure.

Expected:

```text failure detected
    ↓
safe state
    ↓
recovery
    ↓
validated normal operation
```

Recovery itself must obey the state machine.

---

# 104. Scenario CQ: Non-Recoverable Failure

Inject corrupted state that cannot be safely reconstructed.

Expected:

```text FAIL_CLOSED.
```

No new exposure is permitted.

---

# 105. Scenario CR: Safety Dominance

Create simultaneous events:

```text valid new entry
+
risk reconciliation failure.
```

Expected:

```text safety failure wins.
```

The entry must not occur.

---

# 106. Scenario CS: Exit Dominance

Create:

```text valid new entry
+
active emergency exit obligation.
```

Expected:

```text exit obligation dominates new entry.
```

---

# 107. Scenario CT: Risk Dominance

Create:

```text extremely attractive opportunity
+
zero remaining risk budget.
```

Expected:

```text NO_TRADE.
```

Economic attractiveness cannot override risk authorization.

---

# 108. Scenario CU: Execution Dominance

Create:

```text positive expected value
+
unexecutable market state.
```

Expected:

```text NO_EXECUTION.
```

---

# 109. Scenario CV: Accounting Dominance

Create a situation where:

```text execution appears profitable
```

but:

```text accounting reconciliation fails.
```

Expected:

```text result invalidated.
```

Profitability cannot override accounting integrity.

---

# 110. Scenario CW: Full Adversarial Chain

Construct:

```text false breakout
+
spread expansion
+
partial fill
+
latency
+
rapid reversal
+
protection breach
+
failed exit
+
reconciliation mismatch.
```

The system must:

```text preserve state integrity
preserve risk accounting
preserve fill accounting
detect failure
fail safely.
```

This is the highest-value integrated adversarial test.

---

# 111. Metamorphic Testing

The test suite should also use metamorphic properties.

For example:

```text If transaction costs increase,
net economic value should not improve.
```

Or:

```text If authorized risk decreases,
permitted quantity should not increase.
```

These properties are often more powerful than individual expected-output tests.

---

# 112. Metamorphic Test Classes

The canonical classes include:

```text Causality
Monotonicity
Conservation
Idempotency
Temporal Consistency
Risk Monotonicity
Economic Monotonicity
Execution Monotonicity
Accounting Conservation
```

---

# 113. Conservation Properties

The following must be conserved:

```text quantity
fill identity
trade identity
P&L reconciliation
risk accounting.
```

---

# 114. Monotonicity Properties

Examples:

```text higher cost
→ no higher economic value

lower risk budget
→ no higher permitted risk

higher protected profit
→ no weaker protection

more unfavorable execution
→ no better realized execution cost.
```

---

# 115. Idempotency Properties

Repeated processing of the same authoritative event must not duplicate:

```text fills
orders
position changes
P&L
state transitions.
```

---

# 116. Causality Properties

Every output must have an auditable dependency path back to information that existed before the output's timestamp.

---

# 117. Test Severity

Failures are classified:

```text CRITICAL
HIGH
MEDIUM
LOW
```

---

# 118. Critical Failures

Examples:

```text future leakage
risk expansion without authorization
impossible position
accounting corruption
duplicate fill
exit-before-entry
production safety bypass.
```

A critical failure blocks implementation promotion.

---

# 119. High Failures

Examples:

```text incorrect execution assumption
incorrect partial-fill handling
state recovery inconsistency
incorrect option contract mapping.
```

These must be resolved before production.

---

# 120. Medium Failures

Examples:

```text incomplete diagnostics
non-critical metric inconsistency
poor observability.
```

These require explicit disposition.

---

# 121. Low Failures

Examples:

```text reporting formatting
non-critical metadata omissions.
```

These may be deferred if they cannot affect strategy correctness.

---

# 122. Test Coverage Requirement

The test suite must cover:

```text every state
every transition
every invariant
every failure state
every externally supplied contract boundary
```

before implementation is considered formally verified.

---

# 123. Coverage Is Not Proof

High test coverage does not mathematically prove correctness.

Therefore:

```text coverage
+
property testing
+
adversarial scenarios
+
invariant checking
```

are all required.

---

# 124. Formal Specification Versus Implementation

At this stage:

```text specification = authority.
```

The implementation must conform to the specification.

If implementation behavior contradicts the specification:

```text implementation is wrong
```

unless the specification itself is formally revised.

---

# 125. Specification Change

A discovered contradiction may require specification modification.

If so:

```text SpecificationVersion increments.
```

Affected tests must be rerun.

---

# 126. Regression Requirement

Every fixed defect creates:

```text regression test.
```

The original failure must never silently return.

---

# 127. Golden Scenarios

A subset of synthetic scenarios becomes:

```text GoldenTestSuite.
```

These represent canonical expected behavior.

Every future implementation must pass them.

---

# 128. Golden State Trace

A golden test stores:

```text EventSequence
StateSequence
DecisionSequence
OrderSequence
FillSequence
PositionSequence
AccountingSequence
```

The implementation is compared against this canonical trace.

---

# 129. Full-System Golden Test

At least one scenario should exercise:

```text market
→ signal
→ entry
→ management
→ trailing
→ exit
→ accounting
```

end-to-end.

---

# 130. Adversarial Regression Suite

All previously discovered failures become permanent regression scenarios.

The suite grows monotonically.

---

# 131. Test Results

Every test run produces:

```text TestRunID
ScenarioID
SpecificationVersion
ModelVersion
Result
FailureClass
ObservedTrace
ExpectedTrace
Diagnostics
```

---

# 132. Test Reproducibility

A failed test must be reproducible from its:

```text ScenarioID
Seed
Versions
Configuration.
```

---

# 133. Test Invariants

```text ADV-001
Every scenario is reproducible.

ADV-002
Every expected transition is explicit.

ADV-003
Every invariant violation is observable.

ADV-004
Future information cannot influence prior state.

ADV-005
Unauthorized risk cannot be created.

ADV-006
Impossible states cannot be accepted.

ADV-007
Duplicate events cannot duplicate economic effects.

ADV-008
Missing data cannot silently become fabricated data.

ADV-009
Unexecutable orders cannot become fills.

ADV-010
Accounting quantities are conserved.

ADV-011
Realized P&L is fill-derived.

ADV-012
Production safety dominates opportunity generation.

ADV-013
Critical failures block promotion.

ADV-014
Every fixed defect becomes a regression test.

ADV-015
Specification changes trigger affected-test reevaluation.
```

---

# 134. Numerical Parameters Still Unfrozen

We deliberately do not yet choose:

```text exact synthetic volatility levels
exact spread multipliers
exact latency values
exact slippage multipliers
exact depth distributions
exact adversarial scenario frequencies
numerical tolerances
floating-point tolerances
minimum test repetitions.
```

Those should be finalized alongside the implementation/test harness and real-data contract.

---

# 135. Formal Verification Boundary

At this point we have defined:

```text WHAT the system should calculate
WHEN it should calculate it
WHAT state it should enter
WHAT state it must never enter
HOW risk is constrained
HOW execution occurs
HOW P&L is calculated
HOW research is validated
HOW failures are detected
```

The next boundary is no longer conceptual.

It is:

```text SPECIFICATION
        ↓
CANONICAL SCHEMAS
        ↓
IMPLEMENTATION CONTRACTS
```

---

# 136. Architecture Status

```text Mathematical Specification              COMPLETE
Variable Registry                          COMPLETE
Dependency Graph                           COMPLETE
State Transition Specification              COMPLETE
Historical Label Specification              COMPLETE
Statistical Estimation                     COMPLETE
Economic Decision                          COMPLETE
Option Selection                           COMPLETE
Risk Budget                                COMPLETE
Position Sizing                            COMPLETE
Execution / Slippage                       COMPLETE
P&L / Accounting                           COMPLETE
Performance Attribution                    COMPLETE
Model Validation                           COMPLETE
Promotion / Rejection                      COMPLETE
Research Experiment Control                COMPLETE
Version Control                             COMPLETE
Synthetic / Adversarial Verification        COMPLETE
```

---

# 137. Next Artifact

The next artifact should be the:

# CANONICAL IMPLEMENTATION CONTRACT AND MODULE BOUNDARY SPECIFICATION

This is the first artifact where we begin translating the specification into software architecture.

It will define, without writing implementation code yet:

```text module boundaries
interfaces
input/output contracts
type ownership
state ownership
dependency direction
pure versus stateful components
event contracts
persistence boundaries
calculation ownership
validation ownership
error contracts
version contracts
```

The critical rule remains:

```text Implementation must conform to the specification.
```

We do not add a new "strategy layer."

We convert the existing canonical specification into **strict software contracts**.