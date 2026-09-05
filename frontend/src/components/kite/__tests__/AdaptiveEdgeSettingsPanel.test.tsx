import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AdaptiveEdgeSettingsPanel } from '../AdaptiveEdgeSettingsPanel';

const { settingsQuery, snapshotQuery, engineConfigQuery, engineSave } = vi.hoisted(() => {
  const settings = {
    enabled: true,
    symbol: 'NIFTY-I',
    symbols: ['NIFTY-I'],
    scan_source: 'spot',
    scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX'],
    scan_stocks: [],
    scan_all_stocks: false,
    scan_stock_contracts: false,
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
  };
  return {
    settingsQuery: { data: { settings, live_trading: false }, isLoading: false, error: null },
    snapshotQuery: { data: { software_complete: true, readiness: [] } },
    /* The engine configuration the scanner and runner actually read, as opposed
       to the legacy settings above. Kept minimal but real: the section renders
       straight off `config`, so a wrong key here shows up as a missing field. */
    engineConfigQuery: {
      data: {
        strategy: {
          id: 'adaptive_edge', name: 'Adaptive Edge', validated: false,
          calibrated_fields: [], calibration: { status: 'UNCALIBRATED — research defaults' },
          headline_finding: 'has no demonstrated edge', what_to_do: 'Run it on paper',
        },
        config: {
          lots: 1, stop_percent: 30, target_multiple: 2, max_positions: 1,
          max_daily_loss: 0, square_off_time: '15:15',
        },
        defaults: {},
        vocabularies: {},
        warnings: ['No parameter in this configuration has been walk-forward calibrated.'],
      },
      isLoading: false, error: null,
    },
    engineSave: vi.fn(),
  };
});

vi.mock('../../../hooks/useAdaptiveEdge', () => ({
  useAdaptiveEdgeSettings: () => settingsQuery,
  useAdaptiveEdgeSnapshot: () => snapshotQuery,
  useSetAdaptiveEdgeSettings: () => ({ mutate: vi.fn(), isPending: false }),
  useAdaptiveEdgeEngineConfig: () => engineConfigQuery,
  useSetAdaptiveEdgeEngineConfig: () => ({ mutate: engineSave, isPending: false }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useStockRegistry: () => ({ data: [] }),
}));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AdaptiveEdgeSettingsPanel />
    </QueryClientProvider>,
  );
}

describe('AdaptiveEdgeSettingsPanel', () => {
  it('has the same dedicated engine sections as SuperTrend', () => {
    renderPanel();
    expect(screen.getByText('Chart source')).toBeInTheDocument();
    expect(screen.getByText('Instruments')).toBeInTheDocument();
    expect(screen.getByText('Contracts')).toBeInTheDocument();
    expect(screen.getByText('Trail tightness')).toBeInTheDocument();
    expect(screen.getByText('Exit rule')).toBeInTheDocument();
    expect(screen.getByText('Spot')).toBeInTheDocument();
    expect(screen.getByText('Strike range')).toBeInTheDocument();
    expect(screen.getByText('Minimum days to expiry')).toBeInTheDocument();
    expect(screen.getByText('Maximum days to expiry')).toBeInTheDocument();
    expect(screen.getByText('Stop points')).toBeInTheDocument();
    expect(screen.getByText('Daily drawdown circuit breaker')).toBeInTheDocument();
    expect(screen.getByLabelText('Enable daily drawdown circuit breaker')).toBeInTheDocument();
    expect(screen.getByLabelText('Flatten at 14:45 IST')).toBeDisabled();
  });
});

describe('AdaptiveEdgeSettingsPanel — engine risk section', () => {
  it('exposes the risk controls that actually reach the engine', () => {
    renderPanel();
    expect(screen.getByText('Risk and session')).toBeInTheDocument();
    for (const label of ['Lots', 'Stop (% of premium)', 'Target multiple',
                         'Max positions', 'Max daily loss', 'Square off']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('opens by default, so the risk numbers are not hidden behind a disclosure', () => {
    renderPanel();
    // Section renders a <details>; children sit in the DOM either way, so the
    // open flag is the only thing that proves an operator can see these.
    const heading = screen.getByText('Risk and session');
    const details = heading.closest('details');
    expect(details).not.toBeNull();
    expect((details as HTMLDetailsElement).open).toBe(true);
  });

  it('states that nothing is calibrated rather than showing bare numbers', () => {
    renderPanel();
    expect(screen.getByText(/walk-forward calibrated/i)).toBeInTheDocument();
  });

  it('summarises the configured risk without opening the section', () => {
    renderPanel();
    expect(screen.getByText(/1 lot · 30% stop · max 1 · flat 15:15/)).toBeInTheDocument();
  });
});

describe('AdaptiveEdgeSettingsPanel — inert sections are declared', () => {
  it('says which sections reach no engine instead of letting a save look real', () => {
    renderPanel();
    // Four legacy sections configure the moving-average strategy this engine
    // replaced. An operator setting a stop there and getting a 200 back would
    // reasonably believe it took effect.
    const notes = screen.getAllByText(/does not reach the engine/);
    expect(notes.length).toBe(4);
  });

  it('points at the section that does drive the live stop', () => {
    renderPanel();
    expect(screen.getAllByText(/Use Risk and session for the live stop/).length).toBeGreaterThan(0);
  });
});
