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
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false,
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

const patchSpy = vi.fn();

function mockRows(rows: ReturnType<typeof makeRow>[], overrides: Record<string, unknown> = {}) {
  vi.doMock('../../../hooks/useSterlingKiteEngine', () => ({
    useEngineConfig: () => ({ data: { ...cfg, ...overrides } }),
    useSetEngineConfig: () => ({ mutate: vi.fn() }),
    usePatchEngineConfig: () => ({ mutate: patchSpy, isPending: false, isError: false, error: null }),
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
  fireEvent.click(screen.getAllByTitle(/^VIEW — A local lens/)[0]);
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
    const exitRuleTitle = /^EXIT —/;

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

    // This used to assert the source control was SHARED and so stayed visible
    // under every lens. It is not shared: navigator/runtime reads its own
    // `record.config.scan_source` unconditionally, and Navigator's settings page
    // says so ("Always its own — SuperTrend's source never applied here"). The
    // header was the last surface still claiming otherwise, so it now hides on
    // the Navigator lens for exactly the reason the exit rule does.
    const sourceTitle = /^SOURCE —/;

    it('shows the source dropdown under Combined', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      expect(screen.getByTitle(sourceTitle)).toBeInTheDocument();
    });

    it('hides the source dropdown under the Navigator lens — it is SuperTrend\'s, not shared', async () => {
      mockRows([makeRow('NIFTY 50', 1, 'CONFIRMED')]);
      await renderPane();
      openSignalModeMenu();
      fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
      expect(screen.queryByTitle(sourceTitle)).not.toBeInTheDocument();
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

describe('when the SuperTrend engine is switched off', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
    patchSpy.mockClear();
  });

  const off = { engine_enabled: false };

  it('says the engine is off under the SuperTrend lens, not "no setups"', async () => {
    // No SuperTrend rows exist by construction, so blaming the market is wrong.
    mockRows([makeNavigatorRow('SENSEX', 2, 'CONFIRMED')], off);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^SuperTrend only/ }));
    expect(screen.getByText('SuperTrend is off')).toBeInTheDocument();
    expect(screen.getByText(/only SuperTrend setups, and the engine is not scanning/i)).toBeInTheDocument();
  });

  it('offers the switch, and turning it on patches the engine config', async () => {
    mockRows([makeNavigatorRow('SENSEX', 2, 'CONFIRMED')], off);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^SuperTrend only/ }));
    fireEvent.click(screen.getByRole('button', { name: /Turn on SuperTrend/i }));
    expect(patchSpy).toHaveBeenCalledWith({ engine_enabled: true });
  });

  it('explains that "where both agree" cannot fill with one engine off', async () => {
    mockRows([makeNavigatorRow('SENSEX', 2, 'CONFIRMED')], off);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Where both agree/ }));
    expect(screen.getByText('SuperTrend is off')).toBeInTheDocument();
    expect(screen.getByText(/needs a SuperTrend setup for Navigator to agree/i)).toBeInTheDocument();
  });

  it('still shows Navigator-originated rows under Combined rather than the off-state', async () => {
    // Combined is not blocked while the other engine is producing.
    mockRows([makeNavigatorRow('SENSEX', 2, 'CONFIRMED')], off);
    await renderPane();
    expect(screen.queryByText('SuperTrend is off')).not.toBeInTheDocument();
    expect(screen.getAllByText('SENSEX').length).toBeGreaterThan(0);
  });

  it('never blocks the Navigator lens, which is meant to work with SuperTrend off', async () => {
    mockRows([makeNavigatorRow('SENSEX', 2, 'CONFIRMED')], off);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^Navigator/ }));
    expect(screen.queryByText('SuperTrend is off')).not.toBeInTheDocument();
    expect(screen.getAllByText('SENSEX').length).toBeGreaterThan(0);
  });

  it('leaves the board alone when the engine is on', async () => {
    mockRows([makeRow('NIFTY 50', 1, null)]);
    await renderPane();
    openSignalModeMenu();
    fireEvent.click(screen.getByRole('option', { name: /^SuperTrend only/ }));
    expect(screen.queryByText('SuperTrend is off')).not.toBeInTheDocument();
    expect(screen.getAllByText('NIFTY 50').length).toBeGreaterThan(0);
  });
});
