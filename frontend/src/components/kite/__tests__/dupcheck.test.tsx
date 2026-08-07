import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { TradeRulesPanel } from '../TradeRulesPanel';

const baseCfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  price_stop_exit: true, strike_moneyness: ['ITM1', 'ATM', 'OTM1'], scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', protect_manual_orders: true, directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: 25, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false,
};
let cfgData: Record<string, unknown> = { ...baseCfg };
const setCfgMutate = vi.fn((_v: unknown, o?: { onSuccess?: () => void }) => o?.onSuccess?.());

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfgData }),
  useSetEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setCfgMutate, isPending: false }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({ data: { rows: [] } }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
  useStockRegistry: () => ({ data: [] }),
}));

describe('duplicate control audit', () => {
  beforeEach(() => { localStorage.clear(); cfgData = { ...baseCfg }; });

  it('counts editable adx/atr/wire controls on the Trade Rules page', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={qc}><TradeRulesPanel /></QueryClientProvider>);

    const numbers = screen.queryAllByRole('spinbutton') as HTMLInputElement[];
    const all = Array.from(document.querySelectorAll('input')) as HTMLInputElement[];
    const withValue25 = all.filter((i) => i.value === '25');
    // eslint-disable-next-line no-console
    console.log('SPINBUTTONS', numbers.length, 'INPUTS_VALUE_25', withValue25.length);
    console.log('MIN_ADX_TEXT_OCCURRENCES', screen.queryAllByText(/Min ADX/i).length,
      'REGISTRY_LABEL', screen.queryAllByLabelText(/Minimum ADX/i).length);
    console.log('ENTRY_QUALITY_HEADING', screen.queryAllByText(/ENTRY QUALITY FILTERS/i).length);
    console.log('RISK_INFRA_HEADING', screen.queryAllByText(/RISK INFRASTRUCTURE/i).length);
    console.log('ATR_TEXT', screen.queryAllByText(/Min ATR/i).length,
      'ATR_REGISTRY', screen.queryAllByLabelText(/Minimum ATR percentile/i).length);
    expect(true).toBe(true);
  });
});
