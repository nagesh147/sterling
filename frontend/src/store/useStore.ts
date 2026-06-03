import { create } from 'zustand';

const STORAGE_KEY = 'sterling_underlying';
const THEME_KEY = 'sterling_theme';
const MODE_KEY = 'sterling_app_mode';

type Theme = 'dark' | 'grey' | 'light';

function loadTheme(): Theme {
  try { return (localStorage.getItem(THEME_KEY) as Theme) || 'dark'; }
  catch { return 'dark'; }
}

const THEME_CYCLE: Theme[] = ['dark', 'grey', 'light'];

function loadUnderlying(): string {
  try {
    let val = localStorage.getItem(STORAGE_KEY) || 'BTC';
    if (val.includes('-')) {
      val = val.split('-')[0];
      try { localStorage.setItem(STORAGE_KEY, val); } catch { /* ignore */ }
    }
    return val;
  } catch {
    return 'BTC';
  }
}

function loadMode(): 'basic' | 'pro' {
  try { return (localStorage.getItem(MODE_KEY) as 'basic' | 'pro') || 'basic'; }
  catch { return 'basic'; }
}

const ENGINE_KEY = 'sterling_engine_mode';
function loadEngineMode(): 'sterling' | 'grok' {
  try { return (localStorage.getItem(ENGINE_KEY) as 'sterling' | 'grok') || 'sterling'; }
  catch { return 'sterling'; }
}

const V2_KEY = 'sterling_v2_enabled';
function loadV2(): boolean {
  try { return localStorage.getItem(V2_KEY) === 'true'; }
  catch { return false; }
}

const ZOOM_KEY = 'sterling_zoom';
function loadZoom(): number {
  try { return parseFloat(localStorage.getItem(ZOOM_KEY) || '1') || 1; }
  catch { return 1; }
}

interface StoreState {
  selectedUnderlying: string;
  setSelectedUnderlying: (u: string) => void;
  tradingMode: string;
  setTradingMode: (mode: string) => void;
  routerMode: string;
  setRouterMode: (mode: string) => void;
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  appMode: 'basic' | 'pro';
  setAppMode: (m: 'basic' | 'pro') => void;
  engineMode: 'sterling' | 'grok';
  setEngineMode: (m: 'sterling' | 'grok') => void;
  sterlingV2: boolean;
  setSterlingV2: (on: boolean) => void;
  zoomLevel: number;
  setZoomLevel: (z: number) => void;
  resetUI: () => void;
}

export const useStore = create<StoreState>((set) => ({
  selectedUnderlying: loadUnderlying(),
  setSelectedUnderlying: (u) => {
    try { localStorage.setItem(STORAGE_KEY, u); } catch { /* ignore */ }
    set({ selectedUnderlying: u });
  },
  tradingMode: 'swing',
  setTradingMode: (mode) => set({ tradingMode: mode }),
  routerMode: 'live',
  setRouterMode: (mode) => set({ routerMode: mode }),
  theme: loadTheme(),
  setTheme: (t: Theme) => {
    try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
    document.documentElement.setAttribute('data-theme', t);
    set({ theme: t });
  },
  toggleTheme: () => set((s) => {
    const idx  = THEME_CYCLE.indexOf(s.theme);
    const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
    try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
    document.documentElement.setAttribute('data-theme', next);
    return { theme: next };
  }),
  appMode: loadMode(),
  setAppMode: (m) => {
    try { localStorage.setItem(MODE_KEY, m); } catch { /* ignore */ }
    set({ appMode: m });
  },
  engineMode: loadEngineMode(),
  setEngineMode: (m) => {
    try { localStorage.setItem(ENGINE_KEY, m); } catch { /* ignore */ }
    set({ engineMode: m });
  },
  sterlingV2: loadV2(),
  setSterlingV2: (on) => {
    try { localStorage.setItem(V2_KEY, String(on)); } catch { /* ignore */ }
    set({ sterlingV2: on });
  },
  zoomLevel: loadZoom(),
  setZoomLevel: (z) => {
    const clamped = Math.max(0.6, Math.min(2.0, z)); // Min 60%, Max 200%
    try { localStorage.setItem(ZOOM_KEY, clamped.toString()); } catch { /* ignore */ }
    document.documentElement.style.setProperty('--app-zoom', clamped.toString());
    set({ zoomLevel: clamped });
  },
  resetUI: () => {
    try {
      localStorage.setItem(ZOOM_KEY, '1');
      localStorage.setItem(THEME_KEY, 'dark');
    } catch { /* ignore */ }
    document.documentElement.setAttribute('data-theme', 'dark');
    document.documentElement.style.setProperty('--app-zoom', '1');
    set({ zoomLevel: 1, theme: 'dark' });
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

export const useRouterModeStore = () =>
  useStore((s) => s.routerMode);

export const useSetRouterModeStore = () =>
  useStore((s) => s.setRouterMode);

export type { Theme };
export const useTheme = () => useStore((s) => s.theme);
export const useSetTheme = () => useStore((s) => s.setTheme);
export const useToggleTheme = () => useStore((s) => s.toggleTheme);
export const useAppMode = () => useStore((s) => s.appMode);
export const useSetAppMode = () => useStore((s) => s.setAppMode);

export const useZoomLevel = () => useStore((s) => s.zoomLevel);
export const useSetZoomLevel = () => useStore((s) => s.setZoomLevel);
export const useResetUI = () => useStore((s) => s.resetUI);

export const useEngineMode = () => useStore((s) => s.engineMode);
export const useSetEngineMode = () => useStore((s) => s.setEngineMode);

export const useSterlingV2 = () => useStore((s) => s.sterlingV2);
export const useSetSterlingV2 = () => useStore((s) => s.setSterlingV2);
