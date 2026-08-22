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
  ACTIONABLE, ENGINE_TAG, STATUS_LABEL, STATUS_RANK, groupByDay, sessionDayLabel,
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

/** The value of one column for one signal, plus how to colour it. */
function cellContent(
  signal: BoardSignal,
  id: ColumnId,
  onOpenDetail?: (signal: BoardSignal) => void,
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
            <Pill tone={dirTone} title={`${signal.direction} ${signal.instrument.optionType ?? signal.instrument.kind}`}>
              {signal.instrument.optionType ?? signal.instrument.kind.toUpperCase()} · {signal.direction.toUpperCase()}
            </Pill>
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
      const { symbol, strike, expiry } = signal.instrument;
      const parts = [strike ?? null, expiry ?? null].filter(Boolean).join(' · ');
      return { node: <span title={parts || undefined}>{symbol}</span>, color: k.dim };
    }
    // The levels are plain ink. Colouring every stop red and every target green
    // was decoration, not information — the value was the same colour whatever
    // it said, and a board where a third of the numbers are permanently red has
    // nothing left to say when something is actually wrong. The column heading
    // already names which level it is.
    case 'ltp': return { node: num(signal.levels.ltp) };
    case 'entry': return { node: num(signal.levels.entry) };
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
export function visibleColumns(signals: readonly BoardSignal[], requested: readonly ColumnId[]): ColumnDef[] {
  const always = new Set<ColumnId>(['instrument', 'status', 'time']);
  const filled = new Set<ColumnId>();
  for (const s of signals) {
    if (s.instrument.exchange) filled.add('exchange');
    if (s.instrument.strike != null || s.instrument.expiry) filled.add('leg');
    if (s.levels.ltp != null) filled.add('ltp');
    if (s.levels.entry != null) filled.add('entry');
    if (s.levels.stop != null) filled.add('stop');
    if (s.levels.trail != null) filled.add('trail');
    if (s.levels.target != null) filled.add('target');
    if (s.levels.exit != null) filled.add('exit');
    if (s.sizing.quantity != null) filled.add('qty');
    if (s.sizing.atRiskInr != null) filled.add('risk');
    if (s.score != null) filled.add('score');
    filled.add('engine');
  }
  return COLUMNS.filter((c) => requested.includes(c.id) && (always.has(c.id) || filled.has(c.id)));
}

/** True when more than one engine is on the board, so the Engine tag earns its width. */
export const isMixedEngine = (signals: readonly BoardSignal[]) =>
  new Set(signals.map((s) => s.engine)).size > 1;

function Row({ signal, columns, template, open, onToggle, renderDetail, onOpenDetail, striped }: {
  signal: BoardSignal;
  columns: ColumnDef[];
  template: string;
  open: boolean;
  onToggle: () => void;
  renderDetail?: (signal: BoardSignal) => React.ReactNode;
  onOpenDetail?: (signal: BoardSignal) => void;
  /** Alternating row shade, which is how rows separate without hard borders. */
  striped: boolean;
}) {
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-label={`${signal.underlying} ${signal.instrument.optionType ?? ''} ${STATUS_LABEL[signal.status]}`}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        className="sb-row"
        style={{
          display: 'grid',
          gridTemplateColumns: `18px ${template}`,
          alignItems: 'center',
          gap: 10,
          padding: '0 12px',
          minHeight: 38,
          cursor: 'pointer',
          outlineOffset: -2,
          borderBottom: `1px solid ${k.border}`,
          // The left accent marks the OPEN row only. It used to carry the
          // direction on every row, which put a saturated band down the whole
          // board and left nothing to mark the row you had actually opened —
          // direction is already stated by the pill beside the symbol.
          borderLeft: `3px solid ${open ? k.blue : 'transparent'}`,
          // Alternating shade separates rows the way the old Adaptive Edge
          // table did, without a coloured edge on each one.
          background: open ? k.surfaceHover : striped ? 'var(--k-surface-2)' : k.bg,
        }}
      >
        <span style={{ color: k.dim, display: 'inline-flex' }}><Chevron open={open} /></span>
        {columns.map((col) => {
          const { node, color } = cellContent(signal, col.id, col.id === 'instrument' ? onOpenDetail : undefined);
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
  sort = DEFAULT_SORT, onSortChange, hidden,
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
  /** Passed in so day labels are deterministic and testable. */
  nowMs: number;
  emptyLabel?: string;
}) {
  const wanted = requested ?? COLUMNS.map((c) => c.id);
  const withoutEngine = isMixedEngine(signals) ? wanted : wanted.filter((c) => c !== 'engine');
  // Two separate reasons a column is absent, applied in order: the user
  // switched it off, or no row can fill it. Keeping them separate means
  // un-hiding a column still respects the second rule.
  const chosen = hidden ? withoutEngine.filter((c) => !hidden.has(c)) : withoutEngine;
  const cols = visibleColumns(signals, chosen);
  const template = cols.map((c) => c.width).join(' ');
  const days = groupByDay(signals);

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
                const live = rows.filter((r) => ACTIONABLE.includes(r.status)).length;
                return live ? ` · ${live} live` : '';
              })()}
            </span>
          </h3>
          {sortSignals(rows, sort).map((signal, i) => (
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
          ))}
        </section>
      ))}
    </div>
  );
}

export type { EngineId };
