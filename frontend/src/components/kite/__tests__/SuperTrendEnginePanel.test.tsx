import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SuperTrendEnginePanel } from '../SuperTrendEnginePanel';

const baseCfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  exit_aligned_trail: false,
  price_stop_exit: true,
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'],
  scan_indices: ['NIFTY 50'],
  scan_stocks: [],
  scan_all_stocks: false,
  auto_execute: false,
  risk_sizing: true,
  risk_pct: 1.0,
  max_lots: 10,
  stop_mode: 'both',
  directional_mode: false,
  vehicle: 'otm_options',
  enabled_vehicles: ['otm_options'],
  itm_depth: 'ITM10',
  target_delta: null,
  futures_expiry: 'near',
  adx_min: null,
  atr_pct_min: null,
  wire_risk_infra: false,
};

let cfgData: Record<string, unknown> = { ...baseCfg };
const setCfgMutate = vi.fn((_vars: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
const runScanMutate = vi.fn();

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfgData }),
  useSetEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useRunScan: () => ({ mutate: runScanMutate, isPending: false }),
}));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SuperTrendEnginePanel />
    </QueryClientProvider>,
  );
}

describe('SuperTrendEnginePanel — strategy mechanics only', () => {
  beforeEach(() => {
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('rescans when the exit mode changes, because the board rows are then stale', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: '3R + Signal' }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ exit_mode: 'three_red_signal' }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('rescans when the exit-aligned trail flips, because it moves the computed stop', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('switch', { name: /anchor stop to exit counter/i }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ exit_aligned_trail: true }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('exposes the trailing-stop-as-a-real-exit switch, which had no coverage before', () => {
    // The UI face of the 2026-08-06 hardening. It could previously have been
    // deleted in a refactor with every test still green.
    renderPanel();
    const toggle = screen.getByRole('switch', { name: /enforce the trailing stop as a real exit/i });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(toggle);

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ price_stop_exit: false }),
      expect.anything(),
    );
  });

  it('changes the trailing style and rescans', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Loose' }));

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ trail_target: 'slow' }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('no longer offers the hybrid weight input, which the engine never read', () => {
    // hybrid_st_weight was written into SterlingKiteEngineConfig and consumed by
    // nothing in the Kite engine, yet it saved, said "Saved" and forced a full
    // rescan. Removing the control is the point of this assertion.
    renderPanel();
    expect(screen.queryByTestId('hybrid-weight-input')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/hybrid weight/i)).not.toBeInTheDocument();
  });

  it('does not own what it scans — it points at Market & Contracts instead', () => {
    renderPanel();
    fireEvent.click(screen.getByText('What this engine scans'));

    // No editable strike or universe control on this page any more…
    expect(screen.queryByRole('checkbox', { name: /Deep ITM/i })).not.toBeInTheDocument();
    // …just pointers to the layer that genuinely owns them.
    expect(screen.getAllByRole('button', { name: /Change in Market & Contracts/ }).length)
      .toBeGreaterThanOrEqual(3);
  });

  it('does not own sizing or the order guards either', () => {
    renderPanel();
    expect(screen.queryByLabelText(/maximum lots/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('daily-loss-input')).not.toBeInTheDocument();
    expect(screen.queryByTestId('expiry-squareoff-input')).not.toBeInTheDocument();
  });
});
