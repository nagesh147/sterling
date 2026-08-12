# Adaptive Edge V2 — Configuration, Policy Versioning and Runtime Governance Contract

**Artifact:** A48  
**Version:** 2.0.0-draft  
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED  
**Implementation:** FRAMEWORK-ONLY

## 1. Purpose

A48 defines how configuration, strategy policy, risk policy, execution policy, feature definitions, model versions, and runtime controls are identified, validated, activated, and audited.

The objective is to prevent mutable configuration from silently changing the meaning of historical or live decisions.

## 2. Configuration classes

Every parameter must belong to an explicit class:

```text
FROZEN
SOURCE_DEFINED
CONFIGURED
LEARNED
EXTERNAL_UNKNOWN
```

A parameter must not be treated as learned merely because it changes over time.

## 3. Semantic versioning

A change that alters the meaning of a policy, formula, input, transition, threshold, or state interpretation requires a new version.

Examples include changes to:

```text
feature definition
label definition
risk formula
eligibility rule
instrument selection
execution policy
protection policy
accounting policy
promotion rule
```

## 4. Configuration identity

A runtime decision must be traceable to an immutable configuration identity containing, as applicable:

```text
configuration_id
policy/version identifiers
activation time
deactivation time if applicable
source/provenance
owner
validation status
```

## 5. Activation boundary

A new policy/model/configuration version may affect decisions only at or after its explicit activation boundary:

```text
active_from >= promotion/approval time
```

It must not silently alter prior decisions.

## 6. Promotion

Promotion is an explicit state transition:

```text
DRAFT
  -> VALIDATED
  -> APPROVED
  -> ACTIVE
  -> RETIRED
```

Exact organizational approval requirements remain external.

## 7. Validation

A candidate configuration must be validated against the applicable evaluation contract before activation.

A configuration is not production-valid merely because it compiles or produces plausible output.

## 8. Immutable historical reference

Every decision record must retain the exact policy/model/configuration versions used at the decision boundary.

A later active version cannot be substituted during replay.

## 9. Runtime configuration changes

A live runtime change must create an auditable configuration event.

Silent environment-variable or database mutations that alter strategy semantics without a versioned event are prohibited.

## 10. Emergency controls

Runtime safety controls may include:

```text
GLOBAL_DISABLE
STRATEGY_DISABLE
ACCOUNT_DISABLE
INSTRUMENT_DISABLE
NEW_ENTRY_DISABLE
EXECUTION_DISABLE
```

These controls are operational state, not strategy predictions.

## 11. Emergency control semantics

A safety disable must define whether it affects:

```text
new decisions
new authorizations
new orders
existing positions
protection orders
cancellation/reconciliation
```

No automatic liquidation behavior is assumed unless explicitly defined by the protection/execution policy.

## 12. Kill switch

A kill switch is a runtime safety mechanism.

It must not be represented as:

```text
prediction = false
risk = zero
strategy edge = zero
```

unless a separate policy explicitly defines those semantics.

## 13. Configuration precedence

If multiple configuration sources exist, precedence must be explicit:

```text
source-defined contract
strategy policy
runtime configuration
emergency override
```

No hidden precedence is permitted.

## 14. Invalid configuration

A configuration must fail validation if required fields are:

```text
missing
invalid
out of range where range is defined
semantically incompatible
expired
unauthorized
version-inconsistent
```

Invalid configuration must not silently fall back to a prior version unless the fallback policy is explicit and auditable.

## 15. Unknown configuration

Unknown values are distinct from defaults.

The system must not infer:

```text
UNKNOWN -> 0
UNKNOWN -> false
UNKNOWN -> previous value
UNKNOWN -> recommended value
```

unless a documented policy authorizes the substitution.

## 16. Parameter provenance

Every nontrivial strategy parameter must identify:

```text
origin
semantic definition
unit
version
validation evidence
activation time
owner/source
```

## 17. Units

Configuration values with physical/economic dimensions must identify their units.

For example:

```text
currency
points
percentage
seconds
contracts
shares
risk units
```

A numeric value without a unit is not sufficient for a dimensionally constrained policy.

## 18. Parameter dependencies

Configuration dependencies must be explicit.

For example:

```text
RiskPolicyVersion
    depends on RiskMeasureVersion
```

A policy cannot claim a resolved dependency while using an unresolved semantic definition.

## 19. Compatibility

When one version depends on another, compatibility must be validated.

An incompatible combination must be rejected rather than silently coerced.

## 20. Runtime startup gate

A production strategy instance must verify at startup that all required versions are:

```text
present
compatible
approved
active
not expired
```

where applicable.

If required semantics are unresolved, the instance must enter a non-executable state.

## 21. Hot reload

Hot reload of strategy semantics is not permitted unless the reload mechanism creates an explicit versioned activation event and preserves the previous version for historical reconstruction.

Operational changes that do not alter semantics may use a separate non-strategy configuration channel.

## 22. Rollback

Rollback means activating a prior known-good version for future decisions.

It does not rewrite historical records that were produced under the failed version.

## 23. Canary / staged activation

A future production deployment may use staged activation:

```text
candidate
 -> canary
 -> broader activation
 -> full activation
```

Each stage must preserve version identity and activation timestamps.

A48 does not select traffic percentages or durations.

## 24. Runtime observability

The runtime should expose:

```text
active strategy version
active feature version
active model version
active risk policy version
active execution policy version
safety-control state
configuration validation state
```

This is operational evidence, not a replacement for immutable decision provenance.

## 25. Configuration drift

The system must detect when two components believe they are running different incompatible versions.

For example:

```text
decision service = strategy v2.3
sizing service   = risk policy expecting v2.4
```

Such incompatibility must fail closed where semantics could differ.

## 26. Distributed consistency

In a distributed deployment, activation of a new semantic version must account for propagation delay.

A decision cannot safely assume every service has the new version merely because the deployment command succeeded.

The exact deployment mechanism is infrastructure-specific.

## 27. Partial deployment

If components are running incompatible versions, the system must either:

```text
use an explicitly compatible combination
```

or:

```text
block execution
```

It must not silently mix semantics.

## 28. Policy registry

A canonical registry should be able to answer:

```text
which version existed?
when was it active?
what depended on it?
what validation approved it?
what decisions used it?
```

## 29. Learned parameter promotion

A learned parameter becomes operational only through the learning/promotion protocol.

The parameter must retain:

```text
training population
cutoff
validation evidence
candidate identity
promotion decision
active_from
```

## 30. Configuration versus learning

A configured parameter may be changed by an authorized policy owner.

A learned parameter must be produced through the defined research/validation/promotion pipeline.

The two processes must not be conflated.

## 31. Research configuration

Research-only parameters must be clearly marked so they cannot accidentally become production configuration.

A backtest configuration is not evidence of production authorization.

## 32. Production gate

A strategy cannot enter executable state if required dependencies remain:

```text
UNKNOWN
BLOCKED
UNVALIDATED
INCOMPATIBLE
EXPIRED
```

unless an explicit degraded mode is defined and authorized.

## 33. Audit trail

Configuration changes must retain:

```text
who/what initiated the change where available
old version
new version
reason
validation reference
time
activation status
```

Exact identity/audit infrastructure remains external.

## 34. Adversarial cases

### Silent threshold change

Changing a threshold in a database without creating a new policy version invalidates historical reproducibility.

### Model replacement

Replacing a model artifact without changing its identity/version is invalid if its behavior changes.

### Emergency disable

Disabling new entries does not automatically imply existing positions are closed.

### Rollback

Rollback affects future behavior only.

### Partial deployment

A service using an incompatible risk-policy version must not process executable sizing merely because its API is reachable.

### Unknown parameter

Unknown must not become a convenient default.

## 35. Implementation gate

A48 framework implementation may provide:

```text
configuration registry
version validation
activation events
compatibility checks
runtime state
rollback
safety controls
configuration audit
```

Production activation remains blocked for unresolved upstream semantic dependencies.

## 36. Parameter classes

### Frozen architecture

```text
versioned semantics
activation boundaries
immutable historical references
compatibility checks
runtime governance
safety-control separation
rollback
configuration audit
fail-closed unresolved dependencies
```

### Source-defined configuration

```text
provider settings
instrument metadata
calendar configuration
broker constraints
```

### Learned

```text
model parameters
learned thresholds
calibration parameters
validated adaptive parameters
```

only after the applicable learning/promotion contract is satisfied.

### External UNKNOWN

```text
organizational approval workflow
deployment infrastructure
provider configuration requirements
retention/audit obligations
```

## 37. Completion criterion

A48 becomes `RESOLVED` when every production decision can identify:

```text
all semantic versions used
why those versions were active
whether dependencies were compatible
which configuration activated them
whether a safety override applied
```

and historical replay can reconstruct the same version set.

## ARCHITECTURE STATUS

**FROZEN:** configuration classification; semantic versioning; activation boundaries; dependency compatibility; rollback; runtime safety separation; immutable historical references; fail-closed governance.

**UNRESOLVED:** deployment mechanism; approval workflow; exact runtime distribution semantics; provider-specific configuration requirements.

**BLOCKERS:** Production governance requires operational/deployment contracts beyond the strategy specification. The governance framework itself is defined.

**NEXT ARTIFACT:** A49 — Observability, Audit and Operational Integrity Contract.
