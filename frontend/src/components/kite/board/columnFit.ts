/**
 * Which columns survive when the board is narrower than its columns.
 *
 * This is the half of "the same app on every monitor" that scaling cannot do.
 * Matching the layout everywhere holds the content constant and lets text size
 * follow the panel; matching text size — what YouTube and essentially every
 * other site does, by rendering 1:1 and trusting the platform's scale factor —
 * holds text constant and lets the content vary. You cannot have both, and the
 * second only works if the table actually adapts instead of clipping.
 *
 * So columns drop by priority rather than the row growing a horizontal
 * scrollbar. A trader scanning a board reads left to right and stops; a column
 * pushed off the right edge behind a scrollbar is not "still available", it is
 * invisible. Dropping it and saying so in the column picker is honest.
 *
 * Nothing here overrides the user. Auto-dropping only ever removes columns
 * from what is already on screen; it never restores one that was switched off
 * by hand.
 */

/**
 * Drop order when room runs short — lowest goes first.
 *
 * Ordered by what a trader needs to act on a row. Price and the instrument it
 * belongs to are the row's reason for existing; the risk ladder (entry, stop)
 * comes next; provenance and conviction are the first things a scanning eye
 * can do without.
 */
export const COLUMN_PRIORITY: Readonly<Record<string, number>> = {
  instrument: 1000, // never dropped
  ltp: 900,         // never dropped
  // Buy and Sell outrank the numbers they act on. They were absent from this
  // table, so `priorityOf` gave them the fallback 10 — BELOW `engine` — which
  // made them the first two columns dropped on every board narrower than the
  // full set. They were in `BOARD_COLUMNS`, offered in the picker, ticked on, and
  // never once drawn in the signals dock: "partially working", because the same
  // buttons do appear on a wide enough window.
  trade: 95,
  entry: 90,
  stop: 85,
  time: 80,
  status: 75,
  // Just above the trailing stop, which is the cheapest thing left worth losing.
  //
  // Measured on the real 982px dock rather than reasoned about: at 58 it lost to
  // `target`, and freeing 78px by hiding Time handed the room to `leg` instead —
  // so the column existed, was ticked on, and could never appear at any realistic
  // dock width. The observed cutoff sits between 75 and 70, so this is the lowest
  // rank that actually shows it. It briefly sat at 94, which worked but claimed
  // the chart outranks entry and stop; on a narrower dock that would shed the
  // risk ladder to keep a 34px icon, which is the wrong way round.
  chart: 76,
  trail: 70,
  leg: 65,
  exit: 60,
  target: 55,
  exchange: 50,
  score: 40,
  risk: 35,
  qty: 30,
  engine: 20,
};

/** Columns that stay whatever happens: without them a row says nothing. */
export const ESSENTIAL_COLUMNS: readonly string[] = ['instrument', 'ltp'];

const priorityOf = (id: string) => COLUMN_PRIORITY[id] ?? 10;

export interface FitOptions {
  /** The instrument cell flexes; this is the least it may be squeezed to. */
  minInstrument?: number;
  /** Gap between cells. */
  gap?: number;
  /** Row padding, both sides combined. */
  padding?: number;
  /** Width claimed by anything that is not a column — action buttons. */
  reserve?: number;
}

export interface FitResult<T> {
  columns: T[];
  /** What was dropped for width, most recently dropped last. */
  dropped: T[];
  /** Width the surviving set needs. */
  required: number;
}

/**
 * The widest subset of `columns` that fits `availableWidth`.
 *
 * A non-positive width means "not measured yet" — every column is kept, so a
 * board renders complete on first paint rather than flashing a stripped-down
 * table before the measurement lands.
 */
export function fitColumns<T extends { id: string; width: number }>(
  columns: readonly T[],
  availableWidth: number,
  options: FitOptions = {},
): FitResult<T> {
  const { minInstrument = 150, gap = 16, padding = 32, reserve = 0 } = options;

  const widthOf = (c: T) => (c.id === 'instrument' ? minInstrument : c.width);
  const required = (set: readonly T[]) =>
    set.reduce((sum, c) => sum + widthOf(c), 0)
    + Math.max(0, set.length - 1) * gap
    + padding
    + reserve;

  const keep = [...columns];
  const dropped: T[] = [];
  if (!(availableWidth > 0)) return { columns: keep, dropped, required: required(keep) };

  while (required(keep) > availableWidth) {
    // The lowest-priority column still standing, ignoring the essentials.
    let victim = -1;
    for (let i = 0; i < keep.length; i += 1) {
      if (ESSENTIAL_COLUMNS.includes(keep[i].id)) continue;
      if (victim === -1 || priorityOf(keep[i].id) < priorityOf(keep[victim].id)) victim = i;
    }
    if (victim === -1) break; // only essentials left; let them overflow
    dropped.push(keep[victim]);
    keep.splice(victim, 1);
  }

  return { columns: keep, dropped, required: required(keep) };
}
