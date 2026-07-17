import { create } from 'zustand';

type Theme = 'dark' | 'grey' | 'light';
export type TabId = 'sterlingEngine' | 'grok' | 'sterling_v2' | 'positions' | 'backtest' | 'paper' | 'kite';

interface StoreState {
  selectedUnderlying: string;
  setSelectedUnderlying: (u: string) => void;
  tradingMode: string;
  setTradingMode: (mode: string) => void;
  routerMode: 'paper' | 'shadow' | 'live';
  setRouterMode: (mode: 'paper' | 'shadow' | 'live') => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
  appMode: 'basic' | 'pro';
  setAppMode: (m: 'basic' | 'pro') => void;
  engineMode: 'sterling' | 'grok';
  setEngineMode: (m: 'sterling' | 'grok') => void;
  sterlingV2: boolean;
  setSterlingV2: (on: boolean) => void;
  apiHost: string;
  setApiHost: (host: string) => void;
}

export const useStore = create<StoreState>((set) => ({
  selectedUnderlying: 'BTC',
  setSelectedUnderlying: (u) => set({ selectedUnderlying: u }),
  tradingMode: 'swing',
  setTradingMode: (mode) => set({ tradingMode: mode }),
  routerMode: 'paper',
  setRouterMode: (mode) => set({ routerMode: mode }),
  theme: 'dark',
  setTheme: (t) => set({ theme: t }),
  toggleTheme: () => set((state) => {
    const cycle: Theme[] = ['dark', 'grey', 'light'];
    const nextIdx = (cycle.indexOf(state.theme) + 1) % cycle.length;
    return { theme: cycle[nextIdx] };
  }),
  appMode: 'basic',
  setAppMode: (m) => set({ appMode: m }),
  engineMode: 'sterling',
  setEngineMode: (m) => set({ engineMode: m }),
  sterlingV2: false,
  setSterlingV2: (on) => set({ sterlingV2: on }),
  
  // Mobile specific setting: API host URL
  // Default to localhost, but on actual Android emulators it is 10.0.2.2.
  // The user can modify this inside the Settings tab.
  apiHost: 'http://10.0.2.2:8000', 
  setApiHost: (host) => set({ apiHost: host }),
}));

export const useSelectedUnderlying = () => useStore((s) => s.selectedUnderlying);
export const useSetSelectedUnderlying = () => useStore((s) => s.setSelectedUnderlying);
export const useTradingModeStore = () => useStore((s) => s.tradingMode);
export const useSetTradingModeStore = () => useStore((s) => s.setTradingMode);
export const useRouterModeStore = () => useStore((s) => s.routerMode);
export const useSetRouterModeStore = () => useStore((s) => s.setRouterMode);
export const useTheme = () => useStore((s) => s.theme);
export const useSetTheme = () => useStore((s) => s.setTheme);
export const useToggleTheme = () => useStore((s) => s.toggleTheme);
export const useAppMode = () => useStore((s) => s.appMode);
export const useSetAppMode = () => useStore((s) => s.setAppMode);
export const useEngineMode = () => useStore((s) => s.engineMode);
export const useSetEngineMode = () => useStore((s) => s.setEngineMode);
export const useSterlingV2 = () => useStore((s) => s.sterlingV2);
export const useSetSterlingV2 = () => useStore((s) => s.setSterlingV2);
export const useApiHost = () => useStore((s) => s.apiHost);
export const useSetApiHost = () => useStore((s) => s.setApiHost);
