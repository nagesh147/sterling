/**
 * useSignalFeed — append-only signal feed, Instagram-style.
 *
 * Instead of replacing the list on every poll, we accumulate entries:
 * - New actionable signals are PREPENDED at the top.
 * - Existing entries are NEVER reordered — only their live price updates.
 * - Entries survive across polls, even when the underlying state goes back to IDLE.
 * - Persisted to sessionStorage so page refresh keeps history.
 */
import { useEffect, useRef, useState } from 'react';
import { useSignals } from './useSignals';
import type { SignalItem } from './useSignals';

export interface FeedEntry {
  id: string;               // unique: underlying + type + entryAt
  underlying: string;
  direction: 'long' | 'short';
  type: 'futures' | 'options';

  // Prices frozen at signal time
  entry: number;
  stopLoss: number | null;
  takeProfit: number | null;

  // Instrument details frozen at signal time
  leverage: number;
  futuresSymbol: string;
  optSymbol: string | null;
  optStrike: number | null;
  optType: 'CE' | 'PE' | null;
  optExpiry: string | null;
  optDte: number | null;

  // Signal context frozen at signal time
  state: string;
  regime: string;
  score: number;
  adx: number;
  rsi: number;
  entryAt: number;          // timestamp when this entry was added to feed

  // Live-updating fields (mutated in place, no reorder)
  currentPrice: number | null;
  currentState: string;
  dismissed: boolean;
}

const FEED_KEY   = 'sterling_signal_feed';
const MAX_FEED   = 100;
const DEDUP_MS   = 25 * 60 * 1000;   // don't add same instrument+type again within 25 min
const EXPIRE_MS  = 8 * 60 * 60 * 1000; // remove entries older than 8 hours

const ACTIONABLE = new Set([
  'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION',
  'CONFIRMED_SETUP_ACTIVE', 'EARLY_SETUP_ACTIVE',
]);

function load(): FeedEntry[] {
  try {
    const raw = sessionStorage.getItem(FEED_KEY);
    if (!raw) return [];
    const parsed: FeedEntry[] = JSON.parse(raw);
    const cutoff = Date.now() - EXPIRE_MS;
    return parsed.filter(e => e.entryAt > cutoff).slice(0, MAX_FEED);
  } catch { return []; }
}

function save(feed: FeedEntry[]) {
  try { sessionStorage.setItem(FEED_KEY, JSON.stringify(feed.slice(0, MAX_FEED))); }
  catch { /* storage full — silent */ }
}

function nextFridayExpiry(): string {
  const today = new Date();
  const daysToFri = ((5 - today.getDay()) + 7) % 7 || 7;
  const exp = new Date(today.getTime() + daysToFri * 86_400_000);
  return exp.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
    .replace(/ /g, '').toUpperCase();
}

const NEXT_EXPIRY = nextFridayExpiry();

function buildEntries(sig: SignalItem, now: number): FeedEntry[] {
  const entries: FeedEntry[] = [];
  const dir  = sig.direction as 'long' | 'short';
  const spot = sig.spot_price ?? 0;
  const atr  = sig.atr ?? spot * 0.02;
  const mult = sig.stop_atr_mult ?? 2;
  const sl   = sig.stop_price  ?? (dir === 'long' ? spot - atr * mult : spot + atr * mult);
  const tp   = sig.target_price ?? (dir === 'long' ? spot + atr * mult * 2 : spot - atr * mult * 2);
  const lev  = sig.rec_leverage ?? 5;
  const score = dir === 'long' ? sig.score_long : sig.score_short;

  // Futures entry
  entries.push({
    id: `${sig.underlying}_futures_${now}`,
    underlying: sig.underlying, direction: dir, type: 'futures',
    entry: spot, stopLoss: sl, takeProfit: tp,
    leverage: lev, futuresSymbol: sig.futures_symbol ?? `${sig.underlying}USDT`,
    optSymbol: null, optStrike: null, optType: null, optExpiry: null, optDte: null,
    state: sig.state, regime: sig.regime, score: Math.round(score),
    adx: sig.adx ?? 0, rsi: sig.rsi ?? 50,
    entryAt: now, currentPrice: spot, currentState: sig.state, dismissed: false,
  });

  // Options entry — only for liquid instruments (estimated premium >= $2)
  const estPremium = spot * 0.01;
  if (sig.has_options && estPremium >= 2) {
    const step    = spot > 10_000 ? 500 : 100;
    const strike  = sig.opt_strike  ?? Math.round(spot / step) * step;
    const optType = (sig.opt_type  ?? (dir === 'long' ? 'CE' : 'PE')) as 'CE' | 'PE';
    const expiry  = sig.opt_expiry  ?? NEXT_EXPIRY;
    const dte     = sig.opt_dte     ?? ((5 - new Date().getDay() + 7) % 7 || 7);
    const optSym  = sig.opt_symbol  ?? `${optType[0]}-${sig.underlying}-${strike}-${expiry}`;

    entries.push({
      id: `${sig.underlying}_options_${now}`,
      underlying: sig.underlying, direction: dir, type: 'options',
      entry: spot, stopLoss: sl, takeProfit: tp,
      leverage: 1, futuresSymbol: sig.futures_symbol ?? `${sig.underlying}USDT`,
      optSymbol: optSym, optStrike: strike, optType, optExpiry: expiry, optDte: dte,
      state: sig.state, regime: sig.regime, score: Math.round(score),
      adx: sig.adx ?? 0, rsi: sig.rsi ?? 50,
      entryAt: now, currentPrice: spot, currentState: sig.state, dismissed: false,
    });
  }

  return entries;
}

export function useSignalFeed() {
  const { data } = useSignals();
  const [feed, setFeed] = useState<FeedEntry[]>(() => load());
  const seenRef = useRef<Map<string, number>>(new Map()); // key → last seen ms

  useEffect(() => {
    if (!data?.signals) return;
    const now = Date.now();
    const fresh = data.signals.filter(
      s => s.fresh && s.direction !== 'neutral' && ACTIONABLE.has(s.state)
    );
    if (fresh.length === 0) {
      // Still update currentPrice + currentState in existing entries
      setFeed(prev => {
        let changed = false;
        const next = prev.map(e => {
          const match = data.signals.find(s => s.underlying === e.underlying && s.fresh);
          if (!match) return e;
          const cp = match.spot_price;
          const cs = match.state;
          if (cp === e.currentPrice && cs === e.currentState) return e;
          changed = true;
          return { ...e, currentPrice: cp, currentState: cs };
        });
        return changed ? next : prev;
      });
      return;
    }

    const newEntries: FeedEntry[] = [];
    for (const sig of fresh) {
      for (const type of ['futures', 'options'] as const) {
        if (type === 'options' && (!sig.has_options || (sig.spot_price ?? 0) * 0.01 < 2)) continue;
        const key = `${sig.underlying}_${type}`;
        const lastSeen = seenRef.current.get(key) ?? 0;
        if (now - lastSeen < DEDUP_MS) continue;   // skip: too recent
        seenRef.current.set(key, now);
        const built = buildEntries(sig, now).filter(e => e.type === type);
        newEntries.push(...built);
      }
    }

    setFeed(prev => {
      // Update current prices on all existing entries
      const updated = prev.map(e => {
        const match = data.signals.find(s => s.underlying === e.underlying && s.fresh);
        if (!match) return e;
        return { ...e, currentPrice: match.spot_price, currentState: match.state };
      });
      // Prepend genuinely new entries; cap at MAX_FEED
      const next = newEntries.length > 0
        ? [...newEntries, ...updated].slice(0, MAX_FEED)
        : updated;
      save(next);
      return next;
    });
  }, [data]);

  const dismiss = (id: string) =>
    setFeed(prev => {
      const next = prev.map(e => e.id === id ? { ...e, dismissed: true } : e);
      save(next);
      return next;
    });

  const clearAll = () => {
    setFeed([]);
    sessionStorage.removeItem(FEED_KEY);
    seenRef.current.clear();
  };

  return { feed, dismiss, clearAll };
}
