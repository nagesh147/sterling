import React, { useState, useEffect, useRef } from 'react';
import {
  useExchanges, useAddExchange, useUpdateExchange, useActivateExchange,
  useDeleteExchange, useTestConnection, useSupportedExchanges,
  useActivateDataSource, useDataSource,
} from '../hooks/useExchanges';
import type { ExchangeConfigResponse } from '../hooks/useExchanges';
import { c as t, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  row: { background: t.bg, border: `1px solid ${t.border}`, borderRadius: 4, padding: '10px 14px', marginBottom: 8 },
  rowHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  name: { fontWeight: 700, color: t.bright, fontSize: 13 },
  activeBadge: { background: '#44cc8822', color: t.green, border: `1px solid ${t.green}`, padding: '2px 8px', borderRadius: 3, fontSize: 10, fontWeight: 700 },
  paperBadge: { background: '#f0a50022', color: t.amber, border: `1px solid ${t.amber}`, padding: '2px 8px', borderRadius: 3, fontSize: 10 },
  credsBadge: { background: '#88aaff22', color: t.blue, border: `1px solid ${t.blue}`, padding: '2px 8px', borderRadius: 3, fontSize: 10 },
  dataBadge: { background: '#aa88ff22', color: 'var(--k-violet-3)', border: '1px solid var(--k-violet-3)', padding: '2px 8px', borderRadius: 3, fontSize: 10, fontWeight: 700 },
  actions: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 },
  btn: { background: t.raised, color: t.blue, border: `1px solid ${t.border}`, padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnGreen: { background: '#1a2a1a', color: t.green, border: `1px solid ${t.green}`, padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnRed: { background: t.raised, color: t.red, border: `1px solid ${t.red}`, padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnPurple: { background: t.raised, color: 'var(--k-violet-3)', border: '1px solid var(--k-violet-3)', padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  hint: { color: t.dim, fontSize: 11 },
  form: { background: t.bg, border: `1px solid ${t.border}`, borderRadius: 4, padding: 16, marginTop: 12 },
  formTitle: { color: t.dim, fontSize: 11, letterSpacing: 1, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1 },
  input: { background: t.raised, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 3, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 },
  select: { background: t.raised, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 3, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 },
  testResult: { marginTop: 6, fontSize: 11 },
  success: { color: t.green, fontSize: 11, marginTop: 6 },
  error: { color: t.red, fontSize: 11 },
};

const EXTRA_HINTS: Record<string, string> = {
  zerodha: '{"access_token":"session_token_from_kite_login"}',
  delta_india: '{}',
  deribit: '{}',
  okx: '{"subaccount":"optional"}',
  binance: '{}',
};

const DATA_SOURCE_ADAPTERS = new Set(['deribit', 'binance', 'okx', 'delta_india']);

function ExchangeRow({ ex, currentDataSource }: { ex: ExchangeConfigResponse; currentDataSource?: string }) {
  const [showEdit, setShowEdit] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [extraJson, setExtraJson] = useState(JSON.stringify(ex.extra ?? {}));
  const [isPaper, setIsPaper] = useState(ex.is_paper);
  const [saveMsg, setSaveMsg] = useState('');
  const saveMsgTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activate = useActivateExchange();

  // Cleanup timer on unmount
  useEffect(() => () => { if (saveMsgTimer.current) clearTimeout(saveMsgTimer.current); }, []);
  const activateDs = useActivateDataSource();
  const del = useDeleteExchange();
  const update = useUpdateExchange();
  const test = useTestConnection();

  const isCurrentDataSource = currentDataSource === ex.name;

  const handleUpdate = () => {
    let extra: Record<string, unknown> | undefined;
    try { extra = JSON.parse(extraJson || '{}'); } catch { extra = undefined; }

    const payload: Record<string, unknown> = { is_paper: isPaper };
    if (apiKey.trim()) payload.api_key = apiKey.trim();
    if (apiSecret.trim()) payload.api_secret = apiSecret.trim();
    if (extra !== undefined) payload.extra = extra;

    update.mutate(
      { id: ex.id, ...(payload as Omit<Parameters<typeof update.mutate>[0], 'id'>) },
      {
        onSuccess: () => {
          setSaveMsg('✓ Saved to database');
          setShowEdit(false);
          setApiKey('');
          setApiSecret('');
          if (saveMsgTimer.current) clearTimeout(saveMsgTimer.current);
          saveMsgTimer.current = setTimeout(() => setSaveMsg(''), 3000);
        },
        onError: (err) => setSaveMsg(`✗ Save failed: ${err.message}`),
      }
    );
  };

  return (
    <div style={S.row}>
      <div style={S.rowHeader}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={S.name}>{ex.display_name}</span>
          {ex.is_active && <span style={S.activeBadge}>ACCOUNT</span>}
          {isCurrentDataSource && <span style={S.dataBadge}>DATA SOURCE</span>}
          {ex.is_paper && <span style={S.paperBadge}>PAPER</span>}
          {ex.has_credentials && <span style={S.credsBadge}>KEYS SET</span>}
        </div>
        <span style={S.hint}>{ex.api_key_hint}</span>
      </div>

      <div style={{ color: t.dim, fontSize: 11, marginBottom: 6 }}>
        {ex.name} · {ex.supported ? 'supported' : 'unsupported'}
        {!ex.has_credentials && ' · no credentials set'}
      </div>

      {test.data && (
        <div style={{ ...S.testResult, color: test.data.connected ? t.green : t.red }}>
          {test.data.connected ? '✓' : '✗'} {test.data.message ?? test.data.error}
        </div>
      )}
      {saveMsg && (
        <div style={saveMsg.startsWith('✓') ? S.success : S.error}>{saveMsg}</div>
      )}
      {activateDs.isSuccess && activateDs.variables === ex.id && (
        <div style={S.success}>✓ Market data source switched</div>
      )}

      <div style={S.actions}>
        {!ex.is_active && (
          <button style={S.btnGreen} onClick={() => activate.mutate(ex.id)} disabled={activate.isPending}>
            {activate.isPending ? '…' : 'SET ACCOUNT'}
          </button>
        )}
        {DATA_SOURCE_ADAPTERS.has(ex.name) && !isCurrentDataSource && (
          <button
            style={S.btnPurple}
            onClick={() => activateDs.mutate(ex.id)}
            disabled={activateDs.isPending}
            title="Switch market data (candles, prices, options) to this exchange"
          >
            {activateDs.isPending ? '…' : 'USE FOR DATA'}
          </button>
        )}
        <button style={S.btn} onClick={() => test.mutate(ex.id)} disabled={test.isPending}>
          {test.isPending ? 'TESTING…' : 'TEST'}
        </button>
        <button style={S.btn} onClick={() => setShowEdit(!showEdit)}>
          {showEdit ? 'CANCEL' : 'EDIT KEYS'}
        </button>
        <button style={S.btnRed} onClick={() => del.mutate(ex.id)} disabled={del.isPending}>
          REMOVE
        </button>
      </div>

      {showEdit && (
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input
            style={S.input}
            type="text"
            placeholder="New API Key (leave empty to keep current)"
            value={apiKey}
            onChange={e => setApiKey(e.target.value)}
            autoComplete="off"
          />
          <input
            style={S.input}
            type="password"
            placeholder="New API Secret (leave empty to keep current)"
            value={apiSecret}
            onChange={e => setApiSecret(e.target.value)}
            autoComplete="new-password"
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ color: t.dim, fontSize: 10, letterSpacing: 1 }}>
              EXTRA CONFIG (JSON)
              {ex.name === 'zerodha' && (
                <span style={{ color: t.amber, marginLeft: 6 }}>Zerodha: set access_token daily</span>
              )}
            </span>
            <input
              style={{ ...S.input, fontFamily: 'monospace', fontSize: 11 }}
              type="text"
              placeholder={EXTRA_HINTS[ex.name] ?? '{}'}
              value={extraJson}
              onChange={e => setExtraJson(e.target.value)}
            />
          </div>
          <label style={{ ...S.label, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={isPaper} onChange={e => setIsPaper(e.target.checked)} />
            Paper mode (no real trades)
          </label>
          <button style={S.btnGreen} onClick={handleUpdate} disabled={update.isPending}>
            {update.isPending ? 'SAVING…' : 'SAVE CREDENTIALS'}
          </button>
          {update.error && <div style={S.error}>✗ {update.error.message}</div>}
        </div>
      )}
    </div>
  );
}

function AddExchangeForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('delta_india');
  const [displayName, setDisplayName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [extraJson, setExtraJson] = useState('{}');
  const [isPaper, setIsPaper] = useState(true);
  const add = useAddExchange();
  const { data: supported } = useSupportedExchanges();

  const handleAdd = () => {
    let extra = {};
    try { extra = JSON.parse(extraJson || '{}'); } catch { /* ignore bad JSON */ }
    add.mutate(
      { name, display_name: displayName, api_key: apiKey, api_secret: apiSecret, is_paper: isPaper, extra },
      { onSuccess: onDone }
    );
  };

  return (
    <div style={S.form}>
      <div style={S.formTitle}>ADD EXCHANGE</div>
      <div style={S.grid}>
        <div style={S.field}>
          <label style={S.label}>EXCHANGE</label>
          <select style={S.select} value={name} onChange={e => { setName(e.target.value); setExtraJson('{}'); }}>
            {(supported?.exchanges ?? []).map(ex => (
              <option key={ex.name} value={ex.name}>{ex.display_name}</option>
            ))}
          </select>
        </div>
        <div style={S.field}>
          <label style={S.label}>DISPLAY NAME (optional)</label>
          <input style={S.input} type="text" placeholder="My Delta Account"
            value={displayName} onChange={e => setDisplayName(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>API KEY</label>
          <input style={S.input} type="text" placeholder="Enter API key"
            value={apiKey} onChange={e => setApiKey(e.target.value)} autoComplete="off" />
        </div>
        <div style={S.field}>
          <label style={S.label}>API SECRET</label>
          <input style={S.input} type="password" placeholder="Enter API secret"
            value={apiSecret} onChange={e => setApiSecret(e.target.value)} autoComplete="new-password" />
        </div>
      </div>
      {EXTRA_HINTS[name] && EXTRA_HINTS[name] !== '{}' && (
        <div style={S.field}>
          <label style={S.label}>
            EXTRA CONFIG (JSON)
            <span style={{ color: t.amber, marginLeft: 8 }}>e.g. {EXTRA_HINTS[name]}</span>
          </label>
          <input
            style={{ ...S.input, fontFamily: 'monospace', fontSize: 11 }}
            type="text"
            placeholder={EXTRA_HINTS[name]}
            value={extraJson}
            onChange={e => setExtraJson(e.target.value)}
          />
        </div>
      )}
      <label style={{ ...S.label, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', marginBottom: 10, marginTop: 8 }}>
        <input type="checkbox" checked={isPaper} onChange={e => setIsPaper(e.target.checked)} />
        Paper mode (disable live account calls)
      </label>
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={S.btnGreen} onClick={handleAdd} disabled={add.isPending}>
          {add.isPending ? 'ADDING…' : '+ ADD EXCHANGE'}
        </button>
        <button style={S.btn} onClick={onDone}>CANCEL</button>
      </div>
      {add.error && <div style={S.error}>{(add.error as Error).message}</div>}
    </div>
  );
}

export function ExchangeManager() {
  const { data, isLoading } = useExchanges();
  const { data: dsData } = useDataSource();
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div style={S.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <div style={S.title}>EXCHANGE ACCOUNTS</div>
          {dsData && (
            <div style={{ color: 'var(--k-violet-3)', fontSize: 11 }}>
              Data source: <strong>{dsData.display_name}</strong>
              {' '}
              <span style={{ color: dsData.reachable ? t.green : t.red }}>
                {dsData.reachable ? '● live' : '● unreachable'}
              </span>
            </div>
          )}
        </div>
        <button style={S.btnGreen} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? 'CANCEL' : '+ ADD EXCHANGE'}
        </button>
      </div>

      {isLoading && <div style={{ color: t.dim, fontSize: 12 }}>Loading…</div>}
      {data?.exchanges.map(ex => (
        <ExchangeRow key={ex.id} ex={ex} currentDataSource={dsData?.exchange} />
      ))}

      {showAdd && <AddExchangeForm onDone={() => setShowAdd(false)} />}

      <div style={{ marginTop: 12, color: t.dim, fontSize: 10, lineHeight: 1.8 }}>
        <strong style={{ color: t.dim }}>ACCOUNT</strong> — active exchange for balance/positions/orders<br />
        <strong style={{ color: 'var(--k-violet-3)' }}>DATA SOURCE</strong> — exchange providing candles, prices, option chains<br />
        PAPER MODE: account calls return mock data. KEYS SET: real credentials saved.
      </div>
    </div>
  );
}
