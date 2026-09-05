import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { useAlgoMode, useSetAlgoMode, useScalpMode, useSetScalpMode } from '../hooks/useSignalAlerts';
import { useSterlingEngineConfig, useSetSterlingEngineConfig } from '../hooks/useSterlingEngine';
import { api } from '../utils/api';
import { useDailyLossConfig, useUpdateDailyLossConfig } from '../hooks/useRiskConfig';
import { FontPicker } from './FontPicker';
import { useKiteSettings } from '../store/useKiteSettings';
import type { NavItem } from './kite/KiteLayout';

interface TelegramConfig {
  bot_token_set: boolean;
  bot_token_hint: string;
  chat_id: string;
  enabled: boolean;
  reachable: boolean;
}

// ── Status light ──────────────────────────────────────────────────────────────
function StatusLight({ ok, label }: { ok: boolean | null; label: string }) {
  const color = ok === null ? 'var(--t-dim)' : ok ? 'var(--t-blue)' : 'var(--t-red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: color,
        display: 'inline-block', flexShrink: 0,
      }} />
      <span style={{ fontSize: 9, color, fontWeight: 500, letterSpacing: 0.5 }}>{label}</span>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, status, children, defaultOpen = true }: { title: string; status?: React.ReactNode; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 28 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: open ? 14 : 0, cursor: 'pointer', userSelect: 'none' }}
      >
        <span style={{ fontSize: 10, fontWeight: 500, letterSpacing: '0.14em', color: 'var(--t-bright)', textTransform: 'uppercase' }}>{title}</span>
        <div style={{ flex: 1, height: 1, background: 'var(--t-border)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {status}
          <span style={{ fontSize: 10, color: 'var(--t-dim)', transition: 'transform 0.2s', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}>▼</span>
        </div>
      </div>
      {open && children}
    </div>
  );
}

// ── Field ─────────────────────────────────────────────────────────────────────
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, fontWeight: 500, color: 'var(--t-dim)', letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 4, lineHeight: 1.5 }}>{hint}</div>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--t-bg)', color: 'var(--t-bright)',
  border: '1px solid var(--t-border)', borderRadius: 6,
  padding: '7px 10px', fontFamily: 'monospace', fontSize: 12, outline: 'none',
  transition: 'border-color 0.15s, background 0.15s',
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

  const [testResult, setTestResult] = useState<{
    ok: boolean; message?: string; reason?: string; hint?: string; account?: string; balance?: string; server_ip?: string;
  } | null>(null);

  // Auto-test saved credentials on mount so user always sees current status
  useEffect(() => {
    if (hasKeys && connOk === null) {
      testConnection();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasKeys]);

  const testConnection = async () => {
    setTesting(true); setTestResult(null); setMsg('');
    try {
      // Guard against a hung request (no internet / Delta unreachable) so the
      // button never sticks on "Testing…" forever — fail with a clear message.
      const res = await Promise.race([
        api.get<{ ok: boolean; message?: string; reason?: string; hint?: string; account?: string; balance?: string; server_ip?: string }>(
          '/api/v1/trading/test-credentials'
        ),
        new Promise<never>((_, reject) => setTimeout(
          () => reject(new Error('Test timed out — no response from server/exchange. Check connectivity or the API-key IP whitelist.')),
          25_000,
        )),
      ]);
      setConnOk(res.ok);
      setTestResult(res);
    } catch (e: unknown) {
      setConnOk(false);
      setTestResult({ ok: false, reason: (e as Error).message });
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
      status={<StatusLight ok={connOk} label={connOk === null ? 'NOT TESTED' : connOk ? 'CONNECTED' : 'ERROR'} />}
    >
      {/* Test result — rich block */}
      {testResult && (
        <div style={{
          marginBottom: 14, padding: '10px 12px', borderRadius: 4,
          background: 'transparent',
          border: `1px solid ${testResult.ok ? 'var(--t-blue)33' : 'var(--t-red)33'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: testResult.ok ? 2 : 6 }}>
            <span style={{ fontSize: 14 }}>{testResult.ok ? '✅' : '❌'}</span>
            <span style={{ fontSize: 11, fontWeight: 500, color: testResult.ok ? 'var(--t-blue)' : 'var(--t-red)' }}>
              {testResult.ok ? testResult.message : 'Connection failed'}
            </span>
          </div>
          {testResult.ok && testResult.balance && (
            <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 2 }}>
              Margin available: <span style={{ color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums' }}>{testResult.balance}</span>
            </div>
          )}
          {testResult.ok && (
            <a
              href="https://www.delta.exchange/app/account/deposit"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-block', marginTop: 6,
                fontSize: 10, color: 'var(--t-blue)',
                textDecoration: 'none', opacity: 0.8,
              }}
            >
              + Add Funds ↗
            </a>
          )}
          {!testResult.ok && testResult.reason && (
            <div style={{ fontSize: 10, color: 'var(--t-dim)', marginBottom: 6, lineHeight: 1.5 }}>
              {testResult.reason}
            </div>
          )}
          {!testResult.ok && testResult.hint && (
            <div style={{ fontSize: 10, color: 'var(--t-amber)', lineHeight: 1.6, marginBottom: 8 }}>
              {testResult.hint}
            </div>
          )}
          {!testResult.ok && testResult.server_ip && (
            <div style={{
              marginBottom: 8, padding: '6px 10px',
              background: 'var(--t-bg2)', border: '1px solid var(--t-amber)33', borderRadius: 4,
            }}>
              <div style={{ fontSize: 9, color: 'var(--k-ink-6)', marginBottom: 3 }}>WHITELIST THIS SERVER IP IN DELTA EXCHANGE:</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontFamily: 'monospace', fontSize: 13, fontWeight: 500, color: 'var(--t-amber)',
                  letterSpacing: 1,
                }}>
                  {testResult.server_ip}
                </span>
                <button
                  onClick={() => navigator.clipboard.writeText(testResult.server_ip!)}
                  style={{
                    background: 'var(--t-bg2)', color: 'var(--t-amber)', border: '1px solid var(--t-amber)44',
                    padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                    fontFamily: 'inherit', fontSize: 9,
                  }}
                >
                  COPY
                </button>
              </div>
              <div style={{ fontSize: 9, color: 'var(--k-ink-4)', marginTop: 4, lineHeight: 1.5 }}>
                Go to india.delta.exchange → Profile → API Keys → Edit Key → Allowed IPs → Add this IP
              </div>
            </div>
          )}
          {!testResult.ok && (
            <a
              href="https://www.delta.exchange/app/account/manageapikeys"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-block', marginTop: 2,
                fontSize: 10, fontWeight: 500,
                color: 'var(--t-blue)', textDecoration: 'none',
                background: 'var(--t-bg2)', border: '1px solid var(--t-blue)44',
                borderRadius: 4, padding: '5px 12px',
              }}
            >
              Open delta.exchange API Keys ↗
            </a>
          )}
        </div>
      )}

      {hasKeys && !testResult && (
        <div style={{ marginBottom: 12, padding: '6px 10px', background: 'var(--t-bg2)', borderRadius: 4, border: '1px solid var(--t-border)', fontSize: 10, color: 'var(--t-dim)' }}>
          Current key: <span style={{ fontFamily: 'monospace', color: 'var(--t-bright)' }}>••••{hint}</span>
          <span style={{ marginLeft: 8, color: 'var(--t-dim)' }}>— click Test to verify</span>
        </div>
      )}

      <Field label="API KEY" hint="From delta.exchange (global platform) → Settings → API Keys">
        <input
          type="password" placeholder={hasKeys ? '(unchanged — enter new key to update)' : 'Paste API key from delta.exchange'}
          value={apiKey} onChange={e => setApiKey(e.target.value)}
          style={{
            ...inputStyle,
            border: testResult && !testResult.ok ? '1px solid var(--t-red)66' : inputStyle.border,
          }}
        />
      </Field>
      <Field label="API SECRET">
        <input
          type="password" placeholder={hasKeys ? '(unchanged — enter new secret to update)' : 'Paste API secret'}
          value={apiSecret} onChange={e => setApiSecret(e.target.value)}
          style={{
            ...inputStyle,
            border: testResult && !testResult.ok ? '1px solid var(--t-red)66' : inputStyle.border,
          }}
        />
      </Field>

      {msg && (
        <div style={{ fontSize: 10, color: msgOk ? 'var(--t-blue)' : 'var(--t-red)', marginBottom: 8, lineHeight: 1.5 }}>
          {msg}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={save}
          disabled={update.isPending || (!apiKey.trim() && !apiSecret.trim())}
          style={{
            flex: 1, padding: '8px 0', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: update.isPending || (!apiKey.trim() && !apiSecret.trim()) ? 'not-allowed' : 'pointer',
            background: 'var(--t-bg2)',
            color: 'var(--t-bright)',
            border: '1px solid var(--t-border)',
            opacity: update.isPending || (!apiKey.trim() && !apiSecret.trim()) ? 0.4 : 1,
          }}
        >
          {update.isPending ? 'Saving…' : 'Save Credentials'}
        </button>

        {hasKeys && (
          <button
            onClick={testConnection}
            disabled={testing}
            style={{
              padding: '8px 16px', borderRadius: 4,
              fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
              cursor: testing ? 'not-allowed' : 'pointer',
              background: 'transparent',
              color: 'var(--t-dim)',
              border: '1px solid var(--t-border)',
              opacity: testing ? 0.4 : 1,
            }}
          >
            {testing ? 'Testing…' : 'Test'}
          </button>
        )}
      </div>
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
  // Separate in-flight state per button so clicking one doesn't visually
  // activate/disable the other.
  const [sendingTest, setSendingTest]     = useState(false);
  const [sendingSignal, setSendingSignal] = useState(false);

  useEffect(() => { if (data) setChatId(data.chat_id || ''); }, [data]);

  // 3-state light: null=no token, true=connected, false=configured-but-not-verified
  const lightOk: boolean | null = !data?.bot_token_set ? null : data.reachable ? true : false;
  // Base eligibility — both buttons need token+chat set; each button's own
  // in-flight flag handles its loading/disabled state independently.
  const canTest = !!(data?.enabled);

  const save = useMutation<TelegramConfig, Error, void>({
    mutationFn: () => api.put<TelegramConfig>('/api/v1/config/telegram', {
      bot_token: botToken.trim() || undefined,
      chat_id: chatId,
    }),
    onSuccess: (d) => {
      // Update cache directly from the PUT response — avoids a GET refetch
      // that could race and briefly show NOT VERIFIED before completing.
      qc.setQueryData(['telegram-config'], d);
      setBotToken('');
      if (d.reachable) {
        setMsgOk(true);  setMsg('✅ Saved & verified — Telegram is connected');
      } else if (d.enabled) {
        setMsgOk(true);
        setMsg('✅ Saved — click Send Test to verify (make sure you sent /start to your bot)');
      } else {
        setMsgOk(false); setMsg('⚠ Bot token required to enable alerts');
      }
      setTimeout(() => setMsg(''), 8000);
    },
    onError: (e) => { setMsgOk(false); setMsg(`❌ ${e.message}`); },
  });

  // Save disabled when nothing changed
  const telegramChanged = botToken.trim() !== '' || (chatId !== (data?.chat_id ?? '') && chatId !== '');

  const sendTest = async () => {
    setSendingTest(true); setMsg('');
    try {
      const result = await api.post<TelegramConfig>('/api/v1/config/telegram/test', {});
      qc.setQueryData(['telegram-config'], result);
      setMsgOk(true); setMsg('✅ Test message sent — check your Telegram');
    } catch (e: unknown) {
      const err = (e as Error).message ?? 'Unknown error';
      setMsgOk(false);
      setMsg(`❌ ${err}${err.includes('chat') || err.includes('bot') ? '' : ' — send /start to your bot first'}`);
    } finally {
      setSendingTest(false);
      setTimeout(() => setMsg(''), 6000);
    }
  };

  const sendSignalTest = async () => {
    setSendingSignal(true); setMsg('');
    try {
      const result = await api.post<{ sent: boolean; reason: string }>('/api/v1/directional/test-alert', {});
      if (result.sent) {
        setMsgOk(true); setMsg('✅ Signal alert test sent — you should see a formatted signal card in Telegram');
      } else {
        setMsgOk(false); setMsg(`❌ Not sent: ${result.reason}`);
      }
    } catch (e: unknown) {
      setMsgOk(false); setMsg(`❌ ${(e as Error).message}`);
    } finally {
      setSendingSignal(false);
      setTimeout(() => setMsg(''), 8000);
    }
  };

  const needsToken = !data?.bot_token_set && !botToken.trim();

  // Status label
  const statusLabel = !data?.bot_token_set
    ? 'NO TOKEN'
    : !data?.enabled
      ? 'DISABLED'
      : data.reachable
        ? 'CONNECTED'
        : 'NOT VERIFIED';

  return (
    <Section
      title="TELEGRAM ALERTS"
      status={<StatusLight ok={lightOk} label={statusLabel} />}
    >
      {/* Info line */}
      <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.6, marginBottom: 12 }}>
        Receive trade signals, alerts, and order confirmations via Telegram.
        Configure separately for Kite (Indian markets) and Crypto (Delta Exchange).
      </div>

      {/* Kite / Crypto toggle */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
        <span style={{ fontSize: 9, color: 'var(--t-dim)', fontWeight: 500 }}>NOTIFY FOR</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['kite', 'crypto', 'both'] as const).map(mode => {
            const savedMode = localStorage.getItem('tg_notify_mode') || 'crypto';
            return (
              <button key={mode}
                onClick={() => localStorage.setItem('tg_notify_mode', mode)}
                style={{
                  fontSize: 9, fontWeight: 600, padding: '3px 10px', borderRadius: 999,
                  cursor: 'pointer', border: `1px solid ${savedMode === mode ? 'var(--t-blue)44' : 'var(--t-border)'}`,
                  background: savedMode === mode ? 'var(--t-blue)11' : 'var(--t-bg2)',
                  color: savedMode === mode ? 'var(--t-blue)' : 'var(--t-dim)',
                  transition: 'all .14s ease',
                }}
              >{mode === 'kite' ? 'KITE' : mode === 'crypto' ? 'CRYPTO' : 'BOTH'}</button>
            );
          })}
        </div>
      </div>

      {needsToken && (
        <div style={{ marginBottom: 10, padding: '6px 10px', background: 'var(--t-bg2)', border: '1px solid var(--t-amber)33', borderRadius: 4, fontSize: 10, color: 'var(--t-amber)' }}>
          Enter bot token to enable Telegram alerts
        </div>
      )}
      {data?.enabled && !data?.reachable && !needsToken && (
        <div style={{ marginBottom: 10, padding: '6px 10px', background: 'var(--t-bg2)', border: '1px solid var(--t-blue)33', borderRadius: 4, fontSize: 10, color: 'var(--t-blue)', lineHeight: 1.5 }}>
          Token saved. Click <strong>Send Test</strong> to verify.
          If it fails, open Telegram and send <code style={{ background: '#1a2030', padding: '1px 4px', borderRadius: 2 }}>/start</code> to your bot first.
        </div>
      )}
      <Field label="BOT TOKEN" hint={data?.bot_token_set ? `Current: ${data.bot_token_hint} — leave blank to keep` : '@BotFather → /newbot → copy the HTTP API token'}>
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
        <div style={{ fontSize: 10, color: msgOk ? 'var(--t-blue)' : 'var(--t-amber)', marginBottom: 8, lineHeight: 1.5 }}>
          {msg}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={() => save.mutate()} disabled={save.isPending || !telegramChanged}
          style={{
            flex: 1, padding: '8px 0', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: save.isPending || !telegramChanged ? 'not-allowed' : 'pointer',
            background: 'var(--t-bg2)',
            color: 'var(--t-bright)',
            border: '1px solid var(--t-border)',
            opacity: save.isPending || !telegramChanged ? 0.4 : 1,
          }}
        >
          {save.isPending ? 'Saving…' : 'Save Config'}
        </button>

        {canTest && (
          <>
            <button
              onClick={sendTest}
              disabled={sendingTest}
              style={{
                padding: '8px 12px', borderRadius: 4,
                fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
                cursor: sendingTest ? 'not-allowed' : 'pointer',
                background: 'transparent',
                color: 'var(--t-blue)',
                border: '1px solid var(--t-border)',
                opacity: sendingTest ? 0.4 : 1,
              }}
            >
              {sendingTest ? '...' : 'Test'}
            </button>
            <button
              onClick={sendSignalTest}
              disabled={sendingSignal}
              title="Send a sample signal alert"
              style={{
                padding: '8px 12px', borderRadius: 4,
                fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
                cursor: sendingSignal ? 'not-allowed' : 'pointer',
                background: 'transparent',
                color: 'var(--t-purple)',
                border: '1px solid var(--t-border)',
                opacity: sendingSignal ? 0.4 : 1,
              }}
            >
              {sendingSignal ? '...' : 'Signal'}
            </button>
          </>
        )}
      </div>
    </Section>
  );
}

// ── UI Preferences ─────────────────────────────────────────────────────────────

// ── Daily Loss Circuit Breaker ───────────────────────────────────────────────
function DailyLossSection() {
  const { data } = useDailyLossConfig();
  const update = useUpdateDailyLossConfig();
  const [enabled, setEnabled] = React.useState<boolean | null>(null);
  const [soft, setSoft] = React.useState<number | null>(null);
  const [hard, setHard] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (data) {
      if (enabled === null) setEnabled(data.enabled);
      if (soft === null) setSoft(data.soft_warn_usd);
      if (hard === null) setHard(data.hard_halt_usd);
    }
  }, [data]);

  if (!data) return null;

  const handleSave = () => {
    if (enabled !== null && soft !== null && hard !== null) {
      update.mutate({ enabled, soft_warn_usd: soft, hard_halt_usd: hard });
    }
  };

  const isDirty = enabled !== data.enabled || soft !== data.soft_warn_usd || hard !== data.hard_halt_usd;

  const statusLabel = !data.enabled ? 'DISABLED' : (data.level === 'halt' ? 'HALTED' : (data.level === 'warning' ? 'WARNING' : 'CLEAR'));
  const statusColor = !data.enabled ? 'var(--t-dim)' : (data.level === 'halt' ? 'var(--t-red)' : (data.level === 'warning' ? 'var(--t-amber)' : 'var(--t-green)'));

  return (
    <Section title="DAILY LOSS LIMIT" status={<span style={{ fontSize: 9, color: statusColor, fontWeight: 500 }}>{statusLabel}</span>}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)', letterSpacing: '0.06em' }}>CIRCUIT BREAKER</span>
        <button
          onClick={() => setEnabled(!enabled)}
          style={{
            background: enabled ? 'var(--t-green)22' : 'var(--t-bg2)',
            color: enabled ? 'var(--t-green)' : 'var(--t-dim)',
            border: `1px solid ${enabled ? 'var(--t-green)66' : 'var(--t-border)'}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: 10,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          {enabled ? 'ON' : 'OFF'}
        </button>
      </div>

      <Field label="SOFT WARN (USD)" hint="Warning level before hard halt. Expressed as negative USD (e.g. -1000)">
        <input
          type="number"
          step={100}
          value={soft ?? 0}
          onChange={e => setSoft(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      <Field label="HARD HALT (USD)" hint="Blocks new orders if daily realized PnL drops below this">
        <input
          type="number"
          step={100}
          value={hard ?? 0}
          onChange={e => setHard(parseFloat(e.target.value))}
          style={inputStyle}
          disabled={!enabled}
        />
      </Field>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
          Realized Today: <strong style={{ color: data.pnl_usd < 0 ? 'var(--t-red)' : 'var(--t-green)' }}>${data.pnl_usd.toFixed(2)}</strong>
        </span>
        <button
          onClick={handleSave}
          disabled={update.isPending || !isDirty}
          style={{
            padding: '6px 12px', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: update.isPending || !isDirty ? 'not-allowed' : 'pointer',
            background: isDirty ? 'var(--t-bg2)' : 'transparent',
            color: isDirty ? 'var(--t-bright)' : 'var(--t-dim)',
            border: '1px solid var(--t-border)',
            opacity: update.isPending || !isDirty ? 0.4 : 1,
          }}
        >
          {update.isPending ? 'Saving…' : (isDirty ? 'Save Config' : 'Saved')}
        </button>
      </div>
    </Section>
  );
}

function UiSection() {
  return (
    <Section title="DISPLAY">
      <FontPicker />
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
    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
      <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0.5, fontWeight: 500 }} title={hasKeys ? 'Delta Exchange credentials configured' : 'No Delta credentials'}>
        <span style={{ color: hasKeys ? 'var(--t-blue)' : 'var(--t-red)', marginRight: 4 }}>●</span>
        Δ
      </span>
      <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0.5, fontWeight: 500 }} title={tgOk ? 'Telegram connected' : 'Telegram not configured'}>
        <span style={{ color: tgOk ? 'var(--t-blue)' : 'var(--t-dim)', marginRight: 4 }}>●</span>
        TG
      </span>
    </div>
  );
}

// ── Algo mode section (settings drawer) ──────────────────────────────────────
function AlgoSection() {
  const { data: algoData, isLoading } = useAlgoMode();
  const setAlgoMode = useSetAlgoMode();
  const [confirming, setConfirming] = useState(false);
  const enabled = algoData?.enabled ?? false;
  const pending = setAlgoMode.isPending;

  // Preflight credential check — runs when modal opens, gates the Enable button.
  type PreflightState =
    | { state: 'pending' }
    | { state: 'ok'; message: string; account: string }
    | { state: 'fail'; reason: string; hint?: string; serverIp?: string }
    | null;
  const [preflight, setPreflight] = useState<PreflightState>(null);

  const runPreflight = async () => {
    setPreflight({ state: 'pending' });
    try {
      const resp = await api.get<{
        ok: boolean;
        account?: string;
        message?: string;
        balance?: string;
        reason?: string;
        hint?: string;
        server_ip?: string;
      }>('/api/v1/trading/test-credentials');
      if (resp.ok) {
        setPreflight({
          state: 'ok',
          message: resp.message ?? `Connected · ${resp.balance ?? 'OK'}`,
          account: resp.account ?? 'Delta Exchange',
        });
      } else {
        setPreflight({
          state: 'fail',
          reason: resp.reason ?? 'Credential check failed',
          hint: resp.hint,
          serverIp: resp.server_ip,
        });
      }
    } catch (e) {
      setPreflight({
        state: 'fail',
        reason: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const handleToggle = () => {
    if (enabled) {
      setAlgoMode.mutate(false);
    } else {
      setConfirming(true);
      runPreflight();
    }
  };

  const closeModal = () => {
    setConfirming(false);
    setPreflight(null);
  };

  const confirmEnable = () => {
    closeModal();
    setAlgoMode.mutate(true);
  };

  const canEnable = preflight?.state === 'ok' && !pending;

  return (
    <Section
      title="ALGO MODE"
      status={
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%',
            background: enabled ? 'var(--t-green)' : 'var(--t-border)',
            transition: 'background 0.2s',
          }} />
          <span style={{ fontSize: 9, fontWeight: 500, color: enabled ? 'var(--t-green)' : 'var(--t-dim)', letterSpacing: 1 }}>
            {isLoading ? '…' : enabled ? 'ON' : 'OFF'}
          </span>
        </div>
      }
    >
      <div style={{
        padding: '12px 14px', borderRadius: 6, marginBottom: 14,
        background: enabled ? 'transparent' : 'var(--t-bg2)',
        border: `1px solid ${enabled ? 'var(--t-green)44' : 'var(--t-border)'}`,
      }}>
        <div style={{ fontSize: 11, fontWeight: 500, color: enabled ? 'var(--t-blue)' : 'var(--t-dim)', lineHeight: 1.6, marginBottom: 12 }}>
          {enabled
            ? '⚡ Algo is ACTIVE — Sterling automatically places live orders on Delta Exchange when signals reach actionable states.'
            : 'When enabled, Sterling automatically places live market orders on Delta Exchange India for every actionable signal (ARMED / CONFIRMED), with a 2-hour cooldown per instrument.'}
        </div>

        {enabled && (
          <div style={{ fontSize: 10, color: 'var(--k-ink-4)', lineHeight: 1.6, marginBottom: 12 }}>
            Failed orders appear in the Positions tab with a <strong style={{ color: 'var(--t-red)' }}>✕ FAILED</strong> badge and a <strong style={{ color: 'var(--t-blue)' }}>RETRY</strong> button.
          </div>
        )}

        <button
          onClick={handleToggle}
          disabled={pending || isLoading}
          style={{
            width: '100%', padding: '8px 0', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: pending ? 'wait' : 'pointer',
            opacity: pending ? 0.6 : 1,
            background: enabled ? 'var(--t-bg2)' : 'var(--t-green)11',
            color: enabled ? 'var(--t-dim)' : 'var(--t-green)',
            border: `1px solid ${enabled ? 'var(--t-border)' : 'var(--t-green)44'}`,
            transition: 'all 0.15s',
          }}
        >
          {pending ? '…' : enabled ? '■ DISABLE ALGO' : '▶ ENABLE ALGO'}
        </button>

        {setAlgoMode.isError && (
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--t-red)' }}>
            {(setAlgoMode.error as Error).message}
          </div>
        )}
      </div>

      {!enabled && (
        <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.6 }}>
          Requires live Delta Exchange credentials. Failed orders are kept open for retry.
        </div>
      )}

      {/* Confirm enable modal */}
      {confirming && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
          zIndex: 3100, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--t-bg)', border: '1px solid var(--t-border)',
            borderTop: '3px solid var(--t-green)', borderRadius: 6,
            padding: '22px 24px', width: 400,
          }}>
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--t-green)', marginBottom: 6 }}>
              ⚡ Enable Algo Trading?
            </div>
            <div style={{ fontSize: 11, color: 'var(--t-dim)', lineHeight: 1.7, marginBottom: 14 }}>
              Sterling will automatically place <strong style={{ color: 'var(--t-bright)' }}>real live orders</strong> on Delta Exchange India whenever a signal becomes actionable.
            </div>

            {/* Preflight status block */}
            <div style={{
              border: `1px solid ${
                preflight?.state === 'ok' ? 'var(--t-green)66' :
                preflight?.state === 'fail' ? 'var(--t-red)66' :
                'var(--t-border)'
              }`,
              background: preflight?.state === 'ok' ? 'var(--t-bg2)' :
                          preflight?.state === 'fail' ? 'var(--t-bg2)' :
                          'var(--t-bg2)',
              borderRadius: 4, padding: '8px 10px', marginBottom: 14, fontSize: 10,
            }}>
              {preflight === null && (
                <span style={{ color: 'var(--t-dim)' }}>Preflight not run.</span>
              )}
              {preflight?.state === 'pending' && (
                <span style={{ color: 'var(--t-dim)' }}>
                  ⏳ Verifying Delta Exchange credentials…
                </span>
              )}
              {preflight?.state === 'ok' && (
                <div style={{ color: 'var(--t-green)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 500 }}>✓</span>
                  <div>
                    <div style={{ fontWeight: 500 }}>{preflight.account}</div>
                    <div style={{ color: 'var(--t-green)', marginTop: 2 }}>{preflight.message}</div>
                  </div>
                </div>
              )}
              {preflight?.state === 'fail' && (
                <div style={{ color: 'var(--t-red)' }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>✕ {preflight.reason}</div>
                  {preflight.hint && (
                    <div style={{ color: 'var(--t-red)', fontSize: 9, lineHeight: 1.5, marginBottom: 4 }}>
                      {preflight.hint}
                    </div>
                  )}
                  {preflight.serverIp && (
                    <div style={{ color: 'var(--t-red)', fontSize: 9, fontFamily: 'monospace' }}>
                      Server IP: {preflight.serverIp}
                    </div>
                  )}
                  <button
                    onClick={runPreflight}
                    style={{
                      marginTop: 6, background: 'transparent', color: 'var(--t-red)',
                      border: '1px solid var(--t-red)66', borderRadius: 3,
                      padding: '3px 10px', cursor: 'pointer', fontSize: 9,
                      fontFamily: 'inherit', letterSpacing: 1,
                    }}
                  >
                    RETRY
                  </button>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
              {[
                ['💸', 'Real funds will be used — orders go to your Delta Exchange account'],
                ['⏱', '2-hour cooldown per instrument prevents over-trading'],
                ['🔁', 'Failed orders stay open in Positions tab for manual retry'],
                ['🛑', 'Turn off at any time — open positions are not auto-closed'],
              ].map(([icon, text]) => (
                <div key={text as string} style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--t-dim)', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>{icon as string}</span>
                  <span style={{ lineHeight: 1.5 }}>{text as string}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={closeModal}
                style={{ flex: 1, padding: '9px 0', background: 'var(--t-bg2)', color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 }}
              >
                Cancel
              </button>
              <button
                onClick={confirmEnable}
                disabled={!canEnable}
                title={canEnable ? 'Credentials verified — enable algo' : 'Preflight must succeed first'}
                style={{
                  flex: 2, padding: '9px 0',
                  background: canEnable ? 'var(--t-green)20' : 'var(--t-bg2)',
                  color: canEnable ? 'var(--t-green)' : 'var(--t-dim)',
                  border: `1px solid ${canEnable ? 'var(--t-green)66' : 'var(--t-border)'}`,
                  borderRadius: 4, cursor: canEnable ? 'pointer' : 'not-allowed',
                  fontFamily: 'inherit', fontSize: 12, fontWeight: 500,
                  opacity: canEnable ? 1 : 0.6,
                }}
              >
                ▶ Enable Algo
              </button>
            </div>
          </div>
        </div>
      )}
    </Section>
  );
}

// ── Compact algo toggle for header bar ────────────────────────────────────────
export function AlgoToggle({ chipStyle }: { chipStyle?: React.CSSProperties } = {}) {
  const { data: algoData, isLoading } = useAlgoMode();
  const setAlgoMode = useSetAlgoMode();
  const [confirming, setConfirming] = useState(false);
  // Preflight check state — runs when modal opens, gates the Enable button.
  const [preflight, setPreflight] = useState<
    | { state: 'pending' }
    | { state: 'ok'; message: string; account: string }
    | { state: 'fail'; reason: string; hint?: string; serverIp?: string }
    | null
  >(null);
  const enabled = algoData?.enabled ?? false;
  const pending = setAlgoMode.isPending;

  const runPreflight = async () => {
    setPreflight({ state: 'pending' });
    try {
      const resp = await api.get<{
        ok: boolean;
        account?: string;
        message?: string;
        balance?: string;
        reason?: string;
        hint?: string;
        server_ip?: string;
      }>('/api/v1/trading/test-credentials');
      if (resp.ok) {
        setPreflight({
          state: 'ok',
          message: resp.message ?? `Connected · ${resp.balance ?? 'OK'}`,
          account: resp.account ?? 'Delta Exchange',
        });
      } else {
        setPreflight({
          state: 'fail',
          reason: resp.reason ?? 'Credential check failed',
          hint: resp.hint,
          serverIp: resp.server_ip,
        });
      }
    } catch (e) {
      setPreflight({
        state: 'fail',
        reason: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const handleClick = () => {
    if (enabled) {
      setAlgoMode.mutate(false);
    } else {
      setConfirming(true);
      // Fire preflight on open so the button reflects credential state immediately.
      runPreflight();
    }
  };

  const closeModal = () => {
    setConfirming(false);
    setPreflight(null);
  };

  const canEnable = preflight?.state === 'ok' && !pending;

  return (
    <>
      <button
        onClick={handleClick}
        disabled={pending || isLoading}
        title={enabled ? 'Algo ON — click to disable auto-trading' : 'Algo OFF — click to enable auto-trading on Delta Exchange'}
        style={{
          ...chipStyle,
          background: enabled ? 'var(--t-green)11' : (chipStyle?.background ?? 'var(--t-bg2)'),
          color: enabled ? 'var(--t-green)' : (chipStyle?.color ?? 'var(--t-dim)'),
          border: enabled
            ? '1px solid var(--t-green)44'
            : `1px solid ${(chipStyle as any)?.borderColor ?? 'var(--t-border)'}`,
          cursor: pending ? 'wait' : 'pointer',
          opacity: pending ? 0.6 : 1,
          transition: 'all 0.15s',
        }}
      >
        {pending ? '…' : enabled ? '⚡ ALGO ON' : 'ALGO OFF'}
      </button>

      {confirming && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
          zIndex: 3100, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--t-bg)', border: '1px solid var(--t-border)',
            borderTop: '3px solid var(--t-red)', borderRadius: 6,
            padding: '22px 24px', width: 400,
          }}>
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--t-red)', marginBottom: 6 }}>⚡ Enable Algo Trading?</div>
            <div style={{ fontSize: 11, color: 'var(--t-dim)', lineHeight: 1.7, marginBottom: 14 }}>
              Sterling will automatically place <strong style={{ color: 'var(--t-bright)' }}>real live orders</strong> on Delta Exchange India for every actionable signal.
            </div>

            {/* Preflight status block */}
            <div style={{
              border: `1px solid ${
                preflight?.state === 'ok' ? 'var(--t-green)66' :
                preflight?.state === 'fail' ? 'var(--t-red)66' :
                'var(--t-border)'
              }`,
              background: preflight?.state === 'ok' ? 'var(--t-bg2)' :
                          preflight?.state === 'fail' ? 'var(--t-bg2)' :
                          'var(--t-bg2)',
              borderRadius: 4, padding: '8px 10px', marginBottom: 14, fontSize: 10,
            }}>
              {preflight === null && (
                <span style={{ color: 'var(--t-dim)' }}>Preflight not run.</span>
              )}
              {preflight?.state === 'pending' && (
                <span style={{ color: 'var(--t-dim)' }}>
                  ⏳ Verifying Delta Exchange credentials…
                </span>
              )}
              {preflight?.state === 'ok' && (
                <div style={{ color: 'var(--t-green)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 500 }}>✓</span>
                  <div>
                    <div style={{ fontWeight: 500 }}>{preflight.account}</div>
                    <div style={{ color: 'var(--t-green)', marginTop: 2, fontSize: 10 }}>
                      {preflight.message}
                    </div>
                  </div>
                </div>
              )}
              {preflight?.state === 'fail' && (
                <div style={{ color: 'var(--t-red)' }}>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>✕ {preflight.reason}</div>
                  {preflight.hint && (
                    <div style={{ color: 'var(--t-red)', fontSize: 9, lineHeight: 1.5, marginBottom: 4 }}>
                      {preflight.hint}
                    </div>
                  )}
                  {preflight.serverIp && (
                    <div style={{ color: 'var(--t-red)', fontSize: 9, fontFamily: 'monospace' }}>
                      Server IP: {preflight.serverIp}
                    </div>
                  )}
                  <button
                    onClick={runPreflight}
                    style={{
                      marginTop: 6, background: 'transparent', color: 'var(--t-red)',
                      border: '1px solid var(--t-red)66', borderRadius: 3,
                      padding: '3px 10px', cursor: 'pointer', fontSize: 9,
                      fontFamily: 'inherit', letterSpacing: 1,
                    }}
                  >
                    RETRY
                  </button>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
              {[
                ['💸', 'Real funds — orders go to your Delta Exchange account'],
                ['⏱', '2-hour cooldown per instrument'],
                ['🔁', 'Failed orders stay in Positions tab for retry'],
                ['🛑', 'Disable anytime — open positions not auto-closed'],
              ].map(([icon, text]) => (
                <div key={text as string} style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--t-dim)', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>{icon as string}</span>
                  <span style={{ lineHeight: 1.5 }}>{text as string}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={closeModal}
                style={{ flex: 1, padding: '8px 0', background: 'var(--t-bg2)', color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Cancel
              </button>
              <button
                onClick={() => { closeModal(); setAlgoMode.mutate(true); }}
                disabled={!canEnable}
                title={canEnable ? 'Credentials verified — enable algo' : 'Preflight must succeed first'}
                style={{
                  flex: 2, padding: '8px 0',
                  background: canEnable ? 'var(--t-green)11' : 'var(--t-bg2)',
                  color: canEnable ? 'var(--t-green)' : 'var(--t-dim)',
                  border: `1px solid ${canEnable ? 'var(--t-green)44' : 'var(--t-border)'}`,
                  borderRadius: 4, cursor: canEnable ? 'pointer' : 'not-allowed',
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase',
                  opacity: canEnable ? 1 : 0.6,
                }}
              >
                ▶ Enable Algo
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Crypto Engine toggle (global kill switch for all Delta/crypto background tasks) ──
export function ScalpModeToggle({ chipStyle }: { chipStyle?: React.CSSProperties } = {}) {
  const { data: scalpData, isLoading } = useScalpMode();
  const setScalpMode = useSetScalpMode();
  const enabled = scalpData?.enabled ?? false;
  const pending = setScalpMode.isPending;

  return (
    <button
      onClick={() => setScalpMode.mutate(!enabled)}
      disabled={pending || isLoading}
      title={enabled ? 'Stop all crypto engines and sensors' : 'Start crypto engines, sensors, and live data'}
      style={{
        ...chipStyle,
        background: enabled ? 'var(--t-green)11' : 'var(--t-red)11',
        color: enabled ? 'var(--t-green)' : 'var(--t-red)',
        border: enabled ? '1px solid var(--t-green)44' : '1px solid var(--t-red)44',
        cursor: pending ? 'wait' : 'pointer',
        opacity: pending ? 0.6 : 1,
        transition: 'all 0.15s',
      }}
    >
      {pending ? '…' : enabled ? '⚡ ENGINES LIVE' : '⏸ ENGINES PAUSED'}
    </button>
  );
}

// ── AI Gatekeeper Toggle (Header) ─────────────────────────────────────────────
export function AIGatekeeperToggle({ chipStyle }: { chipStyle?: React.CSSProperties } = {}) {
  const { data, isLoading } = useSterlingEngineConfig();
  const setConfig = useSetSterlingEngineConfig();

  const enabled = data?.config.use_optimized ?? false;
  const pending = setConfig.isPending;

  const handleClick = () => {
    if (!data?.config) return;
    setConfig.mutate({
      ...data.config,
      use_optimized: !enabled,
    });
  };

  return (
    <button
      onClick={handleClick}
      disabled={pending || isLoading}
      title={enabled ? 'AI Gatekeeper ON — Institutional WFO Active' : 'AI Gatekeeper OFF — Retail Mode Active'}
      style={{
        ...chipStyle,
        background: enabled ? 'var(--t-blue)11' : (chipStyle?.background ?? 'var(--t-bg2)'),
        color: enabled ? 'var(--t-blue)' : (chipStyle?.color ?? 'var(--t-dim)'),
        border: enabled
          ? '1px solid var(--t-blue)44'
          : `1px solid ${(chipStyle as any)?.borderColor ?? 'var(--t-border)'}`,
        cursor: pending ? 'wait' : 'pointer',
        opacity: pending ? 0.6 : 1,
        transition: 'all 0.15s',
      }}
    >
      {pending ? '…' : enabled ? '● AI Gatekeeper ON' : '○ AI Gatekeeper OFF'}
    </button>
  );
}

// ── Main drawer ───────────────────────────────────────────────────────────────
export function SimpleSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  const { data: scalpData } = useScalpMode();
  const setScalpMode = useSetScalpMode();
  const scalpOn = scalpData?.enabled ?? false;
  const scalpPending = setScalpMode.isPending;

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000 }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 380, zIndex: 2001, background: 'var(--t-bg)', borderLeft: '1px solid var(--t-border)', overflowY: 'auto', scrollbarWidth: 'thin', padding: '20px 22px 48px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, paddingBottom: 16, borderBottom: '1px solid var(--t-border)' }}>
          <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--t-bright)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>SETTINGS</span>
          <button onClick={onClose} style={{ background: 'var(--t-bg2)', border: '1px solid var(--t-border)', borderRadius: 4, color: 'var(--t-dim)', cursor: 'pointer', fontSize: 12, padding: '3px 8px', lineHeight: 1 }}>✕</button>
        </div>

        {/* ── Crypto engine kill switch ── */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--t-bright)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>CRYPTO ENGINES</span>
            <div style={{ width: 9, height: 9, borderRadius: '50%', background: scalpOn ? 'var(--t-green)' : 'var(--t-dim)' }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--t-dim)', lineHeight: 1.6, marginBottom: 14 }}>
            Master kill‑switch for all Delta Exchange crypto engines, sensors, and background scans (Sterling, Grok, V2, derivatives scanner, IV stream, live tickers).
            <br /><br />
            <strong style={{ color: scalpOn ? 'var(--t-green)' : 'var(--t-red)' }}>{scalpOn ? '▶ Running' : '■ Stopped'}</strong> — {scalpOn ? 'all crypto processes are active. Background tasks poll and scan.' : 'no crypto tasks run. Only the Kite engine (Indian markets) remains active.'}
          </div>
          <button
            onClick={() => setScalpMode.mutate(!scalpOn)}
            disabled={scalpPending}
            style={{
              width: '100%', padding: '8px 0', borderRadius: 5, border: `1px solid ${scalpOn ? 'var(--t-red)44' : 'var(--t-green)44'}`,
              background: scalpOn ? 'var(--t-red)11' : 'var(--t-green)11',
              color: scalpOn ? 'var(--t-red)' : 'var(--t-green)',
              cursor: scalpPending ? 'wait' : 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700,
              letterSpacing: '0.08em', textTransform: 'uppercase', opacity: scalpPending ? 0.6 : 1, transition: 'all .15s ease',
            }}>
            {scalpPending ? '…' : scalpOn ? '⏸ STOP ALL CRYPTO ENGINES' : '▶ START CRYPTO ENGINES'}
          </button>
        </div>

        {/* ── UI preferences ── */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--t-bright)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>DISPLAY</span>
          </div>
          <DefaultPageLoadSectionPicker />
          <CryptoTabToggle />
        </div>

        <TelegramSection />
      </div>
    </>
  );
}

function DefaultPageLoadSectionPicker() {
  const defaultSection = useKiteSettings((s) => s.defaultSection || 'dashboard');
  const setDefaultSection = useKiteSettings((s) => s.setDefaultSection);

  const options: Array<{ value: NavItem; label: string }> = [
    { value: 'dashboard', label: 'Dashboard' },
    { value: 'positions', label: 'Positions' },
    { value: 'orders', label: 'Orders' },
    { value: 'holdings', label: 'Holdings' },
    { value: 'astro', label: 'Astrology' },
    { value: 'pcr', label: 'PCR' },
    { value: 'openingLeaders', label: 'Opening Leaders' },
    { value: 'adaptiveEdge', label: 'Adaptive Edge' },
    { value: 'backtest', label: 'Backtest' },
    { value: 'data', label: 'Data' },
    { value: 'connect', label: 'Connect' },
    { value: 'more', label: 'More' },
    { value: 'help', label: 'Help' },
  ];

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, color: 'var(--t-dim)', marginBottom: 6 }}>Default Section on Load:</div>
      <select
        value={defaultSection}
        onChange={(e) => setDefaultSection(e.target.value as NavItem)}
        style={{
          width: '100%',
          padding: '6px 10px',
          background: 'var(--t-bg2)',
          border: '1px solid var(--t-border)',
          borderRadius: 4,
          color: 'var(--t-bright)',
          fontSize: 11,
          fontFamily: 'inherit',
          cursor: 'pointer',
        }}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function CryptoTabToggle() {
  const [showCrypto, setShowCrypto] = useState(() => {
    const stored = localStorage.getItem('sterling_show_crypto_tab');
    return stored === null ? true : stored === 'true';
  });

  const handleToggle = () => {
    const newValue = !showCrypto;
    setShowCrypto(newValue);
    localStorage.setItem('sterling_show_crypto_tab', String(newValue));
  };

  return (
    <div style={{
      padding: '12px 14px', borderRadius: 6,
      background: 'var(--t-bg2)',
      border: '1px solid var(--t-border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--t-bright)' }}>Show Crypto Tab</span>
        <button
          onClick={handleToggle}
          style={{
            background: showCrypto ? 'var(--t-blue)22' : 'var(--t-bg)',
            color: showCrypto ? 'var(--t-blue)' : 'var(--t-dim)',
            border: `1px solid ${showCrypto ? 'var(--t-blue)66' : 'var(--t-border)'}`,
            padding: '4px 10px',
            borderRadius: 4,
            fontSize: 10,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          {showCrypto ? 'ON' : 'OFF'}
        </button>
      </div>
      <div style={{ fontSize: 9, color: 'var(--t-dim)', lineHeight: 1.6 }}>
        {showCrypto
          ? 'Crypto tab is visible in the header. Toggle off to hide Sterling, Grok, V2, and other crypto features.'
          : 'Crypto tab is hidden. Toggle on to access Sterling, Grok, V2, and other crypto features.'}
      </div>
    </div>
  );
}
