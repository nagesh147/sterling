import React from 'react';
import { useKiteSettings } from '../../../store/useKiteSettings';

/* ─────────────────────────────────────────────────────────────────────────
 * MacKiteToggle — the single Settings entry point for Mac Kite mode.
 *
 * Lives in the Kite footer control bar beside lock/reset (it is a view/layout
 * preference, and keeps the Kite navbar pixel-faithful to Zerodha). Kite-styled
 * so it disappears into the chrome when off.
 * ───────────────────────────────────────────────────────────────────────── */
export function MacKiteToggle() {
  const macKite = useKiteSettings((s) => s.macKite);
  const setMacKite = useKiteSettings((s) => s.setMacKite);

  const ORANGE = 'var(--k-brand)';
  return (
    <button
      onClick={() => setMacKite(!macKite)}
      title={macKite ? 'Mac Kite: on — fluid Apple-grade motion' : 'Mac Kite: off — stock Kite'}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        height: 22, padding: '0 8px', borderRadius: 11, cursor: 'pointer',
        border: `1px solid ${macKite ? ORANGE : 'var(--k-border)'}`,
        background: macKite ? 'rgba(240,100,40,0.08)' : 'transparent',
        color: macKite ? ORANGE : 'var(--k-dim)',
        fontSize: 10, fontWeight: 600, letterSpacing: 0.3,
        transition: 'all 0.3s cubic-bezier(0.25, 1, 0.5, 1)',
      }}
    >
      {/* Sparkle glyph — signals the "special mode" without breaking Kite parity. */}
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z" />
      </svg>
      MAC
      {/* Mini switch track. */}
      <span style={{
        width: 22, height: 12, borderRadius: 6, position: 'relative', flexShrink: 0,
        background: macKite ? ORANGE : '#d0d0d0',
        transition: 'background 0.3s cubic-bezier(0.25, 1, 0.5, 1)',
      }}>
        <span style={{
          position: 'absolute', top: 1, left: 1, width: 10, height: 10, borderRadius: '50%',
          background: 'var(--k-bg)', boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
          transform: macKite ? 'translateX(10px)' : 'translateX(0)',
          transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }} />
      </span>
    </button>
  );
}
