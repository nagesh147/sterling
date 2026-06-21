import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** Visual style for loaders/spinners across the Kite UI. More styles can be added
 *  here later (e.g. 'aurora', 'pulse'); 'mac' is the Apple-grade default. */
export type LoaderStyle = 'mac' | 'classic' | 'off';

export interface KiteSettingsState {
  /** Mac Kite — Apple-grade physics/motion layer. Off ⇒ stock Kite behaviour. */
  macKite: boolean;
  /** Loader/spinner visual style used for auth overlays, buttons and pending states. */
  loaderStyle: LoaderStyle;
  /** SuperTrend settings-drawer layout: tab bar vs collapsible cards (chosen in Connect). */
  engineSettingsLayout: 'tabs' | 'cards';
  chgType: 'close' | 'open';
  showPriceChange: boolean;
  showPriceChangePct: boolean;
  showPriceDirection: boolean;
  showHoldings: boolean;
  showNotes: boolean;
  showGroupColors: boolean;
  showExchange: boolean;
  showLeg: boolean;
  sortBy: string;
  legSort: { key: string; dir: string };
  setMacKite: (on: boolean) => void;
  setLoaderStyle: (s: LoaderStyle) => void;
  setEngineSettingsLayout: (l: 'tabs' | 'cards') => void;
  setChgType: (t: 'close' | 'open') => void;
  toggleShow: (key: keyof Omit<KiteSettingsState, 'chgType'|'sortBy'|'setChgType'|'toggleShow'|'setSortBy'|'legSort'|'setLegSort'|'macKite'|'setMacKite'|'loaderStyle'|'setLoaderStyle'|'engineSettingsLayout'|'setEngineSettingsLayout'>) => void;
  setSortBy: (s: string) => void;
  setLegSort: (sort: { key: string; dir: string }) => void;
}

export const useKiteSettings = create<KiteSettingsState>()(
  persist(
    (set) => ({
      macKite: false,
      loaderStyle: 'mac',
      engineSettingsLayout: 'tabs',
      chgType: 'close',
      showPriceChange: true,
      showPriceChangePct: true,
      showPriceDirection: true,
      showHoldings: true,
      showNotes: true,
      showGroupColors: true,
      showExchange: true,
      showLeg: true,
      sortBy: 'Custom',
      legSort: { key: '', dir: '' },
      setMacKite: (on) => set({ macKite: on }),
      setLoaderStyle: (s) => set({ loaderStyle: s }),
      setEngineSettingsLayout: (l) => set({ engineSettingsLayout: l }),
      setChgType: (t) => set({ chgType: t }),
      toggleShow: (key) => set((state) => ({ [key]: !state[key as keyof KiteSettingsState] })),
      setSortBy: (s) => set({ sortBy: s }),
      setLegSort: (sort) => set({ legSort: sort }),
    }),
    {
      name: 'kite-settings',
    }
  )
);
