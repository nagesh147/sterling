import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
      extreme_zone: 96, require_for_index_gate: true,
    },
    gamma: {
      enabled: true, rate_source: 'manual', risk_free_rate: null, dividend_yield: null, min_iv: 0.01, max_iv: 5.0,
      robust_window_samples: 120, min_samples: 30, blast_z_min: 3.0, acceleration_z_min: 2.0,
      expiry_profile_start_ist: '14:00', require_flow_alignment: true, required_for_gate: false,
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

// The panel reads the engine's own config (to show what a SHARED scan scope
// currently covers) and the stock registry (to populate a CUSTOM scope's
// picker). Both are React Query hooks; mock them so this suite keeps
// rendering the panel bare, without a QueryClientProvider.
vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: engineCfg }),
  useStockRegistry: () => ({
    data: [{ liquidity: 'Very High', stocks: [{ name: 'RELIANCE' }, { name: 'TCS' }] }],
  }),
}));

// Retrying after a revision conflict has to re-read the revision the server holds
// now, so the panel calls refetch(). It resolves with whatever `queryData` is at
// that moment, which is how a test moves the server on underneath the draft.
const refetchConfig = vi.fn(async () => ({ data: queryData }));

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({
    data: queryData, isLoading: !queryData, error: null, refetch: refetchConfig,
  }),
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
    engineCfg = {
      scan_indices: ['NIFTY 50', 'NIFTY BANK'],
      scan_stocks: [],
      scan_all_stocks: false,
      scan_source: 'spot',
      scan_stock_contracts: true,
    };
  });

  it('loads server config disabled by default and shows the master toggle off', () => {
    render(<NavigatorSettingsPanel />);
    const toggle = screen.getByRole('switch', { name: 'Value-Flow Navigator engine' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    // A freshly loaded config is not a draft. The bar no longer says "Saved" —
    // the clean state is the quiet one, and the absence of the unsaved warning
    // is what carries the meaning. Reset stays reachable either way.
    expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reset to defaults/i })).not.toBeInTheDocument();
  });

  it('does not autosave — toggling shows Unsaved changes and requires Apply', () => {
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('switch', { name: 'Value-Flow Navigator engine' }));
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    expect(setConfig).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
    expect(setConfig).toHaveBeenCalledTimes(1);
    const [body] = setConfig.mock.calls[0];
    expect(body.expected_revision).toBe(1);
    expect(body.config.enabled).toBe(true);
  });

  it('retrying after a revision conflict actually overwrites', async () => {
    // The banner says "Reload or Apply to overwrite". `baseRevision` is refreshed
    // only while !dirty, and a conflict leaves you dirty by definition — so every
    // retry resent the revision the server had just rejected and 409'd forever.
    // The user was offered two ways out where only one worked, and the one that
    // worked (Reload) throws their edits away.
    setConfig.mockImplementation((_body, opts) => {
      opts?.onError?.(new Error('REVISION_CONFLICT: expected 1, found 2'));
    });
    render(<NavigatorSettingsPanel />);
    fireEvent.click(screen.getByRole('switch', { name: 'Value-Flow Navigator engine' }));
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));

    expect(setConfig.mock.calls[0][0].expected_revision).toBe(1);
    expect(await screen.findByText(/changed elsewhere/i)).toBeInTheDocument();

    // Someone else's write landed; the server is now at revision 2.
    queryData = makeRecord({}, { revision: 2 });
    setConfig.mockImplementation((_body, opts) => {
      opts?.onSuccess?.({ record: { ...queryData!.record, revision: 3 } });
    });
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));

    await waitFor(() => expect(setConfig).toHaveBeenCalledTimes(2));
    expect(refetchConfig).toHaveBeenCalled();
    expect(setConfig.mock.calls[1][0].expected_revision).toBe(2);
    expect(setConfig.mock.calls[1][0].config.enabled).toBe(true);
  });

  it('treats a stocks-only scope with stocks switched off as empty', () => {
    // The single-stock master switch drops every stock from the universe backend
    // side, so this scope scans nothing at all. The guard only looked at whether
    // the stock LIST was populated, so it let Apply through with no warning and
    // Navigator saved a scope that could never produce a row.
    queryData = makeRecord({
      scan_scope_mode: 'custom',
      scan_indices: [],
      scan_stocks: ['RELIANCE'],
      scan_all_stocks: false,
      scan_stock_contracts: false,
    });
    render(<NavigatorSettingsPanel />);

    expect(screen.getByText(/scans nothing at all/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('switch', { name: 'Value-Flow Navigator engine' }));
    expect(screen.getByRole('button', { name: /Apply changes/i })).toBeDisabled();
  });

  it('a stocks-only scope with stocks switched ON is not empty', () => {
    queryData = makeRecord({
      scan_scope_mode: 'custom',
      scan_indices: [],
      scan_stocks: ['RELIANCE'],
      scan_all_stocks: false,
      scan_stock_contracts: true,
    });
    render(<NavigatorSettingsPanel />);

    expect(screen.queryByText(/scans nothing at all/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('switch', { name: 'Value-Flow Navigator engine' }));
    expect(screen.getByRole('button', { name: /Apply changes/i })).not.toBeDisabled();
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
    fireEvent.click(screen.getByRole('switch', { name: 'Value-Flow Navigator engine' }));
    const resetBtn = screen.getByRole('button', { name: /Reset to defaults/i });
    fireEvent.click(resetBtn);
    expect(resetConfig).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Click again to confirm reset/i }));
    expect(resetConfig).toHaveBeenCalledTimes(1);
  });

  // The one "What Navigator scans" section became three, matching SuperTrend's
  // order (chart source → instruments → contracts) so the two engines read the
  // same way. "Instruments" and "Contracts" each appear twice — the scope wrapper
  // and the group inside it — so these are matched by getAllByText.
  const SECTION_TITLES = [
    'Chart source', 'Instruments', 'Contracts',
    'Structure Radar and Signal Origination', 'Anchored VWAP and signal grades',
    'Daily and weekly ranges', 'Volatility regime', 'Option-flow oscillator', 'Gamma activity',
    'Fusion and eligibility', 'Data retention',
  ];

  it('renders every settings section', () => {
    render(<NavigatorSettingsPanel />);
    for (const title of SECTION_TITLES) {
      expect(screen.getAllByText(title).length).toBeGreaterThan(0);
    }
  });

  describe('Scan scope — shared with SuperTrend, or Navigator\'s own', () => {
    it('defaults to shared and shows what the engine currently covers, read-only', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByRole('button', { name: 'Instruments: Like SuperTrend' })).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByText(/Following SuperTrend:/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Instruments: Like SuperTrend' })).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByText('Chart source')).toBeInTheDocument();
    });

    it('the dead read-only "Engine source" row is gone', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.queryByText('Engine source')).not.toBeInTheDocument();
      expect(screen.queryByText(/This build is Kite-only/)).not.toBeInTheDocument();
    });

    it('switching to its own scope reveals the universe pickers and a contracts choice', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
      expect(screen.getByText('Chart source')).toBeInTheDocument();
      expect(screen.getByText('Indices')).toBeInTheDocument();
      expect(screen.queryByText('Currently covering')).not.toBeInTheDocument();
    });

    it('seeds a fresh custom scope from the engine so the first save is never empty', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
      fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
      const [body] = setConfig.mock.calls[0];
      expect(body.config.scan_scope_mode).toBe('custom');
      expect(body.config.scan_indices).toEqual(['NIFTY 50', 'NIFTY BANK']);
    });

    it('blocks Apply and warns when a custom scope has nothing selected', () => {
      queryData = makeRecord({ scan_scope_mode: 'custom', scan_indices: ['NIFTY 50'] });
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('checkbox', { name: 'NIFTY' }));
      expect(screen.getByText(/Navigator scans nothing at all/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Apply changes/i })).toBeDisabled();
    });

    it('stocks can be picked for a custom scope — not just indices', () => {
      queryData = makeRecord({ scan_scope_mode: 'custom', scan_indices: ['NIFTY 50'] });
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('checkbox', { name: 'RELIANCE' }));
      fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
      const [body] = setConfig.mock.calls[0];
      expect(body.config.scan_stocks).toEqual(['RELIANCE']);
    });

    it('a configured custom universe survives flipping to shared and back', () => {
      queryData = makeRecord({ scan_scope_mode: 'custom', scan_stocks: ['RELIANCE'] });
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: 'Instruments: Like SuperTrend' }));
      fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
      fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
      const [body] = setConfig.mock.calls[0];
      expect(body.config.scan_stocks).toEqual(['RELIANCE']);
    });

    describe('the single-stock switch follows the scope the backend reads', () => {
      const SWITCH = 'Navigator scan single-stock underlyings';

      it('is hidden on a shared scope, where the engine\'s value is what applies', () => {
        queryData = makeRecord({ scan_scope_mode: 'shared', strike_moneyness: ['ATM'] });
        render(<NavigatorSettingsPanel />);
        expect(screen.getByText('Strike range')).toBeInTheDocument();
        expect(screen.queryByRole('switch', { name: SWITCH })).not.toBeInTheDocument();
      });

      it('is reachable on a custom scope even while contracts follow SuperTrend', () => {
        queryData = makeRecord({
          scan_scope_mode: 'custom', scan_indices: ['NIFTY 50'], strike_moneyness: null,
        });
        render(<NavigatorSettingsPanel />);
        expect(screen.queryByText('Strike range')).not.toBeInTheDocument();
        expect(screen.getByRole('switch', { name: SWITCH })).toBeInTheDocument();
      });

      it('saves onto Navigator and hides the now-inert stock pickers', () => {
        queryData = makeRecord({ scan_scope_mode: 'custom', scan_indices: ['NIFTY 50'] });
        render(<NavigatorSettingsPanel />);
        expect(screen.getByRole('checkbox', { name: 'RELIANCE' })).toBeInTheDocument();

        fireEvent.click(screen.getByRole('switch', { name: SWITCH }));
        expect(screen.queryByRole('checkbox', { name: 'RELIANCE' })).not.toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
        expect(setConfig.mock.calls[0][0].config.scan_stock_contracts).toBe(false);
      });

      it('seeds from the engine, so an indices-only engine does not silently gain stocks', () => {
        engineCfg = { ...engineCfg, scan_stock_contracts: false };
        render(<NavigatorSettingsPanel />);
        fireEvent.click(screen.getByRole('button', { name: 'Instruments: Own' }));
        fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));
        expect(setConfig.mock.calls[0][0].config.scan_stock_contracts).toBe(false);
      });
    });
  });

  describe('Structure Radar and Signal Origination', () => {
    it('signal origination defaults to Off and explains today\'s unchanged behaviour', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByRole('button', { name: /^Off$/i })).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByText(/Navigator only ever comments on a setup that SuperTrend already found/)).toBeInTheDocument();
    });

    it('switching to Full updates the explanation and unlocks Apply', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      expect(screen.getByText(/now you can actually trade it/)).toBeInTheDocument();
      expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
    });

    it('auto-execute originated is locked until Full is selected', () => {
      render(<NavigatorSettingsPanel />);
      const toggle = screen.getByRole('switch', { name: 'Auto-Execute Originated' });
      expect(toggle).toHaveAttribute('aria-checked', 'false');
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'false');
    });

    it('auto-execute originated is locked until calibration is ready even when Full is selected', () => {
      render(<NavigatorSettingsPanel />);
      fireEvent.click(screen.getByRole('button', { name: /^Full$/i }));
      const toggle = screen.getByRole('switch', { name: 'Auto-Execute Originated' });
      fireEvent.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'false');
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

  describe('Strategy Definition is the "Advanced" (collapsed, protected) group', () => {
    it('is collapsed by default, badged "6/6 at manual default", and shows no revert buttons', () => {
      render(<NavigatorSettingsPanel />);
      const heading = screen.getByText('Strategy definition (from the source manual)');
      expect(heading).toBeInTheDocument();
      expect(screen.getByText('6/6 at manual default')).toBeInTheDocument();
      const advancedDetails = heading.closest('details') as HTMLDetailsElement;
      expect(advancedDetails.open).toBe(false);
      expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument();
    });

    it('every ordinary settings section is a sibling, NOT nested inside the Strategy Definition group', () => {
      render(<NavigatorSettingsPanel />);
      const advancedDetails = screen.getByText('Strategy definition (from the source manual)').closest('details') as HTMLDetailsElement;
      for (const title of SECTION_TITLES) {
        for (const node of screen.getAllByText(title)) {
          expect(advancedDetails.contains(node)).toBe(false);
        }
      }
    });

    it('each of the 6 manual fields carries a "From the source manual" indicator, not a repeated number', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getAllByLabelText('From the source manual').length).toBe(6);
      expect(screen.queryByText(/Manual default:/)).not.toBeInTheDocument();
    });

    it('explains each of the 6 manual fields in plain text — visible without hovering, no help cursor', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByText(/Dynamic watches only the strikes closest to the price/)).toBeInTheDocument();
      expect(screen.getByText(/Below a confidence score of 60, Navigator isn't sure enough/)).toBeInTheDocument();
      const advancedDetails = screen.getByText('Strategy definition (from the source manual)').closest('details') as HTMLDetailsElement;
      const helpCursorEls = Array.from(advancedDetails.querySelectorAll('*')).filter((el) => (el as HTMLElement).style.cursor === 'help');
      expect(helpCursorEls.length).toBe(0);
    });

    it('shows the two always-on hardcoded manual rules with their plain-text explanation always visible', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getByText('Compression always forces WAIT')).toBeInTheDocument();
      expect(screen.getByText(/no setting can override this/)).toBeInTheDocument();
      expect(screen.getByText('Gamma never sets direction by itself')).toBeInTheDocument();
      expect(screen.getByText(/it can never be the only reason one fires/)).toBeInTheDocument();
    });

    it('changing a manual-anchored field shows a "was X — revert" note and updates the at-default count', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      expect(screen.getByText('5/6 at manual default')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /was 68 — revert/i })).toBeInTheDocument();
    });

    it('clicking revert restores that field to the manual default and clears the note', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      fireEvent.click(screen.getByRole('button', { name: /revert/i }));
      expect(strongZoneInput.value).toBe('68');
      expect(screen.getByText('6/6 at manual default')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument();
    });

    it('reverting one field does not touch another changed field', () => {
      render(<NavigatorSettingsPanel />);
      const strongZoneInput = screen.getByLabelText('Strong flow zone') as HTMLInputElement;
      const extremeZoneInput = screen.getByLabelText('Extreme flow zone') as HTMLInputElement;
      fireEvent.change(strongZoneInput, { target: { value: '75' } });
      fireEvent.change(extremeZoneInput, { target: { value: '99' } });
      expect(screen.getByText('4/6 at manual default')).toBeInTheDocument();
      fireEvent.click(screen.getAllByRole('button', { name: /revert/i })[0]);
      expect(extremeZoneInput.value).toBe('99');
      expect(screen.getByText('5/6 at manual default')).toBeInTheDocument();
    });

    it('the old sections point to the moved fields instead of duplicating an editable control', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.getAllByText(/Set under Strategy definition/).length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Sterling-calibration fields: highlighted quietly, no permanent text', () => {
    it('never shows a redundant "Default: X" label for any field', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.queryByText(/^Default:/)).not.toBeInTheDocument();
    });

    it('every number field hides the native spinner and gets a consistent focus ring (nav-settings-input class)', () => {
      render(<NavigatorSettingsPanel />);
      const pivotLeftInput = screen.getByLabelText('Pivot left bars') as HTMLInputElement;
      expect(pivotLeftInput.className).toContain('nav-settings-input');
      const styleTag = document.querySelector('style');
      expect(styleTag?.textContent).toContain('-webkit-appearance: none');
      expect(styleTag?.textContent).toContain(':focus');
    });

    it('clicking the custom increment/decrement buttons still steps the value up and down', () => {
      render(<NavigatorSettingsPanel />);
      const pivotLeftInput = screen.getByLabelText('Pivot left bars') as HTMLInputElement;
      expect(pivotLeftInput.value).toBe('3');
      fireEvent.click(screen.getByRole('button', { name: 'Increase Pivot left bars' }));
      expect(pivotLeftInput.value).toBe('4');
      fireEvent.click(screen.getByRole('button', { name: 'Decrease Pivot left bars' }));
      fireEvent.click(screen.getByRole('button', { name: 'Decrease Pivot left bars' }));
      expect(pivotLeftInput.value).toBe('2');
    });

    it('the stepper clamps to min/max and respects a fractional step', () => {
      render(<NavigatorSettingsPanel />);
      const minSlopeInput = screen.getByLabelText('Min slope (ATR/bar)') as HTMLInputElement;
      expect(minSlopeInput.value).toBe('0.02');
      fireEvent.click(screen.getByRole('button', { name: 'Increase Min slope (ATR/bar)' }));
      expect(minSlopeInput.value).toBe('0.03');
    });

    it('an at-default field shows no revert control at all', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument();
    });

    it('changing a Sterling-calibration field shows a "was X — revert" note; reverting restores it and removes the note', () => {
      render(<NavigatorSettingsPanel />);
      const pivotLeftInput = screen.getByLabelText('Pivot left bars') as HTMLInputElement;
      fireEvent.change(pivotLeftInput, { target: { value: '7' } });
      expect(screen.getByRole('button', { name: /was 3 — revert/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /revert/i }));
      expect(pivotLeftInput.value).toBe('3');
      expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument();
    });

    it('an unset optional field (risk-free rate) is treated as its default — no revert shown until a real value is entered', () => {
      render(<NavigatorSettingsPanel />);
      expect(screen.queryByRole('button', { name: /revert/i })).not.toBeInTheDocument();
      const riskFreeRateInputs = screen.getAllByRole('spinbutton').filter((el) => (el as HTMLInputElement).placeholder === 'unset');
      fireEvent.change(riskFreeRateInputs[0], { target: { value: '0.07' } });
      expect(screen.getByRole('button', { name: /was unset — revert/i })).toBeInTheDocument();
    });

    it('toggling a boolean field away from its default shows a "was On/Off — revert" note', () => {
      render(<NavigatorSettingsPanel />);
      const toggle = screen.getByRole('switch', { name: 'Require fresh trigger' });
      fireEvent.click(toggle);
      expect(screen.getByRole('button', { name: /was on — revert/i })).toBeInTheDocument();
    });
  });

  it('shows raw and effective concepts distinctly via fusion weight fields', () => {
    render(<NavigatorSettingsPanel />);
    expect(screen.getByText('Base weight')).toBeInTheDocument();
    expect(screen.getByText('AVWAP weight')).toBeInTheDocument();
  });
});
