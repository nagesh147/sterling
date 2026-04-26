import { useEffect, useRef, useState } from 'react';

export interface AlertFired {
  id: string;
  condition: string;
  message: string;
}

export interface StreamPayload {
  underlying: string;
  state: string;
  direction: string;
  macro_regime: string;
  signal_trend: number;
  all_green: boolean;
  all_red: boolean;
  green_arrow: boolean;
  red_arrow: boolean;
  st_trends: number[];
  score_long: number;
  score_short: number;
  ivr?: number;
  spot_price: number;
  timestamp_ms: number;
  alert_fired?: AlertFired;
  error?: string;
}

export type StreamStatus = 'connecting' | 'connected' | 'disconnected';

export function useSignalStream(underlying: string, intervalSec = 30) {
  const [data, setData] = useState<StreamPayload | null>(null);
  const [status, setStatus] = useState<StreamStatus>('disconnected');
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!underlying) return;

    const base = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
    const url = `${base}/api/v1/directional/stream/${underlying}?interval=${intervalSec}`;

    setStatus('connecting');
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setStatus('connected');

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data) as StreamPayload;
        setData(payload);
        setStatus('connected');
      } catch {
        // ignore parse error
      }
    };

    es.onerror = () => {
      setStatus('disconnected');
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
      setStatus('disconnected');
    };
  }, [underlying, intervalSec]);

  return { data, status };
}
