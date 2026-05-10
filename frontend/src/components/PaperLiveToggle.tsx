import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { api } from '../utils/api';

type ModalView = 'none' | 'go-live-confirm' | 'add-keys';
type Status = { type: 'idle'|'saving'|'success'|'error'; msg: string };

export function PaperLiveToggle() {
  const qc      = useQueryClient();
  const { data: exData, isLoading: exLoading } = useExchanges();
  const update  = useUpdateExchange();

  const [modal, setModal]         = useState<ModalView>('none');
  const [apiKey, setApiKey]       = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [status, setStatus]       = useState<Status>({ type: 'idle', msg: '' });
  const [testStatus, setTestStatus] = useState<{ ok: boolean; msg: string; hint?: string } | null>(null);
  const [testing, setTesting]     = useState(false);

  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  const hasKeys = !!delta?.has_credentials;
  const keyHint = delta?.api_key_hint ?? '';
  const saving  = status.type === 'saving';

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['exchanges'] });
    qc.invalidateQueries({ queryKey: ['config-info'] });
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

  const handleLiveClick = () => {
    if (isLive) return;
    setStatus({ type: 'idle', msg: '' });
    setTestStatus(null);
    if (!hasKeys) { setModal('add-keys'); return; }
    setModal('go-live-confirm');
  };

  const confirmGoLive = () => {
    if (!delta) {
      setStatus({ type: 'error', msg: 'Exchange config not loaded — try refreshing.' });
      return;
    }
    setStatus({ type: 'saving', msg: 'Switching to Live…' });
    update.mutate({ id: delta.id, is_paper: false }, {
      onSuccess: () => {
        setStatus({ type: 'success', msg: '● Now in Live mode' });
        invalidateAll();
        setTimeout(() => { setModal('none'); setStatus({ type: 'idle', msg: '' }); }, 1200);
      },
      onError: (e) => setStatus({ type: 'error', msg: (e as Error).message }),
    });
  };

  const switchToPaper = () => {
    if (!delta || !isLive) return;
    setStatus({ type: 'saving', msg: '' });
    update.mutate({ id: delta.id, is_paper: true }, {
      onSuccess: () => { invalidateAll(); setStatus({ type: 'idle', msg: '' }); },
      onError: (e) => setStatus({ type: 'error', msg: (e as Error).message }),
    });
  };

  const saveCreds = () => {
    if (!apiKey.trim() || !apiSecret.trim()) {
      setStatus({ type: 'error', msg: 'Both API key and secret are required.' });
      return;
    }
    if (!delta) {
      setStatus({ type: 'error', msg: 'Exchange config not loaded — try refreshing.' });
      return;
    }
    setStatus({ type: 'saving', msg: 'Connecting…' });
    update.mutate({ id: delta.id, api_key: apiKey.trim(), api_secret: apiSecret.trim(), is_paper: false }, {
      onSuccess: () => {
        invalidateAll();
        setStatus({ type: 'success', msg: '● Connected — now in Live mode' });
        setApiKey(''); setApiSecret('');
        setTimeout(() => { setModal('none'); setStatus({ type: 'idle', msg: '' }); }, 1500);
      },
      onError: (e) => setStatus({ type: 'error', msg: (e as Error).message }),
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
      {/* Toggle pill */}
      <div style={{
        display: 'flex', alignItems: 'center',
        background: 'var(--bg)', border: `1px solid ${isLive ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 4, overflow: 'hidden', cursor: saving ? 'wait' : 'pointer',
        opacity: saving ? 0.7 : 1,
      }}>
        <button onClick={isLive ? switchToPaper : undefined} disabled={saving || !isLive}
          style={{ padding: '3px 10px', border: 'none', cursor: isLive ? 'pointer' : 'default',
            background: !isLive ? '#1a1a2a' : 'transparent',
            color: !isLive ? '#88aaff' : 'var(--text-faint)',
            fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: 1 }}>
          PAPER
        </button>
        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />
        <button onClick={isLive ? switchToPaper : handleLiveClick} disabled={saving}
          style={{ padding: '3px 10px', border: 'none', cursor: 'pointer',
            background: isLive ? '#0f2a1a' : 'transparent',
            color: isLive ? 'var(--accent)' : 'var(--text-faint)',
            fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: 1 }}>
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
                    <a href="https://www.delta.exchange/app/settings/api" target="_blank" rel="noopener noreferrer"
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

      {/* ── Add credentials → go live ── */}
      {modal === 'add-keys' && (
        <Backdrop onClose={closeModal}>
          <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--accent)', marginBottom: 4 }}>Connect Delta Exchange India</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 16, lineHeight: 1.6 }}>
            Enter your API credentials from{' '}
            <a href="https://www.delta.exchange/app/settings/api" target="_blank" rel="noopener noreferrer"
              style={{ color: '#88aaff', textDecoration: 'none' }}>
              delta.exchange → Settings → API Keys
            </a>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16, padding: '10px 12px', background: '#0d1a0d', border: '1px solid var(--accent)22', borderRadius: 5 }}>
            {[
              { icon: '🔑', text: 'Read account balance & positions' },
              { icon: '📤', text: 'Place and cancel orders' },
              { icon: '🚫', text: 'Cannot withdraw funds' },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--text-faint)', alignItems: 'center' }}>
                <span>{icon}</span><span>{text}</span>
              </div>
            ))}
          </div>

          {[['API KEY', apiKey, setApiKey], ['API SECRET', apiSecret, setApiSecret]].map(([label, val, set]) => (
            <div key={label as string} style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 4 }}>{label as string}</div>
              <input type="password" value={val as string}
                onChange={e => (set as (v: string) => void)(e.target.value)}
                placeholder="Paste your key here"
                style={{ width: '100%', boxSizing: 'border-box', background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border-light)', borderRadius: 3, padding: '7px 9px', fontFamily: 'monospace', fontSize: 12, outline: 'none' }}
              />
            </div>
          ))}

          <StatusBar status={status} />

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button onClick={closeModal} disabled={saving} style={btnSecondary}>Cancel</button>
            <button onClick={saveCreds} disabled={saving || !apiKey.trim() || !apiSecret.trim() || status.type === 'success'}
              style={{ ...btnPrimary, opacity: saving || !apiKey.trim() || !apiSecret.trim() ? 0.5 : 1 }}>
              {saving ? 'Connecting…' : status.type === 'success' ? '✓ Connected' : '▶ Go Live'}
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
  flex: 2, padding: '9px 0', background: '#0f2a1a',
  color: 'var(--accent)', border: '1px solid var(--accent)',
  borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 800,
};
const btnSecondary: React.CSSProperties = {
  flex: 1, padding: '9px 0', background: 'var(--bg)',
  color: 'var(--text-dim)', border: '1px solid var(--border)',
  borderRadius: 5, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
};

function Backdrop({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-card)', border: '1px solid var(--accent)33',
        borderTop: '3px solid var(--accent)', borderRadius: 8, padding: '22px 24px', width: 360,
        boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
      }}>
        {children}
      </div>
    </div>
  );
}
