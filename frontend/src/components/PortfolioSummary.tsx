import React from 'react';
import { usePortfolioSummary } from '../hooks/usePortfolioSummary';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 16, fontWeight: 700, color: '#e0e0e0' },
  footer: { display: 'flex', gap: 12, alignItems: 'center', marginTop: 6 },
  monitorBtn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff',
    padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  alertBadge: {
    background: '#cc4444' + '22', color: '#cc4444',
    border: '1px solid #cc4444', padding: '3px 8px', borderRadius: 3, fontSize: 11,
  },
};

interface MonitorResult { exit_recommended: string[]; partial_recommended: string[] }

export function PortfolioSummary() {
  const { data } = usePortfolioSummary();
  const qc = useQueryClient();
  const monitor = useMutation<MonitorResult, Error, void>({
    mutationFn: () => api.post<MonitorResult>('/api/v1/positions/monitor-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });

  if (!data) return null;

  const pnlColor = data.total_realized_pnl_usd >= 0 ? '#44cc88' : '#cc4444';
  const pnlSign = data.total_realized_pnl_usd >= 0 ? '+' : '';

  return (
    <div style={styles.card}>
      <div style={styles.title}>PORTFOLIO SUMMARY</div>
      <div style={styles.grid}>
        <div style={styles.cell}>
          <span style={styles.key}>OPEN POSITIONS</span>
          <span style={{ ...styles.val, color: data.open_count > 0 ? '#f0c040' : '#555' }}>
            {data.open_count}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>TOTAL OPEN RISK</span>
          <span style={{ ...styles.val, color: '#ff8844' }}>
            ${data.total_open_risk_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>REALIZED P&L</span>
          <span style={{ ...styles.val, color: pnlColor }}>
            {pnlSign}${data.total_realized_pnl_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>AVG RISK %</span>
          <span style={styles.val}>{data.avg_capital_at_risk_pct.toFixed(2)}%</span>
        </div>
      </div>

      <div style={styles.footer}>
        <button
          style={monitor.isPending ? { ...styles.monitorBtn, opacity: 0.5 } : styles.monitorBtn}
          onClick={() => monitor.mutate()}
          disabled={monitor.isPending || data.open_count === 0}
        >
          {monitor.isPending ? 'CHECKING…' : '⟳ MONITOR ALL'}
        </button>

        {monitor.data && monitor.data.exit_recommended.length > 0 && (
          <span style={styles.alertBadge}>
            EXIT: {monitor.data.exit_recommended.join(', ')}
          </span>
        )}
        {monitor.data && monitor.data.partial_recommended.length > 0 && (
          <span style={{ ...styles.alertBadge, color: '#f0c040', borderColor: '#f0c040', background: '#f0c040' + '22' }}>
            PARTIAL: {monitor.data.partial_recommended.join(', ')}
          </span>
        )}
        {data.underlyings_open.length > 0 && (
          <span style={{ color: '#444', fontSize: 11 }}>
            Open in: {data.underlyings_open.join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}
