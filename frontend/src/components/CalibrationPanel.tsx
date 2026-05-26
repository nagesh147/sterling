import React from 'react';
import { useCalibration } from '../hooks/useCalibration';
import { useSelectedUnderlying } from '../store/useStore';
import { grpBox, gridStyle } from '../styles/terminalUI';

export function CalibrationPanel() {
  const underlying = useSelectedUnderlying();
  const { data, isLoading } = useCalibration(underlying);

  if (isLoading) return <div style={{ color: 'var(--t-dim)', fontSize: 11 }}>Loading calibration…</div>;
  if (!data) return null;

  const confidence = data.trade_count >= 10 ? 'adaptive' : `fallback (${data.trade_count}/10 trades)`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-dim)' }}>
        ADAPTIVE CALIBRATION — {underlying}
      </div>
      <div style={gridStyle(150, 8)}>
        <div style={grpBox}>
          <div style={{ fontSize: 9, letterSpacing: '0.08em', color: 'var(--t-dim)', fontWeight: 600, marginBottom: 4 }}>WIN RATE</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--t-bright)' }}>{(data.win_rate * 100).toFixed(1)}%</div>
          <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 2 }}>{confidence}</div>
        </div>
        <div style={grpBox}>
          <div style={{ fontSize: 9, letterSpacing: '0.08em', color: 'var(--t-dim)', fontWeight: 600, marginBottom: 4 }}>IVR BUY</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--t-bright)' }}>{data.ivr_buy_threshold.toFixed(1)}</div>
          <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 2 }}>{data.ivr_readings >= 20 ? 'adaptive' : `fallback (${data.ivr_readings}/20)`}</div>
        </div>
        <div style={grpBox}>
          <div style={{ fontSize: 9, letterSpacing: '0.08em', color: 'var(--t-dim)', fontWeight: 600, marginBottom: 4 }}>IVR SELL</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--t-bright)' }}>{data.ivr_sell_threshold.toFixed(1)}</div>
          <div style={{ fontSize: 9, color: 'var(--t-dim)', marginTop: 2 }}>{data.ivr_readings >= 20 ? 'adaptive' : ''}</div>
        </div>
      </div>
      {data.note && <div style={{ fontSize: 10, color: 'var(--t-dim)', fontStyle: 'italic' }}>{data.note}</div>}
    </div>
  );
}