import React from 'react';

/**
 * Kite settings design system
 * Pattern: Linear / Stripe settings — open groups, not stacked accordion cards.
 *
 * Hierarchy:
 *   Page title (ConnectPane)
 *   → Group (Section): title + description + plain summary
 *   → Field: label | control, hint under
 *   → Advanced: only collapsible block
 */

export const ORANGE = '#f06428';
export const BORDER = '#ebebeb';
export const TEXT = '#171717';
export const MUTED = '#737373';
export const DIM = '#a3a3a3';
export const SOFT = '#f5f5f5';
export const ORANGE_SOFT = '#fff7f3';

export const inputStyle: React.CSSProperties = {
  width: 112,
  height: 34,
  padding: '0 10px',
  border: '1px solid #d4d4d4',
  borderRadius: 6,
  background: '#fff',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 13,
  boxSizing: 'border-box',
};

/**
 * Settings group — always open.
 * Left rail already navigates between pages; within a page we show all groups.
 * Summary is plain status text on the right (not a chip).
 */
export function Section({ title, description, summary, defaultOpen: _defaultOpen = false, children }: {
  title: string;
  description: string;
  summary: string;
  /** Kept for API compatibility; groups are always expanded. */
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className="sk-settings-group"
      style={{ marginBottom: 32 }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 16,
          paddingBottom: 12,
          marginBottom: 4,
          borderBottom: `1px solid ${BORDER}`,
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <h3
            style={{
              margin: 0,
              color: TEXT,
              fontSize: 15,
              fontWeight: 650,
              letterSpacing: '-0.02em',
              lineHeight: 1.3,
            }}
          >
            {title}
          </h3>
          {description ? (
            <p
              style={{
                margin: '4px 0 0',
                color: MUTED,
                fontSize: 13,
                lineHeight: 1.45,
                maxWidth: 560,
              }}
            >
              {description}
            </p>
          ) : null}
        </div>
        {summary ? (
          <span
            className="sk-config-summary"
            title={summary}
            style={{
              flexShrink: 0,
              maxWidth: 180,
              marginTop: 2,
              color: DIM,
              fontSize: 12,
              fontWeight: 500,
              textAlign: 'right',
              lineHeight: 1.35,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {summary}
          </span>
        ) : null}
      </header>
      <div className="sk-config-section-body" style={{ paddingTop: 2 }}>
        {children}
      </div>
    </section>
  );
}

/**
 * Single setting row.
 * Label left · control right · hint full-width under (never beside the control).
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
        padding: '14px 0',
        borderBottom: '1px solid #f0f0f0',
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
              boxShadow: selected ? '0 1px 2px rgba(0,0,0,.08)' : 'none',
              outline: selected ? `1px solid ${ORANGE}` : '1px solid transparent',
              outlineOffset: 0,
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
