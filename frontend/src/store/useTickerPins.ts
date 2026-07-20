import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { exchangeFromSymbol, isKiteExchangeEnabled } from '../utils/kiteExchanges';

// Stored as EXCHANGE:TRADINGSYMBOL strings. Defaults stay in the NSE family;
// other venues become available when enabled in Kite display settings.
const DEFAULT_PINS = ['NSE:NIFTY 50', 'NSE:NIFTY BANK'];
const DEFAULT_TILE_SCALE = 1;
const MIN_TILE_SCALE = 0.78;
const MAX_TILE_SCALE = 1.34;
const TILE_SCALE_STEP = 0.08;

function clampTileScale(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_TILE_SCALE;
  return Math.min(MAX_TILE_SCALE, Math.max(MIN_TILE_SCALE, Number(value.toFixed(2))));
}

function exchangeAllowed(symbol: string): boolean {
  return isKiteExchangeEnabled(exchangeFromSymbol(symbol));
}

function filterPins(pins: unknown): string[] {
  if (!Array.isArray(pins)) return [...DEFAULT_PINS];
  const filtered = pins.filter((symbol): symbol is string => typeof symbol === 'string' && exchangeAllowed(symbol));
  return filtered.length ? Array.from(new Set(filtered)) : [...DEFAULT_PINS];
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
      pin: (symbol) => {
        if (!exchangeAllowed(symbol)) return;
        set((st) => (st.pins.includes(symbol) ? st : { pins: [...st.pins, symbol] }));
      },
      unpin: (symbol) => set((st) => ({ pins: st.pins.filter((s) => s !== symbol) })),
      toggle: (symbol) => {
        if (!exchangeAllowed(symbol) && !get().pins.includes(symbol)) return;
        set((st) =>
          st.pins.includes(symbol)
            ? { pins: st.pins.filter((s) => s !== symbol) }
            : { pins: [...st.pins, symbol] },
        );
      },
      increaseTileScale: () => set((st) => ({ tileScale: clampTileScale((st.tileScale ?? DEFAULT_TILE_SCALE) + TILE_SCALE_STEP) })),
      decreaseTileScale: () => set((st) => ({ tileScale: clampTileScale((st.tileScale ?? DEFAULT_TILE_SCALE) - TILE_SCALE_STEP) })),
      resetTileScale: () => set({ tileScale: DEFAULT_TILE_SCALE }),
      resetDefaults: () => set({ pins: DEFAULT_PINS }),
    }),
    {
      name: 'sterling.kite.tickerPins.v1',
      version: 5,
      migrate: (persisted: unknown) => {
        const state = (persisted ?? {}) as Partial<TickerPinsState>;
        return {
          ...state,
          pins: filterPins(state.pins),
          tileScale: clampTileScale(state.tileScale ?? DEFAULT_TILE_SCALE),
        };
      },
      merge: (persisted, current) => {
        const state = (persisted ?? {}) as Partial<TickerPinsState>;
        return { ...current, ...state, pins: filterPins(state.pins) };
      },
    },
  ),
);
