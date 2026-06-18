/**
 * useKiteLiveTicks — module-level singleton consuming the Kite tick WebSocket.
 *
 * The backend already runs one KiteTicker per user and fans decoded ticks out to
 * the `kite_ticks:{userId}` channel over the shared `/api/v1/stream/ws` socket
 * (see services/exchanges/kite/ticker_manager.py). This module:
 *
 *   1. Opens ONE WebSocket and subscribes that channel.
 *   2. Keeps a `token → tick` map, notifying React subscribers on each frame.
 *   3. Reconciles a ref-counted union of "tokens someone wants" against the
 *      server-side subscription via POST /ticker/{subscribe,unsubscribe}.
 *
 * Price hooks (useKiteLtp / useKiteQuote) read from here and overlay live ticks
 * on a slow REST heartbeat — replacing the old 5s/15s polling loops. Mirrors the
 * connection/reconnect pattern of useAppStream + useKiteOrderUpdates.
 */
import { useSyncExternalStore } from 'react';
import { api } from '../utils/api';

const K = '/api/v1/kite';

// Same channel user-id the order-update consumer uses (single-tenant local).
const USER_ID = 'default';

const STREAM_WS_URL =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000')
    .replace(/^http/, 'ws') + '/api/v1/stream/ws';

const BASE_DELAY = 2_000;
const MAX_DELAY = 30_000;
const RECONCILE_DEBOUNCE = 250;

export interface KiteTick {
  instrument_token: number;
  last_price?: number;
  change?: number;
  ohlc?: { open?: number; high?: number; low?: number; close?: number };
  oi?: number;
  // full mode only — quote-mode ticks omit these; REST fallback supplies them
  depth?: unknown;
  [k: string]: unknown;
}

// ── tick store ──────────────────────────────────────────────────────────────
const _tickByToken = new Map<number, KiteTick>();
let _version = 0;                                   // bumps on every tick batch
const _storeListeners = new Set<() => void>();
let _notifyScheduled = false;

// Coalesce re-renders: the tick map updates immediately (getTick is always
// current), but listeners are flushed at most ~5×/sec so a burst of frames from
// Kite can't trigger a render storm across every consumer pane.
function _notify() {
  _version += 1;
  if (_notifyScheduled) return;
  _notifyScheduled = true;
  setTimeout(() => {
    _notifyScheduled = false;
    _storeListeners.forEach((fn) => fn());
  }, 200);
}

export function getTick(token: number): KiteTick | undefined {
  return _tickByToken.get(token);
}

// ── subscription reconciler (ref-counted union) ───────────────────────────────
const _desired = new Map<number, number>();         // token → refcount
const _subscribed = new Set<number>();              // tokens sent to the server
let _reconcileTimer: ReturnType<typeof setTimeout> | null = null;

function _scheduleReconcile() {
  if (_reconcileTimer) return;
  _reconcileTimer = setTimeout(() => {
    _reconcileTimer = null;
    void _reconcile();
  }, RECONCILE_DEBOUNCE);
}

async function _reconcile() {
  const want = new Set<number>();
  for (const [tok, n] of _desired) if (n > 0) want.add(tok);

  const toAdd = [...want].filter((t) => !_subscribed.has(t));
  const toRemove = [..._subscribed].filter((t) => !want.has(t));
  if (toAdd.length === 0 && toRemove.length === 0) return;

  // Optimistically record intent so concurrent reconciles don't double-fire.
  toAdd.forEach((t) => _subscribed.add(t));
  toRemove.forEach((t) => _subscribed.delete(t));

  try {
    if (toAdd.length) {
      // subscribe auto-starts the ticker server-side via ensure()
      await api.post(`${K}/ticker/subscribe`, { instrument_tokens: toAdd, mode: 'quote' });
    }
    if (toRemove.length) {
      await api.post(`${K}/ticker/unsubscribe`, { instrument_tokens: toRemove });
    }
  } catch {
    // Roll back so the next reconcile retries (e.g. account not connected yet).
    toAdd.forEach((t) => _subscribed.delete(t));
  }
}

/**
 * Register interest in a set of instrument tokens. Returns a cleanup that
 * releases them. Tokens are ref-counted across all callers so the server sees
 * exactly the displayed union, and rapid mount/unmount churn is debounced.
 */
export function registerTokens(tokens: number[]): () => void {
  if (tokens.length === 0) return () => {};
  for (const t of tokens) _desired.set(t, (_desired.get(t) ?? 0) + 1);
  _refConnect();
  _scheduleReconcile();
  return () => {
    for (const t of tokens) {
      const n = (_desired.get(t) ?? 0) - 1;
      if (n <= 0) _desired.delete(t);
      else _desired.set(t, n);
    }
    _refDisconnect();
    _scheduleReconcile();
  };
}

// ── WebSocket lifecycle (connect while any tokens are registered) ─────────────
let _ws: WebSocket | null = null;
let _refCount = 0;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _reconnectDelay = BASE_DELAY;

function _connect() {
  if (_ws) return;
  const ws = new WebSocket(STREAM_WS_URL);
  _ws = ws;

  ws.onopen = () => {
    _reconnectDelay = BASE_DELAY;
    ws.send(JSON.stringify({ action: 'subscribe', channel: `kite_ticks:${USER_ID}` }));
    // The server ticker may have restarted while we were away — re-assert the
    // full desired set (subscribe is idempotent).
    _subscribed.clear();
    _scheduleReconcile();
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type !== 'kite_ticks' || !Array.isArray(msg.ticks)) return;
      for (const t of msg.ticks as KiteTick[]) {
        if (typeof t?.instrument_token === 'number') _tickByToken.set(t.instrument_token, t);
      }
      _notify();
    } catch {
      /* ignore non-JSON / unrelated frames */
    }
  };

  ws.onclose = () => {
    _ws = null;
    if (_refCount > 0) {
      _reconnectTimer = setTimeout(() => {
        _reconnectDelay = Math.min(_reconnectDelay * 2, MAX_DELAY);
        _connect();
      }, _reconnectDelay);
    }
  };

  ws.onerror = () => ws.close();
}

function _disconnect() {
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  if (_ws) { _ws.close(); _ws = null; }
}

function _refConnect() {
  _refCount += 1;
  _connect();
}

function _refDisconnect() {
  _refCount = Math.max(0, _refCount - 1);
  if (_refCount === 0) _disconnect();
}

// ── React read hook ───────────────────────────────────────────────────────────
function _subscribeStore(cb: () => void): () => void {
  _storeListeners.add(cb);
  return () => { _storeListeners.delete(cb); };
}
function _getVersion(): number {
  return _version;
}

/** Re-renders the caller on every tick batch. Read values via getTick(token). */
export function useTickVersion(): number {
  return useSyncExternalStore(_subscribeStore, _getVersion, _getVersion);
}
