import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { NavigatorSettingsPanel } from '../NavigatorSettingsPanel';
import type { NavigatorConfigModel } from '../../../types/navigator';

function makeConfig(overrides: Partial<NavigatorConfigModel> = {}): NavigatorConfigModel {
  return {
    schema_version: 1, enabled: false, operating_mode: 'advisory', engine_sources: ['kite_triple_supertrend'],
    underlyings: ['NIFTY 50'],
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

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: queryData, isLoading: !queryData, error: null }),
  useSetNavigatorConfig: () => ({ mutate: setConfig, isPending: false, isError: false, error: null }),
  useResetNavigatorConfig: () => ({ mutate: resetConfig }),
  useValidateNavigatorConfig: () => ({ mutate: vi.fn() }),
  useNavigatorStatus: () => ({ data: undefined }),
}));

describe('NavigatorSettingsPanel', () => {
  beforeEach(() => {
    setConfig.mockClear();
    resetConfig.mockClear();
    queryData = makeRecord();
  });

  it('loads server config disabled by default and shows the master toggle off', () => {
    render(<NavigatorSettingsPanel />);
    const toggle = screen.getByRole('switch', { name: 'Enable Navigator' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByText('Saved')).toBeInTheDocument();
  });

  it('does not autosave — toggling shows Unsaved changes and requires Apply', () => {
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('switch', { name: 'Enable Navigator' }));
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    expect(setConfig).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
    expect(setConfig).toHaveBeenCalledTimes(1);
    const [body] = setConfig.mock.calls[0];
    expect(body.expected_revision).toBe(1);
    expect(body.config.enabled).toBe(true);
  });

  it('gate mode is locked until calibration is ready', () => {
    render(<NavigatorSettingsPanel />);
    expect(screen.getByRole('button', { name: /Gate \(locked\)/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Gate \(locked\)/i }));
    // still locked — no Apply-enabling change occurred
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument();
  });

  it('gate mode is selectable once calibration is ready', () => {
    queryData = makeRecord({}, { calibration_readiness: 'ready' });
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: /^Gate$/i }));
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  });

  it('reset requires a confirmation click before firing', () => {
    render(<NavigatorSettingsPanel />);
    const resetBtn = screen.getByRole('button', { name: /Reset to defaults/i });
    fireEvent.click(resetBtn);
    expect(resetConfig).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Click again to confirm reset/i }));
    expect(resetConfig).toHaveBeenCalledTimes(1);
  });

  it('renders every settings section', () => {
    render(<NavigatorSettingsPanel />);
    for (const title of [
      'Instruments and timing', 'Structure Radar and Signal Origination', 'Anchored VWAP and signal grades',
      'Daily and weekly ranges', 'Volatility regime', 'Option-flow oscillator', 'Gamma activity',
      'Fusion and eligibility', 'Data retention and diagnostics',
    ]) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  describe('Structure Radar and Signal Origination', () => {
    it('signal origination defaults to Off and explains today\'s unchanged behaviour', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByRole('button', { name: /^Off$/i })).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByText(/Navigator only ever evaluates a setup that the SuperTrend engine already triggered/)).toBeInTheDocument();
    });

    it('switching to Full updates the explanation and unlocks Apply', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      expect(screen.getByText(/becomes a real, tradeable setup/)).toBeInTheDocument();
      expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    });

    it('auto-execute originated is locked until Full is selected', () => {
      render(<NavigatorSettingsPanel />);
      const toggle = screen.getByRole('switch', { name: 'Auto-Execute Originated' });
      expect(toggle).toHaveAttribute('aria-checked', 'false');
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'false'); // still locked — Full not selected yet
    });

    it('auto-execute originated is locked until calibration is ready even when Full is selected', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      const toggle = screen.getByRole('switch', { name: 'Auto-Execute Originated' });
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'false'); // calibration_readiness is 'not_ready' by default
    });

    it('auto-execute originated is togglable once Full is selected and calibration is ready', () => {
      queryData = makeRecord({}, { calibration_readiness: 'ready' });
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      const toggle = screen.getByRole('switch', { name: 'Auto-Execute Originated' });
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });

    it('switching origination away from Full clears auto-execute originated', () => {
      queryData = makeRecord({}, { calibration_readiness: 'ready' });
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      fireEvent.click(screen.getByRole('switch', { name: 'Auto-Execute Originated' }));
      expect(screen.getByRole('switch', { name: 'Auto-Execute Originated' })).toHaveAttribute('aria-checked', 'true');
      fireEvent.click(screen.getByRole('button', { name: /^Heads-up$/i }));
      expect(screen.getByRole('switch', { name: 'Auto-Execute Originated' })).toHaveAttribute('aria-checked', 'false');
    });

    it('structure radar toggles independently of signal origination', () => {
      render(<NavigatorSettingsPanel />);
      const toggle = screen.getByRole('switch', { name: 'Structure Radar' });
      expect(toggle).toHaveAttribute('aria-checked', 'false');
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'true');
      expect(screen.getByRole('button', { name: /^Off$/i })).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('Strategy Definition (from the source manual)', () => {
    it('renders the section with all six manual-anchored fields at their default, no revert buttons shown', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByText('Strategy Definition (from the source manual)')).toBeInTheDocument();
      expect(screen.getByText('6/6 at manual default')).toBeInTheDocument();
      expect(screen.getAllByText(/Manual default:/).length).toBe(6);
      expect(screen.queryByRole('button', { name: /changed — revert/i })).not.toBeInTheDocument();
    });

    it('shows the two always-on hardcoded manual rules', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByText('Compression always forces WAIT')).toBeInTheDocument();
      expect(screen.getByText('Gamma never sets direction by itself')).toBeInTheDocument();
    });

    it('changing a manual-anchored field shows a revert button and updates the at-default count', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      expect(screen.getByText('5/6 at manual default')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /changed — revert/i })).toBeInTheDocument();
    });

    it('clicking revert restores that field to the manual default and clears the revert button', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      fireEvent.click(screen.getByRole('button', { name: /changed — revert/i }));
      expect(strongZoneInput.value).toBe('68');
      expect(screen.getByText('6/6 at manual default')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /changed — revert/i })).not.toBeInTheDocument();
    });

    it('reverting one field does not touch another changed field', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      const extremeZoneInput = screen.getByLabelText('Extreme flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      fireEvent.change(extremeZoneInput, { target: { value: '99' } });
      expect(screen.getByText('4/6 at manual default')).toBeInTheDocument();
      fireEvent.click(screen.getAllByRole('button', { name: /changed — revert/i })[0]);
      expect(extremeZoneInput.value).toBe('99'); // untouched
      expect(screen.getByText('5/6 at manual default')).toBeInTheDocument();
    });

    it('the old sections point to the moved fields instead of duplicating an editable control', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getAllByText(/Moved to Strategy Definition/).length).toBeGreaterThanOrEqual(4);
    });
  });

  it('shows raw and effective concepts distinctly via fusion weight fields', () => {
    render(<NavigatorSettingsPanel />);
    expect(screen.getByText('Base weight')).toBeInTheDocument();
    expect(screen.getByText('AVWAP weight')).toBeInTheDocument();
  });
});
