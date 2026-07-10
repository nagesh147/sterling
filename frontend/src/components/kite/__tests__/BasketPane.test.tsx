import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BasketPane } from '../BasketPane';
import { useKiteBasketStore } from '../../../store/useKiteBasketStore';

const mockMutateAsync = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  usePlaceKiteOrder: () => ({ mutateAsync: mockMutateAsync }),
  useKiteMarginsBasket: () => ({ mutate: vi.fn(), data: null, isPending: false }),
}));

beforeEach(() => {
  useKiteBasketStore.setState({ entries: [] });
  mockMutateAsync.mockReset();
});

describe('BasketPane', () => {
  it('renders one row per staged entry', () => {
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    useKiteBasketStore.getState().add({ symbol: 'TCS', exchange: 'NSE', side: 'SELL', qty: 2, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    render(<BasketPane onClose={vi.fn()} />);
    expect(screen.getByText('INFY')).toBeInTheDocument();
    expect(screen.getByText('TCS')).toBeInTheDocument();
  });

  it('removes a row when its remove button is clicked', () => {
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByTitle('Remove from basket'));
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });

  it('places entries sequentially, not in parallel, and marks each placed on success', async () => {
    let resolveFirst: (v: any) => void = () => {};
    mockMutateAsync
      .mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }))
      .mockImplementationOnce(() => Promise.resolve({ order_id: 'o2' }));
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    useKiteBasketStore.getState().add({ symbol: 'TCS', exchange: 'NSE', side: 'SELL', qty: 2, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });

    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Place Basket'));

    // Second order must not be attempted until the first resolves.
    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    resolveFirst({ order_id: 'o1' });

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const entries = useKiteBasketStore.getState().entries;
      expect(entries[0].status).toBe('placed');
      expect(entries[1].status).toBe('placed');
    });
  });

  it('does not place an order for a row removed while an earlier row is still placing', async () => {
    let resolveFirst: (v: any) => void = () => {};
    mockMutateAsync.mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }));
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    useKiteBasketStore.getState().add({ symbol: 'TCS', exchange: 'NSE', side: 'SELL', qty: 2, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });
    const tcsId = useKiteBasketStore.getState().entries[1].id;

    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Place Basket'));

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1));
    // Remove the second (not-yet-placed) row while the first is still pending.
    useKiteBasketStore.getState().remove(tcsId);
    resolveFirst({ order_id: 'o1' });

    await waitFor(() => {
      expect(useKiteBasketStore.getState().entries).toHaveLength(1);
      expect(useKiteBasketStore.getState().entries[0].symbol).toBe('INFY');
      expect(useKiteBasketStore.getState().entries[0].status).toBe('placed');
    });
    // The removed TCS row must never have reached mutateAsync — only INFY (call 1) should have fired.
    expect(mockMutateAsync).toHaveBeenCalledTimes(1);
  });

  it('marks a failed entry as failed with its error and leaves it in the basket', async () => {
    mockMutateAsync.mockRejectedValueOnce(new Error('Insufficient margin'));
    useKiteBasketStore.getState().add({ symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC', orderType: 'MARKET', price: 0, trigger: 0 });

    render(<BasketPane onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Place Basket'));

    await waitFor(() => {
      expect(useKiteBasketStore.getState().entries[0].status).toBe('failed');
      expect(useKiteBasketStore.getState().entries[0].error).toBe('Insufficient margin');
    });
    // Failed entry stays in the basket for retry/removal.
    expect(useKiteBasketStore.getState().entries).toHaveLength(1);
  });
});
