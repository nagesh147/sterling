import React from 'react';
import { k, tint } from '../../styles/kiteUI';

/**
 * Settings primitives — compact accordion + Kite system typography.
 * Section cards match Trading Mode (radius 9, light shadow).
 */

export const ORANGE = k.orange;
export const BORDER = k.border;
export const TEXT = k.text;
export const MUTED = k.dim;
export const DIM = k.dim;
export const SOFT = k.surface;
export const ORANGE_SOFT = tint(k.orange, 10);

/** Shared shell — matches Trading Mode cards everywhere in Settings. */
export const settingsCardStyle: React.CSSProperties = {
  background: k.bg,
  border: `1px solid ${k.border}`,
  borderRadius: 9,
  marginBottom: 16,
  boxShadow: '0 1px 2px rgba(0,0,0,.025)',
  overflow: 'hidden',
};

export const inputStyle: React.CSSProperties = {
  width: 88,
  height: 28,
  padding: '0 8px',
  border: `1px solid ${k.border}`,
  borderRadius: 2,
  background: k.bg,
  color: k.text,
  fontFamily: k.fontFamily,
  fontSize: 12,
  boxSizing: 'border-box',
};

/** Accordion section — same card chrome as Trading Mode. */
export function Section({
  title, description, summary, defaultOpen = false, headerAction, persistKey, children,
}: {
  title: string;
  description: string;
  summary: string;
  defaultOpen?: boolean;
  headerAction?: React.ReactNode;
  persistKey?: string;
  children: React.ReactNode;
}) {
  const storageKey = persistKey ? `kite-settings-section:${persistKey}` : null;
  const [isOpen, setIsOpen] = React.useState(() => {
    if (storageKey && typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(storageKey);
        if (raw === '1') return true;
        if (raw === '0') return false;
      } catch { /* ignore */ }
    }
    return defaultOpen;
  });

  const onToggle = (event: React.SyntheticEvent<HTMLDetailsElement>) => {
    const next = event.currentTarget.open;
    setIsOpen(next);
    if (storageKey) {
      try { window.localStorage.setItem(storageKey, next ? '1' : '0'); } catch { /* ignore */ }
    }
  };

  const META_W = 200;

  return (
    <details
      className="sk-settings-group"
      open={isOpen}
      onToggle={onToggle}
      style={{ ...settingsCardStyle, fontFamily: k.fontFamily }}
    >
      <summary
        style={{
          listStyle: 'none',
          cursor: 'pointer',
          display: 'grid',
          gridTemplateColumns: `14px minmax(0, 1fr) ${META_W}px`,
          columnGap: 10,
          alignItems: 'center',
          padding: '12px 16px',
          minHeight: 56,
          userSelect: 'none',
          background: k.bg,
          borderLeft: isOpen ? `2px solid ${k.orange}` : '2px solid transparent',
          boxSizing: 'border-box',
        }}
      >
        <span aria-hidden style={{
          width: 14, color: isOpen ? k.orange : k.dim, fontSize: 12, fontWeight: 700,
          lineHeight: 1, transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform .12s ease',
          justifySelf: 'center',
        }}>›</span>

        <span style={{ minWidth: 0 }}>
          <span style={{ display: 'block', color: k.text, fontSize: 12, fontWeight: 700, lineHeight: 1.25 }}>
            {title}
          </span>
          {description ? (
            <span style={{
              display: 'block', color: k.dim, fontSize: 10.5, lineHeight: 1.35, marginTop: 1, maxWidth: 440,
              whiteSpace: 'pre-line',
            }}>
              {description}
            </span>
          ) : null}
        </span>

        <span
          className="sk-config-meta"
          style={{
            width: META_W,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            justifyContent: 'center',
            gap: headerAction ? 6 : 0,
            textAlign: 'left',
            boxSizing: 'border-box',
          }}
        >
          {headerAction ? (
            <span
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
              onKeyDown={(e) => e.stopPropagation()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                maxWidth: '100%',
              }}
            >
              {headerAction}
            </span>
          ) : null}
          <span
            className="sk-config-summary"
            title={summary || undefined}
            style={{
              width: '100%',
              color: k.dim,
              fontSize: 10.5,
              fontWeight: 500,
              lineHeight: 1.35,
              paddingTop: headerAction ? 1 : 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              textAlign: 'left',
            }}
          >
            {summary || '\u00a0'}
          </span>
        </span>
      </summary>
      <div className="sk-config-section-body" style={{ padding: '2px 16px 12px 16px', background: k.bg }}>
        {children}
      </div>
    </details>
  );
}

export function Field({ label, hint, badge, children, wide = false }: {
  label: string;
  hint?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  /** Control full-width under the label (choice strips, long option rows). */
  wide?: boolean;
}) {
  const hintStyle: React.CSSProperties = {
    color: k.dim,
    fontSize: 10.5,
    lineHeight: 1.4,
    maxWidth: 440,
    userSelect: 'text',
  };

  if (wide) {
    return (
      <div
        className="sk-config-field sk-config-field--wide"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          padding: '8px 0',
          fontFamily: k.fontFamily,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, userSelect: 'none' }}>
          <span style={{ color: k.text, fontSize: 12, fontWeight: 600 }}>{label}</span>
          {badge}
        </div>
        <div style={{ width: '100%' }}>{children}</div>
        {hint != null && hint !== '' ? <div style={hintStyle}>{hint}</div> : null}
      </div>
    );
  }

  return (
    <div
      className="sk-config-field"
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(88px, max-content)',
        columnGap: 16,
        rowGap: 2,
        alignItems: 'center',
        padding: '7px 0',
        fontFamily: k.fontFamily,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, maxWidth: 320, userSelect: 'none' }}>
        <span style={{ color: k.text, fontSize: 12, fontWeight: 600 }}>{label}</span>
        {badge}
      </div>
      <div style={{ justifySelf: 'end', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
        {children}
      </div>
      {hint != null && hint !== '' ? (
        <div style={{ gridColumn: '1 / -1', ...hintStyle }}>{hint}</div>
      ) : null}
    </div>
  );
}

export function ChoiceRow<T extends string>({ value, options, onChange }: {
  value: T;
  options: Array<{ value: T; label: string; hint?: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="group"
      style={{
        display: 'flex',
        width: '100%',
        maxWidth: '100%',
        gap: 0,
        border: `1px solid ${k.border}`,
        borderRadius: 2,
        background: k.bg,
        flexWrap: 'nowrap',
        fontFamily: k.fontFamily,
      }}
    >
      {options.map((option, i) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            title={option.hint}
            onClick={() => onChange(option.value)}
            style={{
              flex: '1 1 0',
              border: 'none',
              borderLeft: i > 0 ? `1px solid ${k.border}` : 'none',
              minHeight: 28,
              borderRadius: 0,
              background: selected ? k.surface : k.bg,
              color: selected ? k.text : k.dim,
              padding: '0 10px',
              fontSize: 11,
              fontWeight: selected ? 600 : 500,
              boxShadow: selected ? `inset 0 -2px 0 ${k.orange}` : 'none',
              fontFamily: k.fontFamily,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              textAlign: 'center' as const,
            }}
          >
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
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      disabled={disabled}
      style={{
        width: 34,
        height: 18,
        borderRadius: 9,
        border: 'none',
        padding: 0,
        flexShrink: 0,
        position: 'relative',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        background: checked ? k.orange : 'var(--k-faint-5)',
        transition: 'background .15s ease',
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: 14,
          height: 14,
          borderRadius: 7,
          top: 2,
          left: checked ? 18 : 2,
          background: k.bg,
          boxShadow: '0 1px 2px rgba(0,0,0,.15)',
          transition: 'left .15s ease',
        }}
      />
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
    <label
      title={hint}
      style={{
        minHeight: compact ? 26 : 30,
        display: 'grid',
        gridTemplateColumns: '14px minmax(0, 1fr)',
        alignItems: 'center',
        gap: 8,
        border: 'none',
        background: 'transparent',
        color: k.text,
        borderRadius: 2,
        padding: compact ? '2px 0' : '4px 0',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.7 : 1,
        boxSizing: 'border-box',
        fontFamily: k.fontFamily,
      }}
    >
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.()}
        style={{ width: 13, height: 13, margin: 0, accentColor: k.orange }}
      />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', fontSize: compact ? 10 : 12, fontWeight: checked || indeterminate ? 600 : 500, lineHeight: 1.25 }}>
          {label}
        </span>
        {hint && !compact && (
          <span style={{ display: 'block', marginTop: 1, color: k.dim, fontSize: 10, lineHeight: 1.3 }}>{hint}</span>
        )}
      </span>
    </label>
  );
}


/**
 * A numeric setting that tells you whether it is still at the engine's default.
 *
 * Without this a panel of numbers gives no clue which ones you have moved. The
 * default is supplied by the server (not mirrored in the client) so the badge
 * cannot drift from the engine, and a changed field shows what it was and
 * offers one click back.
 */
/**
 * "default" / "changed · default X ↺" for any setting, not just numbers.
 *
 * A panel of fields is only readable at a glance if every one of them answers
 * the same question the same way, so choices, switches and time windows use
 * this too — a number was never the only kind of value a user can move.
 */
export function DefaultBadge({ isDefault, defaultLabel, onRestore, restoreTitle }: {
  isDefault: boolean;
  /** The default, already formatted for reading. */
  defaultLabel: string;
  onRestore: () => void;
  restoreTitle?: string;
}) {
  if (isDefault) {
    return (
      <span
        title="Unchanged from the engine default"
        style={{
          color: k.dim, fontSize: 9, fontWeight: 600, letterSpacing: '.03em',
          border: `1px solid ${k.border}`, borderRadius: 3, padding: '0 5px', height: 16, lineHeight: '15px',
        }}
      >
        default
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onRestore}
      title={restoreTitle ?? `Restore the default, ${defaultLabel}`}
      style={{
        border: `1px solid ${tint(k.orange, 40)}`, background: tint(k.orange, 10), color: k.orange,
        borderRadius: 3, padding: '0 5px', height: 16, fontSize: 9, fontWeight: 700,
        letterSpacing: '.03em', cursor: 'pointer', fontFamily: 'inherit',
      }}
    >
      changed · default {defaultLabel} ↺
    </button>
  );
}

export function NumberField({
  label, hint, value, defaultValue, onChange,
  min, max, step = 1, suffix, disabled = false, format,
}: {
  label: string;
  hint?: string;
  value: number;
  /** The engine's default. Omit only when the server does not publish one. */
  defaultValue?: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  disabled?: boolean;
  format?: (v: number) => string;
}) {
  const known = defaultValue != null && Number.isFinite(defaultValue);
  // Compare on the step's precision: 1.15 typed back over 1.15 is not a change.
  const decimals = String(step).includes('.') ? String(step).split('.')[1].length : 0;
  const same = (a: number, b: number) => a.toFixed(decimals) === b.toFixed(decimals);
  const isDefault = !known || same(value, defaultValue as number);
  const show = format ?? ((v: number) => String(v));

  return (
    <Field
      label={label}
      hint={hint}
      badge={known ? (
        <DefaultBadge
          isDefault={isDefault}
          defaultLabel={show(defaultValue as number)}
          onRestore={() => onChange(defaultValue as number)}
        />
      ) : undefined}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => {
            const next = Number(e.target.value);
            if (Number.isFinite(next)) onChange(next);
          }}
          style={{
            ...inputStyle,
            width: 96,
            textAlign: 'right',
            // A moved value is tinted so a panel of numbers reads at a glance.
            borderColor: isDefault ? k.border : k.orange,
            background: isDefault ? 'var(--k-bg)' : tint(k.orange, 6),
            opacity: disabled ? 0.55 : 1,
          }}
        />
        {suffix && <span style={{ color: k.dim, fontSize: 11, minWidth: 26 }}>{suffix}</span>}
      </div>
    </Field>
  );
}
