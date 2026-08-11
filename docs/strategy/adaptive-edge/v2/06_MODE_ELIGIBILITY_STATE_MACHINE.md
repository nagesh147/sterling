# Adaptive Edge V2 — Operating Mode and Eligibility State Machine

**Version:** 2.0.0-draft
**Artifact:** A30
**Status:** SPECIFICATION-DRAFT / PARTIALLY-BLOCKED
**Depends on:** A25, A26, A28, A29
**Implementation authorization:** NONE

## Purpose

A30 defines the causal state-machine boundary between economic assessment and subsequent risk authorization.

The fundamental invariant is:

```text
OperatingMode != RiskAuthorization
```

A mode may influence eligibility policy, but a mode transition must not silently increase or decrease authorized risk unless a separate, explicit, versioned risk-policy transition authorizes that change.

## Canonical state separation

OperatingMode is the strategy's current operating regime under a versioned mode policy. The initial architectural vocabulary is:

```text
NORMAL
RESTRICTED
DISABLED
```

No numerical transition threshold is frozen.

Eligibility is the decision-time status of a specific opportunity:

```text
ELIGIBLE
INELIGIBLE
INSUFFICIENT_INFORMATION
BLOCKED
```

RiskAuthorization is separate state representing explicit permission to expose risk. It is not inferred merely from OperatingMode.

## Causal dependency

```text
Market / Strategy State
        |
        v
OperatingMode
        |
        v
EligibilityPolicy
        |
        v
Eligibility
        |
        v
RiskPolicy
        |
        v
RiskAuthorization
```

Forbidden implicit mappings include:

```text
Mode = NORMAL -> automatically larger risk
Mode = RESTRICTED -> automatically smaller risk
Eligibility = ELIGIBLE -> RiskAuthorization = MAX
Prediction score increased -> AuthorizedRisk increased
```

unless a separately versioned risk-policy definition explicitly establishes the relationship.

## State transition contract

For state `S_t` and event `e_t`:

```text
S_{t+1} = Transition(S_t, e_t, PolicyVersion)
```

A transition is valid only when its preconditions are satisfied and its postconditions hold. Forbidden transitions must fail rather than being coerced into another state.

Every transition must identify:

```text
strategy_version
policy_version
source_event_id
transition_time
previous_state
new_state
reason
provenance
```

## Causal boundary

A transition at `t_d` may consume only state available by `t_d`.

The following are forbidden as contemporaneous mode/eligibility inputs:

```text
future outcome
future P&L
future fill
future label
```

Historical learning may inform a future promoted policy only through the separately versioned learning and promotion process.

## Eligibility transition

```text
Candidate
   |
   +--> invalid / insufficient data -> INSUFFICIENT_INFORMATION or BLOCKED
   |
   v
EconomicAssessment
   |
   v
Mode/Eligibility Policy
   |
   +--> fail -> INELIGIBLE
   |
   +--> pass -> ELIGIBLE
```

`ELIGIBLE` does not mean risk-authorized, sized, executable, filled, or profitable.

## Disabled and restricted states

`DISABLED` prevents new strategy opportunities from becoming executable. It does not implicitly liquidate existing positions. Position-management behavior belongs to later position/protection artifacts.

`RESTRICTED` means the eligibility policy operates under a more restrictive policy state. It does not itself specify risk amount, position size, instrument, stop, or exit.

`NORMAL` is the baseline operating state and does not imply a particular risk budget or minimum expected value.

## Mode state identity

```text
mode_state_id
strategy_version
mode_policy_version
state
entered_at
source_event_id
transition_reason
provenance
```

The transition record is immutable.

## Eligibility identity

```text
eligibility_id
opportunity_id
strategy_version
mode_state_id
economic_assessment_id
eligibility_policy_version
result
reason_codes
decision_time
provenance
```

Eligibility must be persisted rather than reconstructed later from mutable state.

## Mode hysteresis

If numerical thresholds are eventually introduced, the policy must explicitly define whether hysteresis exists. A30 does not select a hysteresis value or require hysteresis; it requires the behavior to be specified if threshold crossings can produce repeated transitions.

## Transition atomicity and ordering

A mode transition must be recorded atomically with its triggering event and policy version. The system must not represent two conflicting current modes for the same effective timestamp/version.

If events overlap or share timestamps, a canonical deterministic event-ordering rule must determine their sequence. Strategy decisions must not depend on nondeterministic processing order.

## Data-quality interaction

Data-quality degradation may cause `RESTRICTED` or `DISABLED` only if the policy explicitly defines that transition. Missing data must not silently mean zero risk or an exit.

Required transition inputs that are missing, stale, invalid, ambiguous, out of order, or from an unauthorized policy version must produce an explicit failure state/reason code.

## Versioning

Every mode and eligibility transition identifies:

```text
strategy_version
mode_policy_version
eligibility_policy_version
```

Changing a threshold, transition rule, or state definition creates a new policy version.

## Adversarial scenarios

### Strong prediction, bad economics

```text
Prediction appears strong
ExpectedNetValue is insufficient
```

Result:

```text
INELIGIBLE
```

### Strong economics, disabled mode

```text
ExpectedNetValue passes
OperatingMode = DISABLED
```

Result:

```text
BLOCKED / INELIGIBLE
```

### Eligible, but no risk authorization

```text
Eligibility = ELIGIBLE
RiskAuthorization = unavailable
```

Result:

```text
NO_EXECUTION
```

### Mode changes after eligibility

If mode changes after eligibility but before execution, the execution artifact must define whether the decision remains valid, expires, or requires revalidation. A30 deliberately does not invent that rule.

### Replay

Identical ordered events plus identical policy versions must produce the same state sequence. Otherwise the state machine is not deterministic.

## Forbidden transitions

```text
future outcome -> current mode
future label -> current eligibility
realized P&L -> current eligibility
UI state -> strategy mode
prediction -> risk authorization without explicit policy
mode transition -> automatic position liquidation
ELIGIBLE -> FILLED without execution stage
```

## Invariants

At every decision timestamp:

```text
exactly one current OperatingMode exists
exactly one applicable mode-policy version exists
an Eligibility record references one mode state
Eligibility does not imply RiskAuthorization
RiskAuthorization is independently versioned
future information is absent from transition inputs
```

## What A30 does not define

A30 does not select:

```text
mode thresholds
edge thresholds
risk budgets
position sizes
strike/expiry rules
stop distances
profit targets
re-entry counts
```

Those belong to later artifacts.

## Dependencies

A29 provides the economic assessment consumed by eligibility.

The risk authorization artifact will define the separate risk state and its policy transitions.

The data/event-ordering contract defines deterministic event ordering and availability.

The position artifact defines behavior when mode changes while a position already exists.

## Completion criterion

A30 is complete as an architectural state-machine artifact when OperatingMode is distinct from RiskAuthorization, Eligibility is distinct from execution, state identities are versioned, transitions have explicit event/precondition/postcondition structure, future information is forbidden, failure states are explicit, and mode changes cannot silently mutate positions.

Numerical transition policies remain unresolved.

## ARCHITECTURE STATUS

Frozen:

```text
OperatingMode state abstraction
Eligibility state abstraction
RiskAuthorization separation
causal transition boundary
versioned policy identity
state transition structure
fail-closed principle
mode/position separation
```

## UNRESOLVED

```text
exact mode definitions
mode transition conditions
eligibility thresholds
hysteresis policy
risk-policy mapping
transition ordering for simultaneous events
behavior when mode changes during an existing position
```

## BLOCKERS

No blocker to the state-machine architecture. Exact transition mathematics remains blocked until prediction/economic target semantics and later policy artifacts are resolved.

## NEXT ARTIFACT

**A31 — Risk Authorization Definition**

A31 must define exactly what `AuthorizedRisk` means, how it is granted, consumed, revoked, and versioned. It must not infer risk from prediction score, P&L, stop distance, premium, or position size unless those relationships are explicitly defined and dimensionally complete.
