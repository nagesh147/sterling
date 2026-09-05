import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OpeningVolumeLeadersPane } from '../OpeningVolumeLeadersPane';

const { mutate, contractResult, scanResult, executionConfigResult, updateExecutionResult, executeResult } = vi.hoisted(() => ({
  mutate: vi.fn(),
  contractResult: {
    current: {
      data: {
        strategy: { version: '1.4.0' },
        tier_score: 'Sterling transparent bounded score',
      },
      error: null,
    } as Record<string, unknown>,
  },
  scanResult: {
    current: {
      data: undefined,
      error: null,
      isPending: false,
      mutate: vi.fn(),
    } as Record<string, unknown>,
  },
  executionConfigResult: {
    current: {
      data: { config: { enabled: true, min_score: 55, min_conviction: 5 } },
      error: null,
    } as Record<string, unknown>,
  },
  updateExecutionResult: {
    current: { data: undefined, error: null, isPending: false, mutate: vi.fn() } as Record<string, unknown>,
  },
  executeResult: {
    current: { data: undefined, error: null, isPending: false, mutate: vi.fn() } as Record<string, unknown>,
  },
}));

vi.mock('../../../hooks/useOpeningVolumeLeaders', () => ({
  useOpeningVolumeContract: () => contractResult.current,
  useOpeningVolumeScan: () => scanResult.current,
  useOpeningExecutionConfig: () => executionConfigResult.current,
  useUpdateOpeningExecutionConfig: () => updateExecutionResult.current,
  useExecuteOpeningVolumeScan: () => executeResult.current,
}));

const signal = (over: Record<string, unknown> = {}) => ({
  symbol: 'GODREJCP',
  session_date: '2026-09-03',
  signal_time: '2026-09-03T09:15:00+05:30',
  volume_signal_time: '2026-09-03T09:15:00+05:30',
  actionable_signal_time: '2026-09-03T09:16:00+05:30',
  observed_at: '2026-09-03T09:24:00+05:30',
  direction: 'DOWN',
  tier: 'explosive',
  rvol: 17.73,
  opening_volume: 177300,
  average_opening_volume: 10000,
  baseline_session_count: 10,
  opening_open: 1250,
  opening_high: 1260,
  opening_low: 1220,
  opening_close: 1230,
  current_price: 1210,
  live_price: 1209.5,
  price_source: 'kite_live_quote',
  previous_close: 1240,
  day_change_pct: -2.42,
  gap_pct: 0.81,
  body_pct: 1.6,
  range_pct: 3.2,
  body_fraction: 0.5,
  close_location: 0.75,
  candle_quality: 'moderate',
  average_turnover_inr: 350000000,
  turnover_session_count: 20,
  liquidity_state: 'pass',
  liquidity_reasons: [],
  orb_break_side: 'DOWN',
  orb_break_time: '2026-09-03T09:16:00+05:30',
  orb_cumulative_volume: 220000,
  orb_aligned: true,
  orb_immediate: true,
  combo: true,
  session_high: 1260,
  session_low: 1205,
  orb_break_level: 1220,
  orb_age_minutes: 8,
  orb_fresh: false,
  orb_distance_pct: 0.82,
  chase_state: 'caution',
  protective_stop_price: 1260,
  stop_distance_pct: 3.28,
  stop_too_wide: true,
  consecutive_leader_days: 1,
  third_day_repeat: false,
  hold_5m_status: 'pass',
  hold_5m_check_time: '2026-09-03T09:21:00+05:30',
  hold_5m_price: 1215,
  move_1pct_within_60m: true,
  move_1pct_time: '2026-09-03T09:18:00+05:30',
  intraday_vwap: 1224,
  vwap_aligned: true,
  previous_day_high: 1270,
  previous_day_low: 1230,
  pdh_pdl_break_aligned: true,
  rsi_14_1m: 44,
  rally_aligned: true,
  rise_from_low_pct: 0.2,
  fall_from_high_pct: 3.97,
  is_leader: true,
  passes_quality_filters: true,
  entry_phase: 'planning',
  signal_key: 'opening-volume:2026-09-03:GODREJCP:DOWN',
  playbook: {
    known_gate_status: 'caution',
    known_gate_blockers: [],
    known_gate_cautions: ['opening-range stop exceeds 1.5%; halve size or skip'],
    breadth_alignment: 'aligned',
    recommended_risk_pct: 0.5,
    primary_gate_complete: false,
    sterling_gate_complete: false,
    unverified_private_gates: ['ORION score >=55', 'ORION conviction >=5/7'],
    entry_reference: '09:15 ORB boundary',
    staged_entry_pct: [30, 30, 40],
    first_scale_r_multiple: [1.5, 2],
    daily_loss_cap_r: 2,
    weekly_loss_cap_r: 4,
    max_open_positions: 2,
  },
  decision: {
    model: 'sterling_opening_decision_v1',
    provenance: 'Sterling-owned transparent replacement; not ORION proprietary parity',
    score: {
      lower_bound: 71,
      upper_bound: 73,
      coverage_pct: 98,
      trade_threshold: 55,
      special_threshold: 75,
      trade: true,
      special: false,
      components: [
        { name: 'rvol', weight: 20, earned: 20, status: 'pass', rule: 'test' },
      ],
    },
    conviction: {
      passed: 5,
      known: 6,
      total: 7,
      required: 5,
      factors: {},
      rules: {},
    },
    momentum: {
      box_x: true,
      box_y: false,
      state: 'setup',
      box_x_rule: 'test',
      box_y_rule: 'test',
    },
    sterling_combo: true,
    combo_rule: 'test',
    execution_eligible: false,
  },
  market_context: {
    status: 'available',
    daily_session_count: 252,
    sma_50: 1240,
    trend_50dma_aligned: true,
    high_52w: 1500,
    low_52w: 900,
    distance_from_52w_high_pct: -19.33,
    source: 'Kite daily candles; current/forming daily bar excluded',
  },
  option: {
    tradingsymbol: 'GODREJCP26SEP1220PE',
    exchange: 'NFO',
    option_type: 'PE',
    strike: 1220,
    expiry: '2026-09-24',
    dte: 21,
    ltp: 50,
    bid: 49.5,
    ask: 50.5,
    lot_size: 500,
    lot_cost: 25000,
    premium_stop_price: 35,
    premium_target_price: 75,
    premium_risk_per_lot: 7500,
    beginner_expiry_warning: false,
  },
  option_status: 'quoted',
  option_rule: 'nearest strike on the nearest non-expired listed expiry',
  ...over,
});

const response = (over: Record<string, unknown> = {}) => ({
  strategy: { version: '1.4.0' },
  as_of: '2026-09-03T09:24:00+05:30',
  universe: {
    source: 'kite_nfo_options_intersect_nse_equities',
    available_fno_equity_count: 212,
    requested_count: 212,
    selected_count: 212,
    truncated: false,
    symbols: ['GODREJCP'],
  },
  universe_count: 212,
  evaluated_count: 211,
  leader_count: 1,
  watch_count: 0,
  weak_count: 0,
  enrichment: {
    daily_context_limit: 50,
    daily_context_count: 1,
    option_quote_count: 1,
    historical_quotes_omitted: false,
  },
  breadth: {
    advances: 140,
    declines: 70,
    unchanged: 1,
    observed: 211,
    advance_decline_ratio: 2,
    green_pct: 66.35,
    mood: 'bullish',
    participation: 'strong_green',
    mood_rule: 'bullish when advances >= 1.5x declines; bearish at the inverse',
    coverage_pct: 99.53,
    reliable: true,
    source: 'successfully evaluated current F&O cash equities',
  },
  leaders: [signal()],
  watch: [],
  weak: [],
  failures: [{ symbol: 'ABC', error: 'fewer than 10 valid prior sessions' }],
  ...over,
});

describe('OpeningVolumeLeadersPane', () => {
  beforeEach(() => {
    mutate.mockReset();
    (updateExecutionResult.current.mutate as ReturnType<typeof vi.fn>).mockReset();
    scanResult.current = { data: undefined, error: null, isPending: false, mutate };
  });

  it('shows the strategy power state without a separate paper/live mode', () => {
    render(<OpeningVolumeLeadersPane />);
    expect(screen.getByText('Opening Leaders')).toBeInTheDocument();
    expect(screen.getByText(/Strategy enabled/i)).toBeInTheDocument();
    expect(screen.getByText(/Transparent bounded Sterling score/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run opening scan/i })).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('submits the full current F&O universe with the displayed controls', () => {
    render(<OpeningVolumeLeadersPane />);
    fireEvent.click(screen.getByLabelText(/Include 2–3× watchlist/i));
    fireEvent.change(screen.getByLabelText(/Max stocks/i), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: /Run opening scan/i }));

    expect(mutate).toHaveBeenCalledWith({
      symbols: [],
      scan_all_stocks: true,
      include_watch: true,
      include_weak: false,
      max_candidates: 100,
      concurrency: 3,
      history_calendar_days: 45,
      config: {},
    });
  });

  it('publishes editable fail-closed execution thresholds', () => {
    render(<OpeningVolumeLeadersPane />);
    fireEvent.change(screen.getByLabelText(/minimum execution score/i), {
      target: { value: '65' },
    });
    fireEvent.change(screen.getByLabelText(/minimum conviction/i), {
      target: { value: '6' },
    });

    expect(updateExecutionResult.current.mutate).toHaveBeenCalledWith({ min_score: 65 });
    expect(updateExecutionResult.current.mutate).toHaveBeenCalledWith({ min_conviction: 6 });
  });

  it('does not send an empty custom-symbol scan', () => {
    render(<OpeningVolumeLeadersPane />);
    fireEvent.click(screen.getByRole('button', { name: 'Custom' }));
    fireEvent.click(screen.getByRole('button', { name: /Run opening scan/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Enter at least one/);
    expect(mutate).not.toHaveBeenCalled();
  });

  it('sends an explicit IST replay boundary without changing the live default', () => {
    render(<OpeningVolumeLeadersPane />);
    fireEvent.click(screen.getByLabelText('Replay'));
    fireEvent.change(screen.getByLabelText(/Replay as of/i), {
      target: { value: '2026-09-03T09:24' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run opening scan/i }));

    expect(mutate).toHaveBeenCalledWith(expect.objectContaining({
      as_of: '2026-09-03T09:24:00+05:30',
    }));
  });

  it('renders signal time, ORB time, tier, combo, breadth, and failures from the API', () => {
    scanResult.current = { data: response(), error: null, isPending: false, mutate };
    render(<OpeningVolumeLeadersPane />);

    expect(screen.getByText('GODREJCP')).toBeInTheDocument();
    expect(screen.getByText('17.73×')).toBeInTheDocument();
    expect(screen.getByText('explosive')).toBeInTheDocument();
    expect(screen.getByText('COMBO')).toBeInTheDocument();
    expect(screen.getByText('Actionable signal')).toBeInTheDocument();
    expect(screen.getByText('Volume signal')).toBeInTheDocument();
    expect(screen.getAllByText(/71–73/).length).toBeGreaterThan(0);
    expect(screen.getByText(/20\.0 \/ 20\.0 · pass/i)).toBeInTheDocument();
    expect(screen.getByText(/09:15 IST/)).toBeInTheDocument();
    expect(screen.getAllByText(/09:16 IST/)).toHaveLength(2);
    expect(screen.getByText('140:70')).toBeInTheDocument();
    expect(screen.getByText('Bullish')).toBeInTheDocument();
    expect(screen.getByText(/5m hold Pass/i)).toBeInTheDocument();
    expect(screen.getByText(/1 symbol could not be evaluated/)).toBeInTheDocument();
  });

  it('shows a truthful completed-empty result instead of the pre-scan state', () => {
    scanResult.current = {
      data: response({ leader_count: 0, leaders: [], failures: [] }),
      error: null,
      isPending: false,
      mutate,
    };
    render(<OpeningVolumeLeadersPane />);
    expect(screen.getByText(/No opening-volume leaders found/i)).toBeInTheDocument();
    expect(screen.queryByText(/Ready for the completed/i)).toBeNull();
  });
});
