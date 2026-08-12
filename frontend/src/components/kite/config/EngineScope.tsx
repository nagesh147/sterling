import React from 'react';
import { BORDER, MUTED, ORANGE, SOFT, TEXT } from '../kiteSettingsPrimitives';

/** Own vs Like SuperTrend — per settings group. */
export function ScopeLink({ groupLabel, linked, onChange, sharedLabel = 'Like SuperTrend', ownLabel = 'Own', hint }: {
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
        {opt(ownLabel, !linked, false)}
        {opt(sharedLabel, linked, true)}
      </div>
      {hint && <span style={{ color: MUTED, fontSize: 10.5, lineHeight: 1.45, maxWidth: 280 }}>{hint}</span>}
    </div>
  );
}

/** Follow SuperTrend or own values. Parent Section can host ScopeLink via headerAction + hideLink. */
export function ScopedGroup({ title, description, linked, onLinkChange, sharedSummary, hint, hideLink = false, children }: {
  title: string;
  description: string;
  linked: boolean;
  onLinkChange: (linked: boolean) => void;
  sharedSummary: React.ReactNode;
  hint?: string;
  hideLink?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div style={{ padding: hideLink ? 0 : '4px 0' }}>
      {!hideLink && (
        <div style={{ marginBottom: 10 }}>
          <ScopeLink groupLabel={title} linked={linked} onChange={onLinkChange} hint={hint} />
        </div>
      )}
      {linked ? (
        <div style={{
          padding: '9px 11px', borderRadius: 7, background: SOFT,
          border: `1px solid ${BORDER}`, color: MUTED, fontSize: 11, lineHeight: 1.5, maxWidth: 440,
        }}>
          {sharedSummary}
        </div>
      ) : children}
    </div>
  );
}
