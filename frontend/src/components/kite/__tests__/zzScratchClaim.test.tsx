import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { NavigatorSettingsPanel } from '../NavigatorSettingsPanel';
import type { NavigatorConfigModel } from '../../../types/navigator';

function makeConfig(overrides: Partial<NavigatorConfigModel> = {}): NavigatorConfigModel {
  return {
    schema_version: 1, enabled: false, operating_mode: 'advisory', engine_sources: ['kite_triple_supertrend'],
    underlyings: ['NIFTY 50'],
    scan_scope_mode: 'shared', scan_indices: [], scan_stocks: [], scan_all_stocks: false, scan_source: 'spot',
    structure_radar_enabled: false, signal_origination: 'off', auto_execute_originated: false,
    price_timeframe: '60minute', flow_sample_seconds: 60, max_feature_age_seconds: 120,
    event_alignment_bars: 2, entry_delay_after_open_minutes: 5, retention_raw_days: 30, retention_features_days: 365,
    avwap: {
      enabled: true, pivot_left_bars: 3, pivot_right_bars: 3, slope_lookback_bars: 5, min_slope_atr_per_bar: 0.02,
      atr_period: 14, relative_volume_period: 20, touch_tolerance_atr: 0.2, min_body_atr: 0.35, min_relative_volume: 1.2,
      breakout_buffer_atr: 0.1, max_extension_atr: 1.5, cooldown_bars: 5, grade_a_plus_min: 85, grade_a_min: 75,
      grade_b_min: 65, stop_buffer_atr: 0.15, max_stop_distance_atr: 2.0, target_r: 2.0,
      show_session_vwap: true, show_daily_range: true, show_weekly_range: true,
    },
    ranges: {
      method: 'rolling_empirical_quantile_v1', target_coverage: 0.8, daily_lookback_sessions: 120, daily_min_sessions: 60,
      weekly_lookback_periods: 104, weekly_min_periods: 52, condition_on_volatility: true, min_condition_bucket: 30,
      decay: 0.98, edge_tolerance_atr: 0.25,
    },
    volatility: {
      enabled: true, atr_period: 14, rv_short_bars: 8, rv_long_bars: 32, band_period: 20, band_stddev: 2.0,
      percentile_lookback: 120, gradient_bars: 5, expansion_min: 65, compression_max: 35, adx_period: 14, adx_min: 18,
      ema_fast_period: 8, ema_slow_period: 21, trend_confirm_bars: 2, max_flip_age_bars: 8, min_direction_confidence: 60,
    },
    flow: {
      enabled: true, mode: 'dynamic', dynamic_strike_radius: 2, broad_strike_radius: 5, expiry_policy: 'nearest_valid',
      manual_expiry: null, manual_atm: null, strike_step_override: null, max_quote_age_seconds: 20, max_sample_gap_seconds: 150,
      min_chain_completeness: 0.8, max_spread_pct: 0.08, warmup_samples: 30, robust_window_samples: 120,
      price_scale_floor: 0.0001, oi_intensity_weight: 0.25, z_scale: 2.0, zero_hysteresis: 10, strong_zone: 68,
      extreme_zone: 96, require_for_index_gate: true, allow_na_for_single_stocks: true,
    },
    gamma: {
      enabled: true, rate_source: 'manual', risk_free_rate: null, dividend_yield: null, min_iv: 0.01, max_iv: 5.0,
      robust_window_samples: 120, min_samples: 30, blast_z_min: 3.0, acceleration_z_min: 2.0,
      expiry_profile_enabled: true, expiry_profile_start_ist: '14:00', require_flow_alignment: true, required_for_gate: false,
    },
    expiry_profile: {
      enabled: true, require_expansion: true, min_avwap_grade: 'A', min_abs_flow: 68, max_extension_atr: 1.0, emit_tighten_note: true,
    },
    fusion: {
      base_weight: 35, avwap_weight: 25, volatility_weight: 20, flow_weight: 15, gamma_weight: 5,
      min_avwap_grade: 'A', strong_conflict_confidence: 70, confirmed_score_min: 70, high_conviction_score_min: 85,
      require_fresh_trigger: true, require_all_gate_components: true,
    },
    ...overrides,
  };
}

function makeRecord(cfgOverrides: Partial<NavigatorConfigModel> = {}, recordOverrides: Record<string, unknown> = {}) {
  return {
    record: {
      user_id: 'user-1', config: makeConfig(cfgOverrides), revision: 1, activation_watermark_ms: 0,
      calibration_readiness: 'not_ready', calibration_report_id: null, created_at_ms: 1, updated_at_ms: 1,
      ...recordOverrides,
    },
    capabilities: { engine_sources: ['kite_triple_supertrend'], price_timeframe: '60minute', schema_version: 1 },
  };
}

const setConfig = vi.fn();
const resetConfig = vi.fn();
let queryData: ReturnType<typeof makeRecord> | undefined;
let engineCfg: Record<string, unknown>;

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: engineCfg }),
  useStockRegistry: () => ({
    data: [{ liquidity: 'Very High', stocks: [{ name: 'RELIANCE' }, { name: 'TCS' }] }],
  }),
}));

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: queryData, isLoading: !queryData, error: null }),
  useSetNavigatorConfig: () => ({ mutate: setConfig, isPending: false, isError: false, error: null }),
  useResetNavigatorConfig: () => ({ mutate: resetConfig }),
  useValidateNavigatorConfig: () => ({ mutate: vi.fn() }),
  useNavigatorStatus: () => ({ data: undefined }),
}));

describe('CLAIM: Instruments -> Own overwrites Navigator chart source with SuperTrend s', () => {
  beforeEach(() => {
    setConfig.mockClear();
    resetConfig.mockClear();
    queryData = makeRecord();
    engineCfg = {
      scan_indices: ['NIFTY 50', 'NIFTY BANK'],
      scan_stocks: [],
      scan_all_stocks: false,
      scan_source: 'spot',
      scan_stock_contracts: true,
    };
  });

  it('A: engine=derivatives, nav=spot(default) -> click Own -> saved scan_source', () => {
    engineCfg = { ...engineCfg, scan_source: 'derivatives' };
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
    const [body] = setConfig.mock.calls[0];
    // eslint-disable-next-line no-console
    console.log('CASE A saved scan_source =', body.config.scan_source);
    expect(body.config.scan_source).toBe('spot');
  });

  it('B: user explicitly picks Derivatives, engine=spot -> click Own -> saved scan_source', () => {
    render(<NavigatorSettingsPanel />);
    const derivRadio = screen.getAllByRole('radio').find((r) => (r as HTMLInputElement)
      .closest('label')?.textContent?.startsWith('Derivatives'))!;
    fireEvent.click(derivRadio);
    // sanity: the pick registered
    expect((derivRadio as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
    // eslint-disable-next-line no-console
    console.log('CASE B radio after Own click, checked =', (screen.getAllByRole('radio').find((r) => (r as HTMLInputElement).closest('label')?.textContent?.startsWith('Derivatives')) as HTMLInputElement).checked);
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
    const [body] = setConfig.mock.calls[0];
    // eslint-disable-next-line no-console
    console.log('CASE B saved scan_source =', body.config.scan_source);
    expect(body.config.scan_source).toBe('derivatives');
  });

  it('C: nav already has a custom universe -> Own is guarded (control)', () => {
    engineCfg = { ...engineCfg, scan_source: 'derivatives' };
    queryData = makeRecord({ scan_scope_mode: 'shared', scan_indices: ['NIFTY 50'], scan_source: 'spot' });
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
    const [body] = setConfig.mock.calls[0];
    // eslint-disable-next-line no-console
    console.log('CASE C saved scan_source =', body.config.scan_source);
    expect(body.config.scan_source).toBe('spot');
  });
});
