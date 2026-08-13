# A141 — Canonical Model/Policy Registry, Version Authority & Promotion/Rollback Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH
**Version:** 1.0

## Purpose

Define authoritative version identity and lifecycle for every production-affecting model, formula, policy, configuration, feature definition, label definition, execution model, and research artifact.

The registry is an authority for identity and lifecycle, not a source of hidden business logic.

## 1. Versioned artifact classes

```text
MODEL
POLICY
FORMULA
FEATURE_DEFINITION
LABEL_DEFINITION
CONFIGURATION
EXECUTION_MODEL
DATASET
EXPERIMENT
STRATEGY_BUNDLE
```

Every production-relevant artifact has an immutable version identity.

## 2. Authority rule

For an artifact class, exactly one canonical registry authority may declare the active version.

```text
ACTIVE_VERSION(class, scope, time)
```

must resolve deterministically or the dependent production action fails closed.

No local cache, filename, database default, or environment variable may silently override registry authority.

## 3. Immutable versions

A version is append-only.

```text
V1 -> V2 -> V3
```

V1 is never edited in place. A semantic change creates V2.

Metadata corrections that alter reproducibility create a new immutable version or explicit correction lineage; historical evidence is never silently rewritten.

## 4. Artifact manifest

Each version records, as applicable:

```text
artifact_id
artifact_type
version
parent_version
content_hash
schema_version
created_at
effective_at
retired_at
owner
source_experiment_id
configuration_hash
data_dependencies
code/build identity
compatibility constraints
status
```

Missing provider identifiers remain UNKNOWN; they are never fabricated.

## 5. Status lifecycle

```text
DRAFT
  -> VALIDATED
  -> APPROVED
  -> ACTIVE
  -> RETIRED
```

Failure paths include:

```text
DRAFT -> REJECTED
VALIDATED -> REJECTED
APPROVED -> REVOKED
ACTIVE -> ROLLED_BACK / RETIRED
```

A rejected or revoked version cannot become active without a new explicit approval lineage.

## 6. Promotion

Promotion consumes the acceptance evidence from A140.

Required lineage includes:

```text
candidate_version
experiment_id
validation_result
out_of_sample_result
risk_result
execution_result
robustness_result
approval_record
```

A version cannot become ACTIVE solely because it has the best historical score.

## 7. Atomic activation

Activation is a state transition, not an overwrite.

```text
old_version ACTIVE
       |
       v
new_version APPROVED
       |
       v
activation transaction
       |
       v
new_version ACTIVE
old_version RETIRED/ROLLBACK-ELIGIBLE
```

There must never be an observable state in which two mutually exclusive versions are both authoritative for the same scope and effective time.

## 8. Scope

Active-version identity is scoped by the smallest domain that requires independent versioning, potentially including:

```text
strategy
instrument family
market/session
environment
account
model role
```

The concrete scope taxonomy is configuration and must be explicitly registered.

## 9. Dependency compatibility

A strategy bundle may require compatible versions of:

```text
features
formulas
labels
models
risk policies
execution policies
instrument schema
configuration
```

The registry must validate compatibility before activation.

A missing or incompatible dependency blocks activation.

## 10. No floating dependencies

Production artifacts may not depend on:

```text
latest
current
master copy
unversioned configuration
mutable model file
```

Every dependency resolves to an immutable version.

## 11. Rollback

Rollback selects a previously approved compatible version for future decisions.

```text
V3 ACTIVE
   |
rollback
   v
V2 ACTIVE
```

Rollback does not rewrite:

```text
V3 decisions
V3 orders
V3 fills
V3 positions
V3 outcomes
```

Those remain attached to V3 lineage.

## 12. Rollback preconditions

Rollback requires:

```text
known target version
compatibility validation
scope validation
activation authorization
reason
causal timestamp
```

If the target version is incompatible with the current instrument/schema/execution environment, rollback is blocked.

## 13. Emergency rollback

Emergency rollback may bypass ordinary optimization but may not bypass safety invariants, identity, audit, compatibility, or causal recording.

The emergency path must remain separately auditable.

## 14. Registry failure

If the registry cannot resolve an authoritative version:

```text
normal new exposure -> BLOCKED
```

Existing positions continue through A136/A137 protection and emergency lifecycle semantics.

The system must not substitute an arbitrary cached version unless an explicitly validated failover authority exists.

## 15. Reproducibility

A historical decision resolves its exact version set from immutable lineage:

```text
decision
 -> strategy bundle
 -> model
 -> feature version
 -> formula version
 -> policy versions
 -> configuration version
 -> dataset/snapshot versions
```

Current ACTIVE versions must never be used to reinterpret historical decisions.

## 16. Learned versus frozen

The registry architecture is frozen. The registry does not decide which model is statistically superior; A140 provides the evidence and acceptance contract.

Learned quantities remain ordinary immutable versioned artifacts once promoted.

## 17. Failure conditions

Activation/promotion is blocked by:

```text
missing manifest
missing dependency
hash mismatch
incompatible dependency
unverified acceptance evidence
ambiguous scope
duplicate active authority
unapproved artifact
unresolved registry state
```

## 18. Audit lineage

Every activation/rollback records:

```text
transition_id
artifact/version
previous_active_version
new_active_version
scope
reason
approval evidence
operator/automation identity
effective_at
recorded_at
```

## 19. External dependencies

```text
REGISTRY TECHNOLOGY = UNKNOWN
PERSISTENCE TECHNOLOGY = UNKNOWN
DISTRIBUTED LOCK/ATOMICITY MECHANISM = TODO
ARTIFACT STORAGE = UNKNOWN
```

These are implementation dependencies, not architectural permission to weaken version authority.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- immutable artifact versions
- single canonical version authority per scope
- explicit artifact classes
- manifest and content identity
- lifecycle states
- promotion evidence requirement
- atomic activation semantics
- dependency compatibility
- no floating dependencies
- rollback without historical mutation
- emergency rollback boundary
- fail-closed registry uncertainty
- historical reproducibility
- complete activation/rollback lineage

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- registry technology
- persistence technology
- distributed atomicity/locking mechanism
- artifact storage technology

CONFIGURATION TO VALIDATE:
- scope taxonomy
- retention policy
- approval roles
- activation timing
- rollback eligibility window

LEARNED / VALIDATION-DEPENDENT:
None; promoted learned artifacts inherit their validated version identity.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A142 — Canonical Runtime Configuration, Feature-Quality Gate & Operational Readiness Contract
```
