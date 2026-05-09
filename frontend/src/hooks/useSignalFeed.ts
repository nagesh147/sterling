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
  rsi: number;
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
function loadFeed(): FeedEntry[] {
  try {
    const raw = sessionStorage.getItem(FEED_KEY);
    if (!raw) return [];
    const all: FeedEntry[] = JSON.parse(raw);
    const cut = Date.now() - EXPIRE_MS;
    return all.filter(e => e.entryAt > cut).slice(0, MAX_FEED);
  } catch { return []; }
}

function saveFeed(feed: FeedEntry[]) {
  try { sessionStorage.setItem(FEED_KEY, JSON.stringify(feed.slice(0, MAX_FEED))); }
  catch { /* quota exceeded */ }
}

function loadStates(): Record<string, string> {
  try { return JSON.parse(sessionStorage.getItem(STATES_KEY) || '{}'); }
  catch { return {}; }
}

function saveStates(m: Record<string, string>) {
  try { sessionStorage.setItem(STATES_KEY, JSON.stringify(m)); }
  catch { /* quota */ }
}

// ── option expiry ─────────────────────────────────────────────────────────────
function nextFridayExpiry(): string {
  const d = new Date();
  const daysToFri = ((5 - d.getDay()) + 7) % 7 || 7;
  const exp = new Date(d.getTime() + daysToFri * 86_400_000);
  return exp.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
    .replace(/ /g, '').toUpperCase();
}
const NEXT_EXPIRY = nextFridayExpiry();

// ── build a FeedEntry from a SignalItem ───────────────────────────────────────
function buildEntry(sig: SignalItem, type: 'futures' | 'options', now: number): FeedEntry {
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
    rsi: sig.rsi ?? 50,
    entryAt: now,
    currentPrice: spot,
    currentState: sig.state,
    dismissed: false,
  };
}

// ── main hook ─────────────────────────────────────────────────────────────────
export function useSignalFeed() {
  const { data } = useSignals();

  // Lazy initializer — runs exactly once on mount, not on every render
  const [feed, setFeed] = useState<FeedEntry[]>(() => loadFeed());

  // useRef with lazy pattern: store the loaded value in a ref that is
  // only computed once (via a flag check), avoiding repeated sessionStorage reads
  const statesRef  = useRef<Record<string, string> | null>(null);
  if (statesRef.current === null) statesRef.current = loadStates();

  // Persist feed to sessionStorage whenever it changes — PURE side effect,
  // NOT inside setFeed updater (React calls updaters multiple times in concurrent mode)
  useEffect(() => {
    saveFeed(feed);
  }, [feed]);

  useEffect(() => {
    if (!data?.signals) return;

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
          newEntries.push(buildEntry(sig, type, now));
        }
      }
    }

    // Commit state changes after the loop — not mid-loop
    if (statesChanged) {
      statesRef.current = states;
      saveStates(states);
    }

    // Pure updater — no side effects inside
    setFeed(prev => {
      const updated = prev.map(e => {
        const match = data.signals.find(s => s.underlying === e.underlying && s.fresh);
        if (!match) return e;
        const cp = match.spot_price ?? e.currentPrice;
        const cs = match.state;
        if (cp === e.currentPrice && cs === e.currentState) return e;
        return { ...e, currentPrice: cp, currentState: cs };
      });
      if (newEntries.length === 0) return updated;
      return [...newEntries, ...updated].slice(0, MAX_FEED);
    });
  }, [data]);

  const dismiss = (id: string) =>
    setFeed(prev => prev.map(e => e.id === id ? { ...e, dismissed: true } : e));

  const clearAll = () => {
    setFeed([]);
    sessionStorage.removeItem(FEED_KEY);
    sessionStorage.removeItem(STATES_KEY);
    statesRef.current = {};
  };

  return { feed, dismiss, clearAll };
}
