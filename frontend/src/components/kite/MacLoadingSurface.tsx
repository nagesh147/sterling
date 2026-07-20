import React from 'react';
import { createPortal } from 'react-dom';
import { k } from '../../styles/kiteUI';
import { KiteLoader } from './KiteLoader';

const MAC_LOADING_CSS = `
@keyframes mls-shimmer {
  0% { transform: translate3d(-115%, 0, 0); }
  100% { transform: translate3d(115%, 0, 0); }
}
@keyframes mls-reveal {
  0% { opacity: 0; transform: translate3d(0, 7px, 0) scale(.997); }
  100% { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
}
@keyframes mls-overlay-in {
  0% { opacity: 0; }
  100% { opacity: 1; }
}
@keyframes mls-card-in {
  0% { opacity: 0; transform: translate3d(0, 10px, 0) scale(.965); }
  100% { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
}
@keyframes mls-progress {
  0% { transform: translate3d(-120%, 0, 0); }
  100% { transform: translate3d(310%, 0, 0); }
}
.mls-skeleton {
  position: relative;
  display: block;
  overflow: hidden;
  background: linear-gradient(180deg, #f1f2f4 0%, #e9ebee 100%);
  contain: paint;
}
.mls-skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 20%, rgba(255,255,255,.82) 49%, transparent 78%);
  transform: translate3d(-115%, 0, 0);
  animation: mls-shimmer 1.05s cubic-bezier(.4, 0, .2, 1) infinite;
  will-change: transform;
}
.mls-reveal {
  animation: mls-reveal 280ms cubic-bezier(.16, 1, .3, 1) both;
  will-change: transform, opacity;
}
.mls-overlay {
  animation: mls-overlay-in 140ms ease-out both;
  transition: opacity 180ms ease-out;
}
.mls-overlay[data-leaving='true'] { opacity: 0; pointer-events: none; }
.mls-boot-card {
  animation: mls-card-in 260ms cubic-bezier(.16, 1, .3, 1) both;
  transition: transform 180ms ease-out, opacity 180ms ease-out;
  will-change: transform, opacity;
}
.mls-overlay[data-leaving='true'] .mls-boot-card {
  opacity: 0;
  transform: translate3d(0, -4px, 0) scale(.985);
}
.mls-progress-runner {
  animation: mls-progress 1.1s cubic-bezier(.4, 0, .2, 1) infinite;
  will-change: transform;
}
@media (prefers-reduced-motion: reduce) {
  .mls-skeleton::after, .mls-reveal, .mls-overlay, .mls-boot-card, .mls-progress-runner {
    animation: none !important;
    transition: none !important;
  }
}
`;

let loadingStylesInstalled = false;

function ensureMacLoadingStyles() {
  if (loadingStylesInstalled || typeof document === 'undefined') return;
  const existing = document.getElementById('sterling-mac-loading-styles');
  if (existing) {
    loadingStylesInstalled = true;
    return;
  }
  const style = document.createElement('style');
  style.id = 'sterling-mac-loading-styles';
  style.textContent = MAC_LOADING_CSS;
  document.head.appendChild(style);
  loadingStylesInstalled = true;
}

export function MacLoadingStyles() {
  ensureMacLoadingStyles();
  return null;
}

export function MacSkeleton({
  width = '100%',
  height = 12,
  radius = 6,
  style,
  testId,
}: {
  width?: React.CSSProperties['width'];
  height?: React.CSSProperties['height'];
  radius?: React.CSSProperties['borderRadius'];
  style?: React.CSSProperties;
  testId?: string;
}) {
  ensureMacLoadingStyles();
  return (
    <span
      data-testid={testId}
      className="mls-skeleton"
      aria-hidden="true"
      style={{ width, height, borderRadius: radius, ...style }}
    />
  );
}

export function MacReveal({
  children,
  delay = 0,
  style,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
  className?: string;
}) {
  ensureMacLoadingStyles();
  return (
    <div
      className={`mls-reveal${className ? ` ${className}` : ''}`}
      style={{ animationDelay: `${Math.max(0, delay)}ms`, ...style }}
    >
      {children}
    </div>
  );
}

export function MacBootOverlay({
  active,
  title = 'Preparing Sterling Kite',
  detail = 'Syncing session, workspace and live market surfaces',
}: {
  active: boolean;
  title?: string;
  detail?: string;
}) {
  const [mounted, setMounted] = React.useState(active);
  const [leaving, setLeaving] = React.useState(false);

  ensureMacLoadingStyles();

  React.useEffect(() => {
    if (active) {
      setMounted(true);
      setLeaving(false);
      return;
    }
    if (!mounted) return;
    setLeaving(true);
    const timer = window.setTimeout(() => {
      setMounted(false);
      setLeaving(false);
    }, 190);
    return () => window.clearTimeout(timer);
  }, [active, mounted]);

  if (!mounted || typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="mls-overlay"
      data-leaving={leaving ? 'true' : 'false'}
      role="status"
      aria-live="polite"
      aria-label={title}
      style={{
        position: 'fixed', inset: 0, zIndex: 100000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'linear-gradient(145deg, rgba(252,253,254,.985), rgba(246,248,251,.97))',
        fontFamily: k.fontFamily,
      }}
    >
      <div
        className="mls-boot-card"
        style={{
          width: 'min(360px, calc(100vw - 40px))',
          padding: '24px 26px 22px',
          borderRadius: 18,
          background: 'rgba(255,255,255,.96)',
          border: '1px solid rgba(15,23,42,.08)',
          boxShadow: '0 24px 70px rgba(15,23,42,.14), 0 2px 10px rgba(15,23,42,.06)',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(145deg, #ffffff, #eef1f5)',
            border: '1px solid rgba(15,23,42,.08)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.9), 0 5px 14px rgba(15,23,42,.08)',
            flexShrink: 0,
          }}>
            <KiteLoader size={24} color="#6b7280" styleOverride="mac" />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 650, color: '#20242b', letterSpacing: '-.01em' }}>{title}</div>
            <div style={{ marginTop: 4, fontSize: 11.5, lineHeight: 1.45, color: '#7c838d' }}>{detail}</div>
          </div>
        </div>

        <div style={{ marginTop: 20, height: 3, borderRadius: 999, overflow: 'hidden', background: '#edf0f3' }}>
          <div
            className="mls-progress-runner"
            style={{ width: '34%', height: '100%', borderRadius: 999, background: 'linear-gradient(90deg, #8bb8ff, #4184f3)' }}
          />
        </div>

        <div style={{ marginTop: 13, display: 'flex', alignItems: 'center', gap: 12, color: '#a0a6ae', fontSize: 9.5, letterSpacing: '.03em', textTransform: 'uppercase' }}>
          <span>Session</span><span style={{ width: 3, height: 3, borderRadius: '50%', background: '#c5c9cf' }} />
          <span>Workspace</span><span style={{ width: 3, height: 3, borderRadius: '50%', background: '#c5c9cf' }} />
          <span>Market data</span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
