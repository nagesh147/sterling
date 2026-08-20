import React from 'react';
import { k, tint } from '../../styles/kiteUI';

/**
 * Shown when a signal tab's engine is switched off.
 *
 * An empty list and a disabled engine look identical but mean opposite things:
 * one says "the market is quiet", the other "nothing is even looking". This
 * states which, and carries the switch, so the fix is one click away rather
 * than a hunt through settings.
 */
export function EngineOffNotice({
  engine,
  detail,
  onEnable,
  pending = false,
  onConfigure,
  configureLabel = 'Open settings',
  error,
}: {
  engine: string;
  detail: string;
  onEnable?: () => void;
  pending?: boolean;
  onConfigure?: () => void;
  configureLabel?: string;
  error?: string | null;
}) {
  return (
    <div
      role="status"
      style={{
        margin: 12, padding: '18px 16px', borderRadius: 6,
        border: `1px solid ${k.border}`, background: k.surface,
        display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* An SVG, not an emoji: it inherits colour and scales with the type. */}
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v4" strokeLinecap="round" />
          <path d="M12 16h.01" strokeLinecap="round" />
        </svg>
        <span style={{ fontSize: 11.5, fontWeight: 700, color: k.text }}>{engine} is off</span>
        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color: k.dim, background: tint(k.dim, 14), border: `1px solid ${k.border}`, borderRadius: 3, padding: '1px 5px' }}>
          NOT SCANNING
        </span>
      </div>

      <p style={{ margin: 0, fontSize: 10.5, lineHeight: 1.6, color: k.dim, maxWidth: 460 }}>{detail}</p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {onEnable && (
          <button
            type="button"
            onClick={onEnable}
            disabled={pending}
            // 32px min height keeps this comfortably tappable in a narrow dock.
            style={{
              minHeight: 32, padding: '0 14px', borderRadius: 6, cursor: pending ? 'wait' : 'pointer',
              border: `1px solid ${k.blue}`, background: pending ? tint(k.blue, 10) : k.blue,
              color: pending ? k.blue : '#fff', fontFamily: 'inherit', fontSize: 10.5, fontWeight: 700,
              opacity: pending ? 0.75 : 1, transition: 'background .12s ease, opacity .12s ease',
            }}
          >
            {pending ? 'Turning on…' : `Turn on ${engine}`}
          </button>
        )}
        {onConfigure && (
          <button
            type="button"
            onClick={onConfigure}
            style={{
              minHeight: 32, padding: '0 12px', borderRadius: 6, cursor: 'pointer',
              border: `1px solid ${k.border}`, background: k.bg, color: k.text,
              fontFamily: 'inherit', fontSize: 10.5, fontWeight: 600,
            }}
          >
            {configureLabel}
          </button>
        )}
      </div>

      {error && (
        // Beside the control that failed, not banished to a page-level banner.
        <div style={{ fontSize: 10, color: k.red }}>Could not turn it on: {error}</div>
      )}
    </div>
  );
}

export default EngineOffNotice;
