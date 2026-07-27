# Sterling Value-Flow Navigator - Implementation Specification

> **For the implementing AI:** Read this document completely before editing code.
> Implement it in phases, test first, and do not silently substitute an invented
> formula when a source does not disclose one.

**Status:** Implementation handoff

**Date:** 2026-07-27

**Target branch:** `kitev2-develop`

**Primary integration:** Sterling Kite Engine, with an adapter boundary for other
Sterling signal engines.

**Goal:** Add an optional, separately configured "Sterling Value-Flow Navigator"
that combines Sterling's existing directional signal with independently designed
anchored-VWAP structure, projected ranges, volatility regime, option-flow, and
gamma-activity evidence. It must emit auditable fused signals without repainting,
using stale data, or bypassing any existing order or risk control.

**Short product rule:** Existing Sterling strategy decides the candidate
direction. Navigator decides whether the market structure, volatility, and
options evidence confirm, oppose, or cannot evaluate that candidate.

---

## 1. Source Contract and Intellectual-Honesty Boundary

### 1.1 Inputs used for this specification

1. `AVWAP_Navigator_Suite_Manual.pdf`
   - Local source used while preparing this plan:
     `/home/nageshmadaram/Downloads/AVWAP_Navigator_Suite_Manual.pdf`
   - SHA-256:
     `5f4e917e8bbd9563a700f782e2b36f53b6c1f4f05175e8d59203c366a1873897`
   - Document title: "AVWAP Navigator Suite - Official Trader's Manual"
   - Document version: 1.0, 2026
2. YouTube video:
   - URL: <https://www.youtube.com/watch?v=Ykm3-QeKIgg>
   - Video ID: `Ykm3-QeKIgg`
   - Title observed during research: "AVWAP Navigator : Updated indicators"
   - Channel observed during research: Subhadip Nandy / QuantGym
   - Duration observed during research: approximately 24 minutes

### 1.2 Requirement labels

Every behavior in this plan belongs to one of these classes:

- **`SOURCE-DEFINED`**: Directly described by the supplied manual or video.
- **`STERLING-DESIGNED`**: An independent, transparent implementation selected
  for Sterling because the source does not provide its formula.
- **`CALIBRATION-REQUIRED`**: A proposed initial threshold or weight. It must be
  measured on Sterling data before it is permitted to gate paper or live orders.

Use these labels in code comments, configuration descriptions, and validation
reports where the distinction matters. Do not market or label the implementation
as an exact reproduction of QuantGym's proprietary indicators.

### 1.3 What the sources define

| Area | Source-defined behavior |
|---|---|
| AutoAVWAP structure | Upper, Lower, and Mid anchored-VWAP levels; Mid is an equilibrium/value reference. Above Mid favors buyers, below Mid favors sellers, and behavior near Mid is balanced/choppy. |
| AutoAVWAP signals | Pullback families `P_Buy` and `P_Sell`; continuation families `Buy` and `Sell`; fewer, higher-quality signals; participation, candle quality, volatility, structure, extension, and cooldown matter. |
| Signal quality | Grades A+, A, and B represent decreasing confluence. Stops are volatility-aware; targets use reward-to-risk context; a stop must never be widened. |
| Projected ranges | Daily and weekly expected ranges are optional context. Range breaks can support continuation; rejection near an edge can support a fade. The video describes adaptive forecasts based on volatility and prior forecast outcomes. |
| Option flow | An oscillator centered at zero. Positive is bullish, negative is bearish, and near zero is neutral. Reference areas around `+68`, `+96`, `-68`, and `-96` are shown. A dynamic near-ATM mode is preferred for intraday use; a wider legacy mode is also described. |
| Gamma activity | A gamma "blast/burst" is an alert that unusual ATM option activity is expanding. It is confirmation or warning, not a standalone buy/sell command. It is emphasized on expiry day, especially later in the session, while a non-expiry occurrence can warn of an unusually forceful move. |
| Volatility regime | `EXPANSION`, `COMPRESSION`, and `NEUTRAL`; directional output `LONG`, `SHORT`, or `WAIT`; confidence, last flip, volatility score, gradient, and persistence. Compression should force `WAIT` for trend trades. |
| Confidence bands | The manual maps 80-100 to normal-size conditions, 60-80 to moderate, 40-60 to small, and below 40 to avoidance. Sterling treats these as advisory risk bands until independently validated and never uses them to increase existing risk limits. |
| Timeframes | The manual lists 1, 2, 3, 5, 10, 15, 30, 60, 75, and 240 minute contexts. Sterling v1 intentionally supports only the current Kite engine's 60-minute base-signal clock; other values must not appear selectable until implemented and tested end to end. |
| Suite hierarchy | First ask whether volatility supports directional trading, then evaluate AVWAP structure and risk, then check whether options flow agrees. The best setup is agreement across all layers; disagreement means reduce size or stand aside. |
| Non-repainting | The video specifically says the persistent "rocket" signal should not disappear after appearing. |

### 1.4 What the sources do not define

The sources do **not** disclose:

- how anchors are selected or replaced;
- exact AVWAP formulas beyond the anchored-VWAP concept;
- exact pullback, continuation, or grade formulas;
- exact range-forecast model;
- exact volatility score, regime, gradient, or confidence formulas;
- exact option-flow oscillator formula;
- exact gamma-event formula;
- exact suite fusion weights or thresholds;
- evidence that a claimed historical range-coverage percentage transfers to
  Sterling's instruments, data, timeframes, or execution.

The manual also states that its internal methodology is proprietary. Therefore:

1. Do not reverse engineer obfuscated or proprietary scripts.
2. Do not claim formula parity.
3. Do not turn presentation examples into hard-coded trading rules.
4. Implement the transparent clean-room models in this document.
5. Preserve raw inputs and diagnostics so every Sterling result can be explained.

### 1.5 Claims that must remain claims

The video's approximate "80-85% within the projected range" statement is a
presenter claim, not a Sterling acceptance criterion. Sterling must select a
target coverage, test actual out-of-sample coverage, and show the measured value.

The video's example trades are behavioral demonstrations, not performance
evidence. Do not encode the example date, symbol, or outcome into tests.

The walkthrough avoids the first five-minute bar. Treat that as session-risk
context, not proof of a universal edge. Sterling exposes a configurable
post-open entry delay and validates it independently.

---

## 2. Non-Negotiable Product and Safety Rules

1. Navigator is **off by default**.
2. Navigator has its own Settings section, persistence model, API, status, and
   reset action. Do not bury it in `EngineConfigModel`.
3. Turning Navigator on defaults to **advisory** mode. It combines evidence and
   generates fused signals, but it does not arm order execution.
4. `shadow` mode computes and stores decisions without changing visible
   eligibility. `advisory` mode surfaces fused decisions. `gate` mode may gate an
   existing auto-execution candidate only after the calibration-readiness gate is
   satisfied.
5. Navigator can block or downgrade a candidate when required data is unsafe. It
   cannot create an order independently of an active Sterling base direction.
6. Gamma activity never supplies direction by itself.
7. Missing, stale, incomplete, crossed, or invalid option data is `NO_DATA`, not
   neutral and never bullish/bearish.
8. Only closed price bars are used for entry decisions.
9. Once emitted, a signal event is immutable. Corrections create a new revision
   or diagnostic event; they do not rewrite the original decision.
10. Enabling Navigator creates an activation watermark. Data or signals before
    that timestamp cannot become "fresh" entries after enablement.
11. Disabling Navigator stops new sampling and new Navigator entry decisions. It
    does not close positions and does not stop existing position protection,
    trailing, GTT, or risk-breaker behavior.
12. Existing order gates remain mandatory: engine enabled, auto-execute enabled,
    trading mode, live-safety interlock, position dedupe, liquidity, risk sizing,
    loss breaker, expiry guard, and broker acceptance.
13. No historical option-flow or gamma backtest may be reported until Sterling
    has captured the required historical chain snapshots.
14. No client-computed indicator value may be used as order truth.
15. All defaults marked `CALIBRATION-REQUIRED` remain advisory until promoted by
    a recorded validation report.

---

## 3. Current Sterling Baseline

### 3.1 Existing integration points

| Current file | Current responsibility | Navigator action |
|---|---|---|
| `backend/app/engines/sterling_kite_engine/engine.py` | Closed-candle triple-SuperTrend direction, fresh alignment, trailing lifecycle | Preserve as a base-signal producer. Do not embed Navigator math here. |
| `backend/app/engines/sterling_kite_engine/schemas.py` | `EngineSignalRow`, legs, score, source, and engine configuration | Add an optional nested `navigator` result to rows. Keep existing `score` and `source` semantics compatible. |
| `backend/app/services/kite_engine/scanner.py` | Spot, derivative, and current spot-plus-premium confluence scans | Join a time-aligned Navigator snapshot after the raw signal has been computed. |
| `backend/app/services/kite_engine/service.py` | Scan orchestration and optional auto-execution callback | Enforce Navigator `gate` in the one central pre-order path. Never add a second order path. |
| `backend/app/services/kite_engine/state.py` | Per-user engine config and runtime state | Do not store Navigator in this module. Use a dedicated, versioned store with surfaced write failures. |
| `backend/app/services/exchanges/kite/instruments.py` | Cached instrument dump, token, lot-size, and expiry resolution | Reuse `InstrumentCache`; extend with an indexed option-slice query instead of rescanning all rows on every poll. |
| `backend/app/services/exchanges/kite/client.py` | Quote methods and broad option-chain construction | Add a narrow quote-slice service around `get_quote`; do not poll the current up-to-400-symbol broad chain. Support both NFO and BFO metadata. |
| `backend/app/engines/risk/option_pricing.py` | Black-Scholes enrichment | Reuse tested primitives where valid, but add fractional expiry time and never turn absent IV/gamma into zero. |
| `backend/app/engines/derivatives/gex_engine.py` | Existing static GEX view with its own scale | Do not reuse its arbitrary routing scale as a gamma-blast threshold. Navigator measures gamma activity, not dealer positioning. |
| `backend/app/services/db.py` | SQLite schema and `system_config` | Add explicit Navigator tables and indexes through the existing idempotent schema setup. |
| `backend/app/api/v1/endpoints/kite_engine.py` | Authenticated `/api/v1/kite/engine/*` endpoints | Follow its `UserContext` and active-client pattern in a separate Navigator router. |
| `backend/main.py` | Router and background-service lifecycle | Register the Navigator router and sampler lifecycle explicitly. |
| `frontend/src/components/kite/ConnectPane.tsx` | Settings category rail | Add a separate `navigator` section and render `NavigatorSettingsPanel`. |
| `frontend/src/components/kite/SterlingKiteEnginePane.tsx` | Signal table and detail workflow | Surface status, effective score, reasons, and diagnostics without changing raw signal provenance. |
| `frontend/src/hooks/useSterlingKiteEngine.ts` | React Query hooks for engine state | Keep existing hooks; add dedicated Navigator hooks and query keys. |
| `frontend/src/types/kiteEngine.ts` | Engine response types | Add only the optional row bridge; put full Navigator types in a new file. |

### 3.2 Prerequisite defects to resolve explicitly

#### A. Directional score contract

`backend/app/engines/directional/signal_engine.py` currently behaves like a
0-100 score producer, while `backend/app/schemas/directional.py` documents a
0-20 score and an auto-order path multiplies by five. Before a non-Kite engine
can use Navigator:

- define one canonical `score_100: float` contract;
- add an adapter for every legacy score scale;
- remove implicit multiplication from execution code only after regression tests
  prove all callers were migrated;
- version persisted or cached legacy rows so they cannot be misread.

Do not mix score cleanup with the Navigator formula. Complete it as a separate
Phase 0 change.

#### B. Existing `confluence` name

In the current Kite scanner, `source="confluence"` means underlying
triple-SuperTrend plus the selected option premium's triple-SuperTrend. Navigator
must not redefine it. Preserve `source` and add:

```text
navigator.status
navigator.suite_score
navigator.effective_score
navigator.reason_codes
```

#### C. Persistence failures

Current engine config persistence catches database exceptions and can silently
fall back. Navigator settings must:

- validate before writing;
- write transactionally;
- increment a revision;
- return the saved revision;
- leave the prior config active on failure;
- return a visible API error;
- never silently force a user-disabled setting back on.

#### D. Option-chain history

Current option summaries expose cumulative volume and current OI, not interval
deltas. A flow oscillator requires snapshots over time. Build and retain those
snapshots before claiming historical flow performance.

#### E. Expiry time

Integer calendar-day DTE is invalid for expiry-day gamma analysis. Navigator
must use positive fractional years based on the exchange session's exact expiry
timestamp, with timezone-aware timestamps.

---

## 4. Target Architecture

```text
                           closed price bars
                                  |
                     +------------+-------------+
                     |                          |
             existing Sterling            Navigator price
               base engine                  feature engine
                     |                 AVWAP / ranges / vol
                     |                          |
                     |                  captured option chain
                     |                          |
                     |                    flow / gamma
                     |                          |
                     +------------+-------------+
                                  |
                         event-time fusion
                                  |
                 +----------------+----------------+
                 |                |                |
             raw signal      fused decision    diagnostics
             unchanged       and eligibility   and history
                 |                |
                 +-------- signal table
                                  |
                  central existing order path
                    (gate mode only; all other
                     Sterling controls still run)
```

### 4.1 Bounded contexts

1. **Base signal adapter**
   - Converts an existing Sterling signal into one normalized contract.
   - Does not calculate Navigator features.
2. **Price feature engine**
   - Computes AVWAP structure, projected ranges, and volatility/trend regime from
     closed bars only.
3. **Option evidence engine**
   - Captures narrow option-chain snapshots and computes flow and gamma activity.
4. **Fusion engine**
   - Performs event-time alignment, hard gates, evidence scoring, and immutable
     event generation.
5. **Runtime service**
   - Owns per-account sampling, per-user configuration, status, persistence, and
     lifecycle.
6. **Presentation**
   - Displays server-calculated values; never recalculates order evidence.

### 4.2 Proposed files

```text
backend/app/engines/navigator/
  __init__.py
  schemas.py
  avwap.py
  projected_ranges.py
  volatility.py
  option_flow.py
  gamma_activity.py
  fusion.py
  quality.py

backend/app/services/navigator/
  __init__.py
  adapters.py
  calendar.py
  chain_sampler.py
  config_store.py
  instrument_slice.py
  repository.py
  service.py
  status.py

backend/app/api/v1/endpoints/
  navigator.py

backend/tests/engines/navigator/
  conftest.py
  test_avwap.py
  test_projected_ranges.py
  test_volatility.py
  test_option_flow.py
  test_gamma_activity.py
  test_fusion.py
  test_properties.py

backend/tests/services/navigator/
  test_chain_sampler.py
  test_config_store.py
  test_repository.py
  test_service_integration.py

backend/tests/api/
  test_navigator.py

frontend/src/components/kite/
  NavigatorSettingsPanel.tsx
  NavigatorStatusStrip.tsx
  NavigatorEvidencePanel.tsx

frontend/src/hooks/
  useNavigator.ts

frontend/src/types/
  navigator.ts

frontend/src/components/kite/__tests__/
  NavigatorSettingsPanel.test.tsx
  NavigatorEvidencePanel.test.tsx
  ConnectPane.navigator.test.tsx
  SterlingKiteEnginePane.navigator.test.tsx
```

### 4.3 Base-signal contract

Create a broker-neutral immutable model:

```python
class BaseSignalEvidence(BaseModel):
    signal_id: str
    engine_id: Literal["kite_triple_supertrend", "directional"]
    user_id: str
    underlying: str
    exchange: str
    instrument_token: int
    timeframe: str
    bar_open_ms: int
    bar_close_ms: int
    observed_at_ms: int
    direction: Literal["long", "short"]
    state: Literal["fresh", "active"]
    score_100: float
    source: str
    strategy: str
    config_revision: str
    raw_payload_hash: str
```

Validation:

- `0 <= score_100 <= 100`;
- `bar_close_ms <= observed_at_ms`;
- reject an open/incomplete bar;
- `raw_payload_hash` is deterministic canonical JSON;
- adapter errors are explicit and cannot produce a default direction.

Initial adapter:

- `KiteTripleSupertrendAdapter` maps `EngineSignalRow`.

Second adapter, after Phase 0 score cleanup:

- `DirectionalSignalAdapter` maps the current directional result.

---

## 5. Domain Models

### 5.1 Common directional evidence

Every component returns a common shape:

```python
class DirectionalEvidence(BaseModel):
    component: str
    as_of_bar_close_ms: int
    observed_at_ms: int
    direction: Literal[-1, 0, 1]
    confidence_100: float
    quality: Literal["ok", "degraded", "unavailable"]
    reason_codes: list[str]
    diagnostics: dict[str, float | int | str | bool | None]
```

`direction=0` means genuinely neutral. It does not mean missing. Missing uses
`quality="unavailable"`.

### 5.2 Fused result

```python
NavigatorStatus = Literal[
    "NO_DATA",
    "WAIT",
    "CONFLICT",
    "WATCH",
    "CONFIRMED",
    "HIGH_CONVICTION",
]

class NavigatorDecision(BaseModel):
    decision_id: str
    schema_version: int
    config_revision: int
    model_versions: dict[str, str]
    generated_at_ms: int
    bar_close_ms: int
    activation_watermark_ms: int
    base_signal_id: str
    trigger: Literal["base_fresh", "avwap_fresh"]
    direction: Literal["long", "short"]
    status: NavigatorStatus
    base_score: float
    suite_score: float | None
    effective_score: float | None
    execution_eligible: bool
    data_quality: str
    reason_codes: list[str]
    avwap: DirectionalEvidence | None
    volatility: DirectionalEvidence | None
    option_flow: DirectionalEvidence | None
    gamma: DirectionalEvidence | None
```

Rules:

- `decision_id` is deterministic from user, engine, underlying, timeframe, bar
  close, direction, trigger, and config revision.
- Reprocessing identical inputs is idempotent.
- `execution_eligible` defaults to `False`.
- `effective_score=None` for `NO_DATA`.
- Reasons are stable machine codes; UI labels are a separate mapping.
- Persist the model versions and config revision used for every decision.

### 5.3 Data-quality reason codes

Start with this closed enum:

```text
OK
MARKET_CLOSED
CALENDAR_UNKNOWN
AUTH_REQUIRED
UNSUPPORTED_INSTRUMENT
PRICE_BARS_MISSING
PRICE_BAR_OPEN
PRICE_VOLUME_INVALID
CHAIN_UNAVAILABLE
CHAIN_INCOMPLETE
CHAIN_STALE
CHAIN_CLOCK_SKEW
QUOTE_CROSSED
QUOTE_TOO_WIDE
COUNTER_RESET
FLOW_WARMING_UP
IV_MISSING
IV_INVALID
EXPIRY_INVALID
GAMMA_WARMING_UP
CONFIG_INVALID
RATE_LIMITED
COMPONENT_CONFLICT
ACTIVATION_WATERMARK
```

Do not use free-form errors for decision logic.

---

## 6. Configuration Contract

Store one `NavigatorConfigModel` per user in a dedicated versioned record.

### 6.1 Root settings

| Field | Initial value | UI | Rule |
|---|---:|---|---|
| `schema_version` | `1` | hidden | Server-owned. Reject unknown future versions. |
| `enabled` | `false` | toggle | Master switch. Enabling writes `activation_watermark_ms=now`. |
| `operating_mode` | `advisory` | segmented control | `shadow`, `advisory`, or `gate`. Gate is disabled until readiness is true. |
| `engine_sources` | `["kite_triple_supertrend"]` | checkboxes | Directional source appears only after its score contract migration. |
| `underlyings` | supported index defaults | multi-select | Validate against live instrument metadata. |
| `price_timeframe` | `60minute` | read-only in v1 | Must match the Kite base engine initially. Do not imply unsupported timeframe parity. |
| `flow_sample_seconds` | `60` | numeric stepper | `CALIBRATION-REQUIRED`; clamp to a broker-safe range. |
| `max_feature_age_seconds` | `120` | numeric stepper | Hard stale-data limit. |
| `event_alignment_bars` | `2` | numeric stepper | `CALIBRATION-REQUIRED`; applies to fresh base/AVWAP events. |
| `entry_delay_after_open_minutes` | `5` | numeric stepper | `CALIBRATION-REQUIRED`; source walkthrough context. Uses official session open. |
| `retention_raw_days` | `30` | numeric stepper | Raw chain retention; validate available disk budget. |
| `retention_features_days` | `365` | numeric stepper | Feature and signal retention. |

### 6.2 AVWAP settings

These are `STERLING-DESIGNED`; numeric defaults are
`CALIBRATION-REQUIRED`.

| Field | Initial value | Validation |
|---|---:|---|
| `avwap.enabled` | `true` | Required for `gate`. |
| `avwap.pivot_left_bars` | `3` | 1-20 |
| `avwap.pivot_right_bars` | `3` | 1-20 |
| `avwap.slope_lookback_bars` | `5` | 2-50 |
| `avwap.min_slope_atr_per_bar` | `0.02` | 0-2; normalized slope, `CALIBRATION-REQUIRED`. |
| `avwap.atr_period` | `14` | 5-100 |
| `avwap.relative_volume_period` | `20` | 5-200 |
| `avwap.touch_tolerance_atr` | `0.20` | 0.01-1.00 |
| `avwap.min_body_atr` | `0.35` | 0-3 |
| `avwap.min_relative_volume` | `1.20` | 0-10 |
| `avwap.breakout_buffer_atr` | `0.10` | 0-2 |
| `avwap.max_extension_atr` | `1.50` | 0.25-10 |
| `avwap.cooldown_bars` | `5` | 0-100 |
| `avwap.grade_a_plus_min` | `85` | Must be greater than A. |
| `avwap.grade_a_min` | `75` | Must be greater than B. |
| `avwap.grade_b_min` | `65` | 0-100 |
| `avwap.stop_buffer_atr` | `0.15` | 0-3 |
| `avwap.max_stop_distance_atr` | `2.00` | Must exceed stop buffer. |
| `avwap.target_r` | `2.00` | 0.5-10 |
| `avwap.show_session_vwap` | `true` | Display/config only; server still stores required features. |
| `avwap.show_daily_range` | `true` | Display/config only. |
| `avwap.show_weekly_range` | `true` | Display/config only. |

### 6.3 Projected-range settings

| Field | Initial value | Rule |
|---|---:|---|
| `ranges.method` | `rolling_empirical_quantile_v1` | Versioned, not arbitrary user text. |
| `ranges.target_coverage` | `0.80` | `CALIBRATION-REQUIRED`; never display as achieved coverage. |
| `ranges.daily_lookback_sessions` | `120` | Uses completed sessions only. |
| `ranges.daily_min_sessions` | `60` | Below this, daily forecast is unavailable. |
| `ranges.weekly_lookback_periods` | `104` | Uses completed exchange weeks only. |
| `ranges.weekly_min_periods` | `52` | Below this, weekly forecast is unavailable. |
| `ranges.condition_on_volatility` | `true` | Fall back to unconditional only if configured and labeled. |
| `ranges.min_condition_bucket` | `30` | No undersized conditional estimate. |
| `ranges.decay` | `0.98` | `CALIBRATION-REQUIRED`; 0.90-1.00. |
| `ranges.edge_tolerance_atr` | `0.25` | `CALIBRATION-REQUIRED`; classifies near-edge context. |

Range endpoints are always frozen from the session/week open. This is an
invariant, not a toggle.

### 6.4 Volatility settings

| Field | Initial value | Rule |
|---|---:|---|
| `volatility.enabled` | `true` | Required for `gate`. |
| `volatility.atr_period` | `14` | Closed bars only. |
| `volatility.rv_short_bars` | `8` | Must be less than long bars. |
| `volatility.rv_long_bars` | `32` | Must exceed short bars. |
| `volatility.band_period` | `20` | Bollinger-width input. |
| `volatility.band_stddev` | `2.0` | `CALIBRATION-REQUIRED`. |
| `volatility.percentile_lookback` | `120` | Minimum 60. |
| `volatility.gradient_bars` | `5` | 2-50; robust normalized slope window. |
| `volatility.expansion_min` | `65` | `CALIBRATION-REQUIRED`. |
| `volatility.compression_max` | `35` | Must be less than expansion. |
| `volatility.adx_period` | `14` | Transparent trend evidence. |
| `volatility.adx_min` | `18` | `CALIBRATION-REQUIRED`. |
| `volatility.ema_fast_period` | `8` | Must be less than slow period. |
| `volatility.ema_slow_period` | `21` | Must exceed fast period. |
| `volatility.trend_confirm_bars` | `2` | No one-tick flip. |
| `volatility.max_flip_age_bars` | `8` | `CALIBRATION-REQUIRED`; older trend is late. |
| `volatility.min_direction_confidence` | `60` | `CALIBRATION-REQUIRED`. |

Compression forcing `WAIT` is a source-defined invariant in `gate` mode.

### 6.5 Option-flow settings

| Field | Initial value | Rule |
|---|---:|---|
| `flow.enabled` | `true` | Applies only where listed options are supported. |
| `flow.mode` | `dynamic` | `dynamic` or `broad`; source-defined concepts. |
| `flow.dynamic_strike_radius` | `2` | ATM +/- N strikes; `CALIBRATION-REQUIRED`. |
| `flow.broad_strike_radius` | `5` | Must exceed dynamic radius. |
| `flow.expiry_policy` | `nearest_valid` | Resolve from instrument dump, never weekday assumptions. |
| `flow.manual_expiry` | `null` | Optional diagnostic override, validated as listed. |
| `flow.manual_atm` | `null` | Optional diagnostic override; default is automatic spot rounding. |
| `flow.strike_step_override` | `null` | Otherwise derive from listed strikes. |
| `flow.max_quote_age_seconds` | `20` | Hard quality gate. |
| `flow.max_sample_gap_seconds` | `150` | Counter deltas after a larger gap are not comparable. |
| `flow.min_chain_completeness` | `0.80` | `CALIBRATION-REQUIRED`. |
| `flow.max_spread_pct` | `0.08` | Mid-relative; `CALIBRATION-REQUIRED`. |
| `flow.warmup_samples` | `30` | No oscillator before warmup. |
| `flow.robust_window_samples` | `120` | Must exceed warmup. |
| `flow.price_scale_floor` | `0.0001` | Numerical floor for robust option-return scale. |
| `flow.oi_intensity_weight` | `0.25` | `CALIBRATION-REQUIRED`; OI affects intensity, not inferred aggressor side. |
| `flow.z_scale` | `2.0` | `CALIBRATION-REQUIRED`; positive and finite. |
| `flow.zero_hysteresis` | `10` | Prevent zero-line chatter. |
| `flow.strong_zone` | `68` | Source display reference; enforcement requires calibration. |
| `flow.extreme_zone` | `96` | Source display reference; enforcement requires calibration. |
| `flow.require_for_index_gate` | `true` | Missing index flow blocks gate eligibility. |
| `flow.allow_na_for_single_stocks` | `true` | Renormalize with an explicit `NOT_APPLICABLE` reason. |

### 6.6 Gamma-activity settings

| Field | Initial value | Rule |
|---|---:|---|
| `gamma.enabled` | `true` | Confirmation only. |
| `gamma.rate_source` | `manual` | Future providers require a versioned source and timestamp. |
| `gamma.risk_free_rate` | `null` | Required for gamma availability; do not invent a current rate. |
| `gamma.dividend_yield` | `null` | Required unless a validated instrument-specific source exists. |
| `gamma.min_iv` | `0.01` | Reject lower/invalid values. |
| `gamma.max_iv` | `5.00` | Reject implausible feed errors. |
| `gamma.robust_window_samples` | `120` | Same-session or comparable-bucket history. |
| `gamma.min_samples` | `30` | Below this, warming up. |
| `gamma.blast_z_min` | `3.0` | `CALIBRATION-REQUIRED`. |
| `gamma.acceleration_z_min` | `2.0` | `CALIBRATION-REQUIRED`. |
| `gamma.expiry_profile_enabled` | `true` | Separate calibration profile, not a signal by time alone. |
| `gamma.expiry_profile_start_ist` | `14:00` | Source-described context; threshold still calibrated. |
| `gamma.require_flow_alignment` | `true` | Gamma cannot determine direction. |
| `gamma.required_for_gate` | `false` | Optional confirmation by default; missing gamma stays explicit and cannot boost score. |

Contract multiplier and lot size come from current instrument metadata and are
stored with the snapshot. They are not editable free-form defaults.

### 6.7 Expiry-session settings

| Field | Initial value | Rule |
|---|---:|---|
| `expiry_profile.enabled` | `true` | Applies only on the exact listed expiry session. |
| `expiry_profile.require_expansion` | `true` | Source-defined stricter directional alignment. |
| `expiry_profile.min_avwap_grade` | `A` | `CALIBRATION-REQUIRED`; never weaker than general fusion grade. |
| `expiry_profile.min_abs_flow` | `68` | Source reference, `CALIBRATION-REQUIRED` before enforcement. |
| `expiry_profile.max_extension_atr` | `1.00` | `CALIBRATION-REQUIRED`; tighter no-chase limit. |
| `expiry_profile.emit_tighten_note` | `true` | Advisory management reason only; it cannot move a stop. |

Expiry identity comes from the listed contract and official session calendar,
not a weekday rule or integer DTE.

### 6.8 Fusion settings

| Field | Initial value | Rule |
|---|---:|---|
| `fusion.base_weight` | `35` | All weights `CALIBRATION-REQUIRED`; sum must be 100. |
| `fusion.avwap_weight` | `25` | |
| `fusion.volatility_weight` | `20` | |
| `fusion.flow_weight` | `15` | |
| `fusion.gamma_weight` | `5` | |
| `fusion.min_avwap_grade` | `A` | B may display as WATCH but cannot confirm by default. |
| `fusion.strong_conflict_confidence` | `70` | Strong opposite evidence produces CONFLICT. |
| `fusion.confirmed_score_min` | `70` | Advisory until validated. |
| `fusion.high_conviction_score_min` | `85` | Advisory until validated. |
| `fusion.require_fresh_trigger` | `true` | Base or AVWAP must be fresh in the join window. |
| `fusion.require_all_gate_components` | `true` | Expected unavailable evidence fails closed. |

### 6.9 Server-owned settings metadata

The server, not the client, owns:

```text
revision
created_at_ms
updated_at_ms
activation_watermark_ms
calibration_readiness
calibration_report_id
```

Use optimistic concurrency: `PUT /config` must include `expected_revision`. A
stale writer receives HTTP 409 with the current config.

---

## 7. Independent Algorithm Specification

### 7.1 Anchored VWAP structure

**Classification:** `STERLING-DESIGNED`

#### Input

Timezone-aware, sorted, duplicate-free closed candles:

```text
timestamp_ms, open, high, low, close, volume
```

Reject negative prices, non-finite values, `high < max(open, close)`,
`low > min(open, close)`, negative volume, or duplicate timestamps.

#### Typical price and AVWAP

For anchor index `a` and bar `t >= a`:

```text
typical_i = (high_i + low_i + close_i) / 3
avwap(a, t) = sum(typical_i * volume_i, i=a..t)
              / sum(volume_i, i=a..t)
```

If the denominator is zero, evidence is unavailable. Do not substitute close.

#### Confirmed anchors

Use independently confirmed swing pivots:

```text
pivot_high(i):
  high[i] is strictly greater than the left N highs
  and greater than or equal to the right N highs

pivot_low(i):
  low[i] is strictly less than the left N lows
  and less than or equal to the right N lows
```

Tie-breaking must be deterministic: for equal extrema, keep the most recent
candidate only after the right window closes.

A pivot at bar `i` becomes usable only at `i + pivot_right_bars`.

Store both:

```text
anchor_origin_ms = timestamp of bar i
visible_from_ms = close timestamp of bar i + right_bars
```

The AVWAP may include volume from the origin, but the plotted series and signal
logic must begin at `visible_from_ms`. Never backfill the line into bars where
the pivot was not yet knowable.

Maintain the latest confirmed high anchor and latest confirmed low anchor:

```text
high_anchor_vwap = avwap(last_confirmed_high, t)
low_anchor_vwap = avwap(last_confirmed_low, t)
upper = max(high_anchor_vwap, low_anchor_vwap)
lower = min(high_anchor_vwap, low_anchor_vwap)
mid = (upper + lower) / 2
```

Before both anchors exist, use session-open VWAP as display context but mark the
three-level structure `WARMING_UP`; do not manufacture an upper/lower envelope.

#### Session VWAP

Reset at the official exchange session open in `Asia/Kolkata`, not UTC midnight:

```text
session_vwap_t = cumulative(typical * volume) / cumulative(volume)
```

Session identity comes from the versioned exchange calendar.

#### Slopes

Normalize slopes so instruments are comparable:

```text
slope_x = (x[t] - x[t-k]) / max(ATR[t], epsilon) / k
```

Do not use a raw point slope across NIFTY, BANKNIFTY, and stocks.

### 7.2 AVWAP signal families

**Names shown in Sterling:**

| Source concept | Sterling event |
|---|---|
| `P_Buy` | `PULLBACK_LONG` |
| `P_Sell` | `PULLBACK_SHORT` |
| `Buy` | `CONTINUATION_LONG` |
| `Sell` | `CONTINUATION_SHORT` |
| persistent rocket-like event | `IMPULSE_CONTINUATION` |

The renamed impulse event avoids implying formula identity.

#### Bullish structure

All must hold:

```text
close > mid
mid_slope > configured minimum
upper_slope and lower_slope are not strongly negative
structure is fully initialized
```

Bearish structure is the exact sign-reversed condition.

#### Pullback long

All hard conditions:

```text
bullish structure
bar low touches lower/upper/mid value area within touch_tolerance_atr
bar closes back above the touched level
close >= open or lower-wick rejection passes candle-quality check
distance from mid <= max_extension_atr
cooldown is clear
```

Pullback short is the exact mirror.

#### Continuation long

All hard conditions:

```text
bullish structure
prior close <= upper + breakout_buffer
current close > upper + breakout_buffer
body / ATR >= min_body_atr
relative volume >= min_relative_volume
distance from mid <= max_extension_atr
cooldown is clear
```

Continuation short is the exact mirror.

#### Impulse continuation

This event is permitted only when:

- continuation conditions pass;
- volatility regime is `EXPANSION`;
- the bar also closes outside the frozen daily or weekly range;
- grade is A+;
- the event is created from a closed bar;
- its immutable decision has been stored successfully.

Gamma alignment may increase confidence but is not required to define the price
event. A stored impulse event can never disappear; a later invalidation is a new
event.

### 7.3 AVWAP grade

**Classification:** formula `STERLING-DESIGNED`, weights
`CALIBRATION-REQUIRED`.

Score each component from 0 to its cap:

| Component | Cap | Meaning |
|---|---:|---|
| Structure | 25 | Price side, envelope order, normalized slopes |
| Trigger | 20 | Rejection or breakout quality |
| Participation | 15 | Relative volume and usable volume |
| Candle quality | 15 | Body/ATR, close location, wick rejection |
| Extension | 15 | Not chasing too far from value |
| Range context | 10 | Frozen range supports the setup |

```text
grade_score = sum(component_points)
A+ = score >= grade_a_plus_min
A  = score >= grade_a_min
B  = score >= grade_b_min
none = below grade_b_min
```

Persist every component score. Never persist only the letter.

### 7.4 Stop and target proposal

Navigator produces a proposal, not an order:

```text
long_structure_stop = min(trigger_bar_low, lower) - ATR * stop_buffer_atr
short_structure_stop = max(trigger_bar_high, upper) + ATR * stop_buffer_atr
risk_points = abs(entry_reference - structure_stop)
```

Reject the proposal if:

- stop is on the wrong side of entry;
- `risk_points <= tick_size`;
- `risk_points / ATR > max_stop_distance_atr`;
- target or next structure level cannot support configured minimum R.

Initial target:

```text
long_target = entry_reference + target_r * risk_points
short_target = entry_reference - target_r * risk_points
```

Also report the nearest daily/weekly range edge. Do not silently move a target
or widen a stop. Existing Kite position management remains authoritative after
entry.

---

## 8. Projected Daily and Weekly Ranges

**Classification:** `STERLING-DESIGNED`; target and lookbacks
`CALIBRATION-REQUIRED`.

### 8.1 Leakage-free observations

For each completed session:

```text
up_excursion = max(0, (session_high - session_open) / session_open)
down_excursion = max(0, (session_open - session_low) / session_open)
```

For each completed exchange week, use the first session open, weekly high, and
weekly low with the same formulas.

At a new session/week open:

1. Load only observations whose period ended before the current period.
2. Optionally select a volatility bucket using information available at the open.
3. Compute weighted empirical quantiles for upside and downside excursions.
4. Freeze endpoints:

```text
upper = period_open * (1 + q_up)
lower = period_open * (1 - q_down)
```

5. Store model version, sample count, target coverage, and endpoints.
6. Do not move those endpoints until the next period.

### 8.2 Adaptation

After the period closes:

- record whether high/low stayed inside each bound;
- record overshoot and unused width;
- add the completed observation to the rolling estimator;
- update the next period only;
- keep a rolling coverage chart and confidence interval.

Use a weighted empirical quantile in v1. Do not add a machine-learning model
until the simple model has a measured baseline and enough samples.

### 8.3 Range context

Produce one of:

```text
INSIDE_BALANCED
NEAR_UPPER
NEAR_LOWER
BREAK_ABOVE
BREAK_BELOW
REENTERED_FROM_ABOVE
REENTERED_FROM_BELOW
UNAVAILABLE
```

Range context contributes evidence but cannot override compression, stale data,
or a strong base-direction conflict.

---

## 9. Volatility and Direction Model

**Classification:** `STERLING-DESIGNED`; all weights and thresholds
`CALIBRATION-REQUIRED`.

### 9.1 Features

From closed bars:

```text
atr_pct = ATR(14) / close
rv_short = std(log returns, short window) * sqrt(annualization)
rv_long = std(log returns, long window) * sqrt(annualization)
rv_ratio = rv_short / max(rv_long, epsilon)
bandwidth = (upper_band - lower_band) / middle_band
vol_gradient = robust_slope(atr_pct over slope window)
adx, plus_di, minus_di
ema_fast, ema_slow, normalized ema slopes
position_vs_mid_avwap
```

Annualization must use bars per actual exchange year and is diagnostic only; the
regime score relies on rank/ratio values.

### 9.2 Volatility score

Convert inputs to rolling percentile ranks using only prior data:

```text
vol_score =
    0.35 * atr_pct_percentile
  + 0.25 * rv_ratio_percentile
  + 0.20 * bandwidth_percentile
  + 0.20 * gradient_percentile
```

The initial weights are calibration candidates.

```text
EXPANSION:
  vol_score >= expansion_min and vol_gradient > 0

COMPRESSION:
  vol_score <= compression_max and vol_gradient <= 0

NEUTRAL:
  otherwise
```

Use hysteresis of at least two closed bars before changing regime unless the
score crosses an extreme threshold selected during calibration.

### 9.3 Direction and confidence

Direction votes:

```text
trend vote: sign(ema_fast - ema_slow) with normalized slope agreement
directional vote: sign(plus_di - minus_di) when ADX >= adx_min
value vote: sign(close - mid_avwap)
base vote: current base-signal direction
```

Require multi-bar persistence. Calculate transparent confidence from vote
agreement, ADX strength, slope magnitude, regime, and flip age.

Output:

```text
LONG
SHORT
WAIT
```

Hard rules:

- `COMPRESSION -> WAIT`;
- insufficient history -> `WAIT` with `VOL_WARMING_UP`;
- conflicting strong votes -> `WAIT`;
- a directional flip older than `max_flip_age_bars` is marked late and cannot
  create high conviction;
- a weakening gradient lowers confidence and emits a tighten/partial-management
  diagnostic, but it never modifies an existing stop itself.

### 9.4 Deterministic notes

Map stable states to concise server reason codes, for example:

```text
TREND_FORMING_WAIT
BULLISH_EXPANSION
BEARISH_EXPANSION
NO_DIRECTIONAL_EDGE
VOLATILITY_FADING
COMPRESSION_NO_TREND
LATE_AFTER_FLIP
```

The UI may localize labels but must not infer them independently.

---

## 10. Option-Chain Capture

### 10.1 Instrument slice

Do not call the current broad `get_option_chain` for every sample.

Add an indexed method backed by `InstrumentCache`:

```python
async def option_slice(
    exchange: Literal["NFO", "BFO"],
    underlying: str,
    expiry: date,
    spot: float,
    strike_radius: int,
    strike_step_override: float | None = None,
) -> OptionInstrumentSlice:
    ...
```

It must:

- filter exact underlying name, exchange segment, listed expiry, CE/PE;
- derive the strike grid from actual listed contracts;
- select nearest ATM and symmetric strikes where available;
- include token, symbol, strike, side, expiry, lot size, tick size, exchange;
- report expected versus found contracts;
- cache the index until the instrument dump changes;
- support NFO and BFO;
- never infer weekly expiries from a weekday.

### 10.2 Sampling

One account-scoped coordinator owns each `(account, underlying, expiry)` poller.
Multiple enabled user views must not multiply identical broker quote requests.

At each interval:

1. Verify official session state.
2. Resolve spot and current slice.
3. Request quotes in one broker batch.
4. Capture broker exchange timestamp where supplied and local receive timestamp.
5. Validate bid, ask, LTP/mid, OI, cumulative volume, IV, and depth.
6. Compute completeness and staleness.
7. Persist raw snapshot transactionally.
8. Publish the snapshot to the feature service.

Use exponential backoff with jitter for rate limits. Do not retry beyond the next
sampling deadline and do not use the last snapshot as if it were current.

### 10.3 Snapshot fields

Persist at minimum:

```text
account_scope
underlying
spot_token
spot
exchange
expiry
instrument_token
tradingsymbol
option_type
strike
lot_size
tick_size
bid
ask
last_price
mid
implied_volatility
open_interest
cumulative_volume
exchange_timestamp_ms
received_at_ms
sample_bucket_ms
quote_quality
config_revision
```

Never persist access tokens.

### 10.4 Counter rules

Interval values are valid only when:

- prior and current samples are in the same official session;
- instrument token and expiry are unchanged;
- time gap is within the configured limit;
- cumulative volume did not decrease;
- OI and quote values are finite and plausible.

```text
delta_volume = current cumulative volume - previous cumulative volume
delta_oi = current OI - previous OI
```

A session reset, instrument rollover, negative cumulative-volume delta, or large
gap starts a new warmup sequence. Do not clamp a reset to a valid zero delta.

---

## 11. Option-Flow Oscillator

**Classification:** behavior `SOURCE-DEFINED`; formula
`STERLING-DESIGNED`; thresholds `CALIBRATION-REQUIRED`.

### 11.1 Per-contract input

For valid contract `j`:

```text
side_j = +1 for CE, -1 for PE
price_return_j = log(mid_t / mid_previous)
rolling_price_scale_j =
    max(1.4826 * rolling_MAD(price_return_j), price_scale_floor)
price_impulse_j = tanh(price_return_j / rolling_price_scale_j)
volume_intensity_j = log1p(delta_volume_j)
oi_intensity_j = log1p(abs(delta_oi_j))
normalized_oi_intensity_j =
    prior-window percentile rank of oi_intensity_j in [0, 1]
proximity_weight_j = exp(-abs(strike - ATM) / strike_scale)
liquidity_weight_j = clamp(1 - spread_pct / max_spread_pct, 0, 1)
```

Do not claim that OI and price reveal aggressor identity. They do not reliably
distinguish option buying from writing without trade-side data.

Use OI only as activity/confirmation intensity:

```text
activity_j =
    side_j
  * price_impulse_j
  * volume_intensity_j
  * (1 + oi_weight * normalized_oi_intensity_j)
  * proximity_weight_j
  * liquidity_weight_j
```

Aggregate calls and puts separately for diagnostics, then sum valid contracts.

### 11.2 Robust normalization

On a rolling window:

```text
center = median(raw_activity)
scale = 1.4826 * median(abs(raw_activity - center))
robust_z = (raw_activity - center) / max(scale, epsilon)
oscillator = 100 * tanh(robust_z / z_scale)
```

The oscillator is bounded `[-100, 100]`.

Use zero-line hysteresis:

```text
bullish only after oscillator >= +hysteresis
bearish only after oscillator <= -hysteresis
retain prior state inside the band for display, but lower confidence
```

`+/-68` and `+/-96` may be displayed as source reference zones. They cannot gate
orders until Sterling's empirical distribution and outcomes validate them.

### 11.3 Dynamic and broad modes

- `dynamic`: ATM-centered, smaller radius, exponential proximity weighting,
  nearest valid expiry; preferred initial intraday mode.
- `broad`: larger symmetric radius and slower normalization; retained for
  comparison, not silently mixed with dynamic history.

Store the mode in each feature snapshot. Changing mode starts a new warmup and
model-version series.

### 11.4 Divergence

Divergence is optional advisory evidence:

- use confirmed price pivots and confirmed oscillator pivots;
- apply the same right-bar confirmation/no-backfill rule as AVWAP;
- require minimum separation and oscillator magnitude;
- never label an unconfirmed current extremum as divergence;
- divergence may downgrade continuation but cannot reverse direction alone.

---

## 12. Gamma Activity

**Classification:** behavior `SOURCE-DEFINED`; formula
`STERLING-DESIGNED`; thresholds `CALIBRATION-REQUIRED`.

### 12.1 Time to expiry

Resolve exact exchange expiry close from instrument and calendar metadata.

```text
seconds_to_expiry = expiry_close_utc - quote_timestamp_utc
T = seconds_to_expiry / (365.0 * 24 * 60 * 60)
```

Require `T > 0`. On expiry day, `T` remains positive until the configured exchange
close. Never use integer calendar-day DTE.

### 12.2 Greeks

Use quote IV only if valid and fresh. Compute Black-Scholes gamma with spot,
strike, `T`, risk-free rate, dividend yield, and IV.

If any required input is unavailable:

- gamma evidence is unavailable;
- the option-flow oscillator may continue if its own inputs are valid;
- gamma is never set to zero as a substitute.

### 12.3 Activity measures

This is **gross gamma activity**, not dealer gamma exposure:

```text
gamma_notional_j =
    abs(gamma_j)
  * spot^2
  * 0.01
  * lot_size_j
  * delta_volume_j

gross_gamma_activity = sum(gamma_notional_j)

signed_gamma_activity =
    sum(sign(price-flow contribution_j) * gamma_notional_j)
```

Normalize gross activity and its first difference with robust rolling statistics:

```text
level_z = robust_z(gross_gamma_activity)
acceleration_z = robust_z(diff(gross_gamma_activity))
```

Gamma event:

```text
level_z >= blast_z_min
and acceleration_z >= acceleration_z_min
and chain quality is OK
and sample history is sufficient
```

Direction comes only from aligned, valid option-flow and price evidence.

### 12.4 Expiry profile

Maintain separate baselines for:

```text
non_expiry
expiry_before_14_ist
expiry_after_14_ist
```

The clock chooses the comparison profile; it does not create a gamma event.
Promotion requires enough samples in each profile. If a profile is undersampled,
return `GAMMA_WARMING_UP`.

---

## 13. Fusion and Signal Generation

### 13.1 Event-time join

At scan start, capture:

```text
config_revision
activation_watermark_ms
scan_as_of_ms
expected base bar close
```

All evidence must have:

- `as_of_bar_close_ms <= scan_as_of_ms`;
- no open price bar;
- option sample timestamp no later than the decision timestamp;
- age within its component limit;
- matching underlying, exchange mapping, expiry policy, and config revision.

If configuration changes during a scan, discard the old-revision fused result
and rescan. Do not publish a mixed-revision decision.

### 13.2 Trigger rule

A new fused entry event needs:

```text
(fresh base signal and aligned initialized AVWAP structure)
or
(fresh AVWAP signal and active base direction within event_alignment_bars)
```

This allows Navigator to generate a new confirmation while an existing
SuperTrend direction remains active, without permitting AVWAP, flow, or gamma to
trade independently.

Deduplicate by decision ID.

### 13.3 Hard-gate truth table

| Condition | Status | Execution eligible |
|---|---|---|
| Required input unavailable/stale | `NO_DATA` | No |
| Activation watermark excludes trigger | `WAIT` | No |
| Volatility is compression | `WAIT` | No |
| No fresh base or AVWAP trigger | `WATCH` | No |
| Strong AVWAP or volatility direction opposes base | `CONFLICT` | No |
| Flow strongly opposes base | `CONFLICT` | No |
| Base and AVWAP align; other required evidence neutral/usable | `CONFIRMED` if score passes | Only in validated gate mode |
| Base, A+ AVWAP, directional expansion, aligned flow, and optional gamma/range impulse agree | `HIGH_CONVICTION` if score passes | Only in validated gate mode |

Gamma disagreement cannot create `CONFLICT` by itself; it is an activity
confirmation layer.

### 13.4 Score calculation

For each available component, convert direction relative to the base:

```text
relative = +1 aligned, 0 neutral, -1 opposed
component_score = 50 * (1 + relative * confidence_100 / 100)
```

Thus:

- fully aligned at confidence 100 -> 100;
- neutral -> 50;
- fully opposed at confidence 100 -> 0.

The base component score is its normalized `score_100`.

```text
effective_score =
  weighted_mean(
    base_score,
    avwap_component_score,
    volatility_component_score,
    flow_component_score,
    gamma_component_score,
  )
```

Rules:

- `suite_score` is the weighted mean excluding base.
- Weights are the configured fusion weights.
- Do not renormalize away a required missing component; return `NO_DATA`.
- If optional gamma is unavailable, retain its weight at neutral score 50 and add
  `GAMMA_UNAVAILABLE_OPTIONAL`; absence must neither help nor block a setup.
- For a genuinely non-applicable component, such as option flow on an allowed
  single stock without suitable chain support, omit and renormalize only when the
  config explicitly permits it. Add reason `COMPONENT_NOT_APPLICABLE`.
- Apply hard conflicts before score thresholds. A high base score cannot average
  away strong opposite evidence.
- Keep raw `EngineSignalRow.score` unchanged. Add `base_score`,
  `suite_score`, and `effective_score`.

### 13.5 Execution eligibility

Set `execution_eligible=True` only when all are true:

```text
navigator.enabled
navigator.operating_mode == "gate"
calibration_readiness == "ready"
decision config revision is current
status in {"CONFIRMED", "HIGH_CONVICTION"}
effective_score >= configured threshold
all required data-quality checks pass
trigger is newer than activation watermark
base signal remains active/fresh
```

This boolean is only one input to the existing central order gate. It does not
replace any current Sterling check.

---

## 14. Persistence and Migrations

Add idempotent schema creation in `backend/app/services/db.py`, following current
SQLite conventions. Use explicit indexes and bounded retention.

### 14.1 `navigator_configs`

```text
user_id TEXT PRIMARY KEY
schema_version INTEGER NOT NULL
revision INTEGER NOT NULL
payload_json TEXT NOT NULL
activation_watermark_ms INTEGER NOT NULL
calibration_readiness TEXT NOT NULL
calibration_report_id TEXT
created_at_ms INTEGER NOT NULL
updated_at_ms INTEGER NOT NULL
```

### 14.2 `navigator_config_audit`

```text
id INTEGER PRIMARY KEY
user_id TEXT NOT NULL
revision INTEGER NOT NULL
changed_at_ms INTEGER NOT NULL
previous_hash TEXT
new_hash TEXT NOT NULL
payload_json TEXT NOT NULL
```

### 14.3 `navigator_option_snapshots`

Use one row per contract per sample. Include all fields in Section 10.3.

Required uniqueness:

```text
(account_scope, instrument_token, sample_bucket_ms)
```

Required indexes:

```text
(account_scope, underlying, expiry, sample_bucket_ms)
(instrument_token, sample_bucket_ms)
```

### 14.4 `navigator_feature_snapshots`

```text
id INTEGER PRIMARY KEY
user_id TEXT NOT NULL
underlying TEXT NOT NULL
timeframe TEXT NOT NULL
bar_close_ms INTEGER NOT NULL
observed_at_ms INTEGER NOT NULL
config_revision INTEGER NOT NULL
model_versions_json TEXT NOT NULL
quality TEXT NOT NULL
avwap_json TEXT
range_json TEXT
volatility_json TEXT
flow_json TEXT
gamma_json TEXT
input_hash TEXT NOT NULL
```

Unique:

```text
(user_id, underlying, timeframe, bar_close_ms, config_revision, input_hash)
```

### 14.5 `navigator_signal_events`

Store the complete immutable `NavigatorDecision` JSON plus indexed columns:

```text
decision_id TEXT PRIMARY KEY
user_id TEXT NOT NULL
underlying TEXT NOT NULL
bar_close_ms INTEGER NOT NULL
generated_at_ms INTEGER NOT NULL
direction TEXT NOT NULL
status TEXT NOT NULL
effective_score REAL
execution_eligible INTEGER NOT NULL
config_revision INTEGER NOT NULL
payload_json TEXT NOT NULL
```

### 14.6 `navigator_calibration_state`

Store model version, instrument/timeframe cohort, train window, validation window,
sample count, metrics JSON, artifact hash, and promotion state.

### 14.7 Retention

- Delete raw option snapshots only after their derived feature snapshot exists.
- Run retention in small indexed batches.
- Keep immutable signal events and calibration reports longer than raw quotes.
- Report row counts, oldest timestamp, database bytes, and last cleanup result.
- Never run unbounded deletes on the request thread.

---

## 15. API Contract

Create `backend/app/api/v1/endpoints/navigator.py`:

```python
router = APIRouter(prefix="/kite/navigator", tags=["kite-navigator"])
```

Every route uses `Depends(get_current_user)`. Market-data routes acquire the
active Kite client with the same authenticated account rules as the engine.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/kite/navigator/config` | Current config, revision, readiness, and server capabilities |
| `PUT` | `/api/v1/kite/navigator/config` | Validate and atomically save with expected revision |
| `POST` | `/api/v1/kite/navigator/config/validate` | Dry-run validation; no state change |
| `POST` | `/api/v1/kite/navigator/config/reset` | Restore defaults, remaining disabled |
| `GET` | `/api/v1/kite/navigator/status` | Sampler health, warmups, data ages, last decision, storage |
| `GET` | `/api/v1/kite/navigator/snapshot/{underlying}` | Latest server-calculated evidence |
| `GET` | `/api/v1/kite/navigator/series/{underlying}` | Paginated/downsampled chart series |
| `GET` | `/api/v1/kite/navigator/signals` | Cursor-paginated immutable signal history |
| `GET` | `/api/v1/kite/navigator/signals/{decision_id}` | Full evidence and reason trace |
| `GET` | `/api/v1/kite/navigator/calibration` | Current metrics and promotion status |

### API error behavior

Use typed errors:

```text
400 INVALID_CONFIG
401/403 existing auth behavior
409 REVISION_CONFLICT or NO_ACTIVE_KITE_ACCOUNT
422 UNSUPPORTED_UNDERLYING / EXPIRY_NOT_LISTED
423 GATE_NOT_CALIBRATED
429 BROKER_RATE_LIMITED
502 BROKER_DATA_ERROR
503 NAVIGATOR_WARMING_UP
```

Do not return HTTP 200 with a silently discarded config write.

Register the router in `backend/main.py`. Start and stop the sampler through the
application lifecycle; no orphan `asyncio.create_task` calls.

---

## 16. Scanner and Order-Path Integration

### 16.1 Scanner

In `backend/app/services/kite_engine/scanner.py`:

1. Produce the existing raw signal exactly as before.
2. Adapt it to `BaseSignalEvidence`.
3. Ask Navigator service for a feature snapshot at the signal's event time.
4. Fuse using the config revision captured at scan start.
5. Attach `NavigatorDecision` to the row.
6. Flush the row as the current scanner does.

Do not issue option-chain requests from each scanned row. The independent sampler
provides cached, timestamped evidence.

For rows with Navigator disabled:

```text
navigator = null
```

For enabled but warming/stale rows, attach a `NO_DATA` or `WAIT` decision with
reasons; do not hide the original raw signal.

### 16.2 Schema compatibility

Extend `EngineSignalRow` with:

```python
navigator: NavigatorDecision | None = None
```

Do not change:

```text
source="spot" | "derivatives" | "confluence"
score
is_active
is_fresh
```

Old cached rows must still deserialize.

### 16.3 Central execution gate

Apply Navigator eligibility immediately before the existing auto-execution
submission callback, in one central location:

```text
if navigator is enabled and mode is gate:
    require current decision.execution_eligible
then run every existing risk/order gate
```

The central path must re-read current config revision before submission. A
disable/config change between scan and order blocks the order.

Never:

- place from `NavigatorDecision` directly;
- bypass engine `auto_execute`;
- convert advisory mode to an order;
- auto-enable gate mode;
- auto-close a position when Navigator is disabled;
- change an already-open position's original hard stop.

---

## 17. Settings and User Experience

## 17.1 Dedicated Settings section

Modify `frontend/src/components/kite/ConnectPane.tsx`:

```ts
type ConnectSection =
  | 'account'
  | 'engine'
  | 'navigator'
  | 'orderSelection'
  | 'markets'
  | 'notifications'
  | 'experience';
```

Add:

```ts
{
  id: 'navigator',
  label: 'Value-Flow Navigator',
  eyebrow: 'AVWAP, volatility & options flow',
}
```

Render:

```tsx
<NavigatorSettingsPanel />
```

The Navigator config must not be copied into the existing engine form.

### 17.2 Settings layout

Top band:

- enabled toggle;
- mode segmented control: Shadow / Advisory / Gate;
- readiness status;
- current config revision;
- save state/error.

Sections:

1. Instruments and timing
2. Anchored VWAP and signal grades
3. Daily and weekly ranges
4. Volatility regime
5. Option-flow oscillator
6. Gamma activity
7. Fusion and eligibility
8. Data retention and diagnostics

Use:

- toggles for binary options;
- segmented controls for mode choices;
- selects for enumerations;
- numeric inputs/steppers for exact thresholds;
- sliders only when an exact accompanying numeric value is visible;
- color swatches only for chart-series colors;
- tooltips for unfamiliar status icons.

Add `lucide-react` because no icon library is currently installed. Use Lucide
icons for reset, health, warning, history, and expand/collapse actions. Do not add
hand-drawn SVG controls.

Keep groups as unframed full-width bands separated by borders. Do not nest cards.
Use at most 8px radius. Advanced numeric groups may collapse, but all active
values must be reachable in this one section.

### 17.3 Save behavior

- Load server config and revision.
- Keep a local draft.
- Validate locally for immediate field feedback.
- Call server `/config/validate` before save.
- Save atomically with expected revision.
- On 409, preserve the local draft and show a reload/compare action.
- On failure, do not show "saved".
- Reset requires confirmation and returns `enabled=false`.
- Enabling displays the new activation time.
- Gate selection is disabled with the readiness reason until promoted.

Do not autosave every keystroke; option polling and safety settings require an
intentional Apply action.

### 17.4 Signal table

Modify `SterlingKiteEnginePane.tsx`:

- retain the raw `score`;
- show Navigator status and `effective_score` as separate fields;
- add a compact evidence breakdown in the detail panel;
- make `NO_DATA`, `WAIT`, and `CONFLICT` reasons inspectable;
- never reduce a failure to a green/red dot with no explanation;
- show an explicit stale age when relevant;
- label source `spot`, `derivatives`, or existing `confluence` unchanged.

The signal table row background remains white by default and uses the existing
light grey only on hover. Navigator state must not reintroduce a permanent grey
row fill.

### 17.5 Chart

Extend the server setup/series response with:

- high-anchor AVWAP;
- low-anchor AVWAP;
- Upper, Mid, Lower;
- session VWAP;
- frozen daily range;
- frozen weekly range;
- immutable signal markers;
- oscillator, strong/extreme zones, gamma events, and volatility regime.

Display price overlays on the price chart and flow/volatility in a separate pane.
Do not recompute them from browser candles.

### 17.6 Responsive and accessibility

- Settings rail remains horizontally scrollable on narrow screens.
- Long labels wrap; no clipped threshold inputs.
- Every input has a programmatic label and error association.
- Toggle and segmented states are keyboard accessible.
- Status is conveyed by text/icon as well as color.
- Chart toggles have stable dimensions.
- Test at 360px, 768px, and 1280px widths.

---

## 18. Observability and Operations

### 18.1 Structured logs

Log with user/account identifiers hashed or internal, never credentials:

```text
navigator.config.saved
navigator.sampler.started
navigator.sampler.stopped
navigator.chain.sampled
navigator.chain.rejected
navigator.feature.computed
navigator.decision.emitted
navigator.decision.blocked
navigator.retention.completed
navigator.calibration.promoted
```

Include config revision, model version, underlying, event timestamp, latency,
quality, and reason codes.

### 18.2 Metrics

At minimum:

```text
quote request count/latency/error/rate-limit
chain completeness
quote stale ratio
sample gap/reset count
sampler lag
feature computation latency
decisions by status/direction/grade
effective-score distribution
NO_DATA reasons
daily/weekly empirical coverage
gamma events by expiry profile
database rows/bytes/retention lag
```

### 18.3 Health behavior

Status must distinguish:

```text
DISABLED
STARTING
WARMING_UP
HEALTHY
DEGRADED
STALE
ERROR
```

An API process restart rehydrates configuration, last valid snapshots, warmup
state, and activation watermark. It does not mark old evidence current.

### 18.4 Resource controls

- batch quote requests;
- cap underlyings and strikes per user;
- share account-scoped pollers;
- apply bounded queues and backpressure;
- skip, rather than queue, a sample whose deadline has passed;
- move CPU-heavy replay/calibration off the request loop;
- enforce retention and disk-watermark alerts.

---

## 19. Backtest, Forward Test, and Calibration

## 19.1 Honest data boundary

Historical candle data can evaluate:

- AVWAP anchor behavior;
- pullback/continuation logic;
- projected ranges;
- volatility regimes;
- price-only fusion ablations.

It cannot honestly evaluate the specified option-flow or gamma model without
historical contract snapshots containing quotes, OI, cumulative volume, IV, and
timestamps. Synthetic options may be used only in unit tests and clearly labeled
scenario tests, never as empirical flow performance.

### 19.2 Replay engine

Build deterministic replay around an injected clock:

```text
input snapshots -> feature snapshots -> fusion decisions
```

Requirements:

- same inputs/config/model versions produce byte-equivalent decisions;
- replay reveals no data after each event timestamp;
- exact session calendar is used;
- outputs include skipped/no-data events;
- baseline and candidate model versions can run side by side.

### 19.3 Validation sequence

1. Run price-only walk-forward tests over multiple market regimes.
2. Enable raw chain capture in shadow mode.
3. Capture at least 20 trading sessions before the first advisory flow report.
4. Include multiple expiry and non-expiry sessions; do not use only one expiry.
5. Split chronologically into calibration and untouched evaluation windows.
6. Freeze thresholds before the evaluation window.
7. Compare with the unchanged Sterling base engine.
8. Run component ablations:
   - base only;
   - base + AVWAP;
   - base + AVWAP + volatility;
   - plus flow;
   - plus gamma.
9. Publish a versioned report with hashes and sample counts.

Twenty sessions is a minimum capture checkpoint, not proof of generalization.
Gate-mode promotion should require substantially more evidence across regimes.

### 19.4 Metrics

Report:

```text
signal count and coverage
precision by status and score bucket
expectancy in R
median and tail MAE/MFE
win/loss size distribution
maximum drawdown
turnover
estimated spread/slippage
calibration curve and Brier score
daily/weekly range coverage and interval width
data-unavailable rate
expiry versus non-expiry results
latency from observation to decision
```

Do not optimize only hit rate.

### 19.5 Promotion gate

`calibration_readiness="ready"` requires:

- predefined minimum sample sizes;
- all mandatory data-quality tests passing;
- no lookahead/repainting finding;
- stable out-of-sample behavior versus base;
- acceptable no-data and stale-data rates;
- no material expectancy degradation after conservative costs;
- reviewed calibration report ID stored in config;
- explicit user action to choose `gate`.

Promotion never turns on `auto_execute`.

---

## 20. Test Specification

## 20.1 AVWAP unit tests

- known hand-calculated anchored VWAP;
- high/low anchors use only confirmed pivots;
- no line before `visible_from_ms`;
- equal-high/equal-low tie behavior;
- anchor replacement begins only after confirmation;
- zero-volume denominator returns unavailable;
- session VWAP resets at the official IST session;
- holiday/weekend does not create a session;
- input validation rejects malformed candles;
- long/short signal symmetry;
- cooldown and max-extension behavior;
- grade component sum and boundaries;
- emitted impulse event remains immutable.

### 20.2 Range tests

- current session excluded from estimator;
- current week excluded;
- frozen endpoints do not move intraday;
- quantile matches hand fixture;
- conditional bucket fallback is labeled;
- insufficient samples return unavailable;
- exchange-holiday week groups correctly;
- adaptation changes only the next period;
- coverage metric uses completed periods.

### 20.3 Volatility tests

- all feature formulas against fixed arrays;
- no percentile leakage from current/future values;
- expansion/compression hysteresis;
- compression always returns WAIT;
- trend confirmation and flip age;
- zero/constant returns are finite;
- score remains in 0-100;
- deterministic reason codes.

### 20.4 Option-flow tests

- ATM and symmetric strike selection;
- NFO and BFO slices;
- listed-expiry resolution;
- dynamic versus broad mode;
- cumulative-volume delta;
- OI delta;
- session counter reset;
- instrument rollover;
- large sample gap;
- crossed/wide/stale quote rejection;
- incomplete chain fail-closed;
- robust median/MAD normalization;
- zero-MAD handling;
- oscillator bounded to [-100, 100];
- zero hysteresis;
- confirmed divergence has no lookahead.

### 20.5 Gamma tests

- fractional same-day time to expiry;
- exact zero/negative T rejection;
- known Black-Scholes gamma fixture;
- invalid/missing IV is unavailable, not zero;
- lot size and scale units;
- gross activity nonnegative;
- signed activity cannot supply direction without flow;
- robust level and acceleration thresholds;
- expiry-profile selection;
- after-14:00 profile alone cannot fire;
- undersampled profile returns warming up.

### 20.6 Fusion tests

- every row of the hard-gate truth table;
- base fresh plus aligned structure;
- AVWAP fresh plus active base;
- neither fresh -> WATCH;
- strong opposite evidence -> CONFLICT regardless of average score;
- missing required flow -> NO_DATA;
- allowed non-applicable flow renormalization;
- gamma cannot create/reverse direction;
- stale event-time join rejected;
- activation watermark;
- config revision race;
- deterministic decision ID;
- idempotent replay;
- effective score formula and bounds;
- gate eligibility cannot become true in shadow/advisory.

### 20.7 Persistence/API tests

- schema upgrade from an existing Sterling DB;
- create/read/update/reset config;
- optimistic revision conflict;
- write failure preserves prior config and returns error;
- settings remain disabled after restart/reset;
- user A cannot read user B config/signals;
- raw snapshot uniqueness and indexes;
- immutable decision insert;
- cursor pagination;
- retention preserves derived/event records;
- auth/no-active-account/rate-limit error mapping;
- sampler startup/shutdown has no leaked task.

### 20.8 Existing engine integration tests

- Navigator disabled produces byte-compatible raw signal behavior;
- existing `source="confluence"` remains unchanged;
- old rows without `navigator` deserialize;
- enabled advisory attaches a decision but cannot order;
- validated gate still runs every existing order/risk guard;
- disabling between scan and order blocks submission;
- disabling does not stop open-position protection;
- scanner does not make per-row chain calls;
- directional adapter rejects ambiguous legacy score scale.

### 20.9 Frontend tests

- dedicated Settings rail item and panel;
- master toggle and activation watermark response;
- all config groups render;
- invalid cross-field values block Apply;
- dry-run/server errors remain visible;
- revision conflict preserves draft;
- reset returns disabled defaults;
- gate disabled until ready;
- status/warmup/stale/no-data states;
- signal raw and effective scores remain distinct;
- existing confluence label remains;
- white default signal rows and grey hover;
- detail evidence and reason codes;
- chart series toggles;
- keyboard and accessible labels;
- 360px layout has no overlap or clipped input.

### 20.10 Property tests

- long/short mirrored input produces mirrored output;
- scores always stay in range;
- long stop is below entry and short stop above entry;
- increasing aligned confidence cannot lower effective score, absent a hard gate;
- adding strong opposing evidence cannot increase status;
- future input changes cannot alter a prior decision;
- duplicate replay cannot create duplicate events.

### 20.11 Commands

Backend focused:

```bash
cd backend
PYTHONWARNINGS=ignore pytest tests/engines/navigator tests/services/navigator tests/api/test_navigator.py -v
```

Existing Kite regressions:

```bash
cd backend
PYTHONWARNINGS=ignore pytest tests/engines/sterling_kite_engine -v
```

Frontend focused:

```bash
cd frontend
npm test -- --run Navigator ConnectPane SterlingKiteEnginePane
npm run build
```

Before completion, run the repository's broader backend and frontend suites
appropriate to the changed files. Record unrelated pre-existing failures
separately; do not suppress them.

---

## 21. Phased Implementation Checklist

## Phase 0 - Contracts and safety prerequisites

**Files likely changed:**

- `backend/app/schemas/directional.py`
- `backend/app/engines/directional/signal_engine.py`
- directional execution adapter/callers
- focused directional tests

- [ ] Inventory every base score producer and consumer.
- [ ] Introduce explicit `score_100` adapters.
- [ ] Test and remove ambiguous implicit scaling.
- [ ] Define `BaseSignalEvidence`.
- [ ] Implement and test the Kite adapter.
- [ ] Implement the directional adapter only after its score contract is clean.
- [ ] Freeze existing `source="confluence"` semantics in regression tests.
- [ ] Confirm Navigator-disabled behavior before any feature integration.

**Exit gate:** Every base signal has an explicit 0-100 score and event timestamp;
no execution path guesses the scale.

## Phase 1 - Configuration, schemas, and persistence

**Create:**

- `backend/app/engines/navigator/schemas.py`
- `backend/app/services/navigator/config_store.py`
- `backend/app/services/navigator/repository.py`

**Modify:**

- `backend/app/services/db.py`

- [ ] Write Pydantic config and decision models.
- [ ] Add cross-field validators.
- [ ] Add tables, uniqueness constraints, and indexes.
- [ ] Implement transaction-safe config save with revision checking.
- [ ] Implement activation watermark semantics.
- [ ] Add immutable event insertion and feature/snapshot repositories.
- [ ] Add bounded retention queries.
- [ ] Test migration against a copy of a populated development DB.

**Exit gate:** Restart-safe config and immutable events work; a failed write is
visible and cannot mutate active state.

## Phase 2 - Price feature engine

**Create:**

- `backend/app/engines/navigator/quality.py`
- `backend/app/engines/navigator/avwap.py`
- `backend/app/engines/navigator/projected_ranges.py`
- `backend/app/engines/navigator/volatility.py`

- [ ] Implement strict candle validation.
- [ ] Implement confirmed pivots and no-backfill AVWAP.
- [ ] Implement Upper/Mid/Lower and IST session VWAP.
- [ ] Implement pullback, continuation, impulse, grade, cooldown, stop, target.
- [ ] Implement frozen rolling-quantile daily/weekly ranges.
- [ ] Implement volatility features, regimes, direction, confidence, notes.
- [ ] Add model version constants.
- [ ] Add deterministic unit, property, and no-lookahead tests.

**Exit gate:** Price features can replay deterministically using only data known at
each bar close.

## Phase 3 - Calendar, instrument slice, and chain capture

**Create:**

- `backend/app/services/navigator/calendar.py`
- `backend/app/services/navigator/instrument_slice.py`
- `backend/app/services/navigator/chain_sampler.py`

**Modify as needed:**

- `backend/app/services/exchanges/kite/instruments.py`
- `backend/app/services/exchanges/kite/client.py`

- [ ] Add a versioned NSE/BSE session-calendar provider.
- [ ] Require an authoritative holiday dataset for every enabled year; unknown
      calendar fails closed.
- [ ] Index option instruments by exchange/underlying/expiry/strike/type.
- [ ] Resolve automatic ATM and exact listed expiry.
- [ ] Batch narrow quotes.
- [ ] Persist raw snapshots with exchange and receive timestamps.
- [ ] Implement reset/gap/completeness/staleness rules.
- [ ] Share account-scoped samplers and add lifecycle cancellation.
- [ ] Add rate-limit backoff, backpressure, and health.
- [ ] Verify quote-call volume against the broker's current documented limits
      before selecting the production poll interval.

**Exit gate:** Shadow capture runs for a full session without stale reuse,
unbounded tasks, duplicate snapshots, or rate-limit thrashing.

## Phase 4 - Flow, gamma, and fusion

**Create:**

- `backend/app/engines/navigator/option_flow.py`
- `backend/app/engines/navigator/gamma_activity.py`
- `backend/app/engines/navigator/fusion.py`
- `backend/app/services/navigator/adapters.py`

- [ ] Implement interval flow and robust normalization.
- [ ] Implement dynamic and broad model versions.
- [ ] Implement optional confirmed divergence.
- [ ] Implement fractional-time gamma and activity profiles.
- [ ] Implement hard-gate truth table.
- [ ] Implement score, reason, and idempotent decision ID.
- [ ] Persist every emitted decision.
- [ ] Add complete truth-table and property tests.

**Exit gate:** Captured fixtures replay to deterministic, explainable decisions;
gamma cannot independently create direction.

## Phase 5 - Runtime and API

**Create:**

- `backend/app/services/navigator/service.py`
- `backend/app/services/navigator/status.py`
- `backend/app/api/v1/endpoints/navigator.py`

**Modify:**

- `backend/main.py`
- `backend/app/engines/sterling_kite_engine/schemas.py`
- `backend/app/services/kite_engine/scanner.py`
- `backend/app/services/kite_engine/service.py`

- [ ] Implement config/status/snapshot/series/history/calibration endpoints.
- [ ] Register router and application lifecycle.
- [ ] Join Navigator evidence to raw scanner rows.
- [ ] Preserve raw signal fields and current confluence.
- [ ] Implement central gate-mode eligibility check.
- [ ] Recheck revision immediately before order submission.
- [ ] Test enable, disable, restart, stale data, and config-race behavior.

**Exit gate:** Advisory decisions appear without changing orders; gate mode is
server-blocked until readiness.

## Phase 6 - Settings, signal detail, and charts

**Create:**

- `frontend/src/types/navigator.ts`
- `frontend/src/hooks/useNavigator.ts`
- `frontend/src/components/kite/NavigatorSettingsPanel.tsx`
- `frontend/src/components/kite/NavigatorStatusStrip.tsx`
- `frontend/src/components/kite/NavigatorEvidencePanel.tsx`

**Modify:**

- `frontend/package.json`
- lockfile
- `frontend/src/components/kite/ConnectPane.tsx`
- `frontend/src/components/kite/SterlingKiteEnginePane.tsx`
- `frontend/src/components/charts/TradingViewKiteChart.tsx`
- `frontend/src/types/kiteEngine.ts`

- [ ] Add `lucide-react`.
- [ ] Add dedicated Settings rail section.
- [ ] Implement draft, validation, revision conflict, Apply, and Reset.
- [ ] Implement health/readiness display.
- [ ] Add separate raw/suite/effective score presentation.
- [ ] Add evidence detail with stable reasons.
- [ ] Add backend series overlays and oscillator pane.
- [ ] Preserve white rows and grey hover.
- [ ] Add accessibility and responsive tests.
- [ ] Verify desktop/mobile with Playwright screenshots and inspect for overlap.

**Exit gate:** A user can configure every related setting, understand unavailable
evidence, and enable advisory fusion without entering another settings section.

## Phase 7 - Replay, observability, and retention

- [ ] Add deterministic replay CLI/service.
- [ ] Add structured logs and metrics.
- [ ] Add data-health dashboard fields.
- [ ] Add retention job and disk-watermark health.
- [ ] Add calibration report artifact and promotion record.
- [ ] Add operational runbook for auth expiry, rate limits, stale quotes, DB
      growth, and calendar rollover.

**Exit gate:** Operators can distinguish no signal from no data and reproduce any
decision from stored inputs/config/model versions.

## Phase 8 - Controlled rollout

- [ ] Deploy with feature available but disabled.
- [ ] Enable internal shadow capture.
- [ ] Complete one-session technical soak.
- [ ] Capture minimum forward-test dataset.
- [ ] Run frozen walk-forward and ablation report.
- [ ] Review threshold stability and execution-cost sensitivity.
- [ ] Promote advisory mode.
- [ ] Continue forward evaluation across multiple regimes/expiries.
- [ ] Mark calibration ready only after all promotion criteria pass.
- [ ] Test gate in paper trading.
- [ ] Require a separate explicit decision before any live use.

---

## 22. External Facts the Implementer Must Verify

These are deliberately not guessed in this plan:

1. Current Zerodha quote endpoint request and rate limits.
2. Official NSE/BSE trading holidays and special sessions for each enabled year.
3. Exact listed expiry timestamp and any early-close behavior.
4. Current instrument-specific risk-free and dividend-yield source, or the
   approved manual values and effective date.
5. Whether Kite quote timestamps are exchange timestamps for every required field.
6. Storage growth from the selected universe, strike radius, and poll interval.

Record each verified source, effective date, and resulting config/model version.
If any fact cannot be verified, the affected component remains unavailable.

---

## 23. Explicit Do-Not-Do List

- Do not call this an exact QuantGym/AutoAVWAP/Volquant clone.
- Do not reverse engineer proprietary code.
- Do not invent hidden formulas.
- Do not treat the video's range-coverage claim as measured Sterling performance.
- Do not backfill an anchor before pivot confirmation.
- Do not use open bars for entry decisions.
- Do not let a signal marker disappear.
- Do not update a frozen daily/weekly range intraperiod.
- Do not use UTC midnight as the Indian cash-session VWAP reset.
- Do not use integer DTE for expiry-day gamma.
- Do not infer option aggressor identity from OI and volume.
- Do not call gross gamma activity dealer GEX.
- Do not reuse `gex_engine.py` thresholds.
- Do not turn missing IV/gamma into zero.
- Do not reuse a stale chain after an API error.
- Do not poll a broad 400-contract chain per signal row.
- Do not overload `source="confluence"`.
- Do not overwrite the raw base score.
- Do not renormalize away a required missing component.
- Do not let gamma create direction.
- Do not add a new direct order endpoint for Navigator.
- Do not auto-enable execution or gate mode.
- Do not silently swallow config persistence errors.
- Do not force a disabled setting back on after restart.
- Do not report a historical option-flow backtest without captured historical
  option snapshots.
- Do not promote thresholds on the same window used to choose them.
- Do not merge unrelated refactors into this implementation.

---

## 24. Final Acceptance Criteria

### Source fidelity

- [ ] Every source-defined behavior in Section 1 is represented.
- [ ] Every undisclosed formula is labeled as Sterling-designed.
- [ ] Every unvalidated threshold is labeled calibration-required.
- [ ] No parity/performance claim exceeds the available evidence.

### Functional behavior

- [ ] Navigator has a separate Settings section and master enable/disable.
- [ ] Enabling advisory mode combines current Sterling direction with Navigator
      evidence and emits fused signals.
- [ ] Raw Sterling signals remain visible and unchanged.
- [ ] Base-fresh and AVWAP-fresh trigger paths both work.
- [ ] Shadow, advisory, and gate modes behave exactly as defined.
- [ ] Disable/restart/config-race behavior is deterministic.

### Algorithm integrity

- [ ] Closed bars only.
- [ ] Confirmed pivots only.
- [ ] No backfill/repainting.
- [ ] Frozen projected ranges.
- [ ] Compression forces WAIT.
- [ ] Stale/incomplete data fails closed.
- [ ] Gamma cannot determine direction.
- [ ] Scores and reason traces are reproducible.

### Execution safety

- [ ] Default off.
- [ ] Gate unavailable before calibration readiness.
- [ ] Navigator cannot bypass any existing order/risk control.
- [ ] Revision and activation watermark are rechecked before order submission.
- [ ] Disabling Navigator does not impair open-position protection.

### Data and operations

- [ ] Narrow chain capture supports NFO and BFO.
- [ ] Exact listed expiry and fractional TTE.
- [ ] Snapshots, features, events, config, and model versions are persisted.
- [ ] Retention is bounded and observable.
- [ ] Health distinguishes no edge from no data.
- [ ] Any decision can be replayed from stored evidence.

### User experience

- [ ] All related configs are present in one Navigator section.
- [ ] Save, failure, conflict, reset, warmup, stale, and readiness states are clear.
- [ ] Raw, suite, and effective scores are distinct.
- [ ] Signal rows remain white at rest and grey on hover.
- [ ] No mobile/desktop overlap or clipping.
- [ ] Controls are keyboard accessible and labeled.

### Validation

- [ ] Unit, property, integration, API, and frontend tests pass.
- [ ] Existing Kite engine regression suite passes.
- [ ] Historical price-only results are labeled correctly.
- [ ] Option-flow/gamma conclusions use captured forward data.
- [ ] A versioned out-of-sample and ablation report exists before gate promotion.

---

## 25. Completion Report Required from the Implementing AI

At the end of each phase, report:

```text
Phase:
Files changed:
Tests added:
Commands run and results:
Source-defined requirements covered:
Sterling-designed choices introduced:
Calibration-required values introduced:
Known limitations:
Next gate:
```

At final completion, include:

- config schema and revision;
- model-version map;
- database migration result;
- sampler quote budget;
- data-health snapshot;
- test summary;
- Playwright desktop/mobile evidence;
- calibration readiness (expected to remain not ready until forward testing);
- explicit confirmation that no execution control was bypassed.

An implementation is not complete merely because the indicators render. It is
complete only when the data lineage, non-repainting behavior, failure states,
fusion logic, settings, persistence, safety checks, tests, and operational
controls all satisfy this contract.
