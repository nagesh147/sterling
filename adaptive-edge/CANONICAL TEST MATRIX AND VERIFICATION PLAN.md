# CANONICAL TEST MATRIX AND VERIFICATION PLAN

Version 1.0

## 1. Purpose

This document converts the mathematical and architectural invariants into an executable verification framework.

The test system must establish five properties:

```text
CORRECTNESS
CAUSALITY
ACCOUNTING INTEGRITY
RISK SAFETY
REPRODUCIBILITY
```

Only after these pass does historical performance testing become meaningful.

---

# 2. Verification Hierarchy

Testing proceeds in this order:

```text
STATIC CONTRACT TESTS
        ↓
MATHEMATICAL UNIT TESTS
        ↓
PROPERTY TESTS
        ↓
STATE-MACHINE TESTS
        ↓
EVENT-SEQUENCE TESTS
        ↓
ADVERSARIAL TESTS
        ↓
HISTORICAL REPLAY
        ↓
WALK-FORWARD VALIDATION
        ↓
PAPER EXECUTION
```

A failure at an earlier level invalidates conclusions from later levels.

---

# 3. Test Severity

Every invariant receives a severity:

```text
CRITICAL
HIGH
MEDIUM
DIAGNOSTIC
```

A critical failure blocks progression.

Examples of critical failures:

```text future-data leakage
negative position
duplicate fill accounting
risk protection decrease
incorrect realized P&L
invalid model promotion
```

---

# 4. Static Contract Tests

Before executing market data, verify:

```text every variable has one owner
every variable has one canonical definition
every dependency exists
every required input is declared
every state transition is defined
every parameter is versioned
every external dependency is identified.
```

---

# 5. Variable Registry Test

For every canonical variable:

```text VariableID
Definition
Owner
Unit
Type
UpdateTrigger
Dependencies
Availability
```

must exist.

A variable without an owner is a specification failure.

A variable with multiple canonical owners is also a specification failure.

---

# 6. Unit Consistency Tests

Every mathematical equation must pass dimensional validation.

For example:

```text ₹ + ₹       = valid
price × quantity = monetary value
probability × ₹  = monetary expectation
```

while:

```text price + probability
```

must be rejected.

---

# 7. Domain Tests

Verify mathematical domains.

Examples:

```text Probability ∈ [0,1]

Quantity >= 0

Risk >= 0

HoldingTime >= 0

Variance >= 0

Volatility >= 0
```

Invalid inputs must not silently propagate.

---

# 8. Probability Tests

Given valid probability inputs:

```text 0 <= P <= 1
```

must always remain true.

Test:

```text P = 0
P = 1
P ≈ 0
P ≈ 1
```

and malformed values.

---

# 9. Expected-Value Tests

For known synthetic distributions:

```text outcome probabilities
+
outcome payoffs
+
costs
```

the Economic Engine must produce the mathematically expected result.

This test does not involve market data.

It validates the operator itself.

---

# 10. Position-Sizing Tests

Given:

```text risk budget
option price
stop/protection distance
lot size
```

the position-sizing function must produce:

```text integer tradable quantity
```

that satisfies:

```text calculated risk <= authorized risk.
```

---

# 11. Rounding Tests

Test values immediately around lot boundaries:

```text 0.99 lots
1.00 lots
1.01 lots
1.99 lots
2.00 lots
```

The system must never produce fractional tradable quantities where the instrument prohibits them.

---

# 12. Protection Tests

For:

```text Protection_old = X
```

test:

```text proposed = X + δ
```

and:

```text proposed = X - δ.
```

The first is valid.

The second must be rejected.

---

# 13. Peak P&L Tests

Given:

```text CurrentPnL:
+10
+20
+15
+30
+5
```

the expected:

```text PeakPnL:
+10
+20
+20
+30
+30
```

must be produced.

Peak P&L can never decrease.

---

# 14. Giveback Tests

For:

```text PeakPnL = 30
CurrentPnL = 12
```

the system must produce:

```text Giveback = 18.
```

A negative giveback is impossible.

---

# 15. State-Machine Verification

The state machine must be tested as transitions rather than isolated functions.

Valid example:

```text NO_POSITION
    ↓
OPPORTUNITY
    ↓
ENTRY_AUTHORIZED
    ↓
ORDER_PENDING
    ↓
ACTIVE
    ↓
EXIT_PENDING
    ↓
CLOSED
    ↓
NO_POSITION
```

---

# 16. Invalid Transition Tests

Attempt:

```text NO_POSITION -> EXIT_PENDING
NO_POSITION -> ACTIVE
CLOSED -> ACTIVE
ACTIVE -> ENTRY_AUTHORIZED
```

without the required events.

Every attempt must be rejected.

---

# 17. No Synthetic Position Test

Generate:

```text BUY_DECISION
```

without:

```text FILL_EVENT.
```

Expected:

```text PositionQuantity = 0.
```

A signal must never create exposure.

---

# 18. Order-Without-Fill Test

Generate:

```text OrderSubmitted
OrderAccepted
```

but no fill.

Expected:

```text PositionQuantity = 0.
```

This is critical.

---

# 19. Partial Fill Test

Request:

```text quantity = 100
```

then receive:

```text fill = 40.
```

Expected:

```text Position = 40
Remaining = 60.
```

Then receive:

```text fill = 60.
```

Expected:

```text Position = 100.
```

---

# 20. Duplicate Fill Test

Process:

```text FillID = F001
```

twice.

Expected:

```text Position changes only once.
```

P&L and transaction costs must also change only once.

---

# 21. Late Fill Test

Generate:

```text cancel request
```

followed by:

```text fill.
```

The system must follow the explicit cancellation/fill race policy.

It must not assume cancellation means no fill.

---

# 22. Out-of-Order Event Test

Feed:

```text Event_2
Event_1
```

where:

```text Timestamp(Event_1) < Timestamp(Event_2).
```

The system must either:

```text reorder according to the canonical event contract
```

or:

```text quarantine the sequence.
```

It must not silently process an invalid causal sequence.

---

# 23. Timestamp Collision Test

Create multiple events with identical timestamps.

The system must use a deterministic secondary ordering rule.

This is important for tick-level data.

Otherwise identical input data can produce different trading outcomes.

---

# 24. Event Replay Test

Replay:

```text E1
E2
E3
...
En
```

twice.

Expected:

```text FinalState_A = FinalState_B.
```

All intermediate state checkpoints must also match.

---

# 25. Event Idempotency Test

Process:

```text E1
E2
E2
E3
```

and compare with:

```text E1
E2
E3.
```

For idempotent events:

```text final state must be identical.
```

---

# 26. Causality Test

Construct:

```text MarketEvent_t
FutureOutcome_(t+1)
```

Then deliberately expose the future outcome to the feature engine.

The system must reject it.

This test proves that future information cannot enter the decision dependency graph.

---

# 27. Future-Price Injection Test

Take a historical decision at time `t`.

Modify:

```text price_(t+1)
```

without changing any information available at `t`.

Expected:

```text Decision_t remains unchanged.
```

If it changes, there is look-ahead leakage.

This is an extremely powerful test.

---

# 28. Future-Volume Injection Test

Perform the same experiment with:

```text future volume.
```

Expected:

```text historical decision unchanged.
```

---

# 29. Future-Option-Price Injection Test

Modify future option prices while preserving all prices available before the decision.

Expected:

```text entry decision unchanged.
```

---

# 30. Future-Aggregate Injection Test

This is more subtle.

Suppose a feature uses:

```text average volatility for a particular time-of-day.
```

Change future years' volatility while keeping the historical training period unchanged.

The historical decision must not change if those observations were outside the eligible training boundary.

---

# 31. Normalization Leakage Test

Construct a feature normalized using:

```text historical-only statistics
```

and another version using:

```text full-dataset statistics.
```

The system must identify the latter as invalid for historical decision generation.

---

# 32. Label-Maturity Test

Create:

```text prediction at T0
label horizon = T0 + H.
```

At:

```text T0 + H - ε
```

the label must remain:

```text IMMATURE.
```

At:

```text T0 + H
```

it becomes:

```text MATURED.
```

---

# 33. Same-Day Learning Test

Create a trade that closes at:

```text 10:00.
```

If its label requires information through:

```text 10:30,
```

then the ten o'clock event cannot be used for learning.

This prevents premature self-training.

---

# 34. Training Boundary Test

Suppose:

```text TrainingCutoff = T.
```

Any feature or label requiring information after `T` must be rejected from training.

---

# 35. Validation Boundary Test

Likewise, validation observations cannot modify the model before the predefined validation boundary.

---

# 36. Final Holdout Test

Attempt to:

```text inspect holdout
+
modify parameter
+
rerun confirmation.
```

The research system must classify the holdout as:

```text CONTAMINATED.
```

A new clean confirmation is then required.

---

# 37. Parameter Version Test

Create:

```text ParameterVersion A
ParameterVersion B.
```

A historical decision generated under A must continue to reference A even after B becomes active.

---

# 38. Model Promotion Test

Attempt to promote:

```text incomplete model
```

The promotion must fail.

Only:

```text validated
+
complete
+
versioned
```

models may become active.

---

# 39. Active-Trade Model Test

Start a trade using:

```text RuntimeVersion A.
```

Promote:

```text RuntimeVersion B.
```

while the trade is active.

The system must not silently switch the trade to B.

The trade remains governed by its explicit active-trade policy.

---

# 40. Risk/Mode Attack

Create:

```text Mode = SCALP
Protection = X.
```

Then generate:

```text Mode = INTRADAY.
```

Attempt to change:

```text Protection = X - δ.
```

Expected:

```text REJECTED.
```

---

# 41. Probability/Risk Attack

Increase:

```text Probability
```

dramatically.

Verify that:

```text existing authorized risk
```

does not automatically increase.

---

# 42. Profit/Risk Attack

Increase:

```text ExpectedProfit
```

dramatically.

Verify:

```text RiskBudget unchanged.
```

This prevents optimistic predictions from becoming uncontrolled exposure.

---

# 43. Reversal Attack

Generate:

```text bullish probability
```

followed immediately by:

```text bearish probability.
```

The system must follow the defined emergency-reversal policy.

It must not:

```text reverse position automatically
```

unless the specification explicitly authorizes that transition.

---

# 44. Protection-Gap Attack

Simulate:

```text protection = X
market jumps directly below X.
```

The system must distinguish:

```text trigger condition
```

from:

```text actual executable exit price.
```

The P&L must reflect the execution model.

---

# 45. Extreme Volatility Test

Create a synthetic event stream with:

```text extremely rapid price movement
```

and verify:

```text no invalid state
no negative position
no protection decrease
no duplicate exit
```

---

# 46. False Breakout Test

Construct:

```text opening-range breakout
        ↓
rapid reversal
        ↓
breakout failure.
```

The system should:

```text update state correctly
evaluate reversal evidence
respect protection
```

without accessing future reversal information before it occurs.

---

# 47. Trend Continuation Test

Construct:

```text breakout
    ↓
continued directional movement
    ↓
extended move.
```

Verify that the continuation model can maintain an appropriate mode without:

```text loosening established protection.
```

---

# 48. Choppy Market Test

Construct:

```text repeated small directional changes
```

with no sustained move.

The system should demonstrate the intended:

```text NO_TRADE
or
early-risk-control
```

behavior according to the learned policy.

The test is not allowed to assume that choppy markets must be profitable.

---

# 49. Volatility Collapse Test

Construct a market where:

```text volatility decreases sharply.
```

Verify that the probability and economic layers respond according to their defined distributions.

No hardcoded assumption about volatility behavior is allowed.

---

# 50. Liquidity Collapse Test

Construct:

```text widening spread
low available size
missing quotes.
```

Expected behavior:

```text option may become economically invalid
```

and potentially:

```text NO_TRADE.
```

---

# 51. Missing Data Test

Remove a critical market event.

The system must not interpret:

```text missing
```

as:

```text zero.
```

The resulting state must become:

```text DATA_DEGRADED
```

or another explicitly defined safe state.

---

# 52. Duplicate Market Event Test

Duplicate a market event.

The result must follow the event's idempotency contract.

It must not create:

```text double volume
double signal
double state transition
```

unless the provider semantics explicitly define separate events.

---

# 53. Data Gap Test

Create a large timestamp gap.

The system must detect that:

```text expected observations are absent.
```

The correct behavior depends on the data-quality contract.

It must not silently treat the market as unchanged.

---

# 54. Session Boundary Test

Construct events around:

```text market open
opening-range end
market close.
```

Verify that session state transitions occur exactly according to the canonical session contract.

Exact exchange times remain a data-contract TODO.

---

# 55. Overnight Test

If the strategy is intraday-only:

```text position at session close
```

must trigger the defined session-close policy.

The system must not accidentally carry exposure into the next session.

---

# 56. Option Identity Test

Create two contracts with:

```text same strike
same option type
different expiry.
```

They must remain distinct instruments.

Likewise:

```text same expiry
different strike
```

must remain distinct.

---

# 57. CE/PE Selection Test

Given identical underlying evidence but different option economics:

```text CE
PE
```

the engine must independently evaluate each candidate.

It must not select based solely on underlying direction.

---

# 58. Option Liquidity Test

Create an option with:

```text valid directional expectation
but unacceptable execution conditions.
```

Expected:

```text NO_VALID_OPTION
```

rather than a forced trade.

---

# 59. Cost Sensitivity Test

Take an otherwise profitable synthetic opportunity.

Increase:

```text execution cost.
```

The economic decision must eventually cross its predefined validity boundary.

This verifies that costs are actually integrated into the decision.

---

# 60. Slippage Stress Test

Increase simulated slippage.

Measure:

```text gross edge
net edge
```

The difference must equal the declared execution impact.

---

# 61. Execution-Feasibility Test

Attempt to execute a quantity larger than historically available liquidity under the execution model.

The simulator must not manufacture the entire fill.

---

# 62. Partial-Liquidity Test

If only part of the desired quantity can be executed:

```text ActualFill < RequestedQuantity.
```

The Position Ledger must reflect only the executed quantity.

---

# 63. Cancellation Test

Submit:

```text order
cancel
```

without confirmation.

The system must distinguish:

```text cancellation requested
```

from:

```text cancellation confirmed.
```

---

# 64. Broker Failure Test

Simulate:

```text broker API unavailable.
```

Expected:

```text order status = UNKNOWN
```

not:

```text CANCELLED.
```

The system enters the appropriate operational state.

---

# 65. Recovery Test

After a simulated process restart:

```text replay events
+
query authoritative external state where available.
```

The reconstructed position must equal the authoritative position.

---

# 66. P&L Accounting Test

Create known executions:

```text entry = ₹100
quantity = Q
exit = ₹120.
```

The realized P&L must equal the defined accounting result after applicable costs.

This establishes the ledger independently of strategy logic.

---

# 67. Fee Test

Add transaction costs.

Verify:

```text NetPnL
=
GrossPnL
-
declared costs.
```

No cost category may silently disappear.

---

# 68. Current-P&L Valuation Test

Once the valuation convention is finalized, construct:

```text bid
ask
mid
last
```

with materially different values.

Verify that CurrentPnL uses exactly the declared valuation source.

---

# 69. Trade Closure Test

A trade cannot become:

```text CLOSED
```

until:

```text actual position = 0
```

and:

```text execution state reconciled.
```

---

# 70. Outcome Immutability Test

Once a trade's final accounting is reconciled:

```text FinalTradeOutcome
```

cannot be altered by a later model version.

---

# 71. Learning Isolation Test

A model update must not change:

```text historical trade outcomes.
```

It only changes:

```text future decisions.
```

---

# 72. Research Lineage Test

Every candidate model must be traceable to:

```text experiment
dataset
feature version
label version
parameter search
evaluation result.
```

---

# 73. Multiple-Testing Test

Run:

```text N candidate parameter configurations.
```

Verify that all N are recorded.

The system must not retain only the best configuration.

---

# 74. Selection-Bias Test

Construct:

```text many candidate strategies
```

where one happens to perform exceptionally well by chance.

The research report must show:

```text number tested
```

rather than presenting the winner as if it were the only candidate.

---

# 75. Ablation Test

Run:

```text FullStrategy
FullStrategy - FeatureX.
```

The resulting performance difference must be attributable to FeatureX and not to an accidental change in another component.

---

# 76. Baseline Test

Every major strategy component must have a baseline comparison.

Example:

```text Full dynamic management
vs.
simple fixed management.
```

This determines whether complexity produces incremental value.

---

# 77. Parameter Fragility Test

Take the selected parameter:

```text θ.
```

Test:

```text θ - δ
θ
θ + δ.
```

A sharp isolated peak should be flagged as:

```text PARAMETER_FRAGILITY.
```

---

# 78. Regime Test

Partition historical data into predefined regimes.

Compare:

```text performance
calibration
drawdown
execution sensitivity.
```

The purpose is to determine where the model works and where it fails.

---

# 79. Time-of-Day Test

Evaluate performance across predefined session segments.

Do not allow the results to redefine the segments after seeing performance.

Otherwise the analysis becomes exploratory rather than confirmatory.

---

# 80. Synthetic Market Generator

Before historical replay, we should have a synthetic event generator capable of producing:

```text trend
range
breakout
false breakout
reversal
gap
volatility expansion
volatility contraction
liquidity collapse
missing data
duplicate events
delayed events.
```

The generator is for structural verification, not for proving profitability.

---

# 81. Why Synthetic Data Comes First

Synthetic data gives us something historical data cannot:

```text known ground truth. id="h5ly0o"
```

We know exactly:

```text what happened
when it happened
what information was available
what the correct state should be.
```

This makes it possible to detect state-machine errors precisely.

---

# 82. Golden Scenarios

A small set of immutable scenarios should become:

```text GoldenScenario_001
GoldenScenario_002
...
```

Each contains:

```text input events
expected state checkpoints
expected decisions
expected positions
expected exits
expected P&L.
```

Any code change must preserve these unless the specification itself changes.

---

# 83. Golden Scenario: Simple Winning Trade

```text opening range
    ↓
valid breakout
    ↓
high probability
    ↓
valid option
    ↓
entry
    ↓
continuation
    ↓
profit protection
    ↓
exit.
```

This verifies the normal path.

---

# 84. Golden Scenario: Losing Trade

```text valid entry
    ↓
breakout failure
    ↓
adverse movement
    ↓
protection trigger
    ↓
slippage
    ↓
exit.
```

This verifies that losses are accounted realistically.

---

# 85. Golden Scenario: No Trade

```text opportunity
    ↓
insufficient probability
```

Expected:

```text NO_TRADE.
```

No order must be generated.

---

# 86. Golden Scenario: Good Direction, Bad Option

```text strong underlying probability
+
poor option economics
```

Expected:

```text NO_TRADE.
```

This verifies the separation between directional prediction and option selection.

---

# 87. Golden Scenario: Dynamic Continuation

```text entry
    ↓
favorable movement
    ↓
continuation evidence
    ↓
mode changes
```

Expected:

```text mode changes
protection does not loosen.
```

---

# 88. Golden Scenario: Emergency Reversal

```text active long CE
    ↓
strong opposing evidence
    ↓
emergency condition.
```

The exact response depends on the finalized transition policy.

The test verifies that the system follows the policy rather than inventing behavior.

---

# 89. Golden Scenario: Data Failure

```text active trade
    ↓
critical market data failure.
```

Expected:

```text DATA_DEGRADED
no new entry
existing risk state preserved.
```

---

# 90. Golden Scenario: Reconciliation Failure

```text active trade
    ↓
internal position != authoritative position.
```

Expected:

```text RECONCILIATION_REQUIRED
no new trade.
```

---

# 91. Golden Scenario: Future Leak

Inject:

```text future price path
```

into the environment.

Historical decision must remain unchanged.

This becomes one of the strongest regression tests in the system.

---

# 92. Verification Coverage

The final test matrix must map:

```text Invariant
    ↓
Test ID
    ↓
Test Type
    ↓
Expected Result
    ↓
Severity.
```

No critical invariant may exist without a corresponding test.

---

# 93. Verification Status

At implementation start, each invariant receives:

```text NOT_IMPLEMENTED
IMPLEMENTED
PASS
FAIL
BLOCKED
```

A blocked test must identify why.

It cannot simply be marked passed.

---

# 94. External-Contract Tests

Some tests cannot be finalized until the TrueData documentation arrives.

These include:

```text exact event ordering
timestamp semantics
tick/TBT semantics
option quote semantics
historical availability
depth semantics.
```

They remain:

```text BLOCKED_EXTERNAL_CONTRACT.
```

They are not considered failures.

---

# 95. Broker-Contract Tests

Likewise:

```text actual fill behavior
partial fills
cancellation race
latency
fees
position reconciliation
```

remain blocked until the broker/execution contract is known.

---

# 96. Critical Gate

Before historical backtesting:

```text all mathematical tests = PASS
all critical state tests = PASS
all causal tests = PASS
all accounting tests = PASS
all risk invariants = PASS
```

External-contract tests may remain blocked only where the external documentation genuinely has not yet been supplied.

---

# 97. Historical Backtest Gate

After synthetic verification:

```text historical replay
```

is permitted.

But it is still:

```text RESEARCH.
```

It is not yet evidence of production readiness.

---

# 98. Historical Replay Gate

Historical replay must produce:

```text event trace
state trace
decision trace
order trace
fill trace
trade ledger
label ledger
learning events
performance report.
```

A single aggregate P&L number is insufficient.

---

# 99. Walk-Forward Gate

Only after replay correctness is established do we run:

```text train
→ validate
→ forward
→ advance.
```

All previously established research controls apply.

---

# 100. Final Verification Philosophy

The test framework therefore asks two separate questions:

```text Q1:
Did the system do exactly what we specified?

Q2:
Is what we specified actually profitable?
```

The first is answered by this verification framework.

The second is answered by the historical and walk-forward research framework.

We must never use a positive answer to Q2 to excuse failure of Q1.

---

# 101. Canonical Verification Invariants

```text TEST-001 id="n2i8by"
Every critical invariant has a test.

TEST-002
Every state transition has valid and invalid-path tests.

TEST-003
Every execution event has accounting tests.

TEST-004
Future-information injection cannot alter historical decisions.

TEST-005
Duplicate execution events cannot duplicate exposure.

TEST-006
Protection cannot decrease.

TEST-007
Risk cannot increase merely because predicted profitability increases.

TEST-008
Immature labels cannot enter learning.

TEST-009
Holdout information cannot influence development.

TEST-010
Historical replay is deterministic.

TEST-011
Model promotion cannot mutate historical results.

TEST-012
Missing critical data cannot silently become zero.

TEST-013
Unknown execution status cannot silently become cancelled.

TEST-014
No position can exist without execution evidence.

TEST-015
No trade can close while authoritative exposure remains unresolved.

TEST-016
Every critical failure fails closed.

TEST-017
Synthetic scenarios are verified before historical profitability testing.
```

---

# 102. Architecture Status

We have now completed another major boundary:

```text MATHEMATICAL SPECIFICATION       COMPLETE
ARCHITECTURAL SPECIFICATION         COMPLETE
CONSISTENCY AUDIT                   COMPLETE
IMPLEMENTATION CONTRACT             COMPLETE
VERIFICATION PLAN                   COMPLETE
```

What remains is no longer conceptual strategy design.

We are approaching the actual engineering phase.

---

# 103. Next Logical Artifact

The next artifact should be:

# CANONICAL DATA-TO-EVENT CONTRACT

This is where the TrueData documentation finally becomes relevant.

We will define exactly:

```text raw provider field
        ↓
canonical field
        ↓
canonical event
        ↓
state variable
        ↓
feature
        ↓
decision dependency
```

For every field we will record:

```text source
field name
data type
unit
timestamp
precision
update frequency
historical availability
entitlement
missing-data semantics
ordering semantics
transformation
canonical owner.
```

And, critically, we will keep unresolved items explicitly marked:

```text UNKNOWN
```

rather than guessing.

Once you provide the authoritative TrueData documentation, we can fill those mappings without changing the mathematical architecture we have now frozen.