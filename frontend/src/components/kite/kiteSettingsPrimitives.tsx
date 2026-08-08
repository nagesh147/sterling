import React from 'react';

// Shared design tokens + primitives for Kite settings panels
// (EngineConfigurationPanel, NavigatorSettingsPanel, …). Extracted to its
// own module — rather than re-exported from one panel — so panels can
// mock each other out in tests (as ConnectPane's existing test does for
// EngineConfigurationPanel) without losing these shared building blocks.

export const ORANGE = '#f06428';
export const BORDER = '#e0e0e0';
export const TEXT = '#444';
export const MUTED = '#777';
export const DIM = '#9b9b9b';
export const SOFT = '#f3f4f6';
export const ORANGE_SOFT = '#fff5f0';

export const inputStyle: React.CSSProperties = {
  width: 104,
  height: 36,
  padding: '0 10px',
  border: `1px solid ${BORDER}`,
  borderRadius: 7,
  background: '#fff',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 12.5,
  boxSizing: 'border-box',
};

export function Section({ title, description, summary, defaultOpen = false, children }: {
  title: string;
  description: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <details
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      style={{ borderBottom: `1px solid ${BORDER}` }}
    >
      <summary style={{
        listStyle: 'none', cursor: 'pointer', padding: '17px 18px', display: 'flex',
        alignItems: 'center', gap: 11, userSelect: 'none', minHeight: 66, boxSizing: 'border-box',
      }}>
        <span aria-hidden style={{ width: 18, color: DIM, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0, transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform .16s ease' }}>›</span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: 'block', color: TEXT, fontSize: 13.5, fontWeight: 700 }}>{title}</span>
          <span style={{ display: 'block', color: MUTED, fontSize: 11.5, lineHeight: 1.45, marginTop: 3 }}>{description}</span>
        </span>
        <span className="sk-config-summary" style={{ color: DIM, fontSize: 11, textAlign: 'right', maxWidth: 230 }}>{summary}</span>
      </summary>
      <div className="sk-config-section-body" style={{ padding: '0 18px 20px 20px' }}>{children}</div>
    </details>
  );
}

export function Field({ label, hint, badge, children }: {
  label: string;
  hint?: string;
  /** Rendered beside the label — used for the manual/auto applicability chip. */
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="sk-config-field" style={{
      display: 'grid', gridTemplateColumns: 'minmax(140px, 1fr) auto', gap: '6px 20px',
      padding: '12px 0', alignItems: 'center', borderBottom: '1px solid #f0f0f0',
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span style={{ color: TEXT, fontSize: 13, fontWeight: 600 }}>{label}</span>
          {badge}
        </div>
        {hint && <div style={{ color: MUTED, fontSize: 12, lineHeight: 1.4, marginTop: 3, maxWidth: 400 }}>{hint}</div>}
      </div>
      <div style={{ justifySelf: 'end', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>{children}</div>
    </div>
  );
}

export function ChoiceRow<T extends string>({ value, options, onChange }: {
  value: T;
  options: Array<{ value: T; label: string; hint?: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div style={{ display: 'inline-flex', maxWidth: '100%', border: `1px solid ${BORDER}`, borderRadius: 8, padding: 3, gap: 2, background: SOFT, flexWrap: 'wrap' }}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button key={option.value} type="button" aria-pressed={selected} title={option.hint} onClick={() => onChange(option.value)} style={{
            border: 'none', minHeight: 32, borderRadius: 6,
            background: selected ? '#fff' : 'transparent', color: selected ? TEXT : MUTED,
            padding: '0 13px', fontSize: 11.5, fontWeight: selected ? 700 : 550,
            boxShadow: selected ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
            fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
          }}>
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({ checked, label, onChange, disabled = false }: {
  checked: boolean;
  label: string;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={onChange} disabled={disabled} style={{
      width: 40, height: 22, borderRadius: 11, border: 'none', padding: 0, flexShrink: 0,
      position: 'relative', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? .55 : 1,
      background: checked ? ORANGE : '#c7c7c7',
      transition: 'background .16s ease',
    }}>
      <span style={{ position: 'absolute', width: 18, height: 18, borderRadius: 9, top: 2, left: checked ? 20 : 2, background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,.2)', transition: 'left .16s ease' }} />
    </button>
  );
}

export function CheckOption({ label, hint, checked, indeterminate = false, onChange, compact = false, disabled = false }: {
  label: string;
  hint?: string;
  checked: boolean;
  indeterminate?: boolean;
  onChange?: () => void;
  compact?: boolean;
  disabled?: boolean;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <label title={hint} style={{
      minHeight: compact ? 32 : 42,
      display: 'grid', gridTemplateColumns: '16px minmax(0, 1fr)', alignItems: 'center', gap: 9,
      border: compact ? 'none' : `1px solid ${checked || indeterminate ? '#e7c5b7' : BORDER}`,
      background: checked || indeterminate ? ORANGE_SOFT : compact ? 'transparent' : '#fff',
      color: TEXT, borderRadius: 6, padding: compact ? '4px 7px' : '7px 10px',
      cursor: disabled ? 'default' : 'pointer', opacity: disabled ? .72 : 1, boxSizing: 'border-box',
    }}>
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.()}
        style={{ width: 15, height: 15, margin: 0, accentColor: ORANGE }}
      />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', fontSize: compact ? 10.5 : 11.5, fontWeight: checked || indeterminate ? 700 : 550, lineHeight: 1.25 }}>{label}</span>
        {hint && !compact && <span style={{ display: 'block', marginTop: 2, color: DIM, fontSize: 9.5, lineHeight: 1.3 }}>{hint}</span>}
      </span>
    </label>
  );
}
