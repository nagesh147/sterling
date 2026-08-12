# Adaptive Edge — Exact Source Traceability

## Authority

The sole strategy authority is:

```text
Adaptive Order-Flow Options Scalping and Intraday Strategy
Master Mathematical Specification — Version 1.0
```

The provisional F-101..F-114 reconstruction is deprecated and is not a source authority. `RECOVERY.md` explicitly records that those identifiers were a reconstructed v0.1.0 model, not recovered historical mathematics.

## Rule

A component is `EXACT` only when its implemented relationship is directly anchored to the source document **and every required input has a source-defined semantic meaning/provenance** and its tests verify the stated relationship. `PARTIAL` means only part of the source requirement is implemented. `BLOCKED` means the source requirement is known but cannot be implemented faithfully without a missing external contract or learned/validated parameter/method. `REMOVED` means an earlier implementation was deleted because it introduced behavior not supported by the source.

## Traceability

| Source | Requirement | Code | Status |
|---|---|---|---|
| §7 | Mid / spread / relative spread / price change / return / velocity / acceleration | `canonical_math.py`, `feature_state.py` | EXACT for stated operators |
| §8 | Incremental volume | `canonical_math.py`, `feature_state.py` | EXACT for reset semantics |
| §9 | Aggressor classification | `canonical_math.py`, `feature_state.py` | EXACT |
| §10 | Delta / cumulative delta / delta velocity / acceleration | `canonical_math.py`, `feature_state.py` | EXACT for implemented fields |
| §11 | Liquidity imbalance | `canonical_math.py`, `feature_state.py` | EXACT |
| §12 | Volume intensity | `canonical_math.py` | PARTIAL: exact ratio; expected-rate semantic source remains upstream |
| §19 | Causal contextual normalization | `normalization.py`, `test_normalization.py` | PARTIAL: empirical CDF and causal filtering exact for explicit context; context construction/min-data policy remain unresolved |
| §21 | Directional probability / normalized return | `canonical_math.py`, probability layer | PARTIAL: baseline empirical probability implemented; outcome/calibration parameters remain unfrozen |
| §22 | Multinomial logistic model | `canonical_math.py`, probability contract | PARTIAL: equation exists; exact fitting/optimization method not recovered |
| §23 | Empirical similarity | `canonical_math.py`, `similarity_selection.py`, `statistics.py` | PARTIAL: operators and explicit effective-sample gate implemented; complete source-defined selection procedure remains unresolved |
| §24 | Bayesian state | `canonical_math.py`, `bayesian_state.py` | PARTIAL: additive and explicit-decay update boundaries implemented; initialization and learned decay semantics remain unresolved |
| §31 | Execution cost decomposition | `canonical_math.py`, `economic.py` | PARTIAL: decomposition contract; provider-specific distributions pending |
| §32 | Option selection by ExpectedNetEV | `option_selection.py` | PARTIAL: exact argmax/constraint boundary exists; upstream candidate contract is not yet wired |
| §33 | Target/stop EV competition | `target_stop.py` | EXACT for source-defined argmax over supplied candidate estimates |
| §34 | Conservative EV / no-trade | `target_stop.py` | PARTIAL: relationship/gate exact; confidence-bound estimation remains unresolved |
| §35 | Entry gates | `entry_gates.py` | EXACT predicate for stated gate conditions; upstream gate-input derivations remain blocked |
| §36 | Risk per unit / position sizing | `canonical_math.py` | PARTIAL: RiskPerUnit/GrossRisk/position-size relationship exact; `EffectiveRiskPerUnit` semantics unresolved |
| §39 | Continuation value | `canonical_math.py` | EXACT operator over supplied expected quantities |
| §40 | Giveback / profit accounting | `canonical_math.py`, `position_management.py` | PARTIAL: PeakPnL/CurrentPnL/Giveback exact; AllowedGiveback estimator remains blocked |
| §41 | Monotonic stop | `canonical_math.py`, `position_management.py` | PARTIAL: monotonic operator exact; learned/derived protection inputs remain unresolved |
| §42 | No risk expansion | `canonical_math.maximum_accepted_risk` | EXACT invariant |
| §43 | Dynamic mode | not implemented | BLOCKED: source defines a function of state; exact function not recovered |
| §46 | Conservative continuation exit | `canonical_math.py` | PARTIAL: exit predicate exact; upstream conservative continuation-value estimator remains blocked |
| §§50–54 | Walk-forward learning | `research_dataset.py`, `walk_forward.py` | PARTIAL: causal fold machinery exists; exact fitting/calibration method remains blocked |
| §66 | Canonical trade objective / EV per risk | `canonical_math.py`, economic layer | PARTIAL: NetEV and EV-per-risk relationship exists; `EffectiveRisk_i` semantics/derivation is BLOCKED |

## Risk-specific recovery conclusion

The repository search recovered `RISK.md`, `RECOVERY.md`, `FORMULAS.md`, and `TRACEABILITY.md`, but did not recover an authoritative definition of:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
F-107 historical equation
F-108 historical equation
```

`RISK.md` therefore no longer treats F-107/F-108 as recovered equations. `RECOVERY.md` establishes that F-107/F-108 belonged to a reconstructed v0.1.0 model. They cannot be promoted to canonical strategy mathematics.

Consequently, the following substitutions are explicitly prohibited:

```text
EffectiveRisk_i = GrossRisk
EffectiveRisk_i = RiskPerUnit × Q
EffectiveRisk_i = EffectiveRiskPerUnit
EffectiveRisk_i = abs(EntryPrice - InitialStop)
```

A new source artifact defining these semantics is required before §66 EV-per-risk can become `EXACT`.

## Removed as non-canonical

The following were removed because they introduced strategy semantics not explicitly supported by the source:

```text
backend/app/engines/adaptive_edge/contracts.py
backend/app/engines/adaptive_edge/state.py
backend/app/engines/adaptive_edge/state_machine.py
backend/app/engines/adaptive_edge/parameter_fitting.py
```

## Exactness gate

No subsequent implementation may mark a source row `EXACT` merely because it is mathematically plausible. It must be traceable to the source, every required input must have defined semantics/provenance, and tests must verify the source relationship.
