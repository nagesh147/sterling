# CANONICAL INVARIANT AND PROPERTY REGISTRY

## Version 1.0

## 1. Purpose

This registry is the formal correctness layer of the strategy.

Every important property receives:

```text
Invariant ID
Definition
Mathematical condition
Affected state
Triggering events
Permitted transition
Forbidden transition
Failure severity
Verification method
```

The registry is implementation-independent.

The implementation is considered correct only if its observable behavior satisfies these invariants.

---

# 2. Severity Classes

Every invariant has one of four severities:

```text
FATAL
CRITICAL
MAJOR
INFORMATIONAL
```

`FATAL` means the strategy cannot safely continue.

`CRITICAL` means normal operation must stop or transition to a protected state.

`MAJOR` means the affected subsystem cannot continue normally.

`INFORMATIONAL` records behavior that does not directly compromise safety.

---

# 3. Causal Invariants

## INV-CAUSAL-001 — No Future Information

For every decision at timestamp `t`:

```text
Decision_t
=
F(InformationAvailableAt(t))
```

No information whose availability time is greater than `t` may influence the decision.

Severity:

```text FATAL
```

---

## INV-CAUSAL-002 — Feature Availability

For every feature `X`:

```text
AvailabilityTime(X) <= DecisionTime
```

must hold before `X` enters the decision state.

Otherwise:

```text feature invalid.
```

Severity:

```text FATAL
```

---

## INV-CAUSAL-003 — Label Maturity

For every historical training observation:

```text LabelMaturityTime <= TrainingCutoffTime
```

must hold.

Severity:

```text FATAL
```

---

## INV-CAUSAL-004 — Historical Immutability

Once a historical decision has been recorded:

```text DecisionSnapshot_t
```

cannot be altered by future events.

Severity:

```text FATAL
```

---

## INV-CAUSAL-005 — Model Version Immutability

A decision generated under:

```text ModelVersion = V
```

must permanently retain:

```text ModelVersion = V.
```

Severity:

```text CRITICAL
```

---

# 4. Event Integrity Invariants

## INV-EVENT-001 — Valid Timestamp

Every market event used by the state machine must have a valid event timestamp.

Invalid:

```text null
ambiguous
non-monotonic without explicit ordering handling
```

Severity:

```text CRITICAL
```

---

## INV-EVENT-002 — Event Identity

Where the data source provides event identity, duplicate events must not produce duplicate state transitions.

Formally:

```text Process(EventID)
```

is idempotent.

Severity:

```text CRITICAL
```

---

## INV-EVENT-003 — No Invented Event

Missing data cannot silently become an observed market event.

For example:

```text missing tick != zero-price tick
```

Severity:

```text CRITICAL
```

---

## INV-EVENT-004 — Invalid Market Data

An event violating the instrument's data contract cannot enter the mathematical state.

Examples:

```text impossible price
invalid quantity
invalid timestamp
invalid instrument identity
```

Severity:

```text CRITICAL
```

---

# 5. State-Machine Invariants

## INV-STATE-001 — State Must Be Reachable

Every state must have a defined predecessor and transition condition.

No implementation may create an undocumented state.

Severity:

```text FATAL
```

---

## INV-STATE-002 — One Canonical State

At any event timestamp, the strategy must have exactly one canonical position state.

It cannot simultaneously be:

```text NO_POSITION
```

and:

```text POSITION_ACTIVE.
```

Severity:

```text FATAL
```

---

## INV-STATE-003 — Deterministic Transition

Given:

```text PreviousState
+
Event
+
ModelVersion
```

the resulting mathematical state must be uniquely determined.

Severity:

```text CRITICAL
```

---

## INV-STATE-004 — No Impossible Transition

A transition not explicitly permitted by the state machine is forbidden.

Example:

```text NO_POSITION -> POSITION_CLOSED
```

without an active trade is invalid.

Severity:

```text FATAL
```

---

## INV-STATE-005 — State Replay

Given identical:

```text initial state
event sequence
model versions
execution responses
```

the resulting state sequence must be identical.

Severity:

```text CRITICAL
```

---

# 6. Position Invariants

## INV-POS-001 — Active Means Actual Exposure

```text PositionState = ACTIVE
```

requires:

```text ConfirmedQuantity > 0
```

Severity:

```text FATAL
```

---

## INV-POS-002 — No Negative Quantity

For a long-only position:

```text Quantity >= 0
```

must always hold.

Severity:

```text FATAL
```

---

## INV-POS-003 — Entry Requires Fill

An order submission cannot create a position.

Only an actual execution can create exposure.

```text ORDER_SUBMITTED
!=
POSITION_ACTIVE
```

Severity:

```text FATAL
```

---

## INV-POS-004 — Closure Requires Zero Exposure

```text TradeClosed => ConfirmedQuantity = 0
```

Severity:

```text FATAL
```

---

## INV-POS-005 — No Implicit Position Flip

An exit followed by an opposite-direction entry requires:

```text confirmed zero exposure
+
independent new entry authorization.
```

Severity:

```text CRITICAL
```

---

# 7. Entry Invariants

## INV-ENTRY-001 — Entry Requires Complete Eligibility

A trade may be authorized only when all mandatory entry predicates are satisfied:

```text valid market state
+
valid probability state
+
valid economic state
+
valid option selection
+
valid risk capacity
+
valid execution conditions.
```

Severity:

```text FATAL
```

---

## INV-ENTRY-002 — No Stale Authorization

An entry authorization has a defined validity condition.

If material conditions invalidate it:

```text authorization expires.
```

Severity:

```text CRITICAL
```

---

## INV-ENTRY-003 — One Entry Instance

The same opportunity cannot generate multiple independent entries unless explicit pyramiding is later introduced.

Baseline:

```text one active position per strategy instance.
```

Severity:

```text CRITICAL
```

---

# 8. Probability Invariants

## INV-PROB-001 — Probability Domain

For a probability:

```text 0 <= P <= 1
```

must always hold.

Severity:

```text FATAL
```

---

## INV-PROB-002 — Invalid Probability Rejection

Values such as:

```text NaN
infinity
undefined
outside [0,1]
```

cannot enter economic decision logic.

Severity:

```text CRITICAL
```

---

## INV-PROB-003 — Probability Does Not Override Hard Risk

Even:

```text P = 1
```

cannot override:

```text hard protection
execution failure
data invalidity
session boundary
```

Severity:

```text FATAL
```

---

## INV-PROB-004 — Probability Is Not Certainty

The system must never transform:

```text P = 0.80
```

into:

```text guaranteed outcome.
```

The probability remains an estimate.

Severity:

```text MAJOR
```

---

# 9. Economic Invariants

## INV-ECO-001 — Net Economics

Entry decisions must use the defined net economic quantity:

```text ExpectedBenefit
-
ExpectedLoss
-
ExecutionCost
-
TransactionCost
```

rather than gross directional prediction alone.

Severity:

```text FATAL
```

---

## INV-ECO-002 — Positive Direction Is Insufficient

A correct directional prediction does not imply a valid option trade.

The option must independently satisfy the economic contract.

Severity:

```text CRITICAL
```

---

## INV-ECO-003 — Executability

A theoretical positive EV does not authorize a trade if execution conditions violate the defined economic boundary.

Severity:

```text CRITICAL
```

---

## INV-ECO-004 — Uncertainty Matters

A positive point estimate with insufficient statistical evidence cannot automatically authorize a trade.

Severity:

```text MAJOR
```

---

# 10. P&L Invariants

## INV-PNL-001 — Actual Fill Truth

Realized P&L must be calculated from:

```text actual entry fills
actual exit fills
actual quantities
actual costs.
```

Severity:

```text FATAL
```

---

## INV-PNL-002 — Current and Realized P&L Separation

While exposure exists:

```text RealizedPnL
```

and:

```text CurrentPnL
```

must remain distinct.

Severity:

```text CRITICAL
```

---

## INV-PNL-003 — Closed P&L Immutability

After final reconciliation:

```text RealizedPnL
```

cannot change unless a genuine correction event occurs under an explicitly defined correction protocol.

Severity:

```text CRITICAL
```

---

## INV-PNL-004 — Partial Exit Accounting

A partial exit must produce:

```text realized component
+
remaining exposure
```

rather than treating the entire position as closed.

Severity:

```text CRITICAL
```

---

# 11. Peak and Drawdown Invariants

## INV-PEAK-001 — Peak Profit Monotonicity

For a long position:

```text PeakPnL_t >= PeakPnL_(t-1)
```

Severity:

```text CRITICAL
```

---

## INV-PEAK-002 — New High Updates Peak

If:

```text CurrentPnL > PeakPnL
```

then:

```text PeakPnL = CurrentPnL.
```

Severity:

```text CRITICAL
```

---

## INV-PEAK-003 — Drawdown From Peak

```text ProfitGiveback
=
PeakPnL - CurrentPnL
```

when:

```text CurrentPnL < PeakPnL.
```

Severity:

```text MAJOR
```

---

# 12. Protection Invariants

These are among the most important invariants in the entire strategy.

## INV-RISK-001 — Protection Monotonicity

For an existing long position:

```text Protection_t >= Protection_(t-1)
```

unless the position is reset because it has actually closed.

Severity:

```text FATAL
```

---

## INV-RISK-002 — Mode Cannot Widen Protection

A transition:

```text INTRADAY -> SCALP
```

or:

```text SCALP -> INTRADAY
```

cannot weaken an already-established protection boundary.

Severity:

```text FATAL
```

---

## INV-RISK-003 — Probability Cannot Widen Protection

Improved expected continuation cannot reduce already-locked protection.

Severity:

```text FATAL
```

---

## INV-RISK-004 — Volatility Cannot Widen Protection

An increase in estimated ATR or volatility cannot cause the actual protection boundary to move backward.

It may alter the candidate protection calculation.

It cannot override the monotonic floor.

Severity:

```text FATAL
```

---

## INV-RISK-005 — Protection Is Not Guaranteed Execution

The protection boundary represents an exit obligation/trigger.

It does not guarantee an equal execution price.

Severity:

```text CRITICAL
```

---

## INV-RISK-006 — Risk Cannot Increase After Profit Lock

Once the strategy has established a protected profit boundary, future state transitions cannot intentionally increase the maximum permitted giveback.

Severity:

```text FATAL
```

---

# 13. Mode Invariants

## INV-MODE-001 — Mode Is Descriptive

Mode describes the currently inferred continuation horizon.

It does not itself authorize additional risk.

Severity:

```text CRITICAL
```

---

## INV-MODE-002 — Mode Cannot Change Position Size

After entry:

```text mode transition
```

cannot increase position quantity.

Severity:

```text FATAL
```

---

## INV-MODE-003 — Mode Hysteresis

A mode transition must satisfy the validated persistence/sensitivity contract.

A single noisy event cannot automatically cause arbitrary oscillation.

Severity:

```text MAJOR
```

---

## INV-MODE-004 — Backward Transition Permitted

The state machine must permit:

```text INTRADAY -> SCALP
SCALP -> MICRO
```

when the corresponding conditions are satisfied.

Severity:

```text CRITICAL
```

---

## INV-MODE-005 — Backward Transition Cannot Reverse Risk Protection

Even when horizon shortens:

```text Protection_new >= Protection_old.
```

Severity:

```text FATAL
```

---

# 14. Exit Invariants

## INV-EXIT-001 — Hard Risk Has Priority

If a hard risk condition and a favorable continuation condition occur simultaneously:

```text hard risk condition wins.
```

Severity:

```text FATAL
```

---

## INV-EXIT-002 — Exit Obligation Is Sticky

Once a mandatory exit condition is established:

```text later favorable information
```

cannot erase the exit obligation.

Severity:

```text FATAL
```

---

## INV-EXIT-003 — Exit Requires Actual Execution for Closure

```text EXIT_AUTHORIZED
```

does not equal:

```text TRADE_CLOSED.
```

Closure requires confirmed zero exposure.

Severity:

```text FATAL
```

---

## INV-EXIT-004 — Partial Exit Preserves Remaining Risk

After a partial fill:

```text RemainingQuantity
```

continues to be managed under the applicable risk policy.

Severity:

```text CRITICAL
```

---

# 15. Execution Invariants

## INV-EXEC-001 — Broker Truth

Actual exposure is determined by authoritative execution/broker state according to the execution contract.

Severity:

```text FATAL
```

---

## INV-EXEC-002 — No Assumed Fill

An order cannot be treated as filled because:

```text order was submitted
```

or:

```text market appeared favorable.
```

Severity:

```text FATAL
```

---

## INV-EXEC-003 — Quantity Conservation

Across fills:

```text EntryQuantity
-
ExecutedExitQuantity
=
RemainingQuantity
```

subject to explicitly modeled adjustments.

Severity:

```text FATAL
```

---

## INV-EXEC-004 — No Over-Exit

The cumulative exit quantity cannot intentionally exceed confirmed exposure.

Severity:

```text FATAL
```

---

## INV-EXEC-005 — Unknown Execution State

If execution status is unknown:

```text UNKNOWN
```

must remain a valid state.

The engine cannot invent:

```text FILLED
```

or:

```text CANCELLED.
```

Severity:

```text CRITICAL
```

---

## INV-EXEC-006 — Reconciliation Before New Exposure

After an execution-state discrepancy:

```text reconciliation
```

must precede new exposure.

Severity:

```text FATAL
```

---

# 16. Data Failure Invariants

## INV-DATA-001 — Missing Is Not Zero

Missing data cannot silently become zero.

Severity:

```text CRITICAL
```

---

## INV-DATA-002 — Stale Data Is Not Current Data

A feature exceeding its defined freshness boundary must be marked stale.

Severity:

```text CRITICAL
```

---

## INV-DATA-003 — Data Failure Cannot Reset Risk

If critical data disappears while a position is active:

```text existing protection
```

cannot disappear merely because the feature stream failed.

Severity:

```text FATAL
```

---

## INV-DATA-004 — Recovery Requires Revalidation

After data recovery:

```text current state
```

must be reconstructed/revalidated before normal decision-making resumes.

Severity:

```text CRITICAL
```

---

# 17. Session Invariants

## INV-SESSION-001 — Session Boundary

No new position may be opened when insufficient valid session time remains according to the operational contract.

Severity:

```text CRITICAL
```

---

## INV-SESSION-002 — Mandatory Session Closure

Baseline strategy:

```text no overnight position.
```

All exposure must enter the session-termination exit process.

Severity:

```text FATAL
```

---

# 18. Learning Invariants

## INV-LEARN-001 — Matured Data Only

A historical outcome can enter model training only after all required future information has matured.

Severity:

```text FATAL
```

---

## INV-LEARN-002 — Point-in-Time Training

Training data must reconstruct what was actually knowable at the historical decision timestamp.

Severity:

```text FATAL
```

---

## INV-LEARN-003 — Temporal Train/Validation/Test Separation

Chronological boundaries must be preserved.

Severity:

```text FATAL
```

---

## INV-LEARN-004 — No Test Feedback

Test outcomes cannot influence:

```text parameter selection
feature selection
model selection
training-window selection.
```

Severity:

```text FATAL
```

---

## INV-LEARN-005 — Candidate Registry

Every tested candidate must be recorded.

This prevents invisible multiple testing.

Severity:

```text CRITICAL
```

---

## INV-LEARN-006 — Failed Experiments Remain Recorded

A failed experiment cannot simply disappear from the research history.

Severity:

```text MAJOR
```

---

## INV-LEARN-007 — Rare-State Uncertainty

Insufficient historical evidence cannot be converted into artificial confidence.

Severity:

```text CRITICAL
```

---

## INV-LEARN-008 — Trade Outcomes Are Not the Entire Dataset

The learning system must distinguish:

```text all evaluated opportunities
```

from:

```text executed trades.
```

Severity:

```text MAJOR
```

---

# 19. Model Invariants

## INV-MODEL-001 — Model Version Immutability

A deployed model version cannot change internally after deployment.

Severity:

```text FATAL
```

---

## INV-MODEL-002 — Candidate Is Not Active

A candidate model cannot influence production decisions until it passes the promotion contract.

Severity:

```text CRITICAL
```

---

## INV-MODEL-003 — Challenger Isolation

A shadow/challenger model cannot alter production decisions while in evaluation.

Severity:

```text CRITICAL
```

---

## INV-MODEL-004 — Model Reproducibility

Given identical:

```text data version
feature definitions
parameters
training window
model specification
```

the model must be reproducible.

Severity:

```text CRITICAL
```

---

# 20. Replay Invariants

## INV-REPLAY-001 — Deterministic State Replay

Identical event streams must produce identical state transitions.

Severity:

```text CRITICAL
```

---

## INV-REPLAY-002 — Future Event Independence

Appending future events to a replay cannot alter decisions already made.

Severity:

```text FATAL
```

---

# 21. Accounting Invariants

## INV-ACCOUNT-001 — Entry Price Is Immutable

Once actual entry fills are established:

```text EntryPrice
```

cannot be rewritten because of later market movement.

Severity:

```text FATAL
```

---

## INV-ACCOUNT-002 — Entry Timestamp Is Immutable

The actual entry timestamp remains the timestamp established by the execution record.

Severity:

```text CRITICAL
```

---

## INV-ACCOUNT-003 — Peak Is Historical

A later decline cannot reduce recorded historical peak.

Severity:

```text CRITICAL
```

---

## INV-ACCOUNT-004 — Realized P&L Uses Realized Fills

Unrealized prices cannot be substituted for actual exit fills when calculating realized P&L.

Severity:

```text FATAL
```

---

# 22. Option-Specific Invariants

## INV-OPT-001 — Directional Forecast Is Not Option Selection

A bullish underlying forecast cannot directly imply:

```text BUY_CE
```

without passing the option-selection contract.

Severity:

```text CRITICAL
```

---

## INV-OPT-002 — Executable Option Economics

The selected option must satisfy:

```text expected movement
>
option economic burden
```

under the formal net-EV definition.

Severity:

```text CRITICAL
```

---

## INV-OPT-003 — Option Liquidity

The option must satisfy the validated execution/liquidity requirements.

Otherwise:

```text NO_TRADE.
```

Severity:

```text CRITICAL
```

---

# 23. Numerical Integrity Invariants

## INV-NUM-001 — No Undefined Arithmetic

Operations producing:

```text NaN
infinity
division by zero
undefined quantity
```

must be rejected or explicitly handled.

Severity:

```text FATAL
```

---

## INV-NUM-002 — Units Must Match

Quantities such as:

```text price
points
rupees
percentage
probability
time
quantity
```

must never be silently combined as if dimensionally identical.

Severity:

```text CRITICAL
```

---

# 24. Priority Ordering

When multiple conditions occur on the same event, the system follows this conceptual priority:

```text 1. Data / State Integrity
2. Exposure Reconciliation
3. Hard Risk Protection
4. Mandatory Session Exit
5. Emergency Exit
6. Normal Exit
7. Position Management
8. Mode Reclassification
9. Continuation Evaluation
10. New Entry Evaluation
11. Learning Eligibility
```

This ordering prevents a lower-priority optimization from overriding a higher-priority safety condition.

---

# 25. Important Consequence

A profitable continuation signal cannot override:

```text hard exit.
```

A mode transition cannot override:

```text protection.
```

A new model cannot override:

```text execution truth.
```

A historical outcome cannot override:

```text information chronology.
```

These are architectural properties, not tuning parameters.

---

# 26. Invariant Dependency

The invariants themselves form a hierarchy:

```text Data Integrity
      |
      v
Temporal Integrity
      |
      v
State Integrity
      |
      v
Position Integrity
      |
      v
Risk Integrity
      |
      v
Economic Integrity
      |
      v
Execution Integrity
      |
      v
Learning Integrity
```

A lower layer cannot legitimately compensate for a violation in a higher layer.

---

# 27. Example

If:

```text Data Integrity = FAILED
```

we cannot say:

```text Probability = strong,
therefore trade anyway.
```

The correct result is:

```text no normal decision.
```

---

# 28. Hard Safety Boundary

The following are absolute:

```text No future information.
No negative quantity.
No position without fill.
No closure without zero exposure.
No protection widening.
No over-exit.
No fabricated execution.
No test contamination.
No retroactive model mutation.
```

These are not learned.

---

# 29. Learned Boundary

The following remain empirical:

```text Entry probability threshold
Continuation threshold
Profit-floor quantile
Emergency reversal threshold
Mode transition sensitivity
Mode persistence
Hysteresis
Training window
Retraining frequency
Execution tolerance
```

The learning process chooses these.

The invariants constrain what those learned values are allowed to do.

---

# 30. Fundamental Separation

This gives us a crucial architecture:

```text LEARNING
determines:
"How aggressive should the strategy be?"

INVARIANTS
determine:
"What is the strategy never allowed to violate?"
```

Learning operates inside the invariant boundary.

It cannot redefine the boundary.

---

# 31. Verification Requirement

Every future implementation component must map to one or more registry IDs.

For example:

```text Risk Engine
    -> INV-RISK-001
    -> INV-RISK-002
    -> INV-RISK-003
    -> INV-RISK-004
    -> INV-RISK-005
    -> INV-RISK-006
```

The implementation is incomplete if any applicable invariant has no verification mechanism.

---

# 32. Final Registry Contract

The implementation phase will therefore not begin with:

```text "Write the trading strategy."
```

It begins with:

```text "Implement the canonical state machine
such that every mandatory invariant is mechanically testable."
```

That is a materially stronger engineering requirement.

---

# 33. Current Architecture Status

At this point we have:

```text Mathematical Specification
        |
        v
Variable Registry
        |
        v
Dependency DAG
        |
        v
State Transition Specification
        |
        v
Historical Label Specification
        |
        v
Adversarial Attack Specification
        |
        v
Synthetic Scenario Suite
        |
        v
Invariant Registry
```

The architecture is now approaching implementation-grade completeness.

---

# 34. The Next Artifact

The next logical artifact is **not another strategy rule**.

It is the:

```text CANONICAL DECISION PRIORITY AND CONFLICT-RESOLUTION SPECIFICATION
```

This will answer the remaining subtle question:

```text What happens when several mathematically valid conditions
become true on the same event?
```

For example:

```text continuation says HOLD
protection says EXIT
mode says INTRADAY
session says CLOSE
execution says unavailable
```

We need one exact ordering and conflict-resolution mechanism.

Without that, two individually correct modules could produce contradictory actions.

That specification will turn the current collection of correct rules into **one deterministic decision system**.