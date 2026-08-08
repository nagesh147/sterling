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

export function inScope(applies: Applies, scope: Scope): boolean {
  if (scope === 'all') return true;
  return applies === scope || applies === 'both';
}

const SCOPE_OPTIONS: Array<{ value: Scope; label: string; hint: string }> = [
  { value: 'all', label: 'All rules', hint: 'Everything that shapes a trade.' },
  { value: 'manual', label: 'Manual', hint: 'Only what affects orders you place yourself.' },
  { value: 'auto', label: 'Automatic', hint: 'Only what affects orders the engine places.' },
];

export function ScopeFilter({ value, onChange }: { value: Scope; onChange: (next: Scope) => void }) {
  return (
    <div role="group" aria-label="Filter by order origin" style={{
      display: 'inline-flex', gap: 2, padding: 3, borderRadius: 8,
      background: SOFT, border: `1px solid ${BORDER}`,
    }}>
      {SCOPE_OPTIONS.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            title={option.hint}
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            style={{
              border: 'none', minHeight: 28, borderRadius: 6,
              background: selected ? '#fff' : 'transparent',
              color: selected ? TEXT : MUTED,
              padding: '0 11px', fontSize: 12, fontWeight: 600,
              boxShadow: selected ? '0 1px 2px rgba(0,0,0,.06)' : 'none',
              outline: selected ? `1px solid ${ORANGE}` : '1px solid transparent',
              fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function CrossLink({ to, children }: { to: SectionId; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={() => openSettingsSection(to)}
      style={{
        border: 'none', background: 'transparent', color: ORANGE,
        padding: 0, fontSize: 12, fontWeight: 600, cursor: 'pointer',
        fontFamily: 'inherit', textDecoration: 'underline', textUnderlineOffset: 2,
      }}
    >
      {children}
    </button>
  );
}

export function ConfigNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-start',
      padding: '8px 0', color: MUTED, fontSize: 11.5, lineHeight: 1.45,
      maxWidth: 440,
    }}>
      <span aria-hidden style={{ color: DIM, fontSize: 11, lineHeight: 1.4 }}>ⓘ</span>
      <span style={{ minWidth: 0 }}>{children}</span>
    </div>
  );
}

/** Floating save indicator — never pushes layout. */
export function PanelHeader({ title, description, saving }: {
  title?: string;
  description?: string;
  saving?: boolean;
}) {
  if (saving !== true) return null;

  return (
    <div
      aria-live="polite"
      style={{
        position: 'fixed',
        top: 12,
        right: 16,
        zIndex: 40,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 10px',
        borderRadius: 4,
        border: `1px solid ${BORDER}`,
        background: '#fff',
        color: MUTED,
        fontSize: 11,
        fontWeight: 600,
        boxShadow: '0 1px 4px rgba(0,0,0,.08)',
        pointerEvents: 'none',
      }}
    >
      <span aria-hidden style={{
        width: 6, height: 6, borderRadius: '50%', background: ORANGE,
      }} />
      Saving…
    </div>
  );
}

export function PanelCard({ children }: { children: React.ReactNode }) {
  return (
    <section style={{ background: 'transparent', border: 'none', marginBottom: 0 }}>
      {children}
    </section>
  );
}

/** Apply / Discard / Reset — only renders when dirty. Same bar for SuperTrend + Navigator. */
export function SettingsDraftBar({
  dirty,
  saving = false,
  onApply,
  onDiscard,
  onReset,
  resetConfirm = false,
  applyDisabled = false,
  applyTitle,
}: {
  dirty: boolean;
  saving?: boolean;
  onApply: () => void;
  onDiscard: () => void;
  onReset: () => void;
  resetConfirm?: boolean;
  applyDisabled?: boolean;
  applyTitle?: string;
}) {
  if (!dirty) return null;

  const RED = '#c9433e';
  const AMBER = '#b06a13';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
        padding: '12px 16px',
        marginBottom: 16,
        background: '#fff',
        border: `1px solid ${BORDER}`,
        borderRadius: 9,
        boxShadow: '0 1px 2px rgba(0,0,0,.025)',
      }}
    >
      <span
        aria-live="polite"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          color: saving ? MUTED : AMBER,
          fontSize: 10.5,
          fontWeight: 700,
          marginRight: 4,
        }}
      >
        <span
          aria-hidden
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: saving ? '#c2c2c2' : AMBER,
          }}
        />
        {saving ? 'Saving…' : 'Unsaved changes'}
      </span>
      <button
        type="button"
        onClick={onApply}
        disabled={saving || applyDisabled}
        title={applyTitle}
        style={{
          border: 'none',
          background: ORANGE,
          color: '#fff',
          borderRadius: 7,
          padding: '8px 16px',
          fontSize: 11.5,
          fontWeight: 700,
          cursor: saving || applyDisabled ? 'default' : 'pointer',
          fontFamily: 'inherit',
          opacity: saving || applyDisabled ? 0.5 : 1,
        }}
      >
        Apply changes
      </button>
      <button
        type="button"
        onClick={onDiscard}
        disabled={saving}
        style={{
          border: `1px solid ${BORDER}`,
          background: '#fff',
          color: MUTED,
          borderRadius: 7,
          padding: '7px 12px',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
          fontFamily: 'inherit',
        }}
      >
        Discard draft
      </button>
      <div style={{ flex: 1 }} />
      <button
        type="button"
        onClick={onReset}
        disabled={saving}
        style={{
          border: `1px solid ${BORDER}`,
          background: '#fff',
          color: resetConfirm ? RED : MUTED,
          borderRadius: 7,
          padding: '7px 12px',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
          fontFamily: 'inherit',
        }}
      >
        {resetConfirm ? 'Click again to confirm reset' : 'Reset to defaults'}
      </button>
    </div>
  );
}

/**
 * Advanced — quiet disclosure. Nested Section cards keep the same left edge
 * as top-level sections (no indent).
 */
export function AdvancedSection({ count, children, defaultOpen = false }: {
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <details
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      style={{ marginTop: 8, marginBottom: 0 }}
    >
      <summary style={{
        listStyle: 'none', cursor: 'pointer', padding: '8px 2px', display: 'flex',
        alignItems: 'center', gap: 8, userSelect: 'none', boxSizing: 'border-box',
        background: 'transparent', outline: 'none',
      }}>
        <span aria-hidden style={{
          width: 14, color: DIM, display: 'inline-flex', alignItems: 'center',
          justifyContent: 'center', fontSize: 12, flexShrink: 0, fontWeight: 700,
          transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform .12s ease',
        }}>›</span>
        <span style={{ color: MUTED, fontSize: 12, fontWeight: 600 }}>
          Advanced{count != null ? ` · ${count}` : ''}
        </span>
      </summary>
      <div style={{ padding: '0', display: 'flex', flexDirection: 'column', gap: 0 }}>
        {children}
      </div>
    </details>
  );
}
