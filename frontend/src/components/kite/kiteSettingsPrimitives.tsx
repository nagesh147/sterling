import React from 'react';

// Shared design tokens + primitives for Kite settings panels.
// Visual hierarchy (strong → quiet):
//   Section header  →  Field label  →  control  →  hint  →  Advanced

export const ORANGE = '#f06428';
export const BORDER = '#e8e8e8';
export const TEXT = '#1f1f1f';
export const MUTED = '#6b6b6b';
export const DIM = '#9a9a9a';
export const SOFT = '#f6f6f7';
export const ORANGE_SOFT = '#fff5f0';

export const inputStyle: React.CSSProperties = {
  width: 108,
  height: 34,
  padding: '0 10px',
  border: '1px solid #d8d8d8',
  borderRadius: 6,
  background: '#fff',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 13,
  boxSizing: 'border-box',
};

/** Primary accordion block — Stop-loss, Position size, What to buy, … */
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
      style={{
        marginBottom: 10,
        border: `1px solid ${isOpen ? '#e0e0e0' : BORDER}`,
        borderRadius: 10,
        background: '#fff',
        overflow: 'hidden',
      }}
    >
      <summary style={{
        listStyle: 'none',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '14px 16px',
        userSelect: 'none',
        boxSizing: 'border-box',
        background: isOpen ? '#fafafa' : '#fff',
        borderLeft: isOpen ? `3px solid ${ORANGE}` : '3px solid transparent',
        transition: 'background .12s ease',
      }}>
        <span
          aria-hidden
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            flexShrink: 0,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: isOpen ? ORANGE_SOFT : SOFT,
            color: isOpen ? ORANGE : DIM,
            fontSize: 14,
            fontWeight: 700,
            transform: isOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform .15s ease, background .12s ease, color .12s ease',
          }}
        >
          ›
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{
            display: 'block',
            color: TEXT,
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: '-.01em',
            lineHeight: 1.25,
          }}>
            {title}
          </span>
          <span style={{
            display: 'block',
            color: MUTED,
            fontSize: 12,
            lineHeight: 1.4,
            marginTop: 3,
          }}>
            {description}
          </span>
        </span>
        {summary ? (
          <span
            className="sk-config-summary"
            title={summary}
            style={{
              flexShrink: 0,
              maxWidth: 148,
              padding: '4px 9px',
              borderRadius: 999,
              background: isOpen ? '#fff' : SOFT,
              border: `1px solid ${BORDER}`,
              color: DIM,
              fontSize: 11,
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {summary}
          </span>
        ) : null}
      </summary>
      <div
        className="sk-config-section-body"
        style={{
          padding: '4px 16px 14px',
          borderTop: `1px solid ${BORDER}`,
          background: '#fff',
        }}
      >
        {children}
      </div>
    </details>
  );
}

/** One setting row — label left, control right, hint under. */
export function Field({ label, hint, badge, children }: {
  label: string;
  hint?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      className="sk-config-field"
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(108px, max-content)',
        columnGap: 20,
        rowGap: 4,
        alignItems: 'center',
        padding: '12px 0',
        borderBottom: '1px solid #f2f2f2',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        minWidth: 0,
        userSelect: 'none',
      }}>
        <span style={{
          color: TEXT,
          fontSize: 13,
          fontWeight: 600,
          letterSpacing: '-.005em',
        }}>
          {label}
        </span>
        {badge}
      </div>
      <div style={{
        justifySelf: 'end',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
      }}>
        {children}
      </div>
      {hint != null && hint !== '' ? (
        <div style={{
          gridColumn: '1 / -1',
          color: MUTED,
          fontSize: 12,
          lineHeight: 1.45,
          minHeight: '1.35em',
          userSelect: 'text',
        }}>
          {hint}
        </div>
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
    <div style={{
      display: 'inline-flex',
      maxWidth: '100%',
      border: `1px solid ${BORDER}`,
      borderRadius: 8,
      padding: 3,
      gap: 2,
      background: SOFT,
      flexWrap: 'wrap',
    }}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            title={option.hint}
            onClick={() => onChange(option.value)}
            style={{
              border: 'none',
              minHeight: 30,
              borderRadius: 6,
              background: selected ? '#fff' : 'transparent',
              color: selected ? TEXT : MUTED,
              padding: '0 12px',
              fontSize: 12,
              fontWeight: 600,
              boxShadow: selected
                ? `inset 0 -2px ${ORANGE}, 0 1px 2px rgba(0,0,0,.06)`
                : 'none',
              fontFamily: 'inherit',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
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
        width: 40,
        height: 22,
        borderRadius: 11,
        border: 'none',
        padding: 0,
        flexShrink: 0,
        position: 'relative',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        background: checked ? ORANGE : '#cfcfcf',
        transition: 'background .16s ease',
      }}
    >
      <span style={{
        position: 'absolute',
        width: 18,
        height: 18,
        borderRadius: 9,
        top: 2,
        left: checked ? 20 : 2,
        background: '#fff',
        boxShadow: '0 1px 3px rgba(0,0,0,.2)',
        transition: 'left .16s ease',
      }} />
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
        minHeight: compact ? 32 : 40,
        display: 'grid',
        gridTemplateColumns: '16px minmax(0, 1fr)',
        alignItems: 'center',
        gap: 9,
        border: compact ? 'none' : `1px solid ${checked || indeterminate ? '#e7c5b7' : BORDER}`,
        background: checked || indeterminate ? ORANGE_SOFT : compact ? 'transparent' : '#fff',
        color: TEXT,
        borderRadius: 6,
        padding: compact ? '4px 7px' : '7px 10px',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.72 : 1,
        boxSizing: 'border-box',
      }}
    >
      <input
        ref={inputRef}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.()}
        style={{ width: 15, height: 15, margin: 0, accentColor: ORANGE }}
      />
      <span style={{ minWidth: 0 }}>
        <span style={{
          display: 'block',
          fontSize: compact ? 10.5 : 12,
          fontWeight: checked || indeterminate ? 700 : 550,
          lineHeight: 1.25,
        }}>
          {label}
        </span>
        {hint && !compact && (
          <span style={{
            display: 'block',
            marginTop: 2,
            color: DIM,
            fontSize: 10,
            lineHeight: 1.3,
          }}>
            {hint}
          </span>
        )}
      </span>
    </label>
  );
}
