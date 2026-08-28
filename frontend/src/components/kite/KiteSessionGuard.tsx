import React, { useEffect, useRef, useState } from 'react';
import {
  useKiteStatus, useKiteAuthBroadcast, useGenerateKiteSession, useOpenKiteLogin,
  useRefreshKiteSession,
} from '../../hooks/useKite';
import { notifyOrder } from '../../store/useKiteNotifications';
import { authSuccess, authIdle } from '../../store/useAuthFeedback';
import { ButtonLoader } from './KiteLoader';
import { k } from '../../styles/kiteUI';

const DISMISS_KEY = 'sterling_kite_session_guard_dismissed';

// Watches the live Kite /status for a connected→disconnected transition (the daily
// ~6 AM token expiry, or a revoked session). When that happens it:
//   • fires a toast so the user knows the session lapsed, and
//   • auto-opens a reconnect modal with the Kite login link + paste-token flow.
// If the account has a refresh_token, useKiteAutoSession is already trying a silent
// renewal — so we hold the modal briefly to let that win before prompting.
export function KiteSessionGuard() {
  // Mounted for the lifetime of the Kite tab, so this is where the app listens for
  // the callback tab's "connected" broadcast — the modal then closes itself as soon
  // as the redirect login lands, without the user touching anything here.
  useKiteAuthBroadcast();
  const { data: status } = useKiteStatus();
  const kiteLogin = useOpenKiteLogin();
  const gen = useGenerateKiteSession();
  const refresh = useRefreshKiteSession();
  const [open, setOpen] = useState(false);
  const [reqToken, setReqToken] = useState('');
  const prevConnected = useRef<boolean | null>(null);
  const notifiedRef = useRef(false);
  const graceTimer = useRef<number | null>(null);

  const connected = !!status?.connected;
  const hasAccount = !!status?.account_id;
  /**
   * Sterling could not ASK Kite, so it does not know. The stored token is
   * intact.
   *
   * Treated as "still connected" for the purposes of this prompt: nothing has
   * expired, a request failed, and the next poll will very likely answer. This
   * is why the modal used to appear over a perfectly valid session — a dropped
   * request and a refused token arrived as the same `connected: false`.
   */
  const unknown = !!status?.transient;
  const canAutoRecover = !!status?.has_refresh_token;

  const handleDismiss = () => {
    try {
      sessionStorage.setItem(DISMISS_KEY, 'true');
    } catch {}
    if (graceTimer.current) {
      window.clearTimeout(graceTimer.current);
      graceTimer.current = null;
    }
    setOpen(false);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) handleDismiss();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    // Wait for the first real status poll.
    if (!status) return;

    const was = prevConnected.current;
    // Do NOT record an unknown as a disconnect. Otherwise one dropped request
    // rewrites `was` to false, and the genuine expiry that follows is no longer a
    // true -> false transition, so it goes unannounced entirely.
    if (!status?.transient) prevConnected.current = connected;

    if (connected) {
      // Session is healthy again — reset dismissal flag and state
      try {
        sessionStorage.removeItem(DISMISS_KEY);
      } catch {}
      notifiedRef.current = false;
      if (graceTimer.current) {
        window.clearTimeout(graceTimer.current);
        graceTimer.current = null;
      }
      setOpen(false);
      if (was === false) {
        authSuccess(status?.user_name ? `Connected · ${status.user_name}` : 'Kite connected');
        notifyOrder({
          kind: 'complete',
          title: 'Kite connected',
          message: status?.user_name
            ? `Signed in as ${status.user_name}${status.kite_user_id ? ` (${status.kite_user_id})` : ''}.`
            : 'Your Kite session is now active.',
        });
      }
      return;
    }

    // Only prompt on a genuine connected -> disconnected transition
    // Do not endlessly prompt on cold page loads or if previously dismissed.
    let isDismissed = false;
    try {
      isDismissed = sessionStorage.getItem(DISMISS_KEY) === 'true';
    } catch {}

    // A failed CHECK is not a lapsed session. Keep polling and say nothing: the
    // token is still applied, and only Kite actually refusing it earns a prompt.
    if (unknown) return;

    if (was === true && !connected && hasAccount && !isDismissed) {
      if (notifiedRef.current) return;
      notifiedRef.current = true;

      notifyOrder({
        kind: 'error',
        title: 'Kite session expired',
        message: canAutoRecover
          ? 'Renewing automatically… reconnect manually if this persists.'
          : 'Your Kite session has lapsed. Reconnect to resume live data and trading.',
      });

      // Give the silent refresh a moment to win before prompting the user.
      const delay = canAutoRecover ? 8000 : 500;
      if (graceTimer.current) window.clearTimeout(graceTimer.current);
      graceTimer.current = window.setTimeout(() => {
        if (!prevConnected.current) setOpen(true);
      }, delay);
    } else if (was === true) {
      authIdle();
    }
  }, [status, connected, hasAccount, canAutoRecover, unknown]);

  useEffect(() => () => { if (graceTimer.current) window.clearTimeout(graceTimer.current); }, []);

  if (!open) return null;

  return (
    <div
      onClick={handleDismiss}
      style={{
        position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: k.fontFamily,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 440, maxWidth: '90vw', background: 'var(--k-bg)', borderRadius: 8,
          boxShadow: '0 12px 40px rgba(0,0,0,0.25)', padding: 24, position: 'relative',
        }}
      >
        <button
          onClick={handleDismiss}
          style={{
            position: 'absolute', top: 14, right: 14, border: 0, background: 'transparent',
            color: 'var(--k-dim-2)', fontSize: 16, cursor: 'pointer', padding: 4, lineHeight: 1,
          }}
          title="Dismiss"
        >
          ✕
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--k-red-strong)' }} />
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--k-ink-1)' }}>Kite session expired</span>
        </div>
        <div style={{ fontSize: 13, color: 'var(--k-ink-4)', lineHeight: 1.6, marginBottom: 16 }}>
          Zerodha invalidates the access token at its daily ~6 AM IST reset (or when the
          session is revoked). Reconnect to resume live prices, the engine scan, and order placement.
        </div>

        {canAutoRecover && (
          <button
            onClick={() => refresh.mutate({})}
            disabled={refresh.isPending}
            style={{
              width: '100%', marginBottom: 10, padding: '9px 12px', borderRadius: 5,
              border: '1px solid var(--k-border)', background: 'var(--k-surface)', color: 'var(--k-blue-kite)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {refresh.isPending ? <ButtonLoader color="var(--k-blue-kite)" /> : '↻ Try automatic renewal'}
          </button>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button
            disabled={kiteLogin.opening}
            onClick={kiteLogin.open}
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 5, border: 'none',
              background: 'var(--k-green)', color: 'var(--k-on-accent)', fontSize: 13, fontWeight: 700,
              cursor: kiteLogin.opening ? 'wait' : 'pointer', opacity: kiteLogin.opening ? 0.6 : 1,
            }}
          >
            {kiteLogin.opening ? 'Opening…' : '1 · Open Kite Login ↗'}
          </button>
          <label style={{ fontSize: 10, letterSpacing: 1, color: 'var(--k-dim)', marginTop: 4 }}>
            2 · PASTE request_token — only needed if no Redirect URL is registered
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={reqToken}
              onChange={(e) => setReqToken(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && reqToken.trim() && !gen.isPending) {
                  gen.mutate(
                    { request_token: reqToken.trim(), account_id: status?.account_id ?? undefined },
                    { onSuccess: () => { setReqToken(''); setOpen(false); } },
                  );
                }
              }}
              placeholder="request_token from redirect URL"
              style={{
                flex: 1, padding: '8px 10px', border: '1px solid var(--k-border)', borderRadius: 5,
                fontSize: 12, color: 'var(--k-text)', outline: 'none', boxSizing: 'border-box',
              }}
            />
            <button
              disabled={!reqToken.trim() || gen.isPending}
              onClick={() => gen.mutate(
                { request_token: reqToken.trim(), account_id: status?.account_id ?? undefined },
                { onSuccess: () => { setReqToken(''); setOpen(false); } },
              )}
              style={{
                padding: '8px 16px', borderRadius: 5, border: 'none', background: 'var(--k-green)',
                color: 'var(--k-on-accent)', fontSize: 12, fontWeight: 700,
                cursor: reqToken.trim() && !gen.isPending ? 'pointer' : 'not-allowed',
                opacity: reqToken.trim() && !gen.isPending ? 1 : 0.5,
              }}
            >
              {gen.isPending ? <ButtonLoader /> : 'Connect'}
            </button>
          </div>
          {gen.error && <div style={{ color: 'var(--k-red-strong)', fontSize: 11, marginTop: 2 }}>✗ {gen.error.message}</div>}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button
            onClick={handleDismiss}
            style={{
              padding: '6px 14px', borderRadius: 5, border: '1px solid var(--k-border)',
              background: 'var(--k-bg)', color: 'var(--k-ink-4)', fontSize: 12, cursor: 'pointer',
            }}
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export default KiteSessionGuard;
