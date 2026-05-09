import React, { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange, useTestConnection } from '../hooks/useExchanges';

/**
 * Prominent "Go Live" panel for Simple mode.
 * Shows credential entry + paper/live toggle for the active Delta Exchange India config.
 * Hidden when live credentials are already set.
 */
export function GoLivePanel() {
  const qc = useQueryClient();
  const { data: exData } = useExchanges();
  const update = useUpdateExchange();
  const test = useTestConnection();

  const [apiKey, setApiKey]       = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [saving, setSaving]       = useState(false);
  const [msg, setMsg]             = useState<{ ok: boolean; text: string } | null>(null);
  const [expanded, setExpanded]   = useState(false);

  // Find the active Delta Exchange India config
  const deltaEx = exData?.exchanges.find(e =>
    e.name === 'delta_india' && e.is_active
  );

  // Already live — don't show this panel
  if (deltaEx?.has_credentials && !deltaEx.is_paper) return null;

  const handleSave = async () => {
    if (!deltaEx) return;
    if (!apiKey.trim() || !apiSecret.trim()) {
      setMsg({ ok: false, text: 'API key and secret are required' });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      await new Promise<void>((resolve, reject) =>
        update.mutate(
          { id: deltaEx.id, api_key: apiKey.trim(), api_secret: apiSecret.trim(), is_paper: false },
          { onSuccess: () => resolve(), onError: (e) => reject(e) }
        )
      );
      qc.invalidateQueries({ queryKey: ['exchanges'] });
      setMsg({ ok: true, text: '✅ Credentials saved — Live trading enabled!' });
      setApiKey('');
      setApiSecret('');
      setExpanded(false);
    } catch (e: unknown) {
      setMsg({ ok: false, text: `Error: ${(e as Error).message}` });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = () => {
    if (!deltaEx) return;
    test.mutate(deltaEx.id, {
      onSuccess: (r: unknown) => {
        const result = r as { connected: boolean; error?: string };
        setMsg({ ok: !!result.connected, text: result.connected ? '✅ Connection successful' : `❌ ${result.error || 'Failed'}` });
      },
      onError: (e) => setMsg({ ok: false, text: `❌ ${(e as Error).message}` }),
    });
  };

  const isPaper = !deltaEx || deltaEx.is_paper;

  return (
    <div style={{
      marginBottom: 12, border: `1px solid ${isPaper ? '#f0c04055' : '#44cc8855'}`,
      borderRadius: 6, overflow: 'hidden',
    }}>
      {/* header */}
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '10px 14px', background: isPaper ? '#1a1400' : '#0f1a0f',
          border: 'none', cursor: 'pointer', fontFamily: 'inherit',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontSize: 10, fontWeight: 800, letterSpacing: 1,
            padding: '2px 8px', borderRadius: 3,
            background: isPaper ? '#f0c04022' : '#44cc8822',
            color: isPaper ? '#f0c040' : '#44cc88',
            border: `1px solid ${isPaper ? '#f0c04055' : '#44cc8855'}`,
          }}>
            {isPaper ? '📋 PAPER' : '🟢 LIVE'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: 0.5 }}>
            {isPaper
              ? 'Delta Exchange India — Paper mode · Click to go LIVE'
              : 'Delta Exchange India — Live trading active'}
          </span>
        </div>
        <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
      </button>

      {/* credential form */}
      {expanded && (
        <div style={{ padding: '14px 14px 12px', background: 'var(--bg-card)', borderTop: '1px solid var(--border)' }}>
          {isPaper ? (
            <>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.6 }}>
                Enter your <b style={{ color: 'var(--text-primary)' }}>Delta Exchange India</b> API credentials.
                Get them from: <span style={{ color: '#88aaff' }}>delta.exchange → API Keys</span>.
                Orders will be placed as <b>market orders with bracket SL/TP</b>.
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 4 }}>API KEY</div>
                  <input
                    type="password"
                    placeholder="your_api_key"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    style={{
                      width: '100%', background: 'var(--bg)', color: 'var(--text-primary)',
                      border: '1px solid var(--border-light)', borderRadius: 3,
                      padding: '7px 9px', fontFamily: 'monospace', fontSize: 12,
                    }}
                  />
                </div>
                <div>
                  <div style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 4 }}>API SECRET</div>
                  <input
                    type="password"
                    placeholder="your_api_secret"
                    value={apiSecret}
                    onChange={e => setApiSecret(e.target.value)}
                    style={{
                      width: '100%', background: 'var(--bg)', color: 'var(--text-primary)',
                      border: '1px solid var(--border-light)', borderRadius: 3,
                      padding: '7px 9px', fontFamily: 'monospace', fontSize: 12,
                    }}
                  />
                </div>
              </div>

              {msg && (
                <div style={{
                  marginBottom: 10, padding: '7px 10px', borderRadius: 4, fontSize: 11,
                  background: msg.ok ? '#0f2a0f' : '#2a0f0f',
                  color: msg.ok ? '#44cc88' : '#cc4444',
                  border: `1px solid ${msg.ok ? '#44cc8833' : '#cc444433'}`,
                }}>
                  {msg.text}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={handleSave}
                  disabled={saving || !apiKey.trim() || !apiSecret.trim()}
                  style={{
                    flex: 1, padding: '9px 0', borderRadius: 4, cursor: 'pointer',
                    background: '#0f2a0f', color: '#44cc88', border: '1px solid #44cc88',
                    fontFamily: 'inherit', fontSize: 12, fontWeight: 800, letterSpacing: 1,
                    opacity: saving || !apiKey.trim() ? 0.6 : 1,
                  }}
                >
                  {saving ? 'Saving…' : '🔴 ENABLE LIVE TRADING'}
                </button>
                {deltaEx?.has_credentials && (
                  <button
                    onClick={handleTest}
                    disabled={test.isPending}
                    style={{
                      padding: '9px 14px', borderRadius: 4, cursor: 'pointer',
                      background: 'var(--bg)', color: 'var(--text-dim)', border: '1px solid var(--border)',
                      fontFamily: 'inherit', fontSize: 11,
                    }}
                  >
                    Test
                  </button>
                )}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ color: '#44cc88', fontWeight: 700, fontSize: 13, marginBottom: 4 }}>✅ Live trading active</div>
                <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
                  API key: {deltaEx.api_key_hint} · Orders go to Delta Exchange India
                </div>
              </div>
              <button
                onClick={() => update.mutate({ id: deltaEx.id, is_paper: true }, {
                  onSuccess: () => {
                    qc.invalidateQueries({ queryKey: ['exchanges'] });
                    setMsg({ ok: true, text: 'Switched to paper mode' });
                  }
                })}
                style={{
                  padding: '6px 14px', borderRadius: 4, cursor: 'pointer',
                  background: '#2a1a1a', color: '#cc4444', border: '1px solid #cc444455',
                  fontFamily: 'inherit', fontSize: 11,
                }}
              >
                Switch to Paper
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
