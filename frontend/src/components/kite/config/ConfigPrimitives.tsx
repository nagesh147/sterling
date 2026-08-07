import React from 'react';
import {
  BORDER, DIM, MUTED, ORANGE, SOFT, TEXT,
} from '../kiteSettingsPrimitives';
import type { Applies, SectionId } from './registry';
import { openSettingsSection } from './registry';

const BLUE = '#387ed1';
const AMBER = '#b06a13';

const APPLIES_STYLE: Record<Applies, { label: string; color: string; background: string; border: string }> = {
  manual: { label: 'MANUAL', color: BLUE, background: '#eef4fb', border: '#cfe0f2' },
  auto: { label: 'AUTO', color: AMBER, background: '#fdf4e8', border: '#efdcc0' },
  both: { label: 'MANUAL + AUTO', color: '#4a6b4d', background: '#eef5ee', border: '#cfe2d0' },
};

/**
 * Says whether a setting bites on orders you place yourself, on orders the
 * engine places, or on both.
 *
 * The tooltip carries the backend evidence for the claim. These are real-money
 * settings, and "Advanced auto-execution guards" previously grouped two fields
 * (expiry square-off and the time stop) that in fact iterate every registered
 * position, hand-placed ones included — so an unsourced claim here is exactly
 * the failure mode worth designing against.
 */
export function AppliesChip({ applies, evidence }: { applies: Applies; evidence?: string }) {
  const style = APPLIES_STYLE[applies];
  return (
    <span
      title={evidence}
      style={{
        display: 'inline-flex', alignItems: 'center', flexShrink: 0,
        padding: '2px 7px', borderRadius: 4, letterSpacing: .4,
        fontSize: 8.5, fontWeight: 800, whiteSpace: 'nowrap',
        color: style.color, background: style.background, border: `1px solid ${style.border}`,
      }}
    >
      {style.label}
    </span>
  );
}

export type Scope = 'all' | 'manual' | 'auto';

/** Does a field with this applicability survive the current scope filter? */
export function inScope(applies: Applies, scope: Scope): boolean {
  if (scope === 'all') return true;
  return applies === scope || applies === 'both';
}

const SCOPE_OPTIONS: Array<{ value: Scope; label: string; hint: string }> = [
  { value: 'all', label: 'All rules', hint: 'Everything that shapes a trade.' },
  { value: 'manual', label: 'Manual', hint: 'Only what affects orders you place yourself.' },
  { value: 'auto', label: 'Automatic', hint: 'Only what affects orders the engine places.' },
];

/** Filters the Trade Rules page down to one order origin. */
export function ScopeFilter({ value, onChange }: { value: Scope; onChange: (next: Scope) => void }) {
  return (
    <div role="group" aria-label="Show rules for" style={{
      display: 'inline-flex', maxWidth: '100%', flexWrap: 'wrap', gap: 2,
      border: `1px solid ${BORDER}`, borderRadius: 8, padding: 3, background: SOFT,
    }}>
      {SCOPE_OPTIONS.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value} type="button" title={option.hint} aria-pressed={selected}
            onClick={() => onChange(option.value)}
            style={{
              border: 'none', minHeight: 30, borderRadius: 6, padding: '0 13px',
              background: selected ? '#fff' : 'transparent', color: selected ? TEXT : MUTED,
              fontSize: 11.5, fontWeight: selected ? 700 : 550, fontFamily: 'inherit',
              cursor: 'pointer', whiteSpace: 'nowrap',
              boxShadow: selected ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * A setting shown where it is relevant but edited where it is owned.
 *
 * The alternative — rendering the same control on two pages — is how
 * `scan_source` ended up with two different names, and how a user could change
 * "a SuperTrend setting" and silently move Navigator too.
 */
export function SettingPointer({ value, section, sectionLabel }: {
  value: string;
  section: SectionId;
  sectionLabel: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
      <span style={{
        padding: '6px 11px', borderRadius: 7, background: SOFT, border: `1px solid ${BORDER}`,
        color: TEXT, fontSize: 12, fontWeight: 600,
      }}>
        {value}
      </span>
      <button
        type="button"
        onClick={() => openSettingsSection(section)}
        style={{
          border: 'none', background: 'none', padding: 0, cursor: 'pointer',
          fontFamily: 'inherit', color: ORANGE, fontSize: 11, fontWeight: 700,
        }}
      >
        Change in {sectionLabel} →
      </button>
    </div>
  );
}

/** A short explanatory note inside a section — used where the honest answer is
 *  "there is no setting here, and this is why". */
export function ConfigNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 8, margin: '10px 0 2px',
      padding: '9px 11px', borderRadius: 7, background: SOFT, border: `1px solid ${BORDER}`,
      color: MUTED, fontSize: 10.5, lineHeight: 1.55,
    }}>
      <span aria-hidden style={{ color: DIM, fontSize: 11, lineHeight: 1.4 }}>ⓘ</span>
      <span style={{ minWidth: 0 }}>{children}</span>
    </div>
  );
}

/** Header strip shared by the reorganised settings panels. */
export function PanelHeader({ title, description, saving }: {
  title: string;
  description: string;
  saving?: boolean;
}) {
  const green = '#4caf50';
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 12,
      padding: '16px 18px', borderBottom: `1px solid ${BORDER}`,
    }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ color: TEXT, fontSize: 14.5, fontWeight: 800 }}>{title}</div>
        <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 3 }}>{description}</div>
      </div>
      {saving !== undefined && (
        <span aria-live="polite" style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0,
          color: saving ? MUTED : green, fontSize: 10.5, fontWeight: 700,
        }}>
          <span aria-hidden style={{
            width: 6, height: 6, borderRadius: '50%', background: saving ? '#c2c2c2' : green,
          }} />
          {saving ? 'Saving…' : 'Saved'}
        </span>
      )}
    </div>
  );
}

/** The card shell every reorganised settings panel sits in. */
export function PanelCard({ children }: { children: React.ReactNode }) {
  return (
    <section style={{
      background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 9,
      overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)',
    }}>
      {children}
    </section>
  );
}
