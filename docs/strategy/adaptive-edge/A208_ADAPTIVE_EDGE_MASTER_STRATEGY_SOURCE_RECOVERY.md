# A208 — Adaptive Edge Master Strategy Source Recovery and Canonicalization

**Status:** `[CANONICAL RECOVERY DECISION]`
**Date:** 2026-08-17
**Scope:** Adaptive Edge strategy-definition governance

## 1. Decision

The original Adaptive Edge master strategy specification has been recovered from the repository's historical source tree and is accepted as the authoritative original strategy artifact for formula recovery and canonicalization.

Recovered artifact:

```text
adaptive-edge/Adaptive Order-Flow Options Scalping and Intraday Strategy.md
```

Historical source commit:

```text
38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1
```

Source blob SHA:

```text
5ccfde7fcb039282a6753de9440c1484ffc2dfe8
```

Source title:

```text
Adaptive Order-Flow Options Scalping and Intraday Strategy
Master Mathematical Specification — Version 1.0
```

The recovered artifact defines the strategy objective, causal information rule, market-state architecture, probabilistic decision model, economic selection, risk management, position lifecycle, learning boundary, walk-forward validation, execution realism, and final decision function. It is therefore sufficient provenance for genuine formula recovery. 

## 2. Resolution-state correction

The earlier conclusion that no authoritative complete strategy definition had been recovered is now obsolete because the exact historical source artifact has been located at an immutable commit and inspected.

```text
RESOLVED-BLOCKED
      |
      | authoritative original source recovered
      v
SOURCE-RECOVERED
      |
      v
formula-by-formula canonicalization
      |
      v
RESOLVED only when definition + inputs + units + causal semantics
are complete and testable
```

`SOURCE-RECOVERED` is not equivalent to `IMPLEMENTED` and does not authorize filling gaps with plausible mathematics.

## 3. Recovered strategy semantics

The original Version 1.0 specification establishes:

### Objective

Probability-adjusted capital growth subject to bounded risk, positive out-of-sample expectancy, realistic execution, controlled drawdown, statistical robustness, and strict causal integrity.

Entry decisions:

```text
NO_TRADE
BUY_CE
BUY_PE
```

Position-management decisions:

```text
HOLD
UPDATE_STOP
EXIT
```

Previously accepted risk may not be increased merely because prediction becomes more optimistic.

### Causality

At event time `t`:

```text
Information_t = {E_0 ... E_t}
Variable_t = f(E_0 ... E_t)
```

Future information may be used only for historical outcome labels after the decision point has been frozen. Features may not depend on future outcomes.

### Economic selection

Expected execution cost is part of the economic calculation. Candidates must satisfy liquidity, slippage, risk, and data-quality constraints. Non-positive conservative expected value produces `NO_TRADE`.

### Risk and protection

For long options:

```text
RiskPerUnit = EntryPrice - InitialStop
GrossRisk = RiskPerUnit * Q
Q = floor(MaxRisk / EffectiveRiskPerUnit)
```

These equations do not by themselves establish equivalence between `GrossRisk`, `EffectiveRisk`, and `EffectiveRiskPerUnit`; those semantics remain subject to the source-level contract.

The stop is monotonic:

```text
Stop_(t+1) >= Stop_t
```

and accepted risk cannot expand after entry.

### Adaptive horizon

The source estimates a horizon distribution rather than defining trade identity by one fixed clock threshold. Management classifications include:

```text
MICRO_SCALP
SCALP
EXTENDED_SCALP
INTRADAY
```

These are management classifications, not separate strategies.

### Learning boundary

The canonical sequence is:

```text
TRAIN -> FREEZE -> VALIDATE -> TEST -> RECORD -> ADVANCE
```

A trade cannot alter the model that produced that trade.

## 4. Formula recovery contract

Source recovery does not automatically make F-101..F-114 complete. Each registry formula still requires:

```text
Formula ID
Version
Definition
Inputs
Input semantics
Units
Availability timestamp semantics
Boundary conditions
Numerical safeguards
Parameter-estimation methodology, when applicable
Owner module
Unit tests
Adversarial tests
Backtest/parity test
Provenance
```

No formula is promoted merely because the source contains a nearby concept.

## 5. F-101..F-114 next disposition

All strategy-specific formulas should now be re-opened against the recovered source rather than treated as permanently blocked by source absence.

| Formula | Required action |
|---|---|
| F-101 | Recover and canonicalize from V1.0; trial parameters remain non-production |
| F-102 | Recover and canonicalize from V1.0 |
| F-103 | Recover and canonicalize from V1.0 |
| F-104 | Recover; preserve semantic gaps explicitly |
| F-105 | Recover and canonicalize from V1.0 |
| F-106 | Recover and canonicalize from V1.0 |
| F-107 | Recover; keep effective-risk semantics explicit |
| F-108 | Recover and canonicalize from V1.0 |
| F-109 | Recover from V1.0; A207 remains display-only |
| F-110 | Recover and canonicalize from V1.0 |
| F-111 | Recover and canonicalize from V1.0 |
| F-112 | Recover; learned protection parameters remain unfrozen |
| F-113 | Recover and canonicalize from V1.0 |
| F-114 | Recover; multi-position semantics must be explicit |

## 6. A206 input decisions remain binding

For the F-101 recovery path, preserve the previously authorized input decisions:

```text
LiquidityImbalance = authorized
DeltaVelocity = removed; no proxy
```

No heuristic substitute for the removed `DeltaVelocity` input is permitted.

## 7. Prohibited shortcuts

```text
trial parameter -> production parameter
heuristic -> recovered formula
display ladder -> F-109 implementation
GrossRisk -> EffectiveRisk without source equivalence
RiskPerUnit -> EffectiveRiskPerUnit without source equivalence
historical optimum -> production threshold
missing data -> fabricated feature
provider limitation -> synthetic substitute
```

## 8. Execution impact

A208 does not unlock execution. The production boundary remains:

```text
SOURCE RECOVERED
      |
      v
formula canonicalization
      |
      v
IMPLEMENTED + validated formulas
      |
      v
ExecutionGate
```

## 9. Next substantive artifact

Proceed directly to **F-101 canonicalization** from the recovered Version 1.0 source.

The F-101 artifact must explicitly separate:

```text
source-defined mathematics
learned parameters
provider-available inputs
causal availability
trial-only implementation
production implementation
```

Only then can F-101 move toward `RESOLVED` and subsequently `IMPLEMENTED`.

## 10. Canonical conclusion

Adaptive Edge does not need an invented replacement strategy definition. An authoritative original Version 1.0 strategy definition has been recovered.

The correct path is:

```text
recover -> canonicalize -> resolve gaps explicitly -> implement -> calibrate -> validate -> promote
```

Not:

```text
invent -> implement -> backfill justification
```
