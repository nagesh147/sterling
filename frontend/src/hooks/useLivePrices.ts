/**
 * useLivePrices — module-level singleton SSE connection for spot prices.
 *
 * Subscribes to the backend's stream-all `prices` event (emitted every ~2s).
 * All component instances share one SSE connection.
 *
 * Staleness detection: if no new price value has been received for a symbol
 * within STALE_MS, that symbol is dropped from the returned map so callers
 * can fall back to their polling source (e.g. watchlist spot_price).
 */
import { useEffect, useRef, useState } from 'react';

const API_BASE   = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
const STREAM_URL = `${API_BASE}/api/v1/directional/stream-all`;

// A symbol is considered stale if no SSE price event arrived for it in 30s.
// Staleness is based on RECEIPT time (when the event arrived), not change time.
// This means a stable price (same value for >30s) is still shown from SSE —
// it only falls back to the watchlist when the SSE stream itself stops delivering.
const STALE_MS = 30_000;

// ── module-level singleton state ──────────────────────────────────────────────
type Listener = (prices: Record<string, number>) => void;

let _prices: Record<string, number> = {};
// When each symbol last arrived in a prices event (regardless of value)
let _priceReceivedAt: Record<string, number> = {};
const _listeners = new Set<Listener>();
let _es: EventSource | null = null;
let _refCount = 0;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _reconnectDelay = 2_000;

function _freshPrices(): Record<string, number> {
  const now = Date.now();
  const result: Record<string, number> = {};
  for (const [sym, price] of Object.entries(_prices)) {
    if (now - (_priceReceivedAt[sym] ?? 0) < STALE_MS) {
      result[sym] = price;
    }
  }
  return result;
}

function _notify() {
  const snap = _freshPrices();
  _listeners.forEach((fn) => fn(snap));
}

function _connect() {
  if (_es) return;

  const es = new EventSource(STREAM_URL);
  _es = es;

  es.addEventListener('prices', (evt: MessageEvent) => {
    try {
      const incoming = JSON.parse(evt.data) as Record<string, number>;
      const now = Date.now();
      let changed = false;
      for (const [sym, price] of Object.entries(incoming)) {
        _priceReceivedAt[sym] = now;          // always update receipt time
        if (_prices[sym] !== price) {
          _prices = { ..._prices, [sym]: price };
          changed = true;
        }
      }
      // Notify on every tick so the staleness window resets even when
      // the price value is unchanged (stable market, WS still live).
      if (changed || Object.keys(incoming).length > 0) _notify();
    } catch { /* ignore */ }
    _reconnectDelay = 2_000;
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

    if (Object.keys(_prices).length > 0) setPrices({ ..._prices });

    return () => {
      _listeners.delete(listener);
      _refCount--;
      if (_refCount === 0) _disconnect();
    };
  }, []);

  return prices;
}
