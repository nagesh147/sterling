import React, { useState } from 'react';
import {
  useActivateKiteAccount, useAddKiteAccount, useDeleteKiteAccount, useGenerateKiteSession,
  useKiteAccounts, useKiteBasketMargins, useKiteLoginUrl, useKiteLogout, useKiteOrderCharges,
  useKiteOrderMargins, useKiteMargins, useKiteStatus, useKiteTickerStatus,
  useKiteTickerSubscribe, useKiteTickerUnsubscribe, useRefreshKiteSession,
  useTestKiteAccount, useUpdateKiteAccount,
} from '../../hooks/useKite';
import { useEngineConfig } from '../../hooks/useSterlingKiteEngine';
import type { KiteAccount } from '../../types/kite';
import { ModeToggle } from './ModeToggle';
import { KiteTelegramPanel, BrandIconPicker } from './KiteTelegramPanel';
import { ButtonLoader } from './KiteLoader';
import { MotionStyleSettings } from './MotionStyleSettings';
import { KiteExchangeSettingsCard } from './KiteExchangeSettingsCard';
import { NavigatorSettingsPanel } from './NavigatorSettingsPanel';
import { NavigatorCalibrationPanel } from './NavigatorCalibrationPanel';
import { MarketContractsPanel } from './MarketContractsPanel';
import { TradeRulesPanel } from './TradeRulesPanel';
import { SuperTrendEnginePanel } from './SuperTrendEnginePanel';
import { TradingModePanel } from './TradingModePanel';
import { type SectionId, resolveSectionId } from './config/registry';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: `1px solid #e0e0e0`, borderRadius: 9, padding: 18, marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' },
  title: { color: '#777', fontSize: 10.5, letterSpacing: .75, marginBottom: 12, fontWeight: 750 },
  row: { background: '#f7f7f8', border: `1px solid #e0e0e0`, borderRadius: 7, padding: '11px 14px', marginBottom: 8 },
  name: { fontWeight: 700, color: '#444', fontSize: 13 },
  actions: { display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 },
  btn: { minHeight: 34, background: '#fff', color: '#444', border: `1px solid #dcdcdc`, padding: '0 12px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 600 },
  btnGreen: { minHeight: 34, background: '#f06428', color: '#fff', border: `1px solid #f06428`, padding: '0 13px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 700 },
  btnRed: { minHeight: 34, background: '#fff', color: '#c9433e', border: `1px solid #dcdcdc`, padding: '0 12px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11, fontWeight: 600 },
  input: { minHeight: 36, background: '#fff', color: '#444', border: `1px solid #dcdcdc`, borderRadius: 7, padding: '0 10px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  label: { color: '#777', fontSize: 10, letterSpacing: .7, marginBottom: 4, display: 'block', fontWeight: 650 },
  hint: { color: '#888', fontSize: 11.5 },
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

  // Real Zerodha account holder name comes from /status (only for the connected
  // account). Prefer it over the user-chosen label, then fall back to the label.
  const statusName = status?.account_id === acc.id ? status?.user_name : null;
  const kiteId = statusName ? status?.kite_user_id ?? acc.kite_user_id : acc.kite_user_id;
  const displayName = statusName || acc.label;
  const subText = [kiteId ? `ID ${kiteId}` : null, displayName !== acc.label ? acc.label : null]
    .filter(Boolean).join(' · ') || acc.api_key_hint || '';

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
                  {refresh.isPending ? <ButtonLoader color="#387ed1" /> : '↻ Refresh'}
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
                  {gen.isPending ? <ButtonLoader /> : 'Connect'}
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
        style={{ background: '#fff', color: '#444', border: `1px solid #dcdcdc`, borderRadius: 7, padding: 10, fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const, minHeight: 100, resize: 'vertical' }}
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

// ── Settings hub ─────────────────────────────────────────────────────────────
// Connect used to contain another horizontal tab bar, while display, exchange,
// Telegram and engine controls were injected above/between those tabs. A stable
// category rail gives every setting one predictable home and keeps each page calm.
//
// The rail is now grouped by what a setting decides, rather than by which
// component happened to own it. The three trading groups follow the order a
// user actually thinks in: am I live and who places the order → what do we
// scan → how is the trade handled. Each signal engine then keeps only the
// settings that exist because of that engine's own indicator.
type ConnectSection = SectionId;

type SectionDef = { id: ConnectSection; label: string; eyebrow: string; group: string };

const SECTION_DEFS: SectionDef[] = [
  { id: 'account', label: 'Account & Login', eyebrow: 'Zerodha connection', group: 'Connection' },
  { id: 'mode', label: 'Trading Mode', eyebrow: 'Paper/live, manual/automatic', group: 'Trading' },
  { id: 'market', label: 'Market & Contracts', eyebrow: 'What gets scanned', group: 'Trading' },
  { id: 'rules', label: 'Trade Rules', eyebrow: 'Entry, stop, exit, size', group: 'Trading' },
  { id: 'engine', label: 'SuperTrend', eyebrow: 'Triple-SuperTrend strategy', group: 'Signal engines' },
  { id: 'navigator', label: 'Value-Flow Navigator', eyebrow: 'AVWAP, volatility & options flow', group: 'Signal engines' },
  { id: 'markets', label: 'Markets & Tools', eyebrow: 'Exchanges, funds & data', group: 'Platform' },
  { id: 'notifications', label: 'Notifications', eyebrow: 'Kite Telegram alerts', group: 'Platform' },
  { id: 'experience', label: 'Experience', eyebrow: 'Motion & feedback', group: 'Platform' },
];

function readInitialSection(): ConnectSection {
  // resolveSectionId follows the 2026-08-07 renames (sharedScan → market,
  // orderSelection → rules) and the older nested-tab ids, so a stored
  // preference or an existing deep link still lands somewhere sensible.
  return resolveSectionId(localStorage.getItem('kite_connect_section'))
    ?? resolveSectionId(localStorage.getItem('kite_connect_tab'))
    ?? 'account';
}

function StatusPill({ tone, children }: { tone: 'good' | 'warn' | 'quiet'; children: React.ReactNode }) {
  const color = tone === 'good' ? '#2e7d32' : tone === 'warn' ? '#b85c00' : '#777';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#666', padding: '3px 0', fontSize: 10.5, fontWeight: 650, whiteSpace: 'nowrap' }}>
      <span style={{ width: 6, height: 6, borderRadius: 3, background: color }} />{children}
    </span>
  );
}

function SectionHeading({ title, description }: { title: string; description: string }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <h2 style={{ margin: 0, color: '#333', fontSize: 19, fontWeight: 750, letterSpacing: '-.02em' }}>{title}</h2>
      <p style={{ margin: '6px 0 0', color: '#777', fontSize: 12, lineHeight: 1.55, maxWidth: 720 }}>{description}</p>
    </div>
  );
}

export function ConnectPane() {
  const { data, isLoading } = useKiteAccounts();
  const { data: engineCfg } = useEngineConfig();
  const active = data?.accounts.find((account) => account.is_active);
  const connected = !!active?.connected;
  const liveTools = connected && !active?.is_paper;
  const [section, setSection] = useState<ConnectSection>(readInitialSection);

  const select = (next: ConnectSection) => {
    setSection(next);
    localStorage.setItem('kite_connect_section', next);
  };

  React.useEffect(() => {
    const onOpen = (event: Event) => {
      const next = resolveSectionId((event as CustomEvent<string>).detail);
      if (next) select(next);
    };
    window.addEventListener('kite-connect-section', onOpen);
    return () => window.removeEventListener('kite-connect-section', onOpen);
  }, []);

  return (
    <div className="kite-settings-hub" style={{ width: '100%', boxSizing: 'border-box', padding: '28px 30px 48px', background: '#f7f7f8', minHeight: '100%' }}>
      <header style={{ maxWidth: 1120, margin: '0 auto 24px', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#777', fontSize: 10, fontWeight: 750, letterSpacing: .9, textTransform: 'uppercase' }}>
            <span aria-hidden style={{ width: 16, height: 2, borderRadius: 1, background: '#f06428' }} />Kite control center
          </div>
          <h1 style={{ margin: '6px 0 0', color: '#2f2f2f', fontSize: 24, lineHeight: 1.2, fontWeight: 760, letterSpacing: '-.025em' }}>Setup & Settings</h1>
          <p style={{ margin: '8px 0 0', color: '#777', fontSize: 12.5, lineHeight: 1.55, maxWidth: 600 }}>
            One place for the Zerodha connection, engine behaviour, markets, alerts and app experience.
          </p>
        </div>
        <div className="kite-settings-status" aria-label="Kite status" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'flex-end', padding: '7px 10px', borderTop: '1px solid #dedede', borderBottom: '1px solid #dedede' }}>
          <StatusPill tone={connected ? 'good' : active ? 'warn' : 'quiet'}>
            {connected ? `${active?.label ?? 'Kite'} connected` : active ? 'Login required' : 'No account'}
          </StatusPill>
          <StatusPill tone={engineCfg?.engine_enabled ? 'good' : 'quiet'}>
            Engine {engineCfg?.engine_enabled ? 'on' : 'off'}
          </StatusPill>
          {active && <StatusPill tone={active.is_paper ? 'quiet' : 'warn'}>{active.is_paper ? 'Paper' : 'Live'}</StatusPill>}
        </div>
      </header>

      <div className="kite-settings-layout" style={{ maxWidth: 1120, margin: '0 auto', display: 'grid', gridTemplateColumns: '218px minmax(0, 1fr)', gap: 26, alignItems: 'start' }}>
        <nav aria-label="Kite settings sections" style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: 9, padding: 6, position: 'sticky', top: 14, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
          {SECTION_DEFS.map((item, index) => {
            const selected = item.id === section;
            const startsGroup = index === 0 || SECTION_DEFS[index - 1].group !== item.group;
            return (
              <React.Fragment key={item.id}>
                {startsGroup && (
                  <div className="kite-rail-group" style={{
                    padding: '10px 11px 4px', color: '#a0a0a0', fontSize: 9,
                    fontWeight: 750, letterSpacing: .8, textTransform: 'uppercase',
                  }}>
                    {item.group}
                  </div>
                )}
                <button type="button" aria-current={selected ? 'page' : undefined} onClick={() => select(item.id)} style={{
                  width: '100%', minHeight: 52, border: 'none', borderLeft: `3px solid ${selected ? '#f06428' : 'transparent'}`,
                  borderRadius: 6, background: selected ? '#fff5f0' : 'transparent',
                  display: 'flex', alignItems: 'center',
                  padding: '8px 11px', textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit', marginBottom: 2,
                }}>
                  <span style={{ minWidth: 0 }}>
                    <span style={{ display: 'block', color: '#444', fontSize: 12, lineHeight: 1.25, fontWeight: selected ? 750 : 600 }}>{item.label}</span>
                    <span style={{ display: 'block', color: '#929292', fontSize: 10, lineHeight: 1.3, marginTop: 3 }}>{item.eyebrow}</span>
                  </span>
                </button>
              </React.Fragment>
            );
          })}
        </nav>

        <main style={{ minWidth: 0 }}>
          {section === 'account' && (
            <>
              <SectionHeading title="Account & Login" description="Manage API credentials and the daily Zerodha session. Whether those orders are simulated or real is set under Trading Mode." />
              {isLoading && <div style={S.hint}>Loading accounts…</div>}
              {data?.accounts.map((account) => <AccountCard key={account.id} acc={account} />)}
              {data && data.count === 0 && <div style={{ ...S.hint, marginBottom: 10 }}>No Kite accounts yet — add your API key and secret to begin.</div>}
              <AddAccount />
              <div style={{ ...S.hint, lineHeight: 1.7, marginTop: 14 }}>
                Create the API key and secret at kite.trade. Sessions normally reset around 6 AM IST; credentials stay encrypted at rest.
              </div>
            </>
          )}

          {section === 'mode' && (
            <>
              <SectionHeading title="Trading Mode" description="Whether orders are simulated or real, whether you or the engine places them, and which signal engines are running. Everything on this page changes what happens to real money." />
              <TradingModePanel />
            </>
          )}

          {section === 'market' && (
            <>
              <SectionHeading title="Market & Contracts" description="What gets scanned, which chart a signal is read from, and which strikes and expiries are considered. Both signal engines read every setting here, so it is set once rather than configured twice." />
              <MarketContractsPanel />
            </>
          )}

          {section === 'rules' && (
            <>
              <SectionHeading title="Trade Rules" description="How a trade is sized, guarded and protected once a signal exists — in the order it happens, from entry through to the safety net. Every rule is tagged by whether it affects orders you place, orders the engine places, or both." />
              <TradeRulesPanel />
            </>
          )}

          {section === 'engine' && (
            <>
              <SectionHeading title="SuperTrend" description="The triple-SuperTrend strategy itself: how a setup is armed, how the stop trails, and what closes the trade. What it scans is in Market & Contracts; how the order is handled is in Trade Rules." />
              <SuperTrendEnginePanel />
            </>
          )}

          {section === 'navigator' && (
            <>
              <SectionHeading title="Value-Flow Navigator" description="A second signal engine alongside SuperTrend — it reads anchored VWAP structure, projected ranges, volatility regime, option flow and gamma activity. It can confirm SuperTrend's setups, find its own, or both. Off by default; never bypasses any existing order or risk control." />
              <NavigatorSettingsPanel />
              <NavigatorCalibrationPanel />
            </>
          )}

          {section === 'markets' && (
            <>
              <SectionHeading title="Markets & Tools" description="Choose the exchanges Sterling can use, then inspect funds, charges and live ticker subscriptions." />
              <KiteExchangeSettingsCard />
              {liveTools ? (
                <><Funds /><MarginCalc /><TickerControl /></>
              ) : (
                <div style={S.card}>
                  <div style={S.title}>LIVE ACCOUNT TOOLS</div>
                  <div style={S.hint}>Funds, margin/charges and manual ticker subscriptions become available after the active account is connected and switched to Live.</div>
                </div>
              )}
            </>
          )}

          {section === 'notifications' && (
            <>
              <SectionHeading title="Notifications" description="Manage only Kite signal destinations here. Crypto/global alerts remain separate." />
              <KiteTelegramPanel />
            </>
          )}

          {section === 'experience' && (
            <>
              <SectionHeading title="Experience" description="Choose how loading, dialogs and transitions feel throughout Kite." />
              <MotionStyleSettings />
              <section style={{ marginBottom: 16, padding: 18, background: '#fff', border: '1px solid #e0e0e0', borderRadius: 9, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
                <BrandIconPicker />
              </section>
              <div style={{ ...S.card, display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <span aria-hidden style={{ color: '#777', fontSize: 16 }}>ⓘ</span>
                <div style={{ color: '#777', fontSize: 11, lineHeight: 1.55 }}>
                  Signal-table layout, visible columns and history rows now live exclusively behind the settings button in the signal table itself.
                </div>
              </div>
            </>
          )}
        </main>
      </div>

      <style>{`
        @media (max-width: 820px) {
          .kite-settings-hub { padding: 18px 14px 36px !important; }
          .kite-settings-layout { grid-template-columns: 1fr !important; gap: 14px !important; }
          .kite-settings-layout > nav { position: static !important; display: flex; overflow-x: auto; gap: 4px; }
          .kite-settings-layout > nav button { min-width: 156px; margin-bottom: 0 !important; }
          /* The group headings only read as headings in the vertical rail; in the
             horizontal scroller they would be islands of text between buttons. */
          .kite-rail-group { display: none; }
        }
        @media (max-width: 560px) {
          .kite-settings-hub > header { flex-direction: column; }
          .kite-settings-hub > header > div:last-child { justify-content: flex-start !important; }
          .kite-settings-status { width: 100%; box-sizing: border-box; }
        }
      `}</style>
    </div>
  );
}
