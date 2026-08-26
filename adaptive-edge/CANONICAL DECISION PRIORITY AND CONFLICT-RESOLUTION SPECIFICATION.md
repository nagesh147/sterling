# CANONICAL DECISION PRIORITY AND CONFLICT-RESOLUTION SPECIFICATION

## Version 1.0

## 1. Purpose

At any event, several conditions can become true simultaneously.

For example:

```text
Probability says: HOLD
Continuation says: HOLD
Mode says: INTRADAY
Protection says: EXIT
Session says: CLOSE
Execution says: unavailable
```

The system cannot execute all of these instructions.

Therefore every event must pass through a deterministic priority mechanism.

The result must be exactly one canonical decision:

```text
NO_ACTION
ENTER
HOLD
MODIFY_PROTECTION
EXIT
RECONCILE
HALT_NORMAL_OPERATION
```

with execution states handled separately.

---

# 2. Fundamental Rule

The system does not ask:

```text "Which signal is strongest?"
```

It asks:

```text "Which obligation has the highest priority?"
```

This distinction is fundamental.

A strong prediction is not an obligation to trade.

A hard risk condition is an obligation to reduce exposure.

---

# 3. Decision Priority Hierarchy

The canonical priority order is:

```text
P0  SYSTEM / DATA INTEGRITY
P1  EXPOSURE RECONCILIATION
P2  HARD RISK PROTECTION
P3  SESSION TERMINATION
P4  EMERGENCY REVERSAL
P5  NORMAL EXIT
P6  PROTECTION UPDATE
P7  POSITION HOLD / CONTINUATION
P8  MODE TRANSITION
P9  NEW ENTRY
P10 LEARNING / MODEL UPDATE
```

Higher priority always dominates lower priority on the same event.

---

# 4. P0 — System and Data Integrity

This is the highest level.

Examples:

```text invalid event
corrupt state
invalid timestamp
invalid price
invalid probability
critical feature failure
state invariant violation
```

Expected action:

```text HALT_NORMAL_OPERATION
```

The system must not continue making ordinary trading decisions using invalid state.

---

# 5. Example

Suppose:

```text Probability = 0.85
EV > threshold
Mode = SCALP
```

but:

```text timestamp invalid.
```

Expected:

```text NO_ENTRY
```

The attractive market signal is irrelevant.

---

# 6. P0 Does Not Necessarily Mean "Sell Immediately"

This distinction matters.

If there is:

```text NO_POSITION
```

the result may simply be:

```text NO_TRADE.
```

If there is:

```text ACTIVE_POSITION
```

the system follows the predefined protective/reconciliation policy.

Data failure cannot erase existing risk obligations.

---

# 7. P1 — Exposure Reconciliation

If internal exposure and authoritative execution state disagree:

```text RECONCILIATION_REQUIRED
```

takes precedence over normal trading.

Examples:

```text internal quantity = 100
broker quantity = 60
```

or:

```text internal order status = UNKNOWN
broker status = ACTIVE.
```

Expected:

```text reconcile first.
```

---

# 8. New Entry During Reconciliation

If:

```text NO_POSITION internally
```

but broker state is uncertain:

```text NO_ENTRY.
```

The system cannot establish new exposure until the actual exposure state is known.

---

# 9. Existing Position During Reconciliation

If:

```text internal = 100
broker = unknown
```

normal optimization is suspended.

Existing risk obligations remain active.

---

# 10. P2 — Hard Risk Protection

This is the highest trading priority.

Examples:

```text protection boundary breached
mandatory emergency protection
exposure exceeds allowed risk
```

Expected:

```text EXIT_REQUIRED.
```

---

# 11. Prediction Cannot Override Hard Risk

Suppose:

```text P(up) = 0.95
Continuation = strongly positive
```

but:

```text hard protection breached.
```

Expected:

```text EXIT.
```

The system does not reinterpret the risk breach because the prediction remains favorable.

---

# 12. P3 — Session Termination

If:

```text mandatory session closure
```

becomes active, the position must enter the closure process.

This outranks:

```text HOLD
mode extension
continuation
new entry.
```

---

# 13. Example

At the final permitted trading boundary:

```text continuation = extremely strong.
```

Expected:

```text EXIT.
```

No new entry may be initiated.

---

# 14. P4 — Emergency Reversal

An emergency reversal condition represents a sufficiently strong deterioration in the expected continuation of the existing position.

If its validated condition is satisfied:

```text EXIT_REQUIRED.
```

This is below hard protection but above ordinary continuation optimization.

---

# 15. Emergency Reversal Cannot Be Ignored

Suppose:

```text protection = not breached
```

but:

```text emergency reversal condition = TRUE.
```

Expected:

```text EXIT.
```

The strategy does not wait for the stop merely because the stop has not been reached.

---

# 16. P5 — Normal Exit

Normal exit conditions include:

```text continuation value below threshold
economic value no longer sufficient
validated time/opportunity exhaustion
ordinary exit condition.
```

Expected:

```text EXIT_REQUIRED.
```

---

# 17. Multiple Exit Conditions

If several exit conditions are simultaneously true:

```text HARD_RISK
EMERGENCY_REVERSAL
NORMAL_EXIT
```

the canonical reason is the highest-priority one.

For example:

```text HARD_RISK > EMERGENCY_REVERSAL > NORMAL_EXIT.
```

The system must retain the other triggered conditions as secondary evidence.

---

# 18. Exit Reason Must Be Immutable

Once the actual exit obligation is established:

```text ExitReason
```

is recorded.

Later information cannot rewrite:

```text why the exit was originally triggered.
```

---

# 19. P6 — Protection Update

If no mandatory exit condition exists, the system evaluates protection.

Conceptually:

```text CandidateProtection
=
f(
price,
volatility,
mode,
profit state,
continuation,
learned parameters
)
```

Then:

```text ActualProtection
=
max(
PreviousProtection,
CandidateProtection
)
```

for the long-position baseline.

---

# 20. Protection Update Does Not Mean Order Execution

A protection calculation can change the internal risk boundary without necessarily submitting a new broker order at every event.

The execution mechanism remains a separate concern.

---

# 21. Protection Update Versus Exit

If:

```text CandidateProtection >= current executable price
```

and the defined breach condition is satisfied:

the result is:

```text EXIT_REQUIRED
```

not:

```text MODIFY_PROTECTION.
```

---

# 22. P7 — Position Hold / Continuation

If no higher-priority obligation exists:

the system evaluates whether the current position remains economically valid.

Possible result:

```text HOLD.
```

---

# 23. HOLD Is an Active Decision

HOLD does not mean:

```text do nothing conceptually.
```

It means:

```text maintain exposure under the currently valid risk boundary.
```

State continues updating.

---

# 24. P8 — Mode Transition

If the position remains valid:

```text current mode
```

is reassessed.

Possible transition:

```text MICRO -> SCALP
SCALP -> EXTENDED_SCALP
EXTENDED_SCALP -> INTRADAY
INTRADAY -> SCALP
SCALP -> MICRO.
```

---

# 25. Mode Cannot Override HOLD/EXIT

Suppose:

```text Mode evidence says INTRADAY
```

but:

```text continuation value says EXIT.
```

Expected:

```text EXIT.
```

The mode transition is not allowed to keep the position alive.

---

# 26. Mode Is Evaluated Only After Position Validity

Therefore:

```text EXIT?
   |
   NO
   |
   v
Protection update
   |
   v
Continuation valid?
   |
   YES
   |
   v
Mode reassessment
```

This ordering prevents mode classification from overriding risk.

---

# 27. P9 — New Entry

Only when:

```text no active position
+
no reconciliation issue
+
valid market data
+
valid probability
+
valid economics
+
valid option
+
valid execution
+
valid risk capacity
+
valid session time
```

may a new entry be considered.

---

# 28. Entry Is the Lowest Trading Priority

This is intentional.

The strategy is designed to protect existing capital before searching for new opportunities.

---

# 29. P10 — Learning

Learning is the lowest operational priority.

A model update cannot interrupt an emergency exit.

It cannot override a live trading decision.

It cannot modify a historical decision.

---

# 30. Learning Is Asynchronous

Conceptually:

```text LIVE EVENT LOOP
        |
        +----> Trading state
        |
        +----> Execution state

LEARNING PIPELINE
        |
        +----> matured historical observations
        |
        +----> candidate model
        |
        +----> validation
        |
        +----> promotion
```

The two processes interact only through explicitly versioned contracts.

---

# 31. Canonical Conflict Rule

If multiple conditions produce different actions:

```text choose the highest-priority valid obligation.
```

All lower-priority conditions remain recorded.

They are not deleted.

---

# 32. Example

At one event:

```text HARD_EXIT = TRUE
NORMAL_EXIT = TRUE
MODE_CHANGE = TRUE
CONTINUATION = TRUE
```

Canonical action:

```text EXIT.
```

Recorded evidence:

```text hard risk
normal exit
mode transition candidate
continuation state
```

But only:

```text EXIT
```

becomes the canonical action.

---

# 33. Conflict Resolution Is Not Majority Voting

Suppose:

```text three models say HOLD
one risk module says EXIT.
```

The system does not count votes.

Risk priority determines the result.

---

# 34. No Weighted Averaging of Actions

We do not calculate:

```text 70% HOLD
30% EXIT
```

and somehow average them.

Actions are discrete state transitions.

The probabilities belong to prediction.

They do not define action voting.

---

# 35. Decision Object

Every event that reaches decision evaluation conceptually produces:

```text Decision
{
    canonical_action,
    primary_reason,
    secondary_conditions,
    state_before,
    state_after,
    model_version,
    timestamp
}
```

This is an audit object, not implementation code.

---

# 36. Primary Reason

Exactly one:

```text primary reason
```

is selected.

Example:

```text PRIMARY = HARD_RISK_EXIT.
```

---

# 37. Secondary Conditions

Any simultaneously true lower-priority conditions are retained.

Example:

```text PRIMARY:
HARD_RISK_EXIT

SECONDARY:
EMERGENCY_REVERSAL
CONTINUATION_FAILURE
MODE_CHANGE
```

This allows later analysis without ambiguity.

---

# 38. Decision Determinism

For identical:

```text state
+
event
+
model version
```

the same:

```text canonical action
```

must result.

---

# 39. Priority Is Not Learned

The priority ordering itself is not optimized by historical data.

For example:

```text HARD_RISK > ENTRY
```

is an architectural invariant.

We do not backtest:

```text maybe entry should outrank hard risk.
```

No.

---

# 40. Learned Quantities Operate Inside Priority

Learning may determine:

```text whether a condition is true.
```

It cannot determine:

```text whether a hard risk condition outranks entry.
```

---

# 41. Conflict: Protection Candidate Versus Emergency Exit

Suppose:

```text candidate protection = higher
```

but:

```text emergency reversal = TRUE.
```

Expected:

```text EXIT.
```

The protection update is irrelevant because the position is already obligated to exit.

---

# 42. Conflict: Protection Breach Versus Session Close

Both occur simultaneously.

Expected:

```text HARD_RISK_EXIT
```

with:

```text session termination = secondary condition.
```

---

# 43. Conflict: Emergency Reversal Versus Session Close

Both occur simultaneously.

Expected:

```text SESSION_EXIT
```

or:

```text EMERGENCY_EXIT
```

according to the formal priority:

```text SESSION > EMERGENCY
```

because the session boundary is an absolute operational constraint.

---

# 44. Conflict: Normal Exit Versus Mode Transition

Both are true.

Expected:

```text EXIT.
```

Mode transition is suppressed.

---

# 45. Conflict: Mode Transition Versus Protection Update

Both are valid.

Expected conceptual sequence:

```text evaluate mode
+
calculate protection candidate
```

but final protection must still satisfy:

```text Protection_new >= Protection_old.
```

Mode cannot weaken the result.

---

# 46. Conflict: Entry Versus Learning Update

Both become eligible at the same wall-clock time.

Expected:

```text entry decision uses currently active model.
```

The candidate model does not become active merely because training finished at the same time.

---

# 47. Model Promotion Boundary

A model becomes active only at an explicit:

```text ModelActivationTimestamp.
```

Before that timestamp:

```text old model remains active.
```

After it:

```text new model may be used.
```

This avoids ambiguous mid-event model switching.

---

# 48. Event Atomicity

Each market event must produce one logically atomic state transition.

Conceptually:

```text PreviousState
      +
Event
      |
      v
Decision Evaluation
      |
      v
Canonical Decision
      |
      v
NewState
```

Another event cannot be evaluated against a partially updated state.

---

# 49. Same-Timestamp Events

Multiple events may share a timestamp.

Therefore timestamp equality alone cannot determine ordering.

The data contract must eventually define:

```text deterministic event ordering key.
```

This remains a data-source implementation boundary item.

---

# 50. Event Ordering

If two events are genuinely simultaneous but affect different subsystems, the canonical event sequencing contract must define the order.

No implementation may choose arbitrarily.

---

# 51. Market Event Versus Execution Event

Execution events have different semantics from market events.

Example:

```text Market price crosses protection.
```

This may create:

```text EXIT_REQUIRED.
```

Then:

```text Broker fill event
```

determines:

```text actual position reduction.
```

These must not be conflated.

---

# 52. Trigger Versus Fact

This is a critical distinction.

A:

```text protection breach
```

is a:

```text trigger.
```

An:

```text exit fill
```

is a:

```text fact.
```

The trigger creates an obligation.

The fill changes actual exposure.

---

# 53. Trigger Cannot Pretend to Be Fact

Therefore:

```text EXIT_REQUIRED
```

does not mean:

```text POSITION_CLOSED.
```

---

# 54. Execution Failure

If an exit trigger occurs but execution fails:

```text EXIT_REQUIRED
+
POSITION_ACTIVE.
```

can coexist.

This is not an impossible state.

It is an exposed position with an unresolved exit obligation.

---

# 55. Exit Obligation State

The strategy therefore requires a distinction between:

```text ACTIVE
ACTIVE_EXIT_REQUIRED
EXIT_PENDING
PARTIALLY_EXITED
CLOSED
```

rather than treating everything as simply:

```text ACTIVE / CLOSED.
```

---

# 56. Exit Obligation Persistence

Once:

```text ACTIVE_EXIT_REQUIRED
```

is entered, ordinary continuation signals cannot return the position to:

```text NORMAL_ACTIVE.
```

until the exit obligation has been resolved according to the execution policy.

---

# 57. Critical Risk Principle

This is the exact formalization of the earlier discussion:

```text Prediction may change.
Mode may change.
Continuation may change.
Protection may tighten.

But an established mandatory exit obligation cannot be undone
by a later favorable prediction.
```

---

# 58. Entry Conflict

Suppose:

```text existing position = EXIT_PENDING
```

and a new signal appears.

Expected:

```text new entry blocked.
```

Until:

```text confirmed exposure = zero.
```

---

# 59. Why This Is Necessary

Otherwise:

```text old position
+
new position
```

could accidentally coexist due to an execution race.

The strategy would unknowingly increase exposure.

---

# 60. Capital Constraint Conflict

Suppose:

```text new entry signal = valid
```

but:

```text risk capacity = insufficient.
```

Expected:

```text NO_ENTRY.
```

The signal does not override capital constraints.

---

# 61. Option Selection Conflict

Suppose:

```text bullish signal = valid
```

but:

```text CE candidate fails liquidity/economic constraints.
```

Expected:

```text NO_TRADE.
```

The system does not automatically choose a poor option merely because direction is favorable.

---

# 62. CE Versus PE

The baseline decision set is:

```text BUY_CE
BUY_PE
NO_TRADE
```

The strategy does not have:

```text "somewhat bullish"
```

as an executable action.

Probability remains continuous.

Action is discrete.

---

# 63. No Simultaneous CE and PE

Baseline architecture:

```text one directional option position.
```

Therefore:

```text BUY_CE + BUY_PE
```

is not a valid simultaneous action.

---

# 64. Reversal

If a live:

```text BUY_CE
```

position becomes strongly bearish:

the system does not instantly create:

```text BUY_PE
```

while CE remains open.

Correct sequence:

```text EXIT CE
   |
   v
Confirm zero CE exposure
   |
   v
Evaluate new PE entry independently.
```

---

# 65. Conflict: Exit and Opposite Signal

Same event:

```text CE exit condition
+
PE entry condition.
```

Canonical sequence:

```text EXIT CE.
```

Then:

```text PE becomes a new candidate only after closure.
```

---

# 66. No Implicit Reversal

This prevents a subtle state-machine bug where:

```text old position quantity > 0
```

and:

```text opposite position quantity > 0
```

exist simultaneously when the architecture intended one position only.

---

# 67. Conflict: Data Failure During Exit

If:

```text EXIT_REQUIRED
```

has already been established and market data then disappears:

the exit obligation remains.

Data failure cannot erase the obligation.

---

# 68. Conflict: Data Failure Before Exit Trigger

If no mandatory exit exists but critical data disappears:

the system enters:

```text DATA_DEGRADED.
```

and follows the predefined protective policy.

It cannot manufacture a new probability.

---

# 69. Conflict: Learning Update During Data Failure

Model retraining requires complete eligible data.

If the dataset is incomplete:

```text model promotion blocked.
```

The existing active model remains unchanged.

---

# 70. Conflict: Model Health Failure During Position

A model may become degraded while a position remains active.

This does not automatically mean:

```text immediate exit.
```

unless the model-health contract explicitly defines it as an exit trigger.

The distinction is important.

Model uncertainty and position risk are different concepts.

---

# 71. Model Health Versus Risk

A degraded model may mean:

```text stop entering new trades
```

without necessarily meaning:

```text liquidate every existing position.
```

The exact response must be empirically validated.

But the architecture must keep these concepts separate.

---

# 72. Conflict: New Model Has Better Prediction

A newly promoted model predicts:

```text much stronger continuation.
```

Existing position's protection remains:

```text unchanged or tighter.
```

The new model cannot widen risk.

---

# 73. Conflict: New Model Predicts Exit

If the live model changes and produces:

```text normal exit condition
```

the position may exit according to the explicit live-model adoption policy.

However:

```text EntryModelVersion
```

remains immutable for attribution.

---

# 74. Conflict: New Model Predicts Entry While Existing Position Exists

Baseline:

```text no second entry.
```

The new signal is ignored as an executable action while exposure exists.

It may still be recorded as:

```text counterfactual opportunity.
```

---

# 75. Conflict: Multiple Data Sources

If two market feeds disagree:

the data contract must define:

```text authoritative source
```

or:

```text invalid/conflicted state.
```

The model cannot silently average incompatible truth sources.

---

# 76. Conflict: Market Data Versus Execution Data

For:

```text actual position
actual fill
realized P&L
```

execution records are authoritative.

For:

```text market state
```

the designated market-data source is authoritative.

---

# 77. Decision Output Hierarchy

The final canonical output can therefore be represented as:

```text SYSTEM_ERROR
RECONCILE
EXIT
MODIFY_PROTECTION
HOLD
CHANGE_MODE
NO_TRADE
ENTER
LEARNING_ONLY
```

But the internal reasoning retains all evaluated conditions.

---

# 78. Why EXIT Appears Above HOLD

Because:

```text HOLD
```

means:

```text exposure remains acceptable.
```

while:

```text EXIT
```

means:

```text exposure is no longer acceptable.
```

The two cannot be simultaneously executable.

---

# 79. Why ENTER Is Below Everything

Entry creates new risk.

Therefore it must lose every conflict against:

```text data integrity
reconciliation
risk
session
existing position
```

This is intentional risk asymmetry.

---

# 80. Why Learning Is Last

Learning has no immediate authority over live exposure.

It modifies future model versions through a controlled process.

It never outranks an active trading obligation.

---

# 81. Conflict Resolution Algorithm

Conceptually:

```text Event
  |
  v
Validate Event
  |
  +-- invalid --> SYSTEM/DATA FAILURE
  |
  v
Validate Exposure
  |
  +-- mismatch --> RECONCILE
  |
  v
Evaluate Hard Risk
  |
  +-- breached --> EXIT
  |
  v
Evaluate Session
  |
  +-- termination --> EXIT
  |
  v
Evaluate Emergency Reversal
  |
  +-- triggered --> EXIT
  |
  v
Evaluate Normal Exit
  |
  +-- triggered --> EXIT
  |
  v
Evaluate Protection
  |
  v
Evaluate Continuation
  |
  +-- invalid --> EXIT / DEGRADED POLICY
  |
  v
Evaluate Mode
  |
  v
Evaluate Entry
  |
  v
Record Learning Eligibility
```

---

# 82. Important Clarification

This is not pseudocode.

It is the **formal precedence relationship** between state-transition classes.

The eventual implementation may use any internal architecture, provided its observable behavior conforms to this ordering.

---

# 83. Conflict Resolution Invariant

We can now add:

```text INV-CONFLICT-001
```

For any event:

```text exactly one canonical action
```

must be selected from the permitted action set.

Severity:

```text FATAL.
```

---

# 84. Conflict Resolution Invariant

```text INV-CONFLICT-002
```

A lower-priority action cannot override a higher-priority active obligation.

Severity:

```text FATAL.
```

---

# 85. Conflict Resolution Invariant

```text INV-CONFLICT-003
```

Secondary conditions remain auditable even when they do not become the canonical action.

Severity:

```text MAJOR.
```

---

# 86. Conflict Resolution Invariant

```text INV-CONFLICT-004
```

The same:

```text state
+
event
+
model version
```

must produce the same canonical action.

Severity:

```text CRITICAL.
```

---

# 87. Conflict Resolution Invariant

```text INV-CONFLICT-005
```

A mandatory exit cannot be cancelled by a later lower-priority signal before the obligation is resolved.

Severity:

```text FATAL.
```

---

# 88. New Architectural Insight

We now have a very important separation:

```text PREDICTION
"What is likely?"

ECONOMICS
"Is the opportunity worth taking?"

RISK
"How much loss/giveback is acceptable?"

EXECUTION
"Can we actually transact?"

PRIORITY
"What obligation wins if they disagree?"
```

These are different mathematical questions.

---

# 89. Result

The complete strategy is no longer simply:

```text Signal -> Trade.
```

It is:

```text Event
  |
  v
State
  |
  +--> Prediction
  |
  +--> Economics
  |
  +--> Risk
  |
  +--> Execution
  |
  v
Conflict Resolution
  |
  v
Canonical Action
  |
  v
New State
```

---

# 90. Current Architecture Status

We now have:

```text Mathematical specification
Variable registry
Dependency graph
State-transition specification
Historical-label specification
Walk-forward learning specification
Adversarial attack specification
Synthetic scenario suite
Invariant registry
Decision-priority specification
```

The architecture is now internally coherent at the conceptual and mathematical level.

---

# 91. What We Should NOT Do Yet

We should not start coding immediately.

There is one particularly valuable exercise remaining before implementation:

```text FORMAL STATE-MACHINE COMPLETENESS AUDIT
```

We should enumerate **every state and every possible event class**, then verify that each `(state, event)` combination has exactly one defined outcome.

That will expose the final class of bugs that our previous tests can miss:

```text undefined transitions
dead-end states
unreachable states
duplicate transitions
contradictory transitions
transition cycles
states from which the system cannot recover
```

Once that matrix is complete, we will have something very close to a formal specification of the strategy rather than merely a collection of rules.