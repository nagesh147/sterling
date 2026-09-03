/**
 * The settings panel's contract with the user: every field says whether it is
 * still the engine's default, and a moved field restores on one click.
 *
 * The defaults come from the server, never from a second copy in the client —
 * that drift is the bug class this codebase keeps hitting — so these tests feed
 * the panel a server payload and assert off it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import React from 'react';
import { NiftyOrbOptionsSettings } from '../NiftyOrbOptionsSettings';
import type { OrbConfig } from '../../hooks/useOrbConfig';

const DEFAULTS: OrbConfig = {
  enabled: false,
  underlying: 'NIFTY',
  scan_indices: ['NIFTY'],
  scan_stocks: [],
  scan_all_stocks: false,
  scan_stock_contracts: true,
  interval_minutes: 5,
  opening_range_minutes: 15,
  entry_start: '09:30',
  entry_end: '12:00',
  min_breakout_atr: 0.15,
  volume_multiplier: 1.15,
  vwap_slope_lookback: 3,
  trend_lookback: 20,
  atr_period: 14,
  stop_buffer_atr: 0.25,
  target_r: 2.0,
  option_moneyness: 'ATM',
  option_steps_itm: 1,
  max_risk_inr: 3000,
  max_trades_per_day: 3,
  avoid_expiry_day: true,
  expiry_selection: 'nearest',
  expiry_dte_min: 0,
  expiry_dte_max: 7,
  execution_broker: 'kite',
  data_source: 'kite',
  max_spread_pct: 1.5,
  min_option_volume: 1000,
  min_open_interest: 50000,
  max_quote_staleness_s: 30,
  risk_free_rate: 0.065,
  truedata_use_ticks: true,
  truedata_use_oi: true,
  truedata_use_bid_ask: true,
  truedata_use_quote_freshness: true,
};

const setConfig = vi.fn();
let serverConfig: OrbConfig;

vi.mock('../../hooks/useOrbConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../hooks/useOrbConfig')>();
  return {
    ...actual,
    useOrbConfig: () => ({
      data: { config: serverConfig, defaults: DEFAULTS, supported_data_sources: ['kite', 'truedata'], execution_brokers: ['kite'] },
      isLoading: false,
      error: null,
    }),
    useSetOrbConfig: () => ({ mutate: setConfig, isPending: false, isError: false, error: null }),
  };
});

// The instruments picker fetches the F&O registry; this suite is about default
// indication, so keep it rendering bare.
vi.mock('../../hooks/useSterlingKiteEngine', () => ({
  useStockRegistry: () => ({ data: [{ liquidity: 'Very High', stocks: [{ name: 'RELIANCE' }] }] }),
  useEngineConfig: () => ({ data: {} }),
}));

/** The badge sits in the same field row as its label. */
function fieldRow(label: string): HTMLElement {
  const node = screen.getByText(label).closest('div');
  if (!node) throw new Error(`no row for ${label}`);
  return node.parentElement as HTMLElement;
}

beforeEach(() => {
  setConfig.mockClear();
  serverConfig = { ...DEFAULTS };
});

describe('NiftyOrbOptionsSettings — default indication', () => {
  it('says every setting is at default when nothing has moved', () => {
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByText(/Every setting is at the engine default/)).toBeInTheDocument();
    expect(screen.queryByText(/changed · default/)).not.toBeInTheDocument();
  });

  it('badges a moved numeric field with its default and restores it on click', () => {
    serverConfig = { ...DEFAULTS, volume_multiplier: 1.4 };
    render(<NiftyOrbOptionsSettings />);

    const badge = screen.getByRole('button', { name: /changed · default 1.15/ });
    fireEvent.click(badge);

    expect(screen.queryByRole('button', { name: /changed · default 1.15/ })).not.toBeInTheDocument();
    expect(within(fieldRow('Volume confirmation')).getByText('default')).toBeInTheDocument();
  });

  it('badges a moved choice, not only the numbers', () => {
    serverConfig = { ...DEFAULTS, option_moneyness: 'ITM' };
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByRole('button', { name: /changed · default ATM/ })).toBeInTheDocument();
  });

  it('badges a moved switch in words a user reads, not true/false', () => {
    serverConfig = { ...DEFAULTS, avoid_expiry_day: false };
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByRole('button', { name: /changed · default skipped/ })).toBeInTheDocument();
  });

  it('treats the entry window as one setting and restores both ends together', () => {
    serverConfig = { ...DEFAULTS, entry_end: '14:00' };
    render(<NiftyOrbOptionsSettings />);

    fireEvent.click(screen.getByRole('button', { name: /changed · default 09:30–12:00/ }));

    expect(screen.getByDisplayValue('09:30')).toBeInTheDocument();
    expect(screen.getByDisplayValue('12:00')).toBeInTheDocument();
  });

  it('counts only the settings that actually moved', () => {
    serverConfig = { ...DEFAULTS, volume_multiplier: 1.4, target_r: 3 };
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByText(/2 settings differ from the engine defaults/)).toBeInTheDocument();
  });

  it('does not count the power switch as a changed setting', () => {
    serverConfig = { ...DEFAULTS, enabled: true };
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByText(/Every setting is at the engine default/)).toBeInTheDocument();
  });
});

describe('NiftyOrbOptionsSettings — section summaries', () => {
  it('reports a change under the section that owns it, not every section', () => {
    serverConfig = { ...DEFAULTS, target_r: 3 };
    render(<NiftyOrbOptionsSettings />);

    // 'Stop and target' owns target_r; 'Signal thresholds' must stay quiet.
    expect(screen.getByText('all at default')).toBeInTheDocument();
    expect(screen.getByText('1 changed from default')).toBeInTheDocument();
  });

  it('labels Advanced by how many settings it holds, like every other panel', () => {
    render(<NiftyOrbOptionsSettings />);
    expect(screen.getByText(/^Advanced · 9$/)).toBeInTheDocument();
  });
});

describe('NiftyOrbOptionsSettings — saving', () => {
  it('sends only what moved, so a concurrent edit elsewhere survives', () => {
    render(<NiftyOrbOptionsSettings />);

    fireEvent.click(screen.getByRole('switch', { name: /Avoid expiry-day entries/ }));
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/ }));

    expect(setConfig).toHaveBeenCalledTimes(1);
    expect(setConfig.mock.calls[0][0]).toEqual({ avoid_expiry_day: false });
  });

  it('resets to defaults without changing whether the engine is running', () => {
    serverConfig = { ...DEFAULTS, enabled: true, volume_multiplier: 1.4 };
    render(<NiftyOrbOptionsSettings />);

    // Reset is destructive, so the bar asks for a second, confirming click.
    fireEvent.click(screen.getByRole('button', { name: /Reset to defaults/i }));
    fireEvent.click(screen.getByRole('button', { name: /Click again to confirm reset/i }));

    expect(setConfig).toHaveBeenCalledTimes(1);
    expect(setConfig.mock.calls[0][0]).toMatchObject({ volume_multiplier: 1.15, enabled: true });
  });
});
