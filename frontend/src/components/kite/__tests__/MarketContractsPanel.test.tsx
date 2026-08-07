import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { MarketContractsPanel } from '../MarketContractsPanel';

const setCfg = vi.fn();
const runScan = vi.fn();
let engineCfg: Record<string, unknown> | undefined;
let navScopeMode: 'shared' | 'custom' = 'shared';
let navEnabled = true;

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: engineCfg }),
  useSetEngineConfig: () => ({ mutate: setCfg, isPending: false }),
  usePatchEngineConfig: () => ({ mutate: setCfg, isPending: false }),
  useRunScan: () => ({ mutate: runScan, isPending: false }),
  useStockRegistry: () => ({
    data: [{ liquidity: 'Very High', stocks: [{ name: 'RELIANCE', label: 'RELIANCE' }, { name: 'TCS', label: 'TCS' }] }],
  }),
}));

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({
    data: { record: { config: { scan_scope_mode: navScopeMode, enabled: navEnabled } } },
  }),
}));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MarketContractsPanel />
    </QueryClientProvider>,
  );
}

const baseCfg = {
  scan_indices: ['NIFTY 50', 'NIFTY BANK'],
  scan_stocks: ['RELIANCE'],
  scan_all_stocks: false,
  scan_source: 'spot',
  strike_moneyness: ['ITM1', 'ATM', 'OTM1'],
  scan_expiries: ['weekly', 'monthly'],
  scan_expiries_indices: null,
};

describe('MarketContractsPanel', () => {
  beforeEach(() => {
    setCfg.mockClear();
    runScan.mockClear();
    navScopeMode = 'shared';
    navEnabled = true;
    engineCfg = { ...baseCfg };
  });

  it('presents itself as the market layer, not as one engine’s settings', () => {
    renderPanel();
    expect(screen.getByText('Market & contracts')).toBeInTheDocument();
    expect(screen.getByText('Instruments')).toBeInTheDocument();
    expect(screen.getByText('Contracts')).toBeInTheDocument();
  });

  it('shows both engines following it when Navigator is on shared scope', () => {
    renderPanel();
    expect(screen.getByText('SuperTrend')).toBeInTheDocument();
    expect(screen.getByText('Navigator')).toBeInTheDocument();
    expect(screen.queryByText(/affect SuperTrend only/)).not.toBeInTheDocument();
  });

  it('is honest when Navigator has opted out — it no longer claims to drive both', () => {
    navScopeMode = 'custom';
    renderPanel();
    expect(screen.getByText('Navigator — on its own')).toBeInTheDocument();
    expect(screen.getByText(/affect SuperTrend only/)).toBeInTheDocument();
  });

  it('editing the universe saves once and triggers a rescan', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('checkbox', { name: 'FINNIFTY' }));
    expect(setCfg).toHaveBeenCalledTimes(1);
    const [payload, opts] = setCfg.mock.calls[0];
    expect(payload.scan_indices).toContain('NIFTY FIN SERVICE');
    opts.onSuccess?.();
    expect(runScan).toHaveBeenCalledTimes(1);
  });

  it('never lets the index list be emptied to nothing', () => {
    engineCfg = { ...baseCfg, scan_indices: ['NIFTY 50'] };
    renderPanel();
    fireEvent.click(screen.getByRole('checkbox', { name: 'NIFTY' }));
    const [payload] = setCfg.mock.calls[0];
    expect(payload.scan_indices).toEqual(['NIFTY 50']); // falls back rather than clearing
  });

  it('changing the signal source saves it and rescans', () => {
    renderPanel();
    fireEvent.click(screen.getByRole('radio', { name: /Confluence/ }));
    const [payload, opts] = setCfg.mock.calls[0];
    expect(payload.scan_source).toBe('confluence');
    opts.onSuccess?.();
    expect(runScan).toHaveBeenCalledTimes(1);
  });

  it('hides the stock picker when all F&O stocks is on', () => {
    engineCfg = { ...baseCfg, scan_all_stocks: true };
    renderPanel();
    expect(screen.queryByRole('checkbox', { name: 'RELIANCE' })).not.toBeInTheDocument();
  });

  it('now owns strike coverage, which used to sit on the SuperTrend page', () => {
    // Navigator reads strike_moneyness through the same call the scanner does
    // (navigator/runtime.py:568), so editing it from a page titled "SuperTrend
    // Engine" moved Navigator too, silently.
    renderPanel();
    fireEvent.click(screen.getByText('Contracts'));
    fireEvent.click(screen.getByRole('checkbox', { name: /Deep ITM/i }));

    const [payload, opts] = setCfg.mock.calls[0];
    expect(payload.strike_moneyness).toEqual(expect.arrayContaining(['ITM5', 'ITM4']));
    opts.onSuccess?.();
    expect(runScan).toHaveBeenCalledTimes(1);
  });

  it('now owns the index expiries too', () => {
    renderPanel();
    fireEvent.click(screen.getByText('Contracts'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Weekly' }));

    const [payload] = setCfg.mock.calls[0];
    expect(payload.scan_expiries_indices).toEqual(['monthly']);
  });

  it('states the stock-expiry constraint instead of faking a ticked checkbox', () => {
    // The backend validator discards any submitted value and always returns
    // ["monthly"] (schemas.py:458), so a permanently-ticked checkbox read like
    // a setting the user had turned on.
    renderPanel();
    fireEvent.click(screen.getByText('Contracts'));
    expect(screen.getByText(/listed monthly only/i)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /monthly stock/i })).not.toBeInTheDocument();
  });

  it('marks every setting on this page as affecting manual and automatic trades alike', () => {
    renderPanel();
    // Strike coverage decides which contract an automatic BUY hits AND which
    // legs the board offers you to buy by hand.
    expect(screen.getByText('Signal source').closest('div')).toHaveTextContent('MANUAL + AUTO');
  });
});
