# Adaptive Edge — Execution Semantics

## Decision chain

```text
candidate
 -> edge assessment
 -> economic assessment
 -> mode policy
 -> risk authorization
 -> sizing
 -> execution intent
 -> broker order
 -> authoritative fill
 -> position
```

## Non-equivalence rules

```text
signal != authorization
authorization != order
order != fill
fill != position
```

## Price references

```text
BUY  -> executable ASK
SELL -> executable BID
```

Midpoint/LTP may be an observation but is not a default executable fill.

## Fill truth

- Partial fill remains partial.
- Rejection does not create a position.
- Duplicate fill events must be idempotent.
- A failed exit does not erase the position or the exit obligation.
- Actual broker fill data is authoritative for accounting.

## Cost model

Execution-cost inputs belong to economic evaluation/execution modelling, not the prediction equation.

Costs may include configured:

- bid/ask spread
- slippage
- fees
- latency effects
- partial-fill effects

The exact cost model must be versioned and traceable.
