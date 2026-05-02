import React, { useState } from 'react';
import {
  useAlerts, useCreateAlert, useCheckAlerts, useDismissAlert, useDeleteAlert,
  useBulkClearDismissed, CONDITION_LABELS,
} from '../hooks/useAlerts';
import type { Alert, AlertCondition, AlertStatus } from '../hooks/useAlerts';
import { fmtN } from '../utils/fmt';
import { useInstruments } from '../hooks/useInstruments';

const S: Record<string, React.CSSProperties> = {
  card:     { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title:    { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  header:   { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  counts:   { display: 'flex', gap: 10, fontSize: 11, marginTop: 4 },
  filterBar:{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' as const, alignItems: 'center' },
  row:      { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: '8px 12px', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  left:     { display: 'flex', flexDirection: 'column' as const, gap: 3, flex: 1 },
  sym:      { fontWeight: 700, color: '#e0e0e0', fontSize: 13 },
  cond:     { fontSize: 11, color: '#888' },
  ts:       { fontSize: 10, color: '#444' },
  statusChip: { fontSize: 11, padding: '2px 8px', borderRadius: 3, fontWeight: 600 },
  actions:  { display: 'flex', gap: 6, alignItems: 'center', marginLeft: 12 },
  btn:      { background: '#1a1a2a', color: '#88aaff', border: '1px solid #334', padding: '3px 8px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  btnRed:   { background: '#2a1a1a', color: '#cc6666', border: '1px solid #cc666644', padding: '3px 8px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 10 },
  form:     { background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 4, padding: 12, marginTop: 10 },
  grid:     { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 },
  field:    { display: 'flex', flexDirection: 'column' as const, gap: 3 },
  label:    { color: '#555', fontSize: 10, letterSpacing: 1 },
  input:    { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  select:   { background: '#141414', color: '#e0e0e0', border: '1px solid #2a2a2a', borderRadius: 3, padding: '5px 8px', fontFamily: 'inherit', fontSize: 12 },
  addBtn:   { background: '#1a2a1a', color: '#44cc88', border: '1px solid #44cc88', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  checkBtn: { background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff', padding: '5px 14px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11 },
  noData:   { color: '#444', fontSize: 12, textAlign: 'center' as const, padding: 20 },
  checkResult: { background: '#0d1a0d', border: '1px solid #44cc8844', borderRadius: 4, padding: '8px 12px', marginTop: 8, fontSize: 11 },
};

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  active:    { background: '#88aaff22', color: '#88aaff' },
  triggered: { background: '#cc888822', color: '#cc8888' },
  dismissed: { background: '#33333322', color: '#555' },
};

const NEEDS_THRESHOLD = new Set<AlertCondition>(['price_above', 'price_below', 'ivr_above', 'ivr_below']);
const NEEDS_STATE     = new Set<AlertCondition>(['state_is']);

type StatusFilter = 'all' | AlertStatus;
type DayFilter    = 0 | 1 | 7 | 30;

const STATUS_TABS: [StatusFilter, string][] = [
  ['all', 'ALL'], ['active', 'ACTIVE'], ['triggered', 'TRIGGERED'], ['dismissed', 'PAST'],
];

const DAY_OPTIONS: [DayFilter, string][] = [
  [0, 'ALL TIME'], [1, 'TODAY'], [7, 'LAST 7D'], [30, 'LAST 30D'],
];

function fmtTime(ms: number | null | undefined): string {
  if (!ms) return '';
  const d = new Date(ms);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
         ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit',
      fontSize: 10, letterSpacing: 1,
      color: active ? '#e0e0e0' : '#444',
      padding: '4px 10px',
      borderBottom: active ? '2px solid #44cc88' : '2px solid transparent',
    }}>
      {label}
    </button>
  );
}

function AlertRow({ alert }: { alert: Alert }) {
  const dismiss = useDismissAlert();
  const del     = useDeleteAlert();
  const isFired = alert.status === 'triggered';

  return (
    <div style={{
      ...S.row,
      borderLeftColor: alert.status === 'triggered' ? '#cc8888' : alert.status === 'active' ? '#88aaff44' : '#1e1e1e',
      borderLeftWidth: 3,
    }}>
      <div style={S.left}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={S.sym}>{alert.underlying}</span>
          <span style={{ ...S.statusChip, ...STATUS_STYLE[alert.status] }}>
            {alert.status.toUpperCase()}
          </span>
        </div>
        <span style={S.cond}>
          {CONDITION_LABELS[alert.condition]}
          {alert.threshold != null ? ` ${alert.threshold.toLocaleString()}` : ''}
          {alert.target_state ? ` ${alert.target_state}` : ''}
          {isFired && alert.trigger_value != null
            ? ` → fired at ${fmtN(alert.trigger_value, 2)}`
            : ''}
        </span>
        <div style={{ display: 'flex', gap: 12 }}>
          <span style={S.ts}>created {fmtTime(alert.created_at_ms)}</span>
          {alert.triggered_at_ms && (
            <span style={{ ...S.ts, color: '#cc888888' }}>
              triggered {fmtTime(alert.triggered_at_ms)}
            </span>
          )}
        </div>
        {alert.fire_count > 0 && (
          <span style={{ color: '#555', fontSize: 10 }}>
            Fired {alert.fire_count}×
            {alert.cooldown_hours > 0 ? ` · cooldown ${alert.cooldown_hours}h` : ''}
          </span>
        )}
        {alert.notes && <span style={{ color: '#555', fontSize: 10 }}>{alert.notes}</span>}
      </div>
      <div style={S.actions}>
        {alert.status !== 'dismissed' && (
          <button style={S.btn} onClick={() => dismiss.mutate(alert.id)} disabled={dismiss.isPending}>
            DISMISS
          </button>
        )}
        <button style={S.btnRed} onClick={() => del.mutate(alert.id)} disabled={del.isPending}>✕</button>
      </div>
    </div>
  );
}

function AddAlertForm({ onDone }: { onDone: () => void }) {
  const { data: instrumentData } = useInstruments();
  const underlyings = (instrumentData?.instruments ?? []).map(i => i.underlying);
  const [underlying, setUnderlying]       = useState('BTC');
  const [condition, setCondition]         = useState<AlertCondition>('price_above');
  const [threshold, setThreshold]         = useState('');
  const [targetState, setTargetState]     = useState('ENTRY_ARMED_PULLBACK');
  const [cooldownHours, setCooldownHours] = useState('0');
  const [notes, setNotes]                 = useState('');
  const create = useCreateAlert();

  const handleAdd = () => {
    create.mutate({
      underlying,
      condition,
      threshold:    NEEDS_THRESHOLD.has(condition) ? parseFloat(threshold) || undefined : undefined,
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
            {(underlyings.length > 0 ? underlyings : ['BTC', 'ETH', 'SOL', 'XRP']).map(u => (
              <option key={u}>{u}</option>
            ))}
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
          <label style={S.label}>COOLDOWN (h)</label>
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
      {create.error && (
        <div style={{ color: '#cc4444', fontSize: 11, marginTop: 6 }}>
          {(create.error as Error).message}
        </div>
      )}
    </div>
  );
}

export function AlertManager() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [dayFilter, setDayFilter]       = useState<DayFilter>(0);
  const [showAdd, setShowAdd]           = useState(false);

  const queryParams = new URLSearchParams();
  if (statusFilter !== 'all') queryParams.set('status', statusFilter);
  if (dayFilter > 0)          queryParams.set('days',   String(dayFilter));
  const qs = queryParams.toString() ? `?${queryParams}` : '';

  const { data, isLoading } = useAlerts(qs);
  const check     = useCheckAlerts();
  const bulkClear = useBulkClearDismissed();

  const hasDismissed = data?.alerts.some(a => a.status === 'dismissed') ?? false;

  return (
    <div style={S.card}>
      {/* Header */}
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
          <button
            style={check.isPending ? { ...S.checkBtn, opacity: 0.5 } : S.checkBtn}
            onClick={() => check.mutate()} disabled={check.isPending}
          >
            {check.isPending ? 'CHECKING…' : '⟳ CHECK NOW'}
          </button>
          {hasDismissed && statusFilter !== 'active' && (
            <button
              style={{ ...S.btn, color: '#666', borderColor: '#333' }}
              onClick={() => bulkClear.mutate()} disabled={bulkClear.isPending}
            >
              CLEAR DISMISSED
            </button>
          )}
          <button style={S.addBtn} onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? 'CANCEL' : '+ ADD'}
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div style={S.filterBar}>
        <div style={{ display: 'flex', borderBottom: '1px solid #1e1e1e' }}>
          {STATUS_TABS.map(([val, label]) => (
            <TabBtn key={val} label={label} active={statusFilter === val}
              onClick={() => setStatusFilter(val)} />
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
          {DAY_OPTIONS.map(([val, label]) => (
            <button key={val} onClick={() => setDayFilter(val)} style={{
              background: dayFilter === val ? '#1a2a1a' : 'none',
              color: dayFilter === val ? '#44cc88' : '#444',
              border: dayFilter === val ? '1px solid #44cc8844' : '1px solid #1e1e1e',
              padding: '3px 8px', borderRadius: 3, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 10,
            }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {check.data && check.data.newly_triggered > 0 && (
        <div style={S.checkResult}>
          ✓ Checked {check.data.checked} alerts — {check.data.newly_triggered} newly triggered
        </div>
      )}

      {showAdd && <AddAlertForm onDone={() => setShowAdd(false)} />}

      {isLoading ? (
        <div style={S.noData}>Loading…</div>
      ) : !data || data.alerts.length === 0 ? (
        <div style={S.noData}>
          {statusFilter === 'all' && dayFilter === 0 ? (
            <div style={{ color: '#444', fontSize: 12, padding: '20px 0', textAlign: 'center' as const }}>
              No alerts configured.<br />
              <span style={{ fontSize: 11, color: '#333' }}>
                Click <strong style={{ color: '#44cc88' }}>+ ADD</strong> to create a price, IV rank, or signal alert.
                Alerts fire webhooks even when this tab is closed.
              </span>
            </div>
          ) : (
            <div style={S.noData}>No alerts match the current filter.</div>
          )}
        </div>
      ) : (
        data.alerts.map(a => <AlertRow key={a.id} alert={a} />)
      )}
    </div>
  );
}
