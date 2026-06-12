import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useActivateKiteAccount, useAddKiteAccount, useDeleteKiteAccount, useGenerateKiteSession,
  useKiteAccounts, useKiteLoginUrl, useKiteLogout, useKiteMargins, useKiteStatus,
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
          <label style={S.label}>2 · PASTE request_token</label>
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
          {gen.error && <div style={S.err}>✗ {gen.error.message}</div>}
          {account.connected && (
            <button style={{ ...S.btnRed, marginTop: 10 }} onClick={() => logout.mutate()}>Log out</button>
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

export function ConnectPane() {
  const { data, isLoading } = useKiteAccounts();
  const active = data?.accounts.find((a) => a.is_active);
  return (
    <div>
      <StatusBanner />
      {active && <LoginFlow account={active} />}
      {active?.connected && !active.is_paper && <Funds />}
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
