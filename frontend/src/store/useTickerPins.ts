import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { exchangeFromSymbol, isKiteExchangeEnabled } from '../utils/kiteExchanges';
import { DEFAULT_TILE_STYLE, isTileStyle, type TickerTileStyle } from '../utils/tickerTileStyles';

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
  /** How each pinned instrument is drawn. See utils/tickerTileStyles. */
  tileStyle: TickerTileStyle;
  /**
   * Whether the strip is shown at all.
   *
   * Separate from having no pins: an empty strip invites you to add one, a
   * switched-off strip gives the space back. Turning it off keeps the pins.
   */
  stripEnabled: boolean;
  isPinned: (symbol: string) => boolean;
  pin: (symbol: string) => void;
  unpin: (symbol: string) => void;
  toggle: (symbol: string) => void;
  increaseTileScale: () => void;
  decreaseTileScale: () => void;
  resetTileScale: () => void;
  setTileScale: (value: number) => void;
  setTileStyle: (style: TickerTileStyle) => void;
  setStripEnabled: (enabled: boolean) => void;
  resetDefaults: () => void;
  /** Restore presentation only. Pins are the user's data, not a preference. */
  resetAppearance: () => void;
}

export const useTickerPins = create<TickerPinsState>()(
  persist(
    (set, get) => ({
      pins: DEFAULT_PINS,
      tileScale: DEFAULT_TILE_SCALE,
      tileStyle: DEFAULT_TILE_STYLE,
      stripEnabled: true,
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
      setTileScale: (value) => set({ tileScale: clampTileScale(value) }),
      setTileStyle: (style) => set({ tileStyle: isTileStyle(style) ? style : DEFAULT_TILE_STYLE }),
      setStripEnabled: (enabled) => set({ stripEnabled: !!enabled }),
      resetDefaults: () => set({ pins: DEFAULT_PINS }),
      resetAppearance: () => set({ tileScale: DEFAULT_TILE_SCALE, tileStyle: DEFAULT_TILE_STYLE, stripEnabled: true }),
    }),
    {
      name: 'sterling.kite.tickerPins.v1',
      version: 6,
      migrate: (persisted: unknown) => {
        const state = (persisted ?? {}) as Partial<TickerPinsState>;
        return {
          ...state,
          pins: filterPins(state.pins),
          tileScale: clampTileScale(state.tileScale ?? DEFAULT_TILE_SCALE),
          tileStyle: isTileStyle(state.tileStyle) ? state.tileStyle : DEFAULT_TILE_STYLE,
          // Anyone upgrading had a visible strip, so keep it visible.
          stripEnabled: state.stripEnabled ?? true,
        };
      },
      merge: (persisted, current) => {
        const state = (persisted ?? {}) as Partial<TickerPinsState>;
        return { ...current, ...state, pins: filterPins(state.pins) };
      },
    },
  ),
);
