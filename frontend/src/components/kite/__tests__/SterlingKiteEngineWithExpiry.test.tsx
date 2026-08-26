/**
 * The board's contract summary.
 *
 * The picker itself moved to settings; what is left here has to state what is
 * being scanned without becoming a control again. These tests hold that line:
 * a summary, a health signal, and one link out.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const calendar = vi.hoisted(() => ({
  data: undefined as unknown,
  isLoading: false,
  isError: false,
  isFetching: false,
  refetch: vi.fn(),
}));
const engineConfig = vi.hoisted(() => ({ data: undefined as unknown }));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => engineConfig,
  useExpiryCalendar: () => calendar,
  useRunScan: () => ({ mutate: vi.fn() }),
  usePatchEngineConfig: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

const openSection = vi.hoisted(() => vi.fn());
vi.mock('../config/registry', () => ({ openSettingsSection: openSection }));
vi.mock('../SterlingKiteEnginePane', () => ({
  SterlingKiteEnginePane: () => <div data-testid="board">board</div>,
}));

import { SterlingKiteEngineWithExpiry } from '../SterlingKiteEngineWithExpiry';

const show = () => render(<SterlingKiteEngineWithExpiry onSelectSignal={() => {}} />);

beforeEach(() => {
  openSection.mockClear();
  calendar.data = undefined;
  calendar.isLoading = false;
  calendar.isError = false;
  engineConfig.data = undefined;
});

describe('contract summary on the board', () => {
  it('does not put the picker above the rows any more', () => {
    // It was a 56px banner on top of the table it exists to serve.
    const { container } = show();
    expect(container.querySelector('.sk-expiry-trigger')).toBeNull();
    expect(screen.queryByLabelText('Option contract expiries')).not.toBeInTheDocument();
    expect(screen.getByTestId('board')).toBeInTheDocument();
  });

  it('still says what is being scanned', () => {
    calendar.isLoading = true;
    show();
    expect(screen.getByText(/Loading Kite-listed expiries/)).toBeInTheDocument();
  });

  it('marks a failed calendar rather than showing a confident empty summary', () => {
    calendar.isError = true;
    show();
    expect(screen.getByText('Contract dates unavailable')).toBeInTheDocument();
  });

  it('links to the settings section that now owns the picker', () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: /Change/ }));
    expect(openSection).toHaveBeenCalledWith('engine');
  });

  it('counts selected sets and live dates once a calendar arrives', () => {
    calendar.data = {
      as_of: '2026-08-21',
      source: 'kite_instruments',
      indices: [{
        name: 'NIFTY', display_name: 'NIFTY 50',
        weekly: ['2026-08-27', '2026-09-03', '2026-09-10'],
        monthly: ['2026-08-27', '2026-09-24'],
      }],
      stocks: [],
    };
    engineConfig.data = {
      scan_indices: ['NIFTY'], scan_stocks: [], scan_all_stocks: false,
      scan_weekly_series_indices: [0], scan_monthly_series_indices: [], scan_monthly_series_stocks: [],
    };
    show();
    // 1 weekly rank selected out of 3 listed, plus the monthly groups.
    expect(screen.getByText(/of \d+ expiry sets · \d+ live date/)).toBeInTheDocument();
  });
});
