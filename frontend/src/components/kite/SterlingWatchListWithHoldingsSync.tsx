import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useKiteHoldings } from '../../hooks/useKite';
import type { WatchItem } from '../../types/kite';
import { k as t } from '../../styles/kiteUI';
import { SterlingWatchList } from './SterlingWatchList';

const WATCH_KEY = 'sterling.kite.watchlist.v1';
const MANUAL_EMPTY_KEY = 'sterling.kite.watchlist.manual-empty.v1';
const MAX_WATCH_ITEMS = 50;

function readWatchlist(): WatchItem[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCH_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeWatchlist(items: WatchItem[]) {
  localStorage.setItem(WATCH_KEY, JSON.stringify(items));
  window.dispatchEvent(new Event('kite-watchlist-storage-sync'));
}

function holdingToWatchItem(holding: any): WatchItem | null {
  const tradingsymbol = String(holding?.tradingsymbol || holding?.trading_symbol || holding?.symbol || '').trim();
  if (!tradingsymbol) return null;
  const exchange = String(holding?.exchange || 'NSE').trim() || 'NSE';
  const token = Number(holding?.instrument_token || holding?.token || 0);
  return {
    symbol: `${exchange}:${tradingsymbol}`,
    token: Number.isFinite(token) ? token : 0,
    name: tradingsymbol,
    sub: `${exchange} · holding`,
  };
}

function dedupeItems(items: WatchItem[]): WatchItem[] {
  const seen = new Set<string>();
  const out: WatchItem[] = [];
  for (const item of items) {
    if (!item?.symbol || seen.has(item.symbol)) continue;
    seen.add(item.symbol);
    out.push(item);
    if (out.length >= MAX_WATCH_ITEMS) break;
  }
  return out;
}

function SyncHoldingsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 7h10a5 5 0 0 1 5 5v1" />
      <path d="M14 3l4 4-4 4" />
      <path d="M20 17H10a5 5 0 0 1-5-5v-1" />
      <path d="M10 21l-4-4 4-4" />
    </svg>
  );
}

export function SterlingWatchListWithHoldingsSync({
  onOpenInstrument,
}: {
  onOpenInstrument?: (symbol: string, defaultTab: 'chart' | 'option-chain') => void;
}) {
  const hadWatchStorageOnMount = useMemo(() => localStorage.getItem(WATCH_KEY) != null, []);
  const [watchSnapshot, setWatchSnapshot] = useState<WatchItem[]>(() => readWatchlist());
  const [manualEmpty, setManualEmpty] = useState(() => localStorage.getItem(MANUAL_EMPTY_KEY) === '1');
  const [childKey, setChildKey] = useState(0);
  const [autoAttempted, setAutoAttempted] = useState(() => hadWatchStorageOnMount || localStorage.getItem(MANUAL_EMPTY_KEY) === '1');
  const previousCountRef = useRef(watchSnapshot.length);
  const autoSeededRef = useRef(false);

  const holdings = useKiteHoldings(true);
  const holdingItems = useMemo(
    () => dedupeItems((holdings.data || []).map(holdingToWatchItem).filter(Boolean) as WatchItem[]),
    [holdings.data],
  );

  const refreshSnapshot = useCallback(() => {
    setWatchSnapshot(readWatchlist());
    setManualEmpty(localStorage.getItem(MANUAL_EMPTY_KEY) === '1');
  }, []);

  useEffect(() => {
    const timer = window.setInterval(refreshSnapshot, 500);
    window.addEventListener('storage', refreshSnapshot);
    window.addEventListener('focus', refreshSnapshot);
    window.addEventListener('kite-watchlist-storage-sync', refreshSnapshot);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('storage', refreshSnapshot);
      window.removeEventListener('focus', refreshSnapshot);
      window.removeEventListener('kite-watchlist-storage-sync', refreshSnapshot);
    };
  }, [refreshSnapshot]);

  useEffect(() => {
    const previousCount = previousCountRef.current;
    const currentCount = watchSnapshot.length;
    if (previousCount > 0 && currentCount === 0) {
      localStorage.setItem(MANUAL_EMPTY_KEY, '1');
      setManualEmpty(true);
    } else if (currentCount > 0) {
      localStorage.removeItem(MANUAL_EMPTY_KEY);
      setManualEmpty(false);
    }
    previousCountRef.current = currentCount;
  }, [watchSnapshot.length]);

  const addMissingHoldings = useCallback(() => {
    const current = readWatchlist();
    const existing = new Set(current.map((item) => item.symbol));
    const missing = holdingItems.filter((item) => !existing.has(item.symbol));
    if (missing.length === 0) return false;
    const next = dedupeItems([...current, ...missing]);
    writeWatchlist(next);
    localStorage.removeItem(MANUAL_EMPTY_KEY);
    setManualEmpty(false);
    setWatchSnapshot(next);
    setChildKey((key) => key + 1);
    return true;
  }, [holdingItems]);

  const freshEmptyBoot = !hadWatchStorageOnMount && !manualEmpty;
  useEffect(() => {
    if (!freshEmptyBoot || autoSeededRef.current || holdings.isLoading || holdings.isFetching) return;
    autoSeededRef.current = true;
    if (holdingItems.length > 0) addMissingHoldings();
    setAutoAttempted(true);
  }, [addMissingHoldings, freshEmptyBoot, holdingItems.length, holdings.isFetching, holdings.isLoading]);

  const watchedSymbols = useMemo(() => new Set(watchSnapshot.map((item) => item.symbol)), [watchSnapshot]);
  const missingHoldings = useMemo(
    () => holdingItems.filter((item) => !watchedSymbols.has(item.symbol)),
    [holdingItems, watchedSymbols],
  );

  const syncDisabled = missingHoldings.length === 0 || holdings.isLoading || holdings.isFetching;
  const syncTitle = holdings.isLoading || holdings.isFetching
    ? 'Checking Kite holdings…'
    : missingHoldings.length > 0
      ? `Sync ${missingHoldings.length} missing Kite holding${missingHoldings.length === 1 ? '' : 's'} into watchlist`
      : holdingItems.length > 0
        ? 'All Kite holdings are already in the watchlist'
        : holdings.isError
          ? 'Unable to check Kite holdings'
          : 'No Kite holdings found';
  const hideDefaultEmptyPrompt = watchSnapshot.length === 0 && !manualEmpty;

  if (freshEmptyBoot && !autoAttempted && !holdings.isError) {
    return (
      <div style={{ height: '100%', background: t.bg, color: t.dim, fontFamily: t.fontFamily, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: 50, borderBottom: `1px solid ${t.border}` }} />
        <div style={{ padding: 24, fontSize: 12 }}>Syncing Kite holdings…</div>
      </div>
    );
  }

  return (
    <div className="kite-watchlist-sync-shell" style={{ position: 'relative', height: '100%' }}>
      <style>{`
        /* Reserve a real header slot for the holdings-sync action. The wrapped
           watchlist owns the search bar, so move its trailing count/filter group
           left instead of placing the sync control on top of it. */
        .kite-watchlist-sync-shell div:has(> input[placeholder="Search"]) > div:last-child {
          margin-right: 36px;
        }
      `}</style>
      <SterlingWatchList key={childKey} onOpenInstrument={onOpenInstrument} />
      {hideDefaultEmptyPrompt && (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            top: 50,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 15,
            background: t.bg,
            pointerEvents: 'none',
          }}
        />
      )}
      <div style={{ position: 'absolute', top: 13, right: 10, zIndex: 25, display: 'inline-flex', alignItems: 'center' }}>
        <button
          type="button"
          disabled={syncDisabled}
          title={syncTitle}
          aria-label="Sync holdings from Kite"
          onClick={(event) => {
            event.stopPropagation();
            if (!syncDisabled) addMissingHoldings();
          }}
          style={{
            width: 24,
            height: 24,
            padding: 0,
            borderRadius: 4,
            border: 'none',
            background: 'transparent',
            color: syncDisabled ? t.dim : t.blue,
            opacity: syncDisabled ? 0.45 : 1,
            cursor: syncDisabled ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <SyncHoldingsIcon />
        </button>
      </div>
    </div>
  );
}
