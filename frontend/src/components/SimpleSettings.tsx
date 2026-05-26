import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useExchanges, useUpdateExchange } from '../hooks/useExchanges';
import { useAlgoMode, useSetAlgoMode } from '../hooks/useSignalAlerts';
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
  const color = ok === null ? 'var(--t-dim)' : ok ? 'var(--t-blue)' : 'var(--t-red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%', background: color,
        display: 'inline-block', flexShrink: 0,
      }} />
      <span style={{ fontSize: 9, color, fontWeight: 700, letterSpacing: 0.5 }}>{label}</span>
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
        <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.14em', color: 'var(--t-bright)', textTransform: 'uppercase' }}>{title}</span>
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
      <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
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
      status={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusLight ok={connOk} label={connOk === null ? 'NOT TESTED' : connOk ? 'CONNECTED' : 'ERROR'} />
          <button
            onClick={testConnection} disabled={testing || !hasKeys}
            style={{ fontSize: 9, padding: '2px 8px', background: 'var(--t-bg2)', color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 3, cursor: testing || !hasKeys ? 'default' : 'pointer', fontFamily: 'inherit', opacity: !hasKeys ? 0.4 : 1 }}
          >
            {testing ? 'Testing…' : 'Test'}
          </button>
        </div>
      }
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
            <span style={{ fontSize: 11, fontWeight: 700, color: testResult.ok ? 'var(--t-blue)' : 'var(--t-red)' }}>
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
              <div style={{ fontSize: 9, color: '#888', marginBottom: 3 }}>WHITELIST THIS SERVER IP IN DELTA EXCHANGE:</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontFamily: 'monospace', fontSize: 13, fontWeight: 700, color: 'var(--t-amber)',
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
              <div style={{ fontSize: 9, color: '#666', marginTop: 4, lineHeight: 1.5 }}>
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
                fontSize: 10, fontWeight: 700,
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

      <button
        onClick={save}
        disabled={update.isPending || (!apiKey.trim() && !apiSecret.trim())}
        style={{
          width: '100%', padding: '8px 0', borderRadius: 4,
          fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
          cursor: update.isPending || (!apiKey.trim() && !apiSecret.trim()) ? 'not-allowed' : 'pointer',
          background: 'var(--t-bg2)',
          color: 'var(--t-bright)',
          border: '1px solid var(--t-border)',
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
      status={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusLight ok={lightOk} label={statusLabel} />
          <button
            onClick={sendTest}
            disabled={!canTest || sendingTest}
            style={{
              fontSize: 9, padding: '2px 8px', background: 'var(--t-bg2)',
              color: canTest ? 'var(--t-bright)' : 'var(--t-dim)',
              border: `1px solid ${canTest ? 'var(--t-blue)44' : 'var(--t-border)'}`,
              borderRadius: 3, cursor: canTest && !sendingTest ? 'pointer' : 'default',
              fontFamily: 'inherit', opacity: !canTest || sendingTest ? 0.5 : 1,
              fontWeight: canTest ? 700 : 400,
            }}
          >
            {sendingTest ? 'Sending…' : 'Send Test'}
          </button>
          <button
            onClick={sendSignalTest}
            disabled={!canTest || sendingSignal}
            title="Send a sample signal alert in the exact format you'll receive for real signals"
            style={{
              fontSize: 9, padding: '2px 8px', background: 'var(--t-bg2)',
              color: canTest ? 'var(--t-purple)' : 'var(--t-dim)',
              border: `1px solid ${canTest ? 'var(--t-purple)44' : 'var(--t-border)'}`,
              borderRadius: 3, cursor: canTest && !sendingSignal ? 'pointer' : 'default',
              fontFamily: 'inherit', opacity: !canTest || sendingSignal ? 0.5 : 1,
              fontWeight: canTest ? 700 : 400,
            }}
          >
            {sendingSignal ? 'Sending…' : 'Test Signal'}
          </button>
        </div>
      }
    >
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

      <button
        onClick={() => save.mutate()} disabled={save.isPending || !telegramChanged}
        style={{
          width: '100%', padding: '8px 0', borderRadius: 4,
          fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
          cursor: save.isPending || !telegramChanged ? 'not-allowed' : 'pointer',
          background: 'var(--t-bg2)',
          color: 'var(--t-bright)',
          border: '1px solid var(--t-border)',
          opacity: save.isPending || !telegramChanged ? 0.4 : 1,
        }}
      >
        {save.isPending ? 'Saving…' : 'Save Telegram Config'}
      </button>
    </Section>
  );
}

// ── UI Preferences ─────────────────────────────────────────────────────────────
function UiSection() {
  const [zoom, setZoom] = useState(() => {
    const root = document.querySelector('.term-root') as HTMLElement;
    return parseFloat(root?.style.getPropertyValue('--app-zoom') || '1');
  });

  const updateZoom = (val: number) => {
    const root = document.querySelector('.term-root') as HTMLElement;
    if (root) {
      root.style.setProperty('--app-zoom', val.toString());
      setZoom(val);
      localStorage.setItem('sterling-zoom', val.toString());
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem('sterling-zoom');
    if (saved) {
      const v = parseFloat(saved);
      if (!isNaN(v)) updateZoom(v);
    }
  }, []);

  return (
    <Section title="DISPLAY" status={<span style={{ fontSize: 9, color: 'var(--t-dim)' }}>{(zoom * 100).toFixed(0)}%</span>}>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => updateZoom(Math.max(0.6, zoom - 0.1))}
          style={{ flex: 1, padding: '6px 0', background: 'var(--t-bg)', color: 'var(--t-bright)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'monospace', fontSize: 14 }}>
          -
        </button>
        <button onClick={() => updateZoom(1)}
          style={{ flex: 2, padding: '6px 0', background: 'var(--t-bg)', color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em' }}>
          RESET
        </button>
        <button onClick={() => updateZoom(Math.min(1.5, zoom + 0.1))}
          style={{ flex: 1, padding: '6px 0', background: 'var(--t-bg)', color: 'var(--t-bright)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'monospace', fontSize: 14 }}>
          +
        </button>
      </div>
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
      <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0.5, fontWeight: 700 }} title={hasKeys ? 'Delta Exchange credentials configured' : 'No Delta credentials'}>
        <span style={{ color: hasKeys ? 'var(--t-blue)' : 'var(--t-red)', marginRight: 4 }}>●</span>
        Δ
      </span>
      <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: 0.5, fontWeight: 700 }} title={tgOk ? 'Telegram connected' : 'Telegram not configured'}>
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
          <span style={{ fontSize: 9, fontWeight: 700, color: enabled ? 'var(--t-green)' : 'var(--t-dim)', letterSpacing: 1 }}>
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
        <div style={{ fontSize: 11, fontWeight: 700, color: enabled ? 'var(--t-blue)' : 'var(--t-dim)', lineHeight: 1.6, marginBottom: 12 }}>
          {enabled
            ? '⚡ Algo is ACTIVE — Sterling automatically places live orders on Delta Exchange when signals reach actionable states.'
            : 'When enabled, Sterling automatically places live market orders on Delta Exchange India for every actionable signal (ARMED / CONFIRMED), with a 2-hour cooldown per instrument.'}
        </div>

        {enabled && (
          <div style={{ fontSize: 10, color: '#666', lineHeight: 1.6, marginBottom: 12 }}>
            Failed orders appear in the Positions tab with a <strong style={{ color: 'var(--t-red)' }}>✕ FAILED</strong> badge and a <strong style={{ color: 'var(--t-blue)' }}>RETRY</strong> button.
          </div>
        )}

        <button
          onClick={handleToggle}
          disabled={pending || isLoading}
          style={{
            width: '100%', padding: '8px 0', borderRadius: 4,
            fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
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
            <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--t-green)', marginBottom: 6 }}>
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
                  <span style={{ fontSize: 12, fontWeight: 700 }}>✓</span>
                  <div>
                    <div style={{ fontWeight: 700 }}>{preflight.account}</div>
                    <div style={{ color: 'var(--t-green)', marginTop: 2 }}>{preflight.message}</div>
                  </div>
                </div>
              )}
              {preflight?.state === 'fail' && (
                <div style={{ color: 'var(--t-red)' }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>✕ {preflight.reason}</div>
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
                  fontFamily: 'inherit', fontSize: 12, fontWeight: 800,
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
            <div style={{ fontSize: 15, fontWeight: 900, color: 'var(--t-red)', marginBottom: 6 }}>⚡ Enable Algo Trading?</div>
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
                  <span style={{ fontSize: 12, fontWeight: 700 }}>✓</span>
                  <div>
                    <div style={{ fontWeight: 700 }}>{preflight.account}</div>
                    <div style={{ color: 'var(--t-green)', marginTop: 2, fontSize: 10 }}>
                      {preflight.message}
                    </div>
                  </div>
                </div>
              )}
              {preflight?.state === 'fail' && (
                <div style={{ color: 'var(--t-red)' }}>
                  <div style={{ fontWeight: 700, marginBottom: 4 }}>✕ {preflight.reason}</div>
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
                style={{ flex: 1, padding: '8px 0', background: 'var(--t-bg2)', color: 'var(--t-dim)', border: '1px solid var(--t-border)', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
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
                  fontFamily: 'inherit', fontSize: 10, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
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

// ── Main drawer ───────────────────────────────────────────────────────────────
export function SimpleSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;

  return (
    <>
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000 }}
      />
      <div style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 380,
        zIndex: 2001,
        background: 'var(--t-bg)',
        borderLeft: '1px solid var(--t-border)',
        overflowY: 'auto',
        scrollbarWidth: 'thin',
        padding: '20px 22px 48px',
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
          paddingBottom: 16,
          borderBottom: '1px solid var(--t-border)',
        }}>
          <span style={{
            fontSize: 10,
            fontWeight: 800,
            color: 'var(--t-bright)',
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}>
            SETTINGS
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'var(--t-bg2)',
              border: '1px solid var(--t-border)',
              borderRadius: 4,
              color: 'var(--t-dim)',
              cursor: 'pointer',
              fontSize: 12,
              padding: '3px 8px',
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>
        <AlgoSection />
        <ExchangeSection />
        <TelegramSection />
        <UiSection />
      </div>
    </>
  );
}
