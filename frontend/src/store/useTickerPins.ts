import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Symbols pinned to the top-bar horizontal ticker tiles. This is now DECOUPLED
// from the Market Watch list — adding to the watchlist no longer auto-fills the
// ticker. Users explicitly pin instruments from a Market Watch row's "more"
// menu or a Signals row, and NIFTY + SENSEX are seeded as sensible defaults.
//
// Stored as EXCHANGE:TRADINGSYMBOL strings (the same key the quote poll uses).
// A zustand store (not per-component useState) so the ticker reacts instantly
// when any pane pins/unpins, and the choice persists across reloads.
const DEFAULT_PINS = ['NSE:NIFTY 50', 'BSE:SENSEX'];

interface TickerPinsState {
  pins: string[];
  isPinned: (symbol: string) => boolean;
  pin: (symbol: string) => void;
  unpin: (symbol: string) => void;
  toggle: (symbol: string) => void;
  resetDefaults: () => void;
}

export const useTickerPins = create<TickerPinsState>()(
  persist(
    (set, get) => ({
      pins: DEFAULT_PINS,
      isPinned: (symbol) => get().pins.includes(symbol),
      pin: (symbol) => set((st) => (st.pins.includes(symbol) ? st : { pins: [...st.pins, symbol] })),
      unpin: (symbol) => set((st) => ({ pins: st.pins.filter((s) => s !== symbol) })),
      toggle: (symbol) =>
        set((st) =>
          st.pins.includes(symbol)
            ? { pins: st.pins.filter((s) => s !== symbol) }
            : { pins: [...st.pins, symbol] },
        ),
      resetDefaults: () => set({ pins: DEFAULT_PINS }),
    }),
    { name: 'sterling.kite.tickerPins.v1' },
  ),
);
