# A214 — F-108 Position Sizing Canonical Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTED / PARAMETER-GOVERNED]`
**Formula:** F-108
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Canonical sizing equation

F-108 consumes the F-107 effective risk-per-unit and the authorized risk budget.

```text
Q_unconstrained = floor(AuthorizedRisk / EffectiveRiskPerUnit)
```

Then apply independent hard constraints:

```text
Q_capital = floor(MaxCapitalAllocation / EntryPrice)
Q_constrained = min(
    Q_unconstrained,
    Q_capital,
    MaxPositionQty
)
```

Finally enforce instrument lot granularity:

```text
Q_final = floor(Q_constrained / LotSize) * LotSize
```

The current implementation follows this structure. fileciteturn82file0L2-L2

## 2. Authorized-risk boundary

F-108 is not a risk-authorizer. It consumes an already-authorized `RiskAuthorization` state.

Accepted states:

```text
AUTHORIZED
REDUCED
```

Anything else fails closed.

The authorized risk budget is an upper bound, never a target that must be fully consumed.

## 3. Effective-risk invariant

After lot rounding:

```text
EffectiveAuthorizedRisk
    = EffectiveRiskPerUnit * Q_final
```

must satisfy:

```text
EffectiveAuthorizedRisk <= AuthorizedRisk
```

The implementation explicitly checks this invariant after calculating the final lot quantity. fileciteturn83file0L2-L2

## 4. Capital constraint

Capital allocation is independently constraining:

```text
Q_final * EntryPrice <= MaxCapitalAllocation
```

This prevents a low-risk-per-unit trade from consuming disproportionate capital simply because the stop distance is small.

## 5. Lot constraint

`LotSize` is a hard instrument constraint.

```text
Q_final mod LotSize = 0
```

Partial lots are invalid.

If the constrained quantity is smaller than one complete lot:

```text
Q_final = 0
```

and the downstream execution path must not manufacture a partial quantity.

## 6. Zero-budget behavior

When:

```text
AuthorizedRisk <= 0
```

F-108 returns zero quantity rather than inventing authorization.

## 7. Parameter governance

The following remain versioned parameters rather than hard-coded strategy constants:

```text
MaxPositionQty
MaxCapitalAllocation
LotSize
AuthorizedRisk
```

Every operational parameter requires provenance, version, estimation method, and validation status.

Unresolved parameters fail closed.

## 8. Risk monotonicity

F-108 cannot increase the risk authorized by the upstream risk layer.

The following implication is mandatory:

```text
AuthorizedRisk decreases
        =>
Q_final cannot increase
```

Likewise, adding execution friction to F-107 cannot increase F-108 quantity because:

```text
EffectiveRiskPerUnit increases
        =>
Q_unconstrained decreases or remains equal
```

## 9. No hidden sizing logic

F-108 must not incorporate:

```text
prediction confidence -> extra quantity
horizon -> extra quantity
profit target -> extra quantity
recent wins -> extra quantity
unrealized profit -> extra quantity
```

Sizing is constrained by the explicit authorized-risk and capital contract.

## 10. Resolution

```text
Source mathematics:          RECOVERED
Implementation:              EXISTS
Parameter governance:        ENFORCED
Lot constraint:              ENFORCED
Capital constraint:          ENFORCED
Effective-risk cap:          ENFORCED
Production parameter values: NOT FROZEN
```

F-108 is therefore suitable for promotion testing once its adversarial tests pass against the canonical risk authorization contract.

## 11. Next step

Proceed to F-109. F-109 must resolve the option strike/moneyness selection contract separately from the F-106 candidate economics layer; the selector must not silently substitute ATM merely because it is the nearest listed strike.
