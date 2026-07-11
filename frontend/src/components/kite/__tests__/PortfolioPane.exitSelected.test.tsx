import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { PortfolioPane } from '../PortfolioPane';

const mockMutateAsync = vi.fn();

const NET_POSITIONS = [
  { exchange: 'NSE', tradingsymbol: 'INFY', product: 'MIS', quantity: 10, average_price: 1500, last_price: 1510, pnl: 100, multiplier: 1 },
  { exchange: 'NSE', tradingsymbol: 'TCS', product: 'CNC', quantity: -5, average_price: 3600, last_price: 3590, pnl: 50, multiplier: 1 },
];

vi.mock('../../../hooks/useKite', () => ({
  useConvertKitePosition: () => ({ isPending: false, isError: false, isSuccess: false, mutate: vi.fn() }),
  useKiteHoldings: () => ({ data: [] }),
  useKitePositions: () => ({ data: { net: NET_POSITIONS } }),
  useKiteAuctions: () => ({ data: [] }),
  useInitiateHoldingsAuth: () => ({ isPending: false, mutate: vi.fn() }),
  useKiteLtp: () => ({ data: undefined }),
  usePlaceKiteOrder: () => ({ mutateAsync: mockMutateAsync }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineOpenPositions: () => ({ data: { positions: [] }, isLoading: false }),
  useEngineSignals: () => ({ data: undefined }),
  useCloseEnginePosition: () => ({ mutate: vi.fn(), isPending: false }),
}));

beforeEach(() => {
  mockMutateAsync.mockReset();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

describe('PortfolioPane exitSelected', () => {
  it('does not show the Exit Selected button when nothing is selected', () => {
    render(<PortfolioPane view="positions" />);
    expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument();
  });

  it('shows the Exit Selected button with a count once rows are selected, and fires one MARKET order per selected leg sequentially', async () => {
    mockMutateAsync.mockResolvedValue({ order_id: 'o1' });
    render(<PortfolioPane view="positions" />);

    const checkboxes = screen.getAllByRole('checkbox');
    // checkboxes[0] is "select all"; row checkboxes follow in table order (INFY, TCS).
    fireEvent.click(checkboxes[1]); // INFY

    expect(screen.getByText('Exit Selected (1)')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Exit Selected (1)'));

    expect(window.confirm).toHaveBeenCalledWith('Exit 1 selected position at market price?');
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    expect(mockMutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL', quantity: 10,
      order_type: 'MARKET', product: 'MIS', variety: 'regular', validity: 'DAY',
    }));

    // Selection is cleared once the bulk exit completes.
    await waitFor(() => expect(screen.queryByText(/Exit Selected/)).not.toBeInTheDocument());
  });

  it('does not place any orders when the confirm dialog is dismissed', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PortfolioPane view="positions" />);

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.click(screen.getByText('Exit Selected (1)'));

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });
});
