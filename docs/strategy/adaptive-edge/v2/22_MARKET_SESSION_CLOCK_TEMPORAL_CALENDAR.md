# Adaptive Edge V2 — Market Session, Clock and Temporal Calendar Contract

**Artifact:** A46  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A46 defines the temporal foundations required for causal market-data processing, feature construction, decision timing, execution timing, expiry handling, and historical replay.

The purpose is to prevent incorrect assumptions about local time, exchange time, daylight-saving behavior, trading sessions, holidays, breaks, and calendar-dependent instrument validity.

A46 does not invent exchange calendar rules where an authoritative source has not been recovered.

## 2. Canonical time model

Every time-sensitive event must preserve, where applicable:

```text
source_timestamp
availability_timestamp
received_timestamp
processing_timestamp
decision_timestamp
execution_timestamp
```

A timestamp is not sufficient by itself to establish causal availability.

## 3. Timezone identity

A canonical event must identify the timezone or offset semantics associated with its timestamp.

Naive timestamps must not be silently interpreted as:

```text
UTC
IST
local machine time
exchange time
```

without an explicit source contract.

## 4. UTC and exchange-local representation

The system should preserve an unambiguous temporal representation for storage and comparison while retaining the original source time semantics where available.

Conceptually:

```text
CanonicalTime
    = instant
      + source timezone/offset metadata
```

Conversion between representations must preserve the same instant.

## 5. Decision-time identity

Every decision must have one authoritative decision timestamp:

```text
decision_time
```

The feature snapshot, prediction, eligibility, authorization, sizing, and order intent must reference that decision boundary or their explicitly distinct downstream timestamps.

## 6. Event ordering

Events with different timestamps are ordered by their canonical instants.

Events with equal timestamps require a deterministic tie-breaker when their ordering affects state.

The tie-breaker must be based on authoritative sequence/event identity where available, not arbitrary database insertion order.

## 7. Observation time versus availability time

A market observation may describe an event at `t_obs` while becoming available to the system at `t_avail`.

The causal rule remains:

```text
feature_available_time <= decision_time
```

not merely:

```text
observation_time <= decision_time
```

## 8. Trading session

A trading session is an explicit calendar-defined interval during which an instrument/venue permits the applicable market activity.

A46 does not assume that every market has one continuous daily interval.

Session definitions may include:

```text
pre-open
open/auction
continuous trading
break
close/auction
post-market
```

only where the authoritative venue/instrument contract defines them.

## 9. Session identity

A market observation should be attributable to a session identity where session-dependent semantics matter.

Conceptually:

```text
session_id
session_date
session_open
session_close
session_state
calendar_version
```

Exact field requirements depend on the downstream contract.

## 10. Calendar identity

A historical replay must identify the calendar version used to determine:

```text
trading day
session boundaries
holiday
special session
expiry date
contract availability
```

Current calendars must not silently replace historical calendars when historical rules differ.

## 11. Holidays

A date being a calendar date does not imply a trading session exists.

Holiday treatment must come from the authoritative market/instrument calendar.

The strategy must not infer a holiday solely from missing observations.

## 12. Special sessions

Markets may have sessions whose times differ from ordinary sessions.

The system must represent special-session semantics explicitly rather than applying an ordinary daily schedule universally.

No special-session schedule is invented by A46.

## 13. Daylight saving

Where a source or market uses daylight-saving time, conversion must use a timezone database/rule set rather than a fixed offset assumption.

For Indian markets, no daylight-saving conversion should be introduced merely because another system uses DST.

The authoritative exchange timezone remains source-defined.

## 14. Session state

Architectural states may include:

```text
UNKNOWN
CLOSED
PRE_OPEN
OPEN
HALTED
SUSPENDED
POST_MARKET
```

The exact provider/venue mapping is external.

A lack of observations does not by itself distinguish `CLOSED` from `HALTED`, `SUSPENDED`, or `PROVIDER_UNAVAILABLE`.

## 15. Market clock versus system clock

The local machine clock is not automatically market truth.

The system must distinguish:

```text
market/source timestamp
system receipt timestamp
system wall clock
```

Clock synchronization and drift policies are infrastructure concerns but are required for production timestamp integrity.

## 16. Monotonic processing time

For measuring local elapsed durations, a monotonic clock should be used where available.

Wall-clock timestamps remain the canonical record of external event time.

A monotonic duration must not be substituted for an external event timestamp.

## 17. Clock drift

If system time is materially incorrect, timestamp-based decisions can become causally invalid.

The production system therefore requires a clock-health policy defining acceptable drift and failure behavior.

A46 does not select the numerical drift threshold.

## 18. Bar boundaries

A bar's temporal interval must be explicitly defined:

```text
start_time
end_time
inclusion/exclusion convention
timezone
sampling interval
```

A completed bar is not available before its completion/availability boundary.

## 19. Intrabar decisions

If a strategy decision occurs inside a bar, the completed bar's future portion cannot be used.

For example:

```text
decision = 10:15
bar = 10:15..10:30
```

The 10:30 close is not causally available at 10:15.

## 20. Tick-to-bar construction

If bars are derived from ticks, the aggregation policy must define:

```text
bucket boundary
inclusion rule
late-tick policy
out-of-order policy
missing-tick policy
correction policy
```

A46 does not choose these numerical/implementation parameters.

## 21. Session-open features

A feature such as opening range requires an explicit definition of which session boundary establishes the opening reference.

The system must not infer session open from the first received tick if provider delay or missing data could cause the first received tick to differ from the actual session opening event.

## 22. Session-close features

A close-based feature must use the authoritative close semantics:

```text
last observed trade
official close
auction close
provider-defined close
```

These are not interchangeable.

## 23. Expiry dates

Expiry is an instrument-contract event, not merely a calendar date.

The system must preserve:

```text
contract identity
expiry date/time semantics
calendar version
source
availability timestamp
```

Historical selection cannot use future knowledge of expiry status.

## 24. Relative periods

Terms such as:

```text
next session
previous session
same day
one trading day
N sessions
```

must be resolved through the authoritative calendar, not naive calendar arithmetic.

For example, adding one calendar day is not necessarily equivalent to advancing one trading session.

## 25. Time windows

Every temporal window must specify:

```text
start boundary
end boundary
inclusive/exclusive semantics
timezone/instant semantics
calendar interpretation
```

Ambiguous expressions such as `last 15 minutes` must not silently change meaning between live and historical modes.

## 26. Session crossing

A feature or position may cross a session boundary.

The relevant policy must explicitly state whether state:

```text
resets
persists
expires
reinitializes
```

at the boundary.

No universal reset behavior is assumed.

## 27. Overnight state

An overnight gap is not a missing intraday observation.

The system must distinguish:

```text
market closed
provider unavailable
instrument halted
no trade occurred
```

where the source semantics allow that distinction.

## 28. Data freshness across sessions

A value from the prior session may be valid historical information while being stale for a current-session execution decision.

Freshness must therefore reference the applicable session/data policy rather than a universal elapsed-time rule.

## 29. Backtest/live equivalence

Historical replay and live operation must use the same canonical temporal semantics.

Differences in raw provider timestamp formats may be normalized at the adapter boundary, but the resulting canonical instant and causal ordering must remain consistent.

## 30. Temporal causality invariant

For a decision at `t_d`, every contemporaneous input must satisfy:

```text
availability_time <= t_d
```

and every future event must satisfy:

```text
event_time > t_d
```

unless the policy explicitly defines the event as already available despite representing a later observation period.

## 31. Future-calendar leakage

Historical decisions must not use future calendar knowledge unavailable at the decision time when that knowledge is genuinely uncertain or policy-dependent.

Where contract expiry or scheduled events were already formally published and available, their availability timestamp must establish whether they were legitimate inputs.

## 32. Calendar revision

If an authoritative calendar or contract schedule is corrected after a historical decision, the replay must distinguish:

```text
calendar known at decision time
later corrected calendar
```

The evaluation policy determines which version answers the research question.

## 33. Determinism

Given identical:

```text
source timestamps
calendar version
timezone rules
session policy
ordering policy
```

the temporal normalization and session classification must be deterministic.

## 34. Adversarial cases

### Local timezone ambiguity

A naive timestamp must not be interpreted using the server's timezone by accident.

### Holiday

No observation on a date does not prove a holiday; the authoritative calendar determines session existence.

### Late opening tick

The first received tick after session open is not necessarily the true session-opening observation.

### DST transition

A fixed UTC offset must not replace timezone-rule conversion where DST applies.

### Intrabar leakage

A decision inside a bar cannot consume the completed bar's future high/low/close.

### Overnight gap

The absence of overnight ticks does not imply provider failure.

### Calendar correction

A later calendar correction must not silently rewrite the historical temporal boundary used by an earlier causal replay.

## 35. Implementation gate

A46 framework code may implement:

```text
timestamp normalization
calendar abstraction
session identity
ordering
causal boundary checks
bar-boundary representation
```

Production session behavior remains blocked until authoritative market/instrument calendar semantics are sourced.

## 36. Parameter classes

### Frozen architecture

```text
explicit timestamp semantics
availability boundary
calendar versioning
session identity
causal ordering
intrabar boundary protection
historical calendar lineage
```

### Source-defined configuration

```text
exchange timezone
session hours
holidays
special sessions
expiry calendar
DST rules where applicable
```

### Learned

No learned temporal parameter is introduced by A46.

### External UNKNOWN

```text
complete TrueData timestamp semantics
exchange calendar source
special-session schedule
historical calendar corrections
clock-synchronization requirements
```

## 37. Completion criterion

A46 becomes `RESOLVED` when the system can determine for every event and decision:

```text
what instant it represents
which timezone/offset applies
when it became available
which market session contains it
which calendar version applies
whether the event was causally usable
```

and reproduce those classifications during historical replay.

## ARCHITECTURE STATUS

**FROZEN:** timestamp separation; availability causality; calendar versioning; session abstraction; intrabar protection; historical temporal lineage; deterministic temporal normalization.

**UNRESOLVED:** authoritative exchange calendar; exact session schedule; special sessions; historical calendar corrections; complete provider timestamp semantics; clock-drift thresholds.

**BLOCKERS:** Production temporal correctness requires authoritative calendar/provider semantics. Framework implementation is not blocked.

**NEXT ARTIFACT:** A47 — State Persistence, Event Sourcing and Replay Contract.
