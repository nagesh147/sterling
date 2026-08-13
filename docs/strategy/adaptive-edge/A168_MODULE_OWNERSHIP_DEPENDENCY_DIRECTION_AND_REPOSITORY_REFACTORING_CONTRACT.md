# A168 — Module Ownership, Dependency Direction & Repository Refactoring Contract

**Status:** CANONICAL
**Authority:** Repository architecture and dependency-direction gate
**Scope:** Adaptive Edge implementation
**Dependencies:** A153–A167

## 1. Purpose

A168 translates the frozen Adaptive Edge domain contracts into repository ownership and dependency rules. It defines which layer owns each business concept, which direction dependencies may flow, where provider adapters belong, and how existing code may be refactored without introducing new business semantics.

A168 is a structural contract. It does not choose strategy parameters or alter trading logic.

## 2. First principle

Dependency direction must follow business ownership, not current file layout.

```text
DOMAIN / CANONICAL SEMANTICS
          ^
          |
APPLICATION ORCHESTRATION
          ^
          |
INFRASTRUCTURE / PROVIDERS
```

The exact repository package names may change. The ownership rules may not.

## 3. Canonical layers

```text
DOMAIN
APPLICATION
RESEARCH
INFRASTRUCTURE
INTERFACE
TEST
```

### DOMAIN
Owns canonical entities, value objects, invariants, state transitions, mathematical contracts, and pure business semantics.

### APPLICATION
Owns orchestration, sequencing, authorization flow, lifecycle coordination, and use-case execution. It must not redefine domain formulas.

### RESEARCH
Owns dataset construction, labeling, walk-forward evaluation, model fitting, validation, promotion evidence, and research-only workflows.

### INFRASTRUCTURE
Owns persistence, clocks, provider adapters, broker connectivity, market-data transport, external services, and operational mechanisms.

### INTERFACE
Owns API/CLI/UI/transport representations. It must not become a business-rule authority.

### TEST
Owns executable verification of contracts. Test fixtures and helpers must not become production dependencies.

## 4. Ownership rule

Every material concept has exactly one semantic owner.

Examples:

```text
instrument identity       -> DOMAIN
market-event semantics    -> DOMAIN
feature definition        -> DOMAIN/RESEARCH according to canonical ownership
probability contract      -> DOMAIN
model fitting             -> RESEARCH
risk authorization        -> DOMAIN/APPLICATION boundary
order lifecycle           -> DOMAIN
broker protocol           -> INFRASTRUCTURE
persistence mechanism     -> INFRASTRUCTURE
session calendar adapter  -> INFRASTRUCTURE
orchestration             -> APPLICATION
HTTP/CLI serialization    -> INTERFACE
```

If two modules both define the same business meaning, one must become a derived adapter or the design is non-conformant.

## 5. Dependency rules

Allowed high-level direction:

```text
INTERFACE -> APPLICATION -> DOMAIN
APPLICATION -> INFRASTRUCTURE through explicit ports
RESEARCH -> DOMAIN
RESEARCH -> approved data/infrastructure ports
INFRASTRUCTURE -> DOMAIN contracts
TEST -> any layer under test
```

Forbidden:

```text
DOMAIN -> broker SDK
DOMAIN -> database driver
DOMAIN -> HTTP framework
DOMAIN -> environment secrets
DOMAIN -> UI
DOMAIN -> concrete provider implementation
```

Application code must not import concrete broker/data-provider semantics where a canonical port is required.

## 6. Provider adapter rule

External providers are behind explicit adapters.

```text
canonical port
    |
    +--> TrueData adapter
    +--> Kite adapter
```

Provider response models must be normalized into canonical domain events before downstream business logic consumes them.

Provider-specific fields may remain attached as provenance metadata where required, but they cannot silently redefine canonical semantics.

## 7. Broker ownership

Kite is the Adaptive Edge execution provider.

The repository must not introduce Dhan as an alternate execution path unless the architecture is explicitly changed and re-approved.

Broker-specific behavior belongs in infrastructure adapters and provider capability contracts.

## 8. Data ownership

Raw provider payloads belong to infrastructure ingestion.

Canonical market events belong to the domain boundary.

Derived features belong to their declared semantic owner and must carry provenance.

The following layering is mandatory:

```text
raw payload
   -> adapter normalization
   -> canonical event
   -> state
   -> feature
   -> decision
```

A downstream module must not reach backward into raw provider payloads to obtain a value that should have been part of the canonical event contract.

## 9. State ownership

Canonical state machines own legal state transitions.

Orchestration may request a transition but must not independently mutate state in a way that bypasses transition invariants.

Persistence reconstructs state; it does not define what states mean.

## 10. Mathematical ownership

Canonical formulas must have one authoritative implementation location or an explicitly designated generated implementation.

Consumers may call formulas.

Consumers may not redefine them locally through duplicated arithmetic.

```text
canonical formula
      |
      +--> decision
      +--> risk
      +--> economics
      +--> research
```

If different domains require different definitions, they must have different canonical names and explicit semantics rather than accidental divergence.

## 11. Configuration ownership

Configuration parsing belongs to infrastructure/application boundaries.

Configuration validation belongs at the boundary where the configuration becomes authoritative.

Domain code receives validated values and must not silently reinterpret raw environment/configuration strings.

## 12. Persistence ownership

Persistence is infrastructure.

Persistence implementations must preserve domain identity and event semantics but must not introduce domain transitions.

```text
DOMAIN EVENT
    -> persistence port
    -> storage adapter
```

A database schema is not a substitute for the canonical domain model.

## 13. Research boundary

Research code must not become a hidden production dependency.

Forbidden:

```text
production execution
    -> training notebook
    -> ad-hoc research script
    -> mutable experiment state
```

Approved promotion produces immutable, versioned artifacts consumed through explicit production contracts.

## 14. Interface boundary

API/UI/CLI representations must not define business semantics.

```text
interface request
    -> application command
    -> domain decision
```

Changing an external representation must not silently change strategy semantics.

## 15. Time ownership

The system must not scatter calls to wall-clock time throughout business logic.

Time-dependent domain decisions consume explicit timestamps/clock abstractions so causal testing and replay remain possible.

Infrastructure owns the real clock; domain/application code consumes the declared time input.

## 16. Dependency injection

External capabilities must enter business workflows through explicit ports/interfaces.

This includes:

```text
market data
broker
clock
calendar
persistence
audit sink
secrets
observability
```

A concrete external dependency hidden inside a domain function is non-conformant.

## 17. Refactoring rule

Refactoring may change:

```text
file location
module name
class/function organization
internal representation
adapter structure
```

only if externally observable canonical semantics remain unchanged.

Refactoring must not silently change:

```text
state transitions
timestamps
risk authorization
execution semantics
formula definitions
feature timing
provider authority
accounting
```

## 18. Migration strategy

Existing code must be migrated incrementally:

```text
identify authority
    -> freeze behavior
    -> introduce boundary
    -> move implementation
    -> preserve tests
    -> add conformance tests
    -> remove duplicate authority
```

Do not perform a large rewrite that simultaneously changes architecture and business semantics.

## 19. Dependency-cycle prohibition

The implementation graph must be acyclic at the architectural layer.

A cycle such as:

```text
DOMAIN -> APPLICATION -> DOMAIN
```

through concrete imports is forbidden.

Runtime event loops are not architectural import cycles and must remain explicit orchestration mechanisms.

## 20. Failure ownership

Failures belong to the layer that can correctly classify and recover from them.

Examples:

```text
malformed provider payload -> adapter
stale provider data       -> data-quality/domain boundary
invalid state transition  -> domain
broker rejection          -> broker adapter/application
unknown submission        -> execution lifecycle
storage outage            -> infrastructure
risk violation            -> risk/domain
```

A lower-level exception must not be silently converted into a successful business result.

## 21. Audit ownership

Audit lineage is generated at the semantic boundary where the consequential fact is created.

Infrastructure may persist audit records but must not invent decision rationale.

Every consequential record must identify its source event and version context.

## 22. Testing architecture

Tests must be aligned with ownership.

```text
DOMAIN       -> invariant/property/contract tests
APPLICATION  -> orchestration/state-sequencing tests
RESEARCH     -> statistical/walk-forward tests
INFRASTRUCTURE -> adapter/provider/recovery tests
INTERFACE    -> serialization/API tests
```

A passing end-to-end test cannot replace a missing domain invariant test.

## 23. Repository structure rule

The repository may use existing paths where they already satisfy ownership. New directories are not required merely for aesthetic symmetry.

The goal is semantic ownership, not folder proliferation.

Before moving a module, identify:

```text
current owner
required owner
incoming dependencies
outgoing dependencies
public symbols
tests
configuration
persistence implications
```

## 24. Refactoring acceptance

A refactor is accepted only when:

```text
canonical semantics unchanged
AND dependency direction valid
AND no duplicate authority remains
AND public contract changes are explicit
AND causal behavior preserved
AND invariant tests pass
AND conformance mapping remains valid
```

## 25. Hostile review

Attack repository structure for:

```text
circular imports
hidden provider dependencies
domain code accessing infrastructure
research code imported by production
business logic in serializers
business logic duplicated in adapters
configuration bypasses
wall-clock leakage
persistence-defined semantics
duplicate formula implementations
state mutation outside state machines
```

## Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- semantic ownership
- six-layer architecture
- dependency direction
- explicit provider adapters
- Kite execution boundary
- TrueData market/research boundary
- domain state ownership
- canonical formula ownership
- configuration boundary
- persistence boundary
- research/live separation
- explicit external-capability ports
- time/clock boundary
- failure ownership
- audit ownership
- ownership-aligned testing
- incremental refactoring rule
- no semantic changes hidden inside refactoring

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- exact final repository module names after conformance mapping
- exact persistence implementation
- exact dependency-injection framework/mechanism
- exact provider adapter package locations

CONFIGURATION TO VALIDATE:
- module-level dependency lint rules
- import-cycle enforcement
- ownership review policy
- migration sequencing

LEARNED / VALIDATION-DEPENDENT:
None.

BLOCKERS:
None for specification.
Implementation refactoring is blocked only where A167 identifies missing,
partial, non-conformant, or externally unverified behavior.

NEXT ARTIFACT:
A169 — Runtime Composition, Event Flow & Causal Orchestration Contract
```
