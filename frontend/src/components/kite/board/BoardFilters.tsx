/**
 * The view-filter row: search, then the toggles that have something to act on.
 *
 * Every control here is local. A filter that changed a trading rule would
 * belong on the other side of the toolbar's divider, and none of these do.
 *
 * A toggle whose filter is inert is not rendered at all rather than shown
 * disabled — "Ended" greyed out on a board with no ended rows is noise that
 * looks like a broken control.
 */
import React from 'react';
import { COLUMNS, type ColumnId } from './SignalBoard';
import { k, tint } from '../../../styles/kiteUI';
import type { BoardView } from './useBoardView';

/**
 * A local view filter.
 *
 * Exported because SuperTrend's board has its own filter row and had its own
 * differently-shaped toggles. Two controls that do the same job should not look
 * like two different jobs.
 */
export function FilterToggle({ on, label, hint, onChange }: {
  on: boolean; label: string; hint: string; onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      title={hint}
      onClick={onChange}
      className="sb-tool"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4, height: 22, padding: '0 7px',
        border: `1px solid ${on ? tint(k.blue, 45) : k.border}`, borderRadius: 4,
        background: on ? tint(k.blue, 10) : 'transparent',
        color: on ? k.blue : k.dim,
        fontFamily: 'inherit', fontSize: 9, fontWeight: 700, letterSpacing: '.05em',
        cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
      }}
    >
      <span aria-hidden style={{
        width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
        background: on ? k.blue : k.border,
      }} />
      {label}
    </button>
  );
}

/**
 * Which columns to show.
 *
 * Only offers columns the board could actually render — hiding a column no row
 * can fill is a control for nothing, and listing all fifteen on a board that
 * shows nine invites a user to switch on a column that then does not appear.
 *
 * The row identity columns are not offered: a board with no instrument and no
 * status is not a board.
 */
const LOCKED: readonly ColumnId[] = ['instrument', 'status'];

function ColumnPicker({ view, available }: { view: BoardView; available: readonly ColumnId[] }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const offered = COLUMNS.filter((c) => available.includes(c.id) && !LOCKED.includes(c.id));

  React.useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!offered.length) return null;
  const hiddenCount = offered.filter((c) => view.hidden.has(c.id)).length;

  return (
    <div ref={ref} style={{ position: 'relative', flexShrink: 0 }}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={hiddenCount ? `Columns, ${hiddenCount} hidden` : 'Columns'}
        title="Choose which columns this board shows"
        onClick={() => setOpen((v) => !v)}
        className="sb-tool"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4, height: 22, padding: '0 7px',
          border: `1px solid ${hiddenCount ? tint(k.blue, 45) : k.border}`, borderRadius: 4,
          background: hiddenCount ? tint(k.blue, 10) : 'transparent',
          color: hiddenCount ? k.blue : k.dim,
          fontFamily: 'inherit', fontSize: 9, fontWeight: 700, letterSpacing: '.05em', cursor: 'pointer',
        }}
      >
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden>
          <path d="M4 5h16M4 12h16M4 19h16" strokeLinecap="round" />
        </svg>
        COLUMNS{hiddenCount ? ` ${offered.length - hiddenCount}/${offered.length}` : ''}
      </button>

      {open && (
        <div
          role="group"
          aria-label="Visible columns"
          style={{
            position: 'absolute', top: 26, right: 0, zIndex: 60, minWidth: 168,
            background: k.bg, border: '1px solid var(--k-border-strong)', borderRadius: 6,
            boxShadow: '0 10px 26px rgba(0, 0, 0, .26)', padding: 6,
          }}
        >
          {offered.map((col) => {
            const on = !view.hidden.has(col.id);
            return (
              <label
                key={col.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7, padding: '4px 5px', borderRadius: 3,
                  fontSize: 10.5, color: k.text, cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => view.toggleColumn(col.id)}
                  style={{ width: 13, height: 13, margin: 0, accentColor: k.orange }}
                />
                {col.label}
              </label>
            );
          })}
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={view.showAllColumns}
              style={{
                width: '100%', marginTop: 4, padding: '4px 5px', border: 'none', borderTop: `1px solid ${k.border}`,
                background: 'transparent', color: k.blue, fontFamily: 'inherit', fontSize: 9.5, fontWeight: 600,
                cursor: 'pointer', textAlign: 'left',
              }}
            >
              Show all columns
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function BoardFilters({ view, columns, children }: {
  view: BoardView;
  /** The columns this board asks for, so the picker offers only those. */
  columns?: readonly ColumnId[];
  children?: React.ReactNode;
}) {
  const { counts } = view;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
      borderBottom: `1px solid ${k.border}`, background: k.bg, flexWrap: 'wrap',
    }}>
      <label style={{ flex: '1 1 130px', minWidth: 110, display: 'flex', alignItems: 'center', gap: 5 }}>
        <span className="sr-only" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
          Filter signals
        </span>
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="2.4" aria-hidden style={{ flexShrink: 0 }}>
          <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.6-3.6" strokeLinecap="round" />
        </svg>
        <input
          value={view.query}
          onChange={(e) => view.setQuery(e.target.value)}
          placeholder="Symbol, contract or exchange"
          style={{
            flex: 1, minWidth: 0, height: 22, border: `1px solid ${k.border}`, borderRadius: 4,
            background: k.bg, color: k.text, fontFamily: 'inherit', fontSize: 10, padding: '0 6px',
          }}
        />
      </label>

      {view.offers.best && (
        <FilterToggle
          on={view.bestOnly}
          label="BEST LEG"
          hint="Show only the nearest-the-money leg of each underlying — the one whose premium tracks the thesis most directly. A local filter."
          onChange={() => view.setBestOnly(!view.bestOnly)}
        />
      )}
      {view.offers.ended && (
        <FilterToggle
          on={view.showEnded}
          label={`ENDED ${counts.ended}`}
          hint="Include closed positions. They are kept for the record and are not calls to action."
          onChange={() => view.setShowEnded(!view.showEnded)}
        />
      )}

      {columns && <ColumnPicker view={view} available={columns} />}

      {children}

      {counts.shown !== counts.total && (
        <span style={{ fontSize: 9, color: k.dim, whiteSpace: 'nowrap', marginLeft: 'auto' }}>
          {counts.shown} of {counts.total}
        </span>
      )}
    </div>
  );
}
