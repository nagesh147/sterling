# Adaptive Edge — Exact Source Traceability

## Authority

The sole strategy authority is:

```text
Adaptive Order-Flow Options Scalping and Intraday Strategy
Master Mathematical Specification — Version 1.0
```

The provisional F-101..F-114 reconstruction is deprecated and is not a source authority.

## Rule

A component is `EXACT` only when its implemented relationship is directly anchored to the source document and its tests verify the stated relationship. `PARTIAL` means only part of the source requirement is implemented. `BLOCKED` means the source requirement is known but cannot be implemented without a missing external contract or learned/validated parameter/method. `REMOVED` means an earlier implementation was deleted because it introduced behavior not supported by the source.

| Source | Requirement | Code | Status |
|---|---|---|---|
| §7 | Mid / spread / relative spread / price change / return / velocity / acceleration | `canonical_math.py`, `feature_state.py` | EXACT for stated operators |
| §8 | Incremental volume | `canonical_math.py`, `feature_state.py` | EXACT for reset semantics |
| §9 | Aggressor classification | `canonical_math.py`, `feature_state.py` | EXACT |
| §10 | Delta / cumulative delta / delta velocity / acceleration | `canonical_math.py`, `feature_state.py` | EXACT for implemented fields |
| §11 | Liquidity imbalance | `canonical_math.py`, `feature_state.py` | EXACT |
| §12 | Volume intensity | `canonical_math.py` | EXACT operator; contextual rate source not implemented |
| §19 | Causal contextual normalization | `normalization.py` | BLOCKED: exact estimator/context construction not fully recovered |
| §21 | Directional probability / normalized return | `canonical_math.py`, probability layer | PARTIAL |
| §22 | Multinomial logistic model | `canonical_math.py`, probability contract | PARTIAL: mathematical model operator exists; exact source-defined fitting/optimization method is not specified |
| §23 | Empirical similarity | `canonical_math.py` | PARTIAL: operators only; effective-sample gate remains |
| §24 | Bayesian state | `canonical_math.py` | PARTIAL: update relationships only; learned decay/initialization remain |
| §31 | Execution cost decomposition | `canonical_math.py`, `economic.py` | PARTIAL: decomposition contract; provider-specific distributions pending |
| §32 | Option selection by ExpectedNetEV | `option_selection.py` | PARTIAL: exact argmax/constraint boundary exists; upstream candidate contract is not yet wired |
| §33 | Target/stop EV competition | `target_stop.py` | EXACT for source-defined argmax over supplied candidate estimates |
| §34 | Conservative EV / no-trade | `target_stop.py` | EXACT operator for strict-positive eligibility; orchestration gate remains upstream |
| §35 | Entry gates | strategy orchestration | BLOCKED until all exact gate inputs exist |
| §36 | Risk per unit / position sizing | `canonical_math.py` | EXACT operators; full production constraints remain separate |
| §39 | Continuation value | `canonical_math.py` | EXACT operator |
| §40 | Giveback / profit floor | `canonical_math.py`, `position_management.py` | PARTIAL |
| §41 | Monotonic stop | `canonical_math.py`, `position_management.py` | EXACT invariant |
| §42 | No risk expansion | `canonical_math.maximum_accepted_risk` | EXACT invariant |
| §43 | Dynamic mode | not implemented | BLOCKED: source defines a function of state; no arbitrary enum is permitted |
| §46 | Conservative continuation exit | strategy orchestration | BLOCKED |
| §§50–54 | Walk-forward learning | `research_dataset.py`, `walk_forward.py` | PARTIAL: causal fold machinery exists; exact fitting/calibration method remains blocked |
| §66 | Canonical trade objective / EV per risk | `canonical_math.py`, economic layer | PARTIAL |

## Removed as non-canonical

The following were removed because they introduced strategy semantics not explicitly supported by the source:

```text
backend/app/engines/adaptive_edge/contracts.py
backend/app/engines/adaptive_edge/state.py
backend/app/engines/adaptive_edge/state_machine.py
backend/app/engines/adaptive_edge/parameter_fitting.py
```

## Exactness gate

No subsequent implementation may mark a source row `EXACT` merely because it is mathematically plausible. It must be traceable to the source and tested against that source definition.
