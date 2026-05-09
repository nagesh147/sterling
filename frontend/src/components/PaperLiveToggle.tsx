/**
 * PaperLiveToggle — single-click toggle between Paper and Live trading.
 * Live mode connects to the active Delta Exchange India account.
 * Shows a credential prompt if API keys are not yet configured.
 */
import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';

export function PaperLiveToggle() {
  const qc = useQueryClient();
  const { data: exData } = useExchanges();
  const update = useUpdateExchange();

  const [showCreds, setShowCreds] = useState(false);
  const [apiKey, setApiKey]       = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [saving, setSaving]       = useState(false);
  const [err, setErr]             = useState('');

  // Active Delta India exchange config
  const delta = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const isLive = !!(delta?.has_credentials && !delta.is_paper);
  const hasKeys = !!delta?.has_credentials;

  const switchToLive = async () => {
    if (!delta) return;
    if (!hasKeys) { setShowCreds(true); return; }
    setSaving(true);
    update.mutate({ id: delta.id, is_paper: false }, {
      onSuccess: () => { qc.invalidateQueries({ queryKey: ['config-info'] }); setSaving(false); },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
  };

  const switchToPaper = () => {
    if (!delta) return;
    setSaving(true);
    update.mutate({ id: delta.id, is_paper: true }, {
      onSuccess: () => { qc.invalidateQueries({ queryKey: ['config-info'] }); setSaving(false); },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
  };

  const saveCreds = async () => {
    if (!delta || !apiKey.trim() || !apiSecret.trim()) return;
    setSaving(true); setErr('');
    update.mutate({ id: delta.id, api_key: apiKey.trim(), api_secret: apiSecret.trim(), is_paper: false }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['exchanges'] });
        qc.invalidateQueries({ queryKey: ['config-info'] });
        setSaving(false); setShowCreds(false); setApiKey(''); setApiSecret('');
      },
      onError: (e) => { setErr((e as Error).message); setSaving(false); },
    });
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
        <button
          onClick={switchToPaper}
          disabled={saving}
          style={{
            padding: '3px 10px', border: 'none', cursor: 'pointer',
            background: !isLive ? '#1a1a2a' : 'transparent',
            color: !isLive ? '#88aaff' : 'var(--text-faint)',
            fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: 1,
          }}
        >
          PAPER
        </button>
        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />
        <button
          onClick={isLive ? switchToPaper : switchToLive}
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

      {/* Credential modal */}
      {showCreds && (
        <div
          style={{ position: 'fixed', inset: 0, background: '#000000cc', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={() => setShowCreds(false)}
        >
          <div
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', borderRadius: 8, padding: 24, width: 340 }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
              Connect Delta Exchange India
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 16, lineHeight: 1.6 }}>
              Enter your API credentials from{' '}
              <span style={{ color: 'var(--blue)' }}>delta.exchange → Settings → API Keys</span>
            </div>

            {[['API KEY', apiKey, setApiKey], ['API SECRET', apiSecret, setApiSecret]].map(([label, val, set]) => (
              <div key={label as string} style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 4 }}>{label as string}</div>
                <input
                  type="password"
                  value={val as string}
                  onChange={e => (set as (v: string) => void)(e.target.value)}
                  style={{ width: '100%', background: 'var(--bg)', color: 'var(--text-primary)', border: '1px solid var(--border-light)', borderRadius: 3, padding: '7px 9px', fontFamily: 'monospace', fontSize: 12 }}
                />
              </div>
            ))}

            {err && <div style={{ color: 'var(--danger)', fontSize: 11, marginBottom: 10 }}>❌ {err}</div>}

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button
                onClick={() => setShowCreds(false)}
                style={{ flex: 1, padding: '8px 0', background: 'var(--bg)', color: 'var(--text-dim)', border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
              >
                Cancel
              </button>
              <button
                onClick={saveCreds}
                disabled={saving || !apiKey.trim() || !apiSecret.trim()}
                style={{ flex: 2, padding: '8px 0', background: '#0f2a1a', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 800, opacity: saving || !apiKey.trim() ? 0.5 : 1 }}
              >
                {saving ? 'Connecting…' : '▶ GO LIVE'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
