import React, { useEffect, useRef, useState } from 'react';
import {
  useKiteStatus, useKiteLoginUrl, useGenerateKiteSession, useRefreshKiteSession,
} from '../../hooks/useKite';
import { notifyOrder } from '../../store/useKiteNotifications';
import { k } from '../../styles/kiteUI';

// Watches the live Kite /status for a connected→disconnected transition (the daily
// ~6 AM token expiry, or a revoked session). When that happens it:
//   • fires a toast so the user knows the session lapsed, and
//   • auto-opens a reconnect modal with the Kite login link + paste-token flow.
// If the account has a refresh_token, useKiteAutoSession is already trying a silent
// renewal — so we hold the modal briefly to let that win before prompting.
export function KiteSessionGuard() {
  const { data: status } = useKiteStatus();
  const { data: lu } = useKiteLoginUrl(true);
  const gen = useGenerateKiteSession();
  const refresh = useRefreshKiteSession();
  const [open, setOpen] = useState(false);
  const [reqToken, setReqToken] = useState('');
  const prevConnected = useRef<boolean | null>(null);
  const notifiedRef = useRef(false);
  const graceTimer = useRef<number | null>(null);

  const connected = !!status?.connected;
  const hasAccount = !!status?.account_id;
  const canAutoRecover = !!status?.has_refresh_token;

  useEffect(() => {
    const was = prevConnected.current;
    prevConnected.current = connected;

    // Only react to a real transition out of a connected session.
    if (was !== true || connected || !hasAccount) {
      if (connected) {
        // Session is healthy again — reset state + close the modal.
        notifiedRef.current = false;
        if (graceTimer.current) { window.clearTimeout(graceTimer.current); graceTimer.current = null; }
        setOpen(false);
      }
      return;
    }

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
  }, [connected, hasAccount, canAutoRecover]);

  useEffect(() => () => { if (graceTimer.current) window.clearTimeout(graceTimer.current); }, []);

  if (!open) return null;

  return (
    <div
      onClick={() => setOpen(false)}
      style={{
        position: 'fixed', inset: 0, zIndex: 10000, background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: k.fontFamily,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 440, maxWidth: '90vw', background: '#fff', borderRadius: 8,
          boxShadow: '0 12px 40px rgba(0,0,0,0.25)', padding: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#e53935' }} />
          <span style={{ fontSize: 16, fontWeight: 700, color: '#333' }}>Kite session expired</span>
        </div>
        <div style={{ fontSize: 13, color: '#666', lineHeight: 1.6, marginBottom: 16 }}>
          Zerodha invalidates the access token at its daily ~6 AM IST reset (or when the
          session is revoked). Reconnect to resume live prices, the engine scan, and order placement.
        </div>

        {canAutoRecover && (
          <button
            onClick={() => refresh.mutate({})}
            disabled={refresh.isPending}
            style={{
              width: '100%', marginBottom: 10, padding: '9px 12px', borderRadius: 5,
              border: '1px solid #e0e0e0', background: '#f9f9f9', color: '#387ed1',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {refresh.isPending ? 'Renewing…' : '↻ Try automatic renewal'}
          </button>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button
            disabled={!lu?.login_url}
            onClick={() => lu?.login_url && window.open(lu.login_url, '_blank', 'noopener')}
            style={{
              width: '100%', padding: '10px 12px', borderRadius: 5, border: 'none',
              background: '#4caf50', color: '#fff', fontSize: 13, fontWeight: 700,
              cursor: lu?.login_url ? 'pointer' : 'not-allowed', opacity: lu?.login_url ? 1 : 0.5,
            }}
          >
            1 · Open Kite Login ↗
          </button>
          <label style={{ fontSize: 10, letterSpacing: 1, color: '#9b9b9b', marginTop: 4 }}>
            2 · PASTE request_token
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={reqToken}
              onChange={(e) => setReqToken(e.target.value)}
              placeholder="request_token from redirect URL"
              style={{
                flex: 1, padding: '8px 10px', border: '1px solid #e0e0e0', borderRadius: 5,
                fontSize: 12, color: '#444', outline: 'none', boxSizing: 'border-box',
              }}
            />
            <button
              disabled={!reqToken.trim() || gen.isPending}
              onClick={() => gen.mutate(
                { request_token: reqToken.trim(), account_id: status?.account_id ?? undefined },
                { onSuccess: () => { setReqToken(''); setOpen(false); } },
              )}
              style={{
                padding: '8px 16px', borderRadius: 5, border: 'none', background: '#4caf50',
                color: '#fff', fontSize: 12, fontWeight: 700,
                cursor: reqToken.trim() && !gen.isPending ? 'pointer' : 'not-allowed',
                opacity: reqToken.trim() && !gen.isPending ? 1 : 0.5,
              }}
            >
              {gen.isPending ? '…' : 'Connect'}
            </button>
          </div>
          {gen.error && <div style={{ color: '#e53935', fontSize: 11, marginTop: 2 }}>✗ {gen.error.message}</div>}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <button
            onClick={() => setOpen(false)}
            style={{
              padding: '6px 14px', borderRadius: 5, border: '1px solid #e0e0e0',
              background: '#fff', color: '#666', fontSize: 12, cursor: 'pointer',
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
