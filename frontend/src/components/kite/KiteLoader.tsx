import React from 'react';
import { createPortal } from 'react-dom';
import { k } from '../../styles/kiteUI';
import { useKiteSettings, type LoaderStyle } from '../../store/useKiteSettings';
import { useAuthFeedback } from '../../store/useAuthFeedback';

/* ─────────────────────────────────────────────────────────────────────────
 * Kite loaders — selectable visual styles (Connect → Settings → Loader style).
 *
 *   • 'mac'     → Apple-grade segmented spinner + smooth overlays/checkmark.
 *   • 'classic' → simple rotating ring (lightweight, no flourish).
 *   • 'off'     → static dots, no animation (reduced-motion friendly).
 *
 * Everything is self-contained (keyframes injected once via <KiteLoaderStyles/>)
 * so dropping <KiteLoader/> or <KiteAuthOverlay/> anywhere "just works".
 * ───────────────────────────────────────────────────────────────────────── */

const CSS = `
@keyframes kl-mac-fade { 0% { opacity: 1; } 100% { opacity: 0.15; } }
@keyframes kl-spin { to { transform: rotate(360deg); } }
@keyframes kl-overlay-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes kl-card-in {
  from { opacity: 0; transform: scale(0.94) translateY(8px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}
@keyframes kl-check-ring {
  0%   { transform: scale(0.4); opacity: 0; }
  60%  { transform: scale(1.06); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes kl-check-draw { to { stroke-dashoffset: 0; } }
@keyframes kl-dots { 0%, 80%, 100% { opacity: 0.2; } 40% { opacity: 1; } }
`;

// Keyframes are scoped by unique `kl-*` names, so rendering this more than once
// (several loaders on screen) just yields harmless duplicate <style> tags.
export function KiteLoaderStyles() {
  return <style>{CSS}</style>;
}

/** The 12-spoke Apple spinner, drawn with CSS rotation + staggered fade. */
function MacSpinner({ size = 28, color = k.dim }: { size?: number; color?: string }) {
  const spokes = 12;
  const barW = Math.max(1.5, size * 0.08);
  const barH = size * 0.27;
  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'inline-block' }}>
      {Array.from({ length: spokes }).map((_, i) => (
        <span
          key={i}
          style={{
            position: 'absolute', left: '50%', top: '50%',
            width: barW, height: barH, borderRadius: barW,
            background: color,
            transform: `translate(-50%, -50%) rotate(${i * (360 / spokes)}deg) translateY(-${size * 0.36}px)`,
            animation: `kl-mac-fade 1s linear infinite`,
            animationDelay: `${(-(spokes - i) / spokes).toFixed(3)}s`,
            opacity: 0.15,
          }}
        />
      ))}
    </div>
  );
}

/** Lightweight rotating ring for the 'classic' style. */
function ClassicSpinner({ size = 28, color = k.blue }: { size?: number; color?: string }) {
  const bw = Math.max(2, size * 0.1);
  return (
    <span
      style={{
        display: 'inline-block', width: size, height: size, borderRadius: '50%',
        border: `${bw}px solid ${k.border}`, borderTopColor: color,
        animation: 'kl-spin 0.7s linear infinite', boxSizing: 'border-box',
      }}
    />
  );
}

/** Static three-dots for the 'off' style (no spin; honours reduced motion). */
function StaticDots({ size = 28, color = k.dim }: { size?: number; color?: string }) {
  const d = Math.max(4, size * 0.18);
  return (
    <span style={{ display: 'inline-flex', gap: d * 0.6, alignItems: 'center', height: size }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{ width: d, height: d, borderRadius: '50%', background: color, opacity: 0.5 }} />
      ))}
    </span>
  );
}

/** Style-aware inline spinner — drop in anywhere a pending state needs a loader.
 *  Pass `styleOverride` to force a specific look (used by the settings preview). */
export function KiteLoader({ size = 28, color, styleOverride }: { size?: number; color?: string; styleOverride?: LoaderStyle }) {
  const saved = useKiteSettings((s) => s.loaderStyle);
  const style = styleOverride ?? saved;
  return (
    <>
      <KiteLoaderStyles />
      {style === 'classic'
        ? <ClassicSpinner size={size} color={color} />
        : style === 'off'
          ? <StaticDots size={size} color={color} />
          : <MacSpinner size={size} color={color} />}
    </>
  );
}

/** Tiny inline loader sized for buttons (replaces the bare "…" text). */
export function ButtonLoader({ color = '#fff' }: { color?: string }) {
  const style = useKiteSettings((s) => s.loaderStyle);
  if (style === 'off') return <span>…</span>;
  return (
    <>
      <KiteLoaderStyles />
      {style === 'classic'
        ? <ClassicSpinner size={13} color={color} />
        : <MacSpinner size={14} color={color} />}
    </>
  );
}

/** Animated success checkmark (mac style); a static ✓ for classic/off. */
function SuccessMark({ size = 56, animate }: { size?: number; animate: boolean }) {
  if (!animate) {
    return (
      <div style={{
        width: size, height: size, borderRadius: '50%', background: k.green,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#fff', fontSize: size * 0.5, fontWeight: 700,
      }}>✓</div>
    );
  }
  const r = size / 2;
  return (
    <svg width={size} height={size} viewBox="0 0 52 52" style={{ animation: 'kl-check-ring 0.45s cubic-bezier(0.16,1,0.3,1)' }}>
      <circle cx="26" cy="26" r={r - 1} fill={k.green} />
      <path
        fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
        d="M15 27 l7 7 l15 -16"
        style={{ strokeDasharray: 48, strokeDashoffset: 48, animation: 'kl-check-draw 0.4s 0.22s ease forwards' }}
      />
    </svg>
  );
}

/**
 * Full-screen auth overlay. Reads the global auth-feedback phase:
 *   • 'connecting' → dimmed backdrop + spinner + label
 *   • 'success'    → checkmark flourish (auto-dismisses)
 * Renders nothing while idle. Mount once near the app root.
 */
export function KiteAuthOverlay() {
  const phase = useAuthFeedback((s) => s.phase);
  const label = useAuthFeedback((s) => s.label);
  const style = useKiteSettings((s) => s.loaderStyle);
  if (phase === 'idle') return null;

  const animate = style !== 'off';
  const card = (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100001,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(255,255,255,0.55)', backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)', fontFamily: k.fontFamily,
        animation: animate ? 'kl-overlay-in 0.2s ease' : undefined,
      }}
    >
      <div
        style={{
          minWidth: 220, padding: '28px 32px', background: '#fff', borderRadius: 14,
          boxShadow: '0 16px 48px rgba(0,0,0,0.18)', border: '1px solid #eee',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
          animation: animate ? 'kl-card-in 0.32s cubic-bezier(0.16,1,0.3,1)' : undefined,
        }}
      >
        {phase === 'success'
          ? <SuccessMark animate={animate} />
          : <KiteLoader size={36} />}
        <div style={{ fontSize: 14, fontWeight: 600, color: phase === 'success' ? k.green : k.text }}>
          {label || (phase === 'success' ? 'Connected' : 'Connecting…')}
        </div>
      </div>
    </div>
  );

  return createPortal(<><KiteLoaderStyles />{card}</>, document.body);
}

export default KiteLoader;
