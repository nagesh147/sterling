# CANONICAL SYSTEM INVARIANT AND FORMAL VERIFICATION SPECIFICATION

Version 1.0

## 1. Purpose

This specification defines the formal safety properties of the complete trading system.

It consolidates the invariants established across:

```text
data
state
probability
economics
entry
execution
position
risk
mode
exit
learning
research
```

The objective is to establish:

```text no impossible state
no causal violation
no accounting violation
no uncontrolled risk expansion
no future-information leakage
no duplicate-event corruption
no invalid learning update
```

This is a correctness specification.

It does not establish profitability.

---

# 2. System Correctness Model

The system is considered structurally correct only if:

```text InitialState
    +
ValidEventSequence
    +
ValidTransitionFunction
    =
ValidStateSequence
```

Every transition must preserve the canonical invariants.

Formally:

```text S_t ∈ ValidStates
E_t ∈ ValidEvents
F(S_t, E_t) = S_(t+1)

=> S_(t+1) ∈ ValidStates
```

A transition producing an invalid state is a system failure.

---

# 3. Initial State

The canonical initial trading state is:

```text PositionQuantity = 0
OutstandingExposure = 0
TradeID = NULL
CurrentPnL = 0
PeakPnL = 0
Protection = NULL
Mode = NONE
ExitObligation = FALSE
ReconciliationRequired = FALSE
SystemHalted = FALSE
```

Exact initialization values for non-trading metadata may differ.

The exposure-related invariants may not.

---

# 4. State Validity

At every event boundary:

```text State_t ∈ ValidStateSpace
```

There is no valid state in which:

```text PositionQuantity < 0
```

for the baseline long-option architecture.

There is no valid state in which:

```text PositionQuantity > 0
```

while the trade lifecycle claims:

```text NO_POSITION
```

---

# 5. Causality Invariant

For every decision at time `t`:

```text Decision_t
```

may depend only on information whose availability timestamp satisfies:

```text AvailabilityTime <= t
```

Therefore:

```text FutureInformation_t+1
```

must never influence:

```text Decision_t.
```

This is the foundational invariant.

---

# 6. Information Filtration

Conceptually define:

```text F_t
```

as the information set available to the system at time `t`.

Then:

```text Decision_t = f(F_t)
```

and never:

```text Decision_t = f(F_(t+k)), k > 0.
```

The implementation must preserve this property.

---

# 7. Event Ordering

If two events have distinct timestamps:

```text t1 < t2
```

then:

```text Event(t2)
```

cannot affect the state used to process:

```text Event(t1).
```

If timestamps are equal but causal ordering is ambiguous, the event ordering contract must explicitly resolve the ambiguity.

---

# 8. Timestamp Integrity

Every event must carry:

```text EventTimestamp
```

and, where available:

```text SourceTimestamp
ReceiptTimestamp
ProcessingTimestamp
```

These must not be silently conflated.

---

# 9. Historical Replay Invariant

Given the same:

```text initial state
+
canonical event sequence
+
model version
+
parameter version
+
execution policy
```

the state machine must reproduce the same sequence of states.

Therefore:

```text Replay(Input) = Replay(Input)
```

within documented numerical tolerances.

---

# 10. Event Idempotency

If the same event is delivered twice:

```text EventID = X
```

then processing it twice must produce the same final state as processing it once.

Formally:

```text Apply(S, X, X) = Apply(S, X)
```

for idempotent events.

This is particularly important for:

```text fills
order acknowledgements
broker updates
data-feed retries.
```

---

# 11. Duplicate Fill Protection

A fill cannot be counted twice.

If:

```text FillID = F1
Quantity = Q
```

has already been applied, receiving `F1` again must not produce:

```text Position += Q
```

a second time.

---

# 12. Position Conservation

For the baseline long-only option architecture:

```text PositionQuantity_t
=
TotalEntryFills_t
-
TotalExitFills_t
```

subject to explicitly defined adjustments.

This equation must hold after every reconciled execution event.

---

# 13. No Synthetic Position

The following implication is forbidden:

```text Signal
    =>
Position
```

Likewise:

```text OrderSubmitted
    =>
Position
```

and:

```text OrderAcknowledged
    =>
Position
```

Only actual execution creates exposure.

---

# 14. Desired Versus Actual Quantity

At all times:

```text ActualFilledQuantity
<=
AuthorizedQuantity
```

unless an explicit order amendment authorizes additional quantity.

A broker event claiming execution beyond authorized quantity is a reconciliation event, not silently accepted exposure.

---

# 15. Outstanding Order Constraint

The system must maintain:

```text ExecutedQuantity
+
OutstandingAuthorizedQuantity
<=
MaximumAuthorizedExposure
```

according to the applicable execution contract.

This prevents duplicated or conflicting orders from accidentally increasing exposure.

---

# 16. No Negative Position

For a long-only position:

```text PositionQuantity >= 0
```

is invariant.

If an execution event mathematically produces:

```text PositionQuantity < 0
```

the system enters:

```text RECONCILIATION_REQUIRED
```

rather than accepting the state.

---

# 17. Trade Identity Invariant

Every non-zero position belongs to exactly one active trade lifecycle under the baseline single-position architecture.

Therefore:

```text PositionQuantity > 0
```

requires:

```text TradeID != NULL.
```

---

# 18. Trade Closure Invariant

A trade may enter:

```text TRADE_CLOSED
```

only if:

```text ActualPositionQuantity = 0
```

and:

```text ReconciliationStatus = RESOLVED.
```

---

# 19. Exit Obligation Persistence

Once:

```text ExitObligation = TRUE
```

the system cannot return to ordinary continuation management merely because the next market event improves.

The obligation persists until:

```text position closed
```

or the governing operational contract explicitly resolves it.

---

# 20. Protection Monotonicity

For the long-option baseline:

```text Protection_t >= Protection_(t-1)
```

whenever both values are defined.

Therefore:

```text protection may tighten
```

but:

```text protection may never loosen.
```

This is one of the strongest risk invariants in the entire architecture.

---

# 21. Mode-Risk Independence

A mode transition:

```text SCALP -> INTRADAY
```

cannot independently produce:

```text Protection_new < Protection_old.
```

Mode describes continuation interpretation.

Risk protection is governed independently.

---

# 22. Risk Cannot Be Increased by Optimism

An increase in:

```text Probability
ContinuationValue
ExpectedMagnitude
```

cannot automatically increase already-authorized risk.

New evidence may justify:

```text continuation
```

but cannot retroactively erase:

```text established protection.
```

---

# 23. Position Size Invariant

Position size must be determined before execution under the authorized sizing contract.

A favorable market move cannot cause:

```text PositionQuantity
```

to increase unless a separately authorized additional-entry mechanism exists.

The baseline architecture does not assume such scaling.

---

# 24. Risk Budget Invariant

At entry:

```text AuthorizedRisk <= RiskBudget.
```

During management:

```text EffectiveRisk <= PreviouslyAuthorizedRisk
```

unless a separately validated risk-increase mechanism exists.

The baseline system has no such mechanism.

---

# 25. Entry Authorization Expiry

An entry authorization is not permanent.

If the conditions that made the authorization valid become invalid before execution:

```text authorization expires.
```

A stale authorization cannot be treated as a fresh signal.

---

# 26. Signal Freshness

Every actionable signal has:

```text DecisionTimestamp
ValidityWindow
```

The system must reject an expired signal.

This prevents:

```text old information
+
new market state
=
incorrect execution.
```

---

# 27. Probability Causality

At time `t`:

```text P_t
```

must depend only on:

```text F_t
```

and parameters legitimately available at `t`.

It cannot depend on:

```text future label
future trade outcome
future price movement.
```

---

# 28. Probability-State Integrity

The probability state must remain within its mathematical domain:

```text 0 <= P <= 1.
```

Any probability outside this range is an invalid state.

---

# 29. Probability Calibration Integrity

A calibration update may use only labels whose:

```text LabelMaturityTime <= LearningTime.
```

An immature label is not eligible for learning.

---

# 30. Label Maturity Invariant

If:

```text LabelEndTime > CurrentLearningTime
```

then:

```text LabelStatus = IMMATURE.
```

It cannot enter:

```text training
validation
parameter estimation
```

as an observed outcome.

---

# 31. Training Boundary Invariant

For a training cutoff:

```text T_train
```

no observation whose required information becomes available after:

```text T_train
```

may enter training.

This applies to:

```text features
labels
execution outcomes
derived statistics.
```

---

# 32. Validation Boundary

Likewise:

```text ValidationData
```

cannot influence:

```text training parameters
```

unless the experiment explicitly defines validation as part of an adaptive walk-forward procedure.

Even then, its use must occur only at the predefined update boundary.

---

# 33. Final Holdout Invariant

The final holdout cannot influence:

```text feature selection
parameter selection
model selection
strategy design
threshold selection
execution assumptions
```

before the final confirmation is completed.

---

# 34. Research Contamination

If the final holdout is inspected and the strategy is subsequently modified:

the holdout loses its clean-confirmation status.

A new holdout evaluation is required.

---

# 35. Parameter Version Integrity

Every learned parameter used in a decision must have:

```text ParameterVersion
```

and:

```text EffectiveFrom
EffectiveUntil
```

where applicable.

A parameter cannot silently change between two events.

---

# 36. Parameter Promotion

A newly promoted parameter set cannot retroactively alter:

```text historical trades
historical decisions
historical labels.
```

Historical records remain immutable.

---

# 37. Model Version Integrity

Every decision records:

```text ModelVersion.
```

The model used to produce a historical decision cannot later be replaced in the historical record.

---

# 38. Active Trade Model Integrity

If model promotion occurs while a position is active, the system must follow an explicit management-policy rule.

It cannot silently switch models.

Until that policy is finalized:

```text ACTIVE-TRADE MODEL SWITCH = FORBIDDEN.
```

This is safer than leaving the behavior ambiguous.

---

# 39. P&L Integrity

Realized P&L can change only because of:

```text actual execution
accounting correction
```

A market tick cannot change:

```text RealizedPnL.
```

It may change:

```text UnrealizedPnL.
```

---

# 40. Unrealized P&L Integrity

Unrealized P&L must be derived from:

```text actual position
+
valid market valuation.
```

It cannot be based on:

```text requested order price
```

or:

```text theoretical signal price.
```

---

# 41. Peak P&L Monotonicity

For a trade:

```text PeakPnL_t
=
max(PeakPnL_(t-1), CurrentPnL_t)
```

Therefore:

```text PeakPnL_t >= PeakPnL_(t-1).
```

Peak P&L can never decrease.

---

# 42. Giveback Integrity

If:

```text CurrentPnL <= PeakPnL
```

then:

```text Giveback = PeakPnL - CurrentPnL.
```

Therefore:

```text Giveback >= 0.
```

A negative giveback is an invalid state.

---

# 43. Execution Price Integrity

Realized P&L must use:

```text ActualFillPrice.
```

It cannot use:

```text signal price
stop trigger price
mid price
last price
```

unless that value is itself the documented actual fill price.

---

# 44. Stop Execution Integrity

A protection trigger and an actual fill are separate events.

Therefore:

```text TriggeredStop
```

does not imply:

```text ExecutedAtStopPrice.
```

The execution model must explicitly bridge the two.

---

# 45. Slippage Integrity

If:

```text actual execution != reference execution
```

the difference must be reflected in:

```text execution impact.
```

The system cannot silently discard unfavorable execution differences.

---

# 46. Data Quality Invariant

A missing critical field must not silently become:

```text 0
```

unless zero is semantically valid and explicitly encoded as such.

For example:

```text MissingBid != Bid = 0.
```

This distinction is mandatory.

---

# 47. Invalid Event Handling

If an event violates its schema:

```text event rejected
```

or:

```text event quarantined.
```

It must not silently mutate trading state.

---

# 48. Event Sequence Integrity

An event requiring a prerequisite state cannot be processed if that prerequisite does not exist.

For example:

```text EXIT_FILL
```

cannot normally occur for:

```text TradeID with no corresponding order/exposure
```

without triggering reconciliation.

---

# 49. Impossible Transition Detection

The following are invalid:

```text NO_POSITION -> EXIT_FILLED
NO_POSITION -> ACTIVE without fill
ACTIVE -> NO_POSITION without exit execution
CLOSED -> ACTIVE
```

unless an explicit correction/reopening mechanism exists.

---

# 50. State Transition Totality

For every valid:

```text State × Event
```

combination, the system must define one of:

```text valid transition
ignored event
queued event
rejected event
reconciliation state
system halt.
```

There must be no undefined behavior.

---

# 51. Safety Over Ambiguity

When the system cannot determine which state is correct:

```text uncertainty
```

must not be resolved through optimistic assumptions.

The preferred response is:

```text RECONCILIATION_REQUIRED
```

or:

```text SYSTEM_HALT
```

depending on severity.

---

# 52. System Halt Invariant

If a critical invariant is violated:

```text trading continues = FALSE
```

until the violation is resolved according to the operational protocol.

A system that knows its state is invalid must not continue trading blindly.

---

# 53. Data-Feed Failure

A temporary market-data failure does not imply:

```text position = 0.
```

The last authoritative position remains valid until execution evidence says otherwise.

---

# 54. Broker Failure

Likewise, a broker API failure does not imply:

```text order cancelled.
```

The system must distinguish:

```text unknown status
```

from:

```text confirmed cancellation.
```

---

# 55. Reconciliation Priority

When internal state conflicts with authoritative external execution state:

```text authoritative execution state
```

takes precedence for exposure determination.

The internal state is corrected.

---

# 56. No Future Leakage Through Reconciliation

A later broker correction cannot retroactively become an input to an earlier decision.

It may:

```text correct historical execution accounting
```

but it cannot be used to claim:

```text the strategy knew this information earlier.
```

---

# 57. Research/Trading Separation

Research artifacts cannot directly mutate live trading state.

Similarly:

```text live trading outcome
```

cannot automatically modify research parameters unless an explicitly validated adaptation mechanism authorizes it.

---

# 58. Live/Learning Separation

A newly completed trade does not immediately become a training observation if its label is immature.

Therefore:

```text TradeClosed
```

does not imply:

```text LearningEligible.
```

---

# 59. Learning Update Atomicity

A learning update must be atomic with respect to its:

```text dataset
model version
parameter version
training cutoff.
```

A partially updated model must never become the active model.

---

# 60. Model Promotion Atomicity

A model becomes active only when:

```text validation passed
+
promotion authorized
+
model artifact complete.
```

There must be no intermediate state where:

```text half-old model
+
half-new parameters
```

are used.

---

# 61. Numerical Domain Invariants

All mathematical variables must remain within valid domains.

Examples:

```text Probability ∈ [0,1]

Quantity >= 0

RiskBudget >= 0

HoldingTime >= 0

Variance >= 0

Volatility >= 0

Confidence/credibility quantities within their defined domains.
```

Exact domains will be recorded in the canonical variable registry.

---

# 62. Unit Consistency

Every mathematical quantity must have a defined unit.

Examples:

```text price       -> ₹ / point
quantity       -> contracts/lots
time           -> milliseconds/seconds
probability    -> dimensionless
PnL            -> ₹
return         -> dimensionless
volatility     -> defined annualized/intraday convention.
```

An equation combining incompatible units is invalid.

---

# 63. No Duplicate Canonical Variables

Every concept must have exactly one canonical variable.

Previously identified examples:

```text CurrentPnL
ExpectedHorizon
```

must not have competing aliases with different semantics.

Derived representations may exist, but they must point to the canonical definition.

---

# 64. Dependency Acyclicity

Within each event-time slice, the dependency graph must remain acyclic.

If:

```text A -> B
B -> C
C -> A
```

without a legitimate temporal separation, the specification is invalid.

Temporal feedback is allowed only when represented explicitly:

```text State_t
   ->
State_(t+1).
```

---

# 65. Temporal DAG Rule

The system is not one static DAG.

It is:

```text DAG_t
+
StateTransition_t
+
DAG_(t+1)
```

This allows legitimate temporal feedback without creating an instantaneous circular dependency.

---

# 66. Example of Valid Feedback

A valid sequence:

```text Price_t
   ->
Probability_t
   ->
Decision_t
   ->
TradeState_t

Outcome_(t+1)
   ->
LearningUpdate_(t+1)
   ->
ProbabilityModel_(t+2)
```

This is causal.

---

# 67. Example of Invalid Feedback

This is forbidden:

```text FutureOutcome
   ->
Probability_t
   ->
Decision_t
```

because:

```text FutureOutcome
```

was not available at `t`.

---

# 68. Opportunity Selection Invariant

The system must preserve the distinction between:

```text eligible opportunity
```

and:

```text executed trade.
```

A NO_TRADE outcome must remain an observable research observation.

---

# 69. No Survivorship Bias Through Opportunity Filtering

The system must not construct the historical dataset by retaining only opportunities that eventually became attractive.

Opportunity eligibility must be determined using information available at the opportunity timestamp.

---

# 70. No Selection Leakage

The decision to include an observation in training cannot depend on its eventual profitability.

Eligibility precedes outcome.

---

# 71. Cost Integrity

Expected transaction costs used at time `t` must be estimated from information available at `t`.

Actual future costs may be used for:

```text label/outcome analysis
```

but not:

```text historical decision construction.
```

---

# 72. Execution Feasibility Invariant

A trade cannot be considered economically valid if the historical execution model says the required transaction was infeasible.

The system must not generate profit from an unexecutable trade.

---

# 73. Stress-Test Independence

Stress assumptions used to evaluate robustness must not be tuned after seeing which stress scenario produces the desired conclusion.

The stress protocol is versioned.

---

# 74. Performance Metric Integrity

A performance metric must be calculated from the declared population.

For example:

```text WinRate
```

must not silently exclude losing trades.

Similarly:

```text Expectancy
```

must not exclude outliers unless the metric definition explicitly requires robust estimation.

---

# 75. No Cherry-Picking

Reports must not selectively display:

```text best months
best trades
best parameter
best regime
```

while omitting unfavorable periods.

The chronological full sample remains available.

---

# 76. Final Verification Categories

The complete verification suite should contain:

```text STATIC VERIFICATION
TEMPORAL VERIFICATION
ACCOUNTING VERIFICATION
CAUSALITY VERIFICATION
EXECUTION VERIFICATION
RISK VERIFICATION
LEARNING VERIFICATION
RESEARCH VERIFICATION
```

---

# 77. Static Verification

Static checks verify:

```text schema correctness
variable uniqueness
unit consistency
dependency acyclicity
state-transition completeness
```

before any historical simulation runs.

---

# 78. Temporal Verification

Temporal checks verify:

```text no future access
correct event ordering
label maturity
walk-forward boundaries
parameter effective dates
model promotion boundaries.
```

---

# 79. Accounting Verification

Accounting checks verify:

```text fills
position quantity
entry price
exit price
realized P&L
unrealized P&L
fees
```

remain mathematically consistent.

---

# 80. Causality Verification

For every decision variable:

```text dependency timestamp <= decision timestamp.
```

This should eventually be machine-auditable.

---

# 81. Execution Verification

Execution checks verify:

```text no fill without order
no duplicate fill accounting
no negative quantity
partial-fill correctness
cancellation-race handling
reconciliation.
```

---

# 82. Risk Verification

Risk checks verify:

```text protection monotonicity
risk budget
position sizing
mode/risk independence
exit obligation persistence.
```

---

# 83. Learning Verification

Learning checks verify:

```text mature labels only
training cutoff correctness
model versioning
parameter versioning
no test contamination
atomic promotion.
```

---

# 84. Research Verification

Research checks verify:

```text experiment registration
dataset immutability
primary metric immutability
multiple-testing accounting
holdout protection
result reproducibility.
```

---

# 85. Formal Property Set

The following properties become canonical:

```text INV-001  State validity
INV-002  Causal information
INV-003  Event ordering
INV-004  Event idempotency
INV-005  Position conservation
INV-006  No synthetic position
INV-007  No negative position
INV-008  Trade identity
INV-009  Closure correctness
INV-010  Exit-obligation persistence
INV-011  Protection monotonicity
INV-012  Mode/risk independence
INV-013  Risk-budget compliance
INV-014  Signal freshness
INV-015  Probability domain
INV-016  Label maturity
INV-017  Training boundary
INV-018  Final-holdout isolation
INV-019  Version integrity
INV-020  P&L integrity
INV-021  Peak-P&L monotonicity
INV-022  Giveback validity
INV-023  Execution-price integrity
INV-024  Missing-data integrity
INV-025  Impossible-transition detection
INV-026  Reconciliation safety
INV-027  Learning atomicity
INV-028  Unit consistency
INV-029  Canonical-variable uniqueness
INV-030  Temporal-DAG correctness
INV-031  Opportunity/trade separation
INV-032  Selection integrity
INV-033  Cost causality
INV-034  Execution feasibility
INV-035  Stress-test independence
INV-036  Performance-population integrity
INV-037  No cherry-picking
```

---

# 86. Synthetic Verification

Before using real historical data, every invariant should be tested against synthetic event sequences.

Examples:

```text duplicate fill
late fill
partial fill
cancel/fill race
missing quote
timestamp reversal
negative quantity
stop gap
model promotion during trade
immature label
future-information injection
```

The expected result is predetermined.

---

# 87. Adversarial State-Machine Testing

The verification engine should deliberately attempt to produce:

```text impossible state
```

rather than merely testing normal behavior.

For example:

```text fill without order
exit without position
position without fill
parameter update before promotion
future label before maturity
protection decrease
```

Every one must be rejected or routed to reconciliation.

---

# 88. Metamorphic Testing

Some transformations should leave results invariant.

For example:

```text Duplicate identical event
```

should not change final state.

Likewise, irrelevant events outside the trade's dependency set should not change the trade outcome.

These are powerful correctness tests.

---

# 89. Conservation Testing

The system should test conserved quantities.

For example:

```text total executed entry quantity
-
total executed exit quantity
=
final position quantity.
```

If the equality fails:

```text reconciliation failure.
```

---

# 90. Replay Testing

A historical event stream should be replayable from:

```text t0
```

to:

```text tn
```

and produce a complete audit trail.

A replay should identify:

```text every state transition
every order
every fill
every decision
every learning update.
```

---

# 91. Fault Injection

The system should deliberately inject:

```text missing events
duplicate events
delayed events
out-of-order events
incorrect status
extreme prices
zero liquidity
```

and verify that the architecture responds safely.

---

# 92. Fail-Closed Principle

When critical information is uncertain:

```text NO_TRADE
```

or:

```text SAFE_HALT
```

is preferred over:

```text optimistic execution.
```

This principle applies particularly to:

```text data integrity
execution state
position reconciliation
risk state.
```

---

# 93. Formal Verification Does Not Prove Profitability

Passing all invariants establishes:

```text structural correctness.
```

It does not establish:

```text positive expectancy.
```

That remains an empirical question addressed by the validation protocol.

---

# 94. Formal Verification Does Not Prove Data Correctness

The state machine can be perfectly correct while the underlying market data is wrong.

Therefore:

```text Data Quality
```

remains an independent validation layer.

---

# 95. Formal Verification Does Not Prove Broker Behavior

Similarly, an execution simulator can be mathematically correct while its assumptions about actual broker execution are wrong.

The broker/TrueData contracts therefore remain external dependencies.

---

# 96. Verification Gate

Before implementation is allowed to proceed to live-capable execution logic:

```text all critical invariants
+
synthetic tests
+
adversarial tests
+
replay tests
```

must pass.

Non-critical unresolved TODOs may remain documented.

Critical invariant failures may not.

---

# 97. Final Safety Contract

The complete system must satisfy:

```text DATA
  |
  v
VALID EVENT
  |
  v
VALID STATE
  |
  v
VALID DECISION
  |
  v
VALID ORDER
  |
  v
VALID FILL
  |
  v
VALID POSITION
  |
  v
VALID RISK STATE
  |
  v
VALID EXIT
  |
  v
VALID ACCOUNTING
  |
  v
VALID LABEL
  |
  v
VALID LEARNING UPDATE
  |
  v
VALID MODEL PROMOTION
```

A failure at any stage must prevent the invalid state from silently propagating downstream.

---

# 98. Architecture Status

At this point, the architecture has moved beyond ordinary strategy design.

We have now defined:

```text mathematical model
state model
temporal dependency model
state transitions
trade lifecycle
execution lifecycle
performance model
research protocol
formal invariants
verification framework
```

The major remaining task is no longer another strategy layer.

It is to turn these contracts into a **single integrated canonical specification** and then perform a final consistency audit across all documents.

---

# 99. Next Artifact

The next logical artifact is:

# CANONICAL SPECIFICATION INTEGRATION AND CONSISTENCY AUDIT

This will be a deliberate cross-document attack.

We will construct one unified dependency and contract matrix and check:

```text every variable has one definition
every variable has one owner
every input has a source
every derived quantity has dependencies
every state has legal transitions
every transition has required inputs
every learned quantity has a label
every label has a maturity rule
every parameter has a version
every parameter has a training boundary
every execution quantity has provenance
every performance metric has a population
every invariant has a verification test
every unresolved TODO is explicitly isolated
```

Most importantly, we will search for contradictions between the documents we have already created.

For example:

```text Does the performance model assume a price that
the execution model says is unavailable?

Does the learning model use a variable that the state model
doesn't actually maintain?

Does the state machine permit a transition that the risk
invariants prohibit?

Does the label specification accidentally require information
that the execution model makes unavailable?

Does the research protocol permit an adaptation that the
model-version rules prohibit?

Does any supposedly "historical" variable actually contain
future information?
```

That consistency audit is the correct next step before implementation.

At that point, rather than continuing to invent more architecture, we should have one canonical system specification with contradictions and unresolved external dependencies explicitly exposed.