import { create } from 'zustand';

// Order-related toast notifications, styled like Kite's own order notices.
// Two sources push here: the order-placement mutation hooks (success/rejection,
// paper AND live) and the live order-update WS bridge (fill/cancel/reject).
// Rendered by <KiteNotifications />.
export type NotifKind = 'placed' | 'open' | 'complete' | 'cancelled' | 'rejected' | 'error' | 'info';

export interface KiteNotif {
  id: string;
  kind: NotifKind;
  title: string;
  message: string;
  orderId?: string;
  ts: number;
}

interface State {
  items: KiteNotif[];
  push: (n: Omit<KiteNotif, 'id' | 'ts'>) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const MAX = 4; // keep the stack small; oldest toasts drop off the bottom

export const useKiteNotifications = create<State>((set) => ({
  items: [],
  push: (n) => {
    const id = `kn_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    set((s) => ({ items: [{ ...n, id, ts: Date.now() }, ...s.items].slice(0, MAX) }));
    return id;
  },
  dismiss: (id) => set((s) => ({ items: s.items.filter((x) => x.id !== id) })),
  clear: () => set({ items: [] }),
}));

// Non-hook accessor so mutation hooks (which run outside the React render tree)
// can push toasts without being React components.
export const notifyOrder = (n: Omit<KiteNotif, 'id' | 'ts'>): string =>
  useKiteNotifications.getState().push(n);
