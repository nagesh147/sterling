# A182 — Canonical Data Quality, Staleness, Missingness & Degradation Contract

## Status
CANONICAL

## Purpose
Defines how Adaptive Edge evaluates data validity, freshness, completeness, uncertainty, and degraded operating conditions without fabricating unavailable information.

## Data-quality dimensions
Every canonical data dependency may carry:
```text
identity_status
timestamp_status
availability_status
freshness_status
completeness_status
ordering_status
schema_status
source_status
quality_version
```

## Missingness
Missing data is a first-class state.

```text
MISSING != ZERO
MISSING != FALSE
MISSING != STALE
MISSING != UNKNOWN_VALUE
```
A consumer may impute only when an explicit contract permits it.

## Staleness
A value is stale when its age exceeds the consumer's validated freshness policy.

The architecture freezes the comparison:
```text
age = consumer_time - available_at
```
The threshold is configuration/validation-dependent.

## Timestamp semantics
The canonical distinction remains:
```text
source/event time
availability time
processing time
consumer decision time
```
A source timestamp does not establish that the information was available to the consumer at that timestamp.

## Causal rule
For any decision at time `t`:
```text
available_at(input) <= t
```
Future availability is prohibited from historical decision state.

## Ordering
Out-of-order observations must not silently overwrite newer canonical state. Ordering policy is based on canonical event identity, causal ordering, and version semantics.

## Duplicates
Semantically duplicate observations are idempotent. Duplicate detection must preserve evidence of the duplicate without applying duplicate semantic effects.

## Schema validity
Unexpected schema, type, unit, precision, or contract changes are quality failures unless explicitly supported by a versioned adapter.

## Instrument identity
Data cannot be admitted as canonical if instrument identity is ambiguous or inconsistent with A128.

## Degraded states
The runtime may represent:
```text
HEALTHY
DEGRADED
STALE
PARTIAL
UNKNOWN
UNAVAILABLE
INVALID
```
Degraded state is not equivalent to failure, but every consumer defines whether it can operate under that state.

## Consumer-specific acceptance
Data quality is evaluated relative to its consumer. A value acceptable for visualization may be unacceptable for execution economics.

Therefore:
```text
quality_status != global_trade_authorization
```

## Propagation
A quality defect must propagate to dependent outputs when the defect is material.

```text
data defect
   -> feature quality
   -> probability eligibility
   -> economics eligibility
   -> risk eligibility
   -> execution eligibility
```
A downstream component must not erase the evidence of upstream degradation.

## Recovery
After provider recovery, historical degraded evidence remains immutable. Recovery may produce new healthy observations but may not rewrite the historical period as if the outage never occurred.

## Provider outages
Provider unavailable means unavailable. No fabricated quote, fill, timestamp, or position may be created to maintain apparent continuity.

## Fail-closed conditions
For safety-critical consumers, reject or defer when required inputs are:
```text
INVALID
UNKNOWN
UNAVAILABLE
CAUSALLY FUTURE
STALE BEYOND POLICY
IDENTITY-AMBIGUOUS
UNIT-INCONSISTENT
SCHEMA-INCOMPATIBLE
```

## Quality propagation
Every derived object should preserve references to the source quality state sufficiently to explain why it was accepted, degraded, or rejected.

## Configuration classes
Frozen:
```text
missingness is explicit
staleness is distinct from missingness
availability is distinct from source timestamp
quality propagates
provider failure cannot be fabricated away
consumer-specific acceptance
historical degradation immutable
```
Validate/configure:
```text
freshness thresholds
maximum tolerated gaps
imputation permissions
quality acceptance levels
provider retry policy
degraded-mode permissions
```
Learn/validate:
```text
quality-to-outcome relationships
staleness impact
missingness impact
provider reliability distributions
```

## Invariants
```text
INV-182-001 missing is never silently converted to zero
INV-182-002 stale is never silently treated as current
INV-182-003 source timestamp is not availability timestamp
INV-182-004 future-available data cannot influence earlier decisions
INV-182-005 duplicate observations cannot duplicate semantic effects
INV-182-006 provider outages cannot create fabricated market evidence
INV-182-007 historical quality defects remain immutable
INV-182-008 downstream consumers cannot erase material quality evidence
INV-182-009 quality acceptance is consumer-specific
INV-182-010 invalid identity prevents canonical admission
```

## Adversarial tests
```text
future timestamp
future availability
stale quote
missing bid
missing ask
zero bid/ask accidentally substituted
out-of-order event
duplicate event
schema version mismatch
unit mismatch
instrument collision
provider outage
provider recovery
partial data stream
clock skew
```

## Status
ARCHITECTURE STATUS: COMPLETE
UNRESOLVED: None at architectural-contract level.
UNKNOWN / TODO: exact provider heartbeat/reconnect semantics and empirical reliability distributions.
CONFIGURATION TO VALIDATE: freshness, gaps, imputation, retry, degraded-mode policies.
LEARNED / VALIDATION-DEPENDENT: empirical quality-to-outcome relationships.
BLOCKERS: None for specification work.
NEXT ARTIFACT: A183 — Canonical Research Dataset, Label Maturity & Walk-Forward Boundary Contract
