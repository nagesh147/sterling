import { create } from 'zustand';
import type { PlaceGttBody } from '../types/kite';

export interface PendingProtection {
  orderId: string;
  gtt: PlaceGttBody;
}

interface PendingProtectionState {
  pending: PendingProtection[];
  add: (entry: PendingProtection) => void;
  remove: (orderId: string) => void;
}

/**
 * Orders placed with a Stoploss/Target toggle in OrderWindow need their
 * protective GTT created once the order actually FILLS, not the instant
 * it's accepted — OrderWindow closes immediately on submit, so this state
 * has to outlive the ticket. See PendingGttProtectionWatcher (mounted once
 * near the app root) for the consumer side.
 */
export const useKitePendingProtectionStore = create<PendingProtectionState>((set) => ({
  pending: [],
  add: (entry) => set((s) => ({ pending: [...s.pending, entry] })),
  remove: (orderId) => set((s) => ({ pending: s.pending.filter((p) => p.orderId !== orderId) })),
}));
