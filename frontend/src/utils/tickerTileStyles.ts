/**
 * How the pinned-instrument strip presents itself.
 *
 * The strip shows the same six facts however it is styled — symbol, market,
 * last price, absolute change, percent change, and recent shape. What varies is
 * which of them get the space, and that is a real preference rather than a
 * cosmetic one: someone watching two indices wants them large and legible,
 * someone watching twelve wants a tape.
 *
 * Presets are declared here rather than inside the component so the settings
 * screen can describe and preview them without importing the renderer, and so
 * adding one is a data change.
 */

export type TickerTileStyle =
  | 'card' | 'compact' | 'stacked' | 'split' | 'minimal'
  | 'tape' | 'row' | 'badge' | 'spark' | 'heat' | 'range' | 'quote';

export interface TileStyleMeta {
  id: TickerTileStyle;
  label: string;
  /** What a user gains by picking it. Not a restatement of the name. */
  hint: string;
  /** Roughly how many fit across a 1280px strip at scale 1. Drives the preview. */
  perRow: number;
  /** Whether the preset draws the sparkline at all. */
  sparkline: boolean;
}

/**
 * Ordered from most expansive to most compressed, because that is the axis a
 * user is actually choosing along.
 */
export const TILE_STYLES: readonly TileStyleMeta[] = [
  { id: 'card', label: 'Card', hint: 'Price, change and a sparkline in a bordered tile. The default.', perRow: 5, sparkline: true },
  { id: 'quote', label: 'Quote', hint: 'Adds the day’s open, high and low under the price.', perRow: 4, sparkline: true },
  { id: 'spark', label: 'Chart-led', hint: 'The sparkline takes the tile; price sits over it.', perRow: 5, sparkline: true },
  { id: 'range', label: 'Day range', hint: 'A bar showing where the price sits between the day’s low and high.', perRow: 5, sparkline: false },
  { id: 'heat', label: 'Heat', hint: 'Tile tints with the size of the move — scan a dozen at a glance.', perRow: 6, sparkline: false },
  { id: 'stacked', label: 'Stacked', hint: 'Symbol above, price below. No chart.', perRow: 7, sparkline: false },
  { id: 'split', label: 'Split', hint: 'Symbol left, price right, on one line.', perRow: 6, sparkline: false },
  { id: 'compact', label: 'Compact', hint: 'One line: symbol, price, percent.', perRow: 8, sparkline: false },
  { id: 'row', label: 'Table', hint: 'Aligned columns, so prices line up down the strip.', perRow: 6, sparkline: false },
  { id: 'badge', label: 'Badge', hint: 'Small pills. Fits the most instruments on screen.', perRow: 11, sparkline: false },
  { id: 'minimal', label: 'Price only', hint: 'Just the number, coloured by direction. Symbol on hover.', perRow: 12, sparkline: false },
  { id: 'tape', label: 'Ticker tape', hint: 'Scrolls continuously, like an exchange tape. Pauses on hover.', perRow: 0, sparkline: false },
];

export const DEFAULT_TILE_STYLE: TickerTileStyle = 'card';

export const isTileStyle = (v: unknown): v is TickerTileStyle =>
  typeof v === 'string' && TILE_STYLES.some((s) => s.id === v);

export const tileStyleMeta = (id: TickerTileStyle): TileStyleMeta =>
  TILE_STYLES.find((s) => s.id === id) ?? TILE_STYLES[0];
