import React, { useState } from 'react';
import {
  useActivateKiteAccount, useAddKiteAccount, useDeleteKiteAccount, useGenerateKiteSession,
  useKiteAccounts, useKiteBasketMargins, useKiteLoginUrl, useKiteLogout, useKiteOrderCharges,
  useKiteOrderMargins, useKiteMargins, useKiteStatus, useKiteTickerStatus,
  useKiteTickerSubscribe, useKiteTickerUnsubscribe, useRefreshKiteSession,
  useTestKiteAccount, useUpdateKiteAccount,
} from '../../hooks/useKite';
import { useEngineConfig, useSetEngineConfig, useEngineSignals } from '../../hooks/useTripleSupertrend';
import type { KiteAccount } from '../../types/kite';
import { ModeToggle } from './ModeToggle';
import { TradingModeControls } from './TradingModeControls';
import { DirectionalModePanel } from './DirectionalModePanel';
import { KiteTelegramPanel } from './KiteTelegramPanel';
import { useKiteSettings } from '../../store/useKiteSettings';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: `1px solid #e0e0e0`, borderRadius: 4, padding: 16, marginBottom: 14 },
  title: { color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 12, fontWeight: 700 },
  row: { background: '#f9f9f9', border: `1px solid #e0e0e0`, borderRadius: 4, padding: '10px 14px', marginBottom: 8 },
  name: { fontWeight: 700, color: '#444', fontSize: 13 },
  actions: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 },
  btn: { background: '#fff', color: '#387ed1', border: `1px solid #e0e0e0`, padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnGreen: { background: '#4caf50', color: '#fff', border: `1px solid #4caf50`, padding: '5px 12px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700 },
  btnRed: { background: '#fff', color: '#e53935', border: `1px solid #e53935`, padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  input: { background: '#fff', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 4, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  label: { color: '#9b9b9b', fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  hint: { color: '#9b9b9b', fontSize: 11 },
  err: { color: '#e53935', fontSize: 11, marginTop: 6 },
  ok: { color: '#4caf50', fontSize: 11, marginTop: 6 },
};

const badge = (col: string): React.CSSProperties => ({
  background: '#f9f9f9', color: col, border: `1px solid ${col}`,
  padding: '2px 8px', borderRadius: 2, fontSize: 9, fontWeight: 700,
});

/** Map a known Kite/login error message to actionable guidance (null = unknown). */
function kiteErrorHelp(msg: string): string | null {
  const m = (msg || '').toLowerCase();
  if (m.includes('not enabled for the app') || m.includes('user is not enabled')) {
    return 'This comes from Zerodha, not Kite Engine. Sign in with the exact User ID that owns the Kite Connect app (+ TOTP). A subscription activated today can take ~15–30 min to enable login — wait, then retry. If it persists, raise a Kite Connect support ticket.';
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

// Legacy LoginFlow removed — merged into AccountCard below.

function StatusBanner() {
  const { data: s } = useKiteStatus();
  if (!s) return null;
  const col = s.connected ? (s.is_paper ? '#ff9800' : '#4caf50') : '#e53935';
  return (
    <div style={{ ...S.card, borderColor: col, background: '#f9f9f9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ width: 9, height: 9, borderRadius: 5, background: col, display: 'inline-block' }} />
        <span style={{ fontWeight: 700, color: '#444', fontSize: 13 }}>
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
          <span style={{ color: '#9b9b9b' }}>{seg}</span>
          <span style={{ color: '#444', fontWeight: 700 }}>
            ₹{Number(info?.net ?? info?.available?.live_balance ?? 0).toLocaleString('en-IN')}
          </span>
        </div>
      ))}
    </div>
  );
}

function LoginFlow({ account }: { account: KiteAccount }) {
  // Fetch the login URL whenever credentials exist — NOT only when disconnected.
  // `account.connected` just means a token is *stored*, not that it's *valid*: after
  // Kite's daily ~6 AM expiry the token is stale-but-saved (connected=true), which
  // would otherwise leave the "Open Kite Login" button permanently disabled during
  // re-login. The /login-url endpoint only needs the api_key, so this is safe.
  const { data: lu } = useKiteLoginUrl(account.has_credentials);
  const gen = useGenerateKiteSession();
  const logout = useKiteLogout();
  const refresh = useRefreshKiteSession();
  const [reqToken, setReqToken] = useState('');
  const [showRelogin, setShowRelogin] = useState(false);
  const { data: status } = useKiteStatus();
  // `account.connected` only means a token is STORED, not that it's valid. The live
  // /status validates it (and auto-clears it on expiry). Treat a stale token (status
  // says disconnected for this account) as NOT connected, so we show the login flow
  // instead of "Log out / Re-login" before a real session exists.
  const connected = account.connected
    && !(status?.account_id === account.id && status?.connected === false);

  // The manual login steps (Open Kite Login + paste request_token). Shown when
  // NOT connected, or behind the "Re-login manually" toggle when a live session
  // has lapsed and the user wants to re-authenticate without logging out.
  const loginSteps = (
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
          That error is from Zerodha, not Kite Engine — the API key is valid, but your login isn’t enabled for the app yet.
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
          onClick={() => gen.mutate({ request_token: reqToken.trim(), account_id: account.id }, { onSuccess: () => { setReqToken(''); setShowRelogin(false); } })}
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
    </>
  );

  return (
    <div style={S.card}>
      <div style={S.title}>KITE LOGIN — {account.label}</div>
      {!account.has_credentials && <div style={S.hint}>Add API key & secret first (below).</div>}

      {/* Connected → compact session controls; the paste-token flow is hidden
          behind "Re-login manually" so it doesn't clutter an active session. */}
      {account.has_credentials && connected && (
        <>
          <div style={{ ...S.hint, marginBottom: 10, lineHeight: 1.6 }}>
            Session active{account.kite_user_id ? ` · ${account.kite_user_id}` : ''}.{' '}
            {account.has_refresh_token
              ? <>Kite Engine <strong>auto-recovers</strong> this session from the stored refresh token whenever it lapses — no
                clicking needed. A fresh 2FA login may still be required at Zerodha’s daily ~6 AM IST reset.</>
              : <>Kite didn’t issue a refresh token for this app, so the session can’t be auto-renewed — Zerodha requires a
                fresh 2FA login each day (~6 AM IST). Re-login below when it lapses.</>}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {account.has_refresh_token && (
              <button
                style={S.btn}
                onClick={() => refresh.mutate({ account_id: account.id })}
                disabled={refresh.isPending}
                title="Renew the access token from the stored refresh token — no re-login needed"
              >
                {refresh.isPending ? 'Refreshing…' : '↻ Refresh session'}
              </button>
            )}
            <button style={account.has_refresh_token ? S.btn : S.btnGreen} onClick={() => setShowRelogin((v) => !v)}>
              {showRelogin ? 'Cancel re-login' : 'Re-login'}
            </button>
            <button style={S.btnRed} onClick={() => logout.mutate()}>Log out</button>
            {refresh.isSuccess && <span style={S.ok}>✓ Renewed</span>}
            {refresh.error && <span style={S.err}>✗ {refresh.error.message}</span>}
          </div>
          {showRelogin && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid #e0e0e0` }}>
              {loginSteps}
            </div>
          )}
        </>
      )}

      {/* Not connected (or stored token expired) → the full login flow. */}
      {account.has_credentials && !connected && loginSteps}
    </div>
  );
}

/** Returns two initials from a label/name string. */
function initials(s: string): string {
  const parts = s.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
}

/** Unified account card — compact row by default, full controls on expand. */
function AccountCard({ acc }: { acc: KiteAccount }) {
  const { data: status } = useKiteStatus();
  const { data: lu } = useKiteLoginUrl(acc.has_credentials);
  const activate = useActivateKiteAccount();
  const del = useDeleteKiteAccount();
  const test = useTestKiteAccount();
  const update = useUpdateKiteAccount();
  const gen = useGenerateKiteSession();
  const logout = useKiteLogout();
  const refresh = useRefreshKiteSession();

  const [expanded, setExpanded] = useState(false);
  const [showRelogin, setShowRelogin] = useState(false);
  const [editKeys, setEditKeys] = useState(false);
  const [reqToken, setReqToken] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');

  const connected = acc.connected
    && !(status?.account_id === acc.id && status?.connected === false);
  const isLive = !acc.is_paper;

  // Dot colour: green = live+connected, amber = paper+connected, grey = disconnected
  const dotColor = connected ? (isLive ? '#4caf50' : '#ff9800') : '#bbb';
  const modeLabel = connected ? (isLive ? 'LIVE' : 'PAPER') : 'offline';

  // Display name: prefer kite_user_id, fall back to label
  const displayName = acc.label;
  const subText = acc.kite_user_id ? `ID ${acc.kite_user_id}` : acc.api_key_hint ?? '';

  const avatarColor = isLive && connected ? '#2e7d32' : connected ? '#1565c0' : '#9e9e9e';

  const flipPaperLive = () => {
    if (isLive) { update.mutate({ id: acc.id, is_paper: true }); return; }
    if (!acc.has_credentials) return;
    if (window.confirm(`Switch "${acc.label}" to LIVE? Orders will execute on your real Zerodha account.`)) {
      update.mutate({ id: acc.id, is_paper: false });
    }
  };

  return (
    <div style={{ border: `1px solid ${expanded ? '#d0d0d0' : '#e8e8e8'}`, borderRadius: 8, marginBottom: 10, overflow: 'hidden', background: '#fff', transition: 'box-shadow .15s', boxShadow: expanded ? '0 2px 8px rgba(0,0,0,.06)' : 'none' }}>
      {/* ── Collapsed row ── */}
      <div
        onClick={() => setExpanded((v) => !v)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', cursor: 'pointer', userSelect: 'none' }}
      >
        {/* Avatar */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <div style={{
            width: 38, height: 38, borderRadius: '50%', background: avatarColor,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 14, letterSpacing: 0.5,
          }}>
            {initials(displayName)}
          </div>
          {/* Status LED */}
          <span style={{
            position: 'absolute', bottom: 0, right: 0, width: 10, height: 10,
            borderRadius: '50%', background: dotColor, border: '2px solid #fff',
            boxShadow: connected ? `0 0 4px ${dotColor}` : undefined,
          }} />
        </div>

        {/* Name + sub-info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: '#333', fontSize: 14 }}>{displayName}</span>
            {acc.is_active && <span style={badge('#f06428')}>ACTIVE</span>}
          </div>
          {subText && <div style={{ color: '#999', fontSize: 11, marginTop: 1 }}>{subText}</div>}
        </div>

        {/* Mode badge + chevron */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ ...badge(dotColor), fontSize: 9 }}>{modeLabel.toUpperCase()}</span>
          <span style={{ color: '#ccc', fontSize: 12, transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform .15s', display: 'inline-block' }}>▼</span>
        </div>
      </div>

      {/* ── Expanded body ── */}
      {expanded && (
        <div style={{ borderTop: '1px solid #f0f0f0', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Session info */}
          {connected ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 12, color: '#444' }}>
                Session active{acc.has_refresh_token ? ' · auto-renews' : ' · manual re-login required after 6 AM IST'}
              </span>
              {acc.has_refresh_token && (
                <button style={S.btn} onClick={() => refresh.mutate({ account_id: acc.id })} disabled={refresh.isPending}>
                  {refresh.isPending ? '…' : '↻ Refresh'}
                </button>
              )}
              <button style={S.btn} onClick={() => setShowRelogin((v) => !v)}>
                {showRelogin ? 'Cancel' : 'Re-login'}
              </button>
              <button style={S.btnRed} onClick={() => logout.mutate()}>Log out</button>
              {refresh.isSuccess && <span style={S.ok}>✓ Renewed</span>}
              {refresh.error && <span style={S.err}>✗ {refresh.error.message}</span>}
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#999' }}>
              {acc.has_credentials ? 'Not connected — use Kite Login below to get a session.' : 'Add API keys to enable login.'}
            </div>
          )}

          {/* Login flow */}
          {acc.has_credentials && (!connected || showRelogin) && (
            <div style={{ background: '#fafafa', border: '1px solid #e8e8e8', borderRadius: 6, padding: 12 }}>
              <div style={{ ...S.label, marginBottom: 8 }}>KITE LOGIN</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
                <button style={S.btnGreen} disabled={!lu?.login_url} onClick={() => lu?.login_url && window.open(lu.login_url, '_blank', 'noopener')}>
                  1 · Open Kite Login ↗
                </button>
                <span style={S.hint}>Log in, then copy the <code>request_token</code> from the redirect URL.</span>
              </div>
              <div style={{ ...S.hint, marginBottom: 8 }}>
                Or set Redirect URL to <code>http://localhost:8000/api/v1/kite/callback</code> for auto-connect.
              </div>
              <label style={S.label}>2 · Paste request_token (manual)</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input style={S.input} value={reqToken} onChange={(e) => setReqToken(e.target.value)} placeholder="request_token from redirect URL" />
                <button
                  style={S.btnGreen}
                  disabled={!reqToken.trim() || gen.isPending}
                  onClick={() => gen.mutate({ request_token: reqToken.trim(), account_id: acc.id }, { onSuccess: () => { setReqToken(''); setShowRelogin(false); } })}
                >
                  {gen.isPending ? '…' : 'Connect'}
                </button>
              </div>
              {gen.isSuccess && <div style={S.ok}>✓ Connected{gen.data?.user_name ? ` — ${gen.data.user_name}` : ''}</div>}
              {gen.error && (
                <div style={{ marginTop: 6 }}>
                  <div style={S.err}>✗ {gen.error.message}</div>
                  {kiteErrorHelp(gen.error.message) && <div style={{ ...S.hint, marginTop: 4, lineHeight: 1.6 }}>💡 {kiteErrorHelp(gen.error.message)}</div>}
                </div>
              )}
            </div>
          )}

          {/* PAPER / LIVE toggle + key management */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <ModeToggle
              size="sm" left="PAPER" right="LIVE"
              value={acc.is_paper ? 'left' : 'right'}
              onSelect={(side) => { if (side === 'left') update.mutate({ id: acc.id, is_paper: true }); else flipPaperLive(); }}
              leftColor="#387ed1" rightColor="#4caf50"
              rightDotWhenActive busy={update.isPending}
              rightDisabled={!acc.has_credentials}
              rightTitle={acc.has_credentials ? undefined : 'Add API keys first to trade live.'}
            />
            {!acc.is_active && <button style={S.btn} onClick={() => activate.mutate(acc.id)}>Set active</button>}
            <button style={S.btn} onClick={() => test.mutate(acc.id)} disabled={test.isPending}>{test.isPending ? '…' : 'Test connection'}</button>
            <button style={S.btn} onClick={() => setEditKeys((v) => !v)}>{editKeys ? 'Cancel' : 'Edit keys'}</button>
            <button style={{ ...S.btnRed, marginLeft: 'auto' }} onClick={() => { if (window.confirm(`Remove "${acc.label}"?`)) del.mutate(acc.id); }}>Remove</button>
          </div>

          {test.data && (
            <div style={test.data.connected ? S.ok : S.err}>
              {test.data.connected ? '✓' : '✗'} {test.data.message ?? test.data.error}
            </div>
          )}

          {editKeys && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <input style={S.input} placeholder="New API key (blank = keep)" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
              <input style={S.input} type="password" placeholder="New API secret (blank = keep)" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} autoComplete="new-password" />
              <button
                style={S.btnGreen}
                disabled={update.isPending}
                onClick={() => update.mutate({
                  id: acc.id,
                  ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
                  ...(apiSecret.trim() ? { api_secret: apiSecret.trim() } : {}),
                }, { onSuccess: () => { setEditKeys(false); setApiKey(''); setApiSecret(''); } })}
              >
                {update.isPending ? 'Saving…' : 'Save keys'}
              </button>
              {update.error && <div style={S.err}>✗ {update.error.message}</div>}
            </div>
          )}
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
          <button key={m} style={{ ...S.btn, background: method === m ? '#f1f1f1' : S.btn.background, color: method === m ? '#387ed1' : S.btn.color }} onClick={() => setMethod(m)}>
            {m === 'order' ? 'Order Margin' : m === 'basket' ? 'Basket Margin' : 'Charges'}
          </button>
        ))}
        {method === 'basket' && (
          <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', fontSize: 11, color: '#9b9b9b' }}>
            <input type="checkbox" checked={considerPos} onChange={(e) => setConsiderPos(e.target.checked)} /> Consider positions
          </label>
        )}
      </div>
      <textarea
        style={{ background: '#fff', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 4, padding: 10, fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const, minHeight: 100, resize: 'vertical' }}
        value={json}
        onChange={(e) => setJson(e.target.value)}
        rows={5}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
        <button style={S.btnGreen} onClick={calc} disabled={result.isPending}>{result.isPending ? '…' : `CALCULATE ${label}`}</button>
        {result.error && <span style={S.err}>✗ {result.error.message}</span>}
      </div>
      {latched && (
        <pre style={{ background: '#f9f9f9', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 4, padding: 10, marginTop: 10, fontSize: 11, fontFamily: 'monospace', overflow: 'auto', maxHeight: 300 }}>
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
          <div><span style={S.label}>State</span><span style={{ color: ts.connected ? '#4caf50' : ts.active ? '#ff9800' : '#e53935', fontWeight: 700 }}>{ts.active ? (ts.connected ? 'Connected' : 'Connecting…') : 'Off'}</span></div>
          <div><span style={S.label}>Subscribed</span><span style={{ color: '#444' }}>{ts.subscribed?.length ?? 0} tokens</span></div>
          <div><span style={S.label}>Ticks</span><span style={{ color: '#444' }}>{ts.tick_count?.toLocaleString('en-IN') ?? 0}</span></div>
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

function KiteSettings() {
  const layout = useKiteSettings((s) => s.engineSettingsLayout);
  const setLayout = useKiteSettings((s) => s.setEngineSettingsLayout);
  const opts: Array<{ value: 'tabs' | 'cards'; label: string }> = [
    { value: 'tabs', label: 'Tabs' },
    { value: 'cards', label: 'Expand-collapse' },
  ];
  return (
    <div style={S.card}>
      <div style={S.title}>KITE SETTINGS</div>

      <div style={{ marginBottom: 18 }}>
        <label style={{ ...S.label, marginBottom: 6 }}>SUPERTREND SETTINGS LAYOUT</label>
        <div style={{ display: 'inline-flex', border: `1px solid #e0e0e0`, borderRadius: 4, overflow: 'hidden' }}>
          {opts.map((o) => {
            const sel = layout === o.value;
            return (
              <button
                key={o.value}
                onClick={() => setLayout(o.value)}
                style={{
                  background: sel ? '#f06428' : '#fff',
                  color: sel ? '#fff' : '#444',
                  border: 'none',
                  padding: '6px 16px',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontSize: 11,
                  fontWeight: sel ? 700 : 400,
                }}
              >
                {o.label}
              </button>
            );
          })}
        </div>
        <div style={{ ...S.hint, marginTop: 6 }}>Choose how the Triple SuperTrend settings drawer is laid out.</div>
      </div>

      <div style={{ paddingTop: 16, borderTop: `1px solid #e0e0e0` }}>
        <KiteTelegramPanel />
      </div>
    </div>
  );
}

function DirectionalModePanelWrapper() {
  const { data: cfgData } = useEngineConfig();
  const { data: signals } = useEngineSignals();
  const setCfg = useSetEngineConfig();
  if (!cfgData) return null;

  // Pull a representative lot size + ATM premium from the freshest ready signal so
  // the impact calculator opens with real numbers. Prefer a fresh/active row.
  const rows = signals?.rows ?? [];
  const pick = rows.find((r) => r.is_fresh) ?? rows.find((r) => r.is_active) ?? rows[0];
  const leg = pick?.legs?.find((l) => l.moneyness === 'ATM') ?? pick?.legs?.[0];

  return (
    <DirectionalModePanel
      cfg={cfgData}
      onUpdate={(patch) => setCfg.mutate({ ...cfgData, ...patch })}
      busy={setCfg.isPending}
      liveLotSize={leg?.lot_size ?? undefined}
      livePremium={leg?.premium_spot ?? undefined}
      liveUnderlying={pick?.underlying}
    />
  );
}

// Master ON/OFF for the whole Triple-SuperTrend engine. Sits at the very bottom of
// the Connect page. OFF = Kite behaves as a normal manual-trading platform.
function EngineMasterToggle() {
  const { data: cfg } = useEngineConfig();
  const setCfg = useSetEngineConfig();
  if (!cfg) return null;
  const on = cfg.engine_enabled;
  return (
    <div style={{ ...S.card, borderColor: on ? '#4caf50' : '#e0e0e0', borderWidth: 2 }}>
      <div style={S.title}>TRIPLE SUPERTREND ENGINE</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button
          onClick={() => setCfg.mutate({ ...cfg, engine_enabled: !on })}
          disabled={setCfg.isPending}
          style={{
            width: 52, height: 28, borderRadius: 14, border: 'none', position: 'relative',
            cursor: 'pointer', background: on ? '#4caf50' : '#bbb', transition: 'background .2s', flexShrink: 0,
          }}
        >
          <span style={{
            position: 'absolute', top: 3, left: on ? 27 : 3, width: 22, height: 22, borderRadius: 11,
            background: '#fff', transition: 'left .2s', boxShadow: '0 1px 3px rgba(0,0,0,.3)',
          }} />
        </button>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: on ? '#2e7d32' : '#888' }}>
            {on ? 'Engine ON — scanning, signals & auto-execute active' : 'Engine OFF — normal manual Kite only'}
          </div>
          <div style={{ ...S.hint, marginTop: 2 }}>
            {on
              ? 'The strategy scans the market and surfaces signals. Auto-execute (if armed) places orders.'
              : 'No scanning, no signals, no auto-orders. Market watch, charts and manual orders work as usual.'}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Tabbed Connect page ────────────────────────────────────────────────────────
type ConnectTab = 'account' | 'strategy' | 'tools' | 'settings';

const TAB_DEFS: { id: ConnectTab; label: string; icon: string }[] = [
  { id: 'account',  label: 'Account',  icon: '👤' },
  { id: 'strategy', label: 'Strategy', icon: '🎯' },
  { id: 'tools',    label: 'Tools',    icon: '🧰' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
];

export function ConnectPane() {
  const { data, isLoading } = useKiteAccounts();
  const active = data?.accounts.find((a) => a.is_active);
  const liveTools = active?.connected && !active.is_paper;
  const [tab, setTab] = useState<ConnectTab>(() =>
    (localStorage.getItem('kite_connect_tab') as ConnectTab) || 'account');
  const select = (t: ConnectTab) => { setTab(t); localStorage.setItem('kite_connect_tab', t); };

  return (
    <div style={{ padding: '20px 32px 40px', maxWidth: 760, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
      <StatusBanner />

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid #e0e0e0' }}>
        {TAB_DEFS.map((t) => {
          const sel = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => select(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px',
                background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 12.5, fontWeight: sel ? 700 : 500, color: sel ? '#f06428' : '#888',
                borderBottom: `2px solid ${sel ? '#f06428' : 'transparent'}`, marginBottom: -1,
                transition: 'all .15s',
              }}
            >
              <span style={{ fontSize: 13 }}>{t.icon}</span>{t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === 'account' && (
        <>
          {isLoading && <div style={S.hint}>Loading…</div>}
          {data?.accounts.map((a) => <AccountCard key={a.id} acc={a} />)}
          {data && data.count === 0 && <div style={{ ...S.hint, marginBottom: 10 }}>No Kite accounts yet — add your API key & secret to begin.</div>}
          <AddAccount />
          <div style={{ ...S.hint, lineHeight: 1.7, marginTop: 16 }}>
            A Kite Connect app (kite.trade) gives you an <strong>API key + secret</strong>. Each session needs a daily login
            (token expires ~6 AM IST). Credentials are encrypted at rest and scoped to your user.
          </div>
        </>
      )}

      {tab === 'strategy' && (
        <>
          <TradingModeControls />
          <DirectionalModePanelWrapper />
        </>
      )}

      {tab === 'tools' && (
        <>
          {liveTools ? (
            <>
              <Funds />
              <MarginCalc />
              <TickerControl />
            </>
          ) : (
            <div style={{ ...S.card }}>
              <div style={S.title}>TOOLS</div>
              <div style={S.hint}>
                Funds, the margin/charges calculator and the WebSocket ticker appear here once an
                account is <strong>connected and in LIVE mode</strong>.
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'settings' && (
        <>
          <KiteSettings />
          <EngineMasterToggle />
        </>
      )}
    </div>
  );
}
