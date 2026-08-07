import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { TradeRulesPanel } from '../TradeRulesPanel';

const baseCfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  exit_aligned_trail: false,
  price_stop_exit: true,
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'],
  scan_expiries_indices: null,
  scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'],
  scan_stocks: [],
  scan_all_stocks: false,
  auto_execute: false,
  risk_sizing: true,
  risk_pct: 1.0,
  max_lots: 10,
  expiry_square_off_days: 1,
  time_stop_bars: 0,
  stop_mode: 'both',
  protect_manual_orders: true,
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
};

let cfgData: Record<string, unknown> = { ...baseCfg };
const setCfgMutate = vi.fn((_v: unknown, opts?: { onSuccess?: () => void }) => opts?.onSuccess?.());
const runScanMutate = vi.fn();

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfgData }),
  useSetEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
  useRunScan: () => ({ mutate: runScanMutate, isPending: false }),
  useStockRegistry: () => ({ data: [] }),
}));

// NOTE: DirectionalModePanel deliberately NOT mocked here.

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TradeRulesPanel />
    </QueryClientProvider>,
  );
}

describe('duplicate controls on one page', () => {
  beforeEach(() => {
    localStorage.clear();
    cfgData = { ...baseCfg };
    setCfgMutate.mockClear();
    runScanMutate.mockClear();
  });

  it('renders two ADX inputs with different bounds, and both write cfg.adx_min', () => {
    const { container } = renderPanel();
    // open 1b · Vehicle
    fireEvent.click(screen.getByText('1b · Vehicle'));

    const numbers = Array.from(container.querySelectorAll('input[type="number"]')) as HTMLInputElement[];
    const registryAdx = screen.getByTestId('adx-min-input') as HTMLInputElement;
    // The DirectionalModePanel copy: min=5 max=50
    const vehicleAdx = numbers.find((n) => n.min === '5' && n.max === '50');
    const registryAtr = screen.getByTestId('atr-pct-min-input') as HTMLInputElement;
    const vehicleAtr = numbers.find((n) => n.min === '10' && n.max === '95');

    console.log('total number inputs:', numbers.length);
    console.log('registry adx bounds:', registryAdx.min, registryAdx.max, registryAdx.step);
    console.log('vehicle adx present:', !!vehicleAdx, vehicleAdx?.min, vehicleAdx?.max);
    console.log('registry atr bounds:', registryAtr.min, registryAtr.max, registryAtr.step);
    console.log('vehicle atr present:', !!vehicleAtr, vehicleAtr?.min, vehicleAtr?.max);

    expect(vehicleAdx).toBeTruthy();
    expect(vehicleAtr).toBeTruthy();

    // Both write the same key
    fireEvent.change(registryAdx, { target: { value: '3' } });
    expect(setCfgMutate).toHaveBeenCalledWith(expect.objectContaining({ adx_min: 3 }), expect.anything());

    setCfgMutate.mockClear();
    fireEvent.change(vehicleAdx!, { target: { value: '7' } });
    expect(setCfgMutate).toHaveBeenCalledWith(expect.objectContaining({ adx_min: 7 }), expect.anything());
  });

  it('renders two wire_risk_infra toggles', () => {
    const { container } = renderPanel();
    fireEvent.click(screen.getByText('1b · Vehicle'));
    const html = container.innerHTML;
    console.log('occurrences of "Portfolio risk infrastructure":', (html.match(/Portfolio risk infrastructure/g) || []).length);
    console.log('occurrences of "RISK INFRASTRUCTURE":', (html.match(/RISK INFRASTRUCTURE/g) || []).length);
    expect(html).toContain('RISK INFRASTRUCTURE');
    expect(html).toContain('Portfolio risk infrastructure');
  });

  it('with scope=manual the vehicle section is not rendered at all', () => {
    localStorage.setItem('kite_trade_rules_scope', 'manual');
    const { container } = renderPanel();
    console.log('has 1b in manual scope:', container.innerHTML.includes('1b · Vehicle'));
    expect(container.innerHTML.includes('1b · Vehicle')).toBe(false);
  });
});
