import { create } from 'zustand';

const STORAGE_KEY = 'sterling_underlying';
const THEME_KEY = 'sterling_theme';

function loadTheme(): 'dark' | 'light' {
  try { return (localStorage.getItem(THEME_KEY) as 'dark' | 'light') || 'dark'; }
  catch { return 'dark'; }
}

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
  tradingMode: string;
  setTradingMode: (mode: string) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

export const useStore = create<StoreState>((set) => ({
  selectedUnderlying: loadUnderlying(),
  setSelectedUnderlying: (u) => {
    try { localStorage.setItem(STORAGE_KEY, u); } catch { /* ignore */ }
    set({ selectedUnderlying: u });
  },
  tradingMode: 'swing',
  setTradingMode: (mode) => set({ tradingMode: mode }),
  theme: loadTheme(),
  toggleTheme: () => set((s) => {
    const next = s.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
    document.documentElement.setAttribute('data-theme', next);
    return { theme: next };
  }),
}));

export const useSelectedUnderlying = () =>
  useStore((s) => s.selectedUnderlying);

export const useSetSelectedUnderlying = () =>
  useStore((s) => s.setSelectedUnderlying);

export const useTradingModeStore = () =>
  useStore((s) => s.tradingMode);

export const useSetTradingModeStore = () =>
  useStore((s) => s.setTradingMode);

export const useTheme = () => useStore((s) => s.theme);
export const useToggleTheme = () => useStore((s) => s.toggleTheme);
