# A172 — Canonical Market-Data Event Persistence & Temporal Snapshot Contract

**Status:** CANONICAL  
**Authority:** Canonical durable representation of market observations and point-in-time market state  
**Scope:** Adaptive Edge  
**Dependencies:** A128, A153–A171

## 1. Purpose

A172 defines how externally observed market data becomes durable canonical evidence and how point-in-time market snapshots are reconstructed without look-ahead, silent correction, timestamp collapse, or provider-specific semantic leakage.

It separates:

```text
provider observation
    -> canonical market event
    -> temporal state
    -> feature snapshot
```

A172 does not define trading signals, probability, economics, execution policy, or learned parameters.

## 2. Authority boundary

TrueData is the current canonical external market-data provider boundary for Adaptive Edge. Provider observations remain provider evidence; Adaptive Edge owns canonical interpretation.

No consumer may treat an unverified provider field as canonical merely because it exists in a payload.

## 3. MarketDataEvent

Minimum canonical fields:

```text
event_id
event_type
instrument_identity
provider
provider_event_id
provider_sequence
provider_timestamp
exchange_timestamp
received_at
available_at
canonical_event_time
source_version
schema_version
payload_reference
quality_state
causal_parent_ids
```

Provider identifiers and timestamps remain distinct from canonical identifiers and timestamps.

## 4. Temporal semantics

The following times are distinct:

```text
provider_timestamp      = timestamp supplied by provider
exchange_timestamp      = exchange event timestamp when available
received_at             = system receipt time
available_at            = earliest time the system is permitted to consume the event
canonical_event_time    = canonical market-time interpretation
```

`available_at` is the causal boundary for downstream consumption.

A downstream decision at time `t` may consume event `e` only when:

```text
available_at(e) <= t
```

## 5. Event ordering

Events are not assumed to arrive in exchange-time order.

Canonical ordering must preserve both:

```text
event-time ordering
arrival ordering
```

An out-of-order event must not be silently rewritten into the historical stream.

## 6. Duplicate handling

Duplicate provider observations must be identified using the strongest available identity tuple, such as:

```text
provider
provider_event_id
provider_sequence
instrument_identity
provider_timestamp
```

The exact deduplication key is provider-specific and must be verified.

A duplicate observation must not create duplicate semantic state transitions.

## 7. Conflicting duplicates

If two observations claim the same provider identity but contain conflicting material values:

```text
DATA_CONFLICT
```

must be recorded.

The system must not silently select one observation merely because it arrived later.

## 8. Market event types

The canonical event taxonomy may include, subject to provider verification:

```text
TICK
QUOTE
TRADE
BAR
OPEN_INTEREST
AUCTION
CORPORATE_ACTION
REFERENCE_DATA
SESSION_EVENT
```

No event type may be introduced solely to accommodate an implementation shortcut.

## 9. Quote semantics

When available, bid, ask, bid quantity, ask quantity, last traded price, and last traded quantity remain separate observations.

```text
LTP != BID
LTP != ASK
LTP != EXECUTABLE_PRICE
```

Executable-price semantics are defined by the economics/execution contracts, not by market-data persistence.

## 10. Bar semantics

A bar is an observed aggregate, not a replacement for the underlying event stream.

A canonical bar must preserve:

```text
interval
open
high
low
close
volume
open_interest where available
source
formation semantics
availability boundary
```

If the provider's bar-construction methodology is not verified, the bar remains provider-derived evidence rather than a canonical independently reconstructed bar.

## 11. Missing data

Missing observations must remain distinguishable from zero-valued observations.

```text
MISSING != ZERO
MISSING != UNKNOWN_VALUE
MISSING != NO_ACTIVITY
```

No interpolation is permitted in the canonical evidence layer unless explicitly defined by a downstream contract.

## 12. Stale data

A stale observation remains valid historical evidence but may be ineligible for a real-time consumer.

```text
historical_validity != current_eligibility
```

Freshness thresholds are configuration and must be consumer-specific.

## 13. Data-quality state

Canonical quality states include:

```text
VALID
DUPLICATE
CONFLICT
OUT_OF_ORDER
STALE
MISSING
INVALID
UNKNOWN
```

Quality state is evidence, not a hidden filter.

## 14. Temporal snapshot

A temporal snapshot represents the latest admissible state as of a specified causal boundary:

```text
Snapshot(t) = state derived only from events with available_at <= t
```

No event with `available_at > t` may affect `Snapshot(t)`.

## 15. Snapshot reproducibility

A snapshot must be reconstructible from durable market events and the applicable schema/version set.

```text
same events
+
same versions
+
same causal boundary
=
same snapshot
```

Any non-deterministic dependency must be explicitly represented in the version/evidence set.

## 16. Snapshot identity

Minimum fields:

```text
snapshot_id
snapshot_time
causal_cutoff
instrument_universe_version
market_event_schema_version
state_version
source_set_hash
created_at
```

## 17. Snapshot isolation

A feature computation may consume a snapshot only after the snapshot's causal cutoff is established.

A snapshot created after the decision time cannot be retroactively used merely because it describes an earlier market timestamp.

## 18. Revision policy

If provider data is corrected after initial availability:

```text
original observation remains immutable
correction becomes new evidence
historical interpretation is versioned
```

A corrected observation cannot silently rewrite a previously recorded decision.

## 19. Late events

An event arriving after a decision may be valid historical evidence but cannot modify the already-issued decision.

It may affect later reconstruction or explicitly versioned research replay.

## 20. Session boundary

Market events must be interpreted against a canonical session/calendar authority.

The exact calendar implementation and holiday/session rules remain external/configuration dependencies until verified.

A timestamp alone must not be used to infer market-open status.

## 21. Instrument identity

Every event must resolve to the canonical instrument identity contract.

Provider symbol strings are references, not canonical identities.

An unresolved instrument must remain:

```text
INSTRUMENT_IDENTITY_UNKNOWN
```

and cannot silently fall back to a similarly named instrument.

## 22. Option-specific market events

Option events must preserve the canonical contract identity, including at minimum where applicable:

```text
underlying
expiry
strike
option_type
exchange/venue
```

A provider symbol parser must not become the sole authority for contract identity.

## 23. Persistence model

Market evidence must support append-preserving persistence.

Mutable indexes/materialized snapshots may be rebuilt from canonical evidence.

Canonical historical events must not be destructively overwritten.

## 24. Idempotency

Each consequential market event ingestion operation requires an idempotency boundary.

A repeated observation must produce:

```text
one semantic event
```

not multiple downstream state transitions.

## 25. Provider outage

Provider unavailability produces:

```text
MARKET_DATA_UNAVAILABLE
```

It does not produce fabricated values, zero values, or inferred flat market state.

## 26. Provider reconnect

After reconnect, the system must establish whether the event stream has a continuity gap.

A reconnect does not imply that missing observations were received.

Gap detection and recovery policy must be explicit.

## 27. Sequence gaps

Where provider sequence numbers exist, a gap must be detectable.

A gap is evidence of incomplete observation, not proof of the values that occurred during the gap.

## 28. Data retention

Retention must preserve enough evidence for:

```text
live reconciliation
historical replay
research reproduction
audit
incident investigation
label construction
```

Exact retention duration is configuration, not architecture.

## 29. Research boundary

Research may consume historical market events only under the same causal semantics applicable to the historical decision being reconstructed.

Current data availability must not be used to imply that the historical decision had access to later-corrected information.

## 30. Provider field verification

For every provider field promoted to canonical use, the registry must record:

```text
field
provider
meaning
units
timestamp semantics
availability
quality behavior
verification evidence
```

Unverified semantics remain UNKNOWN.

## 31. Hostile scenarios

The implementation must test:

```text
duplicate tick
conflicting duplicate
out-of-order tick
future-dated event
late event
missing event
sequence gap
stale quote
crossed quote
zero-volume event
missing bid/ask
provider reconnect
provider restart
schema change
instrument mismatch
expired option event
corrected historical event
snapshot reconstruction at historical cutoff
```

## 32. Causal attack examples

### Future event

```text
available_at = 10:01:05
decision_time = 10:01:00
```

The event is forbidden from the decision snapshot.

### Late event

```text
exchange_timestamp = 10:00:55
available_at = 10:01:05
decision_time = 10:01:00
```

The event is also forbidden from that decision, despite its earlier exchange timestamp.

### Correction

A provider correction received at 10:05 cannot rewrite a decision made at 10:01.

## 33. Invariants

```text
INV-172-001  Provider evidence is immutable.
INV-172-002  available_at is the causal consumption boundary.
INV-172-003  Future-available events cannot influence earlier decisions.
INV-172-004  Late events cannot rewrite completed decisions.
INV-172-005  Duplicate observations cannot create duplicate state effects.
INV-172-006  Conflicting duplicates remain explicit evidence.
INV-172-007  Missing is distinct from zero.
INV-172-008  Stale is distinct from invalid.
INV-172-009  LTP is not automatically executable price.
INV-172-010  Provider symbols do not replace canonical instrument identity.
INV-172-011  Historical snapshots are reproducible from durable evidence.
INV-172-012  Snapshot reconstruction respects the causal cutoff.
INV-172-013  Provider corrections cannot silently rewrite historical decisions.
INV-172-014  Provider outage cannot create synthetic market observations.
INV-172-015  Sequence gaps remain observable.
INV-172-016  Session interpretation requires canonical calendar authority.
INV-172-017  Unverified provider field semantics remain UNKNOWN.
```

## 34. Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- market-event/provider-evidence separation
- causal availability boundary
- temporal snapshot semantics
- duplicate/conflict handling
- missing/stale/invalid distinctions
- immutable observation history
- late-event handling
- correction/version semantics
- snapshot reproducibility
- sequence-gap semantics
- provider-outage behavior
- canonical instrument identity boundary
- option-contract identity boundary
- provider-field verification boundary

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact TrueData timestamp semantics
- exact TrueData sequence continuity guarantees
- exact TrueData bar-formation methodology
- exact TrueData correction/revision behavior
- exact session-calendar provider
- physical market-event storage technology
- exact gap-recovery mechanism

CONFIGURATION TO VALIDATE:
- freshness thresholds
- retention
- partitioning/indexing
- gap-recovery thresholds
- snapshot materialization cadence
- provider reconnect policy

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification.
Empirical provider verification remains required before production reliance.

NEXT ARTIFACT:
A173 — Canonical Feature Snapshot, Provenance & Point-in-Time Computation Contract
```