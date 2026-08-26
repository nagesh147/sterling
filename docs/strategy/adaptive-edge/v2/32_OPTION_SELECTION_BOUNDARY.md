# Adaptive Edge V2 — Option Selection Implementation Boundary

**Artifact:** §32 implementation boundary
**Status:** PARTIAL

## Source-defined relationship

The canonical source defines:

```text
O* = argmax ExpectedNetEV_i
```

subject to validated liquidity, slippage, risk and data-quality constraints.

## Implemented boundary

`OptionCandidate` represents a candidate whose expected net economic value and four source-defined selection constraints are supplied explicitly.

`select_option()` performs exactly two operations:

1. reject candidates that fail any validated selection constraint;
2. select the candidate with maximum `expected_net_ev` among the remaining candidates.

No probability model, cost model, risk model, option-contract semantics, or candidate-generation rule is invented by this module.

## Empty feasible set

If no candidate satisfies the supplied constraints, the result is `NO_CANDIDATE` rather than a fabricated selection.

## Remaining unresolved inputs

The source does not fully define how the upstream candidate set is constructed or how every constraint input is derived. In particular, provider/instrument contract semantics and upstream liquidity, slippage, risk, and data-quality estimators remain external dependencies.

Therefore §32 remains `PARTIAL`, not `EXACT`.
