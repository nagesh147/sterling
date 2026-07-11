import { describe, it, expect, beforeEach } from 'vitest';
import { useKitePendingProtectionStore } from './useKitePendingProtectionStore';
import type { PlaceGttBody } from '../types/kite';

const gtt = (): PlaceGttBody => ({
  trigger_type: 'single', tradingsymbol: 'INFY', exchange: 'NSE',
  last_price: 1500, trigger_values: [1400], orders: [
    { tradingsymbol: 'INFY', exchange: 'NSE', transaction_type: 'SELL', quantity: 10, order_type: 'LIMIT', product: 'CNC', price: 1400 },
  ],
});

beforeEach(() => {
  useKitePendingProtectionStore.setState({ pending: [] });
});

describe('useKitePendingProtectionStore', () => {
  it('adds a pending protection entry keyed by order id', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
    expect(useKitePendingProtectionStore.getState().pending[0].orderId).toBe('o1');
  });

  it('removes a pending entry by order id', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().add({ orderId: 'o2', gtt: gtt() });
    useKitePendingProtectionStore.getState().remove('o1');
    const pending = useKitePendingProtectionStore.getState().pending;
    expect(pending).toHaveLength(1);
    expect(pending[0].orderId).toBe('o2');
  });

  it('removing a non-existent id is a no-op', () => {
    useKitePendingProtectionStore.getState().add({ orderId: 'o1', gtt: gtt() });
    useKitePendingProtectionStore.getState().remove('does-not-exist');
    expect(useKitePendingProtectionStore.getState().pending).toHaveLength(1);
  });
});
