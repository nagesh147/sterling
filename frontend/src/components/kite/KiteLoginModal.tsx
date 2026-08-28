import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import type { KiteLoginPhase } from '../../hooks/useKite';

/**
 * The Kite login handshake, shown inside the app.
 *
 * The login itself has to happen on Zerodha's own page — their 2FA is
 * interactive by design and cannot be embedded (their headers forbid framing,
 * and so do ours). So this is not the login; it is the app saying what is
 * happening while a small popup does it, and saying it here rather than leaving
 * the operator staring at an unchanged screen.
 *
 * **There is deliberately no field to paste a `request_token` into.** That token
 * is single-use, and by the time it is visible in the popup's address bar the
 * callback has already spent it — so a paste box could only ever hand back
 * something guaranteed to be rejected, which is precisely the dead end this
 * replaces. If the handshake fails the answer is a fresh login, not a fresh
 * paste, so that is the only action offered.
 *
 * Rendered as a portal-free overlay on purpose: it is owned by the pane that
 * starts the login, so it lives and dies with it.
 */
export function KiteLoginModal({
  phase, error, onRetry, onDismiss,
}: {
  phase: KiteLoginPhase;
  error: string | null;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  if (phase === 'idle') return null;

  const done = phase === 'done';
  const failed = phase === 'failed';
  const tone = done ? k.green : failed ? k.red : k.blue;

  const title = done ? 'Connected to Kite'
    : failed ? 'Login did not finish'
    : phase === 'opening' ? 'Opening Kite…'
    : 'Waiting for Kite';

  const body = done
    ? 'Sterling has the session. Nothing else to do — the window has closed itself.'
    : failed
      ? (error ?? 'The login did not complete.')
      : phase === 'opening'
        ? 'Fetching a fresh login link. Login links are only good for about 15 minutes, so Sterling mints a new one each time.'
        : 'Finish signing in on the Kite window. This page updates by itself when it completes — there is no token to copy.';

  // Escape closes a finished handshake, but never one still in flight: closing
  // mid-login would leave the popup orphaned with no listener.
  React.useEffect(() => {
    if (!done && !failed) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onDismiss(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [done, failed, onDismiss]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed', inset: 0, zIndex: 10050,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,.34)', padding: 24,
      }}
      onClick={() => { if (done || failed) onDismiss(); }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 380, background: k.bg,
          border: `1px solid ${k.border}`, borderRadius: 10, overflow: 'hidden',
          boxShadow: '0 1px 2px rgba(0,0,0,.04), 0 14px 36px rgba(0,0,0,.18)',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px',
          background: tint(tone, 10), borderBottom: `1px solid ${k.border}`,
        }}>
          <span
            aria-hidden
            style={{
              width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              background: tint(tone, 22), color: tone, fontSize: 13, fontWeight: 800,
            }}
          >
            {done ? '✓' : failed ? '!' : '·'}
          </span>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: k.text }}>{title}</span>
        </div>

        <div style={{ padding: '14px 16px', fontSize: 11, color: k.dim, lineHeight: 1.6 }}>
          {body}
          {!done && !failed && (
            /* A determinate bar would be a lie: how long this takes is however
               long the operator spends on Zerodha's 2FA. */
            <div style={{
              marginTop: 12, height: 2, borderRadius: 2, overflow: 'hidden',
              background: k.border,
            }}>
              <div style={{
                width: '38%', height: '100%', background: tone,
                animation: 'kite-login-slide 1.15s ease-in-out infinite',
              }} />
            </div>
          )}
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8,
          padding: '11px 16px', borderTop: `1px solid ${k.border}`, background: k.surface,
        }}>
          {failed && (
            <button
              type="button"
              onClick={onRetry}
              style={{
                minHeight: 30, padding: '0 12px', borderRadius: 6, cursor: 'pointer',
                border: 'none', background: k.blue, color: 'var(--k-on-accent)',
                fontFamily: 'inherit', fontSize: 11, fontWeight: 700,
              }}
            >
              Try again
            </button>
          )}
          <button
            type="button"
            onClick={onDismiss}
            disabled={!done && !failed}
            title={done || failed ? undefined : 'Finish or close the Kite window first'}
            style={{
              minHeight: 30, padding: '0 12px', borderRadius: 6,
              border: `1px solid ${k.border}`, background: k.bg,
              color: done || failed ? k.text : k.dim,
              fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
              cursor: done || failed ? 'pointer' : 'not-allowed',
              opacity: done || failed ? 1 : 0.55,
            }}
          >
            {done ? 'Done' : 'Close'}
          </button>
        </div>
      </div>

      <style>{'@keyframes kite-login-slide{0%{transform:translateX(-100%)}100%{transform:translateX(320%)}}'}</style>
    </div>
  );
}

export default KiteLoginModal;
