import React from 'react';
import { useCalibration } from '../hooks/useCalibration';
import { useSelectedUnderlying } from '../store/useStore';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid3: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 },
  statCard: { background: '#111', border: '1px solid #1e1e1e', borderRadius: 4, padding: 10 },
  statLabel: { color: '#555', fontSize: 10, letterSpacing: 1, marginBottom: 4 },
  statVal: { fontSize: 16, fontWeight: 700, color: '#e0e0e0' },
  note: { color: '#333', fontSize: 10, marginTop: 8, fontStyle: 'italic' },
};

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={S.statCard}>
      <div style={S.statLabel}>{label}</div>
      <div style={S.statVal}>{value}</div>
      {sub && <div style={{ color: '#444', fontSize: 9, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function CalibrationPanel() {
  const underlying = useSelectedUnderlying();
  const { data, isLoading } = useCalibration(underlying);

  if (isLoading) return <div style={{ color: '#444', fontSize: 11 }}>Loading calibration…</div>;
  if (!data) return null;

  const confidence = data.trade_count >= 10 ? 'adaptive' : `fallback (${data.trade_count}/10 trades)`;

  return (
    <div style={S.card}>
      <div style={S.title}>ADAPTIVE CALIBRATION — {underlying}</div>
      <div style={S.grid3}>
        <Stat
          label="WIN RATE"
          value={`${(data.win_rate * 100).toFixed(1)}%`}
          sub={confidence}
        />
        <Stat
          label="IVR BUY THRESHOLD"
          value={data.ivr_buy_threshold.toFixed(1)}
          sub={data.ivr_readings >= 20 ? 'adaptive' : `fallback (${data.ivr_readings}/20 readings)`}
        />
        <Stat
          label="IVR SELL THRESHOLD"
          value={data.ivr_sell_threshold.toFixed(1)}
          sub={data.ivr_readings >= 20 ? 'adaptive' : ''}
        />
      </div>
      {data.note && <div style={S.note}>{data.note}</div>}
    </div>
  );
}
