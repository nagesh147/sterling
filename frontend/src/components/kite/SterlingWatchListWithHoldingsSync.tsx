import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useKitePositions, useSyncKiteWatchlist } from '../../hooks/useKite';
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

function watchSignature(items: WatchItem[]): string {
  return items.map((item) => `${item.symbol}:${item.token}:${item.lot_size ?? ''}:${item.expiry ?? ''}`).join('|');
}

function positionToWatchItem(position: any): WatchItem | null {
  const qty = Number(position?.quantity ?? position?.qty ?? position?.net_quantity ?? 0);
  if (!Number.isFinite(qty) || qty === 0) return null;
  const tradingsymbol = String(position?.tradingsymbol || position?.trading_symbol || position?.symbol || '').trim();
  if (!tradingsymbol) return null;
  const exchange = String(position?.exchange || 'NFO').trim() || 'NFO';
  const token = Number(position?.instrument_token || position?.token || 0);
  const product = String(position?.product || '').trim();
  return {
    symbol: `${exchange}:${tradingsymbol}`,
    token: Number.isFinite(token) ? token : 0,
    name: tradingsymbol,
    sub: product ? `${exchange} · ${product} position` : `${exchange} · open position`,
  };
}

function syncItemToPositionWatchItem(item: any): WatchItem | null {
  const source = String(item?.source || item?.sub || '').toLowerCase();
  if (!source.includes('position')) return null;
  const symbol = String(item?.symbol || '').trim();
  if (!symbol) return null;
  const [, fallbackName = symbol] = symbol.split(':');
  const token = Number(item?.token || item?.instrument_token || 0);
  return {
    symbol,
    token: Number.isFinite(token) ? token : 0,
    name: String(item?.name || fallbackName),
    sub: String(item?.sub || 'open position'),
    lot_size: item?.lot_size,
    expiry: item?.expiry,
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

function positionsToWatchItems(positions: { net?: any[]; day?: any[] } | undefined): WatchItem[] {
  // Only net positions represent still-open positions. `day` also contains
  // closed/intraday-touched symbols, which is why ICICI was being added even
  // after its net quantity was zero.
  return dedupeItems((positions?.net || []).map(positionToWatchItem).filter(Boolean) as WatchItem[]);
}

function syncItemsToPositionWatchItems(items: any[] | undefined): WatchItem[] {
  return dedupeItems((items || []).map(syncItemToPositionWatchItem).filter(Boolean) as WatchItem[]);
}

function SyncPositionsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M16 8h5V3" />
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
  const [manualRefreshing, setManualRefreshing] = useState(false);
  const [searchActive, setSearchActive] = useState(false);
  const previousCountRef = useRef(watchSnapshot.length);
  const watchSignatureRef = useRef(watchSignature(watchSnapshot));
  const autoSeededRef = useRef(false);

  const positions = useKitePositions(true);
  const watchlistSync = useSyncKiteWatchlist();
  const positionItems = useMemo(() => positionsToWatchItems(positions.data), [positions.data]);

  const refreshSnapshot = useCallback(() => {
    const next = readWatchlist();
    const signature = watchSignature(next);
    if (signature !== watchSignatureRef.current) {
      watchSignatureRef.current = signature;
      setWatchSnapshot(next);
    }
    const nextManualEmpty = localStorage.getItem(MANUAL_EMPTY_KEY) === '1';
    setManualEmpty((current) => current === nextManualEmpty ? current : nextManualEmpty);
  }, []);

  useEffect(() => {
    window.addEventListener('storage', refreshSnapshot);
    window.addEventListener('focus', refreshSnapshot);
    window.addEventListener('kite-watchlist-storage-sync', refreshSnapshot);
    return () => {
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

  const addMissingPositions = useCallback((items: WatchItem[] = positionItems) => {
    const current = readWatchlist();
    const existing = new Set(current.map((item) => item.symbol));
    const missing = items.filter((item) => !existing.has(item.symbol));
    if (missing.length === 0) {
      const signature = watchSignature(current);
      if (signature !== watchSignatureRef.current) {
        watchSignatureRef.current = signature;
        setWatchSnapshot(current);
      }
      return false;
    }
    const next = dedupeItems([...current, ...missing]);
    watchSignatureRef.current = watchSignature(next);
    writeWatchlist(next);
    localStorage.removeItem(MANUAL_EMPTY_KEY);
    setManualEmpty(false);
    setWatchSnapshot(next);
    setChildKey((key) => key + 1);
    return true;
  }, [positionItems]);

  const refreshAndSyncPositions = useCallback(async () => {
    setManualRefreshing(true);
    try {
      const result = await positions.refetch();
      let items = positionsToWatchItems(result.data);
      if (items.length === 0) {
        const synced = await watchlistSync.mutateAsync();
        items = syncItemsToPositionWatchItems(synced.items as any[]);
      }
      addMissingPositions(items);
    } finally {
      setManualRefreshing(false);
    }
  }, [addMissingPositions, positions, watchlistSync]);

  const handleShellInput = useCallback((event: React.FormEvent<HTMLDivElement>) => {
    const target = event.target as HTMLInputElement | null;
    if (target?.tagName === 'INPUT' && target.placeholder === 'Search') {
      setSearchActive(target.value.trim().length > 0);
    }
  }, []);

  const rewriteLegacyHoldingsButton = useCallback(() => {
    const root = document.querySelector('.kite-watchlist-sync-shell');
    if (!root) return;
    root.querySelectorAll('button').forEach((button) => {
      if (button.textContent?.trim() === 'Sync holdings from Kite') {
        button.textContent = 'Sync open positions from Kite';
      }
    });
  }, []);

  useEffect(() => {
    rewriteLegacyHoldingsButton();
    const root = document.querySelector('.kite-watchlist-sync-shell');
    if (!root || typeof MutationObserver === 'undefined') return;
    const observer = new MutationObserver(rewriteLegacyHoldingsButton);
    observer.observe(root, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [childKey, rewriteLegacyHoldingsButton, watchSnapshot.length]);

  const handleShellClick = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    const button = target?.closest('button');
    if (button?.textContent?.trim() === 'Sync holdings from Kite') {
      event.preventDefault();
      event.stopPropagation();
      void refreshAndSyncPositions();
    }
  }, [refreshAndSyncPositions]);

  const freshEmptyBoot = !hadWatchStorageOnMount && !manualEmpty;
  useEffect(() => {
    if (!freshEmptyBoot || autoSeededRef.current || positions.isLoading || positions.isFetching || watchlistSync.isPending) return;
    autoSeededRef.current = true;
    void refreshAndSyncPositions().finally(() => setAutoAttempted(true));
  }, [freshEmptyBoot, positions.isFetching, positions.isLoading, refreshAndSyncPositions, watchlistSync.isPending]);

  const watchedSymbols = useMemo(() => new Set(watchSnapshot.map((item) => item.symbol)), [watchSnapshot]);
  const missingPositions = useMemo(
    () => positionItems.filter((item) => !watchedSymbols.has(item.symbol)),
    [positionItems, watchedSymbols],
  );

  const refreshing = manualRefreshing || positions.isLoading || positions.isFetching || watchlistSync.isPending;
  const hasSyncError = positions.isError || watchlistSync.isError;
  const syncTitle = refreshing
    ? 'Refreshing Kite open positions…'
    : missingPositions.length > 0
      ? `Refresh and sync ${missingPositions.length} missing open position${missingPositions.length === 1 ? '' : 's'}`
      : hasSyncError
        ? 'Retry Kite open positions refresh'
        : 'Refresh Kite open positions';
  const showEmptyPrompt = watchSnapshot.length === 0 && !searchActive && (manualEmpty || autoAttempted || hasSyncError);
  const hideDefaultEmptyPrompt = watchSnapshot.length === 0 && !searchActive;

  if (freshEmptyBoot && !autoAttempted && !hasSyncError) {
    return (
      <div style={{ height: '100%', background: t.bg, color: t.dim, fontFamily: t.fontFamily, display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: 50, borderBottom: `1px solid ${t.border}` }} />
        <div style={{ padding: 24, fontSize: 12 }}>Syncing Kite open positions…</div>
      </div>
    );
  }

  return (
    <div
      className="kite-watchlist-sync-shell"
      style={{ position: 'relative', height: '100%' }}
      onInputCapture={handleShellInput}
      onChangeCapture={handleShellInput}
      onClickCapture={handleShellClick}
    >
      <style>{`
        .kite-watchlist-sync-shell div:has(> input[placeholder="Search"]) > div:last-child { margin-right: 36px; }
        @keyframes kitePositionsRefreshSpin { to { transform: rotate(360deg); } }
      `}</style>
      <SterlingWatchList key={childKey} onOpenInstrument={onOpenInstrument} />
      {hideDefaultEmptyPrompt && (
        <div aria-hidden style={{ position: 'absolute', top: 50, left: 0, right: 0, bottom: 0, zIndex: 15, background: t.bg, pointerEvents: 'none' }} />
      )}
      {showEmptyPrompt && (
        <div style={{ position: 'absolute', top: 50, left: 0, right: 0, bottom: 0, zIndex: 20, padding: 32, textAlign: 'center', color: t.dim, fontSize: 13, background: t.bg }}>
          <p style={{ marginBottom: 16 }}>Nothing here.</p>
          <p>Use the search bar to add instruments.</p>
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void refreshAndSyncPositions()}
            style={{ marginTop: 24, padding: '8px 16px', background: t.surface, border: `1px solid ${t.border}`, borderRadius: 4, color: t.blue, cursor: refreshing ? 'wait' : 'pointer', fontSize: 13 }}
          >
            {refreshing ? 'Syncing…' : 'Sync open positions from Kite'}
          </button>
        </div>
      )}
      <div style={{ position: 'absolute', top: 13, right: 10, zIndex: 25, display: 'inline-flex', alignItems: 'center' }}>
        <button
          type="button"
          title={syncTitle}
          aria-label="Refresh open positions from Kite"
          aria-busy={refreshing}
          onClick={(event) => { event.stopPropagation(); void refreshAndSyncPositions(); }}
          style={{ width: 24, height: 24, padding: 0, borderRadius: 4, border: 'none', background: 'transparent', color: t.blue, opacity: 1, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <span style={{ display: 'inline-flex', animation: refreshing ? 'kitePositionsRefreshSpin 0.8s linear infinite' : undefined }}>
            <SyncPositionsIcon />
          </span>
        </button>
      </div>
    </div>
  );
}
