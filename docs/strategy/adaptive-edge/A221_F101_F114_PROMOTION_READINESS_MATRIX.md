# A221 — F-101..F-114 Promotion Readiness Matrix

**Status:** `[INTEGRATION BASELINE / PRODUCTION LOCKED]`
**Date:** 2026-08-18

## 1. Purpose

This matrix reconciles the recovered strategy formulas with implementation, tests, provenance, calibration, and production authorization.

`SOURCE-RECOVERED` does not mean `IMPLEMENTED`.

`IMPLEMENTED` does not mean `PRODUCTION-AUTHORIZED` until the promotion contract is satisfied.

## 2. Current matrix

| Formula | Canonical role | Existing/research boundary | Adversarial tests | Calibration | Production |
|---|---|---:|---:|---:|---:|
| F-101 | Feature normalization | YES | YES | REQUIRED | LOCKED |
| F-102 | Probability / prediction | YES | YES | REQUIRED | LOCKED |
| F-103 | Opportunity eligibility | YES | YES | REQUIRED | LOCKED |
| F-104 | Adaptive horizon distribution | YES | YES | REQUIRED | LOCKED |
| F-105 | Target/stop + conservative EV | YES | YES | REQUIRED | LOCKED |
| F-106 | Option candidate economics | YES | YES | REQUIRED | LOCKED |
| F-107 | Effective risk per unit | YES | YES | REQUIRED | LOCKED |
| F-108 | Position sizing | YES | YES | REQUIRED | LOCKED |
| F-109 | Listed contract/moneyness | YES | YES | REQUIRED | LOCKED |
| F-110 | Canonical order intent | YES | EXISTING E2E | REQUIRED | LOCKED |
| F-111 | Canonical execution event | YES | YES | REQUIRED | LOCKED |
| F-112 | Dynamic protection | YES | YES | REQUIRED | LOCKED |
| F-113 | Lifecycle termination | YES | YES | REQUIRED | LOCKED |
| F-114 | Portfolio interaction | SEMANTICS IDENTIFIED | REQUIRED | REQUIRED | LOCKED |

## 3. Promotion gate

A formula may move to `IMPLEMENTED` only when all applicable conditions hold:

```text
authoritative source
       AND
complete mathematical contract
       AND
causal inputs identified
       AND
units identified
       AND
missingness defined
       AND
numerical safeguards defined
       AND
implementation parity
       AND
unit/adversarial tests
       AND
walk-forward calibration
       AND
out-of-sample validation
       AND
provenance recorded
```

## 4. Cross-formula dependency order

Promotion must follow dependency order:

```text
F-101
  -> F-102
  -> F-103
  -> F-104
  -> F-105
  -> F-106
  -> F-107
  -> F-108
  -> F-109
  -> F-110
  -> F-111
  -> F-112
  -> F-113
  -> F-114
```

A downstream formula must not become executable by bypassing an unresolved upstream dependency.

## 5. Research calibration boundary

The repository now contains an explicit **fail-closed calibration-entry gate** at `backend/app/engines/adaptive_edge/calibration_gate.py`.

The gate does not calibrate or promote anything. It only admits a dataset to the A197 calibration phase when the supplied evidence satisfies the minimum coverage, feature completeness, temporal-quality, and cryptographic-provenance requirements.

```text
TrueData corpus
      |
      v
Canonical sequence
      |
      v
Coverage + quality report
      |
      v
F-101 calibration entry gate
      |
      +---- BLOCKED -> stop
      |
      v
TRAIN
  -> fit parameters
  -> FREEZE
  -> VALIDATE
  -> TEST
  -> record predictions/outcomes
  -> advance window
```

No fold may fit on future observations relative to its test interval.

## 6. Current calibration status

The gate is intentionally expected to return `A197_CALIBRATION_BLOCKED` for the currently known TrueData corpus because the repository evidence does not establish the required 120 trading days / 45,000 bars of valid LI history.

Therefore:

```text
Calibration entry = BLOCKED
Parameter freeze = BLOCKED
Formula promotion = BLOCKED
ExecutionGate = BLOCKED
Broker submissions = 0
```

This is a deliberate fail-closed result, not an implementation failure.

## 7. Production gate invariant

Until every required strategy formula is explicitly promoted:

```text
ExecutionGate = BLOCKED
Broker submissions = 0
```

This remains true even if individual research formulas are deterministic and tests pass.

## 8. F-114 special treatment

F-114 is intentionally left unresolved at the mathematical level. The repository contains evidence for distinct risk authorization, risk measurement, and quantity layers but does not justify selecting an arbitrary portfolio aggregation equation.

Therefore F-114 is the remaining strategy-definition gap, not a missing implementation detail to be filled with a convenient heuristic.

## 9. Canonical next phase

```text
A221
  |
  v
TrueData historical corpus
  |
  v
calibration-entry gate
  |
  +--> BLOCKED until A197 coverage is actually met
  |
  v
chronological calibration
  |
  +--> F-101 normalization
  +--> F-102 probability
  +--> F-104 horizon
  +--> F-105 excursion / EV
  +--> F-106 option economics
  +--> F-107/F-108 risk
  +--> F-112 protection
  |
  v
Out-of-sample evaluation
  |
  v
Resolve F-114 portfolio interaction
  |
  v
Promotion review
```

No production unlock occurs merely because historical backtests show profit.
