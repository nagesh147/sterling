import React, { useEffect, useRef, useState } from 'react';
import { useSignalStream } from '../hooks/useSignalStream';
import { useQueryClient } from '@tanstack/react-query';

type NotifType = 'arrow_green' | 'arrow_red' | 'alert';

interface Notification {
  type: NotifType;
  underlying: string;
  spot: number;
  message: string;
  ts: number;
}

interface Props { underlying: string }

export function ArrowAlert({ underlying }: Props) {
  const { data } = useSignalStream(underlying, 30);
  const [notif, setNotif] = useState<Notification | null>(null);
  const lastTs = useRef<number>(0);
  const qc = useQueryClient();

  useEffect(() => {
    if (!data || data.timestamp_ms === lastTs.current) return;
    lastTs.current = data.timestamp_ms;

    if (data.alert_fired) {
      setNotif({
        type: 'alert',
        underlying,
        spot: data.spot_price ?? 0,
        message: data.alert_fired.message,
        ts: data.timestamp_ms,
      });
      qc.invalidateQueries({ queryKey: ['alerts'] });
      const t = setTimeout(() => setNotif(null), 14_000);
      return () => clearTimeout(t);
    }

    if (data.green_arrow || data.red_arrow) {
      const isGreen = data.green_arrow;
      setNotif({
        type: isGreen ? 'arrow_green' : 'arrow_red',
        underlying,
        spot: data.spot_price ?? 0,
        message: isGreen ? '▲ Bullish signal' : '▼ Bearish signal',
        ts: data.timestamp_ms,
      });
      // Refresh arrow history + snapshot so UI reflects new state immediately
      qc.invalidateQueries({ queryKey: ['arrows', underlying] });
      qc.invalidateQueries({ queryKey: ['arrows-all'] });
      qc.invalidateQueries({ queryKey: ['session-stats'] });
      qc.invalidateQueries({ queryKey: ['snapshot', underlying] });
      const t = setTimeout(() => setNotif(null), 12_000);
      return () => clearTimeout(t);
    }
  }, [data?.timestamp_ms, data?.green_arrow, data?.red_arrow, data?.alert_fired, underlying]);

  if (!notif) return null;

  const isGreen = notif.type === 'arrow_green';
  const isAlert = notif.type === 'alert';
  const color = isGreen ? '#44cc88' : isAlert ? '#f0a500' : '#cc4444';
  const bg    = isGreen ? '#0d1f0d' : isAlert ? '#1f1500' : '#1f0d0d';
  const ivr   = data?.ivr;
  const state = data?.state;

  return (
    <div style={{
      position: 'fixed', top: 80, right: 20, zIndex: 9999,
      background: bg, border: `1px solid ${color}`,
      borderRadius: 8, padding: '14px 20px 14px 16px',
      minWidth: 300, maxWidth: 380,
      boxShadow: `0 4px 24px ${color}44`,
    }}>
      <div style={{ fontSize: 15, fontWeight: 800, color, letterSpacing: 0.5 }}>
        {isAlert ? '🔔 Alert triggered' : notif.message}
      </div>
      <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>
        {underlying} · ${(notif.spot ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
        {ivr != null && <span style={{ color: ivr > 60 ? '#f0a500' : '#666', marginLeft: 8 }}>IV Rank {ivr.toFixed(0)}</span>}
      </div>
      {!isAlert && state && (
        <div style={{ fontSize: 11, color: '#555', marginTop: 3 }}>
          {ivr != null && ivr > 60
            ? 'High IV — consider defined-risk spread over naked long premium'
            : 'Setup activation — confirm before entry'}
        </div>
      )}
      {isAlert && (
        <div style={{ fontSize: 11, color: '#888', marginTop: 3 }}>{notif.message}</div>
      )}
      <button
        onClick={() => setNotif(null)}
        style={{
          position: 'absolute', top: 6, right: 10,
          background: 'none', border: 'none', color: '#555',
          cursor: 'pointer', fontSize: 18, lineHeight: 1,
        }}
      >×</button>
    </div>
  );
}
