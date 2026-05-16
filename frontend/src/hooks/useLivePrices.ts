/**
 * useLivePrices — module-level singleton SSE connection for spot prices.
 *
 * Subscribes to the backend's stream-all `prices` event (emitted every ~2s).
 * All component instances share one SSE connection. The connection stays open
 * as long as at least one component is mounted, and closes when all unmount.
 *
 * Returns: Record<underlying, spot_price>   — updates every ~2s.
 */
import { useEffect, useRef, useState } from 'react';

const API_BASE   = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
const STREAM_URL = `${API_BASE}/api/v1/directional/stream-all`;

// ── module-level singleton state ──────────────────────────────────────────────
type Listener = (prices: Record<string, number>) => void;

let _prices: Record<string, number> = {};
const _listeners = new Set<Listener>();
let _es: EventSource | null = null;
let _refCount = 0;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _reconnectDelay = 2_000;

function _notify() {
  const snap = { ..._prices };
  _listeners.forEach((fn) => fn(snap));
}

function _connect() {
  if (_es) return;

  const es = new EventSource(STREAM_URL);
  _es = es;

  es.addEventListener('prices', (evt: MessageEvent) => {
    try {
      const incoming = JSON.parse(evt.data) as Record<string, number>;
      let changed = false;
      for (const [sym, price] of Object.entries(incoming)) {
        if (_prices[sym] !== price) { _prices = { ..._prices, [sym]: price }; changed = true; }
      }
      if (changed) _notify();
    } catch { /* ignore */ }
    _reconnectDelay = 2_000; // reset backoff on success
  });

  es.onerror = () => {
    es.close();
    _es = null;
    if (_refCount > 0) {
      _reconnectTimer = setTimeout(() => {
        _reconnectDelay = Math.min(_reconnectDelay * 2, 30_000);
        _connect();
      }, _reconnectDelay);
    }
  };
}

function _disconnect() {
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  if (_es) { _es.close(); _es = null; }
}

// ── hook ──────────────────────────────────────────────────────────────────────
export function useLivePrices(): Record<string, number> {
  const [prices, setPrices] = useState<Record<string, number>>(() => ({ ..._prices }));
  const setPricesRef = useRef(setPrices);
  setPricesRef.current = setPrices;

  useEffect(() => {
    const listener: Listener = (p) => setPricesRef.current(p);
    _listeners.add(listener);
    _refCount++;
    _connect();

    // Immediately give the component the current snapshot
    if (Object.keys(_prices).length > 0) setPrices({ ..._prices });

    return () => {
      _listeners.delete(listener);
      _refCount--;
      if (_refCount === 0) _disconnect();
    };
  }, []);

  return prices;
}
