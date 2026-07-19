import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { KiteBrandIcon } from '../utils/kiteBrandIcon';

/** Visual style for loaders/spinners across the Kite UI. More styles can be added
 *  here later (e.g. 'aurora', 'pulse'); 'mac' is the Apple-grade default. */
export type LoaderStyle = 'mac' | 'classic' | 'off';

export interface KiteSettingsState {
  /** Mac Kite — Apple-grade physics/motion layer. Off ⇒ stock Kite behaviour. */
  macKite: boolean;
  /** Loader/spinner visual style used for auth overlays, buttons and pending states. */
  loaderStyle: LoaderStyle;
  /** Browser/tab icon shown next to the Sterling title. */
  brandIcon: KiteBrandIcon;
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
  /** Signal-table column order, drag-to-reorder. Two independent groups matching
   *  the table's two flex sections (left flowing group vs. right price-pinned
   *  group) — see SIGNAL_LEFT_COLUMNS/SIGNAL_RIGHT_COLUMNS in
   *  SterlingKiteEnginePane.tsx for the width/label source of truth each key maps to. */
  signalLeftColumnOrder: string[];
  signalRightColumnOrder: string[];
  setMacKite: (on: boolean) => void;
  setLoaderStyle: (s: LoaderStyle) => void;
  setBrandIcon: (icon: KiteBrandIcon) => void;
  setEngineSettingsLayout: (l: 'tabs' | 'cards') => void;
  setChgType: (t: 'close' | 'open') => void;
  toggleShow: (key: keyof Omit<KiteSettingsState, 'chgType'|'sortBy'|'setChgType'|'toggleShow'|'setSortBy'|'legSort'|'setLegSort'|'macKite'|'setMacKite'|'loaderStyle'|'setLoaderStyle'|'brandIcon'|'setBrandIcon'|'engineSettingsLayout'|'setEngineSettingsLayout'|'signalLeftColumnOrder'|'signalRightColumnOrder'|'reorderSignalColumn'>) => void;
  setSortBy: (s: string) => void;
  setLegSort: (sort: { key: string; dir: string }) => void;
  reorderSignalColumn: (group: 'left' | 'right', fromKey: string, toKey: string) => void;
}

export const useKiteSettings = create<KiteSettingsState>()(
  persist(
    (set) => ({
      macKite: false,
      loaderStyle: 'mac',
      brandIcon: 'phoenix',
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
      signalLeftColumnOrder: ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'],
      signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp'],
      setMacKite: (on) => set({ macKite: on }),
      setLoaderStyle: (s) => set({ loaderStyle: s }),
      setBrandIcon: (icon) => set({ brandIcon: icon }),
      setEngineSettingsLayout: (l) => set({ engineSettingsLayout: l }),
      setChgType: (t) => set({ chgType: t }),
      toggleShow: (key) => set((state) => ({ [key]: !state[key as keyof KiteSettingsState] })),
      setSortBy: (s) => set({ sortBy: s }),
      setLegSort: (sort) => set({ legSort: sort }),
      reorderSignalColumn: (group, fromKey, toKey) => set((state) => {
        const field = group === 'left' ? 'signalLeftColumnOrder' : 'signalRightColumnOrder';
        const order = [...state[field]];
        const fromIdx = order.indexOf(fromKey);
        const toIdx = order.indexOf(toKey);
        if (fromIdx === -1 || toIdx === -1) return {};
        order.splice(fromIdx, 1);
        order.splice(toIdx, 0, fromKey);
        return { [field]: order } as Partial<KiteSettingsState>;
      }),
    }),
    {
      name: 'kite-settings',
    }
  )
);
