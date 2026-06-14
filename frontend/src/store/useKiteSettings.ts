import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface KiteSettingsState {
  chgType: 'close' | 'open';
  showPriceChange: boolean;
  showPriceChangePct: boolean;
  showPriceDirection: boolean;
  showHoldings: boolean;
  showNotes: boolean;
  showGroupColors: boolean;
  sortBy: string;
  setChgType: (t: 'close' | 'open') => void;
  toggleShow: (key: keyof Omit<KiteSettingsState, 'chgType'|'sortBy'|'setChgType'|'toggleShow'|'setSortBy'>) => void;
  setSortBy: (s: string) => void;
}

export const useKiteSettings = create<KiteSettingsState>()(
  persist(
    (set) => ({
      chgType: 'close',
      showPriceChange: true,
      showPriceChangePct: true,
      showPriceDirection: true,
      showHoldings: true,
      showNotes: true,
      showGroupColors: true,
      sortBy: 'Custom',
      setChgType: (t) => set({ chgType: t }),
      toggleShow: (key) => set((state) => ({ [key]: !state[key as keyof KiteSettingsState] })),
      setSortBy: (s) => set({ sortBy: s }),
    }),
    {
      name: 'kite-settings',
    }
  )
);
