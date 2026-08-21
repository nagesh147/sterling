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

export function BoardFilters({ view, children }: { view: BoardView; children?: React.ReactNode }) {
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

      {children}

      {counts.shown !== counts.total && (
        <span style={{ fontSize: 9, color: k.dim, whiteSpace: 'nowrap', marginLeft: 'auto' }}>
          {counts.shown} of {counts.total}
        </span>
      )}
    </div>
  );
}
