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
  /**
   * When the signal fired.
   *
   * A column, not a line of text on the row above. SuperTrend used to print it
   * inline in the parent header at 14px weight 800 -- the loudest thing on the
   * row -- while the shared board has always kept it as an ordinary
   * right-aligned cell. Same signal, two presentations, and the louder one was
   * shouting the least actionable number in the row.
   */
  // No `sortKey`, deliberately. In SuperTrend these cells sit on the LEGS of a
  // signal, and every leg of one signal fired at the same moment -- there is
  // nothing to order, and a heading that offers a sort it cannot perform is
  // worse than one that does not offer it. The shared board sorts its own
  // `time` column because there the rows are signals, which do differ.
  time: { key: 'time', label: 'Time', width: 78, align: 'right', visibleWhen: 'always', tooltip: 'When the signal fired' },
  /**
   * Buy and Sell, and the chart, as COLUMNS the picker can switch off.
   *
   * They were rendered outside the column grid so they could not be hidden — my
   * reasoning was that losing a trade button by accident is worse than a busy
   * row. The operator asked for the choice, and it is theirs: a board is read far
   * more often than it is traded from, and someone reading one all day should be
   * able to put the order buttons away.
   *
   * Wide enough for two 35px buttons and their gap, and for one icon
   * respectively. They clip rather than push, so a row can never knock the
   * columns beside it out of line.
   */
  trade: { key: 'trade', label: 'Trade', width: 92, align: 'right', visibleWhen: 'always', tooltip: 'Buy and Sell this contract' },
  chart: { key: 'chart', label: 'Chart', width: 34, align: 'right', visibleWhen: 'always', tooltip: "Open this instrument's chart" },
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
  /**
   * The instrument column is sized by {@link instrumentFlex}, not by a constant
   * here: a leg needs a different basis from a heading, so one string cannot
   * serve both. Only its width lives here.
   *
   * It never shrinks. It is the only flexible column on the row, so
   * `flex-shrink: 1` made it absorb ALL the overflow when the board was narrower
   * than its columns — and an option label ("BANKNIFTY 26 Aug 57000 CE", ~166px
   * at this size, plus the best-R and best-delta badges) does not fit in the 150
   * it used to get. The result was the worst possible truncation: the name of the
   * contract clipped while every column of numbers describing it stayed whole.
   */
  instrumentMinWidth: 200,
  /** Type scale, so a cell in one board is the same size as in another. */
  instrumentFontSize: 13,
  cellFontSize: 11,
  /** Parent (signal) row. */
  parentPadding: '10px 12px',
  parentGap: 6,
  parentFontSize: 12,
} as const;

/**
 * The shade a leg row sits on.
 *
 * A leg is recessed one surface below the idea it belongs to. That shade is what
 * separates one row from the next and what makes a group of legs read as a single
 * block, which is why neither table draws a line under a leg as well — the two
 * together give a heavier grid than either alone.
 *
 * It lives here because SuperTrend's bespoke table and the shared `SignalBoard`
 * both need it, and two files each holding the string `var(--k-surface-2)` is two
 * files that can disagree.
 */
export const LEG_BG = 'var(--k-surface-2)';

/**
 * The column-heading type scale.
 *
 * Headings are deliberately much smaller than the data they label — 8.5px bold
 * uppercase with open letter-spacing — because a heading competing with its own
 * column for attention is what makes a dense table hard to scan. This is the
 * single largest thing that made the two signal tables look unrelated:
 * SuperTrend's headings were 12px regular sentence-case, so its header read as
 * another row of content rather than as a label strip.
 *
 * `textTransform` is typed as a literal so it satisfies React's CSSProperties
 * without a cast at each use.
 */
export const HEAD_METRICS = {
  padding: '7px 16px',
  fontSize: 8.5,
  fontWeight: 700,
  letterSpacing: '.06em',
  textTransform: 'uppercase' as const,
} as const;

/**
 * The band that separates one group of rows from the next.
 *
 * The shared board groups by trading day; SuperTrend groups by underlying. The
 * grouping key differs but the band is the same furniture, so it gets the same
 * treatment: a quiet `surface` strip in the same micro-type as the headings,
 * slightly wider letter-spacing because it sits alone on its line.
 *
 * It stays quiet on purpose. Anything the group needs to shout — an active
 * marker, a count — carries its own colour on top of this baseline.
 */
export const DAY_HEAD_METRICS = {
  padding: '4px 12px',
  fontSize: 8.5,
  fontWeight: 700,
  letterSpacing: '.07em',
  textTransform: 'uppercase' as const,
} as const;


/**
 * How far a leg is indented under the idea it belongs to.
 *
 * Load-bearing, not decoration: the indent is the only thing that still says
 * "this is part of that" once the parent row has scrolled off the top. The
 * recessed shade groups legs together but does not tie them to a particular
 * parent.
 *
 * A row indented by this much also narrows its instrument cell by the same
 * amount, so the column's right edge stays under its heading.
 */
export const LEG_INDENT = 14;

/**
 * SuperTrend's column keys, in the shared board's vocabulary.
 *
 * The two name the same columns differently — `sl`/`tsl`/`exc` here against
 * `stop`/`trail`/`exchange` there — because each was written without the other.
 * Renaming either would break a persisted column order or a persisted hidden-set
 * on someone's machine, so the two vocabularies are reconciled by one table
 * instead.
 *
 * It is exhaustive on purpose: a key added to `SIGNAL_*_COLUMNS` without an
 * entry here would silently fail to hide or reorder on the shared renderer.
 */
export const SIGNAL_COL_TO_BOARD = {
  exc: 'exchange', leg: 'leg', entry: 'entry', sl: 'stop', tsl: 'trail',
  // SuperTrend's `exit` is the red-counter PROGRESS, not a realised price, so it
  // maps to `exitState`. Mapping it to `exit` put a counter under a heading that
  // means "where it got out" and lost the counter entirely.
  exit: 'exitState', target: 'target', chg: 'chg', chgPct: 'chgPct', dir: 'dir',
  ltp: 'ltp', time: 'time', trade: 'trade', chart: 'chart',
} as const satisfies Record<string, string>;

export type SignalColKey = keyof typeof SIGNAL_COL_TO_BOARD;

/** The reverse, for turning a board column back into the key the store holds. */
export const BOARD_COL_TO_SIGNAL = Object.fromEntries(
  Object.entries(SIGNAL_COL_TO_BOARD).map(([k, v]) => [v, k]),
) as Record<string, SignalColKey>;

/** Which of SuperTrend's two column runs a key belongs to. */
export function signalColGroup(key: string): 'left' | 'right' {
  return key in SIGNAL_RIGHT_COLUMNS ? 'right' : 'left';
}

/**
 * The instrument cell's flex, for a leg or for anything else.
 *
 * A leg indents by {@link LEG_INDENT} and has to give the same amount back, or
 * its column runs past the heading above it and every cell to the right drifts.
 * That compensation used to live in `minWidth` — which worked only while the
 * cell could shrink. Now that it cannot (`flex-shrink: 0`, so the contract name
 * is never the thing that clips), `minWidth` bounds nothing and the basis is
 * what has to change.
 *
 * Getting this wrong is invisible in a test that renders one row and obvious the
 * moment a leg sits under its parent, 14px out.
 */
export function instrumentFlex(isLeg = false): string {
  return `1 0 ${ROW_METRICS.instrumentMinWidth - (isLeg ? LEG_INDENT : 0)}px`;
}

/**
 * The parent row's own columns.
 *
 * A parent used to lay its pieces out inline — name, then price, then the
 * contract count, then the badges, each starting wherever the last one ended. So
 * every field in the column was at a different x on every row: AXISBANK's price
 * began under BAJFINANCE's name, and the badges landed anywhere at all. Fixed
 * widths make each one a column that actually lines up.
 *
 * The badge track is wide enough for the two that appear together most often
 * (an origin plus one mark, e.g. "PREMIUM" and "TSL exit") and clips beyond
 * that: a row that grows a third badge must not shove the count and the price
 * out of alignment on that row alone.
 */
/**
 * The two tracks that bracket the columns.
 *
 * A row spent width at BOTH ends that the header never reserved: a chevron
 * gutter at the start, where the header rendered a zero-width `<span />`, and the
 * engine's action buttons at the end, pinned with `margin-left: auto`. The
 * instrument is the only flexible column, so it absorbed the whole shortfall and
 * shrank — which pulled every cell left of the heading naming it. `SL` sat above
 * the TSL value, and so on all the way across.
 *
 * Fixed on both sides, so the header and the row agree about where the columns
 * begin and end.
 */
export const EDGE_METRICS = {
  chevronWidth: 15,
  /** Buy + Sell + chart, with their gaps, and never narrower. */
  actionsWidth: 132,
} as const;

export const PARENT_METRICS = {
  priceWidth: 92,
  countWidth: 78,
  badgeWidth: 136,
} as const;
