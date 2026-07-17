import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

// scan_source='both' mixes derivatives rows (with per-leg premium) and spot rows
// (candidate strikes, NO premium) under ONE list header. The header shows the premium
// columns whenever scan_source !== 'spot', so a spot row MUST also emit those cells
// (as '—' placeholders) or its lone Exit cell drifts right and lands under the wrong
// header. This test locks the alignment fix: a spot-source row in 'both' mode renders
// the SL/TSL/Entry/Target placeholder cells so Exit stays in its column.
const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'both',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false, hybrid_st_weight: 0.5,
};

// A spot-source row: candidate strike leg with NO premium_spot/premium_sl/entry_sl.
const spotRow = {
  underlying: 'NIFTY 50', token: 256265, exchange: 'NFO', regime: 'BULL',
  alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
  spot: 24010, stop_loss: 23900, entry_sl: 23890, exit_state: '1/1 red',
  score: 85, timestamp_ms: 1_700_000_000_000, source: 'spot', is_active: true, is_fresh: true,
  legs: [
    {
      moneyness: 'ATM', option_type: 'CE', option_symbol: 'NIFTY25JUN24000CE', strike: 24000,
      expiry: '2026-06-26', lot_size: 75, token: 44001,
      // no premium fields — spot-mode candidate strike
    },
  ],
};

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfg }),
  useSetEngineConfig: () => ({ mutate: vi.fn((_v: unknown, o?: { onSuccess?: () => void }) => o?.onSuccess?.()) }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: 1, scanning: false, scanning_label: '', rows: [spotRow],
      next_scan_ms: 0, auto_scan: false, market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
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
  fireEvent.click(screen.getByTitle('List layout'));
}

describe('SterlingKiteEnginePane — both-mode spot row keeps its columns aligned', () => {
  beforeEach(() => { localStorage.clear(); });

  it('renders premium-column placeholders for a spot row so Exit stays in its column', () => {
    renderPane();
    // Header shows the premium columns (scan_source='both' !== 'spot').
    expect(screen.getByText('Entry (Δpts)')).toBeInTheDocument();
    expect(screen.getByText('SL')).toBeInTheDocument();
    expect(screen.getByText('TSL')).toBeInTheDocument();
    expect(screen.getByText('Target')).toBeInTheDocument();
    // The spot row (no per-leg premium) still renders the SL/TSL placeholder cells —
    // BEFORE the fix these were gated on per-row hasPremium and absent, collapsing the
    // row to a lone Exit cell that landed under the 'Target' header.
    const sl = screen.getByTitle('Initial stop at entry (fast SuperTrend line)');
    expect(sl).toBeInTheDocument();
    expect(sl.textContent).toBe('—');
    expect(screen.getByTitle('Trailing stop — ratchets tighter as SuperTrend lines flip red').textContent).toBe('—');
    // Exit still shows the row's red-counter progress (in its own column).
    expect(screen.getByText('1/1 red')).toBeInTheDocument();
  });
});
