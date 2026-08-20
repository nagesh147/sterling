/**
 * The one way this app displays a group of read-only numbers.
 *
 * Before this there were three: the position calculator's titled cards
 * (Position & MTM / Risk & Stops / Target & Exit), Adaptive Edge's tile grid,
 * and the quote panel's flat label-over-value run. Same job, three visual
 * languages, so moving between engines meant re-learning where to look.
 *
 * Two layouts, one vocabulary:
 *
 *   `rows`  — label left, value right, one per line. For a handful of figures
 *             a trader reads as a list ("capital deployed … max loss").
 *   `tiles` — a wrapping grid of label-over-value. For a dense readout that is
 *             scanned rather than read (a quote's OHLC, an option's Greeks).
 *
 * Both live in the same card, with the same header and the same type scale, so
 * a section that switches layout still looks like the section next to it.
 */
import React from 'react';
import { k, tint } from '../../../styles/kiteUI';

export interface Stat {
  label: string;
  value: React.ReactNode;
  /** Overrides the default ink. Use for direction, not decoration. */
  color?: string;
  /** Shown on hover and to screen readers. Say what the number means. */
  hint?: string;
  /** Trailing note on the same line, e.g. "(+12 pts · +1.4%)". */
  note?: React.ReactNode;
  /** Marks a figure as inferred rather than observed. */
  estimated?: boolean;
}

const numeric: React.CSSProperties = { fontVariantNumeric: 'tabular-nums' };

/** Distinguishes "we measured this" from "we solved for this". */
function EstimateMark({ hint }: { hint?: string }) {
  return (
    <span
      title={hint ?? 'Modelled, not observed'}
      aria-label="modelled value"
      style={{
        marginLeft: 4, fontSize: 8, fontWeight: 700, color: k.amber,
        border: `1px solid ${tint(k.amber, 45)}`, background: tint(k.amber, 12),
        borderRadius: 2, padding: '0 3px', verticalAlign: 'middle',
      }}
    >
      ~
    </span>
  );
}

export function StatRow({ label, value, color, hint, note, estimated }: Stat) {
  return (
    <div
      title={hint}
      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}
    >
      <span style={{ color: k.dim, whiteSpace: 'nowrap' }}>{label}</span>
      <span style={{ ...numeric, color: color ?? k.text, textAlign: 'right', minWidth: 0 }}>
        {value}
        {estimated && <EstimateMark hint={hint} />}
        {note != null && <span style={{ color: k.dim, fontSize: 11, marginLeft: 6 }}>{note}</span>}
      </span>
    </div>
  );
}

export function StatTile({ label, value, color, hint, note, estimated }: Stat) {
  return (
    <div title={hint} style={{ minWidth: 0 }}>
      <div style={{
        fontSize: 9, color: k.dim, textTransform: 'uppercase', letterSpacing: '.04em',
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>
        {label}
      </div>
      <div style={{
        ...numeric, fontSize: 12, fontWeight: 600, color: color ?? k.text,
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 1,
      }}>
        {value}
        {estimated && <EstimateMark hint={hint} />}
        {note != null && <span style={{ color: k.dim, fontWeight: 400, fontSize: 10, marginLeft: 4 }}>{note}</span>}
      </div>
    </div>
  );
}

export function StatCard({
  title, summary, summaryColor, layout = 'rows', stats, minTile = 84, children, dense = false,
}: {
  title: string;
  /** Right-aligned in the header — the one figure that sums the card up. */
  summary?: React.ReactNode;
  summaryColor?: string;
  layout?: 'rows' | 'tiles';
  stats?: Stat[];
  /** Narrowest a tile may get before the grid rewraps. */
  minTile?: number;
  children?: React.ReactNode;
  dense?: boolean;
}) {
  const visible = (stats ?? []).filter((s) => s.value !== undefined && s.value !== null);
  return (
    <section
      style={{
        background: k.bg,
        border: `1px solid ${k.border}`,
        borderRadius: 4,
        padding: dense ? '9px 10px' : '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: dense ? 7 : 8,
        minWidth: 0,
      }}
    >
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        paddingBottom: 6, borderBottom: `1px solid ${k.border}`,
      }}>
        <h4 style={{
          margin: 0, fontSize: 11, fontWeight: 500, color: k.text,
          textTransform: 'uppercase', letterSpacing: '.04em',
        }}>
          {title}
        </h4>
        {summary != null && (
          <span style={{ ...numeric, fontSize: 10.5, color: summaryColor ?? k.dim, whiteSpace: 'nowrap' }}>
            {summary}
          </span>
        )}
      </header>

      {visible.length > 0 && (
        layout === 'tiles' ? (
          <div style={{
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, minmax(${minTile}px, 1fr))`,
            gap: dense ? '7px 10px' : '9px 12px',
          }}>
            {visible.map((s) => <StatTile key={s.label} {...s} />)}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
            {visible.map((s) => <StatRow key={s.label} {...s} />)}
          </div>
        )
      )}

      {children}
    </section>
  );
}

/**
 * Lays cards out side by side, wrapping to as many columns as fit.
 *
 * `min` is the narrowest a card may get: 240 for reading-width row cards, less
 * for tile cards that stay legible when narrow.
 */
export function StatCardGrid({ children, min = 240, gap = 10 }: {
  children: React.ReactNode;
  min?: number;
  gap?: number;
}) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`, gap }}>
      {children}
    </div>
  );
}
