import { useEffect, useRef, useState, useCallback } from 'react';

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

const BASE_DELAY_MS = 2_000;
const MAX_DELAY_MS = 30_000;

export function useSignalStream(underlying: string, intervalSec = 30) {
  const [data, setData] = useState<StreamPayload | null>(null);
  const [status, setStatus] = useState<StreamStatus>('disconnected');
  const esRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef = useRef(BASE_DELAY_MS);
  const activeRef = useRef(true); // tracks whether effect is still mounted

  const connect = useCallback(() => {
    if (!underlying || !activeRef.current) return;

    // Close existing connection cleanly
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const base = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
    const url = `${base}/api/v1/directional/stream/${underlying}?interval=${intervalSec}`;

    setStatus('connecting');
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (!activeRef.current) return;
      setStatus('connected');
      delayRef.current = BASE_DELAY_MS; // reset backoff on success
    };

    es.onmessage = (e) => {
      if (!activeRef.current) return;
      try {
        const payload = JSON.parse(e.data) as StreamPayload;
        setData(payload);
        setStatus('connected');
      } catch { /* ignore parse errors */ }
    };

    es.onerror = () => {
      if (!activeRef.current) return;
      setStatus('disconnected');
      es.close();
      esRef.current = null;

      // Exponential backoff reconnect
      const delay = delayRef.current;
      delayRef.current = Math.min(delay * 2, MAX_DELAY_MS);
      reconnectRef.current = setTimeout(() => {
        if (activeRef.current) connect();
      }, delay);
    };
  }, [underlying, intervalSec]);

  useEffect(() => {
    activeRef.current = true;
    connect();

    return () => {
      activeRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setStatus('disconnected');
    };
  }, [connect]);

  return { data, status };
}
