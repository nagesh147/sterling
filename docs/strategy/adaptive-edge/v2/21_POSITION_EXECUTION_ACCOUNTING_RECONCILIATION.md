# Adaptive Edge V2 — Position / Execution Accounting Reconciliation Contract

**Artifact:** A45  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A45 operationalizes the accounting boundary after A44 execution reconciliation. It defines how confirmed execution facts become an auditable position/accounting ledger and how internal state is compared with authoritative external state.

A45 does not invent instrument multipliers, fee schedules, settlement semantics, tax treatment, currency conversion, or risk-consumption formulas.

## 2. Canonical chain

```text
A43 Risk Authorization
        |
        v
A44 Order / Execution State
        |
        v
Confirmed Fill Events
        |
        +--> Position Effect
        +--> Account/Cash Effect
        +--> Cost References
        |
        v
Accounting Ledger
        |
        +--> Position State
        +--> Realized/Unrealized Economic State
        +--> Risk Reconciliation Input
        |
        v
External Reconciliation
```

## 3. Accounting source of truth

Only confirmed execution/accounting events may create position effects.

```text
order submitted != fill
order acknowledged != fill
fill observed but unconfirmed != accounting truth
confirmed fill -> accounting input
```

The exact confirmation authority is provider-specific and remains unresolved.

## 4. Immutable fill identity

Each fill must have a stable identity sufficient for idempotent processing:

```text
fill_id
order_intent_id
external_order_id
instrument_id
side
quantity
price
execution_time
received_time
provider_reference
currency
policy/version provenance
```

Fields unavailable from the provider remain explicitly unknown; they are not fabricated.

## 5. Idempotent ingestion

Processing the same confirmed fill more than once must not duplicate any derived effect.

```text
same fill_id
    -> same canonical event
    -> no second position effect
    -> no second accounting effect
```

A conflicting payload for an already-seen identity is a reconciliation/data-integrity exception, not a silent overwrite.

## 6. Position derivation

Position state is derived from confirmed fills.

Conceptually:

```text
PositionState(t)
    = deterministic aggregation of confirmed fills <= t
```

The sign/netting convention remains account/instrument specific.

A45 therefore does not hard-code long/short arithmetic beyond requiring deterministic, versioned semantics.

## 7. Partial fills

An order may produce multiple fills:

```text
OrderIntent
   |
   +--> Fill 1
   +--> Fill 2
   +--> Fill N
```

Each fill is independently traceable.

The aggregate execution state must preserve the underlying fill identities rather than replacing them with one opaque aggregate.

## 8. Partial exits

A partial exit changes position state but does not imply that the position is flat.

```text
prior quantity
    -> exit fill
    -> residual quantity
```

The method for assigning entry economics to partial exits remains unresolved by A45.

## 9. Corrections

Provider corrections must be represented as explicit correction/supersession relationships.

```text
original fill
    |
    v
correction event
    |
    v
reconstructed canonical state
```

The original record is retained for auditability.

## 10. Accounting ledger

Every derived accounting entry must reference its source event(s):

```text
ledger_entry_id
source_event_ids
entry_type
instrument_id
quantity/unit
currency
value when semantically defined
created_at
policy_version
```

A ledger entry without provenance is not production-auditable.

## 11. Economic values

A45 distinguishes:

```text
execution facts
accounting effects
expected economic values
realized economic values
unrealized economic values
```

A45 does not define the missing numerical mapping between these categories.

## 12. Costs

Costs remain separate ledger components.

```text
cost_id
source
semantic type
amount when defined
currency
effective time
provenance
```

A cost already included by an authoritative provider value must not be deducted again.

## 13. Valuation

Unrealized state requires an explicitly defined valuation snapshot.

The valuation snapshot must contain:

```text
instrument
price type
price
observation time
availability time
source
freshness/policy version
```

No universal bid/mid/ask/last/theoretical mark is assumed.

## 14. Risk reconciliation

A45 supplies accounting facts to risk reconciliation but does not redefine A32.

The reconciliation must be able to identify:

```text
unauthorized exposure
unexpected quantity
missing execution
position mismatch
stale valuation
missing cost
duplicate cost
risk ledger mismatch
```

Exact risk equations remain blocked.

## 15. External reconciliation

Internal state may be compared with provider/account state when authoritative provider semantics are available.

A mismatch must produce an explicit status:

```text
RECONCILED
MISMATCH
UNKNOWN
UNAVAILABLE
INVALID
```

A mismatch must not silently mutate the strategy state.

## 16. Deterministic reconstruction

Given the same immutable source events and policy versions, the same accounting state must be reproducible.

```text
SourceEvents + PolicyVersions
        |
        v
Deterministic Ledger
        |
        v
Position / Accounting State
```

## 17. Ordering

Events must be applied according to authoritative event time and deterministic tie-breaking rules.

Receipt order alone cannot redefine historical execution order when authoritative event timestamps are available.

## 18. Late events

A late-arriving event must be recorded with both:

```text
event_time
receipt_time
```

and processed according to the applicable event-ordering policy.

A late event must not be silently discarded because it arrived after a derived snapshot.

## 19. Snapshot invalidation

If a correction or late authoritative event changes a historical accounting state, affected derived snapshots must be marked stale/recomputable rather than silently left as if authoritative.

## 20. Reconciliation status lifecycle

```text
NOT_EVALUATED
    -> EVALUATING
    -> RECONCILED
    -> MISMATCH
    -> RESOLVED
```

Data unavailable or invalid states remain explicit:

```text
UNKNOWN
UNAVAILABLE
INVALID
```

Exact operational transition policy is provider/system dependent.

## 21. No retroactive strategy mutation

Accounting reconciliation cannot rewrite:

```text
prediction
eligibility
risk authorization
order intent
```

A corrected accounting state is a later authoritative fact.

## 22. Learning boundary

Accounting outcomes can become learning labels only after the A38 maturity contract is satisfied.

A45 does not bypass A38.

## 23. Failure handling

The framework must fail closed for required accounting facts that are:

```text
missing
ambiguous
contradictory
causally unavailable
provider-invalid
```

No zero-value/default-value substitution is permitted unless a separately resolved policy explicitly defines it.

## 24. Parameter classes

### Frozen architecture

```text
confirmed fills are accounting inputs
idempotent processing
immutable source events
correction lineage
provenance
partial-fill preservation
explicit reconciliation status
no retroactive strategy mutation
deterministic reconstruction
```

### External/source-defined

```text
fill confirmation authority
instrument multiplier
fee/tax schedule
settlement semantics
account netting
currency conversion
provider accounting semantics
external reconciliation guarantees
```

### Unresolved

```text
partial-exit accounting method
valuation policy
risk-consumption equation
exact economic P&L mapping
reconciliation timing
late-event operational policy
```

## 25. Implementation gate

A45 framework primitives may be implemented without numerical accounting assumptions.

Production accounting remains blocked until the required instrument, provider, execution, accounting, and risk semantics are resolved.

## Completion criterion

A45 becomes `RESOLVED` when a historical or live accounting state can be reconstructed from immutable source events and independently reconciled against the authoritative external state with explicit provenance and correction lineage.

## ARCHITECTURE STATUS

**FROZEN:** fill identity; idempotent accounting; position-from-confirmed-fills boundary; correction lineage; provenance; partial-fill preservation; explicit reconciliation states; deterministic reconstruction; no retroactive strategy mutation.

**UNRESOLVED:** provider confirmation authority; contract multiplier; cost/fee semantics; settlement; valuation; partial-exit accounting; risk-consumption mapping; external reconciliation guarantees.

**NEXT ARTIFACT:** A46 — Historical Replay / Deterministic State Reconstruction Contract.
