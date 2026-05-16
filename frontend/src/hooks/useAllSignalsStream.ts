import { useCallback, useEffect, useRef, useState } from 'react';
import type { SignalItem, SignalsResponse } from './useSignals';

export type StreamStatus = 'connecting' | 'connected' | 'disconnected';

const BASE_DELAY_MS = 2_000;
const MAX_DELAY_MS  = 30_000;

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
const STREAM_URL = `${API_BASE}/api/v1/directional/stream-all`;

/**
 * useAllSignalsStream — Bloomberg-style single SSE connection for all instruments.
 *
 * Listens for two named SSE event types:
 *   - "prices"  (every ~2s): merges spot prices into the current signals array
 *   - "signals" (every ~30s): replaces the full signals array
 *
 * Returns the same shape as useSignals() so it is a drop-in replacement:
 *   { data: SignalsResponse | null, status: StreamStatus }
 *
 * Uses exponential backoff reconnect (2s → 30s) matching useSignalStream.ts.
 * Completely self-contained — no shared global state.
 */
export function useAllSignalsStream(): { data: SignalsResponse | null; status: StreamStatus } {
  const [data, setData]     = useState<SignalsResponse | null>(null);
  const [status, setStatus] = useState<StreamStatus>('disconnected');

  const esRef          = useRef<EventSource | null>(null);
  const reconnectRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const delayRef       = useRef(BASE_DELAY_MS);
  const activeRef      = useRef(true);
  // Keep a live ref to the latest signals so the prices handler can merge into them
  const dataRef        = useRef<SignalsResponse | null>(null);

  const connect = useCallback(() => {
    if (!activeRef.current) return;

    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    setStatus('connecting');
    const es = new EventSource(STREAM_URL);
    esRef.current = es;

    es.onopen = () => {
      if (!activeRef.current) return;
      setStatus('connected');
      delayRef.current = BASE_DELAY_MS; // reset backoff on success
    };

    // "prices" event: partial update — merge spot prices into existing signals
    es.addEventListener('prices', (e: MessageEvent) => {
      if (!activeRef.current) return;
      setStatus('connected');
      try {
        const prices = JSON.parse(e.data) as Record<string, number>;
        setData(prev => {
          if (!prev) return prev;
          const now = Date.now();
          let changed = false;
          const updated = prev.signals.map(sig => {
            const newPrice = prices[sig.underlying];
            if (newPrice == null || newPrice === sig.spot_price) return sig;
            changed = true;
            return { ...sig, spot_price: newPrice };
          });
          if (!changed) return prev;
          const next: SignalsResponse = {
            ...prev,
            signals: updated,
            timestamp_ms: now,
          };
          dataRef.current = next;
          return next;
        });
      } catch { /* ignore parse errors */ }
    });

    // "signals" event: full replacement
    es.addEventListener('signals', (e: MessageEvent) => {
      if (!activeRef.current) return;
      setStatus('connected');
      try {
        const payload = JSON.parse(e.data) as { signals: SignalItem[]; timestamp_ms: number };
        const next: SignalsResponse = {
          signals: payload.signals,
          count:   payload.signals.length,
          timestamp_ms: payload.timestamp_ms,
        };
        dataRef.current = next;
        setData(next);
      } catch { /* ignore parse errors */ }
    });

    // Fallback: unnamed messages (should not occur with stream-all but defensive)
    es.onmessage = () => {
      if (!activeRef.current) return;
      setStatus('connected');
    };

    es.onerror = () => {
      if (!activeRef.current) return;
      setStatus('disconnected');
      es.close();
      esRef.current = null;

      // Exponential backoff
      const delay = delayRef.current;
      delayRef.current = Math.min(delay * 2, MAX_DELAY_MS);
      reconnectRef.current = setTimeout(() => {
        if (activeRef.current) connect();
      }, delay);
    };
  }, []); // no deps — STREAM_URL is module-level constant

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
