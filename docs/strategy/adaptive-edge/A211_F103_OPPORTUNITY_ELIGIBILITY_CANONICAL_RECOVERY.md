# A211 — F-103 Opportunity Eligibility Canonical Recovery

**Status:** `[SOURCE-RECOVERED / IMPLEMENTATION PREPARATION]`
**Date:** 2026-08-17
**Formula:** F-103 — Opportunity eligibility
**Source:** Adaptive Order-Flow Options Scalping and Intraday Strategy — Master Mathematical Specification v1.0

## 1. Canonical semantics

The recovered V1 source defines entry eligibility as a conjunction of mandatory gates. For either directional option candidate:

```text
BUY_CE = DataOK ∧ DirectionalEdgeOK ∧ EV_CE > 0
         ∧ ConservativeEV_CE > 0
         ∧ LiquidityOK ∧ SlippageOK ∧ RiskOK

BUY_PE = DataOK ∧ DirectionalEdgeOK ∧ EV_PE > 0
         ∧ ConservativeEV_PE > 0
         ∧ LiquidityOK ∧ SlippageOK ∧ RiskOK
```

Otherwise:

```text
NO_TRADE
```

This is a gate composition, not a new predictive score.

## 2. Critical governance rule

F-103 must not invent universal numeric thresholds for:

```text
DirectionalEdgeOK
LiquidityOK
SlippageOK
RiskOK
```

Those conditions are outputs of their respective canonical contracts and validated parameters. F-103 only composes them.

The source explicitly rejects universal fixed thresholds unless they survive walk-forward validation and demonstrate robustness.

## 3. Economic requirement

Both raw expected value and conservative expected value must be positive. The conservative value is based on the lower confidence bound of expected value:

```text
EV_conservative = LowerConfidenceBound(EV)

EV_conservative <= 0 -> NO_TRADE
```

Execution cost must already be represented in the expected-value calculation.

## 4. Directional requirement

The underlying generates the primary directional state. The option is principally the execution instrument. Therefore F-103 accepts a validated directional-edge decision; it must not permit option-specific data to override the underlying directional model without separately validated evidence.

## 5. Fail-closed behavior

Missing or invalid mandatory gates produce:

```text
eligible = False
reason = explicit failing gate
```

No missing condition may be coerced to `True`, and F-103 must not manufacture a probability, expected value, liquidity state, slippage estimate, or risk authorization.

## 6. Determinism

Given identical canonical gate inputs, F-103 must produce identical:

```text
decision
reason
formula_id
formula_version
```

No market-data lookup, current-time lookup, randomness, or mutable global state is permitted.

## 7. Execution boundary

F-103 eligibility does not authorize execution. It only determines opportunity eligibility. Risk authorization and the final execution gate remain separate boundaries.

## 8. Resolution

```text
Source definition:        RECOVERED
Mathematical composition: RECOVERED
Numeric thresholds:       NOT FROZEN
Implementation:           RESEARCH / CONTRACT
Production authorization: NOT AUTHORIZED
```

The implementation should therefore encode the source-defined conjunction without inventing additional thresholds.
