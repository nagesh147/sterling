import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { SharedScanSetupPanel } from '../SharedScanSetupPanel';

const setCfg = vi.fn();
const runScan = vi.fn();
let engineCfg: Record<string, unknown> | undefined;
let navScopeMode: 'shared' | 'custom' = 'shared';
let navEnabled = true;

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: engineCfg }),
  useSetEngineConfig: () => ({ mutate: setCfg, isPending: false }),
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

describe('SharedScanSetupPanel', () => {
  beforeEach(() => {
    setCfg.mockClear();
    runScan.mockClear();
    navScopeMode = 'shared';
    navEnabled = true;
    engineCfg = {
      scan_indices: ['NIFTY 50', 'NIFTY BANK'], scan_stocks: ['RELIANCE'],
      scan_all_stocks: false, scan_source: 'spot',
    };
  });

  it('presents itself as shared rather than as one engine\'s settings', () => {
    render(<SharedScanSetupPanel />);
    expect(screen.getByText('Shared by both engines')).toBeInTheDocument();
    expect(screen.getByText('Instruments')).toBeInTheDocument();
    expect(screen.getByText('Contracts to scan')).toBeInTheDocument();
  });

  it('shows both engines following it when Navigator is on shared scope', () => {
    render(<SharedScanSetupPanel />);
    expect(screen.getByText('SuperTrend')).toBeInTheDocument();
    expect(screen.getByText('Navigator')).toBeInTheDocument();
    expect(screen.queryByText(/affect SuperTrend only/)).not.toBeInTheDocument();
  });

  it('is honest when Navigator has opted out — it no longer claims to drive both', () => {
    navScopeMode = 'custom';
    render(<SharedScanSetupPanel />);
    expect(screen.getByText('Navigator — on its own')).toBeInTheDocument();
    expect(screen.getByText(/affect SuperTrend only/)).toBeInTheDocument();
  });

  it('editing the universe saves once and triggers a rescan', () => {
    render(<SharedScanSetupPanel />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'FINNIFTY' }));
    expect(setCfg).toHaveBeenCalledTimes(1);
    const [payload, opts] = setCfg.mock.calls[0];
    expect(payload.scan_indices).toContain('NIFTY FIN SERVICE');
    opts.onSuccess?.();
    expect(runScan).toHaveBeenCalledTimes(1);
  });

  it('never lets the index list be emptied to nothing', () => {
    engineCfg = { ...engineCfg, scan_indices: ['NIFTY 50'] };
    render(<SharedScanSetupPanel />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'NIFTY' }));
    const [payload] = setCfg.mock.calls[0];
    expect(payload.scan_indices).toEqual(['NIFTY 50']); // falls back rather than clearing
  });

  it('changing the contracts source saves it', () => {
    render(<SharedScanSetupPanel />);
    fireEvent.click(screen.getByRole('radio', { name: /Confluence/ }));
    const [payload] = setCfg.mock.calls[0];
    expect(payload.scan_source).toBe('confluence');
  });

  it('hides the stock picker when all F&O stocks is on', () => {
    engineCfg = { ...engineCfg, scan_all_stocks: true };
    render(<SharedScanSetupPanel />);
    expect(screen.queryByRole('checkbox', { name: 'RELIANCE' })).not.toBeInTheDocument();
  });
});
