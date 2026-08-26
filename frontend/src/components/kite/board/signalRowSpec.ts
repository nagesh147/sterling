/**
 * The signal row's geometry and columns, in one place.
 *
 * These numbers were SuperTrend's, hand-typed inside its pane. They are now
 * the spec every board renders against, so "the other boards look like
 * SuperTrend" is enforced by both importing the same table rather than by two
 * sets of literals that agree today and drift next month.
 *
 * Widths are fixed pixels on purpose. A row of tabular numbers only reads as a
 * column if every row agrees where the column starts, and `flex` on a numeric
 * cell makes the decimal point wander with the content.
 */

export type SignalColVisibility = 'always' | 'exchange' | 'leg' | 'premium' | 'chg' | 'chgPct' | 'dir';

export interface SignalColumnDef {
  key: string;
  label: string;
  width: number;
  align: 'left' | 'right';
  sortKey?: string;
  tooltip?: string;
  visibleWhen: SignalColVisibility;
}

/** Flows next to the instrument name, which is the only flexible cell. */
export const SIGNAL_LEFT_COLUMNS: Record<string, SignalColumnDef> = {
  exc: { key: 'exc', label: 'Exc.', width: 40, align: 'left', sortKey: 'exc', visibleWhen: 'exchange' },
  leg: { key: 'leg', label: 'Leg (Δ)', width: 78, align: 'right', sortKey: 'leg', visibleWhen: 'leg' },
  entry: { key: 'entry', label: 'Entry (Δpts)', width: 96, align: 'right', sortKey: 'entry', visibleWhen: 'premium' },
  sl: { key: 'sl', label: 'SL', width: 56, align: 'right', sortKey: 'sl', visibleWhen: 'premium' },
  tsl: { key: 'tsl', label: 'TSL', width: 56, align: 'right', sortKey: 'stop', visibleWhen: 'premium' },
  exit: { key: 'exit', label: 'Exit', width: 58, align: 'right', visibleWhen: 'always', tooltip: 'Progress toward the rule that closes the position' },
  target: { key: 'target', label: 'Target', width: 44, align: 'right', visibleWhen: 'premium', tooltip: 'Where the plan gets out, for an engine that quotes one' },
};

/** Pinned to the far end, after the action buttons. */
export const SIGNAL_RIGHT_COLUMNS: Record<string, SignalColumnDef> = {
  chg: { key: 'chg', label: 'Chg.', width: 50, align: 'right', sortKey: 'chg', visibleWhen: 'chg' },
  chgPct: { key: 'chgPct', label: 'Chg. %', width: 60, align: 'right', sortKey: 'chgPct', visibleWhen: 'chgPct' },
  dir: { key: 'dir', label: '', width: 14, align: 'right', visibleWhen: 'dir' },
  ltp: { key: 'ltp', label: 'LTP', width: 70, align: 'right', sortKey: 'ltp', visibleWhen: 'always' },
};

/**
 * The row's own measurements.
 *
 * Copied off SuperTrend rather than chosen: matching its density is the whole
 * point, and a row two pixels taller reads as a different table.
 */
export const ROW_METRICS = {
  /** Leg row height. */
  legHeight: 41,
  /** Gap between cells. */
  gap: 16,
  /** Horizontal padding on a leg row. */
  legPadding: '0 16px',
  /** The instrument cell is the only one that flexes. */
  instrumentBasis: '1 1 150px',
  instrumentMinWidth: 150,
  /** Type scale, so a cell in one board is the same size as in another. */
  instrumentFontSize: 13,
  cellFontSize: 11,
  /** Parent (signal) row. */
  parentPadding: '10px 12px',
  parentGap: 6,
  parentFontSize: 12,
} as const;
