import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { api } from '../utils/api';

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_hint: string;
  chat_id: string;
  enabled: boolean;
  reachable: boolean;
}

// ── Status light ──────────────────────────────────────────────────────────────
function StatusLight({ ok, label }: { ok: boolean | null; label: string }) {
  const color = ok === null ? '#555' : ok ? 'var(--accent)' : 'var(--danger)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: color,
        boxShadow: ok === null ? 'none' : `0 0 5px ${color}`,
        display: 'inline-block', flexShrink: 0,
      }} />
      <span style={{ fontSize: 9, color, fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, status, children }: { title: string; status?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, borderBottom: '1px solid var(--border)', paddingBottom: 6 }}>
        <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 2, color: 'var(--text-faint)' }}>{title}</div>
        {status}
      </div>
      {children}
    </div>
  );
}

// ── Field ─────────────────────────────────────────────────────────────────────
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 9, color: 'var(--text-faint)', marginTop: 3, lineHeight: 1.5 }}>{hint}</div>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--bg)', color: 'var(--text-primary)',
  border: '1px solid var(--border-light)', borderRadius: 4,
  padding: '7px 10px', fontFamily: 'monospace', fontSize: 12, outline: 'none',
};

// ── Exchange credentials ──────────────────────────────────────────────────────
function ExchangeSection() {
  const qc = useQueryClient();
  const { data: exData }        = useExchanges();
  const update                  = useUpdateExchange();
  const delta                   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);

  const [apiKey, setApiKey]     = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [msg, setMsg]           = useState('');
  const [msgOk, setMsgOk]       = useState(true);
  const [testing, setTesting]   = useState(false);
  const [connOk, setConnOk]     = useState<boolean | null>(null);

  const hint    = delta?.api_key_hint ?? '';
  const hasKeys = !!delta?.has_credentials;

  const testConnection = async () => {
    setTesting(true); setMsg('');
    try {
      const res = await api.get<{ ok: boolean; message?: string; reason?: string; hint?: string; account?: string }>(
        '/api/v1/trading/test-credentials'
      );
      setConnOk(res.ok); setMsgOk(res.ok);
      setMsg(res.ok
        ? `Connected${res.account ? ' · ' + res.account : ''}`
        : `${res.reason ?? 'Failed'}${res.hint ? '\n' + res.hint : ''}`
      );
    } catch (e: unknown) {
      setConnOk(false); setMsgOk(false);
      setMsg((e as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const save = () => {
    if (!delta || (!apiKey.trim() && !apiSecret.trim())) return;
    update.mutate({ id: delta.id, api_key: apiKey.trim() || undefined, api_secret: apiSecret.trim() || undefined }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ['exchanges'] });
        setApiKey(''); setApiSecret('');
        setConnOk(null); // reset light — user should test again
        setMsgOk(true); setMsg('Credentials saved — click Test to verify');
        setTimeout(() => setMsg(''), 5000);
      },
      onError: (e) => { setMsgOk(false); setMsg(e.message); },
    });
  };

  return (
    <Section
      title="DELTA EXCHANGE INDIA"
      status={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusLight ok={connOk} label={connOk === null ? 'NOT TESTED' : connOk ? 'CONNECTED' : 'ERROR'} />
          <button
            onClick={testConnection} disabled={testing || !hasKeys}
            style={{ fontSize: 9, padding: '2px 8px', background: 'var(--bg-input)', color: 'var(--text-dim)', border: '1px solid var(--border)', borderRadius: 3, cursor: testing || !hasKeys ? 'default' : 'pointer', fontFamily: 'inherit', opacity: !hasKeys ? 0.4 : 1 }}
          >
            {testing ? 'Testing…' : 'Test'}
          </button>
        </div>
      }
    >
      {hasKeys && (
        <div style={{ marginBottom: 12, padding: '6px 10px', background: 'var(--bg)', borderRadius: 4, border: '1px solid var(--border)', fontSize: 10, color: 'var(--text-faint)' }}>
          Current key: <span style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>••••{hint}</span>
        </div>
      )}

      <Field label="API KEY" hint={hasKeys ? 'Leave blank to keep current key' : 'Get from delta.exchange → Settings → API Keys'}>
        <input
          type="password" placeholder={hasKeys ? '(unchanged)' : 'Paste API key'}
          value={apiKey} onChange={e => setApiKey(e.target.value)}
          style={inputStyle}
        />
      </Field>
      <Field label="API SECRET">
        <input
          type="password" placeholder={hasKeys ? '(unchanged)' : 'Paste API secret'}
          value={apiSecret} onChange={e => setApiSecret(e.target.value)}
          style={inputStyle}
        />
      </Field>

      {msg && (
        <div style={{ fontSize: 10, color: msgOk ? 'var(--accent)' : 'var(--danger)', marginBottom: 8, lineHeight: 1.5, whiteSpace: 'pre-line' }}>
          {msg}
        </div>
      )}

      <button
        onClick={save}
        disabled={update.isPending || (!apiKey.trim() && !apiSecret.trim())}
        style={{
          width: '100%', padding: '9px 0',
          background: '#0f2a1a', color: 'var(--accent)',
          border: '1px solid var(--accent)66', borderRadius: 4,
          cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700,
          opacity: update.isPending || (!apiKey.trim() && !apiSecret.trim()) ? 0.4 : 1,
        }}
      >
        {update.isPending ? 'Saving…' : 'Save Credentials'}
      </button>
    </Section>
  );
}

// ── Telegram config ───────────────────────────────────────────────────────────
function TelegramSection() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TelegramConfig>({
    queryKey: ['telegram-config'],
    queryFn: () => api.get<TelegramConfig>('/api/v1/config/telegram'),
    staleTime: 30_000,
  });

  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId]     = useState('');
  const [msg, setMsg]           = useState('');
  const [msgOk, setMsgOk]       = useState(true);
  const [sending, setSending]   = useState(false);

  useEffect(() => { if (data) setChatId(data.chat_id || ''); }, [data]);

  const connOk: boolean | null = isLoading ? null : (data?.reachable ?? false);

  const save = useMutation<TelegramConfig, Error, void>({
    mutationFn: () => api.put<TelegramConfig>('/api/v1/config/telegram', {
      bot_token: botToken || undefined,
      chat_id: chatId,
    }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['telegram-config'] });
      setBotToken('');
      setMsgOk(d.reachable);
      setMsg(d.reachable ? '✅ Saved — test message sent' : d.enabled ? '⚠ Saved but unreachable — check token/chat ID' : '✅ Saved (notifications disabled)');
      setTimeout(() => setMsg(''), 6000);
    },
    onError: (e) => { setMsgOk(false); setMsg(`❌ ${e.message}`); },
  });

  const sendTest = async () => {
    setSending(true); setMsg('');
    try {
      await api.post('/api/v1/config/telegram/test', {});
      setMsgOk(true); setMsg('✅ Test message sent to Telegram');
    } catch (e: unknown) {
      setMsgOk(false); setMsg(`❌ ${(e as Error).message}`);
    } finally {
      setSending(false);
      setTimeout(() => setMsg(''), 5000);
    }
  };

  return (
    <Section
      title="TELEGRAM ALERTS"
      status={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusLight
            ok={data?.enabled ? connOk : null}
            label={!data?.enabled ? 'DISABLED' : connOk ? 'CONNECTED' : 'NOT REACHABLE'}
          />
          <button
            onClick={sendTest} disabled={sending || !data?.enabled || !data?.reachable}
            style={{ fontSize: 9, padding: '2px 8px', background: 'var(--bg-input)', color: 'var(--text-dim)', border: '1px solid var(--border)', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', opacity: !data?.enabled || !data?.reachable ? 0.4 : 1 }}
          >
            {sending ? 'Sending…' : 'Send Test'}
          </button>
        </div>
      }
    >
      <Field label="BOT TOKEN" hint={data?.bot_token_set ? `Current: ••••${data.bot_token_hint} — leave blank to keep` : '@BotFather → /newbot → copy HTTP API token'}>
        <input
          type="password"
          placeholder={data?.bot_token_set ? '(unchanged)' : 'Paste bot token'}
          value={botToken} onChange={e => setBotToken(e.target.value)}
          style={inputStyle}
        />
      </Field>
      <Field label="CHAT ID" hint="Your Telegram user ID — send /start to your bot, then check getUpdates">
        <input
          type="text" placeholder="e.g. 123456789"
          value={chatId} onChange={e => setChatId(e.target.value)}
          style={inputStyle}
        />
      </Field>

      {msg && (
        <div style={{ fontSize: 10, color: msgOk ? 'var(--accent)' : '#f0c040', marginBottom: 8, lineHeight: 1.5 }}>
          {msg}
        </div>
      )}

      <button
        onClick={() => save.mutate()} disabled={save.isPending}
        style={{
          width: '100%', padding: '9px 0',
          background: '#1a1a2a', color: '#88aaff',
          border: '1px solid #88aaff66', borderRadius: 4,
          cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700,
          opacity: save.isPending ? 0.4 : 1,
        }}
      >
        {save.isPending ? 'Saving…' : 'Save Telegram Config'}
      </button>
    </Section>
  );
}

// ── Status dots shown in header (always visible in simple mode) ───────────────
export function SimpleStatusDots() {
  const { data: exData }  = useExchanges();
  const { data: tgData }  = useQuery<TelegramConfig>({
    queryKey: ['telegram-config'],
    queryFn: () => api.get<TelegramConfig>('/api/v1/config/telegram'),
    staleTime: 60_000,
  });

  const delta   = exData?.exchanges.find(e => e.name === 'delta_india' && e.is_active);
  const hasKeys = !!delta?.has_credentials;
  const tgOk    = !!(tgData?.enabled && tgData?.reachable);

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <span style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 0.5 }} title={hasKeys ? 'Delta Exchange credentials configured' : 'No Delta credentials'}>
        <span style={{ color: hasKeys ? 'var(--accent)' : 'var(--danger)', marginRight: 3 }}>●</span>
        Δ
      </span>
      <span style={{ fontSize: 9, color: 'var(--text-faint)', letterSpacing: 0.5 }} title={tgOk ? 'Telegram connected' : 'Telegram not configured'}>
        <span style={{ color: tgOk ? 'var(--accent)' : '#555', marginRight: 3 }}>●</span>
        TG
      </span>
    </div>
  );
}

// ── Main drawer ───────────────────────────────────────────────────────────────
export function SimpleSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 2000 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 360,
        zIndex: 2001, background: 'var(--bg-card)',
        borderLeft: '1px solid var(--border)',
        overflowY: 'auto', scrollbarWidth: 'thin',
        padding: '20px 20px 40px',
        boxShadow: '-4px 0 32px rgba(0,0,0,0.5)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
          <span style={{ fontSize: 13, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: 1 }}>SETTINGS</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-faint)', cursor: 'pointer', fontSize: 18, padding: 0, lineHeight: 1 }}>✕</button>
        </div>
        <ExchangeSection />
        <TelegramSection />
      </div>
    </>
  );
}
