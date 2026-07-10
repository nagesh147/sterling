import { create } from 'zustand';
import type { OrderType, Product, Side } from '../components/kite/orderTicket';

export type BasketEntryStatus = 'idle' | 'placing' | 'placed' | 'failed';

export interface BasketEntry {
  id: string;
  symbol: string;
  exchange: string;
  side: Side;
  qty: number;
  product: Product;
  orderType: OrderType;
  price: number;
  trigger: number;
  status: BasketEntryStatus;
  error?: string;
  orderId?: string;
}

export type NewBasketEntry = Omit<BasketEntry, 'id' | 'status' | 'error' | 'orderId'>;

interface BasketState {
  entries: BasketEntry[];
  add: (entry: NewBasketEntry) => void;
  remove: (id: string) => void;
  update: (id: string, patch: Partial<NewBasketEntry>) => void;
  /** Omitted error/orderId are cleared (set to undefined), not left as-is —
   *  e.g. retrying a failed entry via setStatus(id, 'placing') drops its
   *  stale error message rather than carrying it into the new attempt. */
  setStatus: (id: string, status: BasketEntryStatus, error?: string, orderId?: string) => void;
  clear: () => void;
}

let seq = 0;
const nextId = () => `basket_${++seq}_${Math.random().toString(36).slice(2, 7)}`;

export const useKiteBasketStore = create<BasketState>((set) => ({
  entries: [],
  add: (entry) => set((s) => ({ entries: [...s.entries, { ...entry, id: nextId(), status: 'idle' }] })),
  remove: (id) => set((s) => ({ entries: s.entries.filter((e) => e.id !== id) })),
  update: (id, patch) => set((s) => ({ entries: s.entries.map((e) => (e.id === id ? { ...e, ...patch } : e)) })),
  setStatus: (id, status, error, orderId) => set((s) => ({
    entries: s.entries.map((e) => (e.id === id ? { ...e, status, error, orderId } : e)),
  })),
  clear: () => set({ entries: [] }),
}));
