import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { KiteBrandIcon, KiteBrandIconSize } from '../utils/kiteBrandIcon';

export type LoaderStyle = 'ubuntu' | 'mac' | 'material' | 'windows' | 'gnome' | 'kde' | 'minimal' | 'classic' | 'off';

export type MotionStyle = Exclude<LoaderStyle, 'classic' | 'off'>;

// showHoldings / showNotes / showGroupColors were removed on 2026-08-08: two
// separate toggle UIs wrote them and NOTHING rendered them, so they were three
// checkboxes that did nothing on either the watchlist or the signal board.
type ToggleShowKey = 'showPriceChange' | 'showPriceChangePct' | 'showPriceDirection' | 'showExchange' | 'showLeg';

export interface KiteSettingsState {
  macKite: boolean;
  loaderStyle: LoaderStyle;
  brandIcon: KiteBrandIcon;
  brandIconSize: KiteBrandIconSize;
  recentBrandIcons: KiteBrandIcon[];
  engineSettingsLayout: 'tabs' | 'cards';
  chgType: 'close' | 'open';
  showPriceChange: boolean;
  showPriceChangePct: boolean;
  showPriceDirection: boolean;
  showExchange: boolean;
  showLeg: boolean;
  sortBy: string;
  legSort: { key: string; dir: string };
  signalLeftColumnOrder: string[];
  signalRightColumnOrder: string[];
  /**
   * Signal-table columns the operator has switched off, by column key.
   *
   * Per-column, and specific to the signal table. The five `show*` booleans
   * above are the watchlist panel's and group several columns behind one flag —
   * `premium` alone gates Entry, SL, TSL and Target — so a COLUMNS menu built
   * from them could not name the columns it was actually hiding. Ordering is
   * already per-table here (`signalLeftColumnOrder`); visibility now matches.
   */
  hiddenSignalCols: string[];
  setMacKite: (on: boolean) => void;
  setLoaderStyle: (s: LoaderStyle) => void;
  setBrandIcon: (icon: KiteBrandIcon) => void;
  setBrandIconSize: (size: KiteBrandIconSize) => void;
  setEngineSettingsLayout: (l: 'tabs' | 'cards') => void;
  setChgType: (t: 'close' | 'open') => void;
  toggleShow: (key: ToggleShowKey) => void;
  setSortBy: (s: string) => void;
  setLegSort: (sort: { key: string; dir: string }) => void;
  reorderSignalColumn: (group: 'left' | 'right', fromKey: string, toKey: string) => void;
  toggleSignalCol: (key: string) => void;
  showAllSignalCols: () => void;
  resetSignalTableSettings: () => void;
}

export const useKiteSettings = create<KiteSettingsState>()(
  persist(
    (set) => ({
      macKite: false,
      loaderStyle: 'ubuntu',
      brandIcon: 'phoenix',
      brandIconSize: 'medium',
      recentBrandIcons: [],
      engineSettingsLayout: 'tabs',
      chgType: 'close',
      showPriceChange: true,
      showPriceChangePct: true,
      showPriceDirection: true,
      showExchange: true,
      showLeg: true,
      sortBy: 'Custom',
      legSort: { key: '', dir: '' },
      signalLeftColumnOrder: ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'],
      signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp'],
      hiddenSignalCols: [],
      setMacKite: (on) => set({ macKite: on }),
      setLoaderStyle: (s) => set({ loaderStyle: s === 'classic' ? 'material' : s === 'off' ? 'minimal' : s }),
      setBrandIcon: (icon) => set((state) => ({
        brandIcon: icon,
        recentBrandIcons: [icon, ...state.recentBrandIcons.filter((i) => i !== icon)].slice(0, 5),
      })),
      setBrandIconSize: (size) => set({ brandIconSize: size }),
      setEngineSettingsLayout: (l) => set({ engineSettingsLayout: l }),
      setChgType: (t) => set({ chgType: t }),
      toggleShow: (key) => set((state) => ({ [key]: !state[key] })),
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
      toggleSignalCol: (key) => set((state) => ({
        hiddenSignalCols: state.hiddenSignalCols.includes(key)
          ? state.hiddenSignalCols.filter((k) => k !== key)
          : [...state.hiddenSignalCols, key],
      })),
      showAllSignalCols: () => set({ hiddenSignalCols: [] }),
      resetSignalTableSettings: () => set({
        showPriceChange: true,
        showPriceChangePct: true,
        showPriceDirection: true,
        showExchange: true,
        showLeg: true,
        legSort: { key: '', dir: '' },
        signalLeftColumnOrder: ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'],
        signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp'],
        hiddenSignalCols: [],
      }),
    }),
    {
      name: 'kite-settings',
      version: 3,
      migrate: (persisted: any) => {
        const legacy = persisted?.loaderStyle;
        if (legacy === 'classic') return { ...persisted, loaderStyle: 'material' };
        if (legacy === 'off') return { ...persisted, loaderStyle: 'minimal' };
        if (legacy === 'mac' || legacy === 'ubuntu' || legacy === 'material' || legacy === 'windows' || legacy === 'gnome' || legacy === 'kde' || legacy === 'minimal') return persisted;
        return { ...persisted, loaderStyle: 'ubuntu' };
      },
    },
  ),
);
