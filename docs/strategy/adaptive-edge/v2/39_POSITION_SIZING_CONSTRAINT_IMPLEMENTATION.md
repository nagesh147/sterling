# A33 — Position Sizing / Quantity Constraint Implementation Boundary

**Status:** FRAMEWORK IMPLEMENTED / SIZING FORMULA BLOCKED

A33 now implements only the source-authorized constraint boundary. It does not calculate quantity from risk.

## Implemented

```text
risk measure resolved?
contract quantity constraints
minimum quantity
maximum quantity
quantity increment
capital available vs capital required
explicit zero-quantity status
explicit failure statuses
```

## Deliberately not implemented

```text
Q = floor(AuthorizedRisk / RiskPerUnit)
EffectiveRisk(quantity)
RiskPerUnit
EffectiveRisk
rounding policy
instrument-specific lot size
margin/payment semantics
portfolio allocation
```

A33's source contract explicitly prohibits these until A32 and the relevant contract artifacts are resolved.

## Validation boundary

`validate_candidate_quantity()` validates a caller-supplied candidate quantity. It does not derive that quantity.

Therefore the implementation cannot accidentally convert an unresolved risk measure into an executable quantity.

## Failure semantics

```text
risk unresolved       -> RISK_MEASURE_UNRESOLVED
contract violation    -> INVALID_QUANTITY
capital insufficient  -> CAPITAL_CONSTRAINT_FAILURE
quantity == 0         -> NO_TRADE
valid positive        -> SIZED
```

These are structural statuses only. They do not constitute strategy-specific sizing policy.

## Source boundary

The canonical A33 specification states that quantity must never be produced from an unresolved risk measure and that the common `floor(AuthorizedRisk / RiskPerUnit)` formula is not authorized while A32 remains unresolved.
