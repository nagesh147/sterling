import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  createChart, IChartApi, ColorType, CandlestickSeries, LineSeries, HistogramSeries, AreaSeries, BarSeries,
  createSeriesMarkers, CrosshairMode, LineStyle, PriceScaleMode,
} from 'lightweight-charts';
import { useKiteDrawings, Drawing } from '../../hooks/useKiteDrawings';
import { InstrumentLabel } from '../kite/InstrumentLabel';
import {
  ema, sma, atr, bollingerBands, vwap, rsi, macd, supertrend, supertrendRuns, heikinAshi,
  type Candle,
} from '../../utils/indicators';
import { useCandles } from '../../hooks/useCandles';
import { useCreateAlert } from '../../hooks/useAlerts';
import {
  IconCrosshair, IconHLine, IconTrendline, IconRay, IconFib, IconFibExt, IconFibFan,
  IconRect, IconPitchfork, IconText, IconPencil, IconFullscreen, IconClose, IconMore, IconGear,
} from './ChartIcons';
import { MiniGridPane } from './MiniGridPane';
import { freshTripleAlignmentIndex, nearestTimeIndex } from './signalMarkerLogic';
import type { SignalChartData } from '../../types/kiteEngine';
import {
  ChartTemplate,
  ComparisonOverlay,
  DEFAULT_WORKSPACE,
  ExtraIndicatorKind,
  IndicatorStyle,
  MAX_COMPARISONS,
  MAX_EXTRA_INDICATORS,
  compileFormula,
  comparisonSeriesData,
  createChartTemplate,
  createComparisonOverlay,
  createExtraIndicator,
  exportTemplatesToJson,
  formulaSeries,
  loadTemplates,
  loadWorkspace,
  mergeImportedTemplates,
  nearestCandleIndex,
  replayDelayMs,
  saveTemplates,
  saveWorkspace,
  stepReplayIndex,
  stochastic,
  TEMPLATE_KEY,
  WORKSPACE_KEY,
  REPLAY_SPEEDS,
  upsertTemplate,
} from './chartWorkspace';

const COMPARISON_CANDLE_LIMIT = 360;

interface TradingViewKiteChartProps {
  symbol: string;
  rawCandles: any[];
  tf: string;
  isHA?: boolean;
  isLogScale?: boolean;
  isDark?: boolean;
  theme: any;
  activeIndicators: Set<string>;
  params: any;
  drawings?: Drawing[];
  onDrawingsChange?: (d: Drawing[]) => void;
  onZoomChange?: (zoom: any) => void;
  showVP?: boolean;
  height?: number | string;
  position?: any;
  symbolPos?: any;
  persistedZoom?: any;
  drawMode?: string;
  onDrawModeChange?: (m: any) => void;
  signalData?: SignalChartData;
  /** Fired once the main chart has finished a structural rebuild (createChart +
   *  all series/indicators/drawings set) — used by the parent to hide a
   *  switch-instrument loading overlay in sync with the actual expensive work,
   *  not just when candle data has arrived. */
  onChartReady?: (readyKey?: string) => void;
  // for full TV-like control inside the component
  onTfChange?: (tf: string) => void;
  onIsHAChange?: (ha: boolean) => void;
  onIsLogScaleChange?: (log: boolean) => void;
  onShowVPChange?: (show: boolean) => void;
  onSymbolChange?: (symbol: string) => void;
  onToggleIndicator?: (key: string) => void;
  onActiveIndicatorsChange?: (keys: string[]) => void;
  onParamsChange?: (params: any) => void;
}

export function TradingViewKiteChart({
  symbol,
  rawCandles,
  tf,
  isHA = false,
  isLogScale = false,
  isDark = false,
  theme,
  activeIndicators,
  params,
  drawings: externalDrawings,
  onDrawingsChange,
  onZoomChange,
  showVP = false,
  height = '100%',
  position,
  symbolPos,
  persistedZoom,
  signalData,
  onTfChange,
  onIsHAChange,
  onIsLogScaleChange,
  onShowVPChange,
  onSymbolChange,
  onToggleIndicator,
  onActiveIndicatorsChange,
  onParamsChange,
  onChartReady,
}: TradingViewKiteChartProps) {
  const [internalDrawings, setInternalDrawings] = useState<Drawing[]>(externalDrawings || []);
  const drawings = onDrawingsChange ? (externalDrawings || []) : internalDrawings;
  const setDrawings = onDrawingsChange || setInternalDrawings;

  const {
    drawMode,
    setDrawMode,
    drawingPoints,
    setDrawingPoints,
    selectedDrawingId,
    setSelectedDrawingId,
    isDragging,
    onMouseDown: drawingMouseDown,
    onMouseMove: drawingMouseMove,
    onMouseUp: drawingMouseUp,
    handleChartClick,
    clearDrawings,
    snapToOHLC,
    updateDrawingText,
    setDrawings: recordDrawingsChange,
    undo: undoDrawing,
    redo: redoDrawing,
  } = useKiteDrawings({ initialDrawings: drawings, onChange: setDrawings });

  const mainRef = useRef<HTMLDivElement>(null);
  // (drawingPointsRef/drawModeRef are declared below with the other refs, kept
  // fresh here on every render so long-lived chart callbacks can read live values)
  const profileRef = useRef<HTMLCanvasElement>(null); // for full histo VP
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const handlesRef = useRef<HTMLCanvasElement>(null); // visible drag handles + selection

  const mainChartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<Record<string, any>>({});
  // Zoom continuity across chart rebuilds. We remember the last range the user
  // was viewing (lastRangeRef) and restore it after a genuine structural rebuild;
  // we track the instrument key so a symbol/timeframe switch fits fresh; and we
  // track the persisted-zoom object identity so a freshly loaded saved range is
  // honoured exactly once (not re-applied over a later user pan).
  const lastRangeRef = useRef<any>(null);
  const instrumentKeyRef = useRef<string>('');
  const appliedPersistedRef = useRef<any>(null);
  const subChartsRef = useRef<{ rsi?: IChartApi; macd?: IChartApi; rsiSeries?: any; macdSeries?: any }>({});
  // Always-fresh candle data + related inputs, read by the chart-creation effects
  // via `.current` instead of a reactive dependency. The forming (in-progress) bar
  // mutates on essentially every useCandles poll, so putting `baseCandles` directly
  // in a chart-creation effect's dep array means that effect (and its expensive
  // chart.remove()+createChart() teardown/rebuild) reruns on every idle poll tick,
  // not just on a genuine symbol/timeframe/indicator/theme change — this is what
  // produced the reported "repositioning/stutter" both on load and while idle.
  // A separate lightweight effect below pushes fresh data onto the already-built
  // chart via setData() (no teardown) whenever only the candle data changed.
  const baseCandlesRef = useRef<any[]>([]);
  const comparisonCandlesRef = useRef<Array<{ overlay: ComparisonOverlay; candles: any[] }>>([]);
  const activeIndicatorsRef = useRef<Set<string>>(new Set());
  const paramsRef = useRef<any>({});
  const chartTypeRef = useRef<'candles' | 'line' | 'area' | 'bars'>('candles');
  const tvRef = useRef<any>({});
  // symbolPos/signalData come from a 5s position poll + the signal feed, both of
  // which hand back a brand-new object reference on every tick even when the
  // value is unchanged. They used to sit directly in the structural effects'
  // dep arrays below, so a plain position poll (every 5s) forced the same
  // chart.remove()+createChart() teardown/rebuild the baseCandles fix above was
  // written to eliminate — read via `.current` instead so only a genuine value
  // change (new position/new signal) needs to be reflected, on the next
  // structural rebuild rather than on every poll tick.
  const symbolPosRef = useRef<any>(null);
  const signalDataRef = useRef<any>(undefined);
  // Kept fresh via a ref (not a dep) so calling it doesn't force the expensive
  // structural effect below to re-run whenever the parent passes a new closure.
  const onChartReadyRef = useRef<((readyKey?: string) => void) | undefined>(onChartReady);
  // handleChartClick/snapToOHLC come from useKiteDrawings, which hands back a
  // NEW function identity most renders (its own useCallback deps churn as
  // drawingPoints/drawMode/etc. tick) - measured live, this was forcing a full
  // chart.remove()+createChart() rebuild on essentially every InstrumentPane
  // re-render (candle poll, position poll, chart-state load settling...), not
  // just genuine symbol/timeframe switches. That's the actual "loads at one
  // zoom, snaps to another a split second later" bug: two (or more) full
  // rebuilds firing in a burst right after a chart opens, each doing its own
  // fitContent() pass. Read via `.current` instead of a reactive dependency,
  // same fix already applied to baseCandles/symbolPos/signalData above.
  const handleChartClickRef = useRef(handleChartClick);
  const snapToOHLCRef = useRef(snapToOHLC);
  const lastSyncedCandlesRef = useRef<any[] | null>(null);
  // Baseline {from,to} for wheel-driven price-axis zoom (see handlePriceAxisWheel
  // below) - re-seeded from the live auto-fit range whenever the price scale is
  // in (or returns to, via native double-click reset) autoScale mode, so clamp
  // bounds always track the current data-driven range rather than a stale one.
  const priceZoomBaseRef = useRef<{ from: number; to: number } | null>(null);

  // Always-fresh refs for drawMode/drawingPoints so long-lived chart callbacks
  // (subscribeCrosshairMove) can read live values without forcing a chart rebuild.
  const drawingPointsRef = useRef<any[]>([]);
  const drawModeRef = useRef<string>('crosshair');

  // Transient live-preview series/price-lines for in-progress multi-point drawings
  type PreviewEntry = { kind: 'series'; series: any } | { kind: 'priceline'; series: any; line: any };
  const previewSeriesRef = useRef<PreviewEntry[]>([]);

  // Last-price flash badge
  const prevCloseRef = useRef<number | null>(null);
  const flashTimeoutRef = useRef<any>(null);
  const [priceBadge, setPriceBadge] = useState<{ y: number; price: number } | null>(null);
  const [priceFlashDir, setPriceFlashDir] = useState<'up' | 'down' | null>(null);

  // Right price-scale width (for sizing the context-menu hit strip) + its context menu
  const [rightScaleWidth, setRightScaleWidth] = useState<number>(56);
  const [priceScaleMenu, setPriceScaleMenu] = useState<{ x: number; y: number } | null>(null);
  // General chart-area right-click menu (distinct from the price-scale one above)
  const [chartContextMenu, setChartContextMenu] = useState<{ x: number; y: number; price: number } | null>(null);

  // Hover tracking so the keyboard-shortcut listener never hijacks typing elsewhere in the app
  const isHoveringChartRef = useRef(false);

  // Keep the "always-fresh" refs in sync every render (cheap; no extra re-renders caused)
  drawingPointsRef.current = drawingPoints;
  drawModeRef.current = drawMode;

  // Force chart resize when terminal minimized or panes hidden (layout changes free up space for chart)
  useEffect(() => {
    const doResize = () => {
      if (mainChartRef.current && mainRef.current) {
        const w = mainRef.current.clientWidth || 0;
        const h = mainRef.current.clientHeight || 0;
        if (w > 10 && h > 10) {
          mainChartRef.current.applyOptions({ width: w, height: h });
        }
      }
    };
    const onMode = () => setTimeout(doResize, 30);
    window.addEventListener('kite-terminal-mode', onMode);
    window.addEventListener('resize', doResize);
    // listen for pane toggles from layout
    window.addEventListener('kite-pane-toggle', onMode);
    return () => {
      window.removeEventListener('kite-terminal-mode', onMode);
      window.removeEventListener('resize', doResize);
      window.removeEventListener('kite-pane-toggle', onMode);
    };
  }, []);

  const [currentBarInfo, setCurrentBarInfo] = useState<any>(null);
  const [editingTextId, setEditingTextId] = useState<number | null>(null);
  const [editTextValue, setEditTextValue] = useState('');
  const [chartType, setChartType] = useState<'candles' | 'line' | 'area' | 'bars'>('candles');
  const [showStudies, setShowStudies] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [workspace, setWorkspace] = useState(() => {
    if (typeof window === 'undefined') return structuredClone(DEFAULT_WORKSPACE);
    return loadWorkspace();
  });
  const [templates, setTemplates] = useState<ChartTemplate[]>(() => typeof window === 'undefined' ? [] : loadTemplates());
  const [showTemplates, setShowTemplates] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [showChartSettings, setShowChartSettings] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [compareSearch, setCompareSearch] = useState('');
  const [goToDateValue, setGoToDateValue] = useState('');
  const [showGoToDate, setShowGoToDate] = useState(false);
  const [replayIndex, setReplayIndex] = useState<number | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replaySpeed, setReplaySpeed] = useState<number>(1);
  const [alertDialog, setAlertDialog] = useState<{ price: number } | null>(null);
  const [alertCondition, setAlertCondition] = useState<'price_above' | 'price_below'>('price_above');
  const [alertNotes, setAlertNotes] = useState('');
  const [alertDraft, setAlertDraft] = useState<{ price: number; y: number } | null>(null);
  const [templateImportText, setTemplateImportText] = useState('');
  const [templateError, setTemplateError] = useState('');
  const createAlert = useCreateAlert();

  const comparisonSlots = useMemo(() => workspace.comparisons.slice(0, MAX_COMPARISONS), [workspace.comparisons]);
  const { data: comparisonRawCandles0 = [] } = useCandles(comparisonSlots[0]?.symbol || '', tf, COMPARISON_CANDLE_LIMIT);
  const { data: comparisonRawCandles1 = [] } = useCandles(comparisonSlots[1]?.symbol || '', tf, COMPARISON_CANDLE_LIMIT);
  const { data: comparisonRawCandles2 = [] } = useCandles(comparisonSlots[2]?.symbol || '', tf, COMPARISON_CANDLE_LIMIT);
  const { data: comparisonRawCandles3 = [] } = useCandles(comparisonSlots[3]?.symbol || '', tf, COMPARISON_CANDLE_LIMIT);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const timer = window.setTimeout(() => saveWorkspace(workspace), 120);
    return () => window.clearTimeout(timer);
  }, [workspace]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onStorage = (event: StorageEvent) => {
      if (event.key === WORKSPACE_KEY) setWorkspace(loadWorkspace());
      if (event.key === TEMPLATE_KEY) setTemplates(loadTemplates());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Symbol search (TV style dropdown)
  const [showSymbolSearch, setShowSymbolSearch] = useState(false);
  const [symbolSearch, setSymbolSearch] = useState('');

  // Timeframe dropdown (more TFs)
  const [showTfDropdown, setShowTfDropdown] = useState(false);

  // Escape closes these two toolbar dropdowns regardless of where the mouse is
  // hovering (they live in the top toolbar, outside the chart-hover-gated
  // keyboard-shortcut listener below, so they need their own lightweight
  // listener rather than piggybacking on that one).
  useEffect(() => {
    if (!showSymbolSearch && !showTfDropdown) return;
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setShowSymbolSearch(false); setShowTfDropdown(false); }
    };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [showSymbolSearch, showTfDropdown]);

  // Better indicators dropdown (searchable, TV like)
  const [indicatorSearch, setIndicatorSearch] = useState('');
  // Which indicator row (by key) currently has its inline param-editor form
  // expanded in the Indicators modal (only one at a time; null = none open).
  const [paramEditorKey, setParamEditorKey] = useState<string | null>(null);

  // Drawing edit popover for right-click properties (TV style)
  const [editingDrawingId, setEditingDrawingId] = useState<number | null>(null);
  const [drawingPopoverPos, setDrawingPopoverPos] = useState<{x: number, y: number} | null>(null);
  const [drawingEditProps, setDrawingEditProps] = useState<any>(null);
  const [layoutMode, setLayoutMode] = useState<'1'|'2'|'4'>('1');
  // Registry of synced multi-pane grid chart instances (layoutMode '2'/'4') -
  // each MiniGridPane registers/unregisters itself here so panning/zooming any
  // one pane broadcasts to the others via the identical subscribeVisibleTimeRangeChange
  // pattern already used to sync the RSI/MACD sub-panes to the main chart.
  const gridChartsRef = useRef<Map<number, IChartApi>>(new Map());
  const gridSyncGuardRef = useRef(false);

  // Reset some UI state when symbol changes (new chart context)
  useEffect(() => {
    setSelectedDrawingId(null);
    setDrawingPoints([]);
    setEditingTextId(null);
    setEditTextValue('');
    setSelectBox(null);
    setDrawingPopoverPos(null);
    setEditingDrawingId(null);
    setDrawingEditProps(null);
  }, [symbol]);

  // TV-like symbol suggestions (extendable)
  // Index tradingsymbols must match Kite's actual space-separated names
  // (instrument_registry.py / schemas.py) — bare underlying codes like
  // 'NIFTY'/'BANKNIFTY'/'FINNIFTY' 404 against the candles endpoint, and
  // SENSEX trades/quotes on BSE, not NSE.
  const COMMON_SYMBOLS = [
    'NSE:NIFTY 50', 'NSE:NIFTY BANK', 'NSE:NIFTY FIN SERVICE', 'BSE:SENSEX',
    'NSE:RELIANCE', 'NSE:TCS', 'NSE:INFY', 'NSE:HDFCBANK', 'NSE:ICICIBANK',
    'NSE:SBIN', 'NSE:BHARTIARTL', 'NSE:ITC', 'NSE:LT', 'NSE:AXISBANK'
  ];

  const filteredSymbols = COMMON_SYMBOLS.filter(s => 
    s.toLowerCase().includes(symbolSearch.toLowerCase())
  );

  const PRIMARY_TFS = ['1m','3m','5m','15m','30m','1H','2H','4H','D','W','M'];
  const ALL_TFS = ['1m','3m','5m','15m','30m','1H','2H','4H','60m','120m','240m','D','W','M'];

  // Indicators list for searchable dropdown (TV style)
  const ALL_INDICATORS = [
    { key: 'ema', label: 'Exponential Moving Average (EMA)', category: 'Trend' },
    { key: 'bb', label: 'Bollinger Bands', category: 'Volatility' },
    { key: 'st-fast', label: 'SuperTrend Fast (21,1)', category: 'Trend' },
    { key: 'st-mid', label: 'SuperTrend Mid (14,2)', category: 'Trend' },
    { key: 'st-slow', label: 'SuperTrend Slow (7,3)', category: 'Trend' },
    { key: 'vwap', label: 'VWAP', category: 'Volume' },
    { key: 'vol', label: 'Volume', category: 'Volume' },
    { key: 'rsi', label: 'Relative Strength Index (RSI)', category: 'Oscillators' },
    { key: 'macd', label: 'MACD', category: 'Oscillators' },
    { key: 'sma', label: 'Simple Moving Average (SMA)', category: 'Trend' },
    { key: 'atr', label: 'Average True Range (ATR)', category: 'Volatility' },
    { key: 'stoch', label: 'Stochastic', category: 'Oscillators' },
  ];

  const filteredIndicators = ALL_INDICATORS.filter(ind =>
    ind.label.toLowerCase().includes(indicatorSearch.toLowerCase()) ||
    ind.category.toLowerCase().includes(indicatorSearch.toLowerCase())
  );

  // Numeric param fields per indicator, for the inline gear-icon editor in the
  // Indicators modal below. Only indicators whose rendering code actually
  // reads params (EMA/BB/the 3 ST variants/RSI/MACD) get an entry here — vwap/
  // vol has no numeric params. The remaining catalog entries map directly to
  // rendering code below, including SMA/ATR/Stochastic.
  const INDICATOR_PARAM_FIELDS: Record<string, { key: string; label: string; default: number; step?: number }[]> = {
    ema: [
      { key: 'ema1', label: 'Period 1', default: 9 },
      { key: 'ema2', label: 'Period 2', default: 21 },
    ],
    bb: [
      { key: 'bbPeriod', label: 'Period', default: 20 },
      { key: 'bbStd', label: 'StdDev', default: 2, step: 0.1 },
    ],
    'st-fast': [
      { key: 'stFastPeriod', label: 'Period', default: 21 },
      { key: 'stFastMult', label: 'Mult', default: 1, step: 0.1 },
    ],
    'st-mid': [
      { key: 'stMidPeriod', label: 'Period', default: 14 },
      { key: 'stMidMult', label: 'Mult', default: 2, step: 0.1 },
    ],
    'st-slow': [
      { key: 'stSlowPeriod', label: 'Period', default: 7 },
      { key: 'stSlowMult', label: 'Mult', default: 3, step: 0.1 },
    ],
    rsi: [
      { key: 'rsiPeriod', label: 'Period', default: 14 },
    ],
    macd: [
      { key: 'macdFast', label: 'Fast', default: 12 },
      { key: 'macdSlow', label: 'Slow', default: 26 },
      { key: 'macdSig', label: 'Signal', default: 9 },
    ],
    sma: [{ key: 'smaPeriod', label: 'Period', default: 50 }],
    atr: [{ key: 'atrPeriod', label: 'Period', default: 14 }],
    stoch: [{ key: 'stochPeriod', label: 'Period', default: 14 }],
  };

  // Commit a single param-field edit. Mirrors the onToggleIndicator fallback
  // pattern (console.log when the parent hasn't wired the callback) so this
  // degrades the same way if a caller doesn't pass onParamsChange.
  const setParamField = (key: string, value: number) => {
    if (onParamsChange) onParamsChange({ ...params, [key]: value });
    else console.log('Param change:', key, value, ' (provide onParamsChange prop for full sync)');
  };

  const candles = useMemo(() => {
    const valid = rawCandles.filter((c: any) => c.time != null && !isNaN(c.time));
    return [...valid].sort((a: any, b: any) => a.time - b.time)
      .filter((v: any, i: number, a: any[]) => i === 0 || v.time !== a[i - 1].time);
  }, [rawCandles]);

  const fullBaseCandles = useMemo(() => {
    return isHA ? heikinAshi(candles as Candle[]) : (candles as Candle[]);
  }, [candles, isHA]);

  const baseCandles = useMemo(() => {
    if (replayIndex == null) return fullBaseCandles;
    return fullBaseCandles.slice(0, Math.min(replayIndex + 1, fullBaseCandles.length));
  }, [fullBaseCandles, replayIndex]);

  const normalizeComparisonCandles = useCallback((raw: any[]) => {
    const valid = raw.filter((c: any) => c.time != null && !isNaN(c.time));
    return [...valid].sort((a: any, b: any) => a.time - b.time)
      .filter((value: any, index: number, all: any[]) => index === 0 || value.time !== all[index - 1].time);
  }, []);

  const comparisonCandles = useMemo(() => {
    const rawSlots = [comparisonRawCandles0, comparisonRawCandles1, comparisonRawCandles2, comparisonRawCandles3];
    return comparisonSlots.map((overlay, index) => ({
      overlay,
      candles: normalizeComparisonCandles(rawSlots[index] || []),
    }));
  }, [
    comparisonSlots,
    comparisonRawCandles0,
    comparisonRawCandles1,
    comparisonRawCandles2,
    comparisonRawCandles3,
    normalizeComparisonCandles,
  ]);

  useEffect(() => {
    if (replayIndex == null || replayIndex < fullBaseCandles.length) return;
    setReplayIndex(Math.max(0, fullBaseCandles.length - 1));
  }, [fullBaseCandles.length, replayIndex]);

  useEffect(() => {
    if (!replayPlaying || replayIndex == null) return;
    const delay = replayDelayMs(replaySpeed);
    const timer = window.setInterval(() => {
      setReplayIndex((current) => {
        if (current == null || current >= fullBaseCandles.length - 1) {
          setReplayPlaying(false);
          return current;
        }
        return stepReplayIndex(current, fullBaseCandles.length - 1, 1);
      });
    }, delay);
    return () => window.clearInterval(timer);
  }, [replayPlaying, replayIndex, fullBaseCandles.length, replaySpeed]);
  // Boolean (not the array itself) so it only flips once, on the empty->non-empty
  // transition, instead of on every poll tick like `baseCandles` would. The three
  // structural chart-build effects below read candle data via baseCandlesRef and
  // bail out with no chart when it's still empty (candles not fetched yet) - on a
  // fresh mount that race is common (this effect runs before the async candle
  // fetch resolves), and none of those effects' other deps change once the data
  // lands, so without this they never got a second chance to build the chart -
  // the "first load goes blank forever" bug.
  const hasCandles = baseCandles.length > 0;

  // local effective theme (dark/light)
  const effTheme = theme;

  const INDICATOR_LABELS: Record<string, string> = {
    ema: 'EMA',
    bb: 'BB',
    st: 'SuperTrend',
    vwap: 'VWAP',
    vol: 'Volume',
    rsi: 'RSI',
    macd: 'MACD',
    sma: 'SMA',
    atr: 'ATR',
    stoch: 'Stochastic',
  };

  // Exact TradingView dark theme colors + tokens for look & feel
  //
  // ROOT CAUSE OF DRAG/ZOOM DEAD-CHART BUG: this used to be a plain object
  // literal recomputed on *every* render (identity changed even when isDark/
  // theme didn't). It sits in the dep array of the main chart-creation effect
  // (chart.remove() + createChart(...)) below, and that effect also depends
  // on `baseCandles`/`drawings`/etc which don't change on mouse movement — but
  // `subscribeCrosshairMove` calls `setCurrentBarInfo(...)` on every mousemove
  // tick over the chart, which re-renders this component, which regenerated
  // `tv` with a new reference, which re-ran the chart-creation effect (tearing
  // down + rebuilding the chart's canvas and the library's internal pan/zoom
  // state machine) on essentially every mousemove sample during a drag or
  // right before a wheel event — making pan/zoom appear completely dead.
  // useMemo keyed on the real inputs (isDark/theme) fixes this at the source.
  const tv = useMemo(() => (isDark ? {
    bg: '#131722',
    surface: '#1e2c3f',
    surfaceHover: '#2a3a4f',
    border: '#363a45',
    text: '#d1d4dc',
    dim: '#787b86',
    blue: '#2962ff',
    red: '#f23645',
    green: '#089981',
    amber: '#ff9800',
    orange: '#ff6d00',
    cyan: '#00bcd4',
    purple: '#ab47bc',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  } : {
    ...theme,
    bg: theme.bg || '#ffffff',
    surface: theme.surface || '#f8f9fa',
    border: theme.border || '#e0e0e0',
    text: theme.text || '#131722',
    dim: theme.dim || '#787b86',
    green: theme.green || '#089981',
    red: theme.red || '#f23645',
  }), [isDark, theme]);

  const indicatorStyle = (key: string, fallback: IndicatorStyle): IndicatorStyle => ({
    ...fallback,
    ...(workspace.styles[key] || {}),
  });

  const updateIndicatorStyle = (key: string, patch: Partial<IndicatorStyle>) => {
    setWorkspace((current) => ({
      ...current,
      styles: {
        ...current.styles,
        [key]: { ...indicatorStyle(key, { color: tv.blue, lineWidth: 2, visible: true }), ...patch },
      },
    }));
  };

  // Keep always-fresh refs in sync every render (cheap; no extra re-renders caused).
  // Read by the data-only sync effect further below instead of being reactive
  // dependencies, so that effect isn't tied to indicator/param/theme identity.
  baseCandlesRef.current = baseCandles;
  comparisonCandlesRef.current = comparisonCandles;
  onChartReadyRef.current = onChartReady;
  handleChartClickRef.current = handleChartClick;
  snapToOHLCRef.current = snapToOHLC;
  activeIndicatorsRef.current = activeIndicators;
  paramsRef.current = params;
  chartTypeRef.current = chartType;
  tvRef.current = tv;
  symbolPosRef.current = symbolPos;
  signalDataRef.current = signalData;

  // Compute volume profile data (full histogram)
  const volumeProfile = useMemo(() => {
    if (!baseCandles.length || !showVP) return [] as { price: number; vol: number }[];
    const bins = new Map<number, number>();
    let minP = Infinity, maxP = -Infinity;
    baseCandles.forEach((c: any) => {
      const p = c.close;
      minP = Math.min(minP, p);
      maxP = Math.max(maxP, p);
      const bin = Math.round(p / 5) * 5; // ~5 unit buckets for precision
      bins.set(bin, (bins.get(bin) || 0) + (c.volume || 1));
    });
    const arr = Array.from(bins.entries())
      .map(([price, vol]) => ({ price, vol }))
      .sort((a, b) => a.price - b.price);
    return arr;
  }, [baseCandles, showVP]);

  // Draw full VP histogram bars on side canvas (TV style) - linear fallback only (avoids coord typing)
  const drawVolumeProfile = useCallback(() => {
    const cnv = profileRef.current;
    if (!cnv || !volumeProfile.length) return;
    const ctx = cnv.getContext('2d', { alpha: true });
    if (!ctx) return;
    const w = cnv.width = 92;
    const h = cnv.height = (mainRef.current ? mainRef.current.clientHeight : 380);

    ctx.clearRect(0, 0, w, h);
    const maxVol = Math.max(1, ...volumeProfile.map(v => v.vol));
    const minP = volumeProfile[0].price;
    const maxP = volumeProfile[volumeProfile.length - 1].price;
    const priceToY = (p: number) => h - ((p - minP) / Math.max(1e-6, (maxP - minP))) * (h - 4) - 2;

    ctx.fillStyle = (tv.amber || '#ff9800') + '99';
    volumeProfile.forEach(({ price, vol }) => {
      const y = priceToY(price);
      const bw = Math.max(3, Math.floor((vol / maxVol) * (w - 8)));
      ctx.fillRect(w - bw - 2, y - 1.5, bw, 3.5);
    });
    const poc = volumeProfile.reduce((a, b) => b.vol > a.vol ? b : a, volumeProfile[0]);
    const py = priceToY(poc.price);
    ctx.fillStyle = tv.orange || '#ff6d00';
    ctx.fillRect(w - 18, py - 1, 16, 2);
  }, [volumeProfile, tv]);

  // Draw visible drag handles + highlight for selection (polish) using REAL coordinateTo* / priceToCoordinate (with ignores for prod)
  const drawHandles = useCallback(() => {
    const cnv = handlesRef.current;
    const chart = mainChartRef.current;
    if (!cnv || !chart || !selectedDrawingId) return;
    const ctx = cnv.getContext('2d', { alpha: true });
    if (!ctx) return;
    const rect = mainRef.current?.getBoundingClientRect();
    if (!rect) return;
    cnv.width = Math.floor(rect.width);
    cnv.height = Math.floor(rect.height);
    ctx.clearRect(0, 0, cnv.width, cnv.height);

    const sel = drawings.find(d => d.id === selectedDrawingId);
    if (!sel) return;

    const pts: { time: any; price: number }[] = [];
    if (sel.type === 'hline' && sel.price != null) {
      const range = chart.timeScale().getVisibleRange();
      if (range) {
        const f = (range.from as any) as number || 0;
        const t = (range.to as any) as number || 0;
        pts.push({ time: (f + t) / 2, price: sel.price });
      }
    } else if (sel.points && sel.points.length) {
      pts.push(...sel.points);
    } else if (sel.time != null && sel.price != null) {
      pts.push({ time: sel.time, price: sel.price });
    }

    ctx.strokeStyle = '#fff';
    ctx.fillStyle = sel.color || tv.blue || '#58a6ff';
    const ts: any = (chart as any).timeScale ? (chart as any).timeScale() : null;
    const ps: any = (chart as any).priceScale ? (chart as any).priceScale() : null;
    pts.forEach(p => {
      try {
        // @ts-ignore - real coord APIs (prod runtime works; typing varies by lightweight-charts version)
        const x = ts && ts['timeToCoordinate'] ? ts['timeToCoordinate'](p.time) : null;
        // @ts-ignore
        const y = ps && ps['priceToCoordinate'] ? ps['priceToCoordinate'](p.price) : null;
        if (x != null && y != null && x > 0 && y > 0 && x < rect.width && y < rect.height) {
          // small square handle (TV style)
          ctx.fillRect(x - 4, y - 4, 8, 8);
          ctx.lineWidth = 1;
          ctx.strokeRect(x - 5.5, y - 5.5, 11, 11);
          // outer ring for visibility/selection
          ctx.beginPath();
          ctx.arc(x, y, 8, 0, Math.PI * 2);
          ctx.stroke();
        }
      } catch {}
    });
  }, [selectedDrawingId, drawings, tv]);

  // Remove any transient live-preview series/price-lines from the chart
  const clearPreview = useCallback(() => {
    const chart = mainChartRef.current;
    previewSeriesRef.current.forEach(entry => {
      try {
        if (entry.kind === 'priceline') entry.series.removePriceLine(entry.line);
        else if (chart) chart.removeSeries(entry.series);
      } catch {}
    });
    previewSeriesRef.current = [];
  }, []);

  // Render a dashed, lower-opacity live preview for an in-progress multi-point drawing
  // (first point(s) already placed + current cursor position), mirroring the same
  // rendering approach used for the finished drawing of that type further below.
  const renderPreview = useCallback((livePoints: { time: number; price: number }[], mode: string) => {
    const chart = mainChartRef.current;
    const candleS = seriesRefs.current.candle;
    if (!chart) return;
    clearPreview();
    const dashCommon = { lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false };
    const addDashedSeries = (color: string, pts: { time: number; price: number }[], width = 1.5) => {
      const s = chart.addSeries(LineSeries, { color, lineWidth: width as any, ...dashCommon });
      s.setData(pts.map(p => ({ time: p.time as any, value: p.price })));
      previewSeriesRef.current.push({ kind: 'series', series: s });
    };

    if ((mode === 'trend' || mode === 'ray') && livePoints.length === 2) {
      addDashedSeries((mode === 'ray' ? tv.cyan : tv.green) + 'aa', livePoints);
    } else if (mode === 'rect' && livePoints.length === 2) {
      const [p1, p2] = livePoints;
      const y1 = Math.min(p1.price, p2.price);
      const y2 = Math.max(p1.price, p2.price);
      const t1 = Math.min(p1.time, p2.time);
      const t2 = Math.max(p1.time, p2.time);
      addDashedSeries((tv.red || '#f23645') + 'aa', [{ time: t1, price: y1 }, { time: t2, price: y1 }]);
      addDashedSeries((tv.red || '#f23645') + 'aa', [{ time: t1, price: y2 }, { time: t2, price: y2 }]);
    } else if ((mode === 'fib' || mode === 'fibext') && livePoints.length === 2 && candleS) {
      const [p1, p2] = livePoints;
      const minP = Math.min(p1.price, p2.price);
      const maxP = Math.max(p1.price, p2.price);
      const ratios = mode === 'fibext'
        ? [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618, 2.0]
        : [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
      ratios.forEach(ratio => {
        const fibPrice = minP + (maxP - minP) * ratio;
        const line = candleS.createPriceLine({
          price: fibPrice,
          color: (tv.purple || '#a371f7') + '99',
          lineWidth: 1 as any,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: false,
          title: '',
        });
        previewSeriesRef.current.push({ kind: 'priceline', series: candleS, line });
      });
    } else if (mode === 'fibfan' && livePoints.length === 2) {
      const [p1, p2] = livePoints;
      const fanRatios = [0.382, 0.5, 0.618];
      fanRatios.forEach(r => {
        const fanP = { time: p2.time, price: p1.price + (p2.price - p1.price) * r };
        addDashedSeries((tv.purple || '#a371f7') + 'aa', [p1, fanP]);
      });
    } else if (mode === 'pitchfork' && livePoints.length >= 2) {
      addDashedSeries('#ff9800aa', livePoints);
    }
  }, [clearPreview, tv]);

  // Clear the live preview the instant a drawing commits (points reset to empty),
  // rather than waiting for the next mouse move.
  useEffect(() => {
    if (drawingPoints.length === 0) clearPreview();
  }, [drawingPoints, clearPreview]);

  // Main chart + indicators + drawings creation. Reads baseCandles via the ref
  // (kept fresh every render above) instead of depending on it reactively, so
  // this full teardown+rebuild only runs on genuine structural changes (symbol/
  // timeframe/indicator/theme/etc) — not on every candle-data poll tick. See the
  // data-only sync effect further below for the "just push new candle data"
  // path that doesn't touch the chart instance at all.
  useEffect(() => {
    const baseCandles = baseCandlesRef.current;
    const symbolPos = symbolPosRef.current;
    const signalData = signalDataRef.current;
    const instrumentKey = `${symbol}|${tf}`;
    if (layoutMode !== '1' || !mainRef.current || !baseCandles.length) {
      if (mainChartRef.current) {
        mainChartRef.current.remove();
        mainChartRef.current = null;
        seriesRefs.current = {};
        previewSeriesRef.current = [];
        lastSyncedCandlesRef.current = null;
      }
      if (!baseCandles.length) {
        lastRangeRef.current = null;
        priceZoomBaseRef.current = null;
        setPriceBadge(null);
      }
      return;
    }

    if (mainChartRef.current) {
      mainChartRef.current.remove();
      mainChartRef.current = null;
      seriesRefs.current = {};
    }
    // New chart instance -> forget any previous wheel-zoom baseline so the
    // next price-axis wheel tick re-seeds from this chart's own auto-fit range.
    priceZoomBaseRef.current = null;

    const chart = createChart(mainRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: tv.bg },
        textColor: tv.dim,
        fontFamily: tv.fontFamily,
      },
      grid: {
        vertLines: { visible: workspace.appearance.gridVisible, color: tv.border + '66' },
        horzLines: { visible: workspace.appearance.gridVisible, color: tv.border + '66' },
      },
      crosshair: {
        mode: workspace.appearance.magnetCrosshair ? CrosshairMode.Magnet : CrosshairMode.Normal,
        vertLine: { width: 1, color: '#758696', style: LineStyle.Solid, labelBackgroundColor: tv.surface, labelVisible: true },
        horzLine: { width: 1, color: '#758696', style: LineStyle.Solid, labelBackgroundColor: tv.surface, labelVisible: true },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.08, bottom: 0.12 },
        entireTextOnly: true,
        mode: isLogScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 12,
        fixLeftEdge: false,
        // false (not the library default true): a container resize (e.g. the
        // bottom-terminal's 0.2s collapse animation firing right as a chart
        // opens) must NOT re-stretch the already-visible bars to fill the new
        // width - that reads as "the zoom level changed" with no user action.
        // false keeps bar spacing (px/bar) constant across a resize and reveals
        // more/less history at the edges instead, matching real TradingView feel.
        lockVisibleTimeRangeOnResize: false,
        rightBarStaysOnScroll: true,
        minBarSpacing: 0.5,
        // @ts-ignore
        tickMarkFormatter: (time: any, tickMarkType: any) => {
          const d = new Date((time as number) * 1000);
          if (tickMarkType === 0 /* Year */) return d.getFullYear().toString();
          if (tickMarkType === 1 /* Month */) return d.toLocaleString(undefined, { month: 'short' });
          if (tickMarkType === 2 /* Day */) return d.getDate().toString();
          return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },
      },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true, pressedMouseMove: true },
      kineticScroll: { mouse: true, touch: true },
      localization: { priceFormatter: (price: number) => price.toFixed(2) },
      // Floor the initial size: a mount that races a layout collapse should never
      // hand lightweight-charts a 0-width canvas (see ResizeObserver below for the
      // ongoing case).
      width: Math.max(mainRef.current.clientWidth || 0, 300),
      height: mainRef.current.clientHeight,
    });

    const times = baseCandles.map((c: any) => c.time);
    const readySourceCandles = fullBaseCandles.length ? fullBaseCandles : baseCandles;
    const readyKey = `${symbol}|${tf}|${readySourceCandles.length}|${readySourceCandles[0]?.time ?? ''}|${readySourceCandles[readySourceCandles.length - 1]?.time ?? ''}`;
    const candleData = baseCandles.map((b: any) => ({
      time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close,
    }));

    let mainS;
    // Main series: enable labels like TradingView (last value on price scale)
    const mainOpts = { priceLineVisible: true, lastValueVisible: true };
    if (chartType === 'candles') {
      mainS = chart.addSeries(CandlestickSeries, {
        upColor: workspace.appearance.candleUp, downColor: workspace.appearance.candleDown,
        borderUpColor: workspace.appearance.candleUp, borderDownColor: workspace.appearance.candleDown,
        wickUpColor: workspace.appearance.candleUp, wickDownColor: workspace.appearance.candleDown,
        borderVisible: true,
        ...mainOpts,
      });
    } else if (chartType === 'bars') {
      mainS = chart.addSeries(BarSeries, {
        upColor: tv.green, downColor: tv.red,
        ...mainOpts,
      });
    } else if (chartType === 'line') {
      mainS = chart.addSeries(LineSeries, {
        color: tv.blue,
        lineWidth: 2,
        ...mainOpts,
      });
    } else if (chartType === 'area') {
      mainS = chart.addSeries(AreaSeries, {
        topColor: tv.blue + '66',
        bottomColor: tv.blue + '11',
        lineColor: tv.blue,
        lineWidth: 2,
        ...mainOpts,
      });
    }
    seriesRefs.current.main = mainS;
    seriesRefs.current.candle = mainS; // keep for compatibility with drawing code
    let candleS: any = mainS || null;
    if (mainS) {
      mainS.setData(candleData.map(d => (chartType === 'line' || chartType === 'area') ? { time: d.time, value: d.close } : d ));
      // TV style current price line on main series
      mainS.applyOptions({
        priceLineVisible: true,
        priceLineWidth: 1 as any,
        priceLineColor: tv.text,
        priceLineStyle: LineStyle.Dashed,
      });
    }

    const closes = baseCandles.map((c: any) => c.close);
    const highs = baseCandles.map((c: any) => c.high);
    const lows = baseCandles.map((c: any) => c.low);

    // EMA
    if (activeIndicators.has('ema')) {
      const style = indicatorStyle('ema', { color: tv.blue, secondaryColor: tv.orange, lineWidth: 2, visible: true });
      const e1 = ema(closes, params.ema1 || 9);
      const e2 = ema(closes, params.ema2 || 21);
      const e9s = chart.addSeries(LineSeries, { color: style.color, lineWidth: style.lineWidth as any, visible: style.visible, priceLineVisible: false, lastValueVisible: true, title: `EMA(${params.ema1 || 9})` });
      seriesRefs.current.ema9 = e9s;
      e9s.setData(e1.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
      const e21s = chart.addSeries(LineSeries, { color: style.secondaryColor || tv.orange, lineWidth: style.lineWidth as any, visible: style.visible, priceLineVisible: false, lastValueVisible: true, title: `EMA(${params.ema2 || 21})` });
      seriesRefs.current.ema21 = e21s;
      e21s.setData(e2.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
    }

    // Bollinger
    if (activeIndicators.has('bb')) {
      const style = indicatorStyle('bb', { color: tv.cyan, secondaryColor: tv.purple || '#a371f7', lineWidth: 1, visible: true });
      const bb = bollingerBands(closes, params.bbPeriod || 20, params.bbStd || 2);
      const bbMid = chart.addSeries(LineSeries, { color: style.color, lineWidth: style.lineWidth as any, visible: style.visible, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: true, title: `BB(${params.bbPeriod || 20})` });
      const bbUpper = chart.addSeries(LineSeries, { color: (style.secondaryColor || tv.purple || '#a371f7') + '99', lineWidth: style.lineWidth as any, visible: style.visible, priceLineVisible: false, lastValueVisible: true, title: `BB Upper` });
      const bbLower = chart.addSeries(LineSeries, { color: (style.secondaryColor || tv.purple || '#a371f7') + '99', lineWidth: style.lineWidth as any, visible: style.visible, priceLineVisible: false, lastValueVisible: true, title: `BB Lower` });
      seriesRefs.current.bbMid = bbMid; seriesRefs.current.bbUpper = bbUpper; seriesRefs.current.bbLower = bbLower;
      bbMid.setData(bb.flatMap((b, i) => (b.middle != null ? [{ time: times[i] as any, value: b.middle }] : [])));
      bbUpper.setData(bb.flatMap((b, i) => (b.upper != null ? [{ time: times[i] as any, value: b.upper }] : [])));
      bbLower.setData(bb.flatMap((b, i) => (b.lower != null ? [{ time: times[i] as any, value: b.lower }] : [])));
    }

    // VWAP
    if (activeIndicators.has('vwap')) {
      const style = indicatorStyle('vwap', { color: tv.purple, lineWidth: 2, visible: true });
      const v = vwap(baseCandles as any);
      const vs = chart.addSeries(LineSeries, { color: style.color, lineWidth: style.lineWidth as any, visible: style.visible, priceLineVisible: false, lastValueVisible: true, title: 'VWAP' });
      seriesRefs.current.vwap = vs;
      vs.setData(v.map((p) => ({ time: p.time as any, value: p.value })));
    }

    // SuperTrend - show selected variants with direction-based colors (bull=green, bear=red)
    const addSupertrendWithDirection = (period: number, mult: number, label: string, styleKey: string) => {
      const style = indicatorStyle(styleKey, { color: tv.green, secondaryColor: tv.red, lineWidth: 2, visible: true });
      const stData = supertrend(highs, lows, closes, period, mult);
      // One SuperTrend line whose colour flips with the trend. Rendered as one short
      // line series per contiguous same-direction RUN (green up / red down) — NOT two
      // full-length green/red series, because v5 LineSeries connects across whitespace
      // so those drew the green line straight through down-trends and vice-versa = two
      // crossing lines per indicator. See supertrendRuns. Only ONE series carries the
      // legend title (the first up-run, else the first run) so the indicator shows once.
      const runs = supertrendRuns(stData, times);
      const titleIdx = runs.findIndex((r) => r.up);
      const ti = titleIdx >= 0 ? titleIdx : 0;
      runs.forEach((run, ri) => {
        const s = chart.addSeries(LineSeries, {
          color: (run.up ? style.color : (style.secondaryColor || tv.red)) + '99', lineWidth: style.lineWidth as any, visible: style.visible,
          priceLineVisible: false, lastValueVisible: false,
          ...(ri === ti ? { title: label } : {}),
        });
        s.setData(run.points as any);
      });
    };

    if (activeIndicators.has('st-fast')) {
      const p = params.stFastPeriod || 21, m = params.stFastMult || 1;
      addSupertrendWithDirection(p, m, `ST fast (${p},${m})`, 'st-fast');
    }
    if (activeIndicators.has('st-mid')) {
      const p = params.stMidPeriod || 14, m = params.stMidMult || 2;
      addSupertrendWithDirection(p, m, `ST mid (${p},${m})`, 'st-mid');
    }
    if (activeIndicators.has('st-slow')) {
      const p = params.stSlowPeriod || 7, m = params.stSlowMult || 3;
      addSupertrendWithDirection(p, m, `ST slow (${p},${m})`, 'st-slow');
    }

    // Volume
    if (activeIndicators.has('vol')) {
      const volumeStyle = indicatorStyle('vol', { color: tv.green, secondaryColor: tv.red, lineWidth: 1, visible: true });
      const volS = chart.addSeries(HistogramSeries, { visible: volumeStyle.visible, priceFormat: { type: 'volume' }, priceScaleId: 'volume', title: 'Volume' });
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      seriesRefs.current.vol = volS;
      volS.setData(baseCandles.map((b: any) => ({
        time: b.time as any, value: b.volume || 0,
        color: b.close >= b.open ? `${volumeStyle.color}55` : `${volumeStyle.secondaryColor || tv.red}55`,
      })));
    }

    const addLineIndicator = (
      refKey: string,
      title: string,
      values: Array<number | null>,
      style: IndicatorStyle,
      priceScaleId?: string,
    ) => {
      const series = chart.addSeries(LineSeries, {
        color: style.color,
        lineWidth: style.lineWidth as any,
        visible: style.visible,
        priceLineVisible: false,
        lastValueVisible: true,
        title,
        ...(priceScaleId ? { priceScaleId } : {}),
      });
      if (priceScaleId) chart.priceScale(priceScaleId).applyOptions({ visible: false, scaleMargins: { top: 0.78, bottom: 0.02 } });
      series.setData(values.flatMap((value, index) => value != null && Number.isFinite(value)
        ? [{ time: times[index] as any, value }]
        : []));
      seriesRefs.current[refKey] = series;
    };

    if (activeIndicators.has('sma')) {
      const period = params.smaPeriod || 50;
      addLineIndicator('sma', `SMA(${period})`, sma(closes, period), indicatorStyle('sma', { color: tv.orange, lineWidth: 2, visible: true }));
    }
    if (activeIndicators.has('atr')) {
      const period = params.atrPeriod || 14;
      addLineIndicator('atr', `ATR(${period})`, atr(highs, lows, closes, period), indicatorStyle('atr', { color: tv.cyan, lineWidth: 2, visible: true }), 'atr');
    }
    if (activeIndicators.has('stoch')) {
      const period = params.stochPeriod || 14;
      addLineIndicator('stoch', `Stochastic(${period})`, stochastic(highs, lows, closes, period), indicatorStyle('stoch', { color: tv.purple, lineWidth: 2, visible: true }), 'stoch');
    }

    workspace.extraIndicators.forEach((indicator) => {
      const period = Math.max(1, indicator.period || 1);
      let values: Array<number | null> = [];
      let scaleId: string | undefined;
      if (indicator.kind === 'ema') values = ema(closes, period);
      if (indicator.kind === 'sma') values = sma(closes, period);
      if (indicator.kind === 'rsi') { values = rsi(closes, period); scaleId = `extra-${indicator.id}`; }
      if (indicator.kind === 'atr') { values = atr(highs, lows, closes, period); scaleId = `extra-${indicator.id}`; }
      if (indicator.kind === 'stochastic') { values = stochastic(highs, lows, closes, period); scaleId = `extra-${indicator.id}`; }
      if (indicator.kind === 'formula') values = formulaSeries(indicator.formula || 'hlc3', baseCandles);
      addLineIndicator(`extra:${indicator.id}`, `${indicator.name}(${indicator.kind === 'formula' ? indicator.formula : period})`, values, indicator.style, scaleId);
    });

    const comparisons = comparisonCandlesRef.current;
    comparisons.forEach(({ overlay, candles }) => {
      if (!overlay.visible || !candles.length) return;
      const priceScaleId = overlay.mode === 'percent' ? 'compare-percent' : `compare-${overlay.id}`;
      const compareSeries = chart.addSeries(LineSeries, {
        color: overlay.color,
        lineWidth: 2,
        priceScaleId,
        priceLineVisible: false,
        lastValueVisible: true,
        title: overlay.mode === 'percent' ? `${overlay.symbol} %` : overlay.symbol,
      });
      chart.priceScale(priceScaleId).applyOptions({ visible: false, autoScale: true });
      compareSeries.setData(comparisonSeriesData(candles, overlay.mode).map((point) => ({ time: point.time as any, value: point.value })));
      seriesRefs.current[`compare:${overlay.id}`] = compareSeries;
    });

    // Drawings render (full support + fib variants + ray extend)
    drawings.forEach((d, idx) => {
      const idBase = `draw${idx}`;
      const isSel = d.id === selectedDrawingId;
      const lw = isSel ? 2.5 : 1;
      if (d.type === 'hline' && candleS!!) {
        const pl = candleS!.createPriceLine({
          price: d.price!, color: d.color || tv.amber, lineWidth: (isSel ? 2 : 1) as any, lineStyle: LineStyle.Dashed, axisLabelVisible: true,
        });
        seriesRefs.current[idBase] = pl;
      } else if ((d.type === 'trend' || d.type === 'ray') && d.points && d.points.length === 2) {
        let points = [...d.points];
        if (d.type === 'ray') {
          const vr = chart.timeScale().getVisibleRange();
          const visTo = (vr?.to ?? (points[1].time as any)) as number;
          const visibleTo = visTo + 200000;
          const [p1, p2] = points;
          const slope = (p2.price - p1.price) / Math.max(1, ((p2.time as any) - (p1.time as any)) || 1);
          const extP = p2.price + slope * (visibleTo - (p2.time as any));
          points = [p1, { time: visibleTo as any, price: extP }];
        }
        const s = chart.addSeries(LineSeries, {
          color: isSel ? (d.color || tv.cyan) : (d.color || (d.type === 'ray' ? tv.cyan : tv.green)),
          lineWidth: (isSel ? 2.5 : 1.5) as any, priceLineVisible: false, lastValueVisible: true,
        });
        seriesRefs.current[idBase] = s;
        s.setData(points.map((p: any) => ({ time: p.time as any, value: p.price })));
      } else if (d.type === 'fib' && d.points && d.points.length === 2) {
        const [p1, p2] = d.points;
        const minP = Math.min(p1.price, p2.price);
        const maxP = Math.max(p1.price, p2.price);
        const isExt = d.variant === 'ext';
        const isFan = d.variant === 'fan';
        const ratios = isExt
          ? [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618, 2.0]
          : [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
        if (!isFan) {
          ratios.forEach((ratio, i) => {
            const fibPrice = minP + (maxP - minP) * ratio;
            const fid = `${idBase}_fib${i}`;
            const pl = candleS!.createPriceLine({
              price: fibPrice,
              color: isSel ? '#fff' : (d.color || tv.purple),
              lineWidth: (isSel ? 1.5 : 1) as any,
              lineStyle: (ratio === 0 || ratio === 1) ? LineStyle.Solid : LineStyle.Dashed,
              axisLabelVisible: true,
              title: `F${ratio}`,
            });
            seriesRefs.current[fid] = pl;
          });
        } else {
          // Fib Fan: 3 angled rays from p1
          const fanRatios = [0.382, 0.5, 0.618];
          fanRatios.forEach((r, i) => {
            const fanP = { time: (p2.time as any), price: p1.price + (p2.price - p1.price) * r };
            const s = chart.addSeries(LineSeries, { color: d.color || tv.purple, lineWidth: 2 as any, priceLineVisible: false, lastValueVisible: true });
            seriesRefs.current[`${idBase}_fan${i}`] = s;
            s.setData([ { time: (p1.time as any), value: p1.price }, { time: fanP.time as any, value: fanP.price } ]);
          });
        }
      } else if (d.type === 'rect' && d.points && d.points.length === 2) {
        const [p1, p2] = d.points;
        const y1 = Math.min(p1.price, p2.price);
        const y2 = Math.max(p1.price, p2.price);
        const t1 = Math.min(p1.time, p2.time);
        const t2 = Math.max(p1.time, p2.time);
        [y1, y2].forEach((y, i) => {
          const pl = candleS!.createPriceLine({
            price: y, color: d.color || tv.red, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true,
            title: i === 0 ? 'R-L' : 'R-H',
          });
          seriesRefs.current[`${idBase}_h${i}`] = pl;
        });
        const side1 = chart.addSeries(LineSeries, { color: isSel ? '#fff' : (d.color || tv.red), lineWidth: (isSel ? 2 : 1) as any, priceLineVisible: false, lastValueVisible: true });
        const side2 = chart.addSeries(LineSeries, { color: isSel ? '#fff' : (d.color || tv.red), lineWidth: (isSel ? 2 : 1) as any, priceLineVisible: false, lastValueVisible: true });
        seriesRefs.current[`${idBase}_v1`] = side1;
        seriesRefs.current[`${idBase}_v2`] = side2;
        const delta = 2;
        side1.setData([{ time: (t1 - delta) as any, value: y1 }, { time: (t1 + delta) as any, value: y2 }]);
        side2.setData([{ time: (t2 - delta) as any, value: y1 }, { time: (t2 + delta) as any, value: y2 }]);
      } else if (d.type === 'text' && candleS!! && d.time != null) {
        createSeriesMarkers?.(candleS!, [{
          time: d.time as any,
          position: 'aboveBar',
          color: d.color || tv.text,
          shape: 'square',
          text: (d.text || 'Note').slice(0, 14),
        }]);
      } else if (d.type === 'pitchfork' && d.points && d.points.length === 3) {
        const [a, b, c] = d.points;
        const midBC = { time: (((b.time as any) + (c.time as any)) / 2), price: (b.price + c.price) / 2 };
        const lines = [
          [a, midBC],
          [b, { time: midBC.time + (midBC.time - a.time), price: midBC.price + (midBC.price - a.price) }],
          [c, { time: midBC.time + (midBC.time - a.time), price: midBC.price + (midBC.price - a.price) * -1 }],
        ];
        lines.forEach((pts, li) => {
          const s = chart.addSeries(LineSeries, {
            color: isSel ? '#fff' : (d.color || '#ff9800'), lineWidth: (li === 0 ? (isSel ? 2.5 : 2) : (isSel ? 1.5 : 1)) as any,
            priceLineVisible: false, lastValueVisible: false,
          });
          seriesRefs.current[`${idBase}_pf${li}`] = s;
          s.setData(pts.map((p: any) => ({ time: p.time as any, value: p.price })));
        });
      }
    });

    // Position / entry marker
    if (symbolPos && symbolPos.average_price) {
      const entryP = parseFloat(symbolPos.average_price);
      if (entryP > 0 && candleS!) {
        const entryLine = chart.addSeries(LineSeries, { color: tv.blue, lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: true });
        seriesRefs.current.posEntry = entryLine;
        entryLine.setData(times.map((t: number) => ({ time: t as any, value: entryP })));
        createSeriesMarkers?.(candleS!, [{
          time: times[times.length - 1] as any, position: 'aboveBar', color: tv.blue, shape: 'arrowDown', text: 'Pos',
        }]);
      }
    }

    // Source-aware signal marker. CE and PE derivative entries are both
    // long-premium BUYs, therefore both require a fresh THREE-GREEN transition
    // on the selected contract's own premium chart. A bearish underlying regime
    // must never turn a nearby three-red premium transition into an Entry marker.
    if (signalData && signalData.timestamp_ms != null && times.length && candleS) {
      try {
        const entryTargetSec = signalData.timestamp_ms / 1000;
        const premiumTargetSec = (signalData.premium_signal_ms ?? signalData.timestamp_ms) / 1000;
        const avgSpacing = times.length > 1 ? Math.abs(times[times.length - 1] - times[0]) / (times.length - 1) : Infinity;
        const broadTolerance = Math.max(avgSpacing * 1.25, 3600);
        // Premium timestamps are emitted from the exact option candle. Keep this
        // strict so a grouped-parent timestamp cannot snap to a neighbouring bar.
        const premiumTolerance = 60;
        const stF = supertrend(highs, lows, closes, params.stFastPeriod || 21, params.stFastMult || 1);
        const stM = supertrend(highs, lows, closes, params.stMidPeriod || 14, params.stMidMult || 2);
        const stS = supertrend(highs, lows, closes, params.stSlowPeriod || 7, params.stSlowMult || 3);
        const source = signalData.source || 'spot';
        const markers: any[] = [];

        // Confluence is checked before the generic premium-basis branch so its label
        // remains reachable. Both CE and PE premium confirmations are three-green.
        if (source === 'confluence') {
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', premiumTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Confluence' });
        } else if (source === 'derivatives' || signalData.marker_basis === 'premium') {
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', premiumTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Entry' });
        } else if (signalData.marker_basis === 'external') {
          const idx = nearestTimeIndex(times, entryTargetSec, broadTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'aboveBar', color: tv.blue, shape: 'circle', text: 'Underlying entry' });
        } else {
          const dir = (signalData.direction || '').toLowerCase();
          const wanted = dir === 'short' || (signalData.regime || '').toUpperCase() === 'BEAR' ? 'down' : 'up';
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, entryTargetSec, wanted, broadTolerance);
          if (idx >= 0) markers.push({
            time: times[idx] as any,
            position: wanted === 'up' ? 'belowBar' : 'aboveBar',
            color: wanted === 'up' ? tv.green : tv.red,
            shape: wanted === 'up' ? 'arrowUp' : 'arrowDown',
            text: 'Entry',
          });
        }
        if (markers.length) createSeriesMarkers?.(candleS, markers);
      } catch { /* invalid signal metadata must never break chart rendering */ }
    }

    mainChartRef.current = chart;

    // Last-price flash badge: recompute pixel Y for the latest close + flash green/red on change
    const updatePriceBadge = () => {
      if (!candleS || !baseCandles.length) return;
      const lastClose = baseCandles[baseCandles.length - 1].close;
      let y: number | null = null;
      try {
        // @ts-ignore - priceToCoordinate exists at runtime across lightweight-charts versions
        y = candleS.priceToCoordinate ? candleS.priceToCoordinate(lastClose) : null;
      } catch { y = null; }
      if (y == null) return;
      const prev = prevCloseRef.current;
      if (prev != null && prev !== lastClose) {
        const dir: 'up' | 'down' = lastClose > prev ? 'up' : 'down';
        setPriceFlashDir(dir);
        if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
        flashTimeoutRef.current = setTimeout(() => setPriceFlashDir(null), 400);
      }
      prevCloseRef.current = lastClose;
      setPriceBadge({ y, price: lastClose });
    };

    // Right price-scale pixel width (sizes the context-menu hit strip over the axis)
    const updateRightScaleWidth = () => {
      try {
        const w = chart.priceScale('right').width();
        if (w && w > 0) setRightScaleWidth(w);
      } catch {}
    };

    // Apply the visible range on EVERY (re)build - the effect re-runs on each
    // data poll, so gating this to first-mount lost the zoom on every refresh.
    const isNewInstrument = instrumentKeyRef.current !== instrumentKey;
    instrumentKeyRef.current = instrumentKey;
    const applyView = () => {
      try {
        const timeScale = chart.timeScale();
        if (persistedZoom && appliedPersistedRef.current !== persistedZoom) {
          // A freshly loaded/reset saved range for this instrument - honour it once.
          appliedPersistedRef.current = persistedZoom;
          timeScale.setVisibleRange(persistedZoom);
        } else if (isNewInstrument) {
          // Genuine symbol/timeframe switch - start from a fresh fit (or saved zoom).
          lastRangeRef.current = null;
          if (persistedZoom) { appliedPersistedRef.current = persistedZoom; timeScale.setVisibleRange(persistedZoom); }
          else timeScale.fitContent();
        } else if (lastRangeRef.current) {
          // Same instrument, rebuilt only because candle data refreshed - keep the
          // exact range the user was viewing instead of snapping to default.
          timeScale.setVisibleRange(lastRangeRef.current);
        } else {
          timeScale.fitContent();
        }
      } catch { try { chart.timeScale().fitContent(); } catch {} }
    };
    // Apply synchronously (no setTimeout) so the browser never paints the
    // library's default auto-fit frame before the persisted/last-viewed range
    // is applied - that gap was the visible "jump" on chart load.
    applyView();
    lastSyncedCandlesRef.current = baseCandles;

    // Crosshair OHLC (pin-point) + live dashed preview for in-progress multi-point drawings
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time || !param.seriesPrices) { setCurrentBarInfo(null); clearPreview(); return; }
      const c = param.seriesPrices.get(candleS!);
      if (c && typeof c === 'object') {
        setCurrentBarInfo({ time: param.time, open: (c as any).open, high: (c as any).high, low: (c as any).low, close: (c as any).close });
      }

      const mode = drawModeRef.current;
      const basePts = drawingPointsRef.current;
      const previewModes = ['trend', 'ray', 'fib', 'fibext', 'fibfan', 'rect', 'pitchfork'];
      if (previewModes.includes(mode) && basePts.length >= 1) {
        let priceVal: number | null = null;
        if (c && typeof c === 'object') priceVal = (c as any).close;
        else if (typeof c === 'number') priceVal = c;
        if (priceVal == null && baseCandles.length) priceVal = baseCandles[baseCandles.length - 1].close;
        if (priceVal != null) {
          const snapped = snapToOHLCRef.current(priceVal, baseCandles, chart.timeScale().getVisibleRange());
          renderPreview([...basePts, { time: param.time as number, price: snapped }], mode);
        }
      } else {
        clearPreview();
      }
    });

    // Drawing placement via click
    chart.subscribeClick((param: any) => {
      const snapFn = (p: number, bc: any[], _r?: any) => snapToOHLCRef.current(p, bc, chart.timeScale().getVisibleRange());
      handleChartClickRef.current(param, baseCandles, chart, tv, snapFn);
    });

    const ro = new ResizeObserver(() => {
      if (mainRef.current) {
        const w = mainRef.current.clientWidth;
        const h = mainRef.current.clientHeight;
        // Defensive floor (mirrors the window-resize handler above): never push a
        // transient 0/near-0 size into the chart instance — a brief layout collapse
        // during a panel-toggle race would otherwise permanently zero the canvas.
        if (w > 10 && h > 10) {
          chart.applyOptions({ width: w, height: h });
          setTimeout(drawHandles, 0);
          setTimeout(updatePriceBadge, 0);
          setTimeout(updateRightScaleWidth, 0);
        }
      }
    });
    ro.observe(mainRef.current);

    const ts = chart.timeScale();
    const zh = (range: any) => {
      if (!range) return;
      // Remember what the user is looking at so a data-poll rebuild can restore it.
      lastRangeRef.current = range;
      if (onZoomChange) onZoomChange(range);
    };
    ts.subscribeVisibleTimeRangeChange(zh);

    // Redraw handles on pan/zoom so point positions stay accurate (real coords)
    const handleSync = () => { if (selectedDrawingId) setTimeout(drawHandles, 0); };
    ts.subscribeVisibleTimeRangeChange(handleSync);

    // Initial profile + handles + price badge + scale width. A zero-delay timer
    // gives lightweight-charts one layout pass without imposing a visible 120ms
    // delay on every timeframe switch, and cleanup cancels stale ready callbacks
    // from charts that were removed during rapid switches.
    const readyTimer = window.setTimeout(() => {
      drawVolumeProfile();
      drawHandles();
      updatePriceBadge();
      updateRightScaleWidth();
      onChartReadyRef.current?.(readyKey);
    }, 0);

    return () => {
      window.clearTimeout(readyTimer);
      try { ts.unsubscribeVisibleTimeRangeChange(zh); } catch {}
      try { ts.unsubscribeVisibleTimeRangeChange(handleSync); } catch {}
      if (flashTimeoutRef.current) { clearTimeout(flashTimeoutRef.current); flashTimeoutRef.current = null; }
      ro.disconnect();
      chart.remove();
      mainChartRef.current = null;
      seriesRefs.current = {};
      previewSeriesRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, tf, activeIndicators, params, tv, drawings, isLogScale, isDark, persistedZoom, onZoomChange, showVP, chartType, layoutMode, hasCandles, workspace, replayIndex]);

  // Sub RSI pane. Reads baseCandles via the ref (see main chart effect above) so
  // this pane also only tears down/rebuilds on structural changes, not on every
  // candle-data poll tick.
  useEffect(() => {
    const baseCandles = baseCandlesRef.current;
    const el = rsiRef.current;
    const main = mainChartRef.current;
    if (layoutMode !== '1' || !el || !activeIndicators.has('rsi') || !baseCandles.length) {
      if (subChartsRef.current.rsi) { subChartsRef.current.rsi.remove(); subChartsRef.current.rsi = undefined; }
      return;
    }
    const rChart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: tv.bg }, textColor: tv.dim, fontFamily: tv.fontFamily },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      // lockVisibleTimeRangeOnResize: false to match the main chart above -
      // keeps bar spacing in sync with it across a resize instead of the sub-pane
      // stretching independently while the main pane doesn't (or vice versa).
      timeScale: { borderVisible: false, timeVisible: true, rightBarStaysOnScroll: true, lockVisibleTimeRangeOnResize: false, minBarSpacing: 0.5 },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true, pressedMouseMove: true },
      kineticScroll: { mouse: true, touch: true },
      width: el.clientWidth, height: 108,
    });
    const closes = baseCandles.map((c: any) => c.close);
    const times = baseCandles.map((c: any) => c.time);
    const r = rsi(closes, params.rsiPeriod || 14);
    const rsiStyle = indicatorStyle('rsi', { color: tv.blue, lineWidth: 2, visible: true });
    const line = rChart.addSeries(LineSeries, { color: rsiStyle.color, lineWidth: rsiStyle.lineWidth as any, visible: rsiStyle.visible, priceLineVisible: false, lastValueVisible: true, title: `RSI(${params.rsiPeriod || 14})` });
    line.setData(r.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
    const ob = rChart.addSeries(LineSeries, { color: tv.red + '66', lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: false, title: 'Overbought (70)' });
    const os = rChart.addSeries(LineSeries, { color: tv.green + '66', lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: false, title: 'Oversold (30)' });
    ob.setData(times.map(t => ({ time: t as any, value: 70 })));
    os.setData(times.map(t => ({ time: t as any, value: 30 })));
    subChartsRef.current.rsi = rChart;
    subChartsRef.current.rsiSeries = { line, ob, os };

    // Track the subscribed callback so cleanup can unsubscribe it from the
    // exact main-chart instance it was attached to (the main chart is torn
    // down/recreated by its own effect whenever any of its deps change, so
    // this pane's deps below are widened to match the deps that trigger a
    // main-chart rebuild — otherwise this sync would go stale against a
    // disposed chart and the RSI pane would silently stop following pans/zooms).
    let sync: ((rg: any) => void) | null = null;
    if (main) {
      sync = (rg: any) => { try { rChart.timeScale().setVisibleRange(rg); } catch {} };
      main.timeScale().subscribeVisibleTimeRangeChange(sync);
    }
    const ro = new ResizeObserver(() => rChart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      if (main && sync) { try { main.timeScale().unsubscribeVisibleTimeRangeChange(sync); } catch {} }
      ro.disconnect(); rChart.remove(); subChartsRef.current.rsi = undefined; subChartsRef.current.rsiSeries = undefined;
    };
    // Deps intentionally mirror the main chart-creation effect's dep array
    // (minus baseCandles/snapToOHLC - see the comment above this effect) so
    // this pane is torn down/recreated in lockstep with the main chart on every
    // trigger that rebuilds it — otherwise `sync` above goes stale against a
    // disposed chart instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, tf, activeIndicators, params, tv, drawings, isLogScale, isDark, persistedZoom, onZoomChange, showVP, chartType, layoutMode, hasCandles, workspace.styles, replayIndex]);

  // Sub MACD pane. Reads baseCandles via the ref - see the RSI pane above.
  useEffect(() => {
    const baseCandles = baseCandlesRef.current;
    const el = macdRef.current;
    const main = mainChartRef.current;
    if (layoutMode !== '1' || !el || !activeIndicators.has('macd') || !baseCandles.length) {
      if (subChartsRef.current.macd) { subChartsRef.current.macd.remove(); subChartsRef.current.macd = undefined; }
      return;
    }
    const mChart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: tv.bg }, textColor: tv.dim, fontFamily: tv.fontFamily },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      // lockVisibleTimeRangeOnResize: false to match the main chart above -
      // keeps bar spacing in sync with it across a resize instead of the sub-pane
      // stretching independently while the main pane doesn't (or vice versa).
      timeScale: { borderVisible: false, timeVisible: true, rightBarStaysOnScroll: true, lockVisibleTimeRangeOnResize: false, minBarSpacing: 0.5 },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true, pressedMouseMove: true },
      kineticScroll: { mouse: true, touch: true },
      width: el.clientWidth, height: 108,
    });
    const closes = baseCandles.map((c: any) => c.close);
    const times = baseCandles.map((c: any) => c.time);
    const m = macd(closes, params.macdFast || 12, params.macdSlow || 26, params.macdSig || 9);
    const macdStyle = indicatorStyle('macd', { color: tv.blue, secondaryColor: tv.orange, lineWidth: 2, visible: true });
    const ml = mChart.addSeries(LineSeries, { color: macdStyle.color, lineWidth: macdStyle.lineWidth as any, visible: macdStyle.visible, priceLineVisible: false, lastValueVisible: true, title: 'MACD' });
    const sl = mChart.addSeries(LineSeries, { color: macdStyle.secondaryColor || tv.orange, lineWidth: Math.max(1, macdStyle.lineWidth - 1) as any, visible: macdStyle.visible, priceLineVisible: false, lastValueVisible: true, title: 'Signal' });
    const hist = mChart.addSeries(HistogramSeries, { priceScaleId: 'hist', title: 'Histogram' });
    ml.setData(m.flatMap((p, i) => p.macd != null ? [{ time: times[i] as any, value: p.macd }] : []));
    sl.setData(m.flatMap((p, i) => p.signal != null ? [{ time: times[i] as any, value: p.signal }] : []));
    hist.setData(m.flatMap((p, i) => p.hist != null ? [{ time: times[i] as any, value: p.hist, color: p.hist >= 0 ? tv.green + '88' : tv.red + '88' }] : []));
    subChartsRef.current.macd = mChart;
    subChartsRef.current.macdSeries = { ml, sl, hist };

    // See the RSI pane above for why `sync` is hoisted + explicitly
    // unsubscribed, and why the deps below are widened to match whatever
    // triggers the main chart to be torn down/rebuilt.
    let sync: ((rg: any) => void) | null = null;
    if (main) {
      sync = (rg: any) => { try { mChart.timeScale().setVisibleRange(rg); } catch {} };
      main.timeScale().subscribeVisibleTimeRangeChange(sync);
    }
    const ro = new ResizeObserver(() => mChart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => {
      if (main && sync) { try { main.timeScale().unsubscribeVisibleTimeRangeChange(sync); } catch {} }
      ro.disconnect(); mChart.remove(); subChartsRef.current.macd = undefined; subChartsRef.current.macdSeries = undefined;
    };
    // Deps intentionally mirror the main chart-creation effect's dep array
    // (minus baseCandles/snapToOHLC) — see the RSI pane above for why.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, tf, activeIndicators, params, tv, drawings, isLogScale, isDark, persistedZoom, onZoomChange, showVP, chartType, layoutMode, hasCandles, workspace.styles, replayIndex]);

  // Live data-only sync: pushes fresh candle data onto the ALREADY-BUILT chart(s)
  // via setData() whenever only the candle data changed (the common idle-poll
  // case, since the in-progress bar mutates on ~every useCandles tick) — no
  // chart.remove()/createChart(), no ResizeObserver/crosshair resubscription, no
  // zoom reset. SuperTrend runs, drawings, and markers are intentionally left
  // alone here (they only need a recompute on a structural rebuild above) since
  // SuperTrend's per-run line series aren't tracked by stable keys and can't be
  // patched in place without leaking series on every tick.
  useEffect(() => {
    const chart = mainChartRef.current;
    if (!chart || !baseCandles.length) return;
    if (lastSyncedCandlesRef.current === baseCandles) return; // just applied by a structural rebuild this tick
    lastSyncedCandlesRef.current = baseCandles;

    const ind = activeIndicatorsRef.current;
    const p = paramsRef.current;
    const ct = chartTypeRef.current;
    const tv2 = tvRef.current;
    const refs = seriesRefs.current;

    const times = baseCandles.map((c: any) => c.time);
    const closes = baseCandles.map((c: any) => c.close);
    const highs = baseCandles.map((c: any) => c.high);
    const lows = baseCandles.map((c: any) => c.low);

    try {
      if (refs.main) {
        const data = baseCandles.map((b: any) => (ct === 'line' || ct === 'area')
          ? { time: b.time as any, value: b.close }
          : { time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close });
        refs.main.setData(data);
      }
      if (ind.has('ema')) {
        refs.ema9?.setData(ema(closes, p.ema1 || 9).flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
        refs.ema21?.setData(ema(closes, p.ema2 || 21).flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
      }
      if (ind.has('bb') && refs.bbMid) {
        const bb = bollingerBands(closes, p.bbPeriod || 20, p.bbStd || 2);
        refs.bbMid.setData(bb.flatMap((b, i) => (b.middle != null ? [{ time: times[i] as any, value: b.middle }] : [])));
        refs.bbUpper?.setData(bb.flatMap((b, i) => (b.upper != null ? [{ time: times[i] as any, value: b.upper }] : [])));
        refs.bbLower?.setData(bb.flatMap((b, i) => (b.lower != null ? [{ time: times[i] as any, value: b.lower }] : [])));
      }
      if (ind.has('vwap') && refs.vwap) {
        const v = vwap(baseCandles as any);
        refs.vwap.setData(v.map((pt) => ({ time: pt.time as any, value: pt.value })));
      }
      if (ind.has('vol') && refs.vol) {
        const volumeStyle = indicatorStyle('vol', { color: tv2.green, secondaryColor: tv2.red, lineWidth: 1, visible: true });
        refs.vol.setData(baseCandles.map((b: any) => ({
          time: b.time as any, value: b.volume || 0,
          color: b.close >= b.open ? `${volumeStyle.color}55` : `${volumeStyle.secondaryColor || tv2.red}55`,
        })));
      }
      if (ind.has('sma') && refs.sma) {
        refs.sma.setData(sma(closes, p.smaPeriod || 50).flatMap((value, index) => value != null ? [{ time: times[index] as any, value }] : []));
      }
      if (ind.has('atr') && refs.atr) {
        refs.atr.setData(atr(highs, lows, closes, p.atrPeriod || 14).flatMap((value, index) => value != null ? [{ time: times[index] as any, value }] : []));
      }
      if (ind.has('stoch') && refs.stoch) {
        refs.stoch.setData(stochastic(highs, lows, closes, p.stochPeriod || 14).flatMap((value, index) => value != null ? [{ time: times[index] as any, value }] : []));
      }
      workspace.extraIndicators.forEach((indicator) => {
        const series = refs[`extra:${indicator.id}`];
        if (!series) return;
        const period = Math.max(1, indicator.period || 1);
        let values: Array<number | null> = [];
        if (indicator.kind === 'ema') values = ema(closes, period);
        if (indicator.kind === 'sma') values = sma(closes, period);
        if (indicator.kind === 'rsi') values = rsi(closes, period);
        if (indicator.kind === 'atr') values = atr(highs, lows, closes, period);
        if (indicator.kind === 'stochastic') values = stochastic(highs, lows, closes, period);
        if (indicator.kind === 'formula') values = formulaSeries(indicator.formula || 'hlc3', baseCandles);
        series.setData(values.flatMap((value, index) => value != null && Number.isFinite(value) ? [{ time: times[index] as any, value }] : []));
      });
    } catch { /* a mid-tick series/chart disposal race - next poll will retry */ }

    // Price flash badge (mirrors the structural effect's updatePriceBadge)
    try {
      if (refs.main && baseCandles.length) {
        const lastClose = baseCandles[baseCandles.length - 1].close;
        const y = refs.main.priceToCoordinate ? refs.main.priceToCoordinate(lastClose) : null;
        if (y != null) {
          const prev = prevCloseRef.current;
          if (prev != null && prev !== lastClose) {
            const dir: 'up' | 'down' = lastClose > prev ? 'up' : 'down';
            setPriceFlashDir(dir);
            if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
            flashTimeoutRef.current = setTimeout(() => setPriceFlashDir(null), 400);
          }
          prevCloseRef.current = lastClose;
          setPriceBadge({ y, price: lastClose });
        }
      }
    } catch {}

    // RSI / MACD sub-panes
    try {
      const rsiSeries = subChartsRef.current.rsiSeries;
      if (subChartsRef.current.rsi && rsiSeries && ind.has('rsi')) {
        const r = rsi(closes, p.rsiPeriod || 14);
        rsiSeries.line.setData(r.flatMap((v: any, i: number) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
        rsiSeries.ob.setData(times.map((t: number) => ({ time: t as any, value: 70 })));
        rsiSeries.os.setData(times.map((t: number) => ({ time: t as any, value: 30 })));
      }
      const macdSeries = subChartsRef.current.macdSeries;
      if (subChartsRef.current.macd && macdSeries && ind.has('macd')) {
        const m = macd(closes, p.macdFast || 12, p.macdSlow || 26, p.macdSig || 9);
        macdSeries.ml.setData(m.flatMap((pt, i) => (pt.macd != null ? [{ time: times[i] as any, value: pt.macd }] : [])));
        macdSeries.sl.setData(m.flatMap((pt, i) => (pt.signal != null ? [{ time: times[i] as any, value: pt.signal }] : [])));
        macdSeries.hist.setData(m.flatMap((pt, i) => (pt.hist != null ? [{ time: times[i] as any, value: pt.hist, color: pt.hist >= 0 ? tv2.green + '88' : tv2.red + '88' }] : [])));
      }
    } catch { /* sub-pane may be mid-teardown from a concurrent structural rebuild */ }
  }, [baseCandles, workspace.extraIndicators]);

  useEffect(() => {
    try {
      comparisonCandles.forEach(({ overlay, candles }) => {
        const series = seriesRefs.current[`compare:${overlay.id}`];
        if (!series || !overlay.visible) return;
        series.setData(comparisonSeriesData(candles, overlay.mode).map((point) => ({ time: point.time as any, value: point.value })));
      });
    } catch { /* chart may be rebuilding while comparison data settles */ }
  }, [comparisonCandles]);

  // Redraw profile + handles when relevant
  useEffect(() => { setTimeout(drawVolumeProfile, 30); }, [drawVolumeProfile, showVP, volumeProfile]);
  useEffect(() => { setTimeout(drawHandles, 10); }, [drawHandles, selectedDrawingId, drawings]);

  // Mouse wiring for drag/select
  const rectRef = useRef<DOMRect | null>(null);
  const boxStartRef = useRef<{x:number, y:number} | null>(null);
  const isMouseDownRef = useRef(false);
  const [selectBox, setSelectBox] = useState<{x:number,y:number,w:number,h:number} | null>(null);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!mainRef.current || !mainChartRef.current) return;
    const rect = mainRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    // The right price-scale strip is pointer-events:none (so wheel/right-click
    // reach the native chart underneath for price-axis zoom/menu), which means
    // mousedown/mousemove landing in that x-range are seen here too. Ignore a
    // mousedown that originates there so useKiteDrawings' hit-test (which
    // matches an hline purely by price, with no x/time constraint - see
    // findDrawingAt in useKiteDrawings.ts) never gets a chance to start a drag
    // from what the user intends as a price-axis interaction. Same x-range
    // check used in handleContextMenu below.
    if (x >= rect.width - (rightScaleWidth || 56)) return;
    rectRef.current = rect;
    const y = e.clientY - rect.top;
    const chartApi: any = mainChartRef.current;
    // @ts-ignore
    const realPrice = chartApi.priceScale ? chartApi.priceScale().coordinateToPrice?.(y) : undefined;
    drawingMouseDown(e, baseCandles, mainChartRef.current, rect);

    isMouseDownRef.current = true;
    if (drawMode === 'crosshair') {
      boxStartRef.current = {x, y};
      setSelectBox(null);
    }
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!rectRef.current) return;
    // Mirror the handleMouseDown exclusion: only skip when nothing is already
    // in progress, so a drag/box-select that legitimately started on the
    // chart and crosses into the price-scale strip mid-drag keeps working -
    // new interactions are blocked at the source in handleMouseDown above.
    if (!isMouseDownRef.current) {
      const rx = rectRef.current;
      if ((e.clientX - rx.left) >= rx.width - (rightScaleWidth || 56)) return;
    }
    drawingMouseMove(e, baseCandles, mainChartRef.current, rectRef.current);

    // Only show drag-select box on Shift+drag in crosshair (to not interfere with normal chart panning/clicking)
    if (isMouseDownRef.current && boxStartRef.current && drawMode === 'crosshair' && e.shiftKey) {
      const rx = rectRef.current;
      const cx = e.clientX - rx.left;
      const cy = e.clientY - rx.top;
      const sx = boxStartRef.current.x;
      const sy = boxStartRef.current.y;
      setSelectBox({
        x: Math.min(sx, cx),
        y: Math.min(sy, cy),
        w: Math.abs(cx - sx),
        h: Math.abs(cy - sy),
      });
    }
  };
  const handleMouseUp = () => {
    isMouseDownRef.current = false;
    if (boxStartRef.current && selectBox && drawMode === 'crosshair' && mainChartRef.current && (selectBox.w > 5 || selectBox.h > 5)) {
      // Only process as box select if significant drag (avoids interfering with normal clicks/pans)
      const chart: any = mainChartRef.current;
      const {x, y, w, h} = selectBox;
      try {
        const t1 = chart.timeScale().coordinateToTime ? chart.timeScale().coordinateToTime(x) : null;
        const t2 = chart.timeScale().coordinateToTime ? chart.timeScale().coordinateToTime(x + w) : null;
        const p1 = chart.priceScale().coordinateToPrice ? chart.priceScale().coordinateToPrice(y) : null;
        const p2 = chart.priceScale().coordinateToPrice ? chart.priceScale().coordinateToPrice(y + h) : null;
        if (t1 != null && t2 != null && p1 != null && p2 != null) {
          const minT = Math.min(t1 as number, t2 as number);
          const maxT = Math.max(t1 as number, t2 as number);
          const minP = Math.min(p1, p2);
          const maxP = Math.max(p1, p2);
          // pick last drawing with a point inside box
          for (let i = drawings.length - 1; i >= 0; i--) {
            const d = drawings[i];
            const pts = d.points || (d.price != null ? [{time: (d.time||0), price: d.price}] : []);
            if (pts.some((pt: any) => pt.time >= minT && pt.time <= maxT && pt.price >= minP && pt.price <= maxP)) {
              setSelectedDrawingId(d.id);
              break;
            }
          }
        }
      } catch {}
    }
    boxStartRef.current = null;
    setSelectBox(null);
    drawingMouseUp(() => { if (onDrawingsChange) onDrawingsChange(drawings); });
  };

  const handleMouseLeave = () => {
    isMouseDownRef.current = false;
    boxStartRef.current = null;
    setSelectBox(null);
    drawingMouseUp(() => { if (onDrawingsChange) onDrawingsChange(drawings); });
  };

  // Right-click on the chart area: opens the drawing-properties popover (TV
  // style) if a drawing was hit, otherwise opens the general chart-area
  // context menu (Add hline / Remove all / Reset view / Toggle log scale).
  // The right price-scale strip is pointer-events:none (so wheel-to-zoom the
  // price axis reaches the chart underneath), so right-clicks landing in that
  // strip are detected here by coordinate and delegated to
  // handlePriceScaleContextMenu (Auto/Log/Percentage) below, before any
  // drawing-hit-test / general chart menu logic runs.
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!mainRef.current || !mainChartRef.current) return;
    const rect = mainRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    if (x >= rect.width - (rightScaleWidth || 56)) {
      handlePriceScaleContextMenu(e);
      return;
    }
    const chart: any = mainChartRef.current;
    let price = 0;
    let time = 0;
    try {
      price = seriesRefs.current.main?.coordinateToPrice?.(y) || 0;
      const logical = chart.timeScale().coordinateToLogical?.(x) || 0;
      if (baseCandles.length) {
        const idx = Math.floor(logical + baseCandles.length / 2);
        time = baseCandles[Math.max(0, Math.min(baseCandles.length-1, idx))]?.time || 0;
      }
    } catch {}
    // Simple hit test for nearest drawing point
    let hit: any = null;
    if (drawings.length > 0) {
      const tolPrice = (baseCandles[baseCandles.length-1]?.close || 100) * 0.01;
      for (let i = drawings.length-1; i>=0; i--) {
        const d = drawings[i];
        if (d.type === 'hline' && Math.abs((d.price || 0) - price) < tolPrice) {
          hit = d; break;
        }
        if (d.points) {
          for (const p of d.points) {
            if (Math.abs(p.price - price) < tolPrice && Math.abs(p.time - time) < 300) {
              hit = d; break;
            }
          }
        }
      }
    }
    if (hit) {
      setChartContextMenu(null);
      setEditingDrawingId(hit.id);
      setDrawingPopoverPos({x: e.clientX, y: e.clientY});
      setDrawingEditProps({...hit});
    } else {
      setEditingDrawingId(null);
      setDrawingPopoverPos(null);
      setDrawingEditProps(null);
      setChartContextMenu({ x: e.clientX, y: e.clientY, price });
    }
  };

  // Text edit handler (double click or button)
  const startEditSelectedText = () => {
    if (!selectedDrawingId) return;
    const d = drawings.find(x => x.id === selectedDrawingId);
    if (d && d.type === 'text') {
      setEditingTextId(d.id);
      setEditTextValue(d.text || '');
    }
  };
  const commitEditText = () => {
    if (editingTextId != null) {
      updateDrawingText(editingTextId, editTextValue || 'Note');
      setEditingTextId(null);
      setEditTextValue('');
    }
  };

  // Right price-scale context menu (Auto/Log/Percentage) - right-click over the axis strip
  const handlePriceScaleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setPriceScaleMenu({ x: e.clientX, y: e.clientY });
  };
  const applyPriceScaleMode = (mode: PriceScaleMode) => {
    try { mainChartRef.current?.priceScale('right').applyOptions({ mode }); } catch {}
    // Keep in sync with the existing isLogScale prop where sensible (Percentage has no
    // backing prop, so it's left as a session-only choice until the chart next rebuilds).
    if (onIsLogScaleChange) {
      if (mode === PriceScaleMode.Logarithmic) onIsLogScaleChange(true);
      else if (mode === PriceScaleMode.Normal) onIsLogScaleChange(false);
    }
    setPriceScaleMenu(null);
  };

  // Wheel-driven vertical (price-axis) zoom, TradingView-style: lightweight-charts'
  // own wheel handler (attached natively inside the container passed to
  // createChart, i.e. a descendant of mainRef) always zooms TIME on any wheel
  // tick, even over the price-scale strip - there is no built-in option for
  // wheel-to-zoom-price. This is wired as a manually-attached, CAPTURE-phase,
  // NON-PASSIVE native 'wheel' listener on mainRef (see the useEffect below) -
  // NOT React's onWheelCapture prop - because React registers its own
  // synthetic wheel listeners as passive for scroll-perf reasons (confirmed
  // empirically: e.preventDefault() inside onWheelCapture is silently a
  // no-op there), which would defeat requirement #2 below. A plain native
  // listener with {capture:true, passive:false} runs before the library's own
  // listener (capture fires top-down from ancestor to descendant, and
  // mainRef is an ancestor of the library's internal canvases) and can
  // actually call preventDefault(). It only intercepts wheel ticks landing in
  // the same x-range used by handleMouseDown/handleContextMenu above (the
  // price-scale strip) - wheel events anywhere else on the chart body return
  // immediately and fall through to the library's default time-zoom, unchanged.
  //
  // Mechanism: IPriceScaleApi.setVisibleRange({from,to}) (public API) - this is
  // exactly what a price-axis drag uses internally (both flip autoScale off and
  // write an explicit price range), so it composes cleanly with the native
  // double-click-to-reset-price-scale behavior (handleScale.axisDoubleClickReset.price,
  // on by default and left untouched in this file's chart options) - double-click
  // resets autoScale back on and recomputes the range with zero extra code here;
  // the `autoScale` check below just re-seeds this handler's own clamp baseline
  // the next time the user wheels afterward.
  const handlePriceAxisWheel = (e: WheelEvent) => {
    if (!mainRef.current || !mainChartRef.current) return;
    const rect = mainRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    // Same x-range check used by handleMouseDown/handleContextMenu above.
    if (x < rect.width - (rightScaleWidth || 56)) return;

    const chart: any = mainChartRef.current;
    let priceScale: any;
    try { priceScale = chart.priceScale('right'); } catch { return; }
    if (!priceScale) return;

    let mode: PriceScaleMode = PriceScaleMode.Normal;
    try { mode = priceScale.options().mode; } catch {}
    // Log/Percentage price scales have non-linear semantics that a naive
    // coordinate-delta zoom would get wrong - leave the library's default
    // wheel behavior (time zoom) in place for those, exactly as before this
    // feature existed.
    if (mode !== PriceScaleMode.Normal) return;

    const series = seriesRefs.current.main || seriesRefs.current.candle;
    if (!series) return;

    // From here on we are fully replacing the library's default wheel
    // behavior for this event - never let it also see it (that would double
    // up with a time-zoom on top of our price-zoom).
    e.preventDefault();
    e.stopPropagation();

    try {
      const current = priceScale.getVisibleRange();
      if (!current || !isFinite(current.from) || !isFinite(current.to)) return;

      let autoScale = false;
      try { autoScale = !!priceScale.options().autoScale; } catch {}
      if (autoScale || !priceZoomBaseRef.current) {
        priceZoomBaseRef.current = { from: current.from, to: current.to };
      }
      const base = priceZoomBaseRef.current;
      const baseHeight = base.to - base.from;
      if (!isFinite(baseHeight) || baseHeight <= 0) return;

      const y = e.clientY - rect.top;
      let cursorPrice: number | null = null;
      try { cursorPrice = series.coordinateToPrice(y); } catch { cursorPrice = null; }
      if (cursorPrice == null || !isFinite(cursorPrice)) {
        cursorPrice = (current.from + current.to) / 2;
      }

      // ~10% per wheel notch (TradingView-ish feel). Negative deltaY (scroll
      // up) zooms IN (shrinks the range, taller candles); positive deltaY
      // (scroll down) zooms OUT (grows the range).
      const ZOOM_STEP = 0.1;
      const factor = e.deltaY < 0 ? (1 - ZOOM_STEP) : 1 / (1 - ZOOM_STEP);
      let newFrom = cursorPrice - (cursorPrice - current.from) * factor;
      let newTo = cursorPrice + (current.to - cursorPrice) * factor;

      // Clamp total zoom relative to the last auto-fit baseline so this can
      // never invert min/max, collapse to a degenerate zero-height range, or
      // be scrolled into some other unusable state.
      const MIN_MULT = 0.02; // up to ~50x zoomed in
      const MAX_MULT = 25;   // up to ~25x zoomed out
      const newHeight = newTo - newFrom;
      const minHeight = baseHeight * MIN_MULT;
      const maxHeight = baseHeight * MAX_MULT;
      if (newHeight < minHeight) {
        const mid = (newFrom + newTo) / 2;
        newFrom = mid - minHeight / 2;
        newTo = mid + minHeight / 2;
      } else if (newHeight > maxHeight) {
        const mid = (newFrom + newTo) / 2;
        newFrom = mid - maxHeight / 2;
        newTo = mid + maxHeight / 2;
      }
      if (!(newTo > newFrom)) return;

      priceScale.setVisibleRange({ from: newFrom, to: newTo });
    } catch {
      /* never let a wheel-zoom edge case break the chart */
    }
  };
  // Always-fresh ref so the native listener below (attached once) never
  // closes over a stale rightScaleWidth/mainChartRef snapshot.
  const handlePriceAxisWheelRef = useRef(handlePriceAxisWheel);
  handlePriceAxisWheelRef.current = handlePriceAxisWheel;

  // Attach the native, non-passive, capture-phase 'wheel' listener described
  // above, and always delegate to the latest handler via the ref (so the
  // listener body itself never needs to change). NOTE: mainRef.current is
  // NOT stable for the component's life - the <div ref={mainRef}> only
  // exists inside the `layoutMode === '1'` branch of the JSX (multi-chart
  // 2/4-up layouts render a different tree), so toggling layoutMode away
  // from '1' and back unmounts and remounts a brand-new DOM node. A one-shot
  // `useEffect(..., [])` would attach to the first node only and silently go
  // stale (listener never re-attached) after any such round-trip. Depending
  // on `layoutMode` here mirrors the main chart-creation effect above (which
  // already includes `layoutMode` in its deps for the same reason) and makes
  // this effect tear down/re-run whenever the node is swapped, so it always
  // (re)binds to whichever DOM node is currently mounted.
  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    const listener = (e: WheelEvent) => handlePriceAxisWheelRef.current(e);
    el.addEventListener('wheel', listener, { capture: true, passive: false });
    return () => el.removeEventListener('wheel', listener, { capture: true } as any);
  }, [layoutMode]);

  // Keyboard shortcuts - only active while hovering the chart wrapper, and never while
  // typing in an input/textarea/select anywhere in the app.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!isHoveringChartRef.current) return;
      const ae = document.activeElement;
      if (ae && ['INPUT', 'TEXTAREA', 'SELECT'].includes(ae.tagName)) return;

      // Undo/redo (Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl/Cmd+Y) - handled before
      // the generic ctrl/meta guard below, which otherwise ignores every
      // ctrl/cmd combo so it doesn't fight browser/OS shortcuts.
      if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault();
        if (e.shiftKey) redoDrawing(); else undoDrawing();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || e.key === 'Y')) {
        e.preventDefault();
        redoDrawing();
        return;
      }
      if (e.ctrlKey || e.metaKey) return;
      const chart = mainChartRef.current;
      if (!chart) return;

      const key = e.key.toLowerCase();
      if (replayIndex != null && e.key === ' ') {
        e.preventDefault();
        setReplayPlaying((playing) => !playing);
        return;
      }
      if (key === 'i') {
        e.preventDefault();
        setShowStudies(true);
        return;
      }
      if (key === 's') {
        e.preventDefault();
        setShowSymbolSearch(true);
        return;
      }
      if (key === 'c') {
        e.preventDefault();
        setShowCompare(true);
        return;
      }
      if (key === 'p') {
        e.preventDefault();
        setShowTemplates(true);
        return;
      }
      if (key === 'g') {
        e.preventDefault();
        setShowGoToDate(true);
        return;
      }
      if (key === 'r') {
        e.preventDefault();
        setShowGoToDate(true);
        return;
      }
      if (key === 'a') {
        e.preventDefault();
        const candles = baseCandlesRef.current;
        const price = candles[candles.length - 1]?.close;
        const mainSeries = seriesRefs.current.main;
        const y = price && mainSeries?.priceToCoordinate ? mainSeries.priceToCoordinate(price) : null;
        if (price && y != null) setAlertDraft({ price, y });
        return;
      }
      if (key === 'f') {
        e.preventDefault();
        setIsFullscreen((current) => !current);
        return;
      }
      if (key === 'l') {
        e.preventDefault();
        onIsLogScaleChange?.(!isLogScale);
        return;
      }
      if (key === 'v') {
        e.preventDefault();
        onShowVPChange?.(!showVP);
        return;
      }
      if (key === 'x') {
        e.preventDefault();
        setDrawMode('crosshair');
        return;
      }
      if (key === 'h') {
        e.preventDefault();
        setDrawMode('hline');
        return;
      }
      if (key === 't') {
        e.preventDefault();
        setDrawMode('trend');
        return;
      }
      if (key === '1' || key === '2' || key === '4') {
        e.preventDefault();
        setLayoutMode(key as '1' | '2' | '4');
        return;
      }

      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const ts = chart.timeScale();
        const range = ts.getVisibleLogicalRange();
        if (range) {
          const delta = e.key === 'ArrowLeft' ? -3 : 3;
          ts.setVisibleLogicalRange({ from: range.from + delta, to: range.to + delta });
        }
        e.preventDefault();
      } else if (e.key === '+' || e.key === '=' || e.key === '-') {
        const ts = chart.timeScale();
        const cur = ts.options().barSpacing || 6;
        const next = e.key === '-' ? cur / 1.2 : cur * 1.2;
        ts.applyOptions({ barSpacing: Math.max(0.5, Math.min(200, next)) });
        e.preventDefault();
      } else if (e.key === 'Escape') {
        if (chartContextMenu || priceScaleMenu || (editingDrawingId != null && drawingPopoverPos)) {
          setChartContextMenu(null);
          setPriceScaleMenu(null);
          setEditingDrawingId(null);
          setDrawingPopoverPos(null);
          setDrawingEditProps(null);
        } else if (drawingPointsRef.current.length > 0) {
          setDrawingPoints([]);
          setDrawMode('crosshair');
        } else if (selectedDrawingId != null) {
          setSelectedDrawingId(null);
        }
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedDrawingId != null) {
          e.preventDefault();
          const updated = drawings.filter(d => d.id !== selectedDrawingId);
          recordDrawingsChange(updated);
          setSelectedDrawingId(null);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [drawings, selectedDrawingId, onDrawingsChange, recordDrawingsChange, undoDrawing, redoDrawing, setDrawingPoints, setDrawMode, setSelectedDrawingId, chartContextMenu, priceScaleMenu, editingDrawingId, drawingPopoverPos, replayIndex, isLogScale, onIsLogScaleChange, showVP, onShowVPChange]);

  // Toolbar helpers
  const toggleLog = () => {
    // parent usually owns isLogScale state; here we signal via zoom or no-op (parent re-renders with prop)
    // for standalone, we could lift but keep controlled from outside for InstrumentPane
  };

  const downloadChartImage = () => {
    try {
      const canvas = (mainChartRef.current as any)?.takeScreenshot?.();
      if (!canvas) return;
      canvas.toBlob((blob: Blob | null) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${symbol.replace(/[^a-z0-9]+/gi, '-')}-${tf}.png`;
        link.click();
        URL.revokeObjectURL(url);
      }, 'image/png');
    } catch (error) {
      console.error('Failed to export chart image:', error);
    }
  };

  const beginAlertDraft = (price?: number) => {
    const nextPrice = price || baseCandles[baseCandles.length - 1]?.close;
    const mainSeries = seriesRefs.current.main;
    if (!nextPrice || !mainSeries?.priceToCoordinate) return;
    const y = mainSeries.priceToCoordinate(nextPrice);
    if (y == null) return;
    setAlertDraft({ price: nextPrice, y });
    setChartContextMenu(null);
  };

  const startAlertDrag = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const move = (moveEvent: MouseEvent) => {
      if (!mainRef.current || !seriesRefs.current.main?.coordinateToPrice) return;
      const rect = mainRef.current.getBoundingClientRect();
      const y = Math.max(0, Math.min(rect.height, moveEvent.clientY - rect.top));
      const price = seriesRefs.current.main.coordinateToPrice(y);
      if (price != null) setAlertDraft({ price, y });
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      setAlertDraft((current) => {
        if (current) setAlertDialog({ price: current.price });
        return current;
      });
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up, { once: true });
  };

  const submitAlert = () => {
    if (!alertDialog) return;
    createAlert.mutate({
      underlying: symbol,
      condition: alertCondition,
      threshold: Number(alertDialog.price.toFixed(4)),
      notes: alertNotes || `Created from ${tf} chart`,
    }, {
      onSuccess: () => {
        setAlertDialog(null);
        setAlertDraft(null);
        setAlertNotes('');
      },
    });
  };

  const jumpToDate = () => {
    const timestamp = Date.parse(goToDateValue);
    if (!Number.isFinite(timestamp) || !fullBaseCandles.length) return;
    const index = nearestCandleIndex(fullBaseCandles, Math.floor(timestamp / 1000));
    if (index < 0) return;
    const fromIndex = Math.max(0, index - 50);
    const toIndex = Math.min(fullBaseCandles.length - 1, index + 50);
    try {
      mainChartRef.current?.timeScale().setVisibleRange({
        from: fullBaseCandles[fromIndex].time as any,
        to: fullBaseCandles[toIndex].time as any,
      });
      setShowGoToDate(false);
    } catch {}
  };

  const startReplay = () => {
    const dateTimestamp = Date.parse(goToDateValue);
    const requested = Number.isFinite(dateTimestamp)
      ? nearestCandleIndex(fullBaseCandles, Math.floor(dateTimestamp / 1000))
      : Math.max(20, fullBaseCandles.length - 100);
    setReplayIndex(Math.max(0, requested));
    setReplayPlaying(false);
    setShowGoToDate(false);
  };

  const workspaceSnapshot = () => ({
    tf,
    chartType,
    layoutMode,
    isHA,
    isLogScale,
    showVP,
    activeIndicators: Array.from(activeIndicators),
    params: { ...params },
    workspace: structuredClone(workspace),
  });

  const saveCurrentTemplate = () => {
    const name = templateName.trim();
    if (!name) return;
    const template = createChartTemplate(name, workspaceSnapshot());
    const next = upsertTemplate(templates, template);
    setTemplates(next);
    saveTemplates(next);
    setTemplateName('');
    setTemplateError('');
  };

  const applyTemplate = (template: ChartTemplate) => {
    const snapshot = template.snapshot;
    setChartType(snapshot.chartType);
    setLayoutMode(snapshot.layoutMode);
    setWorkspace(snapshot.workspace);
    onTfChange?.(snapshot.tf);
    onIsHAChange?.(snapshot.isHA);
    onIsLogScaleChange?.(snapshot.isLogScale);
    onShowVPChange?.(snapshot.showVP);
    onParamsChange?.(snapshot.params);
    onActiveIndicatorsChange?.(snapshot.activeIndicators);
    setShowTemplates(false);
  };

  const deleteTemplate = (id: string) => {
    const next = templates.filter((template) => template.id !== id);
    setTemplates(next);
    saveTemplates(next);
  };

  const exportTemplateJson = () => {
    setTemplateImportText(exportTemplatesToJson(templates));
    setTemplateError('');
  };

  const importTemplateJson = () => {
    try {
      const next = mergeImportedTemplates(templateImportText, templates);
      setTemplates(next);
      saveTemplates(next);
      setTemplateImportText('');
      setTemplateError('');
    } catch (error: any) {
      setTemplateError(error?.message || 'Invalid template JSON');
    }
  };

  const resetCurrentWorkspace = () => {
    setWorkspace({
      styles: {},
      extraIndicators: [],
      compareSymbol: null,
      comparisons: [],
      appearance: { ...DEFAULT_WORKSPACE.appearance },
    });
    setReplayPlaying(false);
    setReplayIndex(null);
    setAlertDraft(null);
    setTemplateError('');
  };

  const addExtraIndicator = (kind: ExtraIndicatorKind) => {
    setWorkspace((current) => ({
      ...current,
      extraIndicators: current.extraIndicators.length >= MAX_EXTRA_INDICATORS
        ? current.extraIndicators
        : [...current.extraIndicators, createExtraIndicator(kind)],
    }));
  };

  const setComparisons = (comparisons: ComparisonOverlay[]) => ({
    comparisons,
    compareSymbol: comparisons[0]?.symbol ?? null,
  });

  const addComparison = (symbolValue: string) => {
    const value = symbolValue.trim().toUpperCase();
    if (!value) return;
    setWorkspace((current) => {
      if (current.comparisons.some((item) => item.symbol === value)) return current;
      const comparisons = [
        ...current.comparisons,
        createComparisonOverlay(value, Date.now(), current.comparisons.length),
      ].slice(0, MAX_COMPARISONS);
      return { ...current, ...setComparisons(comparisons) };
    });
    setCompareSearch('');
  };

  const updateComparison = (id: string, patch: Partial<ComparisonOverlay>) => {
    setWorkspace((current) => {
      const comparisons = current.comparisons.map((item) => item.id === id ? { ...item, ...patch } : item);
      return { ...current, ...setComparisons(comparisons) };
    });
  };

  const removeComparison = (id: string) => {
    setWorkspace((current) => {
      const comparisons = current.comparisons.filter((item) => item.id !== id);
      return { ...current, ...setComparisons(comparisons) };
    });
  };

  // Vertical side toolbar style (TV drawing toolbar on left) - closer to TV
  const vbarStyle: React.CSSProperties = {
    width: 28,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 1,
    padding: '4px 1px',
    background: tv.surface,
    borderRight: `1px solid ${tv.border}`,
    flexShrink: 0,
    fontSize: 11,
  };
  const vBtn = (mode: string, active: boolean, accent: string, title: string, children: React.ReactNode) => (
    <button
      onClick={() => setDrawMode(mode as any)}
      title={title}
      className="tv-ctrl"
      style={{
        width: 22, height: 20, padding: 0, margin: 0,
        border: `1px solid ${active ? accent : tv.border}`,
        background: active ? accent + '33' : 'transparent',
        color: active ? accent : tv.dim,
        borderRadius: 2,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        lineHeight: '18px',
        fontSize: 11,
      }}
    >
      {children}
    </button>
  );

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: isFullscreen ? '100vh' : (height || '100%'), 
      background: tv.bg, 
      position: isFullscreen ? 'fixed' : 'relative', 
      top: isFullscreen ? 0 : 'auto',
      left: isFullscreen ? 0 : 'auto',
      right: isFullscreen ? 0 : 'auto',
      bottom: isFullscreen ? 0 : 'auto',
      zIndex: isFullscreen ? 9999 : 'auto',
      fontFamily: tv.fontFamily,
      color: tv.text
    }}>
      <style>{`
        .tv-ctrl { transition: filter 0.12s cubic-bezier(0.4,0,0.2,1), transform 0.08s ease, box-shadow 0.12s ease; cursor: pointer; }
        .tv-ctrl:hover { filter: brightness(1.35) saturate(1.1); }
        .tv-ctrl:active { transform: scale(0.93); filter: brightness(0.85); }
        .tv-ctrl:focus-visible { outline: none; box-shadow: 0 0 0 2px rgba(88,166,255,0.5); }
        @keyframes tvFadeSlideIn { from { opacity: 0; transform: translateY(-4px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
        @keyframes tvModalIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
        @keyframes tvBackdropIn { from { opacity: 0; } to { opacity: 1; } }
        .tv-menu-anim { animation: tvFadeSlideIn 0.15s cubic-bezier(0.4,0,0.2,1) both; transform-origin: top left; }
        .tv-modal-anim { animation: tvModalIn 0.16s cubic-bezier(0.4,0,0.2,1) both; }
        .tv-backdrop-anim { animation: tvBackdropIn 0.16s ease both; }
        .tv-tab { position: relative; transition: color 0.15s ease; }
        @keyframes tvPriceFlash { 0% { filter: brightness(2); } 100% { filter: brightness(1); } }
        .tv-flash-up, .tv-flash-down { animation: tvPriceFlash 0.4s ease-out; }
      `}</style>
      {/* TradingView-style top header bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 8px',
        borderBottom: `1px solid ${tv.border}`,
        background: tv.surface,
        fontSize: 12,
        flexWrap: 'wrap',
        minHeight: 32,
      }}>
        {/* Symbol search - exact TV style */}
        <div style={{ position: 'relative', marginRight: 8 }}>
          <div
            onClick={() => setShowSymbolSearch(!showSymbolSearch)}
            className="tv-ctrl"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '2px 6px', border: `1px solid ${tv.border}`, borderRadius: 3,
              background: tv.surface, cursor: 'pointer', minWidth: 140
            }}
          >
            <span style={{ fontWeight: 600, fontSize: 13, color: tv.text }}><InstrumentLabel symbol={symbol} /></span>
            {baseCandles.length > 0 && (
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: tv.text }}>
                {baseCandles[baseCandles.length-1].close.toFixed(2)}
              </span>
            )}
            <span style={{ fontSize: 10, color: tv.dim }}>▼</span>
          </div>
          {showSymbolSearch && (
            <>
            <div onClick={() => setShowSymbolSearch(false)} style={{ position: 'fixed', inset: 0, zIndex: 99 }} />
            <div className="tv-menu-anim" style={{
              position: 'absolute', top: '100%', left: 0, zIndex: 100,
              background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 4,
              width: 220, maxHeight: 220, overflow: 'auto', boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
            }}>
              <input 
                type="text" 
                placeholder="Search symbol..." 
                value={symbolSearch} 
                onChange={(e) => setSymbolSearch(e.target.value)}
                style={{ width: '100%', padding: 6, border: 'none', borderBottom: `1px solid ${tv.border}`, background: tv.bg, color: tv.text, fontSize: 11 }}
                autoFocus
              />
              {filteredSymbols.length > 0 ? filteredSymbols.map(s => (
                <div 
                  key={s} 
                  onClick={() => {
                    if (onSymbolChange) onSymbolChange(s);
                    setSymbolSearch('');
                    setShowSymbolSearch(false);
                  }}
                  style={{ padding: '4px 8px', cursor: 'pointer', fontSize: 11, borderBottom: `1px solid ${tv.border}` }}
                >
                  {s}
                </div>
              )) : <div style={{ padding: 6, fontSize: 10, color: tv.dim }}>No matches</div>}
            </div>
            </>
          )}
        </div>

        {/* TV-style interval bar + dropdown for more */}
        <div style={{ display: 'flex', gap: 1, marginRight: 8, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2, padding: 1, position: 'relative' }}>
          {PRIMARY_TFS.map((t) => (
            <button key={t} className="tv-ctrl" onClick={() => {
              if (onTfChange) onTfChange(t);
            }} style={{
              background: tf === t ? tv.blue : 'transparent',
              color: tf === t ? '#fff' : tv.dim,
              border: 'none',
              padding: '1px 5px',
              fontSize: 10,
              cursor: 'pointer',
              borderRadius: 1,
              minWidth: 24,
            }}>{t}</button>
          ))}
          <button
            onClick={() => setShowTfDropdown(!showTfDropdown)}
            className="tv-ctrl"
            title="More timeframes"
            style={{ padding: '1px 4px', fontSize: 9, color: tv.dim, background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          ><IconMore /></button>
          {showTfDropdown && (
            <>
            <div onClick={() => setShowTfDropdown(false)} style={{ position: 'fixed', inset: 0, zIndex: 99 }} />
            <div className="tv-menu-anim" style={{ position: 'absolute', top: '100%', left: 0, zIndex: 100, background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 3, padding: 4, minWidth: 120, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
              {ALL_TFS.map(t => (
                <div key={t} onClick={() => { if (onTfChange) onTfChange(t); setShowTfDropdown(false); }} style={{ padding: '3px 6px', cursor: 'pointer', fontSize: 10 }}>{t}</div>
              ))}
            </div>
            </>
          )}
        </div>

        {/* Chart type (TV style) */}
        <select
          value={chartType}
          onChange={(e) => setChartType(e.target.value as any)}
          className="tv-ctrl"
          style={{ fontSize: 10, background: tv.surface, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 2, padding: '1px 4px' }}
        >
          <option value="candles">Candles</option>
          <option value="bars">Bars</option>
          <option value="line">Line</option>
          <option value="area">Area</option>
        </select>
        <button className="tv-ctrl" onClick={() => { const next = !isHA; if (onIsHAChange) onIsHAChange(next); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${isHA ? tv.green : tv.border}`, background: isHA ? tv.green+'22' : 'transparent', color: isHA ? tv.green : tv.dim, borderRadius: 2 }}>HA</button>

        {/* Multi-chart layout switcher (TV 1/2/4/8) */}
        <div style={{ display: 'flex', gap: 2, marginLeft: 4, border: `1px solid ${tv.border}`, borderRadius: 2, padding: 1 }}>
          {(['1','2','4'] as const).map(m => (
            <button key={m} className="tv-ctrl" onClick={() => setLayoutMode(m)} style={{
              fontSize: 8, padding: '1px 3px', background: layoutMode === m ? tv.blue : 'transparent',
              color: layoutMode === m ? '#fff' : tv.dim, border: 'none', cursor: 'pointer'
            }}>{m}</button>
          ))}
        </div>

        {/* Main chart actions */}
        {/* Indicators - TV style button opening real dialog */}
        <button className="tv-ctrl" onClick={() => setShowStudies(!showStudies)} style={{ fontSize: 10, padding: '1px 6px', border: `1px solid ${tv.border}`, background: showStudies ? tv.blue + '22' : 'transparent', color: showStudies ? tv.blue : tv.dim, borderRadius: 2 }}>fx Indicators</button>
        <button className="tv-ctrl" onClick={() => { /* drawings in left */ }} style={{ fontSize: 10, padding: '1px 6px', border: `1px solid ${tv.border}`, background: 'transparent', color: tv.dim, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 4 }}><IconPencil /> Draw</button>
        <button className="tv-ctrl" onClick={() => setShowCompare(true)} title="Compare another symbol" style={toolBtnStyle(workspace.comparisons.length > 0, tv, tv.blue)}>
          Compare{workspace.comparisons.length ? ` (${workspace.comparisons.length})` : ''}
        </button>
        <button className="tv-ctrl" onClick={() => beginAlertDraft()} title="Create a draggable price alert" style={toolBtnStyle(!!alertDraft, tv, tv.orange)}>Alert</button>
        <button className="tv-ctrl" onClick={() => setShowTemplates(true)} title="Save or apply chart template" style={toolBtnStyle(false, tv, tv.blue)}>Templates</button>
        <button className="tv-ctrl" onClick={() => setShowGoToDate(true)} title="Go to date or start bar replay" style={toolBtnStyle(replayIndex != null, tv, tv.purple)}>Replay</button>

        {replayIndex != null && (
          <div style={{ display: 'flex', gap: 3, alignItems: 'center', padding: 1, border: `1px solid ${tv.border}`, borderRadius: 2 }}>
            <button className="tv-ctrl" onClick={() => setReplayIndex((index) => stepReplayIndex(index, fullBaseCandles.length - 1, -1))} title="Previous bar" style={toolBtnStyle(false, tv, tv.blue)}>Back</button>
            <button className="tv-ctrl" onClick={() => setReplayPlaying((playing) => !playing)} title={replayPlaying ? 'Pause replay' : 'Play replay'} style={toolBtnStyle(replayPlaying, tv, tv.green)}>{replayPlaying ? 'Pause' : 'Play'}</button>
            <button className="tv-ctrl" onClick={() => setReplayIndex((index) => stepReplayIndex(index, fullBaseCandles.length - 1, 1))} title="Next bar" style={toolBtnStyle(false, tv, tv.blue)}>Next</button>
            <input
              aria-label="Replay progress"
              type="range"
              min={0}
              max={Math.max(0, fullBaseCandles.length - 1)}
              value={replayIndex}
              onChange={(event) => { setReplayPlaying(false); setReplayIndex(Number(event.target.value)); }}
              style={{ width: 92, accentColor: tv.purple }}
            />
            <select
              aria-label="Replay speed"
              value={replaySpeed}
              onChange={(event) => setReplaySpeed(Number(event.target.value))}
              style={{ height: 22, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, fontSize: 10 }}
            >
              {REPLAY_SPEEDS.map((speed) => <option key={speed} value={speed}>{speed}x</option>)}
            </select>
            <button className="tv-ctrl" onClick={() => { setReplayPlaying(false); setReplayIndex(null); }} title="Exit replay" style={toolBtnStyle(false, tv, tv.red)}>Live</button>
          </div>
        )}

        <span style={{ color: tv.dim, margin: '0 4px' }}>|</span>

        <button className="tv-ctrl" onClick={() => { if (onIsLogScaleChange) onIsLogScaleChange(!isLogScale); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${isLogScale ? tv.blue : tv.border}`, background: isLogScale ? tv.blue+'22' : 'transparent', color: isLogScale ? tv.blue : tv.dim }}>Log</button>
        <button className="tv-ctrl" onClick={() => onShowVPChange?.(!showVP)} style={toolBtnStyle(showVP, tv, tv.amber)}>VP</button>
        <button className="tv-ctrl" onClick={downloadChartImage} title="Download chart image" style={toolBtnStyle(false, tv, tv.blue)}>PNG</button>
        <button className="tv-ctrl" onClick={() => setIsFullscreen(!isFullscreen)} title="Fullscreen" style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${tv.border}`, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><IconFullscreen /></button>

        <span style={{ flex: 1 }} />

        <span style={{ fontSize: 9, color: tv.dim }}>{baseCandles.length} bars</span>

        <button className="tv-ctrl" onClick={() => { clearDrawings(); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${tv.border}`, background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Clear drawings"><IconClose /></button>
      </div>

      {layoutMode === '1' ? (
      <>
      {/* Main area: side vertical drawing toolbar + chart */}
      <div style={{ display: 'flex', flex: 1, minHeight: 180, overflow: 'hidden' }} onDoubleClick={startEditSelectedText}>
        {/* Side vertical toolbar (TV style) with icons */}
        <div style={vbarStyle}>
          {vBtn('crosshair', drawMode === 'crosshair', tv.blue, 'Crosshair / Select', <IconCrosshair />)}
          {vBtn('hline', drawMode === 'hline', tv.amber, 'Horizontal Line', <IconHLine />)}
          {vBtn('trend', drawMode === 'trend', tv.green, 'Trend Line', <IconTrendline />)}
          {vBtn('ray', drawMode === 'ray', tv.cyan, 'Ray', <IconRay />)}
          <div style={{ height: 3 }} />
          {vBtn('fib', drawMode === 'fib', tv.purple, 'Fib Retracement', <IconFib />)}
          {vBtn('fibext', drawMode === 'fibext', tv.purple, 'Fib Extension', <IconFibExt />)}
          {vBtn('fibfan', drawMode === 'fibfan', tv.purple, 'Fib Fan', <IconFibFan />)}
          <div style={{ height: 3 }} />
          {vBtn('rect', drawMode === 'rect', tv.red, 'Rectangle', <IconRect />)}
          {vBtn('pitchfork', drawMode === 'pitchfork', '#ff9800', "Andrew's Pitchfork", <IconPitchfork />)}
          {vBtn('text', drawMode === 'text', tv.text, 'Text Annotation', <IconText />)}
        </div>

        {/* Chart container + overlays */}
        <div
          style={{ flex: 1, position: 'relative', background: tv.bg }}
          onMouseEnter={() => { isHoveringChartRef.current = true; }}
          onMouseLeave={() => { isHoveringChartRef.current = false; }}
          onMouseMove={(e) => {
            // A full-viewport transparent backdrop (price-scale/context menus)
            // is a DOM descendant of this wrapper, so moving the mouse anywhere
            // on screen while one is open never fires onMouseLeave (the pointer
            // never leaves this subtree) - leaving keyboard shortcuts wrongly
            // armed elsewhere on the page. Recompute against real cursor
            // position vs this element's own box on every move as a correction.
            // Exception: while a menu/popover owned by this chart is open, its
            // content can render past this wrapper's own right/bottom edge
            // (e.g. the price-scale menu, anchored to this box, clamped only
            // to the viewport) - don't let the box check flip hovering off
            // while the cursor is over that overflow, or Escape can't close it.
            if (priceScaleMenu || chartContextMenu || (editingDrawingId != null && drawingPopoverPos)) {
              isHoveringChartRef.current = true;
              return;
            }
            const rect = e.currentTarget.getBoundingClientRect();
            isHoveringChartRef.current = (
              e.clientX >= rect.left && e.clientX <= rect.right &&
              e.clientY >= rect.top && e.clientY <= rect.bottom
            );
          }}
        >
          <div
            ref={mainRef}
            style={{ position: 'absolute', inset: 0, cursor: isDragging ? 'grabbing' : 'crosshair' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
            onContextMenu={handleContextMenu}
          />
          {/* Drag select box (rubber band) */}
          {selectBox && (
            <div style={{
              position: 'absolute',
              left: selectBox.x,
              top: selectBox.y,
              width: selectBox.w,
              height: selectBox.h,
              border: '1px dashed #f06428',
              background: 'rgba(240,100,40,0.08)',
              pointerEvents: 'none',
              zIndex: 4,
            }} />
          )}
          {/* VP full histo canvas (right aligned) */}
          {showVP && (
            <canvas ref={profileRef} style={{ position: 'absolute', right: 2, top: 2, bottom: 2, pointerEvents: 'none', opacity: 0.95, zIndex: 2 }} />
          )}
          {/* Drag handles / selection overlay (real coord based) */}
          <canvas ref={handlesRef} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3 }} />

          {/* Marks the right price-scale region for visual/debug reference only.
              pointerEvents:'none' so wheel/right-click pass through to the chart's
              own wrapper underneath (native price-axis wheel-zoom) - the
              right-click-for-scale-menu is now detected by coordinate in
              handleContextMenu on mainRef and delegated to
              handlePriceScaleContextMenu. */}
          <div
            style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: rightScaleWidth || 56, zIndex: 5, pointerEvents: 'none' }}
          />
          {priceScaleMenu && (
            <>
              <div onClick={() => setPriceScaleMenu(null)} style={{ position: 'fixed', inset: 0, zIndex: 199 }} />
              <div className="tv-menu-anim" style={{
                position: 'fixed',
                left: Math.max(4, Math.min(priceScaleMenu.x, window.innerWidth - 148)),
                top: Math.max(4, Math.min(priceScaleMenu.y, window.innerHeight - 108)),
                zIndex: 200,
                background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 4,
                minWidth: 140, boxShadow: '0 4px 12px rgba(0,0,0,0.3)', fontSize: 11, overflow: 'hidden',
              }}>
                {[
                  { label: 'Auto (Normal)', mode: PriceScaleMode.Normal },
                  { label: 'Logarithmic', mode: PriceScaleMode.Logarithmic },
                  { label: 'Percentage', mode: PriceScaleMode.Percentage },
                ].map(opt => (
                  <div
                    key={opt.label}
                    className="tv-ctrl"
                    onClick={() => applyPriceScaleMode(opt.mode)}
                    style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}
                  >
                    {opt.label}
                  </div>
                ))}
              </div>
            </>
          )}

          {/* General chart-area right-click menu (distinct from priceScaleMenu above -
              fires from handleContextMenu on the mainRef div when no drawing was hit) */}
          {chartContextMenu && (
            <>
              <div onClick={() => setChartContextMenu(null)} style={{ position: 'fixed', inset: 0, zIndex: 199 }} />
              <div className="tv-menu-anim" style={{
                position: 'fixed',
                left: Math.max(4, Math.min(chartContextMenu.x, window.innerWidth - 228)),
                top: Math.max(4, Math.min(chartContextMenu.y, window.innerHeight - 388)),
                zIndex: 200,
                background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 4,
                minWidth: 220, boxShadow: '0 4px 12px rgba(0,0,0,0.3)', fontSize: 11, overflow: 'hidden',
              }}>
                <div
                  className="tv-ctrl"
                  onClick={() => {
                    const newDrawing: Drawing = { id: Date.now(), type: 'hline', price: chartContextMenu.price, color: tv.amber };
                    recordDrawingsChange([...drawings, newDrawing]);
                    setChartContextMenu(null);
                  }}
                  style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}
                >Add horizontal line here</div>
                <div className="tv-ctrl" onClick={() => { setDrawMode('trend'); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Draw trend line</div>
                <div className="tv-ctrl" onClick={() => { setDrawMode('fib'); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Draw Fibonacci retracement</div>
                <div className="tv-ctrl" onClick={() => { setShowStudies(true); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text, borderTop: `1px solid ${tv.border}` }}>Add indicator...</div>
                <div className="tv-ctrl" onClick={() => beginAlertDraft(chartContextMenu.price)} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Create alert at {chartContextMenu.price.toFixed(2)}</div>
                <div className="tv-ctrl" onClick={() => { setShowCompare(true); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Compare symbol...</div>
                <div className="tv-ctrl" onClick={() => { setShowGoToDate(true); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Go to date...</div>
                <div className="tv-ctrl" onClick={() => { setShowTemplates(true); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Chart templates...</div>
                <div className="tv-ctrl" onClick={() => { setShowChartSettings(true); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Chart settings...</div>
                <div className="tv-ctrl" onClick={() => { downloadChartImage(); setChartContextMenu(null); }} style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text }}>Save chart image</div>
                <div
                  className="tv-ctrl"
                  onClick={() => { clearDrawings(); setChartContextMenu(null); }}
                  style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text, borderTop: `1px solid ${tv.border}` }}
                >Remove all drawings</div>
                <div
                  className="tv-ctrl"
                  onClick={() => { try { mainChartRef.current?.timeScale().fitContent(); } catch {} setChartContextMenu(null); }}
                  style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text, borderTop: `1px solid ${tv.border}` }}
                >Reset view</div>
                <div
                  className="tv-ctrl"
                  onClick={() => { if (onIsLogScaleChange) onIsLogScaleChange(!isLogScale); setChartContextMenu(null); }}
                  style={{ padding: '6px 10px', cursor: 'pointer', color: tv.text, borderTop: `1px solid ${tv.border}` }}
                >Toggle log scale</div>
              </div>
            </>
          )}

          {alertDraft && (
            <div
              onMouseDown={startAlertDrag}
              title="Drag alert price, then release to create"
              style={{
                position: 'absolute', left: 0, right: rightScaleWidth || 56, top: alertDraft.y - 5,
                height: 10, zIndex: 8, cursor: 'ns-resize', pointerEvents: 'auto',
              }}
            >
              <div style={{ position: 'absolute', left: 0, right: 0, top: 4, borderTop: `1px dashed ${tv.orange}` }} />
              <span style={{ position: 'absolute', right: 4, top: -8, padding: '1px 4px', borderRadius: 2, background: tv.orange, color: '#fff', fontSize: 9 }}>
                Alert {alertDraft.price.toFixed(2)}
              </span>
            </div>
          )}

          {/* Last-price flash badge: pill at the current close's pixel Y, flashes on change */}
          {priceBadge && (
            <div
              className={priceFlashDir === 'up' ? 'tv-flash-up' : priceFlashDir === 'down' ? 'tv-flash-down' : undefined}
              style={{
                position: 'absolute',
                right: 2,
                top: priceBadge.y - 8,
                zIndex: 6,
                pointerEvents: 'none',
                background: priceFlashDir === 'up' ? tv.green + '33' : priceFlashDir === 'down' ? tv.red + '33' : tv.surface,
                color: tv.text,
                border: `1px solid ${priceFlashDir === 'up' ? tv.green : priceFlashDir === 'down' ? tv.red : tv.border}`,
                borderRadius: 3,
                padding: '1px 5px',
                fontSize: 10,
                fontFamily: 'monospace',
                lineHeight: '14px',
                whiteSpace: 'nowrap',
              }}
            >
              {priceBadge.price.toFixed(2)}
            </div>
          )}

          {/* (Indicators now in top dropdown - TV style) */}

          {/* Inline text editor for selected text annotation */}
          {editingTextId != null && (
            <div style={{ position: 'absolute', zIndex: 10, left: 60, top: 60, background: tv.surface, border: `1px solid ${tv.border}`, padding: 4, borderRadius: 3 }}>
              <input
                value={editTextValue}
                onChange={e => setEditTextValue(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') commitEditText(); if (e.key === 'Escape') setEditingTextId(null); }}
                style={{ fontSize: 11, background: 'transparent', color: tv.text, border: 'none', outline: 'none', width: 160 }}
                autoFocus
              />
              <button onClick={commitEditText} style={{ fontSize: 9, marginLeft: 4 }}>ok</button>
            </div>
          )}

          {/* Drawing properties popover (right-click, TV style) */}
          {drawingPopoverPos && editingDrawingId != null && drawingEditProps && (
            <div
              style={{
                position: 'fixed',
                left: Math.max(4, Math.min(drawingPopoverPos.x + 10, window.innerWidth - 190)),
                top: Math.max(4, Math.min(drawingPopoverPos.y + 10, window.innerHeight - 160)),
                zIndex: 20, background: tv.surface, border: `1px solid ${tv.border}`, padding: 8,
                borderRadius: 4, fontSize: 11, boxShadow: '0 4px 12px rgba(0,0,0,0.3)', minWidth: 180
              }}
              onClick={e => e.stopPropagation()}
            >
              <div style={{ marginBottom: 6, fontWeight: 600 }}>Drawing Properties</div>
              <label style={{ display: 'block', fontSize: 9 }}>Color
                <input type="text" value={drawingEditProps.color || '#fff'} onChange={e => setDrawingEditProps({...drawingEditProps, color: e.target.value})} style={{ width: '100%', background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }} />
              </label>
              <label style={{ display: 'block', fontSize: 9, marginTop: 4 }}>Width
                <input type="number" value={drawingEditProps.lineWidth || 1} onChange={e => setDrawingEditProps({...drawingEditProps, lineWidth: parseFloat(e.target.value)})} style={{ width: '100%', background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }} />
              </label>
              <div style={{ marginTop: 4 }}>
                <button onClick={() => {
                  const updated = drawings.map(d => d.id === editingDrawingId ? {...d, ...drawingEditProps} : d);
                  recordDrawingsChange(updated);
                  setEditingDrawingId(null); setDrawingPopoverPos(null); setDrawingEditProps(null);
                }} style={{ fontSize: 9, padding: '2px 6px', marginRight: 4 }}>Apply</button>
                <button onClick={() => {
                  const updated = drawings.filter(d => d.id !== editingDrawingId);
                  recordDrawingsChange(updated);
                  setEditingDrawingId(null); setDrawingPopoverPos(null); setDrawingEditProps(null);
                }} style={{ fontSize: 9, padding: '2px 6px' }}>Delete</button>
                <button onClick={() => { setEditingDrawingId(null); setDrawingPopoverPos(null); setDrawingEditProps(null); }} style={{ fontSize: 9, padding: '2px 6px', float: 'right' }}>Close</button>
              </div>
              <div style={{ fontSize: 8, color: tv.dim, marginTop: 4 }}>Right-click drawings for props (TV popover)</div>
            </div>
          )}
        </div>
      </div>

      {/* Sub indicator panes (RSI/MACD) synced */}
      {(activeIndicators.has('rsi') || activeIndicators.has('macd')) && (
        <div style={{ borderTop: `1px solid ${tv.border}`, background: tv.bg }}>
          {activeIndicators.has('rsi') && (
            <div style={{ height: 112 }}>
              <div style={{ padding: '1px 6px', fontSize: 9, color: tv.dim }}>RSI ({params.rsiPeriod || 14})</div>
              <div ref={rsiRef} style={{ width: '100%', height: 96 }} />
            </div>
          )}
          {activeIndicators.has('macd') && (
            <div style={{ height: 112 }}>
              <div style={{ padding: '1px 6px', fontSize: 9, color: tv.dim }}>MACD</div>
              <div ref={macdRef} style={{ width: '100%', height: 96 }} />
            </div>
          )}
        </div>
      )}
      </>
      ) : (
        /* Multi-pane grid (layoutMode '2'/'4'): N synced mini-charts, same
           underlying symbol/timeframe/indicators in every pane (per-pane
           different symbols/timeframes is out of scope for this pass). Each
           pane gets its own createChart instance (MiniGridPane below) and all
           panes stay in lockstep via the same subscribeVisibleTimeRangeChange
           sync pattern already used for the RSI/MACD sub-panes above. */
        <div style={{
          flex: 1, minHeight: 180, overflow: 'hidden', background: tv.bg,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gridTemplateRows: layoutMode === '4' ? '1fr 1fr' : '1fr',
          gap: 1,
        }}>
          {Array.from({ length: layoutMode === '4' ? 4 : 2 }).map((_, i) => (
            <div key={i} style={{ position: 'relative', overflow: 'hidden', border: `1px solid ${tv.border}` }}>
              <MiniGridPane
                paneIndex={i}
                baseCandles={baseCandles}
                activeIndicators={activeIndicators}
                params={params}
                tv={tv}
                isLogScale={isLogScale}
                chartsRef={gridChartsRef}
                syncGuardRef={gridSyncGuardRef}
              />
            </div>
          ))}
        </div>
      )}

      {/* Real Indicator Dialog (TV fx style modal) */}
      {showStudies && (
        <div className="tv-backdrop-anim" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center'
        }} onClick={() => setShowStudies(false)}>
          <div
            className="tv-modal-anim"
            style={{
              background: tv.surface, color: tv.text, width: 520, maxWidth: 'calc(100vw - 24px)', maxHeight: '78vh',
              border: `1px solid ${tv.border}`, borderRadius: 6, overflow: 'hidden',
              boxShadow: '0 8px 30px rgba(0,0,0,0.4)'
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: tv.bg }}>
              <strong style={{ fontSize: 14 }}>Indicators</strong>
              <button onClick={() => setShowStudies(false)} style={{ background: 'none', border: 'none', color: tv.dim, fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><IconClose /></button>
            </div>
            <div style={{ padding: 8, maxHeight: '62vh', overflowY: 'auto' }}>
              <input 
                placeholder="Search (e.g. EMA, RSI, MACD)..." 
                value={indicatorSearch} 
                onChange={e => setIndicatorSearch(e.target.value)}
                style={{ width: '100%', padding: 6, marginBottom: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }}
              />
              {filteredIndicators.map(ind => {
                const isActive = activeIndicators.has(ind.key);
                const paramFields = INDICATOR_PARAM_FIELDS[ind.key];
                const isEditingParams = isActive && paramEditorKey === ind.key;
                const duplicateKind = ({ ema: 'ema', sma: 'sma', rsi: 'rsi', atr: 'atr', stoch: 'stochastic' } as Record<string, ExtraIndicatorKind>)[ind.key];
                const style = indicatorStyle(ind.key, { color: tv.blue, secondaryColor: tv.orange, lineWidth: 2, visible: true });
                return (
                  <div key={ind.key} style={{ borderBottom: `1px solid ${tv.border}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 4px' }}>
                      <div>
                        <div style={{ fontSize: 12 }}>{ind.label}</div>
                        <div style={{ fontSize: 9, color: tv.dim }}>{ind.category}</div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {isActive && (
                          <button
                            className="tv-ctrl"
                            title="Edit parameters"
                            onClick={() => setParamEditorKey(isEditingParams ? null : ind.key)}
                            style={{
                              padding: '2px 5px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                              background: isEditingParams ? tv.blue + '33' : tv.bg,
                              border: `1px solid ${isEditingParams ? tv.blue : tv.border}`,
                              color: isEditingParams ? tv.blue : tv.dim, borderRadius: 2, cursor: 'pointer',
                            }}
                          ><IconGear /></button>
                        )}
                        {duplicateKind && (
                          <button className="tv-ctrl" title="Add another instance" onClick={() => addExtraIndicator(duplicateKind)} style={{ padding: '2px 6px', fontSize: 10, background: tv.bg, border: `1px solid ${tv.border}`, color: tv.text, borderRadius: 2, cursor: 'pointer' }}>+1</button>
                        )}
                        <button
                          className="tv-ctrl"
                          onClick={() => {
                            if (onToggleIndicator) onToggleIndicator(ind.key);
                            else console.log('Indicator toggle:', ind.key, ' (provide onToggleIndicator prop for full sync)');
                            // keep dialog open for multi add
                          }}
                          style={{
                            padding: '2px 8px', fontSize: 10,
                            background: isActive ? tv.green + '33' : tv.bg,
                            border: `1px solid ${isActive ? tv.green : tv.border}`,
                            color: isActive ? tv.green : tv.text, borderRadius: 2, cursor: 'pointer'
                          }}
                        >
                          {isActive ? 'Remove' : 'Add'}
                        </button>
                      </div>
                    </div>
                    {isEditingParams && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, padding: '2px 4px 8px' }}>
                        {(paramFields || []).map(field => {
                          // Periods/multipliers must stay positive - a negative
                          // (or zero) period poisons ema/bollingerBands/atr/
                          // supertrend/rsi/macd with NaN or runaway values (their
                          // `|| default` fallbacks only catch exactly 0), so floor
                          // every field at its smallest sensible positive step.
                          const floor = field.step && field.step < 1 ? field.step : 1;
                          return (
                          <label key={field.key} style={{ fontSize: 9, color: tv.dim, display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {field.label}
                            <input
                              type="number"
                              step={field.step ?? 1}
                              min={floor}
                              value={params[field.key] ?? field.default}
                              onChange={e => {
                                const n = parseFloat(e.target.value);
                                setParamField(field.key, isNaN(n) ? field.default : Math.max(floor, n));
                              }}
                              style={{ width: 56, fontSize: 11, padding: '2px 4px', background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 2 }}
                            />
                          </label>
                          );
                        })}
                        <label style={{ fontSize: 9, color: tv.dim, display: 'flex', flexDirection: 'column', gap: 2 }}>
                          Color
                          <input type="color" value={style.color} onChange={(event) => updateIndicatorStyle(ind.key, { color: event.target.value })} style={{ width: 42, height: 24, padding: 1, background: tv.bg, border: `1px solid ${tv.border}` }} />
                        </label>
                        {['ema', 'bb', 'st-fast', 'st-mid', 'st-slow', 'macd', 'vol'].includes(ind.key) && (
                          <label style={{ fontSize: 9, color: tv.dim, display: 'flex', flexDirection: 'column', gap: 2 }}>
                            Secondary
                            <input type="color" value={style.secondaryColor || tv.orange} onChange={(event) => updateIndicatorStyle(ind.key, { secondaryColor: event.target.value })} style={{ width: 42, height: 24, padding: 1, background: tv.bg, border: `1px solid ${tv.border}` }} />
                          </label>
                        )}
                        <label style={{ fontSize: 9, color: tv.dim, display: 'flex', flexDirection: 'column', gap: 2 }}>
                          Width
                          <select value={style.lineWidth} onChange={(event) => updateIndicatorStyle(ind.key, { lineWidth: Number(event.target.value) as IndicatorStyle['lineWidth'] })} style={{ height: 24, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }}>
                            {[1, 2, 3, 4].map((width) => <option key={width} value={width}>{width}px</option>)}
                          </select>
                        </label>
                        <label style={{ fontSize: 9, color: tv.dim, display: 'flex', alignItems: 'center', gap: 4, alignSelf: 'end', height: 24 }}>
                          <input type="checkbox" checked={style.visible} onChange={(event) => updateIndicatorStyle(ind.key, { visible: event.target.checked })} /> Visible
                        </label>
                      </div>
                    )}
                  </div>
                );
              })}
              {filteredIndicators.length === 0 && <div style={{ padding: 8, color: tv.dim, fontSize: 11 }}>No matches. Try EMA, RSI, etc.</div>}
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${tv.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>Additional instances and formulas</div>
                    <div style={{ fontSize: 9, color: tv.dim }}>Add repeated indicators or a safe OHLC formula.</div>
                  </div>
                  <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {(['ema', 'sma', 'rsi', 'atr', 'stochastic', 'formula'] as ExtraIndicatorKind[]).map((kind) => (
                      <button key={kind} className="tv-ctrl" onClick={() => addExtraIndicator(kind)} style={{ padding: '2px 6px', fontSize: 9, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 2 }}>+ {kind === 'formula' ? 'Formula' : kind.toUpperCase()}</button>
                    ))}
                  </div>
                </div>
                {workspace.extraIndicators.map((indicator, index) => {
                  let formulaError = '';
                  if (indicator.kind === 'formula') {
                    try { compileFormula(indicator.formula || ''); } catch (error: any) { formulaError = error?.message || 'Invalid formula'; }
                  }
                  const updateExtra = (patch: Partial<typeof indicator>) => setWorkspace((current) => ({
                    ...current,
                    extraIndicators: current.extraIndicators.map((item) => item.id === indicator.id ? { ...item, ...patch } : item),
                  }));
                  const moveExtra = (delta: number) => setWorkspace((current) => {
                    const from = current.extraIndicators.findIndex((item) => item.id === indicator.id);
                    const to = Math.max(0, Math.min(current.extraIndicators.length - 1, from + delta));
                    if (from < 0 || from === to) return current;
                    const next = [...current.extraIndicators];
                    const [moved] = next.splice(from, 1);
                    next.splice(to, 0, moved);
                    return { ...current, extraIndicators: next };
                  });
                  const duplicateExtra = () => setWorkspace((current) => {
                    const from = current.extraIndicators.findIndex((item) => item.id === indicator.id);
                    if (from < 0 || current.extraIndicators.length >= MAX_EXTRA_INDICATORS) return current;
                    const next = [...current.extraIndicators];
                    next.splice(from + 1, 0, {
                      ...indicator,
                      id: `${indicator.kind}-${Date.now()}`,
                      name: indicator.kind === 'formula' ? indicator.name : `${indicator.name} copy`,
                      style: { ...indicator.style },
                    });
                    return { ...current, extraIndicators: next };
                  });
                  return (
                    <div key={indicator.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto auto auto auto auto', gap: 6, alignItems: 'end', padding: '7px 4px', borderTop: `1px solid ${tv.border}` }}>
                      <label style={{ fontSize: 9, color: tv.dim }}>
                        {indicator.kind === 'formula' ? 'Formula (open, high, low, close, volume, hl2, hlc3, ohlc4, change)' : 'Name'}
                        <input
                          value={indicator.kind === 'formula' ? (indicator.formula || '') : indicator.name}
                          onChange={(event) => updateExtra(indicator.kind === 'formula' ? { formula: event.target.value } : { name: event.target.value })}
                          style={{ display: 'block', width: '100%', marginTop: 2, padding: '3px 5px', background: tv.bg, color: tv.text, border: `1px solid ${formulaError ? tv.red : tv.border}`, borderRadius: 2 }}
                        />
                        {formulaError && <span style={{ display: 'block', marginTop: 2, color: tv.red }}>{formulaError}</span>}
                      </label>
                      {indicator.kind !== 'formula' && (
                        <label style={{ fontSize: 9, color: tv.dim }}>
                          Period
                          <input type="number" min={1} value={indicator.period} onChange={(event) => updateExtra({ period: Math.max(1, Number(event.target.value) || 1) })} style={{ display: 'block', width: 54, marginTop: 2, padding: '3px', background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }} />
                        </label>
                      )}
                      <label style={{ fontSize: 9, color: tv.dim }}>
                        Color
                        <input type="color" value={indicator.style.color} onChange={(event) => updateExtra({ style: { ...indicator.style, color: event.target.value } })} style={{ display: 'block', width: 38, height: 24, marginTop: 2 }} />
                      </label>
                      <label style={{ fontSize: 9, color: tv.dim }}>
                        Width
                        <select value={indicator.style.lineWidth} onChange={(event) => updateExtra({ style: { ...indicator.style, lineWidth: Number(event.target.value) as IndicatorStyle['lineWidth'] } })} style={{ display: 'block', height: 24, marginTop: 2, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }}>
                          {[1, 2, 3, 4].map((width) => <option key={width} value={width}>{width}</option>)}
                        </select>
                      </label>
                      <label style={{ fontSize: 9, color: tv.dim, display: 'flex', alignItems: 'center', gap: 4, height: 24 }}>
                        <input aria-label={`${indicator.name} visible`} type="checkbox" checked={indicator.style.visible} onChange={(event) => updateExtra({ style: { ...indicator.style, visible: event.target.checked } })} /> On
                      </label>
                      <button className="tv-ctrl" aria-label={`Move ${indicator.name} up`} disabled={index === 0} onClick={() => moveExtra(-1)} style={{ height: 24, padding: '2px 6px', color: tv.text, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2, opacity: index === 0 ? 0.45 : 1 }}>Up</button>
                      <button className="tv-ctrl" aria-label={`Move ${indicator.name} down`} disabled={index === workspace.extraIndicators.length - 1} onClick={() => moveExtra(1)} style={{ height: 24, padding: '2px 6px', color: tv.text, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2, opacity: index === workspace.extraIndicators.length - 1 ? 0.45 : 1 }}>Down</button>
                      <button className="tv-ctrl" aria-label={`Duplicate ${indicator.name}`} onClick={duplicateExtra} style={{ height: 24, padding: '2px 7px', color: tv.text, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2 }}>Copy</button>
                      <button className="tv-ctrl" title="Remove instance" onClick={() => setWorkspace((current) => ({ ...current, extraIndicators: current.extraIndicators.filter((item) => item.id !== indicator.id) }))} style={{ height: 24, padding: '2px 7px', color: tv.red, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2 }}>Remove</button>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ padding: 8, fontSize: 9, color: tv.dim, borderTop: `1px solid ${tv.border}`, background: tv.bg }}>
              Add/remove indicators, use the gear for parameters and style, or add repeated/custom instances below.
            </div>
          </div>
        </div>
      )}

      {showCompare && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowCompare(false)}>
          <div style={{ width: 460, maxWidth: 'calc(100vw - 24px)', background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 6, boxShadow: '0 8px 30px rgba(0,0,0,0.35)' }} onClick={(event) => event.stopPropagation()}>
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between' }}>
              <strong>Compare symbols</strong>
              <button onClick={() => setShowCompare(false)} style={{ border: 0, background: 'none', color: tv.dim, cursor: 'pointer' }}><IconClose /></button>
            </div>
            <div style={{ padding: 12 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <input autoFocus value={compareSearch} onChange={(event) => setCompareSearch(event.target.value)} placeholder="NSE:TCS" style={{ flex: 1, padding: 7, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }} />
                <button
                  onClick={() => addComparison(compareSearch)}
                  disabled={!compareSearch.trim() || workspace.comparisons.length >= MAX_COMPARISONS}
                  style={{ padding: '7px 12px', background: tv.blue, color: '#fff', border: 0, borderRadius: 3, cursor: 'pointer', opacity: compareSearch.trim() && workspace.comparisons.length < MAX_COMPARISONS ? 1 : 0.5 }}
                >
                  Add
                </button>
              </div>
              <div style={{ maxHeight: 150, overflowY: 'auto', marginTop: 6 }}>
                {COMMON_SYMBOLS.filter((item) => item !== symbol && item.toLowerCase().includes(compareSearch.toLowerCase())).map((item) => (
                  <button
                    key={item}
                    onClick={() => addComparison(item)}
                    disabled={workspace.comparisons.length >= MAX_COMPARISONS || workspace.comparisons.some((overlay) => overlay.symbol === item)}
                    style={{ display: 'block', width: '100%', padding: '7px 8px', textAlign: 'left', background: workspace.comparisons.some((overlay) => overlay.symbol === item) ? tv.blue + '22' : 'transparent', color: tv.text, border: 0, borderBottom: `1px solid ${tv.border}`, cursor: 'pointer', opacity: workspace.comparisons.length >= MAX_COMPARISONS ? 0.6 : 1 }}
                  >
                    {item}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 10, borderTop: `1px solid ${tv.border}` }}>
                {workspace.comparisons.map((overlay) => (
                  <div key={overlay.id} style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto auto auto', gap: 8, alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${tv.border}` }}>
                    <input aria-label={`${overlay.symbol} visible`} type="checkbox" checked={overlay.visible} onChange={(event) => updateComparison(overlay.id, { visible: event.target.checked })} />
                    <span style={{ fontSize: 12, color: tv.text }}>{overlay.symbol}</span>
                    <select aria-label={`${overlay.symbol} comparison mode`} value={overlay.mode} onChange={(event) => updateComparison(overlay.id, { mode: event.target.value as ComparisonOverlay['mode'] })} style={{ height: 26, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, fontSize: 10 }}>
                      <option value="percent">% change</option>
                      <option value="price">Price</option>
                    </select>
                    <input aria-label={`${overlay.symbol} color`} type="color" value={overlay.color} onChange={(event) => updateComparison(overlay.id, { color: event.target.value })} style={{ width: 34, height: 26 }} />
                    <button onClick={() => removeComparison(overlay.id)} style={{ padding: '4px 8px', background: tv.bg, color: tv.red, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Remove</button>
                  </div>
                ))}
                {!workspace.comparisons.length && <div style={{ padding: '14px 0 4px', textAlign: 'center', color: tv.dim, fontSize: 11 }}>No comparison overlays.</div>}
              </div>
            </div>
            <div style={{ padding: 10, borderTop: `1px solid ${tv.border}`, display: 'flex', gap: 8 }}>
              <button onClick={() => setWorkspace((current) => ({ ...current, ...setComparisons([]) }))} style={{ flex: 1, padding: 7, background: tv.bg, color: tv.red, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Clear all</button>
              <button onClick={() => setShowCompare(false)} style={{ flex: 1, padding: 7, background: tv.blue, color: '#fff', border: 0, borderRadius: 3, cursor: 'pointer' }}>Done</button>
            </div>
          </div>
        </div>
      )}

      {showChartSettings && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowChartSettings(false)}>
          <div style={{ width: 360, maxWidth: 'calc(100vw - 24px)', background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 6 }} onClick={(event) => event.stopPropagation()}>
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between' }}><strong>Chart settings</strong><button onClick={() => setShowChartSettings(false)} style={{ border: 0, background: 'none', color: tv.dim, cursor: 'pointer' }}><IconClose /></button></div>
            <div style={{ padding: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              {([['candleUp', 'Up candle'], ['candleDown', 'Down candle']] as const).map(([key, label]) => (
                <label key={key} style={{ fontSize: 10, color: tv.dim }}>{label}<input type="color" value={workspace.appearance[key]} onChange={(event) => setWorkspace((current) => ({ ...current, appearance: { ...current.appearance, [key]: event.target.value } }))} style={{ display: 'block', width: '100%', height: 30, marginTop: 4 }} /></label>
              ))}
              <label style={{ fontSize: 11, color: tv.text, display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={workspace.appearance.gridVisible} onChange={(event) => setWorkspace((current) => ({ ...current, appearance: { ...current.appearance, gridVisible: event.target.checked } }))} /> Grid lines</label>
              <label style={{ fontSize: 11, color: tv.text, display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={workspace.appearance.magnetCrosshair} onChange={(event) => setWorkspace((current) => ({ ...current, appearance: { ...current.appearance, magnetCrosshair: event.target.checked } }))} /> Magnet crosshair</label>
            </div>
          </div>
        </div>
      )}

      {showTemplates && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowTemplates(false)}>
          <div style={{ width: 440, maxWidth: 'calc(100vw - 24px)', maxHeight: '75vh', overflow: 'hidden', background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 6 }} onClick={(event) => event.stopPropagation()}>
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between' }}><strong>Chart templates</strong><button onClick={() => setShowTemplates(false)} style={{ border: 0, background: 'none', color: tv.dim, cursor: 'pointer' }}><IconClose /></button></div>
            <div style={{ padding: 10, display: 'flex', gap: 8 }}>
              <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} placeholder="Template name" style={{ flex: 1, padding: 7, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }} />
              <button onClick={saveCurrentTemplate} disabled={!templateName.trim()} style={{ padding: '7px 12px', background: tv.blue, color: '#fff', border: 0, borderRadius: 3, cursor: 'pointer', opacity: templateName.trim() ? 1 : 0.5 }}>Save current</button>
            </div>
            <div style={{ padding: '0 10px 10px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
              <button onClick={exportTemplateJson} style={{ padding: 7, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Export JSON</button>
              <button onClick={importTemplateJson} disabled={!templateImportText.trim()} style={{ padding: 7, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer', opacity: templateImportText.trim() ? 1 : 0.5 }}>Import JSON</button>
              <button onClick={resetCurrentWorkspace} style={{ padding: 7, background: tv.bg, color: tv.red, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Reset workspace</button>
            </div>
            <div style={{ padding: '0 10px 10px' }}>
              <textarea
                value={templateImportText}
                onChange={(event) => { setTemplateImportText(event.target.value); setTemplateError(''); }}
                placeholder="Paste or export template JSON"
                rows={templateImportText ? 5 : 2}
                style={{ width: '100%', resize: 'vertical', padding: 7, background: tv.bg, color: tv.text, border: `1px solid ${templateError ? tv.red : tv.border}`, borderRadius: 3, fontFamily: 'monospace', fontSize: 10 }}
              />
              {templateError && <div style={{ color: tv.red, fontSize: 10, marginTop: 4 }}>{templateError}</div>}
            </div>
            <div style={{ maxHeight: '38vh', overflowY: 'auto', borderTop: `1px solid ${tv.border}` }}>
              {templates.map((template) => (
                <div key={template.id} style={{ padding: 10, display: 'flex', alignItems: 'center', gap: 8, borderBottom: `1px solid ${tv.border}` }}>
                  <div style={{ flex: 1 }}><div style={{ fontSize: 12 }}>{template.name}</div><div style={{ fontSize: 9, color: tv.dim }}>{template.snapshot.tf} / {template.snapshot.chartType} / {template.snapshot.activeIndicators.length} indicators</div></div>
                  <button onClick={() => applyTemplate(template)} style={{ padding: '4px 9px', background: tv.blue, color: '#fff', border: 0, borderRadius: 3, cursor: 'pointer' }}>Apply</button>
                  <button onClick={() => deleteTemplate(template.id)} style={{ padding: '4px 9px', background: tv.bg, color: tv.red, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Delete</button>
                </div>
              ))}
              {!templates.length && <div style={{ padding: 18, textAlign: 'center', color: tv.dim, fontSize: 11 }}>No saved templates.</div>}
            </div>
          </div>
        </div>
      )}

      {showGoToDate && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowGoToDate(false)}>
          <div style={{ width: 360, maxWidth: 'calc(100vw - 24px)', background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 6 }} onClick={(event) => event.stopPropagation()}>
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between' }}><strong>Go to date / Bar Replay</strong><button onClick={() => setShowGoToDate(false)} style={{ border: 0, background: 'none', color: tv.dim, cursor: 'pointer' }}><IconClose /></button></div>
            <div style={{ padding: 14, display: 'grid', gap: 10 }}>
              <input type="datetime-local" value={goToDateValue} onChange={(event) => setGoToDateValue(event.target.value)} style={{ width: '100%', padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }} />
              <label style={{ display: 'grid', gap: 4, fontSize: 10, color: tv.dim }}>
                Replay speed
                <select value={replaySpeed} onChange={(event) => setReplaySpeed(Number(event.target.value))} style={{ padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }}>
                  {REPLAY_SPEEDS.map((speed) => <option key={speed} value={speed}>{speed}x</option>)}
                </select>
              </label>
            </div>
            <div style={{ padding: 12, borderTop: `1px solid ${tv.border}`, display: 'flex', gap: 8 }}>
              <button onClick={jumpToDate} disabled={!goToDateValue} style={{ flex: 1, padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3, cursor: 'pointer' }}>Go to date</button>
              <button onClick={startReplay} disabled={!fullBaseCandles.length} style={{ flex: 1, padding: 8, background: tv.purple, color: '#fff', border: 0, borderRadius: 3, cursor: 'pointer' }}>Start replay</button>
            </div>
          </div>
        </div>
      )}

      {alertDialog && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setAlertDialog(null)}>
          <div style={{ width: 380, maxWidth: 'calc(100vw - 24px)', background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 6 }} onClick={(event) => event.stopPropagation()}>
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between' }}><strong>Create price alert</strong><button onClick={() => setAlertDialog(null)} style={{ border: 0, background: 'none', color: tv.dim, cursor: 'pointer' }}><IconClose /></button></div>
            <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 11, color: tv.dim }}>{symbol}</div>
              <select value={alertCondition} onChange={(event) => setAlertCondition(event.target.value as typeof alertCondition)} style={{ padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }}><option value="price_above">Price crosses above</option><option value="price_below">Price crosses below</option></select>
              <input type="number" step="0.05" value={Number(alertDialog.price.toFixed(4))} onChange={(event) => setAlertDialog({ price: Number(event.target.value) })} style={{ padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }} />
              <input value={alertNotes} onChange={(event) => setAlertNotes(event.target.value)} placeholder="Optional note" style={{ padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}` }} />
              {createAlert.isError && <div style={{ fontSize: 10, color: tv.red }}>{createAlert.error.message}</div>}
            </div>
            <div style={{ padding: 12, borderTop: `1px solid ${tv.border}`, display: 'flex', gap: 8 }}><button onClick={() => { setAlertDialog(null); setAlertDraft(null); }} style={{ flex: 1, padding: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }}>Cancel</button><button onClick={submitAlert} disabled={createAlert.isPending || !(alertDialog.price > 0)} style={{ flex: 1, padding: 8, background: tv.orange, color: '#fff', border: 0, borderRadius: 3, opacity: createAlert.isPending ? 0.6 : 1 }}>{createAlert.isPending ? 'Creating...' : 'Create alert'}</button></div>
          </div>
        </div>
      )}
    </div>
  );
}

function toolBtnStyle(active: boolean, t: any, accent: string): React.CSSProperties {
  return {
    border: `1px solid ${active ? accent : t.border}`,
    background: active ? accent + '22' : 'transparent',
    color: active ? accent : t.dim,
    padding: '1px 5px',
    fontSize: 9,
    borderRadius: 2,
    cursor: 'pointer',
  };
}
