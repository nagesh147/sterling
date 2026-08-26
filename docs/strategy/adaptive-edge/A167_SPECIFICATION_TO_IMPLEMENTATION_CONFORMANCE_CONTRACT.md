# A167 — Specification-to-Implementation Conformance Contract

**Status:** CANONICAL
**Authority:** Specification-to-repository conformance gate
**Scope:** Adaptive Edge
**Dependencies:** A153–A166

## 1. Purpose

A167 is the mandatory bridge between the frozen Adaptive Edge specifications and repository implementation. It prevents semantic drift, duplicate authority, undocumented business logic, and false claims of implementation completeness.

The existence of a similarly named module or passing integration test is not sufficient for conformance.

```text
CANONICAL REQUIREMENT
    -> implementation mapping
    -> owner
    -> invariant
    -> failure semantics
    -> independent test/evidence
    -> code revision
    -> CONFORMANCE STATUS
```

## 2. Conformance statuses

```text
CONFORMANT
PARTIAL
NON_CONFORMANT
MISSING
EXTERNAL
RESEARCH_ONLY
NOT_APPLICABLE
UNKNOWN
```

`UNKNOWN` means the mapping cannot yet be established and therefore cannot satisfy a production gate.

## 3. Canonical requirement record

Every material requirement from A153–A166 must be representable as:

```text
ConformanceRecord {
    requirement_id
    source_artifact
    canonical_definition
    implementation_module
    implementation_symbol
    owner
    input_mapping
    output_mapping
    dependency_mapping
    invariant_mapping
    failure_mapping
    test_mapping
    status
    evidence_revision
    verification_timestamp
}
```

Requirement IDs must be stable. Renaming an implementation symbol must not silently create a new semantic requirement.

## 4. Authority hierarchy

The authority order is:

```text
canonical specification
    > approved implementation contract
    > implementation
    > tests
    > configuration
    > operational evidence
```

Tests demonstrate behavior; they do not redefine business semantics.

Implementation must not introduce business rules absent from the canonical specification. Configuration cannot override frozen invariants.

## 5. Historical versus V2.1 semantics

Recovered historical semantics and newly defined V2.1 semantics remain distinct.

```text
HISTORICAL_RECOVERED
V2.1_DEFINED
IMPLEMENTATION_PROPOSED
VALIDATED
BLOCKED
```

A proposed or inferred formula must never be represented as recovered historical truth.

## 6. Formula conformance

For each canonical formula `F(x1,...,xn)`, conformance requires preservation of:

```text
domain
units
input provenance
temporal availability
precision
missing-value semantics
boundary conditions
output semantics
version identity
```

Numerical equality on a small fixture is insufficient if the implementation violates the domain, units, timing, or failure semantics.

## 7. Temporal conformance

For decision time `t`, every dependency used by the decision must have been observable by `t`.

```text
available_at(dependency) <= decision_time(output)
```

Violation is a conformance failure.

Future prices, future bars/profiles, future option-chain state, future OI/Greeks, future fills, future outcomes, later model state, or future labels must not influence earlier decisions.

## 8. State-machine conformance

Every canonical state transition must map to an implementation transition preserving:

```text
trigger
preconditions
state transformation
postconditions
side effects
idempotency
recovery behavior
forbidden transitions
```

A code path that can create an impossible canonical state is non-conformant even if ordinary tests pass.

## 9. Execution conformance

Execution domains remain distinct:

```text
DECISION
  -> EXECUTION_INTENT
  -> ORDER_SUBMISSION
  -> ACKNOWLEDGED | UNCERTAIN | REJECTED
  -> FILL
  -> POSITION
  -> RECONCILIATION
```

The following identities are forbidden:

```text
DECISION == ORDER
ORDER == FILL
FILL == POSITION
```

Partial fills create actual exposure and therefore require immediate position supervision.

## 10. Provider boundary

Adaptive Edge provider architecture is:

```text
Market/research data: TrueData
Execution/broker:     Zerodha Kite Connect
```

Dhan is not an Adaptive Edge execution dependency.

Provider adapters expose canonical interfaces; they must not manufacture undocumented provider guarantees.

Provider documentation, mocks, or assumptions do not establish empirical provider conformance. Provider-specific semantics remain `EXTERNAL` until verified.

## 11. Research conformance

Research implementations must preserve:

```text
population definition
feature availability
label definition
label maturity
training boundary
validation boundary
test/holdout boundary
model version
configuration version
promotion evidence
```

```text
research infrastructure exists
    !=
research result validated
```

Walk-forward infrastructure does not by itself establish statistical validity.

## 12. Learned quantities

A learned quantity is conformant only when its lineage is reproducible:

```text
historical population
    -> label
    -> maturity
    -> training boundary
    -> fit
    -> validation
    -> test/holdout
    -> promotion
```

A hard-coded numerical value must not be represented as learned merely because it is later tunable.

## 13. Configuration conformance

Configuration is a parameterization of approved semantics, not an alternate business-logic layer.

```text
configuration
    -> validation
    -> authorized configuration
    -> runtime
```

A configuration that violates a frozen invariant is invalid regardless of operator intent.

## 14. Persistence and recovery conformance

Persistent state must preserve canonical identity, lineage, causality, and lifecycle consistency.

Recovery must be tested for at least:

```text
no position
open position
submission in progress
submission timeout
partial fill
exit in progress
broker/local mismatch
restart during uncertainty
```

Uncertainty must never be silently converted into success.

## 15. Audit and lineage conformance

Every consequential decision must eventually support reconstruction of:

```text
raw data
 -> canonical event
 -> state
 -> feature
 -> probability
 -> economics
 -> decision
 -> authorization
 -> execution
 -> position
 -> outcome
 -> label
 -> learning
 -> future model/version
```

Historical evidence is immutable except through an explicitly auditable correction mechanism.

## 16. Test evidence requirements

Critical semantics require tests whose expected behavior is derived independently from the implementation where practical.

This is forbidden:

```text
expected = implementation(input)
assert implementation(input) == expected
```

Required evidence classes may include:

```text
unit invariant tests
contract tests
state-transition tests
causal/leakage tests
property tests
adversarial tests
integration tests
provider verification tests
recovery tests
walk-forward validation
```

An integration test cannot replace a required local invariant test.

## 17. External versus implementation completeness

The following are separate states:

```text
IMPLEMENTATION_COMPLETE
CONFORMANCE_COMPLETE
PROVIDER_VERIFIED
RESEARCH_VALIDATED
PRODUCTION_READY
```

No state may imply another state unless A166 explicitly requires it and its evidence exists.

## 18. Duplicate authority attack

There must not be competing canonical implementations of the same business rule.

If multiple implementations exist:

```text
one canonical authority
    + derived implementations
    + equivalence/conformance tests
```

If two modules independently define different semantics for the same requirement, status is `NON_CONFORMANT` until reconciled.

## 19. Revision binding

Conformance evidence must bind to a concrete repository revision.

A passing test on revision `R1` does not establish conformance for revision `R2` when the relevant implementation changed.

At minimum, evidence must identify:

```text
code revision
requirement version
configuration version where applicable
formula/model version where applicable
test/evidence identity
verification timestamp
```

## 20. No false-green rule

```text
SKIPPED       -> PASS       FORBIDDEN
UNKNOWN       -> PASS       FORBIDDEN
UNTESTED      -> VERIFIED   FORBIDDEN
DOCUMENTED    -> VERIFIED   FORBIDDEN
MOCKED        -> PROVIDER_VERIFIED  FORBIDDEN
RESEARCH_ONLY -> PRODUCTION_READY   FORBIDDEN
```

## 21. Conformance decision

A requirement is `CONFORMANT` only when:

```text
canonical semantics identified
AND implementation owner identified
AND implementation behavior verified
AND required invariants covered
AND failure behavior covered
AND temporal constraints satisfied
AND evidence is revision-bound
AND no higher-authority contradiction exists
```

Otherwise the appropriate non-conformant status must be retained.

## 22. A167 acceptance gate

A167 is complete when:

```text
[ ] A153–A166 requirements have stable identifiers
[ ] each material requirement has one canonical authority
[ ] implementation ownership is explicit
[ ] implementation symbols are mapped
[ ] inputs/outputs are mapped
[ ] dependencies are mapped
[ ] invariants are mapped
[ ] failure semantics are mapped
[ ] tests/evidence are mapped
[ ] statuses use the canonical vocabulary
[ ] historical and V2.1 semantics remain separated
[ ] causal boundaries are explicit
[ ] provider dependencies are explicit
[ ] research-only semantics remain research-only
[ ] revision binding is explicit
[ ] duplicate authority has been attacked
[ ] no false-green path exists
```

## 23. Hostile review requirements

Attack the mapping for:

```text
look-ahead bias
information leakage
circular dependencies
duplicate authority
stale documentation
implementation/test circularity
provider-mock false confidence
impossible states
missing failure paths
partial-fill accounting errors
unverified external semantics
configuration overriding architecture
research code presented as production code
version drift
```

Synthetic adversarial cases must include at least:

```text
future-data injection
out-of-order event
duplicate event
partial fill
ambiguous broker submission
restart during execution
provider timeout
stale market data
invalid instrument
configuration corruption
model-version mismatch
```

## 24. Implementation source-of-truth rule

A167 is the canonical conformance contract between the frozen A153–A166 architecture and repository implementation.

If implementation contradicts a canonical requirement, implementation work stops at that contradiction until the specification is reconciled.

No new business logic may be introduced solely to make a conformance mapping pass.

## Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- specification-to-implementation traceability
- stable requirement identity
- single canonical authority
- explicit conformance vocabulary
- causal conformance
- state-machine conformance
- execution-domain separation
- provider boundary
- research/live separation
- learned-quantity lineage
- configuration validation boundary
- persistence/recovery conformance
- audit lineage
- independent test-evidence principle
- revision-bound evidence
- fail-closed conformance

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- final machine-readable requirement registry location
- final automated traceability-generation mechanism
- exact repository test/evidence indexing mechanism
- exact persistence of conformance evidence

CONFIGURATION TO VALIDATE:
- evidence retention
- traceability retention
- verification cadence
- required evidence classes by requirement severity

LEARNED / VALIDATION-DEPENDENT:
None. A167 defines conformance mechanics; it does not select strategy parameters.

BLOCKERS:
None for specification.
Repository implementation work remains blocked for any requirement whose status is
MISSING, PARTIAL, NON_CONFORMANT, UNKNOWN, or EXTERNAL and is mandatory for production.

NEXT ARTIFACT:
A168 — Module Ownership, Dependency Direction & Repository Refactoring Contract
```
