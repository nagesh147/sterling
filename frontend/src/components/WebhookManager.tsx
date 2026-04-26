import React, { useState } from 'react';
import { useWebhooks, useAddWebhook, useDeleteWebhook, useToggleWebhook, useTestWebhook } from '../hooks/useWebhooks';
import type { WebhookType } from '../hooks/useWebhooks';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  row: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: '10px 14px', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  left: { display: 'flex', flexDirection: 'column', gap: 3 },
  name: { fontWeight: 700, color: '#e0e0e0', fontSize: 13 },
  sub: { fontSize: 11, color: '#555' },
  badge: { fontSize: 10, padding: '2px 7px', borderRadius: 3, fontWeight: 600 },
  actions: { display: 'flex', gap: 6 },
  btn: { background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '3px 9px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  btnGreen: { background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  btnRed: { background: '#2a1a1a', color: '#cc4444', border: '1px solid #cc444444', padding: '3px 9px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  form: { background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 4, padding: 14, marginTop: 10 },
  field: { display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  input: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  select: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  noData: { color: '#444', fontSize: 12, padding: '16px 0', textAlign: 'center' },
  testOk: { color: '#44cc88', fontSize: 11 },
  testFail: { color: '#cc4444', fontSize: 11 },
};

const TYPE_LABELS: Record<WebhookType, string> = {
  discord: 'Discord', telegram: 'Telegram', generic: 'HTTP POST'
};
const TYPE_HINT: Record<WebhookType, string> = {
  discord: 'Webhook URL from Discord channel settings',
  telegram: 'Bot API URL — set chat_id in Extra JSON',
  generic: 'Any URL that accepts POST JSON',
};

function WebhookRow({ wh }: { wh: any }) {
  const del = useDeleteWebhook();
  const toggle = useToggleWebhook();
  const test = useTestWebhook();

  return (
    <div style={S.row}>
      <div style={S.left}>
        <span style={S.name}>{wh.name}</span>
        <span style={S.sub}>{TYPE_LABELS[wh.webhook_type as WebhookType]} · {wh.url.slice(0, 40)}…</span>
        {wh.trigger_count > 0 && (
          <span style={{ ...S.sub, color: '#666' }}>Fired {wh.trigger_count}×</span>
        )}
        {test.data && (
          <span style={test.data.delivered ? S.testOk : S.testFail}>
            {test.data.delivered ? '✓ Delivered' : `✗ ${test.data.error}`}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ ...S.badge, background: wh.active ? '#44cc8822' : '#33333322', color: wh.active ? '#44cc88' : '#555' }}>
          {wh.active ? 'ON' : 'OFF'}
        </span>
        <div style={S.actions}>
          <button style={S.btn} onClick={() => test.mutate(wh.id)} disabled={test.isPending}>
            {test.isPending ? '…' : 'TEST'}
          </button>
          <button style={S.btn} onClick={() => toggle.mutate(wh.id)}>
            {wh.active ? 'DISABLE' : 'ENABLE'}
          </button>
          <button style={S.btnRed} onClick={() => del.mutate(wh.id)}>✕</button>
        </div>
      </div>
    </div>
  );
}

function AddWebhookForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('');
  const [type, setType] = useState<WebhookType>('discord');
  const [url, setUrl] = useState('');
  const [extraJson, setExtraJson] = useState('{}');
  const add = useAddWebhook();

  const handleAdd = () => {
    let extra = {};
    try { extra = JSON.parse(extraJson); } catch { /* ignore */ }
    add.mutate({ name, webhook_type: type, url, extra, active: true }, { onSuccess: onDone });
  };

  return (
    <div style={S.form}>
      <div style={S.field}>
        <label style={S.label}>NAME</label>
        <input style={S.input} placeholder="My Discord Alert" value={name} onChange={e => setName(e.target.value)} />
      </div>
      <div style={S.field}>
        <label style={S.label}>TYPE</label>
        <select style={S.select} value={type} onChange={e => setType(e.target.value as WebhookType)}>
          {(Object.keys(TYPE_LABELS) as WebhookType[]).map(t => (
            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
          ))}
        </select>
        <span style={{ color: '#444', fontSize: 10 }}>{TYPE_HINT[type]}</span>
      </div>
      <div style={S.field}>
        <label style={S.label}>URL</label>
        <input style={S.input} placeholder="https://..." value={url} onChange={e => setUrl(e.target.value)} />
      </div>
      <div style={S.field}>
        <label style={S.label}>EXTRA CONFIG (JSON) — Telegram: {`{"chat_id":"123"}`}</label>
        <input style={S.input} value={extraJson} onChange={e => setExtraJson(e.target.value)} />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={S.btnGreen} onClick={handleAdd} disabled={add.isPending || !name || !url}>
          {add.isPending ? 'ADDING…' : '+ ADD WEBHOOK'}
        </button>
        <button style={S.btn} onClick={onDone}>CANCEL</button>
      </div>
      {add.error && <div style={{ color: '#cc4444', fontSize: 11, marginTop: 6 }}>{(add.error as Error).message}</div>}
    </div>
  );
}

export function WebhookManager() {
  const { data } = useWebhooks();
  const [showAdd, setShowAdd] = useState(false);

  return (
    <div style={S.card}>
      <div style={S.header}>
        <div style={S.title}>WEBHOOK NOTIFICATIONS (Discord / Telegram / HTTP)</div>
        <button style={S.btnGreen} onClick={() => setShowAdd(!showAdd)}>
          {showAdd ? 'CANCEL' : '+ ADD'}
        </button>
      </div>

      {showAdd && <AddWebhookForm onDone={() => setShowAdd(false)} />}

      {!data || data.count === 0 ? (
        <div style={S.noData}>No webhooks. Add one to receive alerts via Discord, Telegram, or HTTP.</div>
      ) : (
        data.webhooks.map(wh => <WebhookRow key={wh.id} wh={wh} />)
      )}
    </div>
  );
}
