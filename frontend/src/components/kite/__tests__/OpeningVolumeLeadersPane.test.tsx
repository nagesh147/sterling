import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OpeningVolumeLeadersPane } from '../OpeningVolumeLeadersPane';

const { mutate, contractResult, scanResult } = vi.hoisted(() => ({
  mutate: vi.fn(),
  contractResult: {
    current: {
      data: {
        strategy: { version: '1.1.0' },
        tier_score: 'not implemented: source weights are not observable',
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
}));

vi.mock('../../../hooks/useOpeningVolumeLeaders', () => ({
  useOpeningVolumeContract: () => contractResult.current,
  useOpeningVolumeScan: () => scanResult.current,
}));

const signal = (over: Record<string, unknown> = {}) => ({
  symbol: 'GODREJCP',
  session_date: '2026-09-03',
  signal_time: '2026-09-03T09:15:00+05:30',
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
  rise_from_low_pct: 0.2,
  fall_from_high_pct: 3.97,
  is_leader: true,
  passes_quality_filters: true,
  entry_phase: 'planning',
  signal_key: 'opening-volume:2026-09-03:GODREJCP:DOWN',
  ...over,
});

const response = (over: Record<string, unknown> = {}) => ({
  strategy: { version: '1.1.0' },
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
  breadth: { advances: 100, declines: 110, unchanged: 1, observed: 211, advance_decline_ratio: 0.909 },
  leaders: [signal()],
  watch: [],
  failures: [{ symbol: 'ABC', error: 'fewer than 10 valid prior sessions' }],
  ...over,
});

describe('OpeningVolumeLeadersPane', () => {
  beforeEach(() => {
    mutate.mockReset();
    scanResult.current = { data: undefined, error: null, isPending: false, mutate };
  });

  it('starts in an explicit manual, advisory-only state', () => {
    render(<OpeningVolumeLeadersPane />);
    expect(screen.getByText('Opening Leaders')).toBeInTheDocument();
    expect(screen.getByText(/Advisory only/i)).toBeInTheDocument();
    expect(screen.getByText(/No proprietary score/i)).toBeInTheDocument();
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
      max_candidates: 100,
      concurrency: 3,
      history_calendar_days: 45,
      config: {},
    });
  });

  it('does not send an empty custom-symbol scan', () => {
    render(<OpeningVolumeLeadersPane />);
    fireEvent.click(screen.getByRole('button', { name: 'Custom' }));
    fireEvent.click(screen.getByRole('button', { name: /Run opening scan/i }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Enter at least one/);
    expect(mutate).not.toHaveBeenCalled();
  });

  it('renders signal time, ORB time, tier, combo, breadth, and failures from the API', () => {
    scanResult.current = { data: response(), error: null, isPending: false, mutate };
    render(<OpeningVolumeLeadersPane />);

    expect(screen.getByText('GODREJCP')).toBeInTheDocument();
    expect(screen.getByText('17.73×')).toBeInTheDocument();
    expect(screen.getByText('explosive')).toBeInTheDocument();
    expect(screen.getByText('Combo')).toBeInTheDocument();
    expect(screen.getByText(/09:15 IST/)).toBeInTheDocument();
    expect(screen.getByText(/09:16 IST/)).toBeInTheDocument();
    expect(screen.getByText('100:110')).toBeInTheDocument();
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
