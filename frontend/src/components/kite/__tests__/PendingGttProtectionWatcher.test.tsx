import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import React from 'react';
import { PendingGttProtectionWatcher } from '../PendingGttProtectionWatcher';
import { useKitePendingProtectionStore } from '../../../store/useKitePendingProtectionStore';

const mockGttMutate = vi.fn();
let mockOrders: any[] = [];
vi.mock('../../../hooks/useKite', () => ({
  useKiteOrders: () => ({ data: mockOrders }),
  usePlaceKiteGtt: () => ({ mutate: mockGttMutate }),
}));

const gtt = () => ({
  trigger_type: 'single' as const, tradingsymbol: 'INFY', exchange: 'NSE',
  last_price: 1500, trigger_values: [1400], orders: [
    { tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL' as const, quantity: 10, order_type: 'LIMIT', product: 'CNC', price: 1400 },
  ],
});

beforeEach(() => {
  useKitePendingProtectionStore.setState({ pending: [] });
  mockGttMutate.mockReset();
  mockOrders = [];
});

describe('PendingGttProtectionWatcher', () => {
  it('does nothing while the pending order has not reached a terminal status', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'OPEN' }];
    render(<PendingGttProtectionWatcher />);
    expect(mockGttMutate).not.toHaveBeenCalled();
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
  });

  it('fires the protective GTT and clears the entry once the order is COMPLETE', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'COMPLETE' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(mockGttMutate).toHaveBeenCalledTimes(1));
    expect(mockGttMutate).toHaveBeenCalledWith(gtt(), expect.objectContaining({ onError: expect.any(Function) }));
    await waitFor(() => expect(useKitePendingProtectionStore.getState().pending).toHaveLength(0));
  });

  it('clears the entry WITHOUT firing the GTT if the order is cancelled or rejected', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'CANCELLED' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(useKitePendingProtectionStore.getState().pending).toHaveLength(0));
    expect(mockGttMutate).not.toHaveBeenCalled();
  });

  it('leaves unrelated pending entries alone', async () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().add({ orderId: 'o2', gtt: gtt() });
    mockOrders = [{ order_id: 'o1', status: 'COMPLETE' }];
    render(<PendingGttProtectionWatcher />);
    await waitFor(() => expect(mockGttMutate).toHaveBeenCalledTimes(1));
    const pending = useKitePendingProtectionStore.getState().pending;
    expect(pending).toHaveLength(1);
    expect(pending[0].orderId).toBe('o2');
  });
});
