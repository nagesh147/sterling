# A213 — F-107 Effective Risk-Per-Unit Canonical Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTED / PARAMETER-GOVERNED]`
**Formula:** F-107
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0
**Source commit:** `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`

## 1. Canonical formula

For a long option:

```text
RiskPerUnit = EntryPrice - InitialStop
```

Execution friction is explicitly part of effective risk:

```text
ExecutionCostPerUnit =
    SpreadCost
  + ExpectedSlippage
  + BrokeragePerUnit
  + ExchangeChargesPerUnit
  + TaxesPerUnit
  + LatencyCostPerUnit
```

Therefore:

```text
EffectiveRiskPerUnit = RiskPerUnit + ExecutionCostPerUnit
```

The source explicitly requires expected execution effects to be incorporated into effective risk. fileciteturn80file0L2-L2

## 2. Preconditions

F-107 requires:

```text
EntryPrice > 0
InitialStop > 0
InitialStop < EntryPrice
all execution-cost components >= 0
all parameter metadata validated
```

A non-positive nominal risk is invalid.

## 3. Parameter governance

Cost components are not arbitrary constants. Each operational/learned parameter requires:

```text
name
value
units
version
provenance
estimation method
validation status
instrument scope
session scope
regime scope
```

Unvalidated or unresolved parameters fail closed.

## 4. Safety invariants

```text
EffectiveRiskPerUnit >= RiskPerUnit > 0
```

The effective risk cannot be smaller than nominal stop risk because execution friction cannot create additional capital protection.

F-107 does not increase risk merely because a prediction becomes more optimistic.

## 5. Missingness

Missing execution-cost components are not silently treated as zero. The current governed implementation requires validated metadata for every component.

If cost estimation is unavailable, the calculation must remain blocked rather than understating risk.

## 6. Implementation state

The existing `risk_sizing.py` implementation already expresses the canonical formula and enforces parameter governance and the effective-risk invariant. fileciteturn81file0L2-L6

Its calculation explicitly sums spread, slippage, brokerage, exchange charges, taxes, and latency into effective risk. fileciteturn82file0L2-L2

Therefore this step is **canonicalization and adversarial hardening**, not a second risk-sizing implementation.

## 7. Next step

F-108 must consume only the F-107 `EffectiveRiskPerUnit` assessment and apply authorized-risk, capital, maximum-position, and lot-size constraints. The final quantity must remain a valid lot multiple and effective authorized risk must not exceed the authorized budget.
