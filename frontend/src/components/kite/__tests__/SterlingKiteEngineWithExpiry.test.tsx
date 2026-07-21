// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SterlingKiteEngineWithExpiry } from '../SterlingKiteEngineWithExpiry';

const mocks = vi.hoisted(() => ({
  setConfig: vi.fn(),
  runScan: vi.fn(),
  refetchCalendar: vi.fn(),
}));

vi.mock('../SterlingKiteEnginePane', () => ({
  SterlingKiteEnginePane: () => <div>Signal board</div>,
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({
    data: {
      scan_indices: ['NIFTY 50'],
      scan_stocks: ['RELIANCE', 'TCS'],
      scan_all_stocks: false,
      scan_weekly_series_indices: [0],
      scan_monthly_series_indices: [0],
      scan_monthly_series_stocks: [0],
    },
  }),
  useExpiryCalendar: () => ({
    data: {
      as_of: '2026-07-21',
      source: 'kite_instruments',
      indices: [
        {
          name: 'NIFTY', display_name: 'NIFTY 50',
          weekly: ['2026-07-21'], monthly: ['2026-07-28', '2026-08-25'],
        },
        {
          name: 'SENSEX', display_name: 'SENSEX',
          weekly: ['2026-07-23'], monthly: ['2026-07-30', '2026-08-27'],
        },
      ],
      stocks: [
        { name: 'RELIANCE', display_name: 'RELIANCE', weekly: [], monthly: ['2026-07-28'] },
        { name: 'TCS', display_name: 'TCS', weekly: [], monthly: ['2026-07-28'] },
      ],
    },
    isLoading: false,
    isError: false,
    refetch: mocks.refetchCalendar,
  }),
  useSetEngineConfig: () => ({ isPending: false, mutate: mocks.setConfig }),
  useRunScan: () => ({ mutate: mocks.runScan }),
}));

describe('SterlingKiteEngineWithExpiry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(cleanup);

  it('shows only selected instruments with exact Kite-listed contract dates', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'NIFTY · 21st Jul' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'NIFTY JUL · 28th Jul' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '2 STOCKS JUL · 28th Jul' })).toBeTruthy();
    expect(screen.queryByText(/SENSEX ·/)).toBeNull();
    expect(screen.queryByText(/\bW[1-4]\b|\bM[1-2]\b/)).toBeNull();
  });

  it('persists the private rank when an exact dated contract is selected', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'NIFTY AUG · 25th Aug' }));
    expect(mocks.setConfig).toHaveBeenCalledTimes(1);
    expect(mocks.setConfig.mock.calls[0][0]).toMatchObject({
      scan_monthly_series_indices: [0, 1],
    });
  });
});
