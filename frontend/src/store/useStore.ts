import { create } from 'zustand';

const STORAGE_KEY = 'sterling_underlying';

function loadUnderlying(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'BTC';
  } catch {
    return 'BTC';
  }
}

interface StoreState {
  selectedUnderlying: string;
  setSelectedUnderlying: (u: string) => void;
}

export const useStore = create<StoreState>((set) => ({
  selectedUnderlying: loadUnderlying(),
  setSelectedUnderlying: (u) => {
    try { localStorage.setItem(STORAGE_KEY, u); } catch { /* ignore */ }
    set({ selectedUnderlying: u });
  },
}));

// Selector hooks — subscribe only to the field you need so unrelated
// state changes do not trigger re-renders in every consumer.
export const useSelectedUnderlying = () =>
  useStore((s) => s.selectedUnderlying);

export const useSetSelectedUnderlying = () =>
  useStore((s) => s.setSelectedUnderlying);
