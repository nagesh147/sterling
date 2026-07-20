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
const STREAM_WS_PATH = '/api/v1/stream/ws';

const BASE_DELAY = 2_000;
const MAX_DELAY = 30_000;
const RECONCILE_DEBOUNCE = 250;

type BrowserLocation = Pick<Location, 'protocol' | 'host'>;

/**
 * Resolve the shared stream endpoint into the absolute ws:// or wss:// URL that
 * the browser WebSocket constructor requires.
 *
 * Production intentionally builds with VITE_API_BASE_URL="" so HTTP requests are
 * relative and nginx proxies `/api`. A relative string is valid for fetch, but it
 * is NOT valid for `new WebSocket()`. Derive the socket origin from the current
 * page in that case; keep explicit API hosts and relative proxy prefixes working.
 */
export function resolveKiteStreamWsUrl(
  apiBase: string | undefined = import.meta.env.VITE_API_BASE_URL as string | undefined,
  locationLike: BrowserLocation | undefined = typeof window !== 'undefined' ? window.location : undefined,
): string {
  const base = (apiBase ?? '').trim().replace(/\/+$/, '');
  const target = `${base}${STREAM_WS_PATH}`;

  if (/^wss?:\/\//i.test(target)) return target;

  if (/^https?:\/\//i.test(target)) {
    const url = new URL(target);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return url.toString();
  }

  if (locationLike) {
    const protocol = locationLike.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = target.startsWith('/') ? target : `/${target}`;
    return `${protocol}//${locationLike.host}${path}`;
  }

  const path = target.startsWith('/') ? target : `/${target}`;
  return `ws://localhost:8000${path}`;
}

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
const _desired = new Map<number, number>();         // token → refcount (any mode)
const _desiredFull = new Map<number, number>();     // token → refcount of FULL-mode (depth) interest
const _subscribed = new Map<number, 'quote' | 'full'>(); // token → mode currently on the server
let _reconcileTimer: ReturnType<typeof setTimeout> | null = null;

// A token streams in "full" mode (5-level depth) if ANY consumer asked for depth,
// else the lighter "quote" mode. Depth views (expanded watch row, market-data card)
// register full; everything else stays quote.
function _wantMode(tok: number): 'quote' | 'full' {
  return (_desiredFull.get(tok) ?? 0) > 0 ? 'full' : 'quote';
}

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

  // (Re)subscribe brand-new tokens, or ones whose desired mode changed — e.g. a depth
  // view opened (upgrade quote→full) or closed (downgrade full→quote).
  const toSub: number[] = [];
  for (const t of want) {
    if (_subscribed.get(t) !== _wantMode(t)) toSub.push(t);
  }
  const toRemove = [..._subscribed.keys()].filter((t) => !want.has(t));
  if (toSub.length === 0 && toRemove.length === 0) return;

  // Optimistically record intent so concurrent reconciles don't double-fire.
  const prev = new Map(_subscribed);
  toSub.forEach((t) => _subscribed.set(t, _wantMode(t)));
  toRemove.forEach((t) => _subscribed.delete(t));

  // Group by mode so each subscribe call carries a single, correct mode.
  const byMode: Record<'quote' | 'full', number[]> = { quote: [], full: [] };
  for (const t of toSub) byMode[_wantMode(t)].push(t);

  try {
    // subscribe auto-starts the ticker server-side via ensure()
    if (byMode.full.length) {
      await api.post(`${K}/ticker/subscribe`, { instrument_tokens: byMode.full, mode: 'full' });
    }
    if (byMode.quote.length) {
      await api.post(`${K}/ticker/subscribe`, { instrument_tokens: byMode.quote, mode: 'quote' });
    }
    if (toRemove.length) {
      await api.post(`${K}/ticker/unsubscribe`, { instrument_tokens: toRemove });
    }
  } catch {
    // Roll back so the next reconcile retries (e.g. account not connected yet).
    _subscribed.clear();
    for (const [t, m] of prev) _subscribed.set(t, m);
  }
}

/**
 * Register interest in a set of instrument tokens. Returns a cleanup that
 * releases them. Tokens are ref-counted across all callers so the server sees
 * exactly the displayed union, and rapid mount/unmount churn is debounced.
 */
export function registerTokens(tokens: number[], mode: 'quote' | 'full' = 'quote'): () => void {
  if (tokens.length === 0) return () => {};
  for (const t of tokens) {
    _desired.set(t, (_desired.get(t) ?? 0) + 1);
    if (mode === 'full') _desiredFull.set(t, (_desiredFull.get(t) ?? 0) + 1);
  }
  _refConnect();
  _scheduleReconcile();
  return () => {
    for (const t of tokens) {
      const n = (_desired.get(t) ?? 0) - 1;
      if (n <= 0) _desired.delete(t);
      else _desired.set(t, n);
      if (mode === 'full') {
        const f = (_desiredFull.get(t) ?? 0) - 1;
        if (f <= 0) _desiredFull.delete(t);
        else _desiredFull.set(t, f);
      }
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

function _scheduleReconnect() {
  if (_refCount <= 0 || _reconnectTimer) return;
  _reconnectTimer = setTimeout(() => {
    _reconnectTimer = null;
    _reconnectDelay = Math.min(_reconnectDelay * 2, MAX_DELAY);
    _connect();
  }, _reconnectDelay);
}

function _connect() {
  if (_ws) return;

  let ws: WebSocket;
  try {
    ws = new WebSocket(resolveKiteStreamWsUrl());
  } catch {
    // Never let an invalid/misconfigured URL throw out of a React effect. Keep the
    // REST heartbeat alive and retry after the normal reconnect backoff.
    _scheduleReconnect();
    return;
  }
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
    _scheduleReconnect();
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
