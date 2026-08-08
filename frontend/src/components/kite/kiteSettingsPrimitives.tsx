import React from 'react';

/**
 * Kite settings primitives
 *
 * Pattern: quiet progressive disclosure
 * - Sections collapse (page stays scannable)
 * - No card frames, orange bars, or pill chips
 * - Summary = plain status text on the right
 * - Only Advanced uses a lighter, secondary treatment
 */

export const ORANGE = '#f06428';
export const BORDER = '#eaeaea';
export const TEXT = '#171717';
export const MUTED = '#6f6f6f';
export const DIM = '#9c9c9c';
export const SOFT = '#f5f5f5';
export const ORANGE_SOFT = '#fff7f3';

export const inputStyle: React.CSSProperties = {
  width: 112,
  height: 34,
  padding: '0 10px',
  border: '1px solid #d6d6d6',
  borderRadius: 6,
  background: '#fff',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 13,
  boxSizing: 'border-box',
};

/**
 * Collapsible group — minimal chrome.
 * Closed: title + summary only (scannable).
 * Open: fields below with a single light rule under the header.
 */
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
      className="sk-settings-group"
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      style={{ marginBottom: 2 }}
    >
      <summary
        style={{
          listStyle: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '14px 0',
          userSelect: 'none',
          borderBottom: `1px solid ${BORDER}`,
        }}
      >
        <span
          aria-hidden
          style={{
            flexShrink: 0,
            width: 14,
            color: DIM,
            fontSize: 13,
            lineHeight: 1,
            transform: isOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform .14s ease',
          }}
        >
          ›
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span
            style={{
              display: 'block',
              color: TEXT,
              fontSize: 14,
              fontWeight: 600,
              letterSpacing: '-0.015em',
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
                lineHeight: 1.4,
                marginTop: 2,
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
              color: DIM,
              fontSize: 12,
              fontWeight: 500,
              textAlign: 'right',
              lineHeight: 1.3,
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
        style={{ padding: '4px 0 12px 24px' }}
      >
        {children}
      </div>
    </details>
  );
}

/**
 * Setting row: label left · control right · hint under the row.
 */
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
        gridTemplateColumns: 'minmax(0, 1fr) minmax(112px, max-content)',
        columnGap: 24,
        rowGap: 4,
        alignItems: 'center',
        padding: '12px 0',
        borderBottom: '1px solid #f3f3f3',
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
        gap: 2,
        padding: 3,
        borderRadius: 8,
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
              minHeight: 30,
              borderRadius: 6,
              background: selected ? '#fff' : 'transparent',
              color: selected ? TEXT : MUTED,
              padding: '0 12px',
              fontSize: 12.5,
              fontWeight: 550,
              boxShadow: selected ? '0 1px 2px rgba(0,0,0,.07)' : 'none',
              outline: selected ? `1px solid ${ORANGE}` : '1px solid transparent',
              fontFamily: 'inherit',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'background .12s ease, box-shadow .12s ease',
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
        opacity: disabled ? 0.5 : 1,
        background: checked ? ORANGE : '#d4d4d4',
        transition: 'background .18s ease',
      }}
    >
      <span
        style={{
          position: 'absolute',
          width: 18,
          height: 18,
          borderRadius: 9,
          top: 2,
          left: checked ? 20 : 2,
          background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,.18)',
          transition: 'left .18s ease',
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
        background: checked || indeterminate ? ORANGE_SOFT : compact ? 'transparent' : '#fff',
        color: TEXT,
        borderRadius: 6,
        padding: compact ? '4px 7px' : '8px 10px',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.7 : 1,
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
