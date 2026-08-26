# Adaptive Edge V2 — Position Sizing and Quantity Constraints

**Artifact:** A33  
**Version:** 2.0.0-draft  
**Status:** RESOLVED-BLOCKED  
**Implementation:** NONE

## Purpose

Define the position-sizing boundary without inventing the unresolved `RiskPerUnit` or `EffectiveRisk` equations.

## Canonical dependency

```text
Eligibility
    -> RiskAuthorization
    -> ResolvedRiskMeasure + ContractConstraints + CapitalConstraints
    -> QuantityCandidate
    -> QuantityValidation
    -> ExecutableQuantity
```

A quantity must never be produced from an unresolved risk measure.

## Canonical contract

```text
PositionSizing(
    RiskAuthorization,
    ResolvedRiskMeasure,
    ContractConstraints,
    CapitalConstraints,
    SizingPolicyVersion
) -> PositionSizingResult
```

This is an interface contract, not a numerical sizing formula.

## Result

```text
PositionSizingResult {
    sizing_id
    opportunity_id
    authorization_id
    risk_measure_reference
    instrument_reference
    quantity
    quantity_unit
    constraint_results
    status
    reason_codes
    strategy_version
    sizing_policy_version
    decision_time
    provenance
}
```

## States

```text
SIZED
NO_TRADE
INSUFFICIENT_INFORMATION
RISK_MEASURE_UNRESOLVED
CONTRACT_CONSTRAINT_FAILURE
CAPITAL_CONSTRAINT_FAILURE
INVALID_QUANTITY
EXPIRED_AUTHORIZATION
```

Errors must not be silently converted to `NO_TRADE` without preserving the reason.

## Risk constraint

Once A32 is resolved, sizing may enforce:

```text
EffectiveRisk(quantity) <= AuthorizedRisk
```

The function is intentionally undefined here.

The common formula:

```text
Q = floor(AuthorizedRisk / RiskPerUnit)
```

is **not** authorized because A32 has not defined `RiskPerUnit`, its unit, contract multiplier semantics, entry/protection semantics, or quantity unit.

## Quantity constraints

The eventual quantity must satisfy all applicable constraints simultaneously:

```text
risk
capital
quantity increment
minimum quantity
maximum quantity
instrument eligibility
execution feasibility
authorization validity
```

Quantity is a non-negative magnitude. Direction belongs to the order/position contract and is not inferred from a risk formula.

## Contract/lot semantics

If the instrument requires a quantity increment:

```text
quantity % quantity_increment = 0
```

may become a constraint, but the actual increment must come from the time-valid instrument contract. Current lot size must not be applied retrospectively when historical terms differ.

No NIFTY strike, expiry, lot size, or liquidity threshold is invented here.

## Capital

Capital is independent of risk authorization:

```text
CapitalRequired(quantity) <= CapitalAvailable
```

is architectural only. Exact capital/margin/payment semantics require the instrument and execution contracts.

## Rounding

`floor`, `ceil`, and `nearest` are not selected yet. Rounding is strategy semantics because it can change risk. Any eventual rule must preserve mandatory risk and contract constraints.

## Zero quantity

`quantity = 0` is allowed only with an explicit reason/status. Zero must not hide an unresolved risk formula, failed contract lookup, invalid data, or expired authorization.

## Re-sizing

A re-sizing decision is a new decision with its own authorization/policy reference. Historical sizing results are immutable.

## Multiple positions

A33 defines single-candidate sizing. Portfolio allocation, shared budgets, correlation offsets, and multi-position interaction are later artifacts.

## Causal boundary

Sizing may use only information available at its decision timestamp. Future fills, exits, realized P&L, future labels, and future contract states are forbidden inputs.

## Failure behavior

Missing, stale, invalid, or semantically unresolved required inputs produce:

```text
no executable quantity
+ explicit status
+ reason code
+ provenance
```

No fallback quantity is invented.

## Determinism

Identical authorization, risk measure, contract constraints, capital state, and policy version must reproduce the same sizing result.

## Adversarial cases

### Risk measure missing

```text
AuthorizedRisk = valid
RiskPerUnit = UNKNOWN
=> RISK_MEASURE_UNRESOLVED
```

Never invent `Q = 1` or silently treat the failure as a normal zero-trade result.

### Minimum lot exceeds risk

If the minimum tradable quantity exceeds resolved authorized risk:

```text
NO_TRADE
```

not an over-risk position.

### Capital sufficient, risk insufficient

```text
CapitalAvailable >= requirement
EffectiveRisk > AuthorizedRisk
=> NO_TRADE / risk constraint failure
```

### Risk sufficient, capital insufficient

```text
EffectiveRisk <= AuthorizedRisk
CapitalAvailable < requirement
=> NO_TRADE / capital constraint failure
```

### Stale contract metadata

Missing/stale historical quantity rules produce `CONTRACT_CONSTRAINT_FAILURE`, not substitution of today's contract metadata.

## Parameter classes

**Frozen:** sizing boundary, risk/quantity separation, capital/risk separation, constraint intersection, explicit failures, historical contract validity, deterministic replay.

**Configuration:** quantity increment, minimum/maximum quantity, capital policy — only when source-defined.

**Learned:** none introduced here.

**External UNKNOWN:** TrueData mappings, undocumented broker constraints, historical instrument metadata until sourced.

## Implementation gate

A33 cannot become executable until:

```text
A32 Risk Measure = RESOLVED
Instrument/Contract semantics = RESOLVED
Capital semantics = RESOLVED where applicable
Quantity constraints = RESOLVED
```

## ARCHITECTURE STATUS

**FROZEN:** sizing boundary; risk/quantity separation; capital/risk separation; constraint intersection; explicit failures; historical contract validity; deterministic replay; no invented fallback.

**UNRESOLVED:** risk-to-quantity formula; `RiskPerUnit`; `EffectiveRisk`; quantity-increment source; capital semantics; rounding; instrument-specific quantity constraints.

**BLOCKERS:** A32 remains `RESOLVED-BLOCKED`; instrument/contract semantics remain partially unresolved.

**NEXT ARTIFACT:** A34 — Instrument / Contract Selection Definition.