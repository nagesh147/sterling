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
      setNotif({
        type: data.green_arrow ? 'arrow_green' : 'arrow_red',
        underlying,
        spot: data.spot_price ?? 0,
        message: data.green_arrow ? '▲ BULLISH ARROW' : '▼ BEARISH ARROW',
        ts: data.timestamp_ms,
      });
      const t = setTimeout(() => setNotif(null), 12_000);
      return () => clearTimeout(t);
    }
  }, [data?.timestamp_ms, data?.green_arrow, data?.red_arrow, data?.alert_fired]);

  if (!notif) return null;

  const isGreen = notif.type === 'arrow_green';
  const isAlert = notif.type === 'alert';
  const color = isGreen ? '#44cc88' : isAlert ? '#f0a500' : '#cc4444';
  const bg = isGreen ? '#0d1f0d' : isAlert ? '#1f1500' : '#1f0d0d';

  return (
    <div style={{
      position: 'fixed', top: 80, right: 20, zIndex: 9999,
      background: bg, border: `1px solid ${color}`,
      borderRadius: 8, padding: '14px 20px 14px 16px',
      minWidth: 280, maxWidth: 360,
      boxShadow: `0 4px 24px ${color}44`,
    }}>
      <div style={{ fontSize: 16, fontWeight: 800, color, letterSpacing: 1 }}>
        {isAlert ? '🔔 ALERT TRIGGERED' : notif.message}
      </div>
      <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>
        {underlying} · ${(notif.spot ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
      </div>
      <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
        {isAlert ? notif.message : 'Setup activation — confirm before entry'}
      </div>
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
