# Execution Cost Input Boundary

**Status:** INPUT BOUNDARY IMPLEMENTED / COST MODEL UNRESOLVED
**Depends on:** A35

## Purpose

Represent the market observations that may be supplied to an execution-cost model without inventing the model itself.

A35 requires reference price, expected execution price, submitted order price, and fill price to remain distinct. Each price observation carries instrument identity, price type, value, observation timestamp, availability timestamp, source, source version, and freshness/validity state.

## Pre-trade rule

Only information available at the decision timestamp may enter a contemporaneous execution assessment.

```text
availability_timestamp <= decision_time
```

Future observations and fill observations are rejected from the pre-trade boundary.

## Provider neutrality

The boundary does not assume:

- bid-side execution for buys
- ask-side execution for sells
- midpoint execution
- zero slippage
- fixed latency
- fill probability
- spread threshold
- liquidity threshold
- broker execution semantics

Those remain unresolved under A35.

## TrueData boundary

TrueData may populate market observations when its documented market-data fields and semantics satisfy the canonical observation contract. TrueData is a market-data provider here; this artifact does not infer broker execution semantics from TrueData quotes.

## Cost-model boundary

```text
Price / market observations
        |
        v
ExecutionCostInputs
        |
        v
[UNRESOLVED COST MODEL]
        |
        v
ExpectedExecutionCost
```

No expected-cost value is produced by this boundary alone.

## Failure behavior

Invalid provenance, future information, instrument mismatch, invalid timestamps, or use of a fill as a pre-trade observation must fail closed.

## Resolution gate

The cost model becomes implementable only when its source defines the cost components, units, estimation method, temporal eligibility, and provider/execution semantics required by A35.
