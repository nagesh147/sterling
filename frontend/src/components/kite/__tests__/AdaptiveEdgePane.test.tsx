import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { AdaptiveEdgePane } from '../AdaptiveEdgePane';

const snapshot = {
  label: 'RESEARCH_NOT_LIVE',
  software_complete: true,
  production_gate_authorized: false,
  meets_a197: false,
  registry_locked: true,
  live_trading: false,
  settings: {
    enabled: true,
    symbol: 'NIFTY-I',
    w_short: 5,
    w_long: 15,
    stop_points: 80,
    trail_points: 40,
    profit_lock_activation_points: 50,
    profit_lock_offset_points: 15,
    persistence_bars: 3,
    scalp_favorable_points: 5,
    extended_favorable_points: 15,
    intraday_favorable_points: 25,
    tick_size: 1,
    ib_minutes: 15,
  },
  readiness: [{ name: 'execution_gate_blocked', ready: true, detail: 'blocked' }],
  session: {
    entries: 42,
    exits: 41,
    reentries: 41,
    blocked_pyramid: 2215,
    last_mode: 'MICRO',
    last_thesis: 'THESIS_VALID',
    last_protection_stage: 'P0_RISK_CONTROLLED',
    last_overlays: ['AT_LVN'],
    last_operating_mode: 'active',
    last_horizon: 'IMPULSE',
    last_poc: 24405,
    last_cvd: 32055,
    last_location: 'above_value',
    last_bar_delta: 12,
    last_vwap: 24409.83,
    last_or_location: 'inside_or',
    last_poc_migration: 'unchanged',
    peak_pnl: 12,
    current_pnl: 4,
    profit_giveback: 0.2,
    lifecycle_action: 'HOLD',
    last_position_quantity: 1,
    exit_fill_price: null,
    audit_stages: ['opportunity'],
  },
  legs: [{
    session_date: '2026-08-14',
    entry_time: '2026-08-14T08:38:00+00:00',
    exit_time: null,
    entry_mode: 'MICRO',
    exit_mode: 'MICRO',
    peak_mode: 'MICRO',
    horizon: 'IMPULSE',
    thesis: 'THESIS_VALID',
    protection_stage: 'P0_RISK_CONTROLLED',
    overlays: ['AT_LVN'],
    quantity: 1,
    flattened: false,
  }],
  daily: [{ session_date: '2026-08-14', entries: 6, exits: 5, flattened: false, last_quantity: 1 }],
  quality: { status: 'TRIAL_NOT_A197_QUALITY', li_valid_rate: 1, missing_score_rate: 0.005 },
  holdout: { label: 'RESEARCH_HOLDOUT_NOT_LIVE', entries: 21, software_complete: true },
  coverage: { symbol: 'NIFTY-I', trading_days: 7, bar_count: 2577, meets_a197: false },
  walk_forward: { label: 'RESEARCH_PLACEHOLDER_SPLITS', train: 909, validation: 581, test: 1077, ineligible: 5, train_test_overlap: false },
  mode_counts: { MICRO: 28, SCALP: 30, EXTENDED_SCALP: 21, INTRADAY: 11 },
  mode_transitions: [{ timestamp: '2026-08-14T08:35:00+00:00', previous_mode: 'INTRADAY', new_mode: 'EXTENDED_SCALP', favorable_points: 91 }],
  formula_table: { 'F-101': { status: 'RESEARCH_CODE_PRESENT_REGISTRY_LOCKED', reason: 'locked' } },
  incomplete_reasons: [],
};

vi.mock('../../../hooks/useAdaptiveEdge', () => ({
  useAdaptiveEdgeSnapshot: () => ({ data: snapshot, isLoading: false, error: null, refetch: vi.fn(), isFetching: false }),
}));

describe('AdaptiveEdgePane', () => {
  it('renders the research desk from the last snapshot', () => {
    render(<AdaptiveEdgePane />);
    expect(screen.getByRole('heading', { name: 'Adaptive Edge' })).toBeInTheDocument();
    expect(screen.getByText('BOARD READY')).toBeInTheDocument();
    expect(screen.getByText('ORDERS OFF')).toBeInTheDocument();
    expect(screen.getByText('WAITING ON HISTORY')).toBeInTheDocument();
    expect(screen.getByText('DISPLAY ONLY')).toBeInTheDocument();
    expect(screen.getByText(/MICRO · 28/)).toBeInTheDocument();
    expect(screen.getAllByText('AT_LVN').length).toBeGreaterThan(0);
    expect(screen.getByText('RESEARCH LEGS')).toBeInTheDocument();
    expect(screen.getByText('DAILY LEDGER')).toBeInTheDocument();
    expect(screen.getByText('FORMULA REGISTRY')).toBeInTheDocument();
  });

  it('opens Adaptive Edge settings from the desk', () => {
    const events: string[] = [];
    window.addEventListener('kite-nav-click', (event) => events.push((event as CustomEvent).detail));
    window.addEventListener('kite-connect-section', (event) => events.push((event as CustomEvent).detail));
    render(<AdaptiveEdgePane />);
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
    expect(events).toContain('connect');
    expect(events).toContain('adaptiveEdge');
  });
});
