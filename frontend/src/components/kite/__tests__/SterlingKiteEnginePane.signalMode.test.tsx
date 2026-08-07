import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false, hybrid_st_weight: 0.5,
};

function navDecision(status: string) {
  return {
    decision_id: `nav_${status}`, schema_version: 1, config_revision: 1, model_versions: {},
    generated_at_ms: 1_700_000_000_000, bar_close_ms: 1_700_000_000_000, activation_watermark_ms: 0,
    base_signal_id: 's1', trigger: 'base_fresh', direction: 'long', status,
    base_score: 85, suite_score: 80, effective_score: 82, execution_eligible: status === 'CONFIRMED' || status === 'HIGH_CONVICTION',
    data_quality: 'ok', reason_codes: ['OK'], avwap: null, volatility: null, option_flow: null, gamma: null,
  };
}

function makeRow(underlying: string, token: number, navigatorStatus: string | null) {
  return {
    underlying, token, exchange: 'NFO', regime: 'BULL',
    alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
    spot: 24010, stop_loss: 23900, score: 85, timestamp_ms: 1_700_000_000_000,
    source: 'spot', is_active: true, is_fresh: true,
    legs: [{ moneyness: 'ATM', option_type: 'CE', option_symbol: `${underlying.replace(' ', '')}25JUN24000CE`, strike: 24000, expiry: '2026-06-26', lot_size: 75, token: token + 1000, is_active: true }],
    ...(navigatorStatus ? { navigator: navDecision(navigatorStatus) } : {}),
  };
}

function makeNavigatorRow(underlying: string, token: number, navigatorStatus: string) {
  return {
    ...makeRow(underlying, token, navigatorStatus),
    source: 'navigator',
    legs: [],
  };
}

function mockRows(rows: ReturnType<typeof makeRow>[]) {
  vi.doMock('../../../hooks/useSterlingKiteEngine', () => ({
    useEngineConfig: () => ({ data: cfg }),
    useSetEngineConfig: () => ({ mutate: vi.fn() }),
    usePatchEngineConfig: () => ({ mutate: vi.fn() }),
    useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
    useEngineSignals: () => ({
      data: { generated_ms: 1, scanning: false, scanning_label: '', rows, next_scan_ms: 0, auto_scan: false, market_open: true },
    }),
    useRunScan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(() => Promise.resolve()), isPending: false }),
    useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
    useStockRegistry: () => ({ data: [] }),
  }));
}

async function renderPane() {
  const { SterlingKiteEnginePane: Pane } = await import('../SterlingKiteEnginePane');
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Pane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

function openSignalModeMenu() {
  fireEvent.click(screen.getByTitle(/^Signal lens —/));
}

describe('SterlingKiteEnginePane — 4-way signal lens (SuperTrend / Navigator / Combined / Common)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('defaults to Combined and shows every row with its Navigator badge when present', async () => {
    mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED'), makeRow('NIFTY BANK', 2, null)]);
    await renderPane();
    expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
    expect(screen.getByText('NIFTY BANK')).toBeInTheDocument();
    expect(screen.getByText(/Nav CONFIRMED/)).toBeInTheDocument();
  });

  it('SuperTrend lens hides the Navigator badge even when evidence exists', async () => {
    mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^SuperTrend/ }));
    expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Nav CONFIRMED/)).not.toBeInTheDocument();
  });

  it('Navigator lens filters out rows with no Navigator evidence', async () => {
    mockRows([makeRow('NIFTY 50', 1, 'WATCH'), makeRow('NIFTY BANK', 2, null)]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
    expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
    expect(screen.queryByText('NIFTY BANK')).not.toBeInTheDocument();
  });

  it('Common lens keeps only rows where Navigator agrees (Confirmed/High Conviction)', async () => {
    mockRows([
      makeRow('NIFTY 50', 1, 'CONFIRMED'),
      makeRow('NIFTY BANK', 2, 'WATCH'),
      makeRow('SENSEX', 3, 'HIGH_CONVICTION'),
    ]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Where both agree/ }));
    expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SENSEX').length).toBeGreaterThan(0);
    expect(screen.queryByText('NIFTY BANK')).not.toBeInTheDocument();
  });

  it('shows a helpful empty state (not the generic "no setups" copy) when the Navigator lens matches nothing', async () => {
    mockRows([makeRow('NIFTY 50', 1, null)]); // SuperTrend has a setup, but no Navigator evidence
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
    expect(screen.getByText(/SuperTrend setup/)).toBeInTheDocument();
    expect(screen.getByText('Connect → Value-Flow Navigator')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Switch to Combined lens/i }));
    expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
  });

  it('counts only real SuperTrend rows in the Common-lens empty state', async () => {
    // Navigator-owned rows share this board now; counting them as SuperTrend
    // setups would overstate what the other engine actually found.
    mockRows([
      makeRow('NIFTY 50', 1, null),
      makeNavigatorRow('SENSEX', 2, 'WATCH'),
      makeNavigatorRow('INFY', 3, 'WATCH'),
    ]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Where both agree/ }));
    expect(screen.getByText(/1 SuperTrend setup on the board/)).toBeInTheDocument();
    expect(screen.queryByText(/3 SuperTrend setups/)).not.toBeInTheDocument();
  });

  it('persists the chosen lens to localStorage across remounts', async () => {
    mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
    expect(localStorage.getItem('kite_st_signal_mode')).toBe('navigator');
  });

  describe('SuperTrend-only controls hide when the lens shows no SuperTrend rows', () => {
    const exitRuleTitle = /^Exit confirmation/;

    it('shows the exit-rule dropdown under Combined (SuperTrend rows are on screen)', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      expect(screen.getByTitle(exitRuleTitle)).toBeInTheDocument();
    });

    it('hides it under the Navigator lens — it governs nothing that is showing', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
      expect(screen.queryByTitle(exitRuleTitle)).not.toBeInTheDocument();
    });

    it('the shared Signal-source control stays visible under every lens', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
      expect(screen.getByTitle(/^Signal source/)).toBeInTheDocument();
    });

    it('comes back when switching off the Navigator lens', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
      expect(screen.queryByTitle(exitRuleTitle)).not.toBeInTheDocument();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Where both agree/ }));
      expect(screen.getByTitle(exitRuleTitle)).toBeInTheDocument();
    });
  });

  describe('Navigator-originated rows (source="navigator", no SuperTrend trigger)', () => {
    it('SuperTrend lens excludes a Navigator-originated row entirely', async () => {
      mockRows([makeRow('NIFTY 50', 1, null), makeNavigatorRow('NIFTY BANK', 2, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^SuperTrend/ }));
      expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
      expect(screen.queryByText('NIFTY BANK')).not.toBeInTheDocument();
    });

    it('Common lens excludes a Navigator-originated row even when Confirmed/High Conviction', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED'), makeNavigatorRow('NIFTY BANK', 2, 'HIGH_CONVICTION')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Where both agree/ }));
      expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
      expect(screen.queryByText('NIFTY BANK')).not.toBeInTheDocument();
    });

    it('Combined lens still shows a Navigator-originated row', async () => {
      mockRows([makeNavigatorRow('NIFTY BANK', 2, 'CONFIRMED')]);
      await renderPane();
      // Combined is the default lens — no menu interaction needed.
      expect(screen.getAllByText('NIFTY BANK').length).toBeGreaterThan(0);
      expect(screen.getByText(/Navigator idea/)).toBeInTheDocument();
    });

    it('Navigator lens still shows a Navigator-originated row', async () => {
      mockRows([makeNavigatorRow('NIFTY BANK', 2, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
      expect(screen.getAllByText('NIFTY BANK').length).toBeGreaterThan(0);
    });
  });
});
