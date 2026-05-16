/**
 * useAppStream — module-level singleton SSE connection for ALL app data.
 *
 * Replaces the duplicate SSE connections in useLivePrices and useAllSignalsStream.
 * All components share one EventSource to /api/v1/directional/stream-all.
 *
 * Event types emitted by the backend:
 *   prices    (~1s)   Record<string, number>
 *   signals   (30s)   { signals: SignalItem[]; timestamp_ms: number }
 *   watchlist (10s)   WatchlistResponse
 *   positions (5s)    PositionListResponse
 *   pnl       (5s)    LivePnlResponse
 *   portfolio (10s)   PortfolioSummary
 *   alerts    (15s)   SignalAlertsResponse
 */
import { useEffect, useRef, useState } from 'react';

export type AppStreamEvent =
  | 'prices'
  | 'signals'
  | 'watchlist'
  | 'positions'
  | 'pnl'
  | 'portfolio'
  | 'alerts';

export type StreamStatus = 'connecting' | 'connected' | 'disconnected';

type Listener<T> = (data: T) => void;

const API_BASE   = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';
const STREAM_URL = `${API_BASE}/api/v1/directional/stream-all`;

const BASE_DELAY = 2_000;
const MAX_DELAY  = 30_000;

// ── module-level singleton state ──────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _listeners: Map<AppStreamEvent, Set<Listener<any>>> = new Map();
const _latest:    Map<AppStreamEvent, unknown> = new Map();
const _statusListeners = new Set<Listener<StreamStatus>>();

let _es:             EventSource | null = null;
let _refCount        = 0;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _reconnectDelay  = BASE_DELAY;
let _status: StreamStatus = 'disconnected';

function _setStatus(s: StreamStatus) {
  if (_status === s) return;
  _status = s;
  _statusListeners.forEach(fn => fn(s));
}

function _getListeners<T>(event: AppStreamEvent): Set<Listener<T>> {
  if (!_listeners.has(event)) _listeners.set(event, new Set());
  return _listeners.get(event) as Set<Listener<T>>;
}

function _emit(event: AppStreamEvent, raw: string) {
  try {
    const data = JSON.parse(raw);
    _latest.set(event, data);
    _getListeners(event).forEach(fn => fn(data));
  } catch { /* ignore parse errors */ }
}

function _connect() {
  if (_es) return;
  _setStatus('connecting');

  const es = new EventSource(STREAM_URL);
  _es = es;

  es.onopen = () => {
    _setStatus('connected');
    _reconnectDelay = BASE_DELAY;
  };

  const events: AppStreamEvent[] = ['prices', 'signals', 'watchlist', 'positions', 'pnl', 'portfolio', 'alerts'];
  events.forEach(evt => {
    es.addEventListener(evt, (e: MessageEvent) => {
      _setStatus('connected');
      _emit(evt, e.data);
    });
  });

  es.onerror = () => {
    es.close();
    _es = null;
    _setStatus('disconnected');
    if (_refCount > 0) {
      _reconnectTimer = setTimeout(() => {
        _reconnectDelay = Math.min(_reconnectDelay * 2, MAX_DELAY);
        _connect();
      }, _reconnectDelay);
    }
  };
}

function _disconnect() {
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  if (_es) { _es.close(); _es = null; }
  _setStatus('disconnected');
}

// ── public hooks ──────────────────────────────────────────────────────────────

/** Subscribe to one event type from the shared SSE stream. */
export function useAppStream<T>(event: AppStreamEvent): { data: T | null; status: StreamStatus } {
  const [data, setData]     = useState<T | null>(() => (_latest.get(event) as T) ?? null);
  const [status, setStatus] = useState<StreamStatus>(_status);
  const setDataRef   = useRef(setData);
  const setStatusRef = useRef(setStatus);
  setDataRef.current   = setData;
  setStatusRef.current = setStatus;

  useEffect(() => {
    const dataListener: Listener<T>          = (d) => setDataRef.current(d);
    const statusListener: Listener<StreamStatus> = (s) => setStatusRef.current(s);

    _getListeners<T>(event).add(dataListener);
    _statusListeners.add(statusListener);
    _refCount++;
    _connect();

    // Replay latest cached value immediately on mount
    const cached = _latest.get(event) as T | undefined;
    if (cached !== undefined) setData(cached);

    return () => {
      _getListeners<T>(event).delete(dataListener);
      _statusListeners.delete(statusListener);
      _refCount--;
      if (_refCount === 0) _disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event]);

  return { data, status };
}

/** Subscribe to prices only (Record<string, number>). */
export function useStreamPrices(): Record<string, number> {
  const { data } = useAppStream<Record<string, number>>('prices');
  return data ?? {};
}

/** Stream status only — cheap way to show connection indicator. */
export function useStreamStatus(): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>(_status);
  const ref = useRef(setStatus);
  ref.current = setStatus;

  useEffect(() => {
    const fn: Listener<StreamStatus> = (s) => ref.current(s);
    _statusListeners.add(fn);
    _refCount++;
    _connect();
    return () => {
      _statusListeners.delete(fn);
      _refCount--;
      if (_refCount === 0) _disconnect();
    };
  }, []);

  return status;
}
