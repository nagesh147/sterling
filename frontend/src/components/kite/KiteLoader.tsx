import React from 'react';
import { createPortal } from 'react-dom';
import { k } from '../../styles/kiteUI';
import { useKiteSettings, type LoaderStyle } from '../../store/useKiteSettings';
import { useAuthFeedback } from '../../store/useAuthFeedback';

const CSS = `
@keyframes kl-fade { 0% { opacity: 1; } 100% { opacity: .14; } }
@keyframes kl-spin { to { transform: rotate(360deg); } }
@keyframes kl-material-dash {
  0% { stroke-dasharray: 1 124; stroke-dashoffset: 0; }
  50% { stroke-dasharray: 92 124; stroke-dashoffset: -34; }
  100% { stroke-dasharray: 92 124; stroke-dashoffset: -124; }
}
@keyframes kl-bounce {
  0%, 80%, 100% { transform: translateY(0) scale(.82); opacity: .35; }
  40% { transform: translateY(-34%) scale(1); opacity: 1; }
}
@keyframes kl-pulse {
  0%, 100% { transform: scale(.72); opacity: .35; }
  50% { transform: scale(1); opacity: 1; }
}
@keyframes kl-windows-dot {
  0% { transform: rotate(0deg) translateY(-42%); opacity: .18; }
  35% { opacity: 1; }
  100% { transform: rotate(360deg) translateY(-42%); opacity: .18; }
}
@keyframes kl-overlay-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes kl-card-in {
  from { opacity: 0; transform: translate3d(0, 8px, 0) scale(.96); }
  to { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
}
@keyframes kl-check-ring {
  0% { transform: scale(.45); opacity: 0; }
  65% { transform: scale(1.06); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes kl-check-draw { to { stroke-dashoffset: 0; } }
@media (prefers-reduced-motion: reduce) {
  .kl-animated, .kl-animated * { animation-duration: .001ms !important; animation-iteration-count: 1 !important; }
}
`;

export function KiteLoaderStyles() {
  return <style>{CSS}</style>;
}

function normalizeStyle(style: LoaderStyle): Exclude<LoaderStyle, 'classic' | 'off'> {
  if (style === 'classic') return 'material';
  if (style === 'off') return 'minimal';
  return style;
}

function MacSpinner({ size, color }: { size: number; color: string }) {
  const spokes = 12;
  const barW = Math.max(1.5, size * .075);
  const barH = size * .255;
  return (
    <span className="kl-animated" aria-hidden="true" style={{ position: 'relative', width: size, height: size, display: 'inline-block' }}>
      {Array.from({ length: spokes }, (_, index) => (
        <span
          key={index}
          style={{
            position: 'absolute', left: '50%', top: '50%', width: barW, height: barH,
            borderRadius: barW, background: color, opacity: .14,
            transform: `translate(-50%, -50%) rotate(${index * 30}deg) translateY(-${size * .36}px)`,
            animation: 'kl-fade 1s linear infinite',
            animationDelay: `${-((spokes - index) / spokes)}s`,
          }}
        />
      ))}
    </span>
  );
}

function UbuntuSpinner({ size, color }: { size: number; color: string }) {
  const border = Math.max(2, size * .105);
  return (
    <span
      className="kl-animated"
      aria-hidden="true"
      style={{
        display: 'inline-block', width: size, height: size, borderRadius: '50%', boxSizing: 'border-box',
        border: `${border}px solid rgba(233,84,32,.18)`, borderTopColor: color,
        borderRightColor: color, animation: 'kl-spin .62s cubic-bezier(.55,.1,.45,.9) infinite',
      }}
    />
  );
}

function MaterialSpinner({ size, color }: { size: number; color: string }) {
  const stroke = Math.max(2, size * .1);
  return (
    <svg className="kl-animated" aria-hidden="true" width={size} height={size} viewBox="0 0 44 44" style={{ animation: 'kl-spin 1.25s linear infinite' }}>
      <circle cx="22" cy="22" r="19" fill="none" stroke="rgba(103,80,164,.14)" strokeWidth={stroke} />
      <circle
        cx="22" cy="22" r="19" fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
        style={{ animation: 'kl-material-dash 1.25s ease-in-out infinite' }}
      />
    </svg>
  );
}

function WindowsSpinner({ size, color }: { size: number; color: string }) {
  const dot = Math.max(2.5, size * .115);
  return (
    <span className="kl-animated" aria-hidden="true" style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      {Array.from({ length: 5 }, (_, index) => (
        <span
          key={index}
          style={{
            position: 'absolute', inset: 0, transformOrigin: '50% 50%',
            animation: 'kl-windows-dot 1.05s cubic-bezier(.1,.9,.2,1) infinite',
            animationDelay: `${index * .075}s`,
          }}
        >
          <span style={{ position: 'absolute', left: '50%', top: 0, width: dot, height: dot, marginLeft: -dot / 2, borderRadius: '50%', background: color }} />
        </span>
      ))}
    </span>
  );
}

function GnomeSpinner({ size, color }: { size: number; color: string }) {
  const dot = Math.max(4, size * .18);
  return (
    <span className="kl-animated" aria-hidden="true" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: dot * .42, width: size, height: size }}>
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          style={{ width: dot, height: dot, borderRadius: '50%', background: color, animation: 'kl-bounce .92s ease-in-out infinite', animationDelay: `${index * .12}s` }}
        />
      ))}
    </span>
  );
}

function KdeSpinner({ size, color }: { size: number; color: string }) {
  const ring = Math.max(2, size * .085);
  const inner = Math.max(3, size * .2);
  return (
    <span className="kl-animated" aria-hidden="true" style={{ position: 'relative', display: 'inline-block', width: size, height: size }}>
      <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', boxSizing: 'border-box', border: `${ring}px solid rgba(29,153,243,.16)`, borderLeftColor: color, borderBottomColor: color, animation: 'kl-spin .72s cubic-bezier(.2,.75,.25,1) infinite' }} />
      <span style={{ position: 'absolute', left: '50%', top: '50%', width: inner, height: inner, marginLeft: -inner / 2, marginTop: -inner / 2, borderRadius: '50%', background: color, animation: 'kl-pulse .72s ease-in-out infinite' }} />
    </span>
  );
}

function MinimalSpinner({ size, color }: { size: number; color: string }) {
  const dot = Math.max(3, size * .15);
  return (
    <span aria-hidden="true" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: dot * .55, width: size, height: size }}>
      {[.35, .58, .82].map((opacity, index) => (
        <span key={index} style={{ width: dot, height: dot, borderRadius: '50%', background: color, opacity }} />
      ))}
    </span>
  );
}

function defaultColor(style: ReturnType<typeof normalizeStyle>) {
  if (style === 'ubuntu') return '#e95420';
  if (style === 'mac') return '#68707c';
  if (style === 'material') return '#6750a4';
  if (style === 'windows') return '#0078d4';
  if (style === 'gnome') return '#3584e4';
  if (style === 'kde') return '#1d99f3';
  return k.dim;
}

export function KiteLoader({ size = 28, color, styleOverride }: { size?: number; color?: string; styleOverride?: LoaderStyle }) {
  const saved = useKiteSettings((state) => state.loaderStyle);
  const style = normalizeStyle(styleOverride ?? saved);
  const resolvedColor = color ?? defaultColor(style);

  let spinner: React.ReactNode;
  if (style === 'mac') spinner = <MacSpinner size={size} color={resolvedColor} />;
  else if (style === 'material') spinner = <MaterialSpinner size={size} color={resolvedColor} />;
  else if (style === 'windows') spinner = <WindowsSpinner size={size} color={resolvedColor} />;
  else if (style === 'gnome') spinner = <GnomeSpinner size={size} color={resolvedColor} />;
  else if (style === 'kde') spinner = <KdeSpinner size={size} color={resolvedColor} />;
  else if (style === 'minimal') spinner = <MinimalSpinner size={size} color={resolvedColor} />;
  else spinner = <UbuntuSpinner size={size} color={resolvedColor} />;

  return <><KiteLoaderStyles />{spinner}</>;
}

export function ButtonLoader({ color = '#fff' }: { color?: string }) {
  const saved = useKiteSettings((state) => state.loaderStyle);
  const style = normalizeStyle(saved);
  if (style === 'minimal') return <span aria-label="Loading">…</span>;
  return <KiteLoader size={14} color={color} styleOverride={style} />;
}

function SuccessMark({ size = 56, animate }: { size?: number; animate: boolean }) {
  if (!animate) {
    return (
      <span style={{ width: size, height: size, borderRadius: '50%', background: k.green, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: size * .5, fontWeight: 700 }}>
        ✓
      </span>
    );
  }

  return (
    <svg className="kl-animated" width={size} height={size} viewBox="0 0 52 52" aria-hidden="true" style={{ animation: 'kl-check-ring .45s cubic-bezier(.16,1,.3,1)' }}>
      <circle cx="26" cy="26" r="25" fill={k.green} />
      <path
        fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
        d="M15 27l7 7 15-16"
        style={{ strokeDasharray: 48, strokeDashoffset: 48, animation: 'kl-check-draw .4s .2s ease forwards' }}
      />
    </svg>
  );
}

export function KiteAuthOverlay() {
  const phase = useAuthFeedback((state) => state.phase);
  const label = useAuthFeedback((state) => state.label);
  const saved = useKiteSettings((state) => state.loaderStyle);
  const style = normalizeStyle(saved);

  if (phase === 'idle' || typeof document === 'undefined') return null;

  const animate = style !== 'minimal';
  const accent = defaultColor(style);
  const overlay = (
    <div
      role="status"
      aria-live="polite"
      aria-label={label || (phase === 'success' ? 'Connected' : 'Connecting')}
      style={{
        position: 'fixed', inset: 0, zIndex: 100001, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(248,250,252,.56)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
        fontFamily: k.fontFamily, animation: animate ? 'kl-overlay-in .16s ease-out' : undefined,
      }}
    >
      <div
        data-motion-popover
        style={{
          minWidth: 230, maxWidth: 'calc(100vw - 40px)', padding: '26px 30px', background: 'rgba(255,255,255,.96)',
          borderRadius: style === 'windows' ? 4 : style === 'ubuntu' ? 8 : 14,
          border: '1px solid rgba(15,23,42,.09)', boxShadow: '0 18px 50px rgba(15,23,42,.18)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 15,
          animation: animate ? 'kl-card-in .26s cubic-bezier(.16,1,.3,1)' : undefined,
        }}
      >
        {phase === 'success' ? <SuccessMark animate={animate} /> : <KiteLoader size={38} color={accent} styleOverride={style} />}
        <div style={{ fontSize: 14, fontWeight: 650, color: phase === 'success' ? k.green : k.text, textAlign: 'center' }}>
          {label || (phase === 'success' ? 'Connected' : 'Connecting…')}
        </div>
      </div>
    </div>
  );

  return createPortal(<><KiteLoaderStyles />{overlay}</>, document.body);
}

export default KiteLoader;
