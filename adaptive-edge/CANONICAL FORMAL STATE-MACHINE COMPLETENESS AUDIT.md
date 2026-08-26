CANONICAL FORMAL STATE-MACHINE COMPLETENESS AUDIT

Version 1.0

Purpose

This audit verifies whether the five-step strategy is a closed deterministic temporal state machine.

The question is not whether the strategy is profitable.

The question is:

For every valid state and every relevant incoming event, does the specification define exactly one valid next state?

The canonical requirement is:

CARDINALITY(AllowedTransitions(S, E)) = 1

for every reachable state S and every valid event E.

If the cardinality is zero, the specification has an undefined transition.

If the cardinality is greater than one, the specification has a conflict.

Both are defects.

==================================================
1. CANONICAL STATE SPACE
==================================================

The strategy does not use one variable called "state".

The canonical state is a composition of several orthogonal state dimensions.

The primary trading-position dimension is:

NO_POSITION

ENTRY_AUTHORIZED

ENTRY_PENDING

ACTIVE

ACTIVE_EXIT_REQUIRED

EXIT_PENDING

PARTIALLY_EXITED

CLOSED_PENDING_RECONCILIATION

RECONCILIATION_REQUIRED

DATA_DEGRADED

SYSTEM_HALTED

These are operational states.

The position's analytical mode is a separate dimension:

NONE

MICRO

SCALP

EXTENDED_SCALP

INTRADAY

The mode does not replace the position state.

For example:

ACTIVE + MICRO

is valid.

ACTIVE + INTRADAY

is valid.

ENTRY_PENDING + MICRO

is not automatically valid because a position does not yet exist.

This separation prevents mode classification from becoming a hidden risk state.

==================================================
2. EVENT SPACE
==================================================

Every incoming event must belong to a defined event class.

The canonical classes are:

MARKET_EVENT

EXECUTION_EVENT

ORDER_STATUS_EVENT

BROKER_RECONCILIATION_EVENT

SESSION_EVENT

DATA_STATUS_EVENT

MODEL_EVENT

CLOCK_EVENT

LEARNING_EVENT

SYSTEM_EVENT

A market tick is therefore not equivalent to an execution fill.

A fill is not equivalent to an order acknowledgement.

A model promotion is not equivalent to a market event.

This distinction is mandatory.

==================================================
3. MARKET EVENT SUBCLASSES
==================================================

A valid market event can produce several types of information simultaneously.

Conceptually:

MARKET_EVENT
    |
    +-- price update
    +-- volume update
    +-- volatility update
    +-- underlying state update
    +-- option state update
    +-- liquidity update
    +-- derived-feature update
    +-- probability-state update

The actual TrueData field mapping remains intentionally unresolved until the data contract is supplied.

The state-machine contract does not depend on the vendor's field names.

==================================================
4. EXECUTION EVENT SUBCLASSES
==================================================

Execution events include:

ORDER_ACCEPTED

ORDER_REJECTED

ORDER_PARTIALLY_FILLED

ORDER_FILLED

ORDER_CANCELLED

ORDER_EXPIRED

ORDER_UNKNOWN

FILL_CORRECTED

These events change execution truth.

They do not directly change prediction state.

==================================================
5. CORE STATE INVARIANT
==================================================

At any instant:

ActualPositionQuantity >= 0

For the baseline directional option-buyer architecture:

ActualPositionQuantity > 0

implies:

PositionState != NO_POSITION

and:

ActualPositionQuantity = 0

implies:

PositionState cannot represent an actually exposed position.

This prevents the most fundamental accounting contradiction.

==================================================
6. NO_POSITION AUDIT
==================================================

State:

NO_POSITION

If a valid market event arrives and there is no entry opportunity:

NO_POSITION -> NO_POSITION

This is a valid self-transition.

If a valid market event creates a fully qualified entry opportunity:

NO_POSITION -> ENTRY_AUTHORIZED

If entry authorization is immediately invalidated before submission:

ENTRY_AUTHORIZED -> NO_POSITION

If an entry order is submitted:

ENTRY_AUTHORIZED -> ENTRY_PENDING

If a critical data failure occurs before authorization:

NO_POSITION -> DATA_DEGRADED

If the session prohibits new entries:

NO_POSITION remains NO_POSITION

If the system is administratively halted:

NO_POSITION -> SYSTEM_HALTED

Therefore NO_POSITION has no undefined normal transition.

==================================================
7. ENTRY_AUTHORIZED AUDIT
==================================================

ENTRY_AUTHORIZED means:

All entry predicates were true at the authorization event.

It does not mean that exposure exists.

A new market event can produce:

authorization remains valid:

ENTRY_AUTHORIZED -> ENTRY_AUTHORIZED

authorization becomes stale:

ENTRY_AUTHORIZED -> NO_POSITION

execution submission:

ENTRY_AUTHORIZED -> ENTRY_PENDING

critical data failure:

ENTRY_AUTHORIZED -> NO_POSITION

session invalidation:

ENTRY_AUTHORIZED -> NO_POSITION

system halt:

ENTRY_AUTHORIZED -> SYSTEM_HALTED

A new opposing signal does not create a position reversal.

It invalidates the authorization if the formal entry contract says the original opportunity is no longer valid.

==================================================
8. ENTRY_PENDING AUDIT
==================================================

ENTRY_PENDING means an order exists but actual exposure is not yet fully established.

If no execution event arrives:

ENTRY_PENDING -> ENTRY_PENDING

If the order is accepted:

ENTRY_PENDING -> ENTRY_PENDING

because order acceptance does not equal fill.

If partially filled:

ENTRY_PENDING -> ACTIVE

with:

ActualPositionQuantity > 0

and the remaining unfilled quantity represented separately.

If completely filled:

ENTRY_PENDING -> ACTIVE

If rejected:

ENTRY_PENDING -> NO_POSITION

If cancelled without fill:

ENTRY_PENDING -> NO_POSITION

If execution status becomes unknown:

ENTRY_PENDING -> RECONCILIATION_REQUIRED

This is essential.

We never infer a fill from elapsed time.

==================================================
9. ACTIVE STATE AUDIT
==================================================

ACTIVE means:

ActualPositionQuantity > 0

and:

No mandatory unresolved exit obligation exists.

Every valid market event can produce one of the following categories.

Continuation remains valid:

ACTIVE -> ACTIVE

Protection candidate improves:

ACTIVE -> ACTIVE

with an updated protection boundary.

Mode changes:

ACTIVE -> ACTIVE

with a different mode dimension.

Normal exit becomes required:

ACTIVE -> ACTIVE_EXIT_REQUIRED

Emergency reversal becomes required:

ACTIVE -> ACTIVE_EXIT_REQUIRED

Hard protection becomes required:

ACTIVE -> ACTIVE_EXIT_REQUIRED

Session termination becomes required:

ACTIVE -> ACTIVE_EXIT_REQUIRED

Critical execution discrepancy:

ACTIVE -> RECONCILIATION_REQUIRED

Critical data degradation:

ACTIVE -> DATA_DEGRADED

provided the data-degradation state retains the existing exposure and protection obligations.

This last point is important.

DATA_DEGRADED must never mean:

"the position disappeared."

==================================================
10. ACTIVE_EXIT_REQUIRED AUDIT
==================================================

This is one of the most important states.

It means:

An exit obligation has been established.

The obligation has not yet been fulfilled.

Therefore:

ACTIVE_EXIT_REQUIRED -> EXIT_PENDING

when an exit order is submitted.

It cannot transition back to ordinary ACTIVE merely because a later market event becomes favorable.

This is:

INV-CONFLICT-005

and:

INV-EXIT-002

in operational form.

If another exit trigger arrives:

ACTIVE_EXIT_REQUIRED -> ACTIVE_EXIT_REQUIRED

The obligation remains.

If an execution fill occurs before order submission:

the state is reconciled according to actual exposure.

If actual quantity reaches zero:

ACTIVE_EXIT_REQUIRED -> CLOSED_PENDING_RECONCILIATION

If quantity remains:

ACTIVE_EXIT_REQUIRED remains an exposed exit-obligation state.

==================================================
11. EXIT_PENDING AUDIT
==================================================

EXIT_PENDING means an exit instruction has been submitted.

It does not mean the position is closed.

If no fill:

EXIT_PENDING -> EXIT_PENDING

If partial fill:

EXIT_PENDING -> PARTIALLY_EXITED

If full fill:

EXIT_PENDING -> CLOSED_PENDING_RECONCILIATION

If order rejection:

EXIT_PENDING -> ACTIVE_EXIT_REQUIRED

The position remains under exit obligation.

This is critical.

A rejected exit does not create:

ACTIVE_NORMAL.

It returns to:

ACTIVE_EXIT_REQUIRED.

If execution status becomes unknown:

EXIT_PENDING -> RECONCILIATION_REQUIRED

==================================================
12. PARTIALLY_EXITED AUDIT
==================================================

PARTIALLY_EXITED means:

ActualPositionQuantity > 0

and:

some quantity has already been exited.

The remaining quantity inherits the active risk obligation.

Therefore:

PARTIALLY_EXITED + favorable market event

cannot automatically become:

NO_POSITION.

It remains exposed.

If continuation remains valid:

PARTIALLY_EXITED -> PARTIALLY_EXITED

If another exit is required:

PARTIALLY_EXITED -> EXIT_PENDING

If remaining quantity reaches zero:

PARTIALLY_EXITED -> CLOSED_PENDING_RECONCILIATION

==================================================
13. CLOSED_PENDING_RECONCILIATION
==================================================

This state exists because execution truth and accounting truth must be reconciled.

The strategy believes:

ActualPositionQuantity = 0

but the trade is not yet considered permanently closed until the required execution/accounting confirmation exists.

If reconciliation confirms zero:

CLOSED_PENDING_RECONCILIATION -> NO_POSITION

If reconciliation reports remaining exposure:

CLOSED_PENDING_RECONCILIATION -> RECONCILIATION_REQUIRED

If a correction event changes the confirmed fill:

the position state is reconstructed from authoritative execution facts.

This prevents false closure.

==================================================
14. RECONCILIATION_REQUIRED
==================================================

This state means:

Internal state and authoritative execution state cannot currently be trusted to agree.

Normal entry is forbidden.

Normal optimization is suspended.

The system must establish:

actual quantity

active orders

completed fills

cancelled orders

unknown orders

and the resulting net exposure.

Successful reconciliation:

RECONCILIATION_REQUIRED -> appropriate canonical position state

If quantity = 0:

RECONCILIATION_REQUIRED -> NO_POSITION

If quantity > 0 and no exit obligation:

RECONCILIATION_REQUIRED -> ACTIVE

If quantity > 0 and mandatory exit remains:

RECONCILIATION_REQUIRED -> ACTIVE_EXIT_REQUIRED

If reconciliation itself cannot establish truth:

RECONCILIATION_REQUIRED -> SYSTEM_HALTED

or remains in reconciliation according to the operational recovery contract.

==================================================
15. DATA_DEGRADED AUDIT
==================================================

DATA_DEGRADED does not mean:

NO_POSITION.

It means:

the information necessary for normal optimization is unavailable or invalid.

If no position exists:

DATA_DEGRADED -> DATA_DEGRADED

until recovery.

No new trade is permitted.

If an active position exists:

DATA_DEGRADED must preserve:

actual quantity

entry facts

realized P&L

peak state

protection boundary

exit obligations

and execution state.

When valid data returns:

DATA_DEGRADED -> state reconstructed from current authoritative facts.

It must not simply resume using stale analytical state.

==================================================
16. SYSTEM_HALTED AUDIT
==================================================

SYSTEM_HALTED is terminal with respect to ordinary strategy decisions.

No:

ENTER

HOLD

MODE_CHANGE

or normal LEARNING action

may emerge from this state.

Recovery requires an explicit operational transition.

This prevents an internal failure from silently becoming a live trading decision.

==================================================
17. MODE STATE AUDIT
==================================================

Mode is orthogonal to operational position state.

The permitted progression is:

MICRO <-> SCALP <-> EXTENDED_SCALP <-> INTRADAY

subject to validated transition conditions.

However, mode cannot create exposure.

Mode cannot increase quantity.

Mode cannot widen protection.

Mode cannot cancel an exit obligation.

Therefore:

ACTIVE + INTRADAY

can become:

ACTIVE + SCALP

but:

ACTIVE_EXIT_REQUIRED + INTRADAY

cannot become:

ACTIVE + SCALP.

The exit obligation dominates mode.

==================================================
18. NO_POSITION MODE
==================================================

NO_POSITION has:

Mode = NONE

Any transition into an active position establishes the initial mode according to the entry-state classification.

There is no historical mode carried from the previous trade.

Each trade starts with a new mode state.

==================================================
19. TRADE RESET INVARIANT
==================================================

When:

ActualPositionQuantity = 0

and the trade is fully reconciled:

all trade-local state is frozen.

A new trade receives a new:

TradeID

and a new trade-local:

EntryTimestamp

EntryPrice

EntryModelVersion

PeakPnL

ProtectionBoundary

Mode

and risk state.

No previous trade's peak profit can leak into the next trade.

==================================================
20. SAME-EVENT PRIORITY AUDIT
==================================================

Suppose a single market event simultaneously produces:

continuation improvement

mode improvement

protection breach

and an entry signal.

The canonical result is:

EXIT

if a position exists.

If no position exists, the protection breach cannot apply to that position, so the entry decision proceeds through the normal entry contract.

This demonstrates that the state itself determines which predicates are semantically applicable.

==================================================
21. POSITION-DEPENDENT EVENT SEMANTICS
==================================================

The same market event can therefore produce different outcomes depending on state.

For example:

Market event:

strong bullish movement.

In:

NO_POSITION

it may create:

ENTRY_AUTHORIZED.

In:

ACTIVE + MICRO

it may create:

HOLD

plus:

MODE = SCALP.

In:

ACTIVE + INTRADAY

it may create:

HOLD

with:

Protection tightened.

In:

ACTIVE_EXIT_REQUIRED

it does not cancel the exit obligation.

This is why the strategy is a temporal state machine rather than a static signal formula.

==================================================
22. EXECUTION EVENT SEMANTICS
==================================================

An execution fill cannot directly produce:

BUY_CE

or:

BUY_PE.

It can only update execution truth.

The resulting position state is then reconstructed from:

previous exposure

plus executed quantity.

This prevents execution events from accidentally becoming strategy signals.

==================================================
23. ORDER STATUS VERSUS FILL STATUS
==================================================

The audit confirms these are different facts.

ORDER_ACCEPTED means:

the broker accepted the order.

ORDER_FILLED means:

actual execution occurred.

Therefore:

ORDER_ACCEPTED != POSITION_ACTIVE

unless actual quantity is independently confirmed.

==================================================
24. DUPLICATE EVENT AUDIT
==================================================

If an identical event arrives twice with the same authoritative event identity:

the second processing must be idempotent.

Therefore:

State_after(Event, Event)

must equal:

State_after(Event)

for a duplicate event.

No second entry.

No second P&L update.

No second mode transition.

No duplicate fill.

==================================================
25. OUT-OF-ORDER EVENT AUDIT
==================================================

An event whose temporal position conflicts with the current event sequence cannot simply overwrite current state.

The system must use the event-ordering contract.

If the event can be safely incorporated:

it is incorporated according to the temporal rules.

If not:

it is quarantined or rejected.

This remains partly dependent on the TrueData event-ordering semantics.

==================================================
26. MISSING EVENT AUDIT
==================================================

If:

t1

then:

t3

arrives with t2 absent:

the system cannot invent t2.

Derived state may become:

STALE

or:

INCOMPLETE

depending on the affected feature.

No synthetic observation is permitted unless explicitly defined by the data contract.

==================================================
27. PROTECTION TRANSITION AUDIT
==================================================

For every active long position:

Protection_new >= Protection_old

must hold.

This remains true regardless of:

mode

ATR

volatility

probability

continuation

time

new model

or new candidate stop.

Therefore:

CandidateProtection < Protection_old

produces:

Protection_new = Protection_old.

CandidateProtection > Protection_old

produces:

Protection_new = CandidateProtection.

This is one of the strongest state-machine invariants.

==================================================
28. PROFIT PEAK TRANSITION AUDIT
==================================================

For every active trade:

PeakPnL_new = max(PeakPnL_old, CurrentPnL_new)

Therefore a declining price cannot reduce the historical peak.

If:

PeakPnL_old = 50

and:

CurrentPnL_new = 30

then:

PeakPnL_new = 50.

If:

CurrentPnL_new = 60

then:

PeakPnL_new = 60.

==================================================
29. MODE TRANSITION AUDIT
==================================================

A mode transition is allowed only when:

the position remains valid

no higher-priority exit obligation exists

the transition condition is satisfied

the persistence/hysteresis condition is satisfied

and the transition does not violate risk monotonicity.

Therefore:

continuation improvement alone does not guarantee a mode transition.

Similarly:

one adverse tick alone does not necessarily force a mode downgrade.

The exact persistence parameters remain learned.

==================================================
30. ENTRY TRANSITION AUDIT
==================================================

An entry requires:

valid state

valid data

valid probability

valid economic value

valid option

valid risk capacity

valid execution conditions

valid session

and no active position.

If any mandatory predicate fails:

NO_ENTRY.

There is no partial entry authorization at the mathematical decision level.

Partial quantity arises only at execution.

==================================================
31. CE/PE DECISION AUDIT
==================================================

The baseline executable decision set is:

BUY_CE

BUY_PE

NO_TRADE

The system cannot simultaneously authorize:

BUY_CE

and:

BUY_PE

for the same strategy instance.

If both directional hypotheses appear sufficiently attractive, the conflict-resolution mechanism must ultimately select:

NO_TRADE

or one candidate according to the formally defined option-ranking contract.

This ranking contract remains a numerical/model boundary rather than a state-machine ambiguity.

==================================================
32. EXIT PRIORITY AUDIT
==================================================

The exit hierarchy remains:

HARD_RISK

then:

SESSION_TERMINATION

then:

EMERGENCY_REVERSAL

then:

NORMAL_EXIT.

If multiple exit predicates are true simultaneously, exactly one becomes the primary exit reason.

The remaining predicates remain secondary audit evidence.

==================================================
33. EXIT STICKINESS AUDIT
==================================================

Once:

ACTIVE_EXIT_REQUIRED

has been entered:

later continuation improvement cannot return the position to ordinary ACTIVE.

This is an explicit anti-race invariant.

The only legitimate resolution paths are execution and reconciliation.

==================================================
34. LEARNING STATE AUDIT
==================================================

Learning is not part of the live position state.

A matured historical observation may enter the learning pipeline without affecting live trading state.

A new model may be trained without changing the active model.

A candidate model may be validated without influencing live decisions.

Only explicit model promotion changes the active model version.

==================================================
35. MODEL PROMOTION AUDIT
==================================================

A candidate model has:

CANDIDATE

then:

VALIDATED

then:

PROMOTED

then:

ACTIVE

status.

A candidate cannot jump directly from:

CANDIDATE

to:

ACTIVE.

The promotion event itself must be versioned and timestamped.

==================================================
36. MODEL CHANGE DURING ACTIVE TRADE
==================================================

If:

Trade A

was opened under:

Model V1

and:

Model V2

becomes active:

Trade A retains:

EntryModelVersion = V1.

The current management policy may use V2 only if the live-management contract explicitly permits it.

This distinction must be preserved.

==================================================
37. CRITICAL UNRESOLVED MODEL QUESTION
==================================================

One item remains intentionally open:

Does a newly promoted model manage already-open positions?

There are two legitimate architectures.

Architecture A:

Entry model and management model remain fixed for the trade.

Architecture B:

Entry model is immutable, but management uses the currently active management model.

This must be decided before implementation.

It cannot be left implicit.

==================================================
38. SESSION TRANSITION AUDIT
==================================================

Before session:

NO_POSITION

During session:

normal operation.

At session termination:

existing positions transition toward:

ACTIVE_EXIT_REQUIRED

New entries become prohibited.

After confirmed closure:

NO_POSITION.

No position may silently persist beyond the defined session boundary.

==================================================
39. SESSION CONFLICT
==================================================

If:

strong continuation

and:

session termination

occur simultaneously:

session termination wins.

This is because session closure is an operational constraint, not a prediction.

==================================================
40. RECONCILIATION CONFLICT
==================================================

If:

new entry signal

and:

execution state uncertainty

occur simultaneously:

RECONCILIATION wins.

No new exposure is established until actual exposure is known.

==================================================
41. DATA FAILURE CONFLICT
==================================================

If:

new entry signal

and:

critical data failure

occur simultaneously:

NO_ENTRY.

If an active position exists, existing risk obligations remain.

The system must not create a new analytical decision from invalid data.

==================================================
42. DEAD-END STATE AUDIT
==================================================

A state is dead-end if:

no valid event can ever transition it to another valid state.

NO_POSITION is not dead-end because market events can produce entries.

ACTIVE is not dead-end because it can continue, change mode, tighten protection, or exit.

ACTIVE_EXIT_REQUIRED is not dead-end because execution events can resolve it.

RECONCILIATION_REQUIRED is not dead-end because reconciliation can resolve it.

SYSTEM_HALTED is intentionally terminal.

Therefore SYSTEM_HALTED is the only intentional terminal state.

==================================================
43. UNREACHABLE STATE AUDIT
==================================================

Every canonical state must have at least one valid predecessor.

NO_POSITION:

initial state or completed trade.

ENTRY_AUTHORIZED:

NO_POSITION.

ENTRY_PENDING:

ENTRY_AUTHORIZED.

ACTIVE:

ENTRY_PENDING or reconciliation.

ACTIVE_EXIT_REQUIRED:

ACTIVE.

EXIT_PENDING:

ACTIVE_EXIT_REQUIRED.

PARTIALLY_EXITED:

EXIT_PENDING.

CLOSED_PENDING_RECONCILIATION:

successful full exit.

RECONCILIATION_REQUIRED:

execution/data discrepancy.

DATA_DEGRADED:

critical data failure.

SYSTEM_HALTED:

fatal system condition.

Therefore all states have a reachable conceptual predecessor.

==================================================
44. ILLEGAL TRANSITION AUDIT
==================================================

The following transitions are explicitly forbidden:

NO_POSITION -> EXIT_PENDING

NO_POSITION -> PARTIALLY_EXITED

NO_POSITION -> ACTIVE_EXIT_REQUIRED

ACTIVE -> NO_POSITION without confirmed zero exposure

ENTRY_PENDING -> CLOSED

ACTIVE_EXIT_REQUIRED -> ACTIVE_NORMAL

EXIT_PENDING -> ACTIVE_NORMAL after rejection

DATA_DEGRADED -> ACTIVE without revalidation

CANDIDATE_MODEL -> ACTIVE without promotion

historical state -> modified historical state

These are invariant violations.

==================================================
45. CYCLE AUDIT
==================================================

Cycles are not inherently errors.

The following are legitimate:

ACTIVE -> ACTIVE

ACTIVE + MICRO -> ACTIVE + SCALP

ACTIVE + SCALP -> ACTIVE + MICRO

ACTIVE + INTRADAY -> ACTIVE + SCALP

ENTRY_AUTHORIZED -> ENTRY_AUTHORIZED

EXIT_PENDING -> EXIT_PENDING

RECONCILIATION_REQUIRED -> RECONCILIATION_REQUIRED

The dangerous cycle is:

ACTIVE_EXIT_REQUIRED -> ACTIVE_NORMAL

without actual resolution.

That cycle is forbidden.

==================================================
46. EVENT-COMPLETENESS CONDITION
==================================================

For every reachable operational state, every relevant event class must have a defined semantic response.

The result can be:

state unchanged

state transition

state degraded

state halted

or event rejected.

"Nothing specified" is not an acceptable result.

==================================================
47. EXPLICIT SELF-TRANSITIONS
==================================================

The audit confirms that self-transition is a legitimate transition.

For example:

ACTIVE + ordinary tick

may produce:

ACTIVE.

This does not mean the event was ignored.

The state variables may still change:

CurrentPnL

PeakPnL

ATR-derived quantities

probability state

continuation distribution

protection candidate

mode evidence.

The operational state may remain identical while internal state evolves.

This distinction is fundamental.

==================================================
48. INTERNAL STATE VERSUS OPERATIONAL STATE
==================================================

We therefore formally distinguish:

OperationalState

from:

AnalyticalState.

For example:

OperationalState = ACTIVE

while:

ProbabilityState

ContinuationState

VolatilityState

ProfitState

ProtectionState

ModeState

may all change on every tick.

This resolves an important earlier ambiguity.

A state transition does not necessarily mean the coarse operational state changed.

==================================================
49. TICK-BY-TICK TRANSITION MODEL
==================================================

The canonical conceptual transformation is:

Event_t

+

State_t

produces:

State_(t+1).

More precisely:

State_(t+1)
=
Transition(
State_t,
Event_t,
ActiveModel_t
)

subject to:

InvariantSet.

The next event then operates on:

State_(t+1).

No future event is visible.

==================================================
50. STATE UPDATE ORDER
==================================================

Within an event, the conceptual dependency order is:

event validation

then:

execution reconciliation if applicable

then:

observable market-state update

then:

derived feature update

then:

probability-state update

then:

economic-state update

then:

position/P&L update

then:

peak/protection update

then:

exit evaluation

then:

mode evaluation

then:

entry evaluation where applicable

then:

audit recording.

The exact micro-order between independent calculations may later be optimized, but dependency order cannot be violated.

==================================================
51. CRITICAL CORRECTION TO EARLIER ARCHITECTURE
==================================================

P&L must be calculated from execution facts for realized accounting.

However:

current mark-to-market P&L can use the current validated market price.

Therefore we retain:

CurrentPnL

and:

RealizedPnL

as distinct quantities.

We do not use the same variable for both.

This resolves the earlier duplicate-variable problem.

==================================================
52. EXPECTED HORIZON VERSUS HOLDING TIME
==================================================

The audit also confirms the distinction:

ExpectedHorizon

means:

the statistical horizon over which continuation is evaluated.

ActualHoldingTime

means:

elapsed time from actual entry to actual exit.

They are not interchangeable.

ExpectedHorizon can change during the trade.

ActualHoldingTime cannot.

==================================================
53. CURRENT P&L VERSUS PEAK P&L
==================================================

The canonical distinction is:

CurrentPnL

=

current mark-to-market economic result.

PeakPnL

=

maximum observed CurrentPnL during the active trade.

ProfitGiveback

=

PeakPnL - CurrentPnL

when:

CurrentPnL < PeakPnL.

These variables must never be collapsed.

==================================================
54. ATR AUDIT
==================================================

ATR or another volatility measure is a state input.

It may influence:

candidate protection

expected movement

option economics

continuation estimates

position sizing at entry.

It cannot directly override:

ProtectionMonotonicity.

Therefore:

ATR increase

does not imply:

Protection decreases.

This formally resolves the earlier widening-stop problem.

==================================================
55. STOP-LOSS AUDIT
==================================================

The strategy therefore contains two distinct concepts:

InitialProtection

and:

DynamicProtection.

InitialProtection is established around entry.

DynamicProtection can tighten.

DynamicProtection cannot widen.

Once the trade is profitable and the protection boundary crosses into positive territory, the resulting locked boundary becomes part of the trade's historical risk state.

==================================================
56. PROFIT LOCK AUDIT
==================================================

Profit locking is therefore not:

"target reached."

It is:

the protection boundary has moved into a favorable region and subsequently cannot move backward.

This is a state transition property.

==================================================
57. TARGET AUDIT
==================================================

A traditional fixed target is not required by the architecture.

The strategy can instead use:

continuation value

expected remaining opportunity

profit-floor distribution

and protection state

to determine whether holding remains justified.

If the empirical specification later establishes a hard target, it becomes another exit condition.

It does not automatically replace the protection system.

==================================================
58. FORWARD/BACKWARD AUDIT
==================================================

The forward component estimates:

what favorable continuation remains available from the current state.

The backward component evaluates:

how much of the already-earned favorable state is at risk of being surrendered.

They have different mathematical purposes.

They must not be represented by one variable.

==================================================
59. FORWARD COMPONENT

Conceptually:

ForwardOpportunity_t

is estimated from information available at t.

It may include:

expected future return

probability of continuation

distribution of favorable excursion

expected remaining horizon

expected cost-adjusted opportunity.

No future observation can enter its calculation at decision time.

==================================================
60. BACKWARD COMPONENT

BackwardProtection_t

is based on already-observed trade history:

Entry

PeakPnL

CurrentPnL

ProfitGiveback

ProtectionHistory

and the validated protection rules.

It is therefore causal with respect to the current trade.

==================================================
61. CONFLICT BETWEEN FORWARD AND BACKWARD

Suppose:

ForwardOpportunity = very high

but:

BackwardProtection = strongly restrictive.

The system cannot simply erase the backward protection.

The forward opportunity can influence:

HOLD

mode

or further tightening.

It cannot weaken:

ProtectionBoundary.

==================================================
62. COMPLETE STATE-MACHINE CLOSURE

The audit therefore establishes:

Every canonical state has a predecessor.

Every relevant event class has a semantic response.

Every mandatory exit has a resolution path.

Every active exposure has a risk state.

Every execution state has a reconciliation path.

Every model state has a promotion path.

Every historical observation has a temporal eligibility rule.

Every protected quantity has a monotonicity rule where required.

==================================================
63. REMAINING CONTRACT GAPS

The state machine itself is substantially closed.

However, several contracts cannot legitimately be finalized without the corresponding data/model specifications.

These are not failures of the state machine.

They are parameter/data-boundary dependencies.

The first is:

exact TrueData event identity and ordering semantics.

The second is:

exact market and option field availability.

The third is:

exact timestamp precision and exchange-time semantics.

The fourth is:

exact broker/execution event semantics.

The fifth is:

whether management of an existing position uses the model version active at entry or the currently promoted management model.

The sixth is:

the exact definition of option liquidity/execution admissibility.

The seventh is:

the exact session-boundary semantics.

==================================================
64. AUDIT RESULT
==================================================

The formal state machine passes the architectural completeness test subject to the explicitly identified contracts.

No fundamental undefined transition remains in the core trading lifecycle.

The critical invariants are preserved:

No future information.

No position without actual exposure.

No closure without confirmed zero exposure.

No protection widening.

No mode-based risk expansion.

No exit cancellation through favorable prediction.

No implicit position reversal.

No fabricated execution.

No learning contamination.

No retroactive model mutation.

==================================================
65. FORMAL STATUS

The result is:

STATE-MACHINE ARCHITECTURE:
COMPLETE

STATE TRANSITION SEMANTICS:
COMPLETE

CONFLICT PRIORITY:
COMPLETE

SAFETY INVARIANTS:
COMPLETE

EXECUTION STATE MODEL:
SUBSTANTIALLY COMPLETE

DATA-SOURCE CONTRACT:
PENDING TRUE DATA DOCUMENTATION

NUMERICAL PARAMETERS:
INTENTIONALLY UNFROZEN

MODEL-MANAGEMENT POLICY:
ONE EXPLICIT DECISION REQUIRED

==================================================
66. NEXT ARTIFACT

The next artifact is therefore no longer another conceptual strategy layer.

It is the:

CANONICAL NUMERICAL PARAMETER LEARNING AND WALK-FORWARD CALIBRATION SPECIFICATION.

That document will finally answer:

What exactly is learned?

From which historical observations?

With what label?

At what timestamp does that label mature?

What constitutes training?

What constitutes validation?

What constitutes test?

How are overlapping observations purged?

How are parameters selected?

How are multiple candidates controlled?

When does a parameter become production-active?

When is it rejected?

And critically:

How do we prevent five years of historical replay from becoming a disguised form of hindsight?

That is the next boundary between our mathematical architecture and actual historical calibration.