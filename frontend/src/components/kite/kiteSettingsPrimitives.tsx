import React from 'react';

/**
 * Kite settings — quiet disclosure with warmth.
 * Collapse stays; chrome stays light; colour and motion add life.
 */

export const ORANGE = '#f06428';
export const BORDER = '#ebe6e2';
export const TEXT = '#1c1917';
export const MUTED = '#78716c';
export const DIM = '#a8a29e';
export const SOFT = '#faf8f6';
export const ORANGE_SOFT = '#fff5ef';

export const inputStyle: React.CSSProperties = {
  width: 112,
  height: 34,
  padding: '0 10px',
  border: '1px solid #e0dbd6',
  borderRadius: 8,
  background: '#fffefb',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 13,
  boxSizing: 'border-box',
  transition: 'border-color .15s ease, box-shadow .15s ease',
};

/** Collapsible group with soft open state — not a skeleton list. */
export function Section({ title, description, summary, defaultOpen = false, children }: {
  title: string;
  description: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  const [hovered, setHovered] = React.useState(false);

  return (
    <details
      className="sk-settings-group"
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      style={{
        marginBottom: 8,
        borderRadius: 12,
        background: isOpen ? '#fffefb' : hovered ? '#fafaf9' : 'transparent',
        border: `1px solid ${isOpen ? '#ebe6e2' : 'transparent'}`,
        transition: 'background .18s ease, border-color .18s ease',
      }}
    >
      <summary
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          listStyle: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 14px',
          userSelect: 'none',
          borderRadius: 12,
        }}
      >
        <span
          aria-hidden
          style={{
            flexShrink: 0,
            width: 26,
            height: 26,
            borderRadius: 8,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: isOpen ? ORANGE_SOFT : SOFT,
            color: isOpen ? ORANGE : DIM,
            fontSize: 14,
            fontWeight: 700,
            transform: isOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform .18s ease, background .18s ease, color .18s ease',
          }}
        >
          ›
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span
            style={{
              display: 'block',
              color: TEXT,
              fontSize: 14.5,
              fontWeight: 650,
              letterSpacing: '-0.02em',
              lineHeight: 1.3,
            }}
          >
            {title}
          </span>
          {description ? (
            <span
              style={{
                display: 'block',
                color: MUTED,
                fontSize: 12.5,
                lineHeight: 1.45,
                marginTop: 3,
              }}
            >
              {description}
            </span>
          ) : null}
        </span>
        {summary ? (
          <span
            className="sk-config-summary"
            title={summary}
            style={{
              flexShrink: 0,
              maxWidth: 168,
              padding: '3px 0',
              color: isOpen ? MUTED : DIM,
              fontSize: 12,
              fontWeight: 500,
              textAlign: 'right',
              lineHeight: 1.35,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              transition: 'color .15s ease',
            }}
          >
            {summary}
          </span>
        ) : null}
      </summary>
      <div
        className="sk-config-section-body"
        style={{
          padding: '2px 14px 16px 52px',
          borderTop: isOpen ? '1px solid #f0ebe6' : 'none',
        }}
      >
        {children}
      </div>
    </details>
  );
}

/** Setting row with soft hover life. */
export function Field({ label, hint, badge, children }: {
  label: string;
  hint?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [hovered, setHovered] = React.useState(false);

  return (
    <div
      className="sk-config-field"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(112px, max-content)',
        columnGap: 24,
        rowGap: 4,
        alignItems: 'center',
        padding: '12px 10px',
        margin: '0 -10px',
        borderRadius: 8,
        background: hovered ? 'rgba(250, 248, 246, 0.9)' : 'transparent',
        transition: 'background .14s ease',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          minWidth: 0,
          userSelect: 'none',
        }}
      >
        <span
          style={{
            color: TEXT,
            fontSize: 13.5,
            fontWeight: 550,
            letterSpacing: '-0.01em',
          }}
        >
          {label}
        </span>
        {badge}
      </div>
      <div
        style={{
          justifySelf: 'end',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
        }}
      >
        {children}
      </div>
      {hint != null && hint !== '' ? (
        <div
          style={{
            gridColumn: '1 / -1',
            color: MUTED,
            fontSize: 12.5,
            lineHeight: 1.45,
            minHeight: '1.35em',
            userSelect: 'text',
          }}
        >
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
    <div
      role="group"
      style={{
        display: 'inline-flex',
        maxWidth: '100%',
        gap: 3,
        padding: 4,
        borderRadius: 10,
        background: SOFT,
        flexWrap: 'wrap',
      }}
    >
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
              minHeight: 32,
              borderRadius: 8,
              background: selected ? '#fff' : 'transparent',
              color: selected ? TEXT : MUTED,
              padding: '0 13px',
              fontSize: 12.5,
              fontWeight: 550,
              boxShadow: selected
                ? `0 1px 3px rgba(28, 25, 23, 0.08), inset 0 -2px 0 ${ORANGE}`
                : 'none',
              fontFamily: 'inherit',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'background .14s ease, box-shadow .14s ease, color .14s ease',
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
        width: 42,
        height: 24,
        borderRadius: 12,
        border: 'none',
        padding: 0,
        flexShrink: 0,
        position: 'relative',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        background: checked ? ORANGE : '#d6d3d1',
        transition: 'background .2s ease',
        boxShadow: checked ? '0 1px 4px rgba(240, 100, 40, 0.35)' : 'none',
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: 18,
          height: 18,
          borderRadius: 9,
          top: 3,
          left: checked ? 21 : 3,
          background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,.16)',
          transition: 'left .2s ease',
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
        minHeight: compact ? 32 : 40,
        display: 'grid',
        gridTemplateColumns: '16px minmax(0, 1fr)',
        alignItems: 'center',
        gap: 9,
        border: compact ? 'none' : `1px solid ${checked || indeterminate ? '#f0d2c4' : BORDER}`,
        background: checked || indeterminate ? ORANGE_SOFT : compact ? 'transparent' : '#fffefb',
        color: TEXT,
        borderRadius: 8,
        padding: compact ? '4px 7px' : '8px 10px',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.7 : 1,
        boxSizing: 'border-box',
        transition: 'background .14s ease, border-color .14s ease',
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
        <span
          style={{
            display: 'block',
            fontSize: compact ? 11 : 12.5,
            fontWeight: checked || indeterminate ? 600 : 500,
            lineHeight: 1.25,
          }}
        >
          {label}
        </span>
        {hint && !compact && (
          <span
            style={{
              display: 'block',
              marginTop: 2,
              color: DIM,
              fontSize: 11,
              lineHeight: 1.3,
            }}
          >
            {hint}
          </span>
        )}
      </span>
    </label>
  );
}
