# Canonical Variable Registry
## Adaptive Options Trading System — Version 1.0

### Registry Purpose

Every variable in the strategy must exist in this registry before implementation.

Each variable has:

`ID`
`Name`
`Layer`
`Definition`
`Formula`
`Source`
`Dependency`
`Update Trigger`
`Historical Requirement`
`Look-Ahead Risk`
`Consumer`
`Status`

`Status` is one of:

`FIXED`

`DERIVED`

`LEARNED`

`TBD`

No implementation variable may exist outside this registry without being added here first.

---

## A. Raw Data Variables

`RAW-001`

Name: `exchange_timestamp`

Layer: Raw Event

Definition: Timestamp assigned by the exchange/feed to the market event.

Source: TrueData.

Update: Every applicable event.

Historical: Required.

Look-ahead risk: None if used only at or before event time.

Consumer: All downstream layers.

Status: TBD — exact TrueData field name and precision.

---

`RAW-002`

Name: `receive_timestamp`

Definition: Local timestamp at which our system receives the event.

Source: Our ingestion layer.

Update: Every received event.

Historical: Must be captured by us.

Look-ahead risk: None.

Consumer: Latency and execution model.

Status: FIXED.

---

`RAW-003`

Name: `sequence`

Definition: Feed/event sequence identifier used for ordering and gap detection.

Source: TrueData if supplied.

Update: Every event.

Historical: Required.

Consumer: Data integrity.

Status: TBD.

---

`RAW-004`

Name: `symbol`

Definition: Canonical instrument identifier.

Source: TrueData instrument metadata/feed.

Consumer: Entire system.

Status: TBD.

---

`RAW-005`

Name: `ltp`

Definition: Last traded price.

Source: TrueData.

Update: Trade/event dependent.

Consumer: Price state, options state, execution model.

Status: TBD — exact field semantics.

---

`RAW-006`

Name: `ltq`

Definition: Last traded quantity.

Source: TrueData.

Consumer: Trade-flow engine.

Status: TBD.

---

`RAW-007`

Name: `volume`

Definition: Cumulative traded volume.

Source: TrueData.

Consumer: Volume and profile engines.

Status: TBD.

---

`RAW-008`

Name: `bid`

Definition: Current best bid.

Source: TrueData.

Consumer: Liquidity and execution.

Status: TBD.

---

`RAW-009`

Name: `bid_quantity`

Definition: Quantity available at best bid.

Source: TrueData.

Consumer: Liquidity and execution.

Status: TBD.

---

`RAW-010`

Name: `ask`

Definition: Current best ask.

Source: TrueData.

Consumer: Liquidity and execution.

Status: TBD.

---

`RAW-011`

Name: `ask_quantity`

Definition: Quantity available at best ask.

Source: TrueData.

Consumer: Liquidity and execution.

Status: TBD.

---

`RAW-012`

Name: `open_interest`

Definition: Current open interest.

Source: TrueData.

Consumer: Options state.

Status: TBD.

---

`RAW-013`

Name: `open_interest_change`

Definition: Change in open interest.

Source: TrueData or derived.

Consumer: Options state.

Status: TBD.

---

`RAW-014`

Name: `option_greeks`

Definition: IV, Delta, Gamma, Theta, Vega where available.

Source: TrueData.

Consumer: Option selection and risk analysis.

Status: TBD.

---

## B. Canonical Market State

`STATE-001`

Name: `mid_price`

Formula:

`Mid = (Bid + Ask) / 2`

Dependency:

`bid, ask`

Update: Bid/ask change.

Consumer: Price and execution models.

Status: FIXED.

---

`STATE-002`

Name: `spread`

Formula:

`Spread = Ask - Bid`

Dependency:

`bid, ask`

Consumer: Liquidity/execution.

Status: FIXED.

---

`STATE-003`

Name: `relative_spread`

Formula:

`RelativeSpread = Spread / Mid`

Consumer: Liquidity/execution.

Status: FIXED.

---

`STATE-004`

Name: `price_change`

Formula:

`ΔP_t = P_t - P_(t-1)`

Consumer: Momentum.

Status: FIXED.

---

`STATE-005`

Name: `return`

Formula:

`R_t = (P_t - P_(t-1)) / P_(t-1)`

Consumer: Volatility and directional models.

Status: FIXED.

---

`STATE-006`

Name: `price_velocity`

Formula:

`Velocity = ΔP / Δt`

Consumer: Momentum/regime.

Status: FIXED.

---

`STATE-007`

Name: `price_acceleration`

Formula:

`Acceleration = ΔVelocity / Δt`

Consumer: Momentum/regime.

Status: FIXED.

---

`STATE-008`

Name: `liquidity_imbalance`

Formula:

`LI = (BidQty - AskQty) / (BidQty + AskQty)`

Undefined when denominator equals zero.

Consumer: Liquidity/regime.

Status: FIXED.

---

## C. Order-Flow Variables

`FLOW-001`

Name: `aggressive_buy_volume`

Definition: Volume classified as buyer initiated.

Dependency:

`trade_price, bid, ask, trade_size`

Consumer: Delta engine.

Status: TBD — classification method depends on available feed semantics.

---

`FLOW-002`

Name: `aggressive_sell_volume`

Definition: Volume classified as seller initiated.

Consumer: Delta engine.

Status: TBD.

---

`FLOW-003`

Name: `unknown_trade_volume`

Definition: Trade volume for which aggressor direction cannot be reliably established.

Consumer: Data quality and delta.

Status: FIXED.

---

`FLOW-004`

Name: `delta`

Formula:

`Delta = AggressiveBuyVolume - AggressiveSellVolume`

Consumer: Order-flow model.

Status: FIXED.

---

`FLOW-005`

Name: `cumulative_delta`

Formula:

`CumDelta_t = CumDelta_(t-1) + Delta_t`

Consumer: Order-flow/regime.

Status: FIXED.

---

`FLOW-006`

Name: `delta_velocity`

Formula:

`ΔDelta / Δt`

Consumer: Momentum/regime.

Status: FIXED.

---

`FLOW-007`

Name: `delta_acceleration`

Formula:

`ΔDeltaVelocity / Δt`

Consumer: Momentum/regime.

Status: FIXED.

---

## D. Volume Variables

`VOL-001`

Name: `volume_rate`

Definition: Volume accumulated per unit time.

Consumer: Volume intensity.

Status: FIXED.

---

`VOL-002`

Name: `trade_frequency`

Definition: Number of trades/events per unit time.

Consumer: Market activity.

Status: FIXED.

---

`VOL-003`

Name: `average_trade_size`

Formula:

`TotalTradeVolume / NumberOfTrades`

Consumer: Flow characterization.

Status: FIXED.

---

`VOL-004`

Name: `volume_intensity`

Definition: Current volume rate relative to historically expected volume for the relevant context.

Conceptual formula:

`VolumeRate / ExpectedVolumeRate(context)`

Consumer: Regime model.

Status: LEARNED because expected-volume distribution is learned.

---

## E. Volatility Variables

`VOLAT-001`

Name: `micro_volatility`

Definition: Realized volatility over the shortest validated observation horizon.

Consumer: Microstructure model.

Status: LEARNED window.

---

`VOLAT-002`

Name: `short_volatility`

Definition: Short-horizon realized volatility.

Consumer: Scalping model.

Status: LEARNED window.

---

`VOLAT-003`

Name: `intraday_volatility`

Definition: Intraday realized volatility.

Consumer: Intraday model.

Status: LEARNED window.

---

`VOLAT-004`

Name: `volatility_percentile`

Formula:

`Fσ(σ_t | context, information <= t)`

Consumer: Regime model.

Status: LEARNED.

---

## F. Profile Variables

`PROFILE-001`

Name: `volume_profile`

Definition: Cumulative traded volume by price level as of event `t`.

Dependency:

`trade_price, trade_volume`

Consumer: Profile model.

Status: FIXED architecture.

---

`PROFILE-002`

Name: `POC`

Definition: Price level with maximum accumulated volume.

Consumer: Profile model.

Status: DERIVED.

---

`PROFILE-003`

Name: `value_area_high`

Definition: Upper boundary of validated value-area construction.

Status: LEARNED construction parameters.

---

`PROFILE-004`

Name: `value_area_low`

Definition: Lower boundary of validated value-area construction.

Status: LEARNED construction parameters.

---

`PROFILE-005`

Name: `distance_from_POC`

Formula:

`Price - POC`

Consumer: Market context.

Status: FIXED.

---

## G. Options Variables

`OPT-001`

Name: `underlying_symbol`

Definition: Underlying instrument associated with option.

Source: TrueData instrument metadata.

Status: TBD.

---

`OPT-002`

Name: `expiry`

Definition: Contract expiry.

Consumer: Contract selection.

Status: TBD.

---

`OPT-003`

Name: `strike`

Definition: Option strike price.

Consumer: Contract selection.

Status: TBD.

---

`OPT-004`

Name: `option_type`

Definition: CE or PE.

Consumer: Directional expression.

Status: TBD.

---

`OPT-005`

Name: `option_bid`

Consumer: Execution.

Status: TBD.

---

`OPT-006`

Name: `option_ask`

Consumer: Execution.

Status: TBD.

---

`OPT-007`

Name: `option_bid_quantity`

Consumer: Execution.

Status: TBD.

---

`OPT-008`

Name: `option_ask_quantity`

Consumer: Execution.

Status: TBD.

---

`OPT-009`

Name: `option_volume`

Consumer: Liquidity and selection.

Status: TBD.

---

`OPT-010`

Name: `option_OI`

Consumer: Option context.

Status: TBD.

---

`OPT-011`

Name: `option_IV`

Consumer: Option selection.

Status: TBD.

---

`OPT-012`

Name: `option_delta`

Consumer: Option selection.

Status: TBD.

---

`OPT-013`

Name: `option_gamma`

Consumer: Risk/option behavior.

Status: TBD.

---

`OPT-014`

Name: `option_theta`

Consumer: Holding-cost model.

Status: TBD.

---

`OPT-015`

Name: `option_vega`

Consumer: Volatility sensitivity.

Status: TBD.

---

## H. Normalized Features

`FEAT-001`

Name: `delta_percentile`

Definition: Current delta relative to historical conditional delta distribution.

Dependency:

`delta + historical_context`

Consumer: Probability model.

Status: LEARNED.

---

`FEAT-002`

Name: `volume_percentile`

Consumer: Probability model.

Status: LEARNED.

---

`FEAT-003`

Name: `spread_percentile`

Consumer: Execution/regime.

Status: LEARNED.

---

`FEAT-004`

Name: `liquidity_percentile`

Consumer: Execution/regime.

Status: LEARNED.

---

`FEAT-005`

Name: `volatility_percentile`

Consumer: Probability model.

Status: LEARNED.

---

`FEAT-006`

Name: `momentum_score`

Definition: Statistical representation of directional price/order-flow persistence.

Dependency:

`price + delta + volume + liquidity`

Consumer: Regime model.

Status: LEARNED.

---

`FEAT-007`

Name: `absorption_score`

Definition: Statistical representation of aggressive flow failing to produce proportional price movement.

Dependency:

`aggressive_flow + price_response + liquidity`

Consumer: Regime model.

Status: LEARNED.

---

`FEAT-008`

Name: `exhaustion_score`

Definition: Statistical representation of declining directional efficiency after sustained movement.

Dependency:

`price + delta + volume + acceleration`

Consumer: Regime model.

Status: LEARNED.

---

`FEAT-009`

Name: `liquidity_stress_score`

Dependency:

`spread + liquidity + withdrawal/replenishment`

Consumer: Regime and execution.

Status: LEARNED.

---

## I. Probability Variables

`PROB-001`

Name: `P_up`

Definition: Probability of validated upward movement over a specified horizon.

Consumer: Step Three.

Status: LEARNED.

---

`PROB-002`

Name: `P_down`

Definition: Probability of validated downward movement.

Consumer: Step Three.

Status: LEARNED.

---

`PROB-003`

Name: `P_neutral`

Definition: Probability of no meaningful directional movement.

Consumer: Step Three.

Status: LEARNED.

---

`PROB-004`

Name: `P_regime`

Definition: Probability distribution over market regimes.

Consumer: Steps Three and Four.

Status: LEARNED.

---

`PROB-005`

Name: `P_horizon`

Definition: Probability distribution of expected movement horizon.

Consumer: Steps Three and Four.

Status: LEARNED.

---

`PROB-006`

Name: `MFE_distribution`

Definition: Conditional distribution of future maximum favorable excursion.

Consumer: Steps Three and Four.

Status: LEARNED.

---

`PROB-007`

Name: `MAE_distribution`

Definition: Conditional distribution of future maximum adverse excursion.

Consumer: Steps Three and Four.

Status: LEARNED.

---

`PROB-008`

Name: `probability_uncertainty`

Definition: Statistical uncertainty surrounding probability estimates.

Consumer: Trade gate.

Status: LEARNED.

---

## J. Trade Decision Variables

`TRADE-001`

Name: `directional_edge`

Formula:

`max(P_up,P_down) - second_best_directional_probability`

Consumer: Trade gate.

Status: DERIVED from learned probabilities.

---

`TRADE-002`

Name: `expected_gross_EV`

Definition: Expected economic value before execution costs.

Consumer: Trade selection.

Status: DERIVED.

---

`TRADE-003`

Name: `execution_cost`

Formula:

`spread + slippage + fees + other validated costs`

Consumer: EV.

Status: DERIVED/LEARNED.

---

`TRADE-004`

Name: `conservative_EV`

Definition: Lower confidence estimate of net expected value.

Consumer: Entry gate.

Status: LEARNED methodology.

---

`TRADE-005`

Name: `effective_risk`

Definition: Expected economic loss including execution effects.

Consumer: Position sizing.

Status: DERIVED/LEARNED.

---

`TRADE-006`

Name: `EV_per_risk`

Formula:

`ConservativeEV / EffectiveRisk`

Consumer: Candidate ranking.

Status: DERIVED.

---

`TRADE-007`

Name: `position_size`

Formula:

`floor(RiskBudget / EffectiveRiskPerUnit)`

Consumer: Execution.

Status: DERIVED.

---

`TRADE-008`

Name: `entry_decision`

Allowed values:

`NO_TRADE`

`BUY_CE`

`BUY_PE`

Consumer: Execution engine.

Status: FIXED state-machine contract.

---

## K. Position Management Variables

`POS-001`

Name: `entry_price`

Definition: Actual or realistically simulated execution price.

Status: DERIVED.

---

`POS-002`

Name: `current_price`

Consumer: Position state.

Status: DERIVED.

---

`POS-003`

Name: `peak_price`

Formula:

`max(all observed favorable prices since entry)`

Status: DERIVED.

---

`POS-004`

Name: `current_profit`

Definition: Current mark-to-market profit after appropriate execution assumptions.

Status: DERIVED.

---

`POS-005`

Name: `peak_profit`

Definition: Maximum observed favorable profit.

Status: DERIVED.

---

`POS-006`

Name: `continuation_probability`

Consumer: Forward management.

Status: LEARNED.

---

`POS-007`

Name: `reversal_probability`

Consumer: Backward protection.

Status: LEARNED.

---

`POS-008`

Name: `expected_additional_MFE`

Consumer: Continuation value.

Status: LEARNED.

---

`POS-009`

Name: `expected_additional_MAE`

Consumer: Risk.

Status: LEARNED.

---

`POS-010`

Name: `continuation_value`

Conceptual formula:

`ExpectedFutureProfit - ExpectedFutureRisk - ExpectedFutureCost`

Consumer: Exit decision.

Status: LEARNED methodology.

---

`POS-011`

Name: `allowed_giveback`

Formula:

`Q_q(Giveback | CurrentState, ProfitState)`

Consumer: Profit protection.

Status: LEARNED.

---

`POS-012`

Name: `profit_floor`

Formula:

`PeakPrice - AllowedGiveback`

Consumer: Stop engine.

Status: DERIVED.

---

`POS-013`

Name: `current_stop`

Constraint:

`Stop_new >= Stop_old`

for long positions.

Consumer: Execution.

Status: FIXED invariant.

---

## L. Execution Variables

`EXEC-001`

Name: `signal_timestamp`

Status: DERIVED.

---

`EXEC-002`

Name: `order_timestamp`

Status: DERIVED from execution system.

---

`EXEC-003`

Name: `fill_timestamp`

Status: DERIVED from execution system or simulator.

---

`EXEC-004`

Name: `signal_to_order_latency`

Formula:

`OrderTimestamp - SignalTimestamp`

Status: DERIVED.

---

`EXEC-005`

Name: `order_to_fill_latency`

Formula:

`FillTimestamp - OrderTimestamp`

Status: DERIVED.

---

`EXEC-006`

Name: `expected_slippage`

Definition: Conditional expected execution deviation.

Consumer: Trade decision and backtest.

Status: LEARNED.

---

`EXEC-007`

Name: `realized_slippage`

Definition: Actual execution price versus reference executable price.

Status: DERIVED.

---

## M. Outcome Variables

`OUT-001`

Name: `realized_PnL`

Definition: Actual net trade result after execution costs.

Status: DERIVED.

---

`OUT-002`

Name: `MFE`

Definition: Maximum favorable excursion after entry.

Status: DERIVED from future observations.

---

`OUT-003`

Name: `MAE`

Definition: Maximum adverse excursion after entry.

Status: DERIVED from future observations.

---

`OUT-004`

Name: `time_in_trade`

Definition: Exit timestamp minus entry timestamp.

Status: DERIVED.

---

`OUT-005`

Name: `time_to_MFE`

Status: DERIVED.

---

`OUT-006`

Name: `time_to_MAE`

Status: DERIVED.

---

`OUT-007`

Name: `target_before_stop`

Definition: Whether defined target condition occurred before defined stop condition.

Status: DERIVED.

---

`OUT-008`

Name: `stop_before_target`

Status: DERIVED.

---

## N. Learning Variables

`LEARN-001`

Name: `model_version`

Definition: Immutable identifier for a trained model.

Status: FIXED contract.

---

`LEARN-002`

Name: `training_cutoff`

Definition: Last timestamp permitted in model training.

Status: FIXED contract.

---

`LEARN-003`

Name: `calibration_model`

Definition: Probability calibration transformation.

Status: LEARNED.

---

`LEARN-004`

Name: `bayesian_state`

Definition: Current Bayesian parameters.

Status: LEARNED.

---

`LEARN-005`

Name: `similarity_parameters`

Definition: Parameters used by historical-state similarity engine.

Status: LEARNED.

---

`LEARN-006`

Name: `profit_floor_quantile`

Definition: Quantile used to determine allowable profit giveback.

Status: LEARNED.

---

`LEARN-007`

Name: `continuation_threshold`

Definition: Minimum validated continuation value required to remain exposed.

Status: LEARNED.

---

`LEARN-008`

Name: `reversal_threshold`

Definition: Validated reversal probability/state threshold.

Status: LEARNED.

---

`LEARN-009`

Name: `regime_transition_sensitivity`

Definition: Sensitivity to statistically abnormal regime transitions.

Status: LEARNED.

---

`LEARN-010`

Name: `risk_budget_model`

Definition: Mapping from capital/state/edge/risk to maximum position risk.

Status: LEARNED.

---

# Dependency Rules

Every variable must satisfy:

`Source → Dependency → Transformation → Consumer`.

No circular dependency is permitted.

The dependency direction is strictly:

`Raw`

→ `State`

→ `Feature`

→ `Probability`

→ `Decision`

→ `Position`

→ `Outcome`

→ `Learning`.

Learning may update future model parameters.

Learning may never retroactively modify a historical decision.

---

# Implementation Gate

Before implementation begins, every `TBD` variable must be resolved against the actual TrueData documentation or explicitly removed from the specification.

The following information must be established for every TrueData-dependent variable:

`Exact field name`

`Feed/API`

`Subscription entitlement`

`Data type`

`Precision`

`Timestamp semantics`

`Update semantics`

`Historical availability`

`Historical retention`

`Missing-data behavior`

`Reset behavior`

`Sequence behavior`

`Known limitations`.

If a variable cannot be sourced reliably, it is not approximated silently.

It is either:

`REMOVED`

or:

`REPLACED WITH VALIDATED DERIVED VARIABLE`.

---

# Canonical Status

This registry is now the authoritative bridge between:

`Master Mathematical Specification`

and:

`Future Implementation`.

Any implementation variable not traceable to this registry is considered undefined.

Any TrueData field not mapped to this registry is considered unused until explicitly incorporated and validated.

Any future strategy modification must update this registry before implementation.