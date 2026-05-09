import { create } from 'zustand';

const STORAGE_KEY = 'sterling_underlying';
const THEME_KEY = 'sterling_theme';
const MODE_KEY = 'sterling_app_mode';

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

function loadMode(): 'basic' | 'pro' {
  try { return (localStorage.getItem(MODE_KEY) as 'basic' | 'pro') || 'basic'; }
  catch { return 'basic'; }
}

interface StoreState {
  selectedUnderlying: string;
  setSelectedUnderlying: (u: string) => void;
  tradingMode: string;
  setTradingMode: (mode: string) => void;
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  appMode: 'basic' | 'pro';
  setAppMode: (m: 'basic' | 'pro') => void;
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
  appMode: loadMode(),
  setAppMode: (m) => {
    try { localStorage.setItem(MODE_KEY, m); } catch { /* ignore */ }
    set({ appMode: m });
  },
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
export const useAppMode = () => useStore((s) => s.appMode);
export const useSetAppMode = () => useStore((s) => s.setAppMode);
