import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { EngineConfigurationPanel } from '../EngineConfigurationPanel';

// Full EngineConfigModel fixture including the exit / auto-exec guard knobs. The
// component reads these with `?? default` fallbacks, but the fixture carries the real
// backend defaults so the assertions exercise the true starting state.
const baseCfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  exit_aligned_trail: false,
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_source: 'spot',
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
  expiry_square_off_days: 1,
  time_stop_bars: 0,
  stop_mode: 'both',
  directional_mode: false,
  vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'],
  itm_depth: 'ITM10',
  target_delta: null,
  futures_expiry: 'near',
  adx_min: null,
  atr_pct_min: null,
  block_entry_minutes_before_close: 0,
  max_spread_pct: null,
  min_oi: null,
  max_daily_loss_pct: null,
  wire_risk_infra: false,
  hybrid_st_weight: 0.5,
};

// Mutable config the mocked useEngineConfig reads on each call. Tests seed it (before
// render) so a controlled input starts at a real value — clearing it then produces a
// genuine value change and fires onChange (a static mock never updates cfg, so a
// field already showing "" can't be "cleared" again).
let cfgData: Record<string, unknown> = { ...baseCfg };

const setCfgMutate = vi.fn((_vars: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
const runScanMutate = vi.fn();

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfgData }),
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
  useStockRegistry: () => ({ data: [] }),
}));

function renderPanel(section: 'exit' | 'risk') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <EngineConfigurationPanel />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText(section === 'exit' ? 'Exit & Protection' : 'Risk & Safeguards'));
  if (section === 'risk') fireEvent.click(screen.getByText(/Advanced auto-execution guards/));
}

describe('EngineConfigurationPanel — exit / auto-exec guard controls', () => {
  beforeEach(() => {
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('exposes the exit-aligned-trail toggle and rescans when it flips (changes the computed stop)', () => {
    renderPanel('exit');
    const sw = screen.getByRole('switch', { name: /anchor stop to exit counter/i });
    fireEvent.click(sw);

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ exit_aligned_trail: true }),
      expect.anything(),
    );
    // It alters scanner._trail_stop_value → the displayed stop/is_active change,
    // so it must force an immediate rescan (same class as trail_target).
    expect(runScanMutate).toHaveBeenCalledTimes(1);
  });

  it('exposes the expiry square-off input and patches it WITHOUT a rescan (auto-exec-only)', () => {
    renderPanel('risk');
    const input = screen.getByTestId('expiry-squareoff-input') as HTMLInputElement;
    expect(input.value).toBe('1');
    fireEvent.change(input, { target: { value: '2' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ expiry_square_off_days: 2 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('exposes the time-stop input (opt-in, default 0) and patches without a rescan', () => {
    renderPanel('risk');
    const input = screen.getByTestId('time-stop-input') as HTMLInputElement;
    expect(input.value).toBe('0');
    fireEvent.change(input, { target: { value: '48' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ time_stop_bars: 48 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('exposes the session no-entry-before-close guard and patches without a rescan', () => {
    renderPanel('risk');
    const input = screen.getByTestId('block-entry-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '15' } });

    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ block_entry_minutes_before_close: 15 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('sets the liquidity guards (max spread %, min OI) from empty, without a rescan', () => {
    renderPanel('risk');
    const spread = screen.getByTestId('max-spread-input') as HTMLInputElement;
    fireEvent.change(spread, { target: { value: '5' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_spread_pct: 5 }),
      expect.anything(),
    );

    const oi = screen.getByTestId('min-oi-input') as HTMLInputElement;
    fireEvent.change(oi, { target: { value: '100' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ min_oi: 100 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('clears the liquidity guards to null (off) when the field is emptied', () => {
    cfgData = { ...baseCfg, max_spread_pct: 5, min_oi: 100 };
    renderPanel('risk');
    const spread = screen.getByTestId('max-spread-input') as HTMLInputElement;
    expect(spread.value).toBe('5');
    fireEvent.change(spread, { target: { value: '' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_spread_pct: null }),
      expect.anything(),
    );
  });

  it('sets the INR daily-loss breaker from empty, without a rescan', () => {
    renderPanel('risk');
    const input = screen.getByTestId('daily-loss-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '2' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_daily_loss_pct: 2 }),
      expect.anything(),
    );
    expect(runScanMutate).not.toHaveBeenCalled();
  });

  it('clears the INR daily-loss breaker to null (off) when emptied', () => {
    cfgData = { ...baseCfg, max_daily_loss_pct: 2 };
    renderPanel('risk');
    const input = screen.getByTestId('daily-loss-input') as HTMLInputElement;
    expect(input.value).toBe('2');
    fireEvent.change(input, { target: { value: '' } });
    expect(setCfgMutate).toHaveBeenCalledWith(
      expect.objectContaining({ max_daily_loss_pct: null }),
      expect.anything(),
    );
  });
});
