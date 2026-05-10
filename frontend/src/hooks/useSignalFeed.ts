/**
 * useSignalFeed — append-only signal feed driven by STATE TRANSITIONS.
 *
 * A new row is added ONLY when:
 *   1. State transitions from non-actionable → actionable (IDLE→EARLY, EARLY→CONFIRMED, etc.)
 *   2. Direction flips (was LONG, now SHORT)
 *   3. A fresh green/red arrow fires
 *
 * Existing rows are NEVER reordered — only their live price & state badge update.
 * Both the feed and the state-tracker are persisted to sessionStorage so page
 * refresh does NOT re-fire signals that are already in an armed state.
 */
import { useEffect, useRef, useState } from 'react';
import { useSignals } from './useSignals';
import type { SignalItem } from './useSignals';
import { useTradingMode } from './useTradingMode';
import { inferModeTag } from '../utils/fmt';

// Module-level registry so ArrowAlert can inject entries without prop drilling
type ArrowParams = [string, 'long'|'short', number, number|null, number|null, number, string, string|null, number|null, 'CE'|'PE'|null, string|null, string, number];
let _globalAddArrow: ((...args: ArrowParams) => void) | null = null;

/** Call from ArrowAlert to instantly add an entry without waiting for the 15s poll. */
export function injectArrowEntry(...args: ArrowParams) {
  _globalAddArrow?.(...args);
}

// Called by TradingModeSelector after mode switch so the next poll generates
// fresh entries with the new mode's parameters (new SL/TP/leverage).
// Without this, the state tracker says EARLY===EARLY → no new entry added.
let _globalClearState: (() => void) | null = null;
let _globalClearFeed:  (() => void) | null = null;

export function clearSignalFeedState() {
  _globalClearState?.();
}

/** Wipe the entire feed + state tracker. Called on mode switch so stale
 *  entries tagged with the old mode don't linger in the list. */
export function clearSignalFeed() {
  _globalClearFeed?.();
}

export interface FeedEntry {
  id: string;
  underlying: string;
  direction: 'long' | 'short';
  type: 'futures' | 'options';
  entry: number;
  stopLoss: number | null;
  takeProfit: number | null;
  leverage: number;
  futuresSymbol: string;
  optSymbol: string | null;
  optStrike: number | null;
  optType: 'CE' | 'PE' | null;
  optExpiry: string | null;
  optDte: number | null;
  state: string;        // state at time of signal
  regime: string;
  score: number;
  adx: number;
  atr_percentile: number;
  rsi: number;
  mode: string;         // trading mode that generated this signal (scalping/swing/etc.)
  entryAt: number;
  currentPrice: number | null;
  currentState: string;
  dismissed: boolean;
}

// ── persistence keys ──────────────────────────────────────────────────────────
const FEED_KEY   = 'sterling_signal_feed_v2';
const STATES_KEY = 'sterling_signal_states_v2';   // last-known state per key

const MAX_FEED  = 100;
const EXPIRE_MS = 8 * 60 * 60 * 1000;   // 8 hours

const ACTIONABLE = new Set([
  'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION',
  'CONFIRMED_SETUP_ACTIVE', 'EARLY_SETUP_ACTIVE',
]);

// ── sessionStorage helpers ────────────────────────────────────────────────────

// Purge ALL legacy sterling_* keys written by previous versions on first load
try {
  const toRemove: string[] = [];
  for (let i = 0; i < sessionStorage.length; i++) {
    const k = sessionStorage.key(i);
    // Keep only the current versioned keys; remove everything else
    if (k && k.startsWith('sterling_') && k !== FEED_KEY && k !== STATES_KEY) {
      toRemove.push(k);
    }
  }
  toRemove.forEach(k => sessionStorage.removeItem(k));
} catch { /* ignore */ }

function isFeedEntry(x: unknown): x is FeedEntry {
  if (!x || typeof x !== 'object') return false;
  const e = x as Record<string, unknown>;
  return typeof e.id === 'string'
    && typeof e.underlying === 'string'
    && typeof e.entryAt === 'number'
    && typeof e.entry === 'number'
    && (e.direction === 'long' || e.direction === 'short')
    && (e.type === 'futures' || e.type === 'options');
}

function loadFeed(): FeedEntry[] {
  try {
    const raw = sessionStorage.getItem(FEED_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const cut = Date.now() - EXPIRE_MS;
    return parsed
      .filter(isFeedEntry)                   // reject bad-shape entries
      .filter((e: FeedEntry) => e.entryAt > cut)
      .slice(0, MAX_FEED);
  } catch { return []; }
}

let _saveTimer: ReturnType<typeof setTimeout> | null = null;
function saveFeed(feed: FeedEntry[]) {
  // Debounce writes — cancel any pending save and reschedule with latest data.
  // The old pattern (skip if timer exists) was saving stale data: entries that
  // accumulated after the first call in the window were never persisted.
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => {
    _saveTimer = null;
    try { sessionStorage.setItem(FEED_KEY, JSON.stringify(feed.slice(0, MAX_FEED))); }
    catch { try { sessionStorage.removeItem(FEED_KEY); } catch { /* ignore */ } }
  }, 3_000);
}

function loadStates(): Record<string, string> {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(STATES_KEY) || '{}');
    if (typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed as Record<string, string>;
  } catch { return {}; }
}

function saveStates(m: Record<string, string>) {
  try { sessionStorage.setItem(STATES_KEY, JSON.stringify(m)); }
  catch { /* quota */ }
}

// ── option expiry ─────────────────────────────────────────────────────────────
function nextFridayExpiry(): string {
  // Delta Exchange India symbol format: DDMMYY (e.g. 150526, not 15MAY26)
  const d = new Date();
  const daysToFri = ((5 - d.getDay()) + 7) % 7 || 7;
  const exp = new Date(d.getTime() + daysToFri * 86_400_000);
  const dd = String(exp.getDate()).padStart(2, '0');
  const mm = String(exp.getMonth() + 1).padStart(2, '0');
  const yy = String(exp.getFullYear()).slice(-2);
  return `${dd}${mm}${yy}`;
}
// ── build a FeedEntry from a SignalItem ───────────────────────────────────────
function buildEntry(sig: SignalItem, type: 'futures' | 'options', now: number, mode = 'swing'): FeedEntry {
  const resolvedMode = mode === 'all'
    ? inferModeTag(sig.adx ?? 0, sig.atr_percentile ?? 50, Math.max(sig.score_long, sig.score_short))
    : mode;
  // nextFridayExpiry() called per-entry so long-lived tabs don't carry a stale week
  const NEXT_EXPIRY = nextFridayExpiry();
  const dir  = sig.direction as 'long' | 'short';
  const spot = sig.spot_price ?? 0;
  const atr  = sig.atr ?? spot * 0.02;
  const mult = sig.stop_atr_mult ?? 2;
  const sl   = sig.stop_price   ?? (dir === 'long' ? spot - atr * mult : spot + atr * mult);
  const tp   = sig.target_price ?? (dir === 'long' ? spot + atr * mult * 2 : spot - atr * mult * 2);
  const lev  = sig.rec_leverage ?? 5;
  const score = Math.round(dir === 'long' ? sig.score_long : sig.score_short);

  const step    = spot > 10_000 ? 500 : 100;
  const strike  = sig.opt_strike  ?? Math.round(spot / step) * step;
  const optType = (sig.opt_type   ?? (dir === 'long' ? 'CE' : 'PE')) as 'CE' | 'PE';
  const expiry  = sig.opt_expiry  ?? NEXT_EXPIRY;
  const dte     = sig.opt_dte     ?? (((5 - new Date().getDay()) + 7) % 7 || 7);
  const optSym  = sig.opt_symbol  ?? `${optType[0]}-${sig.underlying}-${strike}-${expiry}`;

  return {
    id: `${sig.underlying}_${type}_${now}`,
    underlying: sig.underlying,
    direction: dir,
    type,
    entry: spot,
    stopLoss: sl,
    takeProfit: tp,
    leverage: type === 'futures' ? lev : 1,
    futuresSymbol: sig.futures_symbol ?? `${sig.underlying}USDT`,
    optSymbol:  type === 'options' ? optSym   : null,
    optStrike:  type === 'options' ? strike   : null,
    optType:    type === 'options' ? optType  : null,
    optExpiry:  type === 'options' ? expiry   : null,
    optDte:     type === 'options' ? dte      : null,
    state: sig.state,
    regime: sig.regime,
    score,
    adx: sig.adx ?? 0,
    atr_percentile: sig.atr_percentile ?? 0,
    rsi: sig.rsi ?? 50,
    mode: resolvedMode,
    entryAt: now,
    currentPrice: spot,
    currentState: sig.state,
    dismissed: false,
  };
}

// ── main hook ─────────────────────────────────────────────────────────────────
export function useSignalFeed() {
  const { data } = useSignals();
  const { data: modeData } = useTradingMode();
  const currentMode = modeData?.name ?? 'swing';

  // Lazy initializer — runs exactly once on mount, not on every render
  const [feed, setFeed] = useState<FeedEntry[]>(() => loadFeed());

  // useRef with lazy pattern: store the loaded value in a ref that is
  // only computed once (via a flag check), avoiding repeated sessionStorage reads
  const statesRef  = useRef<Record<string, string> | null>(null);
  if (statesRef.current === null) statesRef.current = loadStates();

  // Persist feed whenever it changes (pure side effect, outside updater)
  useEffect(() => { saveFeed(feed); }, [feed]);

  // Stable ref for the global registration (declared after addArrowEntry below)
  const addArrowRef = useRef<typeof addArrowEntry | null>(null);

  useEffect(() => {
    if (!data?.signals) return;
    try {

    const now        = Date.now();
    const states     = { ...statesRef.current! }; // copy — don't mutate during loop
    const newEntries: FeedEntry[] = [];
    let statesChanged = false;

    for (const sig of data.signals) {
      if (!sig.fresh || sig.direction === 'neutral') continue;

      for (const type of ['futures', 'options'] as const) {
        if (type === 'options' && (!sig.has_options || (sig.spot_price ?? 0) * 0.01 < 2)) continue;

        const key      = `${sig.underlying}_${type}`;
        const dirKey   = `${key}_dir`;
        const prevState = states[key]    ?? 'IDLE';
        const prevDir   = states[dirKey] ?? '';
        const curState  = sig.state;

        // Update state tracker
        if (states[key] !== curState)         { states[key]    = curState;      statesChanged = true; }
        if (states[dirKey] !== sig.direction) { states[dirKey] = sig.direction; statesChanged = true; }

        const stateTransition = ACTIONABLE.has(curState) && curState !== prevState;
        const dirFlip         = ACTIONABLE.has(curState) && prevDir !== '' && prevDir !== sig.direction;
        const arrow           = sig.green_arrow || sig.red_arrow;

        if (stateTransition || dirFlip || arrow) {
          newEntries.push(buildEntry(sig, type, now, currentMode));
        }
      }
    }

    // Commit state changes after the loop — not mid-loop
    if (statesChanged) {
      statesRef.current = states;
      saveStates(states);
    }

    setFeed(prev => {
      // Update live price/state per entry — return SAME object reference if unchanged
      // so React bails out of re-rendering that row.
      let anyChanged = false;
      const updated = prev.map(e => {
        const match = data.signals.find(s => s.underlying === e.underlying && s.fresh);
        if (!match) return e;
        const cp = match.spot_price ?? e.currentPrice;
        const cs = match.state;
        if (cp === e.currentPrice && cs === e.currentState) return e;
        anyChanged = true;
        return { ...e, currentPrice: cp, currentState: cs };
      });

      // No new entries and no price changes → return SAME array reference.
      // React uses Object.is() comparison; same ref = skip re-render entirely.
      if (newEntries.length === 0 && !anyChanged) return prev;
      if (newEntries.length === 0) return updated;
      return [...newEntries, ...updated].slice(0, MAX_FEED);
    });

    } catch (err) {
      console.warn('[useSignalFeed] effect error (ignored):', err);
    }
  }, [data]);

  // Called by ArrowAlert when a live arrow fires — injects an entry immediately
  // without waiting for the 15s useSignals poll to pick up the ephemeral arrow.
  const addArrowEntry = (
    underlying: string, direction: 'long' | 'short', spot: number,
    stopLoss: number | null, takeProfit: number | null,
    leverage: number, futuresSymbol: string,
    optSymbol: string | null, optStrike: number | null,
    optType: 'CE' | 'PE' | null, optExpiry: string | null,
    regime: string, score: number,
  ) => {
    const now = Date.now();
    const newEntries: FeedEntry[] = [];

    // Futures entry
    newEntries.push({
      id: `${underlying}_futures_arrow_${now}`,
      underlying, direction, type: 'futures',
      entry: spot, stopLoss, takeProfit,
      leverage, futuresSymbol,
      optSymbol: null, optStrike: null, optType: null, optExpiry: null, optDte: null,
      state: 'ENTRY_ARMED_PULLBACK', regime, score, adx: 0, atr_percentile: 0, rsi: 50, mode: currentMode,
      entryAt: now, currentPrice: spot, currentState: 'ENTRY_ARMED_PULLBACK', dismissed: false,
    });

    // Options entry (if available and liquid)
    if (optSymbol && optStrike && optExpiry && spot * 0.01 >= 2) {
      newEntries.push({
        id: `${underlying}_options_arrow_${now}`,
        underlying, direction, type: 'options',
        entry: spot, stopLoss, takeProfit,
        leverage: 1, futuresSymbol,
        optSymbol, optStrike, optType, optExpiry, optDte: null,
        state: 'ENTRY_ARMED_PULLBACK', regime, score, adx: 0, atr_percentile: 0, rsi: 50, mode: currentMode,
        entryAt: now, currentPrice: null, currentState: 'ENTRY_ARMED_PULLBACK', dismissed: false,
      });
    }

    // Update state tracker so this doesn't get re-added on the next poll
    if (statesRef.current) {
      statesRef.current[`${underlying}_futures`] = 'ENTRY_ARMED_PULLBACK';
      statesRef.current[`${underlying}_options`] = 'ENTRY_ARMED_PULLBACK';
      statesRef.current[`${underlying}_futures_dir`] = direction;
      statesRef.current[`${underlying}_options_dir`] = direction;
      saveStates(statesRef.current);
    }

    setFeed(prev => {
      const next = [...newEntries, ...prev].slice(0, MAX_FEED);
      return next;
    });
  };

  // Keep ref in sync (runs every render, no effect needed — just assignment)
  addArrowRef.current = addArrowEntry;

  // Register globals ONCE on mount (stable ref wrapper pattern)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    _globalAddArrow   = (...args: ArrowParams) => addArrowRef.current?.(...args);
    _globalClearState = () => {
      statesRef.current = {};
      saveStates({});
    };
    _globalClearFeed = () => {
      setFeed([]);
      try {
        sessionStorage.removeItem(FEED_KEY);
        sessionStorage.removeItem(STATES_KEY);
      } catch { /* quota */ }
      statesRef.current = {};
    };
    return () => { _globalAddArrow = null; _globalClearState = null; _globalClearFeed = null; };
  }, []);

  const dismiss = (id: string) =>
    setFeed(prev => prev.map(e => e.id === id ? { ...e, dismissed: true } : e));

  const clearAll = () => {
    setFeed([]);
    sessionStorage.removeItem(FEED_KEY);
    sessionStorage.removeItem(STATES_KEY);
    statesRef.current = {};
  };

  return { feed, dismiss, clearAll, addArrowEntry };
}
