# A224 — Source Recovery State Correction

**Status:** `[CANONICAL CORRECTION]`
**Date:** 2026-08-18

## Decision

The historical V1.0 Adaptive Edge master specification has been recovered at immutable source commit `38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1`. A208 records that recovery and explicitly requires formula-by-formula canonicalization rather than invention.

Therefore the earlier repository wording that F-101..F-114 had **no authoritative source** is obsolete.

The correct state is:

```text
SOURCE-RECOVERED
      |
      v
CANONICALIZATION IN PROGRESS
      |
      +--> complete contract + tests + calibration
      |          -> RESOLVED
      |
      +--> unresolved semantics
                 -> RESOLVED-BLOCKED
```

## Important distinction

`SOURCE-RECOVERED` does not mean `RESOLVED` and does not mean `IMPLEMENTED`.

The source itself establishes, among other things:

- causal information through event `t`;
- liquidity imbalance and delta state;
- probabilistic regime/horizon modeling;
- candidate option economics;
- `O* = argmax ExpectedNetEV_i` subject to liquidity, slippage, risk and data quality;
- conservative EV via a lower confidence bound;
- `Q = floor(MaxRisk / EffectiveRiskPerUnit)`;
- immutable TradePlan;
- continuation value;
- monotonic protection;
- no-risk-expansion after entry;
- explicit state-machine transitions;
- walk-forward learning boundaries.

The source does **not** by itself supply every implementation-level input semantic or calibrated parameter required for promotion.

## Formula disposition

| Formula | State |
|---|---|
| F-101 | SOURCE-RECOVERED / canonicalization + calibration required |
| F-102 | SOURCE-RECOVERED / canonicalization + calibration required |
| F-103 | SOURCE-RECOVERED / canonicalization required |
| F-104 | SOURCE-RECOVERED / canonicalization + calibration required |
| F-105 | SOURCE-RECOVERED / canonicalization + calibration required |
| F-106 | SOURCE-RECOVERED / canonicalization + calibration required |
| F-107 | SOURCE-RECOVERED / effective-risk semantics require explicit reconciliation |
| F-108 | SOURCE-RECOVERED / sizing constraints implemented; promotion pending |
| F-109 | SOURCE-RECOVERED / selection is economic, not an unconditional ATM rule |
| F-110 | SOURCE-RECOVERED / entry gate semantics require canonical mapping |
| F-111 | SOURCE-RECOVERED / exit state machine requires canonical mapping |
| F-112 | SOURCE-RECOVERED / learned protection parameters require validation |
| F-113 | SOURCE-RECOVERED / re-entry semantics require canonical mapping |
| F-114 | SOURCE-RECOVERED / exact portfolio aggregation still unresolved |

## F-109 correction

The authoritative source explicitly selects the eligible option maximizing validated expected net EV. Therefore the system must not treat ATM as the canonical selection rule. The existing moneyness ladder remains a candidate-generation/display mechanism until its economic selection is proven equivalent to the source rule.

## F-114 correction

The source defines the canonical decision function as a function of:

```text
MarketState_t
ProbabilityState_t
CapitalState_t
ExecutionState_t
PositionState_t
```

and defines the single-position state machine. It does not provide a uniquely specified multi-position risk aggregation equation. F-114 therefore remains blocked specifically on portfolio aggregation mathematics, not on source absence.

## Governance consequence

All older documents claiming that the original strategy artifact has not been recovered must be interpreted as superseded by A208 and this correction. The machine-readable registry remains `LOCKED` until promotion conditions are met.

Production execution remains fail-closed.
