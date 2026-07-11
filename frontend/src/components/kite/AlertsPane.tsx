import React, { useState } from 'react';
import { useKiteAlerts, useKiteAlertHistory } from '../../hooks/useKite';
import type { KiteAlert } from '../../types/kite';
import { CreateAlertModal } from './CreateAlertModal';

const S: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 16px', borderBottom: '1px solid #f1f1f1' },
  title: { fontSize: 16, color: '#444', fontWeight: 400 },
  actions: { display: 'flex', gap: 12, alignItems: 'center' },
  primaryBtn: { background: '#387ed1', color: 'white', padding: '8px 16px', borderRadius: 3, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 },
  searchInputWrapper: { position: 'relative', display: 'flex', alignItems: 'center' },
  searchInput: { border: '1px solid #e0e0e0', borderRadius: 3, padding: '8px 12px 8px 30px', fontSize: 13, color: '#444', outline: 'none', width: 200 },
  searchIcon: { position: 'absolute', left: 10, color: '#9b9b9b' },
  th: { textAlign: 'left', color: '#9b9b9b', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: '1px solid #f1f1f1' },
  td: { padding: '12px 16px', fontSize: 13, color: '#444', borderBottom: '1px solid #f1f1f1', verticalAlign: 'top' },
  pill: { padding: '2px 6px', borderRadius: 3, fontSize: 10, fontWeight: 500, display: 'inline-block' },
};

function Pill({ type, children }: { type: 'disabled' | 'enabled' | 'simple' | 'ato'; children: React.ReactNode }) {
  const styles = {
    disabled: { color: '#e53935', background: 'rgba(229, 57, 53, 0.1)' },
    enabled: { color: '#4caf50', background: 'rgba(76, 175, 80, 0.1)' },
    simple: { color: '#9c27b0', background: 'rgba(156, 39, 176, 0.1)' },
    ato: { color: '#ff9800', background: 'rgba(255, 152, 0, 0.1)' },
  };
  return <span style={{ ...S.pill, ...styles[type] }}>{children}</span>;
}

function TriggeredCount({ uuid }: { uuid: string }) {
  const { data: history } = useKiteAlertHistory(uuid);
  return <>{history?.length ?? 0}</>;
}

export function AlertsPane() {
  const { data: allAlerts } = useKiteAlerts(true);
  const [query, setQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const alerts = query.trim()
    ? allAlerts?.filter((a) => a.name?.toLowerCase().includes(query.trim().toLowerCase()))
    : allAlerts;

  return (
    <div style={{ background: '#fff', height: '100%', padding: '24px 32px' }}>
      <div style={S.header}>
        <div style={S.title}>Alerts ({alerts?.length || 0})</div>
        <div style={S.actions}>
          <button style={S.primaryBtn} onClick={() => setCreateOpen(true)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            New alert
          </button>
          <div style={S.searchInputWrapper}>
            <svg style={S.searchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input style={S.searchInput} placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>
      </div>
      
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          <th style={{ ...S.th, width: 40 }}><input type="checkbox" style={{ cursor: 'pointer' }} /></th>
          <th style={S.th}>Name</th>
          <th style={S.th}>Status</th>
          <th style={S.th}>Type</th>
          <th style={S.th}>Triggered</th>
          <th style={S.th}>Created on</th>
        </tr></thead>
        <tbody>
          {(!alerts || alerts.length === 0) && (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', padding: '60px 20px', color: '#9b9b9b', fontSize: 14 }}>
                No alerts found.
              </td>
            </tr>
          )}
          {alerts && alerts.map((a: KiteAlert) => {
            const enabled = (a.status || '').toLowerCase() === 'enabled';
            const cond = `${a.lhs_tradingsymbol ?? ''} ${a.lhs_attribute ?? ''} ${a.operator ?? ''} ${a.rhs_constant ?? ''}`.trim();
            const isAto = (a as any).alert_type === 'ato';
            
            return (
              <tr key={a.uuid} style={{ transition: 'background 0.2s', cursor: 'default' }}>
                <td style={{ ...S.td, width: 40 }}><input type="checkbox" style={{ cursor: 'pointer' }} /></td>
                <td style={S.td}>
                  <div style={{ color: '#444', fontWeight: 400, marginBottom: 4 }}>{a.name}</div>
                  <div style={{ color: '#9b9b9b', fontSize: 11 }}>Last price of {cond}</div>
                </td>
                <td style={S.td}>
                  <Pill type={enabled ? 'enabled' : 'disabled'}>{a.status?.toUpperCase() || 'UNKNOWN'}</Pill>
                </td>
                <td style={S.td}>
                  <Pill type={isAto ? 'ato' : 'simple'}>{isAto ? 'ATO' : 'SIMPLE'}</Pill>
                </td>
                <td style={{ ...S.td, color: '#387ed1' }}>
                  {expandedId === a.uuid ? (
                    <TriggeredCount uuid={a.uuid} />
                  ) : (
                    <span onClick={() => setExpandedId(a.uuid)} style={{ cursor: 'pointer', textDecoration: 'underline' }}>Show</span>
                  )}
                </td>
                <td style={S.td}>{a.created_at ? new Date(a.created_at as string).toISOString().split('T')[0] : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {createOpen && <CreateAlertModal onClose={() => setCreateOpen(false)} />}
    </div>
  );
}
