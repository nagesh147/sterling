import React from 'react';
import { BORDER, MUTED, ORANGE, SOFT, TEXT } from '../kiteSettingsPrimitives';

/**
 * "Same as SuperTrend" / "Its own", per settings group.
 *
 * The old model had ONE scan-scope switch covering the whole of Navigator's
 * coverage, so a user who wanted Navigator on the same instruments but a
 * different strike ladder had no way to say it — and the settings page claimed
 * things were shared that the backend never shared. Each group now carries its
 * own link control, so "both engines" and "just this one" is a per-group choice
 * rather than one all-or-nothing flag.
 */
export function ScopeLink({ groupLabel, linked, onChange, sharedLabel = 'Same as SuperTrend', ownLabel = 'Its own', hint }: {
  /** Names the group this link controls, so two links on one page are
   *  distinguishable to a screen reader (and to a test). */
  groupLabel: string;
  linked: boolean;
  onChange: (linked: boolean) => void;
  sharedLabel?: string;
  ownLabel?: string;
  hint?: string;
}) {
  const opt = (label: string, active: boolean, next: boolean) => (
    <button
      key={label} type="button" aria-pressed={active}
      aria-label={`${groupLabel}: ${label}`}
      onClick={() => onChange(next)}
      style={{
        border: 'none', minHeight: 28, borderRadius: 6, padding: '0 11px',
        background: active ? '#fff' : 'transparent', color: active ? TEXT : MUTED,
        fontSize: 11, fontWeight: active ? 700 : 550, fontFamily: 'inherit',
        cursor: 'pointer', whiteSpace: 'nowrap',
        boxShadow: active ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
      }}
    >
      {label}
    </button>
  );
  return (
    <div role="group" aria-label={`${groupLabel} scope`} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <div style={{
        display: 'inline-flex', gap: 2, padding: 3,
        border: `1px solid ${BORDER}`, borderRadius: 8, background: SOFT,
      }}>
        {opt(sharedLabel, linked, true)}
        {opt(ownLabel, !linked, false)}
      </div>
      {hint && <span style={{ color: MUTED, fontSize: 10.5, lineHeight: 1.45 }}>{hint}</span>}
    </div>
  );
}

/** A settings group that can either follow the other engine or stand alone. */
export function ScopedGroup({ title, description, linked, onLinkChange, sharedSummary, hint, children }: {
  title: string;
  description: string;
  linked: boolean;
  onLinkChange: (linked: boolean) => void;
  /** What the user gets while linked — shown instead of the controls. */
  sharedSummary: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ padding: '15px 0', borderTop: `1px solid ${BORDER}` }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ color: TEXT, fontSize: 12.5, fontWeight: 700 }}>{title}</div>
        <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, margin: '2px 0 9px' }}>{description}</div>
        <ScopeLink groupLabel={title} linked={linked} onChange={onLinkChange} hint={hint} />
      </div>
      {linked ? (
        <div style={{
          padding: '9px 11px', borderRadius: 7, background: SOFT,
          border: `1px solid ${BORDER}`, color: MUTED, fontSize: 11, lineHeight: 1.5,
        }}>
          {sharedSummary}
        </div>
      ) : children}
    </div>
  );
}
