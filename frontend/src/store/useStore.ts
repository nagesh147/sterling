import { create } from 'zustand';

interface StoreState {
  selectedUnderlying: string;
  setSelectedUnderlying: (u: string) => void;
}

export const useStore = create<StoreState>((set) => ({
  selectedUnderlying: 'BTC',
  setSelectedUnderlying: (u) => set({ selectedUnderlying: u }),
}));
