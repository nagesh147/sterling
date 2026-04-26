import React, { useState } from 'react';
import {
  useExchanges, useAddExchange, useUpdateExchange, useActivateExchange,
  useDeleteExchange, useTestConnection, useSupportedExchanges,
} from '../hooks/useExchanges';
import type { ExchangeConfigResponse } from '../hooks/useExchanges';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  row: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: '10px 14px', marginBottom: 8 },
  rowHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  name: { fontWeight: 700, color: '#e0e0e0', fontSize: 13 },
  activeBadge: { background: '#44cc88' + '22', color: '#44cc88', border: '1px solid #44cc88', padding: '2px 8px', borderRadius: 3, fontSize: 10, fontWeight: 700 },
  paperBadge: { background: '#f0a500' + '22', color: '#f0a500', border: '1px solid #f0a500', padding: '2px 8px', borderRadius: 3, fontSize: 10 },
  actions: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 },
  btn: { background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnGreen: { background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88', padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnRed: { background: '#2a1a1a', color: '#cc4444', border: '1px solid #cc4444', padding: '4px 10px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  hint: { color: '#555', fontSize: 11 },
  form: { background: '#0d0d0d', border: '1px solid #222', borderRadius: 4, padding: 16, marginTop: 12 },
  formTitle: { color: '#888', fontSize: 11, letterSpacing: 1, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  input: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 },
  select: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 },
  testResult: { marginTop: 6, fontSize: 11 },
  error: { color: '#cc4444', fontSize: 11 },
};

function ExchangeRow({ ex }: { ex: ExchangeConfigResponse }) {
  const [showEdit, setShowEdit] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [extraJson, setExtraJson] = useState(JSON.stringify(ex.extra ?? {}));
  const [isPaper, setIsPaper] = useState(ex.is_paper);
  const activate = useActivateExchange();
  const del = useDeleteExchange();
  const update = useUpdateExchange();
  const test = useTestConnection();

  const handleUpdate = () => {
    let extra: Record<string, unknown> | undefined;
    try { extra = JSON.parse(extraJson || '{}'); } catch { extra = undefined; }
    update.mutate({
      id: ex.id,
      api_key: apiKey || undefined,
      api_secret: apiSecret || undefined,
      is_paper: isPaper,
      extra,
    });
    setShowEdit(false);
    setApiKey('');
    setApiSecret('');
  };

  return (
    <div style={S.row}>
      <div style={S.rowHeader}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={S.name}>{ex.display_name}</span>
          {ex.is_active && <span style={S.activeBadge}>ACTIVE</span>}
          {ex.is_paper && <span style={S.paperBadge}>PAPER</span>}
        </div>
        <span style={S.hint}>{ex.api_key_hint}</span>
      </div>

      <div style={{ color: '#555', fontSize: 11, marginBottom: 6 }}>
        {ex.name} · {ex.supported ? 'supported' : 'unsupported'}
      </div>

      {test.data && (
        <div style={{ ...S.testResult, color: test.data.connected ? '#44cc88' : '#cc4444' }}>
          {test.data.connected ? '✓' : '✗'} {test.data.message || test.data.error}
        </div>
      )}

      <div style={S.actions}>
        {!ex.is_active && (
          <button style={S.btnGreen} onClick={() => activate.mutate(ex.id)} disabled={activate.isPending}>
            {activate.isPending ? '…' : 'SET ACTIVE'}
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
          <input style={S.input} type="text" placeholder="New API Key (leave empty to keep current)"
            value={apiKey} onChange={e => setApiKey(e.target.value)} />
          <input style={S.input} type="password" placeholder="New API Secret (leave empty to keep current)"
            value={apiSecret} onChange={e => setApiSecret(e.target.value)} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ color: '#555', fontSize: 10, letterSpacing: 1 }}>
              EXTRA CONFIG (JSON)
              {ex.name === 'zerodha' && <span style={{ color: '#f0a500', marginLeft: 6 }}>Zerodha: set access_token here daily</span>}
            </span>
            <input style={{ ...S.input, fontFamily: 'monospace', fontSize: 11 }} type="text"
              placeholder={EXTRA_HINTS[ex.name] ?? '{}'}
              value={extraJson} onChange={e => setExtraJson(e.target.value)} />
          </div>
          <label style={{ ...S.label, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={isPaper} onChange={e => setIsPaper(e.target.checked)} />
            Paper mode (no real trades)
          </label>
          <button style={S.btnGreen} onClick={handleUpdate} disabled={update.isPending}>
            {update.isPending ? 'SAVING…' : 'SAVE'}
          </button>
        </div>
      )}
    </div>
  );
}

const EXTRA_HINTS: Record<string, string> = {
  zerodha: '{"access_token":"session_token_from_kite_login"}',
  delta_india: '{}',
  deribit: '{}',
  okx: '{"subaccount":"optional"}',
};

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
    add.mutate({
      name, display_name: displayName, api_key: apiKey, api_secret: apiSecret,
      is_paper: isPaper, extra,
    }, { onSuccess: onDone });
  };

  return (
    <div style={S.form}>
      <div style={S.formTitle}>ADD EXCHANGE</div>
      <div style={S.grid}>
        <div style={S.field}>
          <label style={S.label}>EXCHANGE</label>
          <select style={S.select} value={name} onChange={e => setName(e.target.value)}>
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
            value={apiKey} onChange={e => setApiKey(e.target.value)} />
        </div>
        <div style={S.field}>
          <label style={S.label}>API SECRET</label>
          <input style={S.input} type="password" placeholder="Enter API secret"
            value={apiSecret} onChange={e => setApiSecret(e.target.value)} />
        </div>
      </div>
      <div style={S.field}>
        <label style={S.label}>
          EXTRA CONFIG (JSON)
          {EXTRA_HINTS[name] && EXTRA_HINTS[name] !== '{}' && (
            <span style={{ color: '#f0a500', marginLeft: 8 }}>
              e.g. {EXTRA_HINTS[name]}
            </span>
          )}
        </label>
        <input
          style={{ ...S.input, fontFamily: 'monospace', fontSize: 11 }}
          type="text"
          placeholder={EXTRA_HINTS[name] ?? '{}'}
          value={extraJson}
          onChange={e => setExtraJson(e.target.value)}
        />
      </div>
      <label style={{ ...S.label, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', marginBottom: 10 }}>
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
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div style={S.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={S.title}>EXCHANGE ACCOUNTS</div>
        <button style={S.btnGreen} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? 'CANCEL' : '+ ADD EXCHANGE'}
        </button>
      </div>

      {isLoading && <div style={{ color: '#444', fontSize: 12 }}>Loading…</div>}
      {data?.exchanges.map(ex => <ExchangeRow key={ex.id} ex={ex} />)}

      {showAdd && <AddExchangeForm onDone={() => setShowAdd(false)} />}

      <div style={{ marginTop: 12, color: '#444', fontSize: 10, lineHeight: 1.6 }}>
        PAPER MODE: market data works, account calls return mock data.<br />
        LIVE MODE: requires valid API key+secret. No order placement — paper trading only.
      </div>
    </div>
  );
}
