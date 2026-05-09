import React from 'react';
import { useGreeksBudget } from '../hooks/useGreeksBudget';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  row: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  label: { color: '#666', fontSize: 11, width: 80 },
};

function Gauge({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, (Math.abs(value) / Math.abs(max)) * 100) : 0;
  const color = pct > 90 ? '#cc4444' : pct > 70 ? '#f0c040' : '#44cc88';
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ color: '#666', fontSize: 11 }}>{label}</span>
        <span style={{ color, fontSize: 11 }}>{(value * 100).toFixed(2)}% / {(max * 100).toFixed(0)}%</span>
      </div>
      <div style={{ height: 6, background: '#1e1e1e', borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
    </div>
  );
}

export function GreeksBudgetGauge() {
  const { data, isLoading } = useGreeksBudget();

  if (isLoading) return null;
  if (!data) return null;

  const withinColor = data.within_limits ? '#44cc88' : '#cc4444';

  return (
    <div style={S.card}>
      <div style={{ ...S.title, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>GREEKS BUDGET</span>
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 3,
          background: `${withinColor}22`, color: withinColor, border: `1px solid ${withinColor}44`,
        }}>
          {data.within_limits ? 'WITHIN LIMITS' : 'BUDGET BREACH'}
        </span>
      </div>
      <Gauge label="Net Delta" value={data.net_delta} max={data.budget.max_net_delta} />
      <Gauge label="Net Vega" value={data.net_vega} max={data.budget.max_net_vega} />
      <div style={{ color: '#444', fontSize: 10, marginTop: 4 }}>
        {data.open_positions} open position{data.open_positions !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
