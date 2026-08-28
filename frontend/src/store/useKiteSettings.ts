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
  /**
   * Board capabilities, as choices rather than as one implementation's habits.
   *
   * SuperTrend's table grew three things the shared board never had: draggable
   * column headers, rows that scroll sideways on their own, and order buttons
   * sitting in the row. Keeping them meant keeping a second table; dropping them
   * meant deciding for the operator which ones they could live without.
   *
   * They are settings instead. Every one defaults ON, so nothing changes for
   * anyone who does not go looking, and the shared board can offer the same
   * three to every engine rather than one engine having them by accident of
   * which component it happens to render through.
   */
  boardDragColumns: boolean;
  boardRowScroll: boolean;
  boardRowActions: boolean;
  toggleBoardCapability: (key: BoardCapabilityKey) => void;
  resetSignalTableSettings: () => void;
}

export type BoardCapabilityKey = 'boardDragColumns' | 'boardRowScroll' | 'boardRowActions';

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
      // ON by default: these describe how the board behaves today, so a fresh
      // install and an existing one look the same.
      boardDragColumns: true,
      boardRowScroll: true,
      boardRowActions: true,
      showPriceChange: true,
      showPriceChangePct: true,
      showPriceDirection: true,
      showExchange: true,
      showLeg: true,
      sortBy: 'Custom',
      legSort: { key: '', dir: '' },
      signalLeftColumnOrder: ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'],
      signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp', 'time'],
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
      toggleBoardCapability: (key) => set((state) => ({ [key]: !state[key] })),
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
        boardDragColumns: true,
        boardRowScroll: true,
        boardRowActions: true,
        showPriceChange: true,
        showPriceChangePct: true,
        showPriceDirection: true,
        showExchange: true,
        showLeg: true,
        legSort: { key: '', dir: '' },
        signalLeftColumnOrder: ['exc', 'leg', 'entry', 'sl', 'tsl', 'exit', 'target'],
        signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp', 'time'],
        hiddenSignalCols: [],
      }),
    }),
    {
      name: 'kite-settings',
      version: 5,
      migrate: (persisted: any) => {
        const loaderStyle = (() => {
          const legacy = persisted?.loaderStyle;
          if (legacy === 'classic') return 'material';
          if (legacy === 'off') return 'minimal';
          const known = ['mac', 'ubuntu', 'material', 'windows', 'gnome', 'kde', 'minimal'];
          return known.includes(legacy) ? legacy : 'ubuntu';
        })();
        let next = { ...persisted, loaderStyle };

        // v4 adds the Time column to the signal table's right group.
        //
        // Bumping the default array is not enough: this order is persisted, so
        // anyone who has used the app already has a stored array without 'time'
        // and would simply never see the column. Appended rather than inserted,
        // so an operator's own column arrangement survives.
        const right = next.signalRightColumnOrder;
        if (Array.isArray(right) && !right.includes('time')) {
          next = { ...next, signalRightColumnOrder: [...right, 'time'] };
        }

        // v5 adds the three board capabilities. A stored state predating them has
        // the keys absent, and `undefined` is falsy — so without this every
        // existing user would open the app to find dragging, row scrolling and
        // the in-row order buttons all switched off, having chosen nothing.
        for (const key of ['boardDragColumns', 'boardRowScroll', 'boardRowActions'] as const) {
          if (typeof next[key] !== 'boolean') next = { ...next, [key]: true };
        }
        return next;
      },
    },
  ),
);
