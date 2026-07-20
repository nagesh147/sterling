import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Symbols added to the horizontal Ticker tiles. This is DECOUPLED
// from the Market Watch list — adding to the watchlist no longer auto-fills the
// ticker. Users explicitly add/remove instruments via "Add/Remove to Ticker"
// from a Market Watch or Signals row’s “more” menu. NIFTY + SENSEX are seeded as defaults.
//
// Stored as EXCHANGE:TRADINGSYMBOL strings (the same key the quote poll uses).
// A zustand store (not per-component useState) so the ticker reacts instantly
// when any pane adds/removes, and the choice persists across reloads.
const DEFAULT_PINS = ['NSE:NIFTY 50', 'BSE:SENSEX'];
const DEFAULT_TILE_SCALE = 1;
const MIN_TILE_SCALE = 0.78;
const MAX_TILE_SCALE = 1.34;
const TILE_SCALE_STEP = 0.08;

function clampTileScale(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_TILE_SCALE;
  return Math.min(MAX_TILE_SCALE, Math.max(MIN_TILE_SCALE, Number(value.toFixed(2))));
}

interface TickerPinsState {
  pins: string[];
  tileScale: number;
  isPinned: (symbol: string) => boolean;
  pin: (symbol: string) => void;
  unpin: (symbol: string) => void;
  toggle: (symbol: string) => void;
  increaseTileScale: () => void;
  decreaseTileScale: () => void;
  resetTileScale: () => void;
  resetDefaults: () => void;
}

export const useTickerPins = create<TickerPinsState>()(
  persist(
    (set, get) => ({
      pins: DEFAULT_PINS,
      tileScale: DEFAULT_TILE_SCALE,
      isPinned: (symbol) => get().pins.includes(symbol),
      pin: (symbol) => set((st) => (st.pins.includes(symbol) ? st : { pins: [...st.pins, symbol] })),
      unpin: (symbol) => set((st) => ({ pins: st.pins.filter((s) => s !== symbol) })),
      toggle: (symbol) =>
        set((st) =>
          st.pins.includes(symbol)
            ? { pins: st.pins.filter((s) => s !== symbol) }
            : { pins: [...st.pins, symbol] },
        ),
      increaseTileScale: () => set((st) => ({ tileScale: clampTileScale((st.tileScale ?? DEFAULT_TILE_SCALE) + TILE_SCALE_STEP) })),
      decreaseTileScale: () => set((st) => ({ tileScale: clampTileScale((st.tileScale ?? DEFAULT_TILE_SCALE) - TILE_SCALE_STEP) })),
      resetTileScale: () => set({ tileScale: DEFAULT_TILE_SCALE }),
      resetDefaults: () => set({ pins: DEFAULT_PINS }),
    }),
    {
      name: 'sterling.kite.tickerPins.v1',
      version: 4,
      migrate: (persisted: unknown) => {
        const state = (persisted ?? {}) as Partial<TickerPinsState>;
        return {
          ...state,
          tileScale: DEFAULT_TILE_SCALE,
        };
      },
    },
  ),
);
