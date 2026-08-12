# Adaptive Edge — Exact Source Traceability

## Authority

The original strategy authority remains:

```text
Adaptive Order-Flow Options Scalping and Intraday Strategy
Master Mathematical Specification — Version 1.0
```

That source does not contain complete authoritative definitions for F-101..F-114.

The new-definition path is explicitly separated:

```text
Original source recovery: NOT RECOVERED
V2.1 new strategy definition: 2.1.0-proposed
```

## Rule

A component is `EXACT` only when its implemented relationship is directly anchored to the source document and every required input has source-defined semantics/provenance and tests verify the relationship.

A V2.1 component is instead marked `IMPLEMENTED-PROPOSED` when it is fully defined by the explicitly versioned A26-ND strategy proposal but is not claimed as recovered historical mathematics.

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
| §25 | Probability calibration | `v2/25_PROBABILITY_CALIBRATION_CONTRACT.md` | BLOCKED: original-source calibration method is undefined |
| §28 | Horizon distribution | `v2/28_HORIZON_DISTRIBUTION_CONTRACT.md` | BLOCKED: original-source target/horizon semantics are undefined |
| §31 | Execution cost decomposition | `execution_cost.py`, `economic.py` | PARTIAL: additive provider-neutral boundary implemented; provider-specific distributions remain unresolved |
| §32 | Option selection by ExpectedNetEV | `option_selection.py`, `test_option_selection.py` | PARTIAL: argmax/constraint boundary implemented; upstream candidate derivation remains unresolved |
| §33 | Target/stop EV competition | `target_stop.py` | EXACT for source-defined argmax over supplied candidate estimates |
| §34 | Conservative EV / no-trade | `target_stop.py` | PARTIAL: relationship/gate exact; confidence-bound estimation remains unresolved |
| §35 | Entry gates | `entry_gates.py` | EXACT predicate for stated gate conditions; upstream gate-input derivations remain blocked |
| §36 | Risk per unit / position sizing | `canonical_math.py` | PARTIAL: generic operators exist; original `EffectiveRiskPerUnit` semantics unresolved |
| §39 | Continuation value | `canonical_math.py` | EXACT operator over supplied expected quantities |
| §40 | Giveback / profit accounting | `canonical_math.py`, `position_management.py` | PARTIAL: PeakPnL/CurrentPnL/Giveback exact; AllowedGiveback estimator remains blocked |
| §41 | Monotonic stop | `canonical_math.py`, `position_management.py` | PARTIAL: monotonic operator exact; original learned protection inputs remain unresolved |
| §42 | No risk expansion | `canonical_math.maximum_accepted_risk` | EXACT invariant |
| §43 | Dynamic mode | `canonical_math.py` | PARTIAL: original function unresolved; V2.1 replacement is explicitly versioned below |
| §§50–54 | Walk-forward learning | `research_dataset.py`, `walk_forward.py` | PARTIAL: causal fold machinery exists; exact original fitting/calibration method remains blocked |
| §66 | Canonical trade objective / EV per risk | `canonical_math.py`, economic layer | PARTIAL: NetEV and EV-per-risk relationship exists; original `EffectiveRisk_i` derivation remains blocked |

## V2.1 proposed strategy traceability

| Formula | V2.1 definition | Implementation | Tests | Status |
|---|---|---|---|---|
| F-101 | weighted z-score composite bounded by tanh | `strategy_v21.py:f101_feature_score` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-102 | three-state softmax directional edge | `strategy_v21.py:f102_edge_score` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-103 | edge + economics + data-quality + mode eligibility | `strategy_v21.py:f103_opportunity_eligibility` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-104 | volatility/drawdown mode state machine | `strategy_v21.py:f104_dynamic_mode` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-105 | monotonic favorable-direction protection | `strategy_v21.py:f105_profit_protection` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-106 | capped mode/edge dynamic risk | `strategy_v21.py:f106_dynamic_risk` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-107 | protection distance + explicit execution cost | `strategy_v21.py:f107_risk_per_unit` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-108 | floor/increment/max constrained sizing | `strategy_v21.py:f108_position_sizing` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-109 | directional CE/PE + constraint argmax | `strategy_v21.py:f109_instrument_selection` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-110 | directional trigger | `strategy_v21.py:f110_entry_trigger` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-111 | protection/target/horizon exit | `strategy_v21.py:f111_exit_trigger` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-112 | explicit protection parameters | `strategy_v21.py:f112_protection_parameters` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-113 | cooldown + new-opportunity re-entry | `strategy_v21.py:f113_reentry` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |
| F-114 | shared risk capacity + max positions | `strategy_v21.py:f114_multi_position_interaction` | `test_strategy_v21.py` | IMPLEMENTED-PROPOSED |

## Promotion boundary

```text
IMPLEMENTED-PROPOSED
        |
        v
walk-forward research
        |
        v
validation report
        |
        v
explicit promotion approval
        |
        v
EXECUTION AUTHORIZED
```

`promotion.py` currently sets the strategy to `RESEARCH_ONLY`. Therefore implementation of F-101..F-114 does not authorize live execution.

## Risk-specific recovery conclusion

The original repository still does not provide an authoritative historical definition of:

```text
EffectiveRisk_i
EffectiveRiskPerUnit
historical F-107
historical F-108
```

The V2.1 definitions are explicitly new strategy semantics and must not be described as recovered historical formulas.
