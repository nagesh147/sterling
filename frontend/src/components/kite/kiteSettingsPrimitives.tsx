import React from 'react';
import { k, tint } from '../../styles/kiteUI';

/**
 * Settings primitives — compact accordion + Kite system typography.
 * Minimal borders; no header fills; small radius.
 */

export const ORANGE = k.orange;
export const BORDER = k.border;
export const TEXT = k.text;
export const MUTED = k.dim;
export const DIM = k.dim;
export const SOFT = k.surface;
export const ORANGE_SOFT = tint(k.orange, 10);

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

/**
 * Compact accordion — one outer border, no header wash, no field rules.
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
      style={{
        marginBottom: 6,
        border: `1px solid ${k.border}`,
        borderRadius: 4,
        background: k.bg,
        overflow: 'hidden',
        fontFamily: k.fontFamily,
      }}
    >
      <summary
        style={{
          listStyle: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '8px 10px',
          userSelect: 'none',
          background: k.bg,
          borderLeft: isOpen ? `2px solid ${k.orange}` : '2px solid transparent',
        }}
      >
        <span
          aria-hidden
          style={{
            flexShrink: 0,
            width: 14,
            color: isOpen ? k.orange : k.dim,
            fontSize: 12,
            fontWeight: 700,
            lineHeight: 1,
            transform: isOpen ? 'rotate(90deg)' : 'none',
            transition: 'transform .12s ease',
          }}
        >
          ›
        </span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span
            style={{
              display: 'block',
              color: k.text,
              fontSize: 12,
              fontWeight: 700,
              lineHeight: 1.25,
            }}
          >
            {title}
          </span>
          {description ? (
            <span
              style={{
                display: 'block',
                color: k.dim,
                fontSize: 10.5,
                lineHeight: 1.35,
                marginTop: 1,
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
              maxWidth: 160,
              color: k.dim,
              fontSize: 10.5,
              fontWeight: 500,
              textAlign: 'right',
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
          padding: '2px 10px 8px 24px',
          background: k.bg,
        }}
      >
        {children}
      </div>
    </details>
  );
}

/** Setting row — no per-row border; hint under control. */
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
        gridTemplateColumns: 'minmax(0, 1fr) minmax(88px, max-content)',
        columnGap: 12,
        rowGap: 1,
        alignItems: 'center',
        padding: '6px 0',
        fontFamily: k.fontFamily,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          minWidth: 0,
          userSelect: 'none',
        }}
      >
        <span
          style={{
            color: k.text,
            fontSize: 12,
            fontWeight: 600,
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
            color: k.dim,
            fontSize: 10.5,
            lineHeight: 1.35,
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
        gap: 0,
        border: `1px solid ${k.border}`,
        borderRadius: 2,
        background: k.bg,
        flexWrap: 'wrap',
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
              border: 'none',
              borderLeft: i > 0 ? `1px solid ${k.border}` : 'none',
              minHeight: 26,
              borderRadius: 0,
              background: selected ? k.surface : k.bg,
              color: selected ? k.text : k.dim,
              padding: '0 9px',
              fontSize: 11,
              fontWeight: selected ? 600 : 500,
              boxShadow: selected ? `inset 0 -2px 0 ${k.orange}` : 'none',
              fontFamily: k.fontFamily,
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
        width: 34,
        height: 18,
        borderRadius: 9,
        border: 'none',
        padding: 0,
        flexShrink: 0,
        position: 'relative',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        background: checked ? k.orange : '#ccc',
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
        <span
          style={{
            display: 'block',
            fontSize: compact ? 10 : 12,
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
              marginTop: 1,
              color: k.dim,
              fontSize: 10,
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
