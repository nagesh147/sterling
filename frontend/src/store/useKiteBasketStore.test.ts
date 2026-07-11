import { describe, it, expect, beforeEach } from 'vitest';
import { useKiteBasketStore, type NewBasketEntry } from './useKiteBasketStore';

const entry = (overrides: Partial<NewBasketEntry> = {}): NewBasketEntry => ({
  symbol: 'INFY', exchange: 'NSE', side: 'BUY', qty: 1, product: 'CNC',
  orderType: 'MARKET', price: 0, trigger: 0,
  ...overrides,
});

beforeEach(() => {
  useKiteBasketStore.setState({ entries: [] });
});

describe('useKiteBasketStore', () => {
  it('adds an entry with a generated id and idle status', () => {
    useKiteBasketStore.getState().add(entry());
    const entries = useKiteBasketStore.getState().entries;
    expect(entries).toHaveLength(1);
    expect(entries[0].symbol).toBe('INFY');
    expect(entries[0].status).toBe('idle');
    expect(entries[0].id).toBeTruthy();
  });

  it('removes an entry by id', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().remove(id);
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });

  it('updates a field on an entry by id', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().update(id, { qty: 5 });
    expect(useKiteBasketStore.getState().entries[0].qty).toBe(5);
  });

  it('sets an entry status', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().setStatus(id, 'placing');
    expect(useKiteBasketStore.getState().entries[0].status).toBe('placing');
    useKiteBasketStore.getState().setStatus(id, 'failed', 'Insufficient margin');
    expect(useKiteBasketStore.getState().entries[0].status).toBe('failed');
    expect(useKiteBasketStore.getState().entries[0].error).toBe('Insufficient margin');
  });

  it('clears a stale error when transitioning away from failed', () => {
    useKiteBasketStore.getState().add(entry());
    const id = useKiteBasketStore.getState().entries[0].id;
    useKiteBasketStore.getState().setStatus(id, 'failed', 'Insufficient margin');
    expect(useKiteBasketStore.getState().entries[0].error).toBe('Insufficient margin');
    useKiteBasketStore.getState().setStatus(id, 'placing');
    expect(useKiteBasketStore.getState().entries[0].status).toBe('placing');
    expect(useKiteBasketStore.getState().entries[0].error).toBeUndefined();
  });

  it('clears all entries', () => {
    useKiteBasketStore.getState().add(entry());
    useKiteBasketStore.getState().add(entry({ symbol: 'TCS' }));
    useKiteBasketStore.getState().clear();
    expect(useKiteBasketStore.getState().entries).toHaveLength(0);
  });
});
