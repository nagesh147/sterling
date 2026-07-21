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
          weekly: ['2026-07-21', '2026-08-04', '2026-08-11', '2026-08-18'],
          monthly: ['2026-07-28', '2026-08-25'],
        },
        {
          name: 'SENSEX', display_name: 'SENSEX',
          weekly: ['2026-07-23', '2026-08-06', '2026-08-13', '2026-08-20'],
          monthly: ['2026-07-30', '2026-08-27'],
        },
      ],
      stocks: [
        { name: 'RELIANCE', display_name: 'RELIANCE', weekly: [], monthly: ['2026-07-28', '2026-08-25'] },
        { name: 'TCS', display_name: 'TCS', weekly: [], monthly: ['2026-07-28', '2026-08-25'] },
      ],
    },
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: mocks.refetchCalendar,
  }),
  useSetEngineConfig: () => ({
    isPending: false,
    isError: false,
    mutate: mocks.setConfig,
  }),
  useRunScan: () => ({ mutate: mocks.runScan }),
}));

function openContractPicker() {
  const trigger = screen.getByRole('button', { name: 'Manage exact option contracts' });
  fireEvent.click(trigger);
  return trigger;
}

describe('SterlingKiteEngineWithExpiry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(cleanup);

  it('keeps the signal board primary and reveals organized exact dates on demand', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);

    const trigger = screen.getByRole('button', { name: 'Manage exact option contracts' });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(screen.getByText('Signal board')).toBeTruthy();
    expect(screen.getByText('3 of 8 expiry sets · 3 live dates')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'NIFTY · 21st Jul' })).toBeNull();

    openContractPicker();

    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('region', { name: 'Exact option contract picker' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'NIFTY · 21st Jul' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'NIFTY JUL · 28th Jul' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '2 STOCKS JUL · 28th Jul' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /SENSEX ·/ })).toBeNull();
    expect(screen.queryByText(/\bW[1-4]\b|\bM[1-2]\b/)).toBeNull();
  });

  it('persists the private rank when an exact dated contract is selected', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);
    openContractPicker();

    fireEvent.click(screen.getByRole('button', { name: 'NIFTY AUG · 25th Aug' }));
    expect(mocks.setConfig).toHaveBeenCalledTimes(1);
    expect(mocks.setConfig.mock.calls[0][0]).toMatchObject({
      scan_monthly_series_indices: [0, 1],
    });
  });

  it('supports a one-click select-all action without exposing rank codes', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);
    openContractPicker();

    fireEvent.click(screen.getByRole('button', { name: 'Select all Weekly indices' }));
    expect(mocks.setConfig.mock.calls[0][0]).toMatchObject({
      scan_weekly_series_indices: [0, 1, 2, 3],
    });
  });

  it('protects the last selected expiry and exposes the live source refresh', () => {
    render(<SterlingKiteEngineWithExpiry onSelectSignal={vi.fn()} />);
    openContractPicker();

    const nearest = screen.getByRole('button', { name: 'NIFTY · 21st Jul' });
    expect(nearest.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(nearest);
    expect(mocks.setConfig).not.toHaveBeenCalled();

    expect(screen.getByText('Kite instruments · as of 21st Jul')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh Kite contract dates' }));
    expect(mocks.refetchCalendar).toHaveBeenCalledTimes(1);
  });
});
