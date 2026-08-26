# Adaptive Edge V2 — Execution Cost Input Boundary

**Artifact:** A31
**Version:** 2.0.0
**Status:** PARAMETERIZED / PROVIDER-DEPENDENT
**Implementation:** `backend/app/engines/adaptive_edge/execution_cost.py`

## 1. Purpose

This artifact defines the provider-neutral input boundary for the execution-cost relationship in Master Specification §31.

The canonical decomposition is:

```text
Cost_i
 = SpreadCost_i
 + Slippage_i
 + Brokerage_i
 + ExchangeCharges_i
 + Taxes_i
 + LatencyCost_i
```

The specification also permits explicitly modeled market impact.

## 2. What is implemented

`ExecutionCostInput` represents the explicitly supplied economic components and computes their additive total.

The implementation does not estimate, learn, or default provider-specific values.

## 3. Market impact

Market impact is optional because the canonical specification permits it as an additional modeled component.

`None` means that market impact is not included in the supplied model. It is **not** a strategy assertion that market impact equals zero.

If supplied, market impact is included exactly once in the total.

## 4. Units

All components supplied to one `ExecutionCostInput` must already be expressed in the same economic unit and currency. Unit conversion and currency conversion are upstream responsibilities and are not invented here.

## 5. Provider-specific semantics remain unresolved

This boundary does not establish:

```text
broker tariff
exchange fee schedule
tax/levy rules
slippage distribution
latency-cost distribution
market-impact model
provider-specific applicability
historical fee validity
```

Those require authoritative provider/instrument/account semantics or an explicitly validated research model.

## 6. Missing-data rule

A missing provider/model definition must not be converted into an arbitrary numerical value merely to make the strategy executable.

The implementation therefore distinguishes:

```text
component absent from model
    !=
component measured as zero
```

## 7. Economic relationship

The downstream economic relationship remains:

```text
ExpectedNetValue
    = ExpectedGrossValue
      - ExpectedExecutionCost
```

The cost boundary supplies the second term; it does not determine economic eligibility or risk authorization.

## 8. Status

The additive operator is implemented. Provider-specific distributions, applicability rules, and estimation procedures remain parameterized and unresolved.

No brokerage, tax, slippage, latency, or impact value is promoted to strategy truth by this artifact.
