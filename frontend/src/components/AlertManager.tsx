import React, { useState } from 'react';
import {
  useAlerts, useCreateAlert, useCheckAlerts, useDismissAlert, useDeleteAlert,
  useBulkClearDismissed, CONDITION_LABELS,
} from '../hooks/useAlerts';
import type { Alert, AlertCondition } from '../hooks/useAlerts';
import { fmtN } from '../utils/fmt';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  counts: { display: 'flex', gap: 10, fontSize: 11 },
  row: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: '8px 12px', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  left: { display: 'flex', flexDirection: 'column', gap: 3 },
  sym: { fontWeight: 700, color: '#e0e0e0', fontSize: 13 },
  cond: { fontSize: 11, color: '#888' },
  status: { fontSize: 11, padding: '2px 8px', borderRadius: 3, fontWeight: 600 },
  actions: { display: 'flex', gap: 6 },
  btn: { background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '3px 8px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  btnRed: { background: '#2a1a1a', color: '#cc6666', border: '1px solid #cc666644', padding: '3px 8px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  form: { background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 4, padding: 12, marginTop: 10 },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 },
  field: { display: 'flex', flexDirection: 'column', gap: 3 },
  label: { color: '#555', fontSize: 10, letterSpacing: 1 },
  input: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  select: { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  addBtn: { background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  checkBtn: { background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  noData: { color: '#444', fontSize: 12, textAlign: 'center', padding: 20 },
  checkResult: { background: '#0d1a0d', border: '1px solid #44cc88' + '44', borderRadius: 4, padding: '8px 12px', marginTop: 8, fontSize: 11 },
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  active: { background: '#88aaff22', color: '#88aaff' },
  triggered: { background: '#cc888822', color: '#cc8888' },
  dismissed: { background: '#33333322', color: '#555' },
};

const NEEDS_THRESHOLD = new Set<AlertCondition>(['price_above', 'price_below', 'ivr_above', 'ivr_below']);
const NEEDS_STATE = new Set<AlertCondition>(['state_is']);

function AlertRow({ alert }: { alert: Alert }) {
  const dismiss = useDismissAlert();
  const del = useDeleteAlert();
  const isFired = alert.status === 'triggered';

  return (
    <div style={S.row}>
      <div style={S.left}>
        <span style={S.sym}>{alert.underlying}</span>
        <span style={S.cond}>
          {CONDITION_LABELS[alert.condition]}
          {alert.threshold != null ? ` ${alert.threshold.toLocaleString()}` : ''}
          {alert.target_state ? ` ${alert.target_state}` : ''}
          {isFired && alert.trigger_value != null ? ` → fired at ${fmtN(alert.trigger_value, 2)}` : ''}
        </span>
        {alert.notes && <span style={{ color: '#555', fontSize: 10 }}>{alert.notes}</span>}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ ...S.status, ...STATUS_STYLE[alert.status] }}>
          {alert.status.toUpperCase()}
        </span>
        <div style={S.actions}>
          {alert.status !== 'dismissed' && (
            <button style={S.btn} onClick={() => dismiss.mutate(alert.id)} disabled={dismiss.isPending}>
              DISMISS
            </button>
          )}
          <button style={S.btnRed} onClick={() => del.mutate(alert.id)} disabled={del.isPending}>✕</button>
        </div>
      </div>
    </div>
  );
}

function AddAlertForm({ onDone }: { onDone: () => void }) {
  const [underlying, setUnderlying] = useState('BTC');
  const [condition, setCondition] = useState<AlertCondition>('price_above');
  const [threshold, setThreshold] = useState('');
  const [targetState, setTargetState] = useState('ENTRY_ARMED_PULLBACK');
  const [cooldownHours, setCooldownHours] = useState('0');
  const [notes, setNotes] = useState('');
  const create = useCreateAlert();

  const handleAdd = () => {
    create.mutate({
      underlying,
      condition,
      threshold: NEEDS_THRESHOLD.has(condition) ? parseFloat(threshold) || undefined : undefined,
      target_state: NEEDS_STATE.has(condition) ? targetState : undefined,
      cooldown_hours: parseFloat(cooldownHours) || 0,
      notes,
    }, { onSuccess: onDone });
  };

  return (
    <div style={S.form}>
      <div style={S.grid}>
        <div style={S.field}>
          <label style={S.label}>UNDERLYING</label>
          <select style={S.select} value={underlying} onChange={e => setUnderlying(e.target.value)}>
            {['BTC', 'ETH', 'SOL', 'XRP'].map(u => <option key={u}>{u}</option>)}
          </select>
        </div>
        <div style={S.field}>
          <label style={S.label}>CONDITION</label>
          <select style={S.select} value={condition} onChange={e => setCondition(e.target.value as AlertCondition)}>
            {Object.entries(CONDITION_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {NEEDS_THRESHOLD.has(condition) && (
          <div style={S.field}>
            <label style={S.label}>THRESHOLD</label>
            <input style={S.input} type="number" placeholder="e.g. 45000"
              value={threshold} onChange={e => setThreshold(e.target.value)} />
          </div>
        )}
        {NEEDS_STATE.has(condition) && (
          <div style={S.field}>
            <label style={S.label}>TARGET STATE</label>
            <select style={S.select} value={targetState} onChange={e => setTargetState(e.target.value)}>
              {['ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION', 'CONFIRMED_SETUP_ACTIVE', 'EARLY_SETUP_ACTIVE'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
        <div style={{ flex: 1 }}>
          <input style={{ ...S.input, width: '100%' }} type="text"
            placeholder="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <label style={{ ...S.label }}>COOLDOWN (h)</label>
          <input style={{ ...S.input, width: 70 }} type="number" step="0.5" min="0"
            title="Re-arm after N hours (0 = fire once)"
            value={cooldownHours} onChange={e => setCooldownHours(e.target.value)} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button style={S.addBtn} onClick={handleAdd} disabled={create.isPending}>
          {create.isPending ? 'ADDING…' : '+ ADD ALERT'}
        </button>
        <button style={S.btn} onClick={onDone}>CANCEL</button>
      </div>
      {create.error && <div style={{ color: '#cc4444', fontSize: 11, marginTop: 6 }}>{(create.error as Error).message}</div>}
    </div>
  );
}

export function AlertManager() {
  const { data } = useAlerts();
  const check = useCheckAlerts();
  const bulkClear = useBulkClearDismissed();
  const [showAdd, setShowAdd] = useState(false);
  const hasDismissed = data?.alerts.some(a => a.status === 'dismissed') ?? false;

  return (
    <div style={S.card}>
      <div style={S.header}>
        <div>
          <div style={S.title}>PRICE & SIGNAL ALERTS</div>
          {data && (
            <div style={S.counts}>
              <span style={{ color: '#88aaff' }}>{data.active_count} ACTIVE</span>
              <span style={{ color: '#cc8888' }}>{data.triggered_count} TRIGGERED</span>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={check.isPending ? { ...S.checkBtn, opacity: 0.5 } : S.checkBtn}
            onClick={() => check.mutate()} disabled={check.isPending}>
            {check.isPending ? 'CHECKING…' : '⟳ CHECK NOW'}
          </button>
          {hasDismissed && (
            <button style={{ ...S.btn, color: '#666', borderColor: '#333' }}
              onClick={() => bulkClear.mutate()} disabled={bulkClear.isPending}>
              CLEAR DISMISSED
            </button>
          )}
          <button style={S.addBtn} onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? 'CANCEL' : '+ ADD'}
          </button>
        </div>
      </div>

      {check.data && check.data.newly_triggered > 0 && (
        <div style={S.checkResult}>
          ✓ Checked {check.data.checked} alerts — {check.data.newly_triggered} newly triggered
        </div>
      )}

      {showAdd && <AddAlertForm onDone={() => setShowAdd(false)} />}

      {!data || data.alerts.length === 0 ? (
        <div style={S.noData}>No alerts. Add one to get notified when conditions are met.</div>
      ) : (
        data.alerts.map(a => <AlertRow key={a.id} alert={a} />)
      )}
    </div>
  );
}
