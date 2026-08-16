import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { AdaptiveEdgeDashboard } from '../AdaptiveEdgeDashboard';
import type { AdaptiveEdgeSnapshot } from '../../../types/adaptiveEdge';

const mockSnapshot: AdaptiveEdgeSnapshot = {
  label: 'RESEARCH_ACTIVE',
  software_complete: true,
  production_gate_authorized: true,
  meets_a197: true,
  registry_locked: false,
  live_trading: false,
  settings: {
    enabled: true,
    symbol: 'NIFTY-I',
    symbols: ['NIFTY-I', 'BANKNIFTY-I', 'FINNIFTY-I', 'SENSEX-I'],
    scan_source: 'both',
    scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX'],
    scan_stocks: ['RELIANCE', 'TCS'],
    scan_all_stocks: false,
    scan_stock_contracts: true,
    strike_moneyness: ['ITM2', 'ITM1', 'ATM', 'OTM1', 'OTM2'],
    scan_expiries: ['weekly', 'monthly'],
    scan_expiries_indices: ['weekly', 'monthly'],
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
  readiness: [
    { name: 'execution_gate_authorized', ready: true, detail: 'Authorized' },
    { name: 'formula_registry_implemented', ready: true, detail: 'F-101..F-114 IMPLEMENTED' },
  ],
  session: {
    entries: 42,
    exits: 41,
    reentries: 41,
    blocked_pyramid: 2215,
    last_mode: 'INTRADAY',
    last_thesis: 'THESIS_VALID',
    last_protection_stage: 'P0_RISK_CONTROLLED',
    last_overlays: ['AT_LVN'],
    last_operating_mode: 'active',
    last_horizon: 'SESSION_TREND',
    last_poc: 24405,
    last_cvd: 32055,
    last_location: 'ABOVE_POC',
    last_bar_delta: 120,
    last_vwap: 24409.84,
    last_or_location: 'INSIDE_OR',
    last_poc_migration: 'NONE',
    peak_pnl: 1400.0,
    current_pnl: 1286.1,
    profit_giveback: 113.9,
    lifecycle_action: 'EXIT_TIME_CUTOFF',
    last_position_quantity: 0,
    exit_fill_price: 24410,
    audit_stages: ['opportunity', 'risk', 'order', 'accounting'],
  },
  legs: [],
  signals: [],
  daily: [],
  quality: null,
  holdout: null,
  coverage: {
    trading_days: 120,
    total_bars: 45000,
    meets_a197: true,
  },
  walk_forward: null,
  mode_counts: { MICRO: 10, SCALP: 15, EXTENDED_SCALP: 10, INTRADAY: 7 },
  mode_transitions: [
    {
      timestamp: '2026-08-14T04:15:00Z',
      previous_mode: 'MICRO',
      new_mode: 'SCALP',
      trigger_reason: 'favorable expansion >= 5 pts',
    },
  ],
  formula_table: {
    'F-101': { status: 'IMPLEMENTED', reason: 'A196 robust normalizer' },
  },
  incomplete_reasons: [],
};

describe('AdaptiveEdgeDashboard', () => {
  it('renders KPI metrics and switches between dashboard sections', () => {
    render(<AdaptiveEdgeDashboard snapshot={mockSnapshot} />);
    expect(screen.getByText('AUTHORIZED')).toBeInTheDocument();
    expect(screen.getByText('24,405')).toBeInTheDocument();
    expect(screen.getByText('24,409.84')).toBeInTheDocument();
    expect(screen.getByText('+32,055')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('2,215')).toBeInTheDocument();

    // Click Microstructure section
    fireEvent.click(screen.getByText('🌊 Order Flow & Microstructure'));
    expect(screen.getByText(/Order Flow & Market Profile Engine Details/)).toBeInTheDocument();

    // Click Opportunity Modes section
    fireEvent.click(screen.getByText('🎯 Opportunity Modes'));
    expect(screen.getByText(/Opportunity Mode Escalation Ladder/)).toBeInTheDocument();
    expect(screen.getAllByText('MICRO').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SCALP').length).toBeGreaterThan(0);

    // Click 14 Quantitative Rules section
    fireEvent.click(screen.getByText('🛡️ 14 Quantitative Rules'));
    expect(screen.getByText('F-101')).toBeInTheDocument();
    expect(screen.getByText('Predictive Feature Vector')).toBeInTheDocument();
    expect(screen.getByText('F-114')).toBeInTheDocument();
    expect(screen.getByText('Concurrency / Single-Position Lock')).toBeInTheDocument();

    // Click Execution Ledger section
    fireEvent.click(screen.getByText('📜 Execution Ledger'));
    expect(screen.getByText(/Execution & Mode Transition Ledger/)).toBeInTheDocument();
  });
});
