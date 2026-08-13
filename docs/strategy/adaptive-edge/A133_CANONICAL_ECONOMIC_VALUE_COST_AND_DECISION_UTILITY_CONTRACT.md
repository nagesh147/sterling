# A133 — Canonical Economic Value, Cost, and Decision Utility Contract

**Status:** CANONICAL / IMPLEMENTATION SOURCE OF TRUTH
**Version:** 1.0
**Depends on:** A126, A127, A128, A129, A130, A131, A132

## Purpose

Define the canonical boundary from probabilistic evidence to ex-ante economic value and decision utility. A133 does not place orders or authorize execution.

```text
A132 Probability / Edge Evidence
            |
            v
A133 Economic Assessment
            |
            +--> Risk
            +--> Execution Economics
            +--> Utility
            |
            v
Decision Eligibility
```

## Frozen separation

The following are distinct:

```text
probability
expected gross outcome
expected execution cost
expected net value
risk exposure
utility
eligibility
order intent
```

Therefore:

```text
high probability != positive economic value
positive expected value != permitted trade
permitted trade != order submission
```

## Action-conditioned economics

For action `a`, outcome `Y`, and causal information set `I_t`:

```text
GrossEV(a,t) = E[G(a,Y) | I_t]
```

For discrete outcomes:

```text
E[G(a,Y) | I_t] = Σ_y P(Y=y | I_t) G(a,y)
```

Expected net value:

```text
NetEV(a,t) = GrossEV(a,t) - ExpectedCost(a,t)
```

All inputs must satisfy:

```text
available_at(input) <= decision_time
```

## Explicit action

Every assessment identifies:

```text
action_id
instrument_id
side
quantity/sizing reference
entry policy
payoff definition
outcome horizon
product semantics
```

The action set always contains:

```text
NO_ACTION
```

## Payoff semantics

`G(a,Y)` must represent the actual economic payoff of the instrument/action. Underlying directional return must not be substituted for option payoff.

Existing positions must be included:

```text
existing_position + proposed_action = resulting_position
```

Partial fills must be represented explicitly; full fill cannot be assumed.

## Cost semantics

Expected cost is ex-ante and may contain applicable components such as:

```text
spread
slippage
commission
exchange charges
statutory taxes/levies
other contract-specific transaction costs
```

Unknown cost is **not zero**. It produces an unavailable/degraded assessment according to policy.

Future realized costs cannot enter pre-trade economics.

## Execution uncertainty

When fill probability materially affects economics:

```text
E[G_net]
=
P(fill) * E[G_net | fill]
+
P(no_fill) * G(no_fill)
```

The fill model is external to A133 and must be versioned.

## Risk separation

Positive `NetEV` does not authorize an action.

```text
RiskMeasure(action, state_t) <= RiskLimit(state_t)
```

Risk semantics are owned by the risk/lifecycle contracts.

## Utility

Utility is explicit:

```text
Utility(a,t) = E[U(G_net(a,Y)) | I_t]
```

Expected monetary value may be used as the decision criterion only if explicitly selected by policy. It is not silently assumed to equal utility.

## Opportunity cost

If enabled:

```text
AdjustedValue(a) = NetEV(a) - OpportunityCost(a)
```

Opportunity cost must be estimated using only information available at decision time.

## No-action baseline

Candidate actions are evaluated against `NO_ACTION` using the same information set. Positive standalone value is insufficient if another permitted action has greater utility.

## Canonical output

```text
EconomicAssessment {
    economic_assessment_id
    decision_time
    information_set_id
    prediction_id
    action_id
    instrument_id
    payoff_definition_id
    probability_definition_id
    gross_expected_value
    expected_cost
    expected_net_value
    risk_assessment_id
    utility_definition_id
    expected_utility
    no_action_baseline
    opportunity_cost_assessment_id?
    execution_assessment_id
    currency
    units
    quality_state
    eligibility_state
    reason_codes[]
    formula_registry_version
    configuration_version
    created_at
}
```

## Quality states

```text
VALID
DEGRADED
UNAVAILABLE
INVALID
CAUSALLY_UNAVAILABLE
```

Degraded economics are usable only where downstream policy explicitly permits them.

## Eligibility

```text
ELIGIBLE
INELIGIBLE
UNKNOWN
```

`ELIGIBLE` means economic constraints are satisfied; it does not mean an order has been authorized.

## Dependencies

```text
A132 probability
A128 instrument contract
A127 position/execution state
execution-cost contract
payoff/outcome contract
risk contract
accounting/unit/currency contract
versioned configuration
```

Every dependency requires source, owner, timestamp, version, and failure behavior.

## Failure conditions

Assessment fails closed or explicitly degrades for:

```text
missing/invalid probability
missing payoff
missing contract
missing cost semantics
unknown currency/unit
causal violation
unresolved version
NaN/Inf
undefined payoff
uncertain position
unavailable risk state
unavailable execution assumptions
```

Forbidden substitutions:

```text
missing cost -> zero
missing risk -> zero
missing payoff -> underlying return
missing probability -> default probability
unknown contract -> nearest contract
future realized cost -> ex-ante cost
```

## Mathematical invariants

```text
NetEV = GrossEV - ExpectedCost
```

for finite, dimensionally compatible quantities.

Probability inputs must satisfy A132's simplex contract.

Monetary values must share compatible currency and units. Currency conversion, when required, is itself a causal dependency.

## Versioning and lineage

An assessment records exact versions of:

```text
probability
payoff
cost model
risk model
utility model
instrument
configuration
```

Replay must never resolve a dependency from `latest`.

Ex-ante assessment is immutable and must not be overwritten by realized P&L or realized costs.

Canonical lineage:

```text
raw data
 -> canonical event
 -> snapshot
 -> feature
 -> probability
 -> payoff/economic model
 -> cost model
 -> risk assessment
 -> EconomicAssessment
 -> decision
 -> execution
 -> realized accounting
 -> outcome/label
```

## Learned/configurable quantities

Not frozen numerically:

```text
payoff distributions
cost distributions
fill probabilities
slippage distributions
risk-adjustment parameters
utility parameters
minimum edge
eligibility thresholds
```

These require historical population, label, maturity, train/validation/test boundaries, update frequency, promotion and rollback rules.

Configurable policy includes:

```text
candidate action set
cost components
utility policy
opportunity-cost policy
risk-adjustment policy
economic eligibility policy
```

No numerical value is frozen because it merely appears reasonable.

## Hostile review requirements

A133 must reject or explicitly degrade under:

```text
high probability + negative economics
positive EV + excessive risk
future realized execution costs
underlying return substituted for option payoff
existing position ignored
missing costs treated as zero
multiple candidate actions evaluated on different information sets
future calibration contamination
currency mismatch
partial-fill assumption
```

## Status

```text
ARCHITECTURE STATUS:
COMPLETE

FROZEN:
- probability/economics separation
- action-conditioned payoff
- ex-ante cost
- expected net value identity
- execution-conditioned economics
- partial-fill semantics
- position-aware economics
- risk/value separation
- explicit utility boundary
- no-action baseline
- opportunity-cost boundary
- causal dependencies
- immutable version lineage
- ex-ante vs realized accounting separation
- unit/currency integrity
- fail-closed missing economics

UNRESOLVED:
None at architectural-contract level.

UNKNOWN / TODO:
None that block the architecture. Concrete provider/model implementations remain owned by their respective contracts.

CONFIGURATION TO VALIDATE:
- candidate action set
- enabled cost components
- utility policy
- opportunity-cost policy
- economic eligibility policy

LEARNED / WALK-FORWARD VALIDATED:
- payoff distributions
- execution-cost distributions
- fill probabilities
- slippage distributions
- risk-adjustment parameters
- utility parameters
- minimum economic edge
- economic acceptance thresholds

BLOCKERS:
None for specification work.

NEXT ARTIFACT:
A134 — Canonical Decision, Eligibility, and Risk Authorization State Machine
```
