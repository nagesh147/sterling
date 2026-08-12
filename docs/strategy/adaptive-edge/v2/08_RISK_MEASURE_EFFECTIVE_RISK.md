# Adaptive Edge V2 — Risk Measure / EffectiveRisk Definition

**Version:** 2.0.0-draft
**Artifact:** A32
**Status:** RESOLVED-BLOCKED
**Depends on:** A31, A29, execution/contract semantics
**Implementation authorization:** NONE

## 1. Purpose

A32 attempts to resolve the semantic meaning of the risk-measure variables required between risk authorization and position sizing:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
```

The purpose is not to find a mathematically plausible formula. The purpose is to establish a complete, causal, dimensionally valid definition whose required inputs and semantics are known.

## 2. Existing source evidence

The existing Adaptive Edge risk artifact explicitly states that risk is authorization rather than prediction, that `RiskAuthorization` is immutable for its opportunity, and that the exact risk-per-unit and sizing equations remain locked as F-107/F-108. It also explicitly prohibits substituting generic Kite sizing or another strategy's sizing formula.

Therefore the existing source does not authorize a V2 formula for these variables.

## 3. Architectural distinction

The following layers remain distinct:

```text
AuthorizedRisk
      |
      v
RiskMeasure
      |
      v
PositionSizing
      |
      v
Quantity
```

`AuthorizedRisk` is a permission/budget.

`RiskMeasure` is the measurement of exposure consumed by a candidate position.

`Quantity` is the resulting tradable amount after risk and contract constraints.

No equality among these concepts is assumed.

## 4. Candidate semantic roles

These names are retained as unresolved roles only:

### GrossRisk

Potentially a pre-adjustment or unmodified risk quantity for a candidate position.

**Status:** UNKNOWN.

No exact calculation is authorized.

### RiskPerUnit

Potentially the risk attributable to one tradable unit.

**Status:** UNKNOWN.

The unit itself is not yet established.

### EffectiveRiskPerUnit

Potentially a risk-per-unit value after explicitly defined adjustments.

**Status:** UNKNOWN.

No adjustment set is authorized.

### EffectiveRisk_i

Potentially the effective risk associated with candidate position `i`.

**Status:** UNKNOWN.

The meaning of `i`, aggregation boundary, and calculation are not defined.

## 5. Why common formulas are insufficient

The following are mathematically valid candidate constructions in some trading systems:

```text
RiskPerUnit = EntryPrice - StopPrice

EffectiveRisk_i = EffectiveRiskPerUnit_i * Quantity_i

EffectiveRisk_i = Premium_i * Quantity_i
```

But none is a V2 definition because each requires additional semantic commitments.

For example, `EntryPrice - StopPrice` requires at minimum:

```text
entry-price semantics
stop semantics
option/underlying identity
price unit
quantity unit
execution boundary
stop validity
```

None may be assumed merely from the formula.

## 6. Minimum completeness requirements

A risk-measure definition can become `RESOLVED` only when all applicable items below are defined:

```text
risk variable identity
mathematical formula
units
instrument scope
position direction
quantity definition
entry reference
exit/protection reference if used
execution-cost treatment if used
slippage treatment if used
contract multiplier if used
time/timestamp semantics
availability semantics
state dependencies
missing-data behavior
stale-data behavior
boundary conditions
negative/zero-value behavior
aggregation semantics
version
provenance
validation method
```

## 7. Causal requirement

A pre-trade risk measure at decision time `t_d` may use only information available by `t_d`, plus parameters previously promoted under the V2 learning protocol.

Forbidden inputs include future:

```text
fill
exit
stop hit
realized loss
realized P&L
future label
```

unless the variable is explicitly defined as a post-trade accounting outcome rather than a pre-trade risk measure.

## 8. Pre-trade versus realized risk

The specification must distinguish:

```text
Expected / authorized pre-trade risk
```

from:

```text
Realized loss / realized P&L
```

A realized loss is an observation after the decision. It cannot be substituted for the risk measure used to determine the original position size.

## 9. Stop-distance candidate attack

Candidate:

```text
RiskPerUnit = EntryPrice - StopPrice
```

Attack:

1. What exactly is `EntryPrice`?
2. What exactly is `StopPrice`?
3. Is the stop guaranteed executable?
4. What happens across gaps?
5. What happens when bid/ask changes before the stop?
6. Does the formula include transaction costs?
7. What is the option contract multiplier?
8. Is the quantity a unit, share, lot, or contract?
9. Is the stop fixed, trailing, predictive, or dynamic?
10. Is the stop known at the sizing decision?

Because these semantics are unresolved, the candidate formula is rejected as a V2 canonical definition.

## 10. Premium candidate attack

Candidate:

```text
RiskPerUnit = PremiumPaid
```

Attack:

1. Is premium the executable ask or another price?
2. Is the maximum-loss assumption contractual or strategy-defined?
3. Are fees included?
4. Is slippage included?
5. Does the position always remain until expiry?
6. Can protection exit earlier?
7. Is the instrument always a long option?
8. Is the premium measured per contract or per unit?

Without these semantics, premium cannot be declared the V2 risk measure.

## 11. GrossRisk candidate attack

Candidate:

```text
GrossRisk = RiskPerUnit * Quantity
```

This is dimensionally plausible but still insufficient because `RiskPerUnit` and `Quantity` are unresolved.

Therefore this equation is not promoted to canonical status.

## 12. EffectiveRisk candidate attack

Candidate:

```text
EffectiveRisk_i = GrossRisk_i + Adjustments_i
```

This is rejected as incomplete because `Adjustments_i` has no defined membership, units, causal availability, or aggregation semantics.

No adjustment is introduced by A32.

## 13. Execution dependence

If risk uses executable entry price, the execution contract must define the reference price and timestamp.

The existing platform contract distinguishes executable BUY and SELL references. A32 does not override those semantics.

However, execution semantics alone do not establish the risk formula.

## 14. Option-contract dependence

If V2 trades options, risk measurement may depend on:

```text
underlying
option type
strike
expiry
contract multiplier
entry price
protection rule
exit price
```

The contract-selection and execution artifacts must define these before an option-specific risk formula can be resolved.

No NIFTY strike, expiry, lot size, or liquidity threshold is invented here.

## 15. Quantity dependence

A circular definition is forbidden:

```text
Quantity -> EffectiveRisk -> Quantity
```

unless the system defines a mathematically valid fixed-point procedure and all inputs are independent at the decision boundary.

V2 does not introduce such a procedure at A32.

## 16. Risk authorization comparison

Only after both sides are fully defined can the system evaluate a constraint such as:

```text
EffectiveRisk_i <= AuthorizedRisk_i
```

This comparison is architectural only.

It is not currently executable because the units and semantics of both sides are incomplete.

## 17. Unit consistency

The following is invalid:

```text
AuthorizedRisk = currency
EffectiveRisk = points
```

unless a defined conversion exists.

Likewise:

```text
risk per share
```

cannot be directly compared to:

```text
risk per lot
```

without a contract multiplier/quantity definition.

## 18. Zero and negative values

The final risk measure must define behavior for:

```text
zero
negative
NaN
infinite
missing
stale
```

A32 does not choose those semantics prematurely.

A negative risk value cannot silently be interpreted as zero.

## 19. Data failure

If a required risk input is unavailable, the sizing stage must not silently substitute:

```text
zero
last known value
current value
estimated value
```

unless a separately versioned policy explicitly authorizes that fallback.

## 20. Temporal validity

Every risk input must have:

```text
observation_time
availability_time
validity interval
```

where relevant.

The risk calculation uses the value known at the decision boundary, not a later corrected historical value that was unavailable at that time.

## 21. Corporate / contract lifecycle

Historical risk calculation must use contract terms valid at the historical decision time.

Using current contract multipliers or current contract specifications for historical positions is prohibited where those values differ through time.

## 22. Portfolio interaction

A32 defines candidate-position risk only.

It does not define portfolio netting, correlation offsets, shared risk budgets, or multi-position allocation.

Those belong to the later portfolio-risk artifact.

## 23. Learning

No risk-measure parameter is learned by A32.

If later validation determines that a risk parameter must be learned, its specification must define:

```text
historical population
label/outcome
observation horizon
maturity
training boundary
validation boundary
test boundary
update frequency
promotion rule
```

## 24. Adversarial scenario — profitable position

A position that later produces a large profit must not retrospectively receive a smaller historical risk measure merely because the outcome was favorable.

Risk is determined causally at the decision boundary.

## 25. Adversarial scenario — stop gap

If a stop is crossed through a gap and the actual execution differs from the stop level, the system must distinguish:

```text
planned protection reference
actual execution
realized loss
```

A32 does not collapse these variables.

## 26. Adversarial scenario — stale quote

If the quote used for risk measurement is stale, the risk measure cannot be treated as contemporaneous without an explicit freshness policy.

## 27. Adversarial scenario — missing option chain

If contract-specific inputs required for risk are unavailable, the correct result is an explicit blocked/insufficient-information state, not an invented strike, expiry, or price.

## 28. Adversarial scenario — multiple candidates

For candidates `i = 1...n`, the system must not select the candidate with the smallest apparent risk after observing future outcomes.

Candidate selection remains upstream and causal.

## 29. Adversarial scenario — risk budget exceeded

If a candidate's resolved effective risk exceeds the authorized risk budget, the position must not be sized above authorization.

The exact rounding and rejection rule belongs to the sizing artifact.

## 30. Resolution decision

After attacking the available source definitions, A32 cannot resolve the exact V2 semantics of:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
```

No authoritative V2 artifact currently supplies the missing definitions.

Therefore the correct state is:

```text
RESOLVED-BLOCKED
```

This is not an implementation defect. It is an intentional specification gate.

## 31. What is resolved

```text
Risk authorization and risk measurement are distinct.
Pre-trade risk must be causal.
Realized outcomes cannot define original risk retrospectively.
Risk-measure units must be explicit.
Contract/execution semantics must precede instrument-specific risk formulas.
Missing risk inputs fail closed.
No generic strategy sizing formula may be imported.
```

## 32. What remains unresolved

```text
EffectiveRisk_i definition
EffectiveRiskPerUnit definition
RiskPerUnit definition
GrossRisk definition
risk unit
entry semantics within risk
protection/stop semantics within risk
cost/slippage treatment
contract multiplier semantics
aggregation boundary
quantity dependency
```

## 33. Blocker

The blocker is not mathematical complexity.

The blocker is missing semantic definition.

A mathematically valid formula without complete input semantics would violate the V2 source-definition rule.

## ARCHITECTURE STATUS

```text
FROZEN
------
Risk-measure layer boundary
Risk authorization vs risk measurement
Pre-trade causal requirement
Realized-risk separation
Dimensional-consistency requirement
Fail-closed requirement
No cross-strategy formula substitution

UNRESOLVED
----------
EffectiveRisk_i
EffectiveRiskPerUnit
RiskPerUnit
GrossRisk
all dependent numerical/contract semantics

BLOCKERS
--------
Authoritative V2 risk-measure definition is absent.

NEXT ARTIFACT
-------------
A33 — Position Sizing and Quantity Constraint Definition
```

A33 may define the architecture and hard quantity constraints, but it must not implement a sizing equation until A32 is resolved or an explicitly versioned V2 risk-measure definition is created.