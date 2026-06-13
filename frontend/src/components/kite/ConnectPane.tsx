import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useActivateKiteAccount, useAddKiteAccount, useDeleteKiteAccount, useGenerateKiteSession,
  useKiteAccounts, useKiteBasketMargins, useKiteLoginUrl, useKiteLogout, useKiteOrderCharges,
  useKiteOrderMargins, useKiteMargins, useKiteStatus, useKiteTickerStatus,
  useKiteTickerSubscribe, useKiteTickerUnsubscribe, useRefreshKiteSession,
  useTestKiteAccount, useUpdateKiteAccount,
} from '../../hooks/useKite';
import type { KiteAccount } from '../../types/kite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 16, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12, fontWeight: 700 },
  row: { background: t.bg, border: `1px solid ${t.border}`, borderRadius: 8, padding: '10px 14px', marginBottom: 8 },
  name: { fontWeight: 700, color: t.bright, fontSize: 13 },
  actions: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 },
  btn: { background: t.raised, color: t.blue, border: `1px solid ${t.border}`, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnGreen: { background: tint(t.green, 10), color: t.green, border: `1px solid ${t.green}`, padding: '5px 12px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700 },
  btnRed: { background: t.raised, color: t.red, border: `1px solid ${t.red}`, padding: '4px 10px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  input: { background: t.raised, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  hint: { color: t.dim, fontSize: 11 },
  err: { color: t.red, fontSize: 11, marginTop: 6 },
  ok: { color: t.green, fontSize: 11, marginTop: 6 },
};

const badge = (col: string): React.CSSProperties => ({
  background: tint(col, 13), color: col, border: `1px solid ${col}`,
  padding: '2px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700,
});

/** Map a known Kite/login error message to actionable guidance (null = unknown). */
function kiteErrorHelp(msg: string): string | null {
  const m = (msg || '').toLowerCase();
  if (m.includes('not enabled for the app') || m.includes('user is not enabled')) {
    return 'This comes from Zerodha, not Sterling. Sign in with the exact User ID that owns the Kite Connect app (+ TOTP). A subscription activated today can take ~15–30 min to enable login — wait, then retry. If it persists, raise a Kite Connect support ticket.';
  }
  if (m.includes('token') && (m.includes('invalid') || m.includes('expired') || m.includes('used'))) {
    return 'request_tokens are single-use and expire within minutes. Open Kite Login again and paste a fresh token immediately.';
  }
  if (m.includes('checksum')) {
    return 'Checksum mismatch — the API secret on this account does not match the app. Re-enter the secret via EDIT KEYS and retry.';
  }
  if (m.includes('api_key') || (m.includes('invalid') && m.includes('key'))) {
    return 'The API key was rejected. Confirm it matches your active Kite Connect app’s key (EDIT KEYS).';
  }
  return null;
}

function StatusBanner() {
  const { data: s } = useKiteStatus();
  if (!s) return null;
  const col = s.connected ? (s.is_paper ? t.amber : t.green) : t.red;
  return (
    <div style={{ ...S.card, borderColor: col, background: tint(col, 6) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ width: 9, height: 9, borderRadius: 5, background: col, display: 'inline-block' }} />
        <span style={{ fontWeight: 700, color: t.bright, fontSize: 13 }}>
          {s.connected ? (s.is_paper ? 'Paper mode' : `Connected${s.user_name ? ` — ${s.user_name}` : ''}`) : 'Not connected'}
        </span>
        {s.kite_user_id && <span style={S.hint}>· {s.kite_user_id}</span>}
      </div>
      <div style={{ ...S.hint, marginTop: 4 }}>{s.message}</div>
    </div>
  );
}

function Funds() {
  const { data: m } = useKiteMargins(true);
  if (!m || typeof m !== 'object') return null;
  const segs = Object.entries(m).filter(([, v]) => v && typeof v === 'object');
  if (!segs.length) return null;
  return (
    <div style={S.card}>
      <div style={S.title}>FUNDS</div>
      {segs.map(([seg, info]: [string, any]) => (
        <div key={seg} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0' }}>
          <span style={{ color: t.dim }}>{seg}</span>
          <span style={{ color: t.bright, fontWeight: 700 }}>
            ₹{Number(info?.net ?? info?.available?.live_balance ?? 0).toLocaleString('en-IN')}
          </span>
        </div>
      ))}
    </div>
  );
}

function LoginFlow({ account }: { account: KiteAccount }) {
  const { data: lu } = useKiteLoginUrl(account.has_credentials);
  const gen = useGenerateKiteSession();
  const logout = useKiteLogout();
  const refresh = useRefreshKiteSession();
  const [reqToken, setReqToken] = useState('');

  return (
    <div style={S.card}>
      <div style={S.title}>KITE LOGIN — {account.label}</div>
      {!account.has_credentials && <div style={S.hint}>Add API key & secret first (below).</div>}
      {account.has_credentials && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
            <button
              style={S.btnGreen}
              disabled={!lu?.login_url}
              onClick={() => lu?.login_url && window.open(lu.login_url, '_blank', 'noopener')}
            >
              1 · Open Kite Login ↗
            </button>
            <span style={S.hint}>Log in on Kite, then copy the <code>request_token</code> from the redirect URL.</span>
          </div>
          <details style={{ marginBottom: 10 }}>
            <summary style={{ ...S.hint, cursor: 'pointer' }}>Kite says “user is not enabled for the app”?</summary>
            <div style={{ ...S.hint, marginTop: 6, lineHeight: 1.6 }}>
              That error is from Zerodha, not Sterling — the API key is valid, but your login isn’t enabled for the app yet.
              Sign in with the exact <strong>User ID that owns the Kite Connect app</strong> (+ TOTP). A subscription activated
              today can take ~15–30 min to propagate — wait and retry in an incognito window. If it persists, raise a
              Kite Connect support ticket at support.zerodha.com.
            </div>
          </details>
          <div style={{ ...S.hint, marginBottom: 8, lineHeight: 1.6 }}>
            ↪ Auto-connect: set your app’s <strong>Redirect URL</strong> to{' '}
            <code>http://localhost:8000/api/v1/kite/callback</code> and login completes itself (no paste needed).
          </div>
          <label style={S.label}>2 · PASTE request_token (manual)</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input style={S.input} value={reqToken} onChange={(e) => setReqToken(e.target.value)} placeholder="request_token from redirect URL" />
            <button
              style={S.btnGreen}
              disabled={!reqToken.trim() || gen.isPending}
              onClick={() => gen.mutate({ request_token: reqToken.trim(), account_id: account.id }, { onSuccess: () => setReqToken('') })}
            >
              {gen.isPending ? '…' : 'Connect'}
            </button>
          </div>
          {gen.isSuccess && <div style={S.ok}>✓ Session active{gen.data?.user_name ? ` — ${gen.data.user_name}` : ''}</div>}
          {gen.error && (
            <div style={{ marginTop: 6 }}>
              <div style={S.err}>✗ {gen.error.message}</div>
              {kiteErrorHelp(gen.error.message) && (
                <div style={{ ...S.hint, marginTop: 4, lineHeight: 1.6 }}>💡 {kiteErrorHelp(gen.error.message)}</div>
              )}
            </div>
          )}
          {account.connected && (
            <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                style={S.btn}
                onClick={() => refresh.mutate({ account_id: account.id })}
                disabled={refresh.isPending}
                title="Renew the access token from the stored refresh token — no re-login needed"
              >
                {refresh.isPending ? 'Refreshing…' : '↻ Refresh session'}
              </button>
              <button style={S.btnRed} onClick={() => logout.mutate()}>Log out</button>
              {refresh.isSuccess && <span style={S.ok}>✓ Renewed</span>}
              {refresh.error && <span style={S.err}>✗ {refresh.error.message}</span>}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function AccountRow({ acc }: { acc: KiteAccount }) {
  const activate = useActivateKiteAccount();
  const del = useDeleteKiteAccount();
  const test = useTestKiteAccount();
  const update = useUpdateKiteAccount();
  const [edit, setEdit] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [paper, setPaper] = useState(acc.is_paper);

  return (
    <div style={S.row}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={S.name}>{acc.label}</span>
          {acc.is_active && <span style={badge(t.green)}>ACTIVE</span>}
          {acc.is_paper && <span style={badge(t.amber)}>PAPER</span>}
          {acc.connected && <span style={badge(t.blue)}>CONNECTED</span>}
          {acc.has_credentials && <span style={badge(t.purple)}>KEYS SET</span>}
        </div>
        <span style={S.hint}>{acc.api_key_hint}</span>
      </div>
      {test.data && (
        <div style={test.data.connected ? S.ok : S.err}>
          {test.data.connected ? '✓' : '✗'} {test.data.message ?? test.data.error}
        </div>
      )}
      <div style={S.actions}>
        {!acc.is_active && <button style={S.btnGreen} onClick={() => activate.mutate(acc.id)}>SET ACTIVE</button>}
        <button style={S.btn} onClick={() => test.mutate(acc.id)} disabled={test.isPending}>{test.isPending ? '…' : 'TEST'}</button>
        <button style={S.btn} onClick={() => setEdit(!edit)}>{edit ? 'CANCEL' : 'EDIT KEYS'}</button>
        <button style={S.btnRed} onClick={() => del.mutate(acc.id)}>REMOVE</button>
      </div>
      {edit && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input style={S.input} placeholder="New API key (blank = keep)" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
          <input style={S.input} type="password" placeholder="New API secret (blank = keep)" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} autoComplete="new-password" />
          <label style={{ ...S.label, display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={paper} onChange={(e) => setPaper(e.target.checked)} /> Paper mode
          </label>
          <button
            style={S.btnGreen}
            disabled={update.isPending}
            onClick={() => update.mutate({
              id: acc.id, is_paper: paper,
              ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
              ...(apiSecret.trim() ? { api_secret: apiSecret.trim() } : {}),
            }, { onSuccess: () => { setEdit(false); setApiKey(''); setApiSecret(''); } })}
          >
            {update.isPending ? 'SAVING…' : 'SAVE CREDENTIALS'}
          </button>
          {update.error && <div style={S.err}>✗ {update.error.message}</div>}
        </div>
      )}
    </div>
  );
}

function AddAccount() {
  const add = useAddKiteAccount();
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState('My Kite');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [paper, setPaper] = useState(true);

  if (!open) return <button style={S.btnGreen} onClick={() => setOpen(true)}>+ ADD KITE ACCOUNT</button>;
  return (
    <div style={S.card}>
      <div style={S.title}>ADD KITE ACCOUNT</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div><label style={S.label}>LABEL</label><input style={S.input} value={label} onChange={(e) => setLabel(e.target.value)} /></div>
        <div><label style={S.label}>API KEY</label><input style={S.input} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Kite Connect API key" autoComplete="off" /></div>
        <div><label style={S.label}>API SECRET</label><input style={S.input} type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="Kite Connect API secret" autoComplete="new-password" /></div>
        <label style={{ ...S.label, display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
          <input type="checkbox" checked={paper} onChange={(e) => setPaper(e.target.checked)} /> Paper mode (no live trades)
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={S.btnGreen} disabled={add.isPending || !apiKey.trim()} onClick={() => add.mutate({ label, api_key: apiKey.trim(), api_secret: apiSecret.trim(), is_paper: paper }, { onSuccess: () => { setOpen(false); setApiKey(''); setApiSecret(''); } })}>
            {add.isPending ? 'ADDING…' : 'ADD'}
          </button>
          <button style={S.btn} onClick={() => setOpen(false)}>CANCEL</button>
        </div>
        {add.error && <div style={S.err}>✗ {add.error.message}</div>}
      </div>
    </div>
  );
}

function MarginCalc() {
  const orderMargin = useKiteOrderMargins();
  const basketMargin = useKiteBasketMargins();
  const orderCharges = useKiteOrderCharges();
  const [json, setJson] = useState('[{"exchange":"NSE","tradingsymbol":"INFY","transaction_type":"BUY","quantity":1,"order_type":"MARKET","product":"MIS"}]');
  const [method, setMethod] = useState<'order' | 'basket' | 'charges'>('order');
  const [considerPos, setConsiderPos] = useState(false);
  const [latched, setLatched] = useState<any>(null);

  const calc = () => {
    let orders: any[];
    try { orders = JSON.parse(json); } catch { return; }
    if (method === 'order') orderMargin.mutate(orders, { onSuccess: setLatched });
    else if (method === 'basket') basketMargin.mutate({ orders, consider_positions: considerPos }, { onSuccess: setLatched });
    else orderCharges.mutate(orders, { onSuccess: setLatched });
  };

  const result = (method === 'order' ? orderMargin : method === 'basket' ? basketMargin : orderCharges);
  const label = method === 'order' ? 'ORDER MARGIN' : method === 'basket' ? 'BASKET MARGIN' : 'CHARGES';

  return (
    <div style={S.card}>
      <div style={S.title}>MARGIN & CHARGES CALCULATOR</div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        {(['order', 'basket', 'charges'] as const).map((m) => (
          <button key={m} style={{ ...S.btn, background: method === m ? tint(t.blue, 20) : S.btn.background, color: method === m ? t.blue : S.btn.color }} onClick={() => setMethod(m)}>
            {m === 'order' ? 'Order Margin' : m === 'basket' ? 'Basket Margin' : 'Charges'}
          </button>
        ))}
        {method === 'basket' && (
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', fontSize: 11, color: t.dim }}>
            <input type="checkbox" checked={considerPos} onChange={(e) => setConsiderPos(e.target.checked)} /> Consider positions
          </label>
        )}
      </div>
      <textarea
        style={{ background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: 10, fontFamily: 'JetBrains Mono, monospace', fontSize: 11, width: '100%', boxSizing: 'border-box' as const, minHeight: 100, resize: 'vertical' }}
        value={json}
        onChange={(e) => setJson(e.target.value)}
        rows={5}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
        <button style={S.btnGreen} onClick={calc} disabled={result.isPending}>{result.isPending ? '…' : `CALCULATE ${label}`}</button>
        {result.error && <span style={S.err}>✗ {result.error.message}</span>}
      </div>
      {latched && (
        <pre style={{ background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: 10, marginTop: 10, fontSize: 11, fontFamily: 'JetBrains Mono, monospace', overflow: 'auto', maxHeight: 300 }}>
          {JSON.stringify(latched, null, 2)}
        </pre>
      )}
    </div>
  );
}

function TickerControl() {
  const { data: ts } = useKiteTickerStatus(true);
  const sub = useKiteTickerSubscribe();
  const unsub = useKiteTickerUnsubscribe();
  const [tokens, setTokens] = useState('');
  const [mode, setMode] = useState('quote');

  return (
    <div style={S.card}>
      <div style={S.title}>WEBSOCKET TICKER</div>
      {ts && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 10 }}>
          <div><span style={S.label}>State</span><span style={{ color: ts.connected ? t.green : ts.active ? t.amber : t.red, fontWeight: 700 }}>{ts.active ? (ts.connected ? 'Connected' : 'Connecting…') : 'Off'}</span></div>
          <div><span style={S.label}>Subscribed</span><span style={{ color: t.bright }}>{ts.subscribed?.length ?? 0} tokens</span></div>
          <div><span style={S.label}>Ticks</span><span style={{ color: t.bright }}>{ts.tick_count?.toLocaleString('en-IN') ?? 0}</span></div>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <label style={S.label}>Tokens (comma-separated)</label>
          <input style={{ ...S.input, width: 260 }} value={tokens} onChange={(e) => setTokens(e.target.value)} placeholder="408065, 356865, 1270529" />
        </div>
        <div>
          <label style={S.label}>Mode</label>
          <select style={S.input} value={mode} onChange={(e) => setMode(e.target.value)}>
            {['ltp', 'quote', 'full'].map((m) => <option key={m}>{m}</option>)}
          </select>
        </div>
        <button
          style={S.btnGreen}
          onClick={() => sub.mutate({
            instrument_tokens: tokens.split(',').map(Number).filter((n) => !isNaN(n)),
            mode,
          })}
          disabled={sub.isPending}
        >SUBSCRIBE</button>
        <button
          style={S.btnRed}
          onClick={() => unsub.mutate({
            instrument_tokens: tokens.split(',').map(Number).filter((n) => !isNaN(n)),
          })}
          disabled={unsub.isPending}
        >UNSUBSCRIBE</button>
      </div>
      {sub.isSuccess && <div style={S.ok}>✓ Subscribed {sub.data?.count ?? sub.data?.subscribed?.length ?? '—'} tokens</div>}
      {sub.error && <div style={S.err}>✗ {sub.error.message}</div>}
      {unsub.isSuccess && <div style={S.ok}>✓ Unsubscribed</div>}
      {unsub.error && <div style={S.err}>✗ {unsub.error.message}</div>}
    </div>
  );
}

export function ConnectPane() {
  const { data, isLoading } = useKiteAccounts();
  const active = data?.accounts.find((a) => a.is_active);
  return (
    <div>
      <StatusBanner />
      {active && <LoginFlow account={active} />}
      {active?.connected && !active.is_paper && <Funds />}
      {active?.connected && !active.is_paper && <MarginCalc />}
      {active?.connected && !active.is_paper && <TickerControl />}
      <div style={S.card}>
        <div style={S.title}>KITE ACCOUNTS</div>
        {isLoading && <div style={S.hint}>Loading…</div>}
        {data?.accounts.map((a) => <AccountRow key={a.id} acc={a} />)}
        {data && data.count === 0 && <div style={{ ...S.hint, marginBottom: 10 }}>No Kite accounts yet — add your API key & secret to begin.</div>}
        <AddAccount />
      </div>
      <div style={{ ...S.hint, lineHeight: 1.7 }}>
        A Kite Connect app (kite.trade) gives you an <strong>API key + secret</strong>. Each session needs a daily login
        (token expires ~6 AM IST). Historical data is a paid Kite add-on. Credentials are encrypted at rest and scoped to your user.
      </div>
    </div>
  );
}
