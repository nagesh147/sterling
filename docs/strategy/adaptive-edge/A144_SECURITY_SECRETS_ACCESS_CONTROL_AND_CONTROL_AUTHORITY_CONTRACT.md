# A144 — Canonical Security, Secrets, Access-Control & Control-Authority Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH  
**Version:** 1.0

## Purpose

Define the security and authority boundary for Adaptive Edge without introducing broker-specific assumptions that have not been verified.

A144 governs who or what may read, create, modify, revoke, execute, promote, recover, or override canonical state.

It does not redefine trading logic, risk mathematics, broker semantics, or model policy.

## 1. Security domains

Security is separated into:

```text
IDENTITY
AUTHENTICATION
AUTHORIZATION
SECRETS
CONTROL AUTHORITY
AUDIT
RECOVERY
```

Authentication establishes who/what an actor is. Authorization establishes what that actor may do. Neither is sufficient without the other.

## 2. Canonical actor classes

Actors are classified as:

```text
STRATEGY_RUNTIME
EXECUTION_ADAPTER
DATA_ADAPTER
RESEARCH_PROCESS
MODEL_REGISTRY
OPERATIONS
ADMINISTRATOR
HUMAN_OPERATOR
RECOVERY_PROCESS
READ_ONLY_AUDITOR
```

An actor receives only the permissions required for its declared responsibility.

## 3. Least privilege

Every capability must be explicitly granted.

Absence of a permission means denial:

```text
permission absent -> DENY
```

No component may infer administrative authority from technical connectivity.

## 4. Domain ownership

Canonical authority follows domain ownership:

```text
strategy -> strategy decisions
execution adapter -> broker interaction
instrument authority -> contract identity
market-data authority -> market evidence
model registry -> model versions
configuration registry -> approved runtime configuration
operations -> operational controls
```

An actor cannot modify another domain's authoritative state merely because it can technically access the storage mechanism.

## 5. Secret boundary

Secrets include, where applicable:

```text
API credentials
oauth/session credentials
private keys
signing material
encryption keys
provider tokens
webhook secrets
```

Secrets must never be treated as ordinary configuration values, model inputs, audit payloads, logs, metrics, source-controlled files, or decision features.

Secret values must not enter canonical decision lineage.

Only a non-secret credential/reference identifier may be recorded where auditability requires it.

## 6. Secret lifecycle

Canonical lifecycle:

```text
PROVISIONED
    -> ACTIVE
    -> ROTATION_REQUIRED
    -> ROTATED
    -> REVOKED
    -> RETIRED
```

A secret must never be silently replaced while preserving the identity of the old credential.

Credential rotation creates a new credential lineage.

## 7. Authentication failure

Authentication failure is a distinct operational state:

```text
AUTHENTICATION_FAILURE
```

It must not be interpreted as:

```text
NO_MARKET_DATA
NO_POSITION
ORDER_REJECTED
```

Normal new exposure is blocked when a mandatory authenticated dependency cannot be established.

Existing-position protection and emergency behavior remain governed by A126/A135/A143 rather than being silently disabled.

## 8. Authorization classes

Permissions are divided into:

```text
READ_MARKET_DATA
READ_ACCOUNT_STATE
CREATE_DECISION
CREATE_AUTHORIZATION
CREATE_ORDER_INTENT
SUBMIT_ORDER
CANCEL_ORDER
MODIFY_ORDER
RECONCILE
PROTECT_POSITION
EMERGENCY_FLATTEN
PROMOTE_MODEL
CHANGE_CONFIGURATION
ROTATE_SECRET
OVERRIDE_OPERATIONAL_STATE
```

These capabilities are intentionally separate.

For example:

```text
SUBMIT_ORDER != CANCEL_ORDER
SUBMIT_ORDER != PROMOTE_MODEL
READ_ACCOUNT_STATE != MODIFY_ACCOUNT_STATE
```

## 9. Human control

Human operators are not automatically granted unrestricted authority.

A human control action must record:

```text
actor_id
action
scope
reason
time
approval/context reference
previous state
requested state
result
```

Manual override must not erase the automated decision or execution lineage that preceded it.

## 10. Dangerous operations

The following require explicit elevated authority:

```text
EMERGENCY_FLATTEN
MODEL_PROMOTION
PRODUCTION_CONFIGURATION_CHANGE
SECRET_ROTATION
DISABLE_RISK_CONTROL
DISABLE_PROTECTION
RECONCILIATION_OVERRIDE
```

A dangerous operation must be auditable and attributable to an authenticated actor/process.

## 11. Emergency authority

Emergency execution must remain available independently of ordinary strategy authorization, but this does not mean unrestricted execution authority.

The emergency path must be:

```text
explicit
scoped
auditable
least-privileged
idempotent
reconcilable
```

An emergency action cannot mutate historical state to justify itself.

## 12. Control-plane / data-plane separation

The system separates:

```text
DATA PLANE
market observation
strategy evaluation
order/fill processing
position state

CONTROL PLANE
configuration
model promotion
runtime enable/disable
secret lifecycle
operational override
```

Control-plane changes must not silently alter historical data-plane records.

## 13. Configuration authority

A runtime configuration is executable only when it is:

```text
identified
versioned
validated
approved
compatible with dependency versions
within its permitted scope
```

A configuration change creates a new version rather than mutating the version used by historical decisions.

A142 owns readiness; A141 owns version authority.

## 14. Model authority

Only an approved model version may be activated for production.

Model promotion/revocation belongs to A141 and its acceptance prerequisites from A140.

A runtime component cannot activate an arbitrary model artifact merely because it can read it.

## 15. Access to audit records

Audit records are append-only from the perspective of trading/runtime actors.

A runtime component may create an audit event but may not rewrite historical audit evidence.

Correction requires a new compensating record with lineage to the original record.

## 16. Time and authorization

Authority is time-scoped where required:

```text
issued_at <= current_time < expires_at
```

Expired credentials, permissions, approvals, and operational overrides cannot be treated as current authority.

Clock semantics must use the canonical time contract; local process clocks are not independently authoritative for causal market decisions.

## 17. Multi-party approval

Where policy requires separation of duties, the same actor/process must not satisfy both independent approval roles.

The exact approval count is configuration/policy and remains UNKNOWN until operational requirements are documented.

## 18. Fail-closed behavior

For mandatory security dependencies:

```text
identity unknown
credential invalid
permission unknown
approval invalid
secret unavailable
```

must not become implicit authorization.

Default:

```text
unknown authority -> DENY
```

## 19. Recovery and break-glass

Break-glass access is an explicit emergency mechanism, not a hidden administrator bypass.

A break-glass action must record:

```text
actor
credential/authority reference
time
scope
reason
operation
result
post-action review reference
```

Break-glass does not authorize retrospective mutation of immutable audit history.

## 20. Security incident boundary

Security incidents integrate with A143.

Examples:

```text
credential compromise
unauthorized access
secret exposure
unexpected privilege use
configuration tampering
model artifact tampering
audit-store integrity failure
```

Security incidents may cause:

```text
BLOCK_NEW_EXPOSURE
REVOKE_AUTHORITY
ROTATE_SECRET
RECONCILE
EMERGENCY_CONTROL
```

according to policy.

## 21. Tamper detection

Security-sensitive artifacts require integrity evidence sufficient to detect unauthorized modification.

The exact mechanism is UNKNOWN until the persistence/security platform is selected.

The architecture requires:

```text
artifact identity
version identity
integrity evidence
actor attribution
change lineage
```

## 22. External provider dependency

The broker is currently architecturally represented by the verified execution adapter boundary. Provider-specific authentication flows, token lifetime, scopes, session semantics, rate limits, and guarantees remain external dependencies.

```text
BROKER_AUTH_SEMANTICS = TODO/UNKNOWN
```

No provider-specific guarantee is invented here.

## 23. Security state machine

```text
UNKNOWN
  |
  v
AUTHENTICATED
  |
  v
AUTHORIZED
  |
  +--> EXPIRED
  +--> REVOKED
  +--> SUSPENDED
```

Invalid authentication cannot transition directly to authorized operation.

## 24. Hostile scenarios

### Credential leak

Revoke/rotate the affected credential and record the incident. Do not continue normal exposure merely because the broker connection still works.

### Stolen operational credential

Least privilege limits reachable operations; incident response may revoke the authority.

### Unauthorized configuration change

Reject activation and generate a security/operational incident.

### Model tampering

Reject activation unless integrity and registry lineage are valid.

### Expired approval

Deny the controlled operation.

### Duplicate emergency command

Emergency execution remains idempotent and reconciled through A135.

### Operator attempts historical edit

Forbidden. Create a compensating audit record instead.

### Audit store unavailable

Normal new exposure is blocked when required audit guarantees are unavailable; emergency/protection handling follows A143/A126 policy.

### Secret appears in logs

Security incident; redact downstream presentation and rotate/revoke according to documented response policy. The original immutable audit record must not be rewritten to conceal the event.

## 25. Frozen architecture

```text
identity/authentication/authorization separation
least privilege
explicit actor classes
domain authority boundaries
secret/configuration separation
secret lifecycle
fine-grained execution permissions
human-action attribution
emergency authority boundary
control-plane/data-plane separation
immutable audit boundary
time-scoped authority
fail-closed unknown authority
break-glass auditability
tamper-evidence requirement
security-incident integration
```

## 26. Configuration / validation dependent

```text
role definitions
approval requirements
credential rotation cadence
session/token lifetime
emergency authority scope
security monitoring thresholds
break-glass review requirements
secret storage technology
identity provider
key-management technology
```

These must be documented and validated before production deployment.

## 27. External dependencies

```text
IDENTITY_PROVIDER = TODO/UNKNOWN
SECRET_MANAGER = TODO/UNKNOWN
KEY_MANAGEMENT = TODO/UNKNOWN
AUDIT_STORAGE = TODO/UNKNOWN
BROKER_AUTHENTICATION_SEMANTICS = TODO/UNKNOWN
```

The architecture does not assume a specific vendor or technology.

# Architecture Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- identity/authentication/authorization separation
- least privilege
- explicit actor classes
- domain authority boundaries
- secret/configuration separation
- secret lifecycle
- fine-grained execution permissions
- human-action attribution
- emergency authority boundary
- control-plane/data-plane separation
- immutable audit boundary
- time-scoped authority
- fail-closed unknown authority
- break-glass auditability
- tamper-evidence requirement
- security-incident integration

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
- identity provider
- secret manager
- key-management technology
- audit storage technology
- broker authentication/session semantics

CONFIGURATION TO VALIDATE:
- role definitions
- approval requirements
- credential rotation cadence
- token/session lifetime
- emergency authority scope
- security monitoring thresholds
- break-glass review requirements

LEARNED / VALIDATION-DEPENDENT:
None. Security authority is not a learned trading parameter.

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A145 — Canonical External Dependency, Environment & Provider Capability Contract
```
