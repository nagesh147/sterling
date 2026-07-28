// Full default-value tree for NavigatorConfigModel, mirrored exactly from the
// Python defaults in backend/app/engines/navigator/schemas.py — the single
// source of truth. Used purely for the settings panel's "Default: X" /
// "changed — revert" affordance on every field; never sent to the server on
// its own (the server always returns its own authoritative config/revision).
//
// Keep this in sync with schemas.py by hand — there is no shared codegen
// between the two today. Fields the UI already renders read-only (schema
// version, engine_sources, price_timeframe, the fixed method/rate_source/
// expiry_policy literals, underlyings) are omitted; they have no meaningful
// "default vs. changed" state to show.

export const AVWAP_DEFAULTS = {
  enabled: true,
  pivot_left_bars: 3,
  pivot_right_bars: 3,
  slope_lookback_bars: 5,
  min_slope_atr_per_bar: 0.02,
  atr_period: 14,
  relative_volume_period: 20,
  touch_tolerance_atr: 0.20,
  min_body_atr: 0.35,
  min_relative_volume: 1.20,
  breakout_buffer_atr: 0.10,
  max_extension_atr: 1.50,
  cooldown_bars: 5,
  grade_a_plus_min: 85.0,
  grade_a_min: 75.0,
  grade_b_min: 65.0,
  stop_buffer_atr: 0.15,
  max_stop_distance_atr: 2.00,
  target_r: 2.00,
  show_session_vwap: true,
  show_daily_range: true,
  show_weekly_range: true,
} as const;

export const RANGES_DEFAULTS = {
  target_coverage: 0.80,
  daily_lookback_sessions: 120,
  daily_min_sessions: 60,
  weekly_lookback_periods: 104,
  weekly_min_periods: 52,
  condition_on_volatility: true,
  min_condition_bucket: 30,
  decay: 0.98,
  edge_tolerance_atr: 0.25,
} as const;

export const VOLATILITY_DEFAULTS = {
  enabled: true,
  atr_period: 14,
  rv_short_bars: 8,
  rv_long_bars: 32,
  band_period: 20,
  band_stddev: 2.0,
  percentile_lookback: 120,
  gradient_bars: 5,
  expansion_min: 65.0,
  compression_max: 35.0,
  adx_period: 14,
  adx_min: 18.0,
  ema_fast_period: 8,
  ema_slow_period: 21,
  trend_confirm_bars: 2,
  max_flip_age_bars: 8,
  min_direction_confidence: 60.0,
} as const;

export const FLOW_DEFAULTS = {
  enabled: true,
  mode: 'dynamic' as const,
  dynamic_strike_radius: 2,
  broad_strike_radius: 5,
  max_quote_age_seconds: 20,
  max_sample_gap_seconds: 150,
  min_chain_completeness: 0.80,
  max_spread_pct: 0.08,
  warmup_samples: 30,
  robust_window_samples: 120,
  oi_intensity_weight: 0.25,
  z_scale: 2.0,
  zero_hysteresis: 10.0,
  strong_zone: 68.0,
  extreme_zone: 96.0,
  require_for_index_gate: true,
  allow_na_for_single_stocks: true,
} as const;

export const GAMMA_DEFAULTS = {
  enabled: true,
  min_iv: 0.01,
  max_iv: 5.00,
  robust_window_samples: 120,
  min_samples: 30,
  blast_z_min: 3.0,
  acceleration_z_min: 2.0,
  expiry_profile_enabled: true,
  expiry_profile_start_ist: '14:00',
  require_flow_alignment: true,
  required_for_gate: false,
} as const;

export const FUSION_DEFAULTS = {
  base_weight: 35.0,
  avwap_weight: 25.0,
  volatility_weight: 20.0,
  flow_weight: 15.0,
  gamma_weight: 5.0,
  min_avwap_grade: 'A' as const,
  strong_conflict_confidence: 70.0,
  confirmed_score_min: 70.0,
  high_conviction_score_min: 85.0,
  require_fresh_trigger: true,
  require_all_gate_components: true,
} as const;

export const ROOT_DEFAULTS = {
  flow_sample_seconds: 60,
  max_feature_age_seconds: 120,
  event_alignment_bars: 2,
  entry_delay_after_open_minutes: 5,
  retention_raw_days: 30,
  retention_features_days: 365,
  structure_radar_enabled: false,
  signal_origination: 'off' as const,
  auto_execute_originated: false,
} as const;
