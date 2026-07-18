import React, { useState, useEffect, useRef, useCallback } from 'react';
import { k, Icons, tint } from '../../styles/kiteUI';
import { useCandles } from '../../hooks/useCandles';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { useKitePositions } from '../../hooks/useKite';
import { useKiteOptionChain } from '../../hooks/useKiteOptionChain';
import { api } from '../../utils/api';
import { heikinAshi, type Candle } from '../../utils/indicators';
import { useKiteDrawings, Drawing } from '../../hooks/useKiteDrawings';
import { TradingViewKiteChart } from '../charts/TradingViewKiteChart';
import { OIView } from './OIView';
import { KiteLoader } from './KiteLoader';

export type InstrumentTab = 'chart' | 'option-chain' | 'fundamentals' | 'oi-change' | 'open-interest';

// Stable (never-recreated) empty-array reference for the initial useKiteDrawings
// seed below. useKiteDrawings resyncs its internal state whenever the identity
// of `initialDrawings` changes (see useKiteDrawings.ts), so passing a fresh `[]`
// literal here on every render would wipe drawings state on every unrelated
// re-render instead of only on an actual symbol-driven reset.
const EMPTY_DRAWINGS: Drawing[] = [];

// ── Global chart configuration ───────────────────────────────────────────────
// The chart config (timeframe, indicators, params, toggles, zoom) is shared
// across EVERY symbol - switching symbols must keep the same view ("same
// throughout"), not reset to per-symbol defaults. Only drawing geometry stays
// keyed by symbol (a trendline at NIFTY 23900 is meaningless on BANKNIFTY
// 51000), carried inside the one global blob under `drawingsBySymbol`.
const GLOBAL_CHART_KEY = '__global__';

// Module-level cache of the loaded global blob for this page session. It is
// populated by the first GET and then updated SYNCHRONOUSLY on every save, so
// that Mac motion mode's MacSectionFade REMOUNT of the pane on a symbol switch
// re-seeds the fresh pane from current in-memory state (via the lazy useState
// initializers below) instead of racing a fresh GET against the just-flushed
// POST on the same key. On a hard page reload it starts null and is re-fetched.
let globalChartStateCache: any = null;

// Test-only: clear the module-level session cache so each test starts cold.
export function __resetGlobalChartStateCache() { globalChartStateCache = null; }

interface InstrumentPaneProps {
  symbol: string;
  initialTab?: InstrumentTab;
  onSymbolChange?: (symbol: string) => void;
  trailTarget?: 'fast' | 'mid' | 'slow';
  signalData?: { timestamp_ms: number; direction: string; regime: string };
}

const TABS: { id: InstrumentTab; label: string; badge?: string }[] = [
  { id: 'chart', label: 'Chart' },
  { id: 'option-chain', label: 'Option chain' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'oi-change', label: 'OI Change', badge: 'NEW' },
  { id: 'open-interest', label: 'Open Interest', badge: 'NEW' },
];

export function InstrumentPane({ symbol, initialTab = 'chart', onSymbolChange, trailTarget, signalData }: InstrumentPaneProps) {
  const [tab, setTab] = useState<InstrumentTab>(initialTab);

  useEffect(() => {
    setTab(initialTab);
  }, [symbol, initialTab]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, overflow: 'hidden', fontFamily: k.fontFamily }}>
      {/* ── Tabs ── */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${k.border}`, background: k.bg }}>
        {TABS.map((tItem) => (
          <div
            key={tItem.id}
            onClick={() => setTab(tItem.id)}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: tab === tItem.id ? 500 : 400,
              color: tab === tItem.id ? k.orange : k.dim,
              borderBottom: tab === tItem.id ? `2px solid ${k.orange}` : '2px solid transparent',
              transition: 'color 0.2s',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              whiteSpace: 'nowrap',
            }}
          >
            {tItem.label}
            {tItem.badge && (
              <span style={{ background: k.orange, color: '#fff', fontSize: 8, fontWeight: 700, letterSpacing: 0.3, padding: '1px 4px', borderRadius: 3, lineHeight: 1.4 }}>
                {tItem.badge}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'chart' && <ChartView symbol={symbol} onSymbolChange={onSymbolChange} trailTarget={trailTarget} signalData={signalData} />}
        {tab === 'option-chain' && <OptionChainView symbol={symbol} />}
        {tab === 'oi-change' && <OIView symbol={symbol} mode="change" />}
        {tab === 'open-interest' && <OIView symbol={symbol} mode="total" />}
        {tab === 'fundamentals' && (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim }}>Fundamentals data not available.</div>
        )}
      </div>
    </div>
  );
}

// ─── Chart View ─────────────────────────────────────────────────────────────

type IndicatorKey = 'ema' | 'bb' | 'st-fast' | 'st-mid' | 'st-slow' | 'vwap' | 'vol' | 'rsi' | 'macd';

const ALL_TFS = ['1m', '5m', '15m', '30m', '1H', '4H', 'D'];
const INDICATOR_LABELS: Record<IndicatorKey, string> = {
  ema: 'EMA',
  bb: 'BB',
  'st-fast': 'ST Fast (21,1)',
  'st-mid': 'ST Mid (14,2)',
  'st-slow': 'ST Slow (7,3)',
  vwap: 'VWAP',
  vol: 'Volume',
  rsi: 'RSI',
  macd: 'MACD',
};

function ChartView({ symbol, onSymbolChange, trailTarget, signalData }: { symbol: string; onSymbolChange?: (symbol: string) => void; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: { timestamp_ms: number; direction: string; regime: string } }) {
  // Default active-indicator set: when opened with a trailTarget (from a signal
  // row) the matching SuperTrend variant is active by default instead of the
  // plain-watchlist default of st-mid. trailTarget undefined (normal watchlist
  // open) resolves to 'st-mid', identical to the prior hardcoded behavior.
  const defaultActiveSet = (target?: 'fast' | 'mid' | 'slow', forSignal?: boolean): Set<IndicatorKey> => {
    // Opened from a signal row: show ALL three SuperTrends so the full 3-line
    // alignment the engine keys off is visible, not just one variant.
    if (forSignal) return new Set<IndicatorKey>(['vol', 'st-fast', 'st-mid', 'st-slow']);
    const stKey: IndicatorKey = target === 'fast' ? 'st-fast' : target === 'slow' ? 'st-slow' : 'st-mid';
    return new Set<IndicatorKey>(['vol', stKey]);
  };

  // The engine evaluates entries on 1H Heikin-Ashi candles. When the chart is
  // opened from a signal row, default to that same view so the SuperTrends and the
  // Entry marker match what the engine actually saw; plain watchlist opens keep the
  // lighter 15m/raw default.
  // Config state seeds from the global cache for a plain (watchlist) open so a
  // Mac-mode remount on symbol switch re-appears with the same view. A signal
  // open ignores the cache and forces the engine's 1H Heikin-Ashi view (and does
  // not persist - see the signalData guard in saveChartState).
  const [tf, setTf] = useState(() => (signalData ? '1H' : (globalChartStateCache?.tf ?? '15m')));
  const [active, setActive] = useState<Set<IndicatorKey>>(() => {
    if (signalData) return defaultActiveSet(trailTarget, true);
    const cached = globalChartStateCache?.active;
    return Array.isArray(cached) && cached.length ? new Set(cached) : defaultActiveSet(trailTarget, false);
  });
  const [isHA, setIsHA] = useState(() => (signalData ? true : (globalChartStateCache?.isHA ?? false)));
  const [isDark, setIsDark] = useState(false);

  const getSTParams = (target?: 'fast' | 'mid' | 'slow') => {
    switch (target) {
      case 'fast': return { stPeriod: 21, stMult: 1 };
      case 'mid': return { stPeriod: 14, stMult: 2 };
      case 'slow': return { stPeriod: 7, stMult: 3 };
      default: return { stPeriod: 10, stMult: 3 };
    }
  };

  // The full default indicator-params object for a given trail target. Factored
  // out of the useState initializer so the symbol-change effect can reset params
  // to these same defaults - otherwise the previous symbol's params leak into the
  // next symbol and get persisted onto it (the load merges over whatever params
  // are currently in state).
  const buildDefaultParams = (target?: 'fast' | 'mid' | 'slow') => ({
    ema1: 9, ema2: 21,
    bbPeriod: 20, bbStd: 2,
    ...getSTParams(target),
    // Per-variant SuperTrend period/multiplier (the chart shows fast/mid/slow
    // simultaneously, so each needs its own pair - the single stPeriod/stMult
    // above is legacy/unused by the chart, kept as-is for compatibility).
    stFastPeriod: 21, stFastMult: 1,
    stMidPeriod: 14, stMidMult: 2,
    stSlowPeriod: 7, stSlowMult: 3,
    rsiPeriod: 14,
    macdFast: 12, macdSlow: 26, macdSig: 9,
  });

  const [params, setParams] = useState(() =>
    signalData
      ? buildDefaultParams(trailTarget)
      : {
          ...buildDefaultParams(trailTarget),
          ...((globalChartStateCache?.params ?? {}) as Partial<ReturnType<typeof buildDefaultParams>>),
        }
  );
  const [showVP, setShowVP] = useState(() => (signalData ? false : (globalChartStateCache?.showVP ?? false)));
  const [isLogScale, setIsLogScale] = useState(() => (signalData ? false : (globalChartStateCache?.isLogScale ?? false)));

  // `useCandles` inherits the app-wide `placeholderData: keepPreviousData` query
  // default (App.tsx) - it exists so background refetches on the SAME symbol/tf
  // don't blank the chart, but it has a side effect here: on a genuine symbol
  // switch (a different query key), react-query serves the OUTGOING symbol's
  // candles as a "placeholder" for the incoming key and reports isLoading=false
  // (there IS data, just stale) - so `candlesLoading` never goes true and the
  // switch loader below would hide immediately, letting the previous symbol's
  // fully-rendered chart sit on screen until the real fetch lands moments later.
  // `isPlaceholderData` is the one flag that's true specifically during that
  // window; it must gate the loader alongside isLoading/isSwitching.
  const { data: rawCandles = [], isLoading: candlesLoading, isPlaceholderData: candlesArePlaceholder } = useCandles(symbol, tf, 800);
  const { data: kitePosData } = useKitePositions();

  // ── Switch loader ────────────────────────────────────────────────────────
  // Visible from the moment the user picks a different instrument or timeframe
  // until the chart has actually finished its (expensive) rebuild - covers both
  // the network wait for fresh candles AND the synchronous createChart()+
  // indicator-recompute work that follows, which is what made a switch feel
  // "stuck" rather than just slow. Adjust state during render (React's
  // documented pattern for "reset state when a prop changes") so the overlay
  // appears on the very same paint as the new instrument, not one frame late.
  const instrumentKey = `${symbol}|${tf}`;
  const [renderedInstrumentKey, setRenderedInstrumentKey] = useState(instrumentKey);
  // Starts true: the very first chart build is exactly as expensive as a later
  // switch, so the initial mount waits for the same onChartReady signal.
  const [isSwitching, setIsSwitching] = useState(true);
  if (instrumentKey !== renderedInstrumentKey) {
    setRenderedInstrumentKey(instrumentKey);
    setIsSwitching(true);
  }
  const handleChartReady = useCallback(() => setIsSwitching(false), []);
  useEffect(() => {
    if (!isSwitching) return;
    // Safety net: never let the overlay get stuck (failed fetch, disabled
    // layoutMode, etc.) - the same ceiling a slow mobile connection would hit.
    const t = setTimeout(() => setIsSwitching(false), 6000);
    return () => clearTimeout(t);
  }, [isSwitching, instrumentKey]);
  const showChartLoader = isSwitching || candlesArePlaceholder || (candlesLoading && rawCandles.length === 0);

  // Refs and low-level chart instances now inside <TradingViewKiteChart> shared component
  // (no direct access needed at this level)

  const candles = React.useMemo(() => {
    const valid = rawCandles.filter((c: any) => c.time != null && !isNaN(c.time));
    return [...valid].sort((a: any, b: any) => a.time - b.time)
      .filter((v: any, i: number, a: any[]) => i === 0 || v.time !== a[i - 1].time);
  }, [rawCandles]);

  const baseCandles = React.useMemo(() => {
    return isHA ? heikinAshi(candles as Candle[]) : (candles as Candle[]);
  }, [candles, isHA]);

  const theme = React.useMemo(() => {
    if (!isDark) return k;
    return {
      ...k,
      bg: '#0d1117',
      surface: '#161b22',
      surfaceHover: '#21262d',
      border: '#30363d',
      text: '#c9d1d9',
      dim: '#8b949e',
      blue: '#58a6ff',
      red: '#f85149',
      green: '#3fb950',
      amber: '#d29922',
      orange: '#f0883e',
      cyan: '#39c5cf',
      purple: '#a371f7',
    };
  }, [isDark]);

  // Simple position for current symbol (approx match)
  const symbolPos = React.useMemo(() => {
    const nets = (kitePosData as any)?.net || [];
    if (!nets.length) return null;
    const shortSym = (symbol.split(':').pop() || symbol).toUpperCase();
    return nets.find((p: any) => 
      (p.tradingsymbol || '').toUpperCase().includes(shortSym) ||
      (p.symbol || '').toUpperCase().includes(shortSym)
    ) || null;
  }, [kitePosData, symbol]);

  // Drawings via shared hook (for persist integration)
  const {
    drawings,
    setDrawings,
    drawMode,
    setDrawMode,
    drawingPoints,
    setDrawingPoints,
    selectedDrawingId,
    setSelectedDrawingId,
    isDragging,
    clearDrawings: hookClear,
  } = useKiteDrawings({ initialDrawings: EMPTY_DRAWINGS, onChange: (d) => { /* parent sees via prop */ } });

  // Proper debounced save for backend (always a function)
  const saveTimeoutRef = useRef<any>(null);
  const saveChartStateRef = useRef<any>(null);
  // Last known visible-range (zoom) - GLOBAL, not per-symbol. The backend does a
  // full replace, so a save that omits zoom (any config/drawing change) would
  // persist zoom:null and wipe the stored zoom. We remember the live range here
  // (seeded from the loaded/cached state, updated on pan/zoom) and use it as the
  // zoom default so non-zoom saves keep the existing zoom. NOT reset on symbol
  // change - the same visible window carries to the next symbol ("same throughout").
  const lastZoomRef = useRef<any>(signalData ? null : (globalChartStateCache?.zoom ?? null));
  // The concrete POST to run when the debounce fires, captured with THIS
  // symbol + payload. Kept in a ref so we can also fire it *immediately*
  // (flushSave) when the pane is about to stop tracking the current symbol -
  // on a symbol switch or unmount - instead of letting the pending timer be
  // silently cancelled, which used to drop the just-made change. The optional
  // `keepalive` arg is set from the page-unload path so the POST survives the
  // tab closing (see the pagehide/visibilitychange effect below).
  const pendingSaveRef = useRef<null | ((keepalive?: boolean) => void)>(null);
  // Per-symbol drawing geometry for the single GLOBAL chart-state blob. Seeded
  // from the mount load; the current symbol's entry is kept in sync on every save.
  const drawingsBySymbolRef = useRef<Record<string, Drawing[]>>(
    (globalChartStateCache?.drawingsBySymbol && typeof globalChartStateCache.drawingsBySymbol === 'object')
      ? globalChartStateCache.drawingsBySymbol : {}
  );
  // Symbol the swap-effect last handled, so it no-ops on initial mount (the mount
  // load applies the initial symbol's drawings) and swaps only on a real change.
  const prevSymbolRef = useRef<string>(symbol);

  const saveChartState = useCallback((zoomArg?: any, drawingsArg?: any) => {
    // Signal opens are a transient engine-view; they must never overwrite the
    // user's shared global config (opening a signal would otherwise persist its
    // 1H/HA view onto every symbol).
    if (signalData) return;
    const nextDrawings = drawingsArg ?? drawings;
    const drawingsBySymbol = { ...drawingsBySymbolRef.current, [symbol]: nextDrawings };
    drawingsBySymbolRef.current = drawingsBySymbol;
    const payload = {
      zoom: zoomArg ?? lastZoomRef.current ?? null,
      drawingsBySymbol,
      tf,
      active: Array.from(active),
      isHA,
      isLogScale,
      showVP,
      params,
    };
    // Keep the session cache current SYNCHRONOUSLY so a Mac-mode remount that
    // happens before the debounced POST lands still re-seeds from this state.
    globalChartStateCache = payload;
    const doPost = (keepalive = false) => {
      saveTimeoutRef.current = null;
      pendingSaveRef.current = null;
      api.post(
        `/api/v1/kite/chart-state/${GLOBAL_CHART_KEY}`,
        payload,
        keepalive ? { keepalive: true } : undefined,
      ).catch((err) => {
        console.error('Failed to save chart state:', err);
      });
    };
    pendingSaveRef.current = doPost;
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => doPost(), 700);
  }, [drawings, symbol, tf, active, isHA, isLogScale, showVP, params, signalData]);

  // Fire any pending debounced save immediately. Called when the pane leaves the
  // current symbol (symbol switch or unmount). Without it, switching symbols
  // within the 700ms debounce window dropped the outgoing symbol's save two ways:
  // (a) the incoming symbol's load schedules its own save whose clearTimeout
  // cancels the still-pending one, and (b) in Mac motion mode MacSectionFade
  // remounts the pane, whose unmount cleanup cleared the timer. Flushing POSTs
  // the outgoing symbol's state before either can happen. doPost captured the
  // outgoing symbol + payload, so this always saves to the correct endpoint.
  const flushSave = useCallback((keepalive = false) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }
    if (pendingSaveRef.current) {
      const run = pendingSaveRef.current;
      pendingSaveRef.current = null;
      run(keepalive);
    }
  }, []);

  useEffect(() => {
    saveChartStateRef.current = saveChartState;
  }, [saveChartState]);

  // Persisted state from backend (zoom + drawings per symbol)
  // (Declared before handleZoomChange/handleDrawingsChange below since those
  // callbacks close over chartStateLoaded — TS block-scoping requires the
  // declaration to precede any use, even inside a different callback.)
  const [persistedZoom, setPersistedZoom] = useState<any>(() => (signalData ? null : (globalChartStateCache?.zoom ?? null)));
  // When the cache is already populated (a remount within this page session), the
  // lazy initializers above have fully seeded config, so saves can start
  // immediately. Only a cold first mount must wait for the GET below.
  const [chartStateLoaded, setChartStateLoaded] = useState(() => !signalData && !!globalChartStateCache);
  // True once we KNOW the final persistedZoom value for this pane instance -
  // either synchronously (signal open, or the cache already had it) or once the
  // chart-state GET below has settled (success or failure). Gates the chart's
  // FIRST mount below: mounting before this resolves let TradingViewKiteChart's
  // very first createChart() call fitContent() to a default range, then a split
  // second later (once the GET resolved with a saved zoom) rebuild again to
  // setVisibleRange() the real one - the "loads at one zoom, snaps to another"
  // bug. Waiting here means the first-ever createChart() already has the right
  // range baked in, so there's only ever one build, not two.
  const [zoomResolved, setZoomResolved] = useState(() => !!signalData || !!globalChartStateCache);

  // Stable identities for the callbacks passed into TradingViewKiteChart.
  // These used to be inline arrow functions recreated on every InstrumentPane
  // render, which fed straight into the chart's giant chart-creation useEffect
  // dep array (via the `onZoomChange`/`onDrawingsChange` props) and forced
  // that effect (chart.remove() + createChart(...)) to re-run far more often
  // than the underlying data actually changed.
  const handleZoomChange = useCallback((range: any) => {
    lastZoomRef.current = range;
    if (chartStateLoaded) saveChartState(range);
  }, [chartStateLoaded, saveChartState]);

  const handleDrawingsChange = useCallback((d: Drawing[]) => {
    setDrawings(d);
    if (chartStateLoaded) saveChartState(undefined, d);
  }, [chartStateLoaded, saveChartState, setDrawings]);

  useEffect(() => {
    // On unmount (incl. Mac-mode MacSectionFade remount on symbol switch), flush
    // the pending save instead of dropping it, so a change made <700ms before the
    // switch still reaches the backend for the outgoing symbol.
    return () => { flushSave(); };
  }, [flushSave]);

  useEffect(() => {
    // A hard page unload - tab close, refresh, or browser navigation away - does
    // NOT run React unmount, so the flush above never fires and a change made
    // within the 700ms debounce window is lost. Flush on the unload signals
    // instead. `pagehide` covers close/refresh/navigation (and bfcache); the
    // `visibilitychange`->hidden check is the reliable mobile/bfcache signal
    // where pagehide/beforeunload are unreliable. We flush with keepalive so the
    // POST survives the unload - a normal fetch would be cancelled mid-flight.
    // flushSave nulls the pending save after running, so whichever signal fires
    // first wins and the other is a no-op (no double POST).
    const flushOnUnload = () => { flushSave(true); };
    const flushIfHidden = () => {
      if (document.visibilityState === 'hidden') flushSave(true);
    };
    window.addEventListener('pagehide', flushOnUnload);
    document.addEventListener('visibilitychange', flushIfHidden);
    return () => {
      window.removeEventListener('pagehide', flushOnUnload);
      document.removeEventListener('visibilitychange', flushIfHidden);
    };
  }, [flushSave]);

  // TradingView-style current bar info (OHLC + indicators)
  const [currentBarInfo, setCurrentBarInfo] = useState<any>(null);

  // ── Mount: load the GLOBAL chart config ONCE per pane instance ──────────────
  // Config is shared across symbols, so it is NOT reloaded/reset on symbol change
  // (that reset was the "config wiped on symbol switch" bug). On a cold first
  // mount the session cache is null and we GET it; a remount within the session
  // (incl. Mac-mode MacSectionFade on a symbol switch) already seeded every config
  // field from the cache via the lazy useState initializers, so we only apply
  // this symbol's drawings and enable saves.
  useEffect(() => {
    if (signalData) return;   // signal opens keep the engine view; nothing to load/persist
    let cancelled = false;
    const applyDrawingsFor = (map: Record<string, Drawing[]>, sym: string) => {
      drawingsBySymbolRef.current = map;
      setDrawings(Array.isArray(map[sym]) ? map[sym] : []);
    };
    if (globalChartStateCache) {
      applyDrawingsFor(globalChartStateCache.drawingsBySymbol ?? {}, symbol);
      setChartStateLoaded(true);
      return;
    }
    (async () => {
      try {
        const res: any = await api.get(`/api/v1/kite/chart-state/${GLOBAL_CHART_KEY}`);
        if (!cancelled && res) {
          if (res.tf !== undefined && res.tf !== null) setTf(res.tf);
          if (Array.isArray(res.active) && res.active.length > 0) setActive(new Set(res.active));
          if (typeof res.isHA === 'boolean') setIsHA(res.isHA);
          if (typeof res.isLogScale === 'boolean') setIsLogScale(res.isLogScale);
          if (typeof res.showVP === 'boolean') setShowVP(res.showVP);
          // Only seed the saved zoom if the user hasn't already panned/zoomed
          // the live chart while this GET was in flight - lastZoomRef is set
          // by handleZoomChange the instant the user interacts, and applying
          // the (older) fetched value over that would silently undo their pan
          // a few seconds after they made it.
          if (res.zoom && lastZoomRef.current == null) { setPersistedZoom(res.zoom); lastZoomRef.current = res.zoom; }
          if (res.params && typeof res.params === 'object') setParams({ ...buildDefaultParams(trailTarget), ...res.params });
          const map = (res.drawingsBySymbol && typeof res.drawingsBySymbol === 'object') ? res.drawingsBySymbol : {};
          globalChartStateCache = res;
          applyDrawingsFor(map, symbol);
        }
        // The final zoom value is known now (whatever was seeded above, or still
        // null if this instrument had none saved) - safe to mount the real chart.
        if (!cancelled) setZoomResolved(true);
      } catch (e) {
        console.error('Failed to load chart state:', e);
        // GET failed: we do NOT know the real stored state, so leave persistence
        // disabled (chartStateLoaded stays false). Flipping it true here would
        // fire the save-on-change effects with DEFAULT config and clobber the
        // real saved global state (the backend POST is a full replace). The
        // session cache stays null too, so a pane remount re-runs this GET and
        // recovers once the backend is reachable again.
        // zoomResolved, however, is safe (and necessary) to flip regardless -
        // it only gates the chart's first mount, not persistence, and the
        // chart must still render (at a default fit) even when the backend
        // is unreachable rather than stay hidden behind the loader forever.
        if (!cancelled) setZoomResolved(true);
        return;
      }
      if (!cancelled) setChartStateLoaded(true);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);   // once per pane instance

  // ── Symbol change: swap drawings + carry zoom (NO config reset, NO reload) ──
  useEffect(() => {
    if (prevSymbolRef.current === symbol) return;   // initial mount handled by the load effect
    prevSymbolRef.current = symbol;
    if (signalData) return;
    // Per-symbol drawings: show this symbol's saved geometry (empty if none).
    setDrawings(Array.isArray(drawingsBySymbolRef.current[symbol]) ? drawingsBySymbolRef.current[symbol] : []);
    // Carry the live visible window to the new symbol so zoom is "same throughout";
    // the chart re-applies a non-null persistedZoom on an instrument switch (see
    // the apply-view block in TradingViewKiteChart).
    if (lastZoomRef.current) setPersistedZoom(lastZoomRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  // Save drawings when they change (outside of click path) - use ref to get latest fn
  useEffect(() => {
    if (chartStateLoaded && saveChartStateRef.current) {
      saveChartStateRef.current(undefined, drawings);
    }
  }, [drawings, chartStateLoaded]);

  // Save other config when they change (tf, indicators, toggles, params)
  useEffect(() => {
    if (chartStateLoaded && saveChartStateRef.current) {
      saveChartStateRef.current();
    }
  }, [tf, active, isHA, isLogScale, showVP, params, chartStateLoaded]);

  const toggleIndicator = (key: IndicatorKey) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Chart rendering fully delegated to shared <TradingViewKiteChart>
  // (includes candles, all indicators, drawings, VP full histo, drag handles, subpanes, precise crosshair, snap)
  // We keep only persistence + control state here.

  // Sub-panes + sync logic now inside TradingViewKiteChart (delegated)

  // Drawing state (drag helpers) kept minimal - delegated to shared TradingViewKiteChart + useKiteDrawings
  // (old snap/find/mouse fns removed; logic lives in shared component + hook)

  // Simple param quick adjust (for demo; full popover could be added)
  const updateParam = (key: keyof typeof params, delta: number) => {
    setParams(p => ({ ...p, [key]: Math.max(1, Math.round((p[key] as number) + delta)) }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: theme.fontFamily, overflow: 'hidden' }}>
      {/* Parent control toolbar (tf, indicators, HA, dark, log, vp, param tweaks) - drawing tools live inside shared chart */}
      {/* Minimal header - full TV UX is inside the shared TradingViewKiteChart component */}
      <div style={{ padding: '2px 8px', borderBottom: `1px solid ${theme.border}`, display: 'flex', gap: 6, alignItems: 'center', background: theme.bg, fontSize: 10, color: theme.dim }}>
        <span style={{ fontWeight: 500 }}>{symbol.split(':')[1] || symbol}</span>
        <span style={{ marginLeft: 'auto', fontSize: 9 }}>{baseCandles.length} bars {isHA ? 'HA' : ''}</span>
      </div>

      {/* The true shared advanced chart */}
      <div style={{ flex: 1, minHeight: 220, position: 'relative' }}>
        {/* Held back until the saved zoom (if any) is known - see zoomResolved
            above. Mounting earlier let the first createChart() default-fit,
            then rebuild moments later once the GET resolved with a real zoom -
            visible as "loads at one zoom, snaps to another" a beat later. */}
        {(signalData || zoomResolved) && (
          <TradingViewKiteChart
            symbol={symbol}
            rawCandles={rawCandles}
            tf={tf}
            isHA={isHA}
            isLogScale={isLogScale}
            isDark={isDark}
            theme={theme}
            activeIndicators={active}
            params={params}
            drawings={drawings}
            onDrawingsChange={handleDrawingsChange}
            onZoomChange={handleZoomChange}
            showVP={showVP}
            symbolPos={symbolPos}
            persistedZoom={persistedZoom}
            onTfChange={setTf}
            onIsHAChange={setIsHA}
            onIsLogScaleChange={setIsLogScale}
            onSymbolChange={onSymbolChange}
            onToggleIndicator={toggleIndicator as any}
            onParamsChange={setParams}
            signalData={signalData}
            onChartReady={handleChartReady}
          />
        )}
        {showChartLoader && (
          // Fully opaque (no `opacity` shorthand - that would composite this
          // whole layer, spinner included, at <100% and let the previous
          // symbol's chart bleed through underneath it). The user must never
          // see even a sliver of the outgoing chart while switching.
          <div
            style={{
              position: 'absolute', inset: 0, zIndex: 20,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10,
              background: theme.bg,
              pointerEvents: 'none',
            }}
          >
            <KiteLoader size={30} />
            <span style={{ fontSize: 11, color: theme.dim }}>Loading chart…</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Option Chain View ──────────────────────────────────────────────────────

type ViewMode = 'oi' | 'greeks';

/* ⚠️ PLACEHOLDER DATA — this chain is generated client-side to be NIFTY-shaped so
 * the layout is realistic. It is NOT live Kite data. Wire /api/v1/options/chain
 * (KiteClient.get_option_chain) + a live spot/quote feed to make it real. */
const SPOT = 23949.35;
const SPOT_CHANGE = -118.45;
const SPOT_PCT = -0.49;
const STRIKE_STEP = 50;
const ATM_STRIKE = Math.round(SPOT / STRIKE_STEP) * STRIKE_STEP; // 23950

const chg = (lo: number, hi: number) => Number((lo + Math.random() * (hi - lo)).toFixed(2));

function buildChain(expiryIdx: number) {
  const tMult = 1 + expiryIdx * 0.55;   // farther expiry → fatter premium / time value
  const oiScale = 1 + expiryIdx * 0.18; // farther expiry → different OI footprint
  const start = ATM_STRIKE - 11 * STRIKE_STEP;
  return Array.from({ length: 24 }).map((_, i) => {
    const strike = start + i * STRIKE_STEP;
    const isAtm = strike === ATM_STRIKE;
    const dist = Math.abs(strike - SPOT);
    const intrinsicC = Math.max(0, SPOT - strike);
    const intrinsicP = Math.max(0, strike - SPOT);
    const tv = Math.max(3, 90 - dist / 7) * tMult;          // time value peaks at ATM
    const iv = 11 + dist / 400;                              // vol smile
    const vega = Math.max(1.5, 12 - dist / 60);
    const gamma = Math.max(0.0002, 0.0014 - dist / 5_000_000);
    const theta = -3 - tv / 14;
    return {
      strike, isAtm,
      call: {
        ltp: (intrinsicC + tv).toFixed(2),
        ltpChg: chg(-48, -22),
        oi: (Math.random() * 480 * oiScale).toFixed(2),
        oiChg: chg(-20, 90),
        iv: iv.toFixed(2),
        delta: Math.max(0.02, Math.min(0.98, 0.5 + (SPOT - strike) / 700)).toFixed(2),
        theta: theta.toFixed(2), vega: vega.toFixed(2), gamma: gamma.toFixed(4),
      },
      put: {
        ltp: (intrinsicP + tv).toFixed(2),
        ltpChg: chg(20, 165),
        oi: (Math.random() * 320 * oiScale).toFixed(2),
        oiChg: chg(-28, 50),
        iv: iv.toFixed(2),
        delta: Math.max(-0.98, Math.min(-0.02, -0.5 + (SPOT - strike) / 700)).toFixed(2),
        theta: theta.toFixed(2), vega: vega.toFixed(2), gamma: gamma.toFixed(4),
      },
    };
  });
}

const EXPIRIES = [
  { label: '23 Jun', dte: '4 days', weekly: true },
  { label: '30 Jun', dte: '11 days', weekly: false },
  { label: '7 Jul', dte: '3 weeks', weekly: true },
];
const EXPIRY_DROPDOWN = ['14 Jul (4 weeks)', '21 Jul (5 weeks)', '28 Jul (6 weeks)'];

// One stable chain per expiry option (3 pills + 3 dropdown) so switching is visible.
const CHAINS = Array.from({ length: EXPIRIES.length + EXPIRY_DROPDOWN.length }).map((_, i) => buildChain(i));
const MAX_OIS = CHAINS.map((c) => Math.max(...c.flatMap((r) => [Number(r.call.oi), Number(r.put.oi)])));

const FOOTER_STATS = [
  { label: 'PCR', value: '0.68' },
  { label: 'Max Pain', value: '23950' },
  { label: 'ATM IV', value: '11.50' },
  { label: 'IV Percentile', value: '54.00 - High' },
];

// Toolbar icons (match Kite's link row)
const SettingsIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
);
const PopoutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
);

function OptionChainView({ symbol }: { symbol: string }) {
  const [viewMode, setViewMode] = useState<ViewMode>('oi');
  const [expiry, setExpiry] = useState(0);
  const [hoverRow, setHoverRow] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState<{ strike: number; side: 'call' | 'put'; top: number; left: number } | null>(null);

  const openOrderWindow = useOrderWindowStore(s => s.openOrderWindow);
  const { data: live } = useKiteOptionChain(symbol);

  const handleAction = (e: React.MouseEvent, type: 'call' | 'put', side: 'BUY' | 'SELL', row: any) => {
    e.stopPropagation();
    const isCall = type === 'call';
    const optSym = `${symbol.split(':')[1] || symbol}${row.strike}${isCall ? 'CE' : 'PE'}`; 
    const ltp = isCall ? Number(row.call.ltp) : Number(row.put.ltp);

    openOrderWindow({
      symbol: optSym,
      exchange: 'NFO',
      initialSide: side,
      initialQty: 15,
      lastPrice: ltp,
      lotSize: 15,
    });
  };

  const handleMenuClick = (e: React.MouseEvent, strike: number, side: 'call' | 'put') => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuOpen({ strike, side, top: rect.bottom + 4, left: rect.left });
  };

  useEffect(() => {
    const closeMenu = () => setMenuOpen(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const name = symbol.split(':')[1] || symbol;
  const linkStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', whiteSpace: 'nowrap' };
  const OI_GRID = '1.3fr 1.3fr 96px 1.3fr 1.3fr';
  const GREEKS_GRID = '1fr 1fr 1fr 1fr 1fr 132px 92px 132px 1fr 1fr 1fr 1fr 1fr';

  const Chg = ({ v }: { v: number | null }) => (
    v == null
      ? <span style={{ fontSize: 11.5, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>–</span>
      : <span style={{ fontSize: 11.5, color: v >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>{v.toFixed(2)}%</span>
  );
  const Val = ({ children }: { children: React.ReactNode }) => (
    <span style={{ color: k.text, fontVariantNumeric: 'tabular-nums', minWidth: 50, textAlign: 'inherit' }}>{children}</span>
  );

  // ── Data source: live per-symbol Kite chain when available, else placeholder ──
  const liveExpiries = live?.expiries ?? [];
  const isLive = !!(live && liveExpiries.length && live.chain);

  type RLeg = { ltp: string; oi: string; iv: string; delta: string; theta: string; vega: string; gamma: string; ltpChg: number | null; oiChg: number | null };
  type RRow = { strike: number; isAtm: boolean; call: RLeg; put: RLeg };
  const EMPTY_LEG: RLeg = { ltp: '–', oi: '0', iv: '–', delta: '–', theta: '–', vega: '–', gamma: '–', ltpChg: null, oiChg: null };
  const normLeg = (l: any): RLeg => {
    if (!l) return EMPTY_LEG;
    if (typeof l.ltp === 'string') return l as RLeg;   // placeholder rows already in shape
    return {
      ltp: Number(l.ltp).toFixed(2), oi: Number(l.oi).toFixed(2), iv: Number(l.iv).toFixed(2),
      delta: Number(l.delta).toFixed(2), theta: Number(l.theta).toFixed(2),
      vega: Number(l.vega).toFixed(2), gamma: Number(l.gamma).toFixed(4),
      ltpChg: null, oiChg: null,
    };
  };

  const expiryPills = isLive
    ? liveExpiries.slice(0, 3).map((e) => ({ text: `${e.label} (${e.dte} ${e.dte === 1 ? 'day' : 'days'})`, weekly: false }))
    : EXPIRIES.map((e) => ({ text: `${e.label} (${e.dte})`, weekly: e.weekly }));
  const dropdownItems = isLive ? liveExpiries.slice(3).map((e) => `${e.label} (${e.dte} days)`) : EXPIRY_DROPDOWN;
  const pillCount = expiryPills.length;

  const optionCount = isLive ? liveExpiries.length : CHAINS.length;
  const selIdx = Math.min(expiry, Math.max(0, optionCount - 1));
  const rawRows: any[] = isLive ? (live!.chain[liveExpiries[selIdx]?.date] ?? []) : (CHAINS[selIdx] ?? CHAINS[0]);
  const rows: RRow[] = rawRows.map((r) => ({ strike: r.strike, isAtm: r.isAtm, call: normLeg(r.call), put: normLeg(r.put) }));
  const MAX_OI = Math.max(1, ...rows.map((r) => Math.max(Number(r.call.oi) || 0, Number(r.put.oi) || 0)));

  const spot = isLive ? live!.spot : SPOT;
  const spotChange = isLive ? null : SPOT_CHANGE;
  const spotPct = isLive ? null : SPOT_PCT;

  let footer = FOOTER_STATS;
  if (isLive) {
    const sumCall = rawRows.reduce((s, r) => s + (r.call?.oi || 0), 0);
    const sumPut = rawRows.reduce((s, r) => s + (r.put?.oi || 0), 0);
    const atmRow = rawRows.find((r) => r.isAtm);
    const atmIv = atmRow?.call?.iv ?? atmRow?.put?.iv;
    // Max pain = strike minimising total option-writer payout across the chain.
    let maxPain = '–', bestLoss = Infinity;
    for (const kRow of rawRows) {
      let loss = 0;
      for (const s of rawRows) {
        loss += (s.call?.oi || 0) * Math.max(0, kRow.strike - s.strike);
        loss += (s.put?.oi || 0) * Math.max(0, s.strike - kRow.strike);
      }
      if (loss < bestLoss) { bestLoss = loss; maxPain = String(kRow.strike); }
    }
    footer = [
      { label: 'PCR', value: sumCall > 0 ? (sumPut / sumCall).toFixed(2) : '–' },
      { label: 'Max Pain', value: maxPain },
      { label: 'ATM IV', value: atmIv != null ? Number(atmIv).toFixed(2) : '–' },
      { label: 'IV Percentile', value: '–' },
    ];
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', fontFamily: k.fontFamily, background: k.bg }}>
      {/* Instrument header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px 6px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ fontSize: 18, fontWeight: 600, color: '#333' }}>{name}</span>
          <span style={{ fontSize: 14, fontWeight: 500, color: (spotPct ?? 0) >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
            {spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {spotPct != null && spotChange != null && (
            <span style={{ fontSize: 13, color: spotPct >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              {spotPct >= 0 ? '+' : ''}{spotChange.toFixed(2)} ({spotPct >= 0 ? '+' : ''}{spotPct.toFixed(2)}%)
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: k.dim, cursor: 'pointer' }}>
          <span style={{ width: 16, height: 16, background: k.orange, borderRadius: 3, color: '#fff', fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>S</span>
          View on Sensibull
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 16px 12px', gap: 12 }}>
        {/* Expiries + OI/Greeks */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {expiryPills.map((e, idx) => (
            <span
              key={e.text}
              onClick={() => setExpiry(idx)}
              style={{
                fontSize: 12.5, cursor: 'pointer', padding: '5px 11px', borderRadius: 16, whiteSpace: 'nowrap',
                background: selIdx === idx ? '#e7f0fe' : 'transparent',
                color: selIdx === idx ? k.blue : k.text,
                fontWeight: selIdx === idx ? 500 : 400,
              }}
            >
              {e.text}{e.weekly && <sup style={{ fontSize: 8, color: k.dim, marginLeft: 1 }}>w</sup>}
            </span>
          ))}
          {dropdownItems.length > 0 && (
          <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
            <select
              value={selIdx >= pillCount ? selIdx - pillCount : -1}
              onChange={(ev) => setExpiry(pillCount + Number(ev.target.value))}
              style={{ appearance: 'none', background: k.bg, color: selIdx >= pillCount ? k.blue : k.text, border: `1px solid ${k.border}`, borderRadius: 6, padding: '5px 26px 5px 11px', fontSize: 12.5, outline: 'none', cursor: 'pointer', fontFamily: k.fontFamily }}
            >
              <option value={-1} disabled hidden>{dropdownItems[0]}</option>
              {dropdownItems.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
            <span style={{ position: 'absolute', right: 9, pointerEvents: 'none', color: k.dim, display: 'flex' }}><Icons.ChevronDown /></span>
          </div>
          )}
          <div style={{ width: 1, height: 18, background: k.border, margin: '0 8px' }} />
          <span onClick={() => setViewMode('oi')} style={{ fontSize: 12.5, cursor: 'pointer', padding: '5px 14px', borderRadius: 16, background: viewMode === 'oi' ? '#e7f0fe' : 'transparent', color: viewMode === 'oi' ? k.blue : k.text, fontWeight: viewMode === 'oi' ? 500 : 400 }}>OI</span>
          <span onClick={() => setViewMode('greeks')} style={{ fontSize: 12.5, cursor: 'pointer', padding: '5px 12px', borderRadius: 16, background: viewMode === 'greeks' ? '#e7f0fe' : 'transparent', color: viewMode === 'greeks' ? k.blue : k.dim, fontWeight: viewMode === 'greeks' ? 500 : 400 }}>Greeks</span>
        </div>

        {/* Right actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, color: k.blue, fontSize: 12.5 }}>
          <span style={linkStyle}><Icons.Search /> Search</span>
          <span style={linkStyle}><SettingsIcon /> Settings</span>
          <span style={linkStyle}><PopoutIcon /> Popout</span>
          <div style={{ width: 1, height: 18, background: k.border }} />
          <span style={{ ...linkStyle, color: k.dim }}><Icons.Basket /> Basket</span>
          <div style={{ width: 30, height: 16, borderRadius: 10, background: k.border, position: 'relative', cursor: 'pointer' }}>
            <div style={{ position: 'absolute', top: 2, left: 2, width: 12, height: 12, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.2)' }} />
          </div>
        </div>
      </div>

      {/* Table Header */}
      <div style={{ display: 'grid', gridTemplateColumns: viewMode === 'oi' ? OI_GRID : GREEKS_GRID, padding: '9px 16px', borderTop: `1px solid ${k.border}`, borderBottom: `1px solid ${k.border}`, fontSize: 11.5, color: k.dim, textAlign: 'center', background: k.bg }}>
        {viewMode === 'oi' ? (
          <>
            <div style={{ textAlign: 'right', paddingRight: 12 }}>OI (in lakhs)</div>
            <div style={{ textAlign: 'right', paddingRight: 14 }}>Call LTP</div>
            <div>Strike</div>
            <div style={{ textAlign: 'left', paddingLeft: 14 }}>Put LTP</div>
            <div style={{ textAlign: 'left', paddingLeft: 12 }}>OI (in lakhs)</div>
          </>
        ) : (
          <>
            <div style={{ textAlign: 'right' }}>Gamma</div>
            <div style={{ textAlign: 'right' }}>Vega</div>
            <div style={{ textAlign: 'right' }}>Theta</div>
            <div style={{ textAlign: 'right' }}>Delta</div>
            <div style={{ textAlign: 'right' }}>IV</div>
            <div style={{ textAlign: 'right', paddingRight: 16 }}>Call LTP</div>
            <div style={{ fontWeight: 500 }}>Strike</div>
            <div style={{ textAlign: 'left', paddingLeft: 16 }}>Put LTP</div>
            <div style={{ textAlign: 'left' }}>IV</div>
            <div style={{ textAlign: 'left' }}>Delta</div>
            <div style={{ textAlign: 'left' }}>Theta</div>
            <div style={{ textAlign: 'left' }}>Vega</div>
            <div style={{ textAlign: 'left' }}>Gamma</div>
          </>
        )}
      </div>

      {/* Table Body */}
      <div style={{ flex: 1, overflowY: 'auto', background: k.bg }}>
        {rows.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 13 }}>
            No option chain available. Connect a Kite account with an active session to load live data.
          </div>
        )}
        {rows.map((row) => {
          const isHover = hoverRow === row.strike;
          const itmCall = row.strike < spot;   // calls below spot are ITM (shade left)
          const itmPut = row.strike > spot;    // puts above spot are ITM (shade right)
          const callBar = Math.min(46, (Number(row.call.oi) / MAX_OI) * 46);
          const putBar = Math.min(46, (Number(row.put.oi) / MAX_OI) * 46);
          return (
              <div
              key={row.strike}
              onMouseEnter={() => setHoverRow(row.strike)}
              onMouseLeave={() => setHoverRow(null)}
              style={{
                display: 'grid',
                gridTemplateColumns: viewMode === 'oi' ? OI_GRID : GREEKS_GRID,
                padding: '0 16px',
                minHeight: 42,
                fontSize: 12.5,
                color: k.text,
                textAlign: 'center',
                alignItems: 'center',
                background: isHover ? k.surfaceHover : k.bg,
                position: 'relative',
              }}
            >
              {viewMode === 'oi' ? (
                <>
                  {/* ITM shading */}
                  {itmCall && <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: '50%', background: 'rgba(0,0,0,0.032)', pointerEvents: 'none', zIndex: 0 }} />}
                  {itmPut && <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', right: 0, background: 'rgba(0,0,0,0.032)', pointerEvents: 'none', zIndex: 0 }} />}
                  {/* OI bars (center-anchored) */}
                  <div style={{ position: 'absolute', left: 0, right: 0, bottom: 6, height: 2, pointerEvents: 'none', zIndex: 1 }}>
                    <div style={{ position: 'absolute', right: '50%', width: `${callBar}%`, height: 2, background: 'rgba(223,81,76,0.7)' }} />
                    <div style={{ position: 'absolute', left: '50%', width: `${putBar}%`, height: 2, background: 'rgba(76,175,80,0.75)' }} />
                  </div>

                  {/* Call OI: change + value */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 14, paddingRight: 12, zIndex: 2 }}>
                    <Chg v={row.call.oiChg} />
                    <Val>{row.call.oi}</Val>
                  </div>
                  {/* Call LTP: change + value */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 14, paddingRight: 14, position: 'relative', zIndex: 2 }}>
                    <Chg v={row.call.ltpChg} />
                    <Val>{row.call.ltp}</Val>
                    {isHover && (
                      <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center', zIndex: 3, boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }}>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'call')}><Icons.More /></button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button onClick={(e) => handleAction(e, 'call', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button onClick={(e) => handleAction(e, 'call', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                      </div>
                    )}
                  </div>
                  {/* Strike */}
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', borderLeft: `1px solid ${k.border}`, borderRight: `1px solid ${k.border}`, height: '100%', zIndex: 2 }}>
                    {row.isAtm ? (
                      <span style={{ background: '#3c3c3c', color: '#fff', fontWeight: 600, fontSize: 12.5, padding: '4px 11px', borderRadius: 4 }}>{row.strike}</span>
                    ) : (
                      <span style={{ fontWeight: 600, color: '#333', fontSize: 12.5 }}>{row.strike}</span>
                    )}
                  </div>
                  {/* Put LTP: value + change */}
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: 14, paddingLeft: 14, position: 'relative', zIndex: 2 }}>
                    {isHover && (
                      <div style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center', zIndex: 3, boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }}>
                        <button onClick={(e) => handleAction(e, 'put', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                        <button onClick={(e) => handleAction(e, 'put', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'put')}><Icons.More /></button>
                      </div>
                    )}
                    <Val>{row.put.ltp}</Val>
                    <Chg v={row.put.ltpChg} />
                  </div>
                  {/* Put OI: value + change */}
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: 14, paddingLeft: 12, zIndex: 2 }}>
                    <Val>{row.put.oi}</Val>
                    <Chg v={row.put.oiChg} />
                  </div>
                </>
              ) : (
                <>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.gamma}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.vega}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.theta}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.delta}</div>
                  <div style={{ textAlign: 'right', color: k.text }}>{row.call.iv}</div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10, paddingRight: 16, fontWeight: 500, position: 'relative' }}>
                    <Chg v={row.call.ltpChg} />
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>{row.call.ltp}</span>
                    {isHover && (
                      <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center' }}>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'call')}><Icons.More /></button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button onClick={(e) => handleAction(e, 'call', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button onClick={(e) => handleAction(e, 'call', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                      </div>
                    )}
                  </div>
                  <div style={{ fontWeight: 600, background: row.isAtm ? k.border : k.surface, padding: '4px 0', borderRadius: 4, display: 'inline-block', margin: '0 auto', width: 60 }}>
                    {row.strike}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: 10, paddingLeft: 16, fontWeight: 500, position: 'relative' }}>
                    {isHover && (
                      <div style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center' }}>
                        <button onClick={(e) => handleAction(e, 'put', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                        <button onClick={(e) => handleAction(e, 'put', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'put')}><Icons.More /></button>
                      </div>
                    )}
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>{row.put.ltp}</span>
                    <Chg v={row.put.ltpChg} />
                  </div>
                  <div style={{ textAlign: 'left', color: k.text }}>{row.put.iv}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.delta}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.theta}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.vega}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.gamma}</div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderTop: `1px solid ${k.border}`, background: k.bg, padding: '10px 16px' }}>
        {footer.map((s) => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: k.dim, marginBottom: 3 }}>{s.label}</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: '#333', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Popover Menu */}
      {menuOpen && (
        <div
          style={{
            position: 'fixed',
            top: menuOpen.top,
            left: menuOpen.left,
            background: k.bg,
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            padding: '8px 0',
            zIndex: 100,
            minWidth: 180,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {[
            { label: 'Chart', icon: <Icons.Chart /> },
            { label: 'Create GTT / GTC', icon: <Icons.Timer /> },
            { label: 'Create alert / ATO', icon: <Icons.Bell /> },
            { label: 'Market depth', icon: <Icons.Depth /> },
            { label: 'Add to watchlist', icon: <Icons.More /> },
            { label: 'Add to basket', icon: <Icons.Basket /> },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                color: k.text,
                cursor: 'pointer',
                display: 'flex',
                gap: 12,
                alignItems: 'center',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = k.surfaceHover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ color: k.dim, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
