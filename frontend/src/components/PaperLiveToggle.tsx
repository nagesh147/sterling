import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { api } from '../utils/api';

type ModalView = 'none' | 'go-live-confirm' | 'add-keys';

export function PaperLiveToggle() {
  const qc = useQueryClient();
  const { data: exData } = useExchanges();
  const update = useUpdateExchange();

  const [modal, setModal]       = useState<ModalView>('none');
  const [apiKey, setApiKey]     = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState('');
  const [testStatus, setTestStatus] = useState<{ ok: boolean; msg: string; hint?: string } | null>(null);
  const [testing, setTesting]   = useState(false);

  const testConnection = async () => {
    setTesting(true); setTestStatus(null);
    try {
      const res = await api.get<{ ok: boolean; message?: string; reason?: string; hint?: string; account?: string }>(
        '/api/v1/trading/test-credentials'
      );
      setTestStatus({
        ok: res.ok,
        msg: res.ok ? (res.message ?? 'Connected') + (res.account ? ` · ${res.account}` : '') : (res.reason ?? 'Unknown error'),
        hint: res.hint,
      });
    } catch (e: unknown) {
      setTestStatus({ ok: false, msg: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive  = !!(delta?.has_credentials && !delta.is_paper);
  const hasKeys = !!delta?.has_credentials;
  const keyHint = delta?.api_key_hint ?? '';

  const handleLiveClick = () => {
    if (isLive) return;
    if (!hasKeys) { setErr(''); setModal('add-keys'); return; }
    setModal('go-live-confirm');
  };

  const confirmGoLive = () => {
    if (!delta) return;
    setSaving(true);
    update.mutate({ id: delta.id, is_paper: false }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['config-info'] });
        qc.invalidateQueries({ queryKey: ['exchanges'] });
        qc.invalidateQueries({ queryKey: ['positions'] });
        qc.invalidateQueries({ queryKey: ['positions', 'live'] });
        setSaving(false); setModal('none');
      },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
  };

  const switchToPaper = () => {
    if (!delta || !isLive) return;
    setSaving(true);
    update.mutate({ id: delta.id, is_paper: true }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['config-info'] });
        qc.invalidateQueries({ queryKey: ['exchanges'] });
        qc.invalidateQueries({ queryKey: ['positions'] });
        setSaving(false);
      },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
  };

  const saveCreds = () => {
    if (!delta || !apiKey.trim() || !apiSecret.trim()) return;
    setSaving(true); setErr('');
    update.mutate({ id: delta.id, api_key: apiKey.trim(), api_secret: apiSecret.trim(), is_paper: false }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['exchanges'] });
        qc.invalidateQueries({ queryKey: ['config-info'] });
        qc.invalidateQueries({ queryKey: ['positions'] });
        setSaving(false); setModal('none'); setApiKey(''); setApiSecret('');
      },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
  };

  const closeModal = () => { if (!saving) { setModal('none'); setErr(''); } };

  return (
    <>
      {/* Toggle pill */}
      <div style={{
        display: 'flex', alignItems: 'center',
        background: 'var(--bg)', border: `1px solid ${isLive ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 4, overflow: 'hidden', cursor: saving ? 'wait' : 'pointer',
        opacity: saving ? 0.7 : 1,
      }}>
        <button
          onClick={isLive ? switchToPaper : undefined}
          disabled={saving || !isLive}
          style={{
            padding: '3px 10px', border: 'none', cursor: isLive ? 'pointer' : 'default',
            background: !isLive ? '#1a1a2a' : 'transparent',
            color: !isLive ? '#88aaff' : 'var(--text-faint)',
            fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: 1,
          }}
        >
          PAPER
        </button>
        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />
        <button
          onClick={isLive ? switchToPaper : handleLiveClick}
          disabled={saving}
          style={{
            padding: '3px 10px', border: 'none', cursor: 'pointer',
            background: isLive ? '#0f2a1a' : 'transparent',
            color: isLive ? 'var(--accent)' : 'var(--text-faint)',
            fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: 1,
          }}
        >
          {isLive ? '● LIVE' : 'LIVE'}
        </button>
      </div>

      {/* ── Go-Live confirmation (keys already set) ── */}
      {modal === 'go-live-confirm' && (
        <Backdrop onClose={closeModal}>
          <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--accent)', marginBottom: 4 }}>
            ⚡ Switch to Live Trading
          </div>
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

          {/* account + test connection */}
          <div style={{ marginBottom: 16, padding: '10px 12px', background: 'var(--bg)', borderRadius: 5, border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: testStatus ? 8 : 0 }}>
              <div>
                <div style={{ fontSize: 8, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 2 }}>CONNECTED ACCOUNT</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  Delta Exchange India{keyHint ? ` · ••••${keyHint}` : ''}
                </div>
              </div>
              <button
                onClick={testConnection}
                disabled={testing}
                style={{
                  padding: '4px 10px', background: 'var(--bg-input)',
                  color: 'var(--text-dim)', border: '1px solid var(--border)',
                  borderRadius: 4, cursor: testing ? 'wait' : 'pointer',
                  fontFamily: 'inherit', fontSize: 10, flexShrink: 0,
                }}
              >
                {testing ? 'Testing…' : 'Test Connection'}
              </button>
            </div>
            {testStatus && (
              <div style={{
                padding: '7px 10px', borderRadius: 4, marginTop: 6,
                background: testStatus.ok ? '#071a14' : '#1a0707',
                border: `1px solid ${testStatus.ok ? 'var(--accent)33' : 'var(--danger)33'}`,
                fontSize: 10,
                color: testStatus.ok ? 'var(--accent)' : 'var(--danger)',
              }}>
                {testStatus.ok ? '✅ ' : '❌ '}{testStatus.msg}
                {testStatus.hint && <div style={{ marginTop: 4, color: 'var(--text-faint)', fontSize: 9 }}>{testStatus.hint}</div>}
              </div>
            )}
          </div>

          {err && <div style={{ color: 'var(--danger)', fontSize: 11, marginBottom: 12 }}>❌ {err}</div>}

          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={closeModal} disabled={saving} style={btnSecondary}>Stay Paper</button>
            <button onClick={confirmGoLive} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.7 : 1 }}>
              {saving ? 'Switching…' : '▶ Go Live'}
            </button>
          </div>
        </Backdrop>
      )}

      {/* ── Add credentials → go live ── */}
      {modal === 'add-keys' && (
        <Backdrop onClose={closeModal}>
          <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--accent)', marginBottom: 4 }}>
            Connect Delta Exchange India
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 16, lineHeight: 1.6 }}>
            Enter your API key and secret from{' '}
            <span style={{ color: '#88aaff' }}>delta.exchange → Settings → API Keys</span>
            {' '}to enable live order placement.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16, padding: '10px 12px', background: '#0d1a0d', border: '1px solid var(--accent)22', borderRadius: 5 }}>
            {[
              { icon: '🔑', text: 'Read your account balance & positions' },
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
              <input
                type="password"
                value={val as string}
                onChange={e => (set as (v: string) => void)(e.target.value)}
                placeholder="Paste your key here"
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'var(--bg)', color: 'var(--text-primary)',
                  border: '1px solid var(--border-light)', borderRadius: 3,
                  padding: '7px 9px', fontFamily: 'monospace', fontSize: 12, outline: 'none',
                }}
              />
            </div>
          ))}

          {err && <div style={{ color: 'var(--danger)', fontSize: 11, marginBottom: 10 }}>❌ {err}</div>}

          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button onClick={closeModal} disabled={saving} style={btnSecondary}>Cancel</button>
            <button
              onClick={saveCreds}
              disabled={saving || !apiKey.trim() || !apiSecret.trim()}
              style={{ ...btnPrimary, opacity: saving || !apiKey.trim() || !apiSecret.trim() ? 0.5 : 1 }}
            >
              {saving ? 'Connecting…' : '▶ Go Live'}
            </button>
          </div>
        </Backdrop>
      )}
    </>
  );
}

// ── shared styles ─────────────────────────────────────────────────────────────

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
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-card)', border: '1px solid var(--accent)33',
          borderTop: '3px solid var(--accent)',
          borderRadius: 8, padding: '22px 24px', width: 360,
          boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
        }}
      >
        {children}
      </div>
    </div>
  );
}
