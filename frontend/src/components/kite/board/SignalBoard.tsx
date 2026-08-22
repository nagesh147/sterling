/**
 * The signal board every engine renders through.
 *
 * Layout is a CSS grid whose column template is computed once from the visible
 * column set, so every row aligns with the header without any of the horizontal
 * scroll-syncing the old table needed. Columns an engine cannot fill are not
 * rendered as empty cells — they are dropped from the template entirely, so a
 * board never shows a run of dashes where another engine happens to have data.
 *
 * Rows are grouped by trading day. Sections stick to the top while their day is
 * on screen, which is the only part of a long scroll that tells you where you
 * are.
 */
import React from 'react';
import { k, tint } from '../../../styles/kiteUI';
import {
  ACTIONABLE, ENGINE_TAG, LIVE_BUCKET, STATUS_LABEL, STATUS_RANK, flattenSignals, groupByDay, markLegs,
  sessionDayLabel, trailBreached,
  type BoardSignal, type BoardStatus, type EngineId,
} from './boardTypes';
import { StatCard, StatCardGrid } from './StatCard';
import { Tip } from '../InfoTooltip';

export type ColumnId =
  | 'instrument' | 'engine' | 'status' | 'exchange' | 'leg'
  | 'ltp' | 'entry' | 'stop' | 'trail' | 'target' | 'exit'
  | 'qty' | 'risk' | 'score' | 'time';

interface ColumnDef {
  id: ColumnId;
  label: string;
  /** Grid track. Instrument flexes; the rest are fixed so numbers line up. */
  width: string;
  align: 'left' | 'right';
  hint?: string;
}

/**
 * Every column the board can show, in reading order: what it is, then what it
 * is worth now, then where it gets out, then how big, then when.
 */
export const COLUMNS: readonly ColumnDef[] = [
  { id: 'instrument', label: 'Instrument', width: 'minmax(150px, 1.6fr)', align: 'left' },
  { id: 'engine', label: 'Engine', width: '48px', align: 'left', hint: 'Which engine produced this signal' },
  { id: 'status', label: 'Status', width: '78px', align: 'left', hint: 'Armed = valid setup, not yet entered' },
  { id: 'exchange', label: 'Exc', width: '44px', align: 'left', hint: 'Exchange the contract trades on' },
  { id: 'leg', label: 'Leg', width: 'minmax(96px, 1fr)', align: 'left', hint: 'Strike and expiry of the traded contract' },
  { id: 'ltp', label: 'LTP', width: '74px', align: 'right', hint: 'Last traded price of the instrument' },
  { id: 'entry', label: 'Entry', width: '74px', align: 'right', hint: 'Price the position is taken at' },
  { id: 'stop', label: 'SL', width: '74px', align: 'right', hint: 'Hard stop set at entry — the original risk' },
  { id: 'trail', label: 'TSL', width: '74px', align: 'right', hint: 'Where the trailing stop has ratcheted to' },
  { id: 'target', label: 'Exit', width: '74px', align: 'right', hint: 'Where the plan gets out — the profit objective, where the engine quotes one' },
  { id: 'exit', label: 'Exited', width: '74px', align: 'right', hint: 'Where it actually got out, once it has' },
  { id: 'qty', label: 'Qty', width: '64px', align: 'right', hint: 'Units, not lots' },
  { id: 'risk', label: 'At risk', width: '82px', align: 'right', hint: 'Rupees lost if the stop is honoured' },
  { id: 'score', label: 'Score', width: '56px', align: 'right', hint: 'Engine conviction. Not comparable across engines' },
  { id: 'time', label: 'Time', width: '92px', align: 'right', hint: 'When the signal fired. Marked stale when the quote behind it has aged out' },
];

export interface SortState {
  column: ColumnId;
  direction: 'asc' | 'desc';
}

/** The board's default: most recent first, which is what a scan produces. */
export const DEFAULT_SORT: SortState = { column: 'time', direction: 'desc' };

/**
 * What each column sorts on.
 *
 * Returning a string sorts alphabetically, a number numerically, and null
 * always sinks to the bottom regardless of direction — a row with no stop is
 * not "the smallest stop", it is a row that has nothing to compare.
 */
function sortKey(signal: BoardSignal, column: ColumnId): string | number | null {
  switch (column) {
    case 'instrument': return signal.underlying;
    case 'engine': return signal.engine;
    case 'status': return STATUS_RANK[signal.status];
    case 'exchange': return signal.instrument.exchange;
    case 'leg': return signal.instrument.symbol;
    case 'ltp': return signal.levels.ltp;
    case 'entry': return signal.levels.entry;
    case 'stop': return signal.levels.stop;
    case 'trail': return signal.levels.trail;
    case 'target': return signal.levels.target;
    case 'exit': return signal.levels.exit;
    case 'qty': return signal.sizing.quantity;
    case 'risk': return signal.sizing.atRiskInr;
    case 'score': return signal.score;
    case 'time': return signal.atMs;
    default: return null;
  }
}

/**
 * Orders rows within one day.
 *
 * Sorting deliberately does NOT cross day boundaries: the day grouping is the
 * board's primary organisation, and a sort that reshuffled rows out of their
 * session would answer a question nobody asked. Sort by risk and you get the
 * largest risk of today, then the largest of yesterday.
 */
export function sortSignals(signals: readonly BoardSignal[], sort: SortState): BoardSignal[] {
  const factor = sort.direction === 'asc' ? 1 : -1;
  return [...signals].sort((a, b) => {
    const ka = sortKey(a, sort.column);
    const kb = sortKey(b, sort.column);
    // Missing values sink, both ways, so flipping direction never promotes a
    // row that has nothing to say to the top of the board.
    if (ka == null && kb == null) return 0;
    if (ka == null) return 1;
    if (kb == null) return -1;
    if (typeof ka === 'string' || typeof kb === 'string') {
      return String(ka).localeCompare(String(kb)) * factor;
    }
    return (ka - kb) * factor;
  });
}

/**
 * Clicking a column sorts it; clicking the same one again flips it.
 *
 * A new column starts descending for numbers and ascending for names, because
 * "biggest first" and "A first" are what each is usually reached for.
 */
export function nextSort(current: SortState, column: ColumnId): SortState {
  if (current.column === column) {
    return { column, direction: current.direction === 'asc' ? 'desc' : 'asc' };
  }
  const alphabetical = column === 'instrument' || column === 'leg' || column === 'exchange' || column === 'engine';
  return { column, direction: alphabetical ? 'asc' : 'desc' };
}

function SortMark({ direction }: { direction: 'asc' | 'desc' | null }) {
  return (
    <span
      aria-hidden
      style={{
        display: 'inline-flex', flexDirection: 'column', gap: 1, marginLeft: 3,
        verticalAlign: 'middle', opacity: direction ? 1 : 0, transition: 'opacity .12s ease',
      }}
    >
      <span style={{
        width: 0, height: 0, borderLeft: '3px solid transparent', borderRight: '3px solid transparent',
        borderBottom: `3px solid ${direction === 'asc' ? k.text : 'transparent'}`,
      }} />
      <span style={{
        width: 0, height: 0, borderLeft: '3px solid transparent', borderRight: '3px solid transparent',
        borderTop: `3px solid ${direction === 'desc' ? k.text : 'transparent'}`,
      }} />
    </span>
  );
}

/** Statuses that earn a coloured pill. The rest are the board's normal state. */
const NOTABLE_STATUS = new Set<BoardStatus>(['armed', 'weakening', 'error']);

/** Engine-accent names resolved to the theme's tokens. */
const ORIGIN_TONE: Record<NonNullable<BoardSignal['origin']>['tone'], string> = {
  brand: 'var(--k-brand)', blue: k.blue, green: k.green,
  purple: k.purple, amber: k.amber, dim: k.dim,
};

const STATUS_TONE: Record<BoardStatus, string> = {
  armed: k.blue,
  running: k.green,
  weakening: k.amber,
  ended: k.dim,
  watching: k.dim,
  error: k.red,
};

const num = (v: number | null | undefined, dp = 2) =>
  v == null || !Number.isFinite(v) ? '—' : v.toFixed(dp);

export const inr = (v: number | null | undefined) =>
  v == null || !Number.isFinite(v) ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`;

/** Older than this and a quote is not describing the market any more. */
const STALE_AFTER_S = 15;

const hhmm = (ms: number | null) =>
  ms == null ? '—' : new Date(ms).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });

function Chevron({ open }: { open: boolean }) {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
      aria-hidden style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .14s ease', flexShrink: 0 }}>
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Pill({ tone, children, title }: { tone: string; children: React.ReactNode; title?: string }) {
  return (
    <span title={title} style={{
      fontSize: 8.5, fontWeight: 700, letterSpacing: '.04em', color: tone,
      background: tint(tone, 12), border: `1px solid ${tint(tone, 35)}`,
      borderRadius: 3, padding: '1px 4px', whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  );
}

/**
 * What kind of contract the row is, for the pill beside the symbol.
 *
 * A parent row has no contract of its own, so it borrows its legs' type when
 * they agree and says nothing when they do not. It must not fall back to the
 * security kind: the parent of an LT signal was reading "LTINDEX · LONG",
 * and LT is a stock.
 */
function contractLabel(signal: BoardSignal): string | null {
  if (signal.instrument.optionType) return signal.instrument.optionType;
  const legs = signal.children ?? [];
  if (legs.length) {
    const types = new Set(legs.map((l) => l.instrument.optionType).filter(Boolean));
    return types.size === 1 ? [...types][0]! : null;
  }
  return signal.instrument.kind === 'option' ? null : signal.instrument.kind.toUpperCase();
}

/** The value of one column for one signal, plus how to colour it. */
function cellContent(
  signal: BoardSignal,
  id: ColumnId,
  onOpenDetail?: (signal: BoardSignal) => void,
  marks?: ReadonlySet<'bestRR' | 'bestDelta'>,
): { node: React.ReactNode; color?: string } {
  const dirTone = signal.direction === 'long' ? k.green : k.red;
  switch (id) {
    case 'instrument':
      return {
        node: (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
            {onOpenDetail ? (
              // A real button, not a click handler on a span: the row itself
              // expands on click, so the label needs its own focus stop and its
              // own announced action or the two are indistinguishable.
              <button
                type="button"
                className="sb-name"
                title={`Open ${signal.underlying} detail`}
                aria-label={`Open ${signal.underlying} detail`}
                onClick={(e) => { e.stopPropagation(); onOpenDetail(signal); }}
                style={{
                  border: 'none', background: 'transparent', padding: 0, font: 'inherit',
                  fontWeight: 700, color: k.text, cursor: 'pointer',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0,
                }}
              >
                {signal.underlying}
              </button>
            ) : (
              <span style={{ fontWeight: 700, color: k.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {signal.underlying}
              </span>
            )}
            <Pill tone={dirTone} title={`${signal.direction} ${contractLabel(signal) ?? 'position'}`}>
              {[contractLabel(signal), signal.direction.toUpperCase()].filter(Boolean).join(' · ')}
            </Pill>
            {signal.origin && (
              <Tip text={`${signal.origin.label} — ${signal.origin.hint}`}>
                <span tabIndex={0} style={{
                  fontSize: 8, fontWeight: 700, letterSpacing: '.04em', cursor: 'help',
                  color: ORIGIN_TONE[signal.origin.tone], border: `1px solid ${tint(ORIGIN_TONE[signal.origin.tone], 34)}`,
                  borderRadius: 2, padding: '0 3px', whiteSpace: 'nowrap', outlineOffset: 2,
                }}>
                  {signal.origin.label}
                </span>
              </Tip>
            )}
            {signal.flags?.map((flag) => (
              <Tip key={flag.label} text={`${flag.label} — ${flag.hint}`}>
                <span tabIndex={0} style={{
                  fontSize: 8, fontWeight: 700, letterSpacing: '.04em', cursor: 'help',
                  color: ORIGIN_TONE[flag.tone], background: tint(ORIGIN_TONE[flag.tone], 10),
                  border: `1px solid ${tint(ORIGIN_TONE[flag.tone], 30)}`,
                  borderRadius: 2, padding: '0 3px', whiteSpace: 'nowrap', outlineOffset: 2,
                }}>
                  {flag.label}
                </span>
              </Tip>
            ))}
            {marks?.has('bestRR') && (
              <Tip text="Best reward for risk across this signal's strikes — the most the plan pays per rupee it puts at stake.">
                <span tabIndex={0} style={{ fontSize: 12, color: k.dim, lineHeight: 1, cursor: 'help' }}>✝</span>
              </Tip>
            )}
            {marks?.has('bestDelta') && (
              <Tip text="Highest delta across this signal's strikes — the one that moves most with the underlying.">
                <span tabIndex={0} style={{ fontSize: 11, color: k.dim, lineHeight: 1, opacity: .75, cursor: 'help' }}>▲</span>
              </Tip>
            )}
            {trailBreached(signal) && (
              <Tip text="Live price is at or below this leg's trailing stop, but the engine has not closed it — this is where an open drawdown builds.">
                <span tabIndex={0} style={{
                  fontSize: 8, fontWeight: 700, color: k.red, border: `1px solid ${k.red}`,
                  borderRadius: 2, padding: '0 3px', whiteSpace: 'nowrap', cursor: 'help', outlineOffset: 2,
                }}>
                  TSL HIT
                </span>
              </Tip>
            )}
          </span>
        ),
      };
    case 'engine':
      return { node: <Pill tone={k.dim}>{ENGINE_TAG[signal.engine]}</Pill> };
    case 'status': {
      // Armed, weakening and error are exceptions and get a pill. Running,
      // watching and ended are the normal state of a board and read as quiet
      // text — if every row is badged, the badge stops meaning anything.
      if (!NOTABLE_STATUS.has(signal.status)) {
        return { node: STATUS_LABEL[signal.status], color: k.dim };
      }
      return { node: <Pill tone={STATUS_TONE[signal.status]}>{STATUS_LABEL[signal.status]}</Pill> };
    }
    case 'exchange':
      return { node: signal.instrument.exchange || '—', color: k.dim };
    case 'leg': {
      // The full contract symbol, because that is the string a trader searches
      // for, reads back to a broker, and matches against a fill. Strike and
      // expiry are the same information pre-parsed, so they go in the tooltip
      // rather than competing for the width.
      const { symbol, strike, expiry, moneyness } = signal.instrument;
      const parts = [strike ?? null, expiry ?? null].filter(Boolean).join(' · ');
      return {
        node: (
          <span title={parts || undefined}>
            {symbol}
            {moneyness && <span style={{ opacity: .8 }}> {moneyness}</span>}
            {signal.delta != null && <span style={{ opacity: .65 }}> (Δ{Math.abs(signal.delta).toFixed(2)})</span>}
          </span>
        ),
        color: k.dim,
      };
    }
    // The levels are plain ink. Colouring every stop red and every target green
    // was decoration, not information — the value was the same colour whatever
    // it said, and a board where a third of the numbers are permanently red has
    // nothing left to say when something is actually wrong. The column heading
    // already names which level it is.
    case 'ltp': return { node: num(signal.levels.ltp) };
    case 'entry': {
      // The bracket is the whole point of showing entry next to LTP: what the
      // position has actually done since it was taken.
      const { entry, ltp } = signal.levels;
      if (entry == null) return { node: '—' };
      const move = ltp == null ? null : ltp - entry;
      return {
        node: (
          <>
            {entry.toFixed(2)}
            {move != null && Math.abs(move) > 0.001 && (
              <span style={{ fontSize: 9.5, marginLeft: 3, fontWeight: 600, color: move >= 0 ? k.green : k.red }}>
                ({move >= 0 ? '+' : ''}{move.toFixed(2)})
              </span>
            )}
          </>
        ),
      };
    }
    case 'stop': return { node: num(signal.levels.stop) };
    case 'trail': return { node: num(signal.levels.trail) };
    case 'target': return { node: num(signal.levels.target) };
    case 'exit': return { node: num(signal.levels.exit) };
    case 'qty': return { node: signal.sizing.quantity ?? '—' };
    case 'risk': return { node: inr(signal.sizing.atRiskInr) };
    case 'score': return { node: signal.score == null ? '—' : signal.score.toFixed(0) };
    case 'time': {
      // A stale quote says so in words as well as in colour. Colour alone is
      // not a message on a board where several columns are already coloured by
      // direction, and it is no message at all to a colour-blind reader.
      const stale = signal.quoteAgeS != null && signal.quoteAgeS > STALE_AFTER_S;
      return {
        node: stale
          ? <span title={`Quote is ${Math.round(signal.quoteAgeS!)}s old`}>{hhmm(signal.atMs)} · stale</span>
          : hhmm(signal.atMs),
        color: stale ? k.red : k.dim,
      };
    }
    default: return { node: '—' };
  }
}

/**
 * Which columns to show.
 *
 * A column survives if at least one signal can fill it — a board of equities
 * should not carry an empty Leg column, and an engine that quotes no target
 * should not imply it forgot to. `always` columns are the row's identity and
 * stay even when sparse.
 */
/** True when more than one engine is on the board, so the Engine tag earns its width. */
export const isMixedEngine = (signals: readonly BoardSignal[]) =>
  new Set(flattenSignals(signals).map((s) => s.engine)).size > 1;

/**
 * The column set every board shows, in one place.
 *
 * All four engines request this same list, so switching tabs never moves a
 * column or renames one. What differs between engines is what they can fill,
 * and an empty cell says "this engine does not produce that" — ORB has no
 * trailing stop, so its TSL column reads as dashes, which is true and useful.
 *
 * That is a deliberate reversal. The board used to drop any column no row
 * could fill, which meant every board showed a different set and moving
 * between them meant re-finding the stop.
 */
export const BOARD_COLUMNS: readonly ColumnId[] = [
  'instrument', 'engine', 'status', 'exchange', 'leg',
  'ltp', 'entry', 'stop', 'trail', 'target', 'exit',
  'qty', 'risk', 'score', 'time',
];

/**
 * Off unless asked for, on every board.
 *
 * Leaves the eleven a trader named as the core of a row — symbol, type,
 * exchange, leg, LTP, entry, SL, TSL, exit, time, status — and keeps the rest
 * one click away in the column picker rather than making the sidebar scroll.
 */
export const DEFAULT_HIDDEN_COLUMNS: readonly ColumnId[] = ['engine', 'qty', 'risk', 'score'];

/**
 * Which columns to render.
 *
 * Only two things remove a column: the caller did not ask for it, or the user
 * switched it off. Emptiness no longer does — see BOARD_COLUMNS.
 *
 * The engine tag is the one exception, because on a single-engine board it
 * would repeat the same three letters down every row.
 */
export function visibleColumns(signals: readonly BoardSignal[], requested: readonly ColumnId[]): ColumnDef[] {
  const wanted = new Set(requested);
  if (!isMixedEngine(signals)) wanted.delete('engine');
  return COLUMNS.filter((c) => wanted.has(c.id));
}

function Row({
  signal, columns, template, open, onToggle, renderDetail, onOpenDetail, striped,
  depth = 0, legCount, marks,
}: {
  signal: BoardSignal;
  columns: ColumnDef[];
  template: string;
  open: boolean;
  onToggle: () => void;
  renderDetail?: (signal: BoardSignal) => React.ReactNode;
  onOpenDetail?: (signal: BoardSignal) => void;
  /** Alternating row shade, which is how rows separate without hard borders. */
  striped: boolean;
  /** 1 for a leg sitting under its signal. Indents and quietens the row. */
  depth?: number;
  /** Set on a parent: how many legs it holds, for the label and the summary. */
  legCount?: number;
  /** Which of its siblings' comparisons this leg wins. */
  marks?: ReadonlySet<'bestRR' | 'bestDelta'>;
}) {
  const isLeg = depth > 0;
  const isParent = legCount != null;
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-label={
          isParent
            ? `${signal.underlying} ${signal.direction}, ${legCount} contract${legCount === 1 ? '' : 's'}, ${STATUS_LABEL[signal.status]}`
            : `${signal.underlying} ${signal.instrument.optionType ?? ''} ${STATUS_LABEL[signal.status]}`
        }
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        className="sb-row"
        style={{
          display: 'grid',
          gridTemplateColumns: `18px ${template}`,
          alignItems: 'center',
          gap: 10,
          // A leg is indented under the idea it belongs to; the indent is the
          // only thing saying "this is part of that", so it has to survive
          // scrolling past the parent.
          padding: isLeg ? '0 12px 0 28px' : '0 12px',
          minHeight: isLeg ? 34 : 38,
          cursor: 'pointer',
          outlineOffset: -2,
          borderBottom: `1px solid ${isLeg ? 'transparent' : k.border}`,
          // The left accent marks the OPEN row only. It used to carry the
          // direction on every row, which put a saturated band down the whole
          // board and left nothing to mark the row you had actually opened —
          // direction is already stated by the pill beside the symbol.
          borderLeft: `3px solid ${open ? k.blue : 'transparent'}`,
          // Alternating shade separates rows the way the old Adaptive Edge
          // table did, without a coloured edge on each one. Legs share one
          // shade so a group reads as a block rather than a stripe pattern.
          background: open ? k.surfaceHover : isLeg ? 'var(--k-surface-2)' : striped ? 'var(--k-surface-2)' : k.bg,
          fontWeight: isParent ? 600 : 400,
          // An ended row is a record, not a live position. Dimming and striking
          // it keeps it readable without letting it read as actionable.
          opacity: signal.status === 'ended' ? 0.62 : 1,
          textDecoration: signal.status === 'ended' ? 'line-through' : 'none',
        }}
      >
        <span style={{ color: k.dim, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
          <Chevron open={open} />
          {isParent && (
            <span
              title={`${legCount} contract${legCount === 1 ? '' : 's'}`}
              style={{ fontSize: 8.5, fontWeight: 700, color: k.dim, fontVariantNumeric: 'tabular-nums' }}
            >
              {legCount}
            </span>
          )}
        </span>
        {columns.map((col) => {
          const { node, color } = cellContent(signal, col.id, col.id === 'instrument' ? onOpenDetail : undefined, marks);
          return (
            <span
              key={col.id}
              style={{
                fontSize: 11,
                color: color ?? k.text,
                textAlign: col.align,
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                minWidth: 0,
              }}
            >
              {node}
            </span>
          );
        })}
      </div>
      {open && (
        <div style={{ padding: 10, background: k.surface, borderBottom: `2px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {renderDetail?.(signal)}
          {signal.sections.length > 0 && (
            <StatCardGrid min={236}>
              {signal.sections.map((section) => (
                <StatCard
                  key={section.title}
                  title={section.title}
                  summary={section.summary}
                  layout={section.layout ?? 'tiles'}
                  stats={section.stats}
                  dense
                />
              ))}
            </StatCardGrid>
          )}
          {signal.reason && (
            <p style={{ margin: 0, fontSize: 10.5, color: k.dim, lineHeight: 1.55 }}>{signal.reason}</p>
          )}
        </div>
      )}
    </>
  );
}

export function SignalBoard({
  signals, columns: requested, openId, onToggle, renderDetail, onOpenDetail, nowMs, emptyLabel,
  sort = DEFAULT_SORT, onSortChange, hidden, collapsedGroups, onToggleGroup, liveFirst = true,
}: {
  signals: readonly BoardSignal[];
  requested?: readonly ColumnId[];
  columns?: readonly ColumnId[];
  openId: string | null;
  onToggle: (id: string) => void;
  renderDetail?: (signal: BoardSignal) => React.ReactNode;
  /** Opens the full detail page. Makes the instrument label a control. */
  onOpenDetail?: (signal: BoardSignal) => void;
  /** Column ordering, applied within each day. */
  sort?: SortState;
  /** Omit to make the header static — the board is then unsortable. */
  onSortChange?: (next: SortState) => void;
  /** Columns the user switched off. */
  hidden?: ReadonlySet<ColumnId>;
  /**
   * Signals whose contracts are FOLDED AWAY. Separate from `openId`, which is
   * a row's own detail.
   *
   * Expressed as collapsed rather than open so the default is legs visible.
   * A board exists to show tradable contracts; making every one of them cost a
   * click, on the board whose job is to show them, is worse than the repetition
   * grouping was introduced to fix — the parent row and the indent already give
   * the structure.
   */
  collapsedGroups?: ReadonlySet<string>;
  onToggleGroup?: (id: string) => void;
  /** Float open positions above the dated history. On by default. */
  liveFirst?: boolean;
  /** Passed in so day labels are deterministic and testable. */
  nowMs: number;
  emptyLabel?: string;
}) {
  const wanted = requested ?? BOARD_COLUMNS;
  const chosen = hidden ? wanted.filter((c) => !hidden.has(c)) : wanted;
  const cols = visibleColumns(signals, chosen);
  const template = cols.map((c) => c.width).join(' ');
  const days = groupByDay(signals, { liveFirst });

  if (!signals.length) {
    return <p style={{ padding: '14px 12px', margin: 0, fontSize: 11, color: k.dim, lineHeight: 1.6 }}>{emptyLabel ?? 'Nothing to show.'}</p>;
  }

  return (
    <div>
      <div
        role="row"
        style={{
          display: 'grid',
          gridTemplateColumns: `18px ${template}`,
          gap: 10,
          padding: '7px 12px',
          borderBottom: `1px solid ${k.border}`,
          borderLeft: '3px solid transparent',
          position: 'sticky',
          top: 0,
          zIndex: 2,
          background: k.bg,
        }}
      >
        <span />
        {cols.map((col) => {
          const active = sort.column === col.id;
          const direction = active ? sort.direction : null;
          return (
            <Tip
              key={col.id}
              text={col.hint ? `${col.label} — ${col.hint}. Click to sort within each day.` : `${col.label} — click to sort within each day.`}
            >
              <button
                type="button"
                className="sb-head"
                // aria-sort belongs on the header cell, and it is how a screen
                // reader announces which column the board is ordered by.
                aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}
                onClick={() => onSortChange?.(nextSort(sort, col.id))}
                disabled={!onSortChange}
                style={{
                  border: 'none', background: 'transparent', padding: 0, font: 'inherit',
                  fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em',
                  color: active ? k.text : k.dim,
                  textTransform: 'uppercase', whiteSpace: 'nowrap',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                  cursor: onSortChange ? 'pointer' : 'default',
                  outlineOffset: 2, minWidth: 0,
                  display: 'flex', alignItems: 'center',
                  justifyContent: col.align === 'right' ? 'flex-end' : 'flex-start',
                }}
              >
                {col.label}
                <SortMark direction={direction} />
              </button>
            </Tip>
          );
        })}
      </div>

      {days.map(({ key, signals: rows }) => (
        <section key={key}>
          <h3 style={{
            margin: 0, position: 'sticky', top: 28, zIndex: 1,
            padding: '4px 12px', background: k.surface, borderBottom: `1px solid ${k.border}`,
            fontSize: 8.5, fontWeight: 700, letterSpacing: '.07em', textTransform: 'uppercase', color: k.dim,
            display: 'flex', justifyContent: 'space-between',
          }}>
            <span>{sessionDayLabel(key, nowMs)}</span>
            <span style={{ fontWeight: 500 }}>
              {rows.length} signal{rows.length === 1 ? '' : 's'}
              {(() => {
                // The live bucket is already all-live; repeating it there
                // would read as "8 signals · 8 live".
                if (key === LIVE_BUCKET) return '';
                const live = rows.filter((r) => ACTIONABLE.includes(r.status)).length;
                return live ? ` · ${live} live` : '';
              })()}
            </span>
          </h3>
          {sortSignals(rows, sort).map((signal, i) => {
            const legs = signal.children ?? [];
            if (!legs.length) {
              return (
                <Row
                  key={signal.id}
                  signal={signal}
                  columns={cols}
                  template={template}
                  open={openId === signal.id}
                  onToggle={() => onToggle(signal.id)}
                  renderDetail={renderDetail}
                  onOpenDetail={onOpenDetail}
                  striped={i % 2 === 1}
                />
              );
            }
            // A parent's chevron shows its contracts, not its own detail —
            // the thing behind a signal with eighteen strikes is the strikes.
            // Its full record is still one click away on the symbol.
            const expanded = !(collapsedGroups?.has(signal.id) ?? false);
            // Best-of comparisons are only meaningful between the strikes of
            // one idea, so they are computed per group, never board-wide.
            const legMarks = markLegs(legs);
            return (
              <React.Fragment key={signal.id}>
                <Row
                  signal={signal}
                  columns={cols}
                  template={template}
                  open={expanded}
                  onToggle={() => onToggleGroup?.(signal.id)}
                  onOpenDetail={onOpenDetail}
                  striped={i % 2 === 1}
                  legCount={legs.length}
                />
                {expanded && sortSignals(legs, sort).map((leg) => (
                  <Row
                    key={leg.id}
                    marks={legMarks.get(leg.id)}
                    signal={leg}
                    columns={cols}
                    template={template}
                    open={openId === leg.id}
                    onToggle={() => onToggle(leg.id)}
                    renderDetail={renderDetail}
                    onOpenDetail={onOpenDetail}
                    striped={false}
                    depth={1}
                  />
                ))}
              </React.Fragment>
            );
          })}
        </section>
      ))}
    </div>
  );
}

export type { EngineId };
