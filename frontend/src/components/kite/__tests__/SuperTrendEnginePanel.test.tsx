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
  useStockRegistry: () => ({
    data: [{ liquidity: 'Very High', stocks: [{ name: 'RELIANCE', label: 'RELIANCE' }] }],
  }),
}));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <SuperTrendEnginePanel />
    </QueryClientProvider>,
  );
}

/**
 * Commit the draft.
 *
 * This panel does not autosave — it edits a draft and writes on Apply, the same
 * way Navigator does. That is the point of the shared draft bar: these are
 * real-money settings, and a stray click on a radio should not reach the engine
 * before you have looked at it. So every assertion about what was SAVED has to
 * apply first; asserting straight after the click only proves the draft moved.
 */
function apply() {
  fireEvent.click(screen.getByRole('button', { name: 'Apply changes' }));
}

describe('SuperTrendEnginePanel — strategy mechanics only', () => {
  beforeEach(() => {
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('holds an edit in the draft until it is applied', () => {
    // The guarantee the Apply step below depends on, pinned on its own so a
    // regression to autosave fails HERE rather than silently passing everywhere.
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Loose' }));

    expect(setCfgMutate).not.toHaveBeenCalled();
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  });

  it('rescans when the exit mode changes, because the board rows are then stale', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: '3R + Signal' }));
    apply();

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ exit_mode: 'three_red_signal' }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('rescans when the exit-aligned trail flips, because it moves the computed stop', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('switch', { name: /anchor stop to exit counter/i }));
    apply();

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
    apply();

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ price_stop_exit: false }),
      expect.anything(),
    );
  });

  it('changes the trailing style and rescans', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Loose' }));
    apply();

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ trail_target: 'slow' }),
      expect.anything(),
    );
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('no longer offers the hybrid weight input, which the engine never read', () => {
    // hybrid_st_weight was written into SterlingKiteEngineConfig and consumed by
    // nothing in the Kite engine, yet it saved, said "Saved" and forced a full
    // rescan. The control went first; the field itself is now gone from
    // EngineConfigModel too, so this guards against it being reintroduced.
    // (The identically-named field on the crypto risk config is a different,
    // live setting — see RiskConfigPanel.)
    renderPanel();
    expect(screen.queryByTestId('hybrid-weight-input')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/hybrid weight/i)).not.toBeInTheDocument();
  });

  it('owns what it scans, rather than pointing at a shared page', () => {
    // The shared "Market & Contracts" page could not express "SuperTrend on the
    // full ladder, Navigator on ATM only", and claimed a sharing the backend
    // only partly does. Each engine now owns its own scan settings.
    renderPanel();
    fireEvent.click(screen.getByText('Contracts'));

    expect(screen.getByRole('checkbox', { name: /Deep ITM/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Confluence/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Change in Market & Contracts/ })).not.toBeInTheDocument();
  });

  it('can be switched off from its own page, the same way Navigator can', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('switch', { name: 'SuperTrend engine' }));
    apply();
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ engine_enabled: false }),
      expect.anything(),
    );
  });

  it('does not claim the engine is OFF while it is still running', () => {
    // The power switch is a draft edit like everything else on this page, but the
    // RUNNING/OFF badge was rendered from that same draft. Flipping the switch
    // repainted the card to "OFF — Not scanning" while nothing had been sent to
    // the server: leave the page without applying and the engine is still scanning
    // and still eligible to auto-execute, having told you it was off.
    renderPanel();
    fireEvent.click(screen.getByRole('switch', { name: 'SuperTrend engine' }));

    expect(screen.getByText('RUNNING')).toBeInTheDocument();
    expect(screen.queryByText('OFF')).not.toBeInTheDocument();
    expect(screen.getByText(/still running until you apply/i)).toBeInTheDocument();
  });

  it('shows the engine as OFF once the server says so', () => {
    cfgData = { ...baseCfg, engine_enabled: false };
    renderPanel();
    expect(screen.getByText('OFF')).toBeInTheDocument();
    expect(screen.queryByText(/until you apply/i)).not.toBeInTheDocument();
  });

  it('does not own sizing or the order guards either', () => {
    renderPanel();
    expect(screen.queryByLabelText(/maximum lots/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('daily-loss-input')).not.toBeInTheDocument();
    expect(screen.queryByTestId('expiry-squareoff-input')).not.toBeInTheDocument();
  });
});
