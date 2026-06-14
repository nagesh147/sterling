import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { api } from '../utils/api';

type ModalView = 'none' | 'go-live-confirm';
type Status = { type: 'idle'|'saving'|'success'|'error'; msg: string };

export function PaperLiveToggle() {
  const qc      = useQueryClient();
  const { data: exData, isLoading: exLoading } = useExchanges();
  const update  = useUpdateExchange();

  const [modal, setModal]         = useState<ModalView>('none');
  const [status, setStatus]       = useState<Status>({ type: 'idle', msg: '' });
  const [testStatus, setTestStatus] = useState<{ ok: boolean; msg: string; hint?: string } | null>(null);
  const [testing, setTesting]     = useState(false);

  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  const isPaper = delta ? delta.is_paper : true;
  const hasKeys = !!delta?.has_credentials;
  const keyHint = delta?.api_key_hint ?? '';
  const saving  = status.type === 'saving';

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['exchanges'] });
    qc.invalidateQueries({ queryKey: ['config-info'] });
    qc.invalidateQueries({ queryKey: ['signals-all'] });
    qc.invalidateQueries({ queryKey: ['positions'] });
    qc.invalidateQueries({ queryKey: ['positions', 'live'] });
    qc.invalidateQueries({ queryKey: ['positions', 'paper'] });
  };

  const testConnection = async () => {
    setTesting(true); setTestStatus(null);
    try {
      const res = await api.get<{ ok: boolean; message?: string; reason?: string; hint?: string; account?: string }>('/api/v1/trading/test-credentials');
      setTestStatus({ ok: res.ok, msg: res.ok ? (res.message ?? 'Connected') : (res.reason ?? 'Failed'), hint: res.hint });
    } catch (e: unknown) {
      setTestStatus({ ok: false, msg: (e as Error).message });
    } finally { setTesting(false); }
  };

  // Auto-verify saved credentials on load so the toggle always reflects real connection state
  useEffect(() => {
    if (hasKeys && testStatus === null && !testing) {
      testConnection();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasKeys]);

  const handleLiveClick = () => {
    if (isLive || !hasKeys) return;
    setStatus({ type: 'idle', msg: '' });
    setTestStatus(null);
    setModal('go-live-confirm');
  };

  const confirmGoLive = () => {
    if (!delta) {
      setStatus({ type: 'error', msg: 'Exchange config not loaded — try refreshing.' });
      return;
    }
    setStatus({ type: 'saving', msg: 'Switching to Live…' });
    Promise.all([
      api.post('/api/v1/trading/algo-router-mode', { mode: 'live' }),
      update.mutateAsync({ id: delta.id, is_paper: false }),
    ]).then(() => {
      setStatus({ type: 'success', msg: '● Now in Live mode' });
      invalidateAll();
      setTimeout(() => { setModal('none'); setStatus({ type: 'idle', msg: '' }); }, 1200);
    }).catch((e) => {
      setStatus({ type: 'error', msg: (e as Error).message });
    });
  };

  const switchToPaper = () => {
    if (!delta) return;
    setStatus({ type: 'saving', msg: '' });
    Promise.all([
      api.post('/api/v1/trading/algo-router-mode', { mode: 'paper' }),
      update.mutateAsync({ id: delta.id, is_paper: true }),
    ]).then(() => {
      invalidateAll();
      setStatus({ type: 'idle', msg: '' });
    }).catch((e) => {
      setStatus({ type: 'error', msg: (e as Error).message });
    });
  };

  const closeModal = () => {
    if (saving) return;
    setModal('none');
    setStatus({ type: 'idle', msg: '' });
    setTestStatus(null);
  };

  return (
    <>
      {/* Toggle pill — PAPER / LIVE (SHADOW = PAPER with keys, backend detail) */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        background: 'var(--t-bg3, var(--bg-surface))',
        border: `1px solid ${isLive ? 'var(--t-green, var(--accent))50' : 'var(--t-border, var(--border))'}`,
        borderRadius: 5,
        overflow: 'hidden',
        cursor: saving ? 'wait' : 'pointer',
        opacity: saving ? 0.7 : 1,
        padding: 2,
        gap: 2,
      }}>
        <button
          onClick={isLive ? switchToPaper : undefined}
          disabled={saving || !isLive}
          style={{
            padding: '3px 12px',
            border: 'none',
            borderRadius: 4,
            cursor: isLive ? 'pointer' : 'default',
            background: !isLive ? 'var(--t-bg2, var(--bg-card))' : 'transparent',
            color: !isLive ? 'var(--t-blue, var(--blue))' : 'var(--t-dim, var(--text-dim))',
            fontFamily: 'inherit',
            fontSize: 10,
            fontWeight: !isLive ? 600 : 400,
            letterSpacing: '0.08em',
            transition: 'background 0.15s, color 0.15s',
            lineHeight: 1,
          }}
        >
          {isPaper && hasKeys ? 'PAPER' : 'PAPER'}
        </button>
        <button
          onClick={isLive ? undefined : handleLiveClick}
          disabled={saving}
          style={{
            padding: '3px 12px',
            border: 'none',
            borderRadius: 4,
            cursor: !isLive ? 'pointer' : 'default',
            background: isLive ? 'var(--t-green, var(--accent))18' : 'transparent',
            color: isLive ? 'var(--t-green, var(--accent))' : 'var(--t-dim, var(--text-dim))',
            fontFamily: 'inherit',
            fontSize: 10,
            fontWeight: isLive ? 700 : 400,
            letterSpacing: '0.08em',
            transition: 'background 0.15s, color 0.15s',
            lineHeight: 1,
          }}
        >
          {isLive ? '● LIVE' : exLoading ? '…' : 'LIVE'}
        </button>
      </div>

      {/* ── Go-Live confirmation (keys already set) ── */}
      {modal === 'go-live-confirm' && (
        <Backdrop onClose={closeModal}>
          <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--accent)', marginBottom: 4 }}>⚡ Switch to Live Trading</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 18, lineHeight: 1.6 }}>
            You're about to trade with real money on Delta Exchange India.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 18 }}>
            {[
              { icon: '💸', text: 'Orders execute on Delta Exchange — real funds deducted' },
              { icon: '📊', text: 'Positions track your actual account balance & P&L' },
              { icon: '📋', text: 'Paper positions will not be shown in Live mode' },
              { icon: '⚙️', text: 'Signal mode and leverage settings remain unchanged' },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 11, color: 'var(--text-muted)' }}>
                <span style={{ fontSize: 13, lineHeight: 1.3, flexShrink: 0 }}>{icon}</span>
                <span style={{ lineHeight: 1.5 }}>{text}</span>
              </div>
            ))}
          </div>

          {/* Account info + Test button */}
          <div style={{ marginBottom: 16, padding: '10px 12px', background: 'var(--bg)', borderRadius: 4, border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: testStatus ? 8 : 0 }}>
              <div>
                <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>CONNECTED ACCOUNT</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  Delta Exchange India{keyHint ? ` · ••••${keyHint}` : ''}
                </div>
              </div>
              <button onClick={testConnection} disabled={testing}
                style={{ fontSize: 9, padding: '2px 8px', background: 'var(--bg-input)', color: 'var(--text-dim)', border: '1px solid var(--border)', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit' }}>
                {testing ? 'Testing…' : 'Test'}
              </button>
            </div>
            {testStatus && (
              <div style={{ padding: '7px 10px', borderRadius: 4, marginTop: 4,
                background: testStatus.ok ? '#071a14' : '#1a0707',
                border: `1px solid ${testStatus.ok ? 'var(--accent)33' : 'var(--danger)33'}` }}>
                <div style={{ fontSize: 10, color: testStatus.ok ? 'var(--accent)' : 'var(--danger)', marginBottom: testStatus.hint ? 3 : 0 }}>
                  {testStatus.ok ? '✅ ' : '❌ '}{testStatus.msg}
                </div>
                {testStatus.hint && (
                  <>
                    <div style={{ fontSize: 9, color: '#f0c040', lineHeight: 1.5, marginBottom: 4 }}>{testStatus.hint}</div>
                    <a href="https://www.delta.exchange/app/account/manageapikeys" target="_blank" rel="noopener noreferrer"
                      style={{ fontSize: 9, color: 'var(--accent)', textDecoration: 'none', background: '#0f2a1a', border: '1px solid var(--accent)33', borderRadius: 3, padding: '3px 8px' }}>
                      Open delta.exchange API Keys ↗
                    </a>
                  </>
                )}
              </div>
            )}
          </div>

          <StatusBar status={status} />

          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={closeModal} disabled={saving} style={btnSecondary}>Stay Paper</button>
            <button onClick={confirmGoLive} disabled={saving || status.type === 'success'}
              style={{ ...btnPrimary, opacity: saving ? 0.7 : 1 }}>
              {saving ? 'Switching…' : status.type === 'success' ? '✓ Done' : '▶ Go Live'}
            </button>
          </div>
        </Backdrop>
      )}
    </>
  );
}

// ── Status banner ─────────────────────────────────────────────────────────────
function StatusBar({ status }: { status: Status }) {
  if (status.type === 'idle') return null;
  const colors: Record<string, string> = {
    saving:  'var(--text-faint)',
    success: 'var(--accent)',
    error:   'var(--danger)',
  };
  const icons: Record<string, string> = { saving: '⏳', success: '✅', error: '❌' };
  return (
    <div style={{ marginBottom: 12, padding: '8px 10px', borderRadius: 4,
      background: status.type === 'success' ? '#071a14' : status.type === 'error' ? '#1a0707' : 'var(--bg)',
      border: `1px solid ${colors[status.type] ?? 'var(--border)'}33`,
      fontSize: 11, fontWeight: 600, color: colors[status.type] }}>
      {icons[status.type]} {status.msg}
    </div>
  );
}

// ── Shared styles ─────────────────────────────────────────────────────────────
const btnPrimary: React.CSSProperties = {
  flex: 2,
  padding: '10px 0',
  background: 'var(--accent)',
  color: '#000',
  border: 'none',
  borderRadius: 7,
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  fontWeight: 800,
  letterSpacing: '0.08em',
};
const btnSecondary: React.CSSProperties = {
  flex: 1,
  padding: '10px 0',
  background: 'var(--bg-surface)',
  color: 'var(--text-muted)',
  border: '1px solid var(--border)',
  borderRadius: 7,
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 11,
};

function Backdrop({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  // Portal to <body>: this toggle lives in the app header, which sits in a
  // `position:relative; z-index:1` stacking context. Rendered inline, the
  // fixed overlay's z-index:3000 is trapped inside that context and paints
  // BEHIND the main content — so only the top bar darkened and the dialog was
  // unreachable ("page top goes blank, doesn't switch to live"). Portaling out
  // of the header lets the overlay cover the whole viewport as intended.
  return createPortal(
    // zIndex must clear `.term-root` (the app root: position:fixed; z-index:10000).
    // Portaled to <body>, the overlay is now a sibling of .term-root, so 3000
    // would still lose to 10000 and stay hidden. 100000 puts it above the app.
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 100000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        width: 360, background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 6, padding: '24px 28px', textAlign: 'center',
      }}>
        {children}
      </div>
    </div>,
    document.body,
  );
}
