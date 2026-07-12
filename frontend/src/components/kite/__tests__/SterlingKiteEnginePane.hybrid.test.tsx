import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

// Full EngineConfigModel fixture — every field the component reads must be present,
// since patch() spreads `{ ...cfg, ...p }` and several sections destructure cfg
// fields unconditionally (e.g. cfg.strike_moneyness.length in the card summaries).
const baseCfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'two_red',
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_source: 'derivatives',
  scan_expiries: ['weekly', 'monthly'],
  scan_expiries_indices: null,
  scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX'],
  scan_stocks: [],
  scan_all_stocks: false,
  auto_execute: false,
  risk_sizing: true,
  risk_pct: 1.0,
  max_lots: 10,
  stop_mode: 'both',
  directional_mode: false,
  vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'],
  itm_depth: 'ITM10',
  target_delta: null,
  futures_expiry: 'near',
  adx_min: null,
  atr_pct_min: null,
  wire_risk_infra: false,
  hybrid_st_weight: 0.5,
};

const setCfgMutate = vi.fn((_vars: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
const runScanMutate = vi.fn();

// Only useSterlingKiteEngine needs deterministic mocking for these assertions — the
// component's other external hooks (useKite's react-query hooks, the Zustand stores)
// are left real; QueryClientProvider below keeps them from throwing on missing context.
vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: baseCfg }),
  useSetEngineConfig: () => ({ mutate: setCfgMutate }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: 0, scanning: false, scanning_label: '', rows: [],
      next_scan_ms: 0, auto_scan: false, market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: runScanMutate, isPending: false }),
  useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
  useScanReport: () => ({ data: undefined }),
  useStockRegistry: () => ({ data: [] }),
}));

function renderPane() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SterlingKiteEnginePane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
  // Settings default to the "tabs" layout, "Scan" tab active — the Hybrid/Exit Mode/
  // Auto-execute controls live under "Execution" and aren't mounted until selected.
  fireEvent.click(screen.getByRole('button', { name: 'Execution' }));
}

describe('SterlingKiteEnginePane — settings → rescan wiring', () => {
  beforeEach(() => {
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('renders the hybrid weight picker and forces a rescan when it changes', () => {
    renderPane();
    const input = screen.getByTestId('hybrid-weight-input') as HTMLInputElement;
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: '0.7' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ hybrid_st_weight: 0.7 }),
      expect.anything(),
    );
    // Regression coverage: a scan-affecting setting must force an immediate re-scan,
    // not sit unused until the 5-min background auto_scan_loop.
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('forces a rescan when the exit mode changes (the reported bug)', () => {
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: '3R + Signal' }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ exit_mode: 'three_red_signal' }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('does NOT force a rescan for execution-only settings (auto-execute)', () => {
    renderPane();
    fireEvent.click(screen.getByText(/Auto-execute (ON|OFF)/));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ auto_execute: true }),
      expect.anything(),
    );
    // auto_execute can't change which signals appear — forcing a rescan here would
    // just waste a Kite historical-data sweep for no visible effect.
    expect(runScanMutate).not.toHaveBeenCalled();
  });
});
