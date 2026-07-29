// Sterling Value-Flow Navigator types — mirrors
// backend/app/engines/navigator/schemas.py exactly. Kite-only build:
// `engine_sources` is fixed to a single value; there is no
// directional/crypto config surface here or on the server.

export type NavigatorOperatingMode = 'shadow' | 'advisory' | 'gate';
export type SignalOrigination = 'off' | 'heads_up' | 'full';
export type NavigatorScanScopeMode = 'shared' | 'custom';
export type NavigatorStatus = 'NO_DATA' | 'WAIT' | 'CONFLICT' | 'WATCH' | 'CONFIRMED' | 'HIGH_CONVICTION';
export type NavigatorComponent = 'avwap' | 'ranges' | 'volatility' | 'option_flow' | 'gamma';
export type AvwapGrade = 'A+' | 'A' | 'B';
export type CalibrationReadiness = 'not_ready' | 'ready';

export interface AvwapConfig {
  enabled: boolean;
  pivot_left_bars: number;
  pivot_right_bars: number;
  slope_lookback_bars: number;
  min_slope_atr_per_bar: number;
  atr_period: number;
  relative_volume_period: number;
  touch_tolerance_atr: number;
  min_body_atr: number;
  min_relative_volume: number;
  breakout_buffer_atr: number;
  max_extension_atr: number;
  cooldown_bars: number;
  grade_a_plus_min: number;
  grade_a_min: number;
  grade_b_min: number;
  stop_buffer_atr: number;
  max_stop_distance_atr: number;
  target_r: number;
  show_session_vwap: boolean;
  show_daily_range: boolean;
  show_weekly_range: boolean;
}

export interface RangesConfig {
  method: 'rolling_empirical_quantile_v1';
  target_coverage: number;
  daily_lookback_sessions: number;
  daily_min_sessions: number;
  weekly_lookback_periods: number;
  weekly_min_periods: number;
  condition_on_volatility: boolean;
  min_condition_bucket: number;
  decay: number;
  edge_tolerance_atr: number;
}

export interface VolatilityConfig {
  enabled: boolean;
  atr_period: number;
  rv_short_bars: number;
  rv_long_bars: number;
  band_period: number;
  band_stddev: number;
  percentile_lookback: number;
  gradient_bars: number;
  expansion_min: number;
  compression_max: number;
  adx_period: number;
  adx_min: number;
  ema_fast_period: number;
  ema_slow_period: number;
  trend_confirm_bars: number;
  max_flip_age_bars: number;
  min_direction_confidence: number;
}

export interface FlowConfig {
  enabled: boolean;
  mode: 'dynamic' | 'broad';
  dynamic_strike_radius: number;
  broad_strike_radius: number;
  expiry_policy: 'nearest_valid';
  manual_expiry: string | null;
  manual_atm: number | null;
  strike_step_override: number | null;
  max_quote_age_seconds: number;
  max_sample_gap_seconds: number;
  min_chain_completeness: number;
  max_spread_pct: number;
  warmup_samples: number;
  robust_window_samples: number;
  price_scale_floor: number;
  oi_intensity_weight: number;
  z_scale: number;
  zero_hysteresis: number;
  strong_zone: number;
  extreme_zone: number;
  require_for_index_gate: boolean;
  allow_na_for_single_stocks: boolean;
}

export interface GammaConfig {
  enabled: boolean;
  rate_source: 'manual';
  risk_free_rate: number | null;
  dividend_yield: number | null;
  min_iv: number;
  max_iv: number;
  robust_window_samples: number;
  min_samples: number;
  blast_z_min: number;
  acceleration_z_min: number;
  expiry_profile_enabled: boolean;
  expiry_profile_start_ist: string;
  require_flow_alignment: boolean;
  required_for_gate: boolean;
}

export interface ExpiryProfileConfig {
  enabled: boolean;
  require_expansion: boolean;
  min_avwap_grade: AvwapGrade;
  min_abs_flow: number;
  max_extension_atr: number;
  emit_tighten_note: boolean;
}

export interface FusionConfig {
  base_weight: number;
  avwap_weight: number;
  volatility_weight: number;
  flow_weight: number;
  gamma_weight: number;
  min_avwap_grade: AvwapGrade;
  strong_conflict_confidence: number;
  confirmed_score_min: number;
  high_conviction_score_min: number;
  require_fresh_trigger: boolean;
  require_all_gate_components: boolean;
}

export interface NavigatorConfigModel {
  schema_version: number;
  enabled: boolean;
  operating_mode: NavigatorOperatingMode;
  engine_sources: ['kite_triple_supertrend'];
  /** DEPRECATED — no longer read by any scan path; see scan_scope_mode. */
  underlyings: string[];
  // ── Scan scope: shared with the Kite engine, or Navigator's own ─────────
  // "shared" (default) = Navigator covers exactly what the Kite engine
  // covers. "custom" = Navigator resolves its own universe from the four
  // fields below, which are read ONLY in custom mode.
  scan_scope_mode: NavigatorScanScopeMode;
  scan_indices: string[];
  scan_stocks: string[];
  scan_all_stocks: boolean;
  scan_source: 'spot' | 'derivatives' | 'both' | 'confluence';
  // ── Structure Radar / Signal Origination (additive, all off by default) ──
  // See docs/superpowers/specs/2026-07-28-navigator-structure-radar-origination-design.md.
  structure_radar_enabled: boolean;
  signal_origination: SignalOrigination;
  auto_execute_originated: boolean;
  price_timeframe: '60minute';
  flow_sample_seconds: number;
  max_feature_age_seconds: number;
  event_alignment_bars: number;
  entry_delay_after_open_minutes: number;
  retention_raw_days: number;
  retention_features_days: number;
  avwap: AvwapConfig;
  ranges: RangesConfig;
  volatility: VolatilityConfig;
  flow: FlowConfig;
  gamma: GammaConfig;
  expiry_profile: ExpiryProfileConfig;
  fusion: FusionConfig;
}

export interface NavigatorConfigRecord {
  user_id: string;
  config: NavigatorConfigModel;
  revision: number;
  activation_watermark_ms: number;
  calibration_readiness: CalibrationReadiness;
  calibration_report_id: string | null;
  created_at_ms: number;
  updated_at_ms: number;
}

export interface NavigatorConfigResponse {
  record: NavigatorConfigRecord;
  capabilities: {
    engine_sources: string[];
    price_timeframe: string;
    schema_version: number;
  };
}

export interface DirectionalEvidence {
  component: NavigatorComponent;
  as_of_bar_close_ms: number;
  observed_at_ms: number;
  direction: -1 | 0 | 1;
  confidence_100: number;
  quality: 'ok' | 'degraded' | 'unavailable';
  reason_codes: string[];
  diagnostics: Record<string, number | string | boolean | null>;
}

export interface NavigatorDecision {
  decision_id: string;
  schema_version: number;
  config_revision: number;
  model_versions: Record<string, string>;
  generated_at_ms: number;
  bar_close_ms: number;
  activation_watermark_ms: number;
  base_signal_id: string;
  trigger: 'base_fresh' | 'avwap_fresh';
  direction: 'long' | 'short';
  status: NavigatorStatus;
  base_score: number;
  suite_score: number | null;
  effective_score: number | null;
  execution_eligible: boolean;
  data_quality: string;
  reason_codes: string[];
  avwap: DirectionalEvidence | null;
  volatility: DirectionalEvidence | null;
  option_flow: DirectionalEvidence | null;
  gamma: DirectionalEvidence | null;
}

export type NavigatorHealth = 'DISABLED' | 'STARTING' | 'WARMING_UP' | 'HEALTHY' | 'DEGRADED' | 'STALE' | 'ERROR';

export interface NavigatorComponentStatus {
  name: string;
  quality: 'ok' | 'degraded' | 'unavailable';
  last_updated_ms: number | null;
  reason_codes: string[];
}

export interface NavigatorStatusResponse {
  health: NavigatorHealth;
  enabled: boolean;
  operating_mode: NavigatorOperatingMode;
  calibration_readiness: CalibrationReadiness;
  config_revision: number;
  activation_watermark_ms: number;
  components: NavigatorComponentStatus[];
  last_decision_at_ms: number | null;
  sampler_running: boolean;
  scanning: boolean;
  scanning_label: string;
  last_scan_ms: number;
  next_scan_ms: number;
  signal_count: number;
  scan_source: 'spot' | 'derivatives' | 'both' | 'confluence';
  failures: Array<{ underlying: string; error: string }>;
  auto_scan: boolean;
}

export interface NavigatorActivityResponse {
  events: Array<{ ts_ms: number; kind: string; message: string }>;
  scanning: boolean;
  scanning_label: string;
  last_scan_ms: number;
  next_scan_ms: number;
  signal_count: number;
  auto_scan: boolean;
  failures: Array<{ underlying: string; error: string }>;
}

export interface NavigatorScanResponse {
  generated_ms: number;
  scanning: boolean;
  scanning_label: string;
  rows: unknown[];
  next_scan_ms: number;
  auto_scan: boolean;
  cancelled?: boolean;
}

export interface NavigatorSignalsPage {
  decisions: string[]; // each entry is a JSON-encoded NavigatorDecision
  next_cursor: { generated_at_ms: number; decision_id: string } | null;
}

export interface NavigatorSeriesResponse {
  underlying: string;
  points: Array<Record<string, unknown>>;
}

export interface CalibrationCriterion {
  key: string;
  label: string;
  passed: boolean;
  /** Human-readable progress, e.g. "12 of 20 sessions" — not just a verdict. */
  detail: string;
}

export interface CalibrationCriteria {
  /** True = a human MAY now promote. Never means anything was promoted. */
  eligible: boolean;
  criteria: CalibrationCriterion[];
}

export interface CalibrationWindow {
  label: string;
  sessions: number;
  session_dates: string[];
  total_decisions: number;
  actionable: number;
  actionable_scored: number;
  actionable_hits: number;
  hit_rate: number | null;
  mean_return_pct: number | null;
  no_data: number;
  no_data_rate: number | null;
  unscorable: number;
}

export interface CalibrationReport {
  model_version: string;
  horizon_bars: number;
  total_decisions: number;
  underlyings: string[];
  /** Honest limits of this report — e.g. returns are gross of costs. */
  caveats: string[];
  /** Something went wrong producing this report (e.g. no price history could
   *  be fetched), so the numbers below understate reality. Empty when clean. */
  warnings?: string[];
  coverage?: {
    decision_underlyings: string[];
    priced: string[];
    unresolved: string[];
    fetch_failed: string[];
  };
  calibration: CalibrationWindow;
  evaluation: CalibrationWindow;
}

export interface NavigatorCalibrationResponse {
  calibration_readiness: CalibrationReadiness;
  calibration_report_id: string | null;
  revision: number;
  latest_report: Record<string, unknown> | null;
  criteria: CalibrationCriteria | null;
}

export interface CalibrationReportResponse {
  report_id: string;
  report: CalibrationReport;
  criteria: CalibrationCriteria;
  calibration_readiness: CalibrationReadiness;
}
