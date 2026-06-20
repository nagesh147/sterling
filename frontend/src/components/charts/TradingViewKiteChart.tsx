import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  createChart, IChartApi, ColorType, CandlestickSeries, LineSeries, HistogramSeries, AreaSeries, BarSeries,
  createSeriesMarkers, CrosshairMode, LineStyle, PriceScaleMode,
} from 'lightweight-charts';
import { useKiteDrawings, Drawing } from '../../hooks/useKiteDrawings';
import {
  ema, bollingerBands, vwap, rsi, macd, supertrend, heikinAshi,
  type Candle,
} from '../../utils/indicators';

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
  // for full TV-like control inside the component
  onTfChange?: (tf: string) => void;
  onIsHAChange?: (ha: boolean) => void;
  onIsLogScaleChange?: (log: boolean) => void;
  onSymbolChange?: (symbol: string) => void;
  onToggleIndicator?: (key: string) => void;
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
  onTfChange,
  onIsHAChange,
  onIsLogScaleChange,
  onSymbolChange,
  onToggleIndicator,
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
  } = useKiteDrawings({ initialDrawings: drawings, onChange: setDrawings });

  const mainRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLCanvasElement>(null); // for full histo VP
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const handlesRef = useRef<HTMLCanvasElement>(null); // visible drag handles + selection

  const mainChartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<Record<string, any>>({});
  const subChartsRef = useRef<{ rsi?: IChartApi; macd?: IChartApi }>({});

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

  // Symbol search (TV style dropdown)
  const [showSymbolSearch, setShowSymbolSearch] = useState(false);
  const [symbolSearch, setSymbolSearch] = useState('');

  // Timeframe dropdown (more TFs)
  const [showTfDropdown, setShowTfDropdown] = useState(false);

  // Better indicators dropdown (searchable, TV like)
  const [indicatorSearch, setIndicatorSearch] = useState('');

  // Drawing edit popover for right-click properties (TV style)
  const [editingDrawingId, setEditingDrawingId] = useState<number | null>(null);
  const [drawingPopoverPos, setDrawingPopoverPos] = useState<{x: number, y: number} | null>(null);
  const [drawingEditProps, setDrawingEditProps] = useState<any>(null);
  const [layoutMode, setLayoutMode] = useState<'1'|'2'|'4'>('1');

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
  const COMMON_SYMBOLS = [
    'NSE:NIFTY', 'NSE:BANKNIFTY', 'NSE:FINNIFTY', 'NSE:SENSEX',
    'NSE:RELIANCE', 'NSE:TCS', 'NSE:INFY', 'NSE:HDFCBANK', 'NSE:ICICIBANK',
    'NSE:SBIN', 'NSE:BHARTIARTL', 'NSE:ITC', 'NSE:LT', 'NSE:AXISBANK'
  ];

  const filteredSymbols = COMMON_SYMBOLS.filter(s => 
    s.toLowerCase().includes(symbolSearch.toLowerCase())
  );

  // Extended TF list for dropdown
  const ALL_TFS = ['1m','3m','5m','15m','30m','1H','2H','4H','D','W','M','1m','5m','15m','30m','60m','240m','D','W','M'];

  // Indicators list for searchable dropdown (TV style)
  const ALL_INDICATORS = [
    { key: 'ema', label: 'Exponential Moving Average (EMA)', category: 'Trend' },
    { key: 'bb', label: 'Bollinger Bands', category: 'Volatility' },
    { key: 'st', label: 'SuperTrend', category: 'Trend' },
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

  const candles = useMemo(() => {
    const valid = rawCandles.filter((c: any) => c.time != null && !isNaN(c.time));
    return [...valid].sort((a: any, b: any) => a.time - b.time)
      .filter((v: any, i: number, a: any[]) => i === 0 || v.time !== a[i - 1].time);
  }, [rawCandles]);

  const baseCandles = useMemo(() => {
    return isHA ? heikinAshi(candles as Candle[]) : (candles as Candle[]);
  }, [candles, isHA]);

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
  };

  // Exact TradingView dark theme colors + tokens for look & feel
  const tv = isDark ? {
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
  };

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

  // Main chart + indicators + drawings creation
  useEffect(() => {
    if (!mainRef.current || !baseCandles.length) return;

    if (mainChartRef.current) {
      mainChartRef.current.remove();
      mainChartRef.current = null;
      seriesRefs.current = {};
    }

    const chart = createChart(mainRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: tv.bg },
        textColor: tv.dim,
        fontFamily: tv.fontFamily,
      },
      grid: { vertLines: { color: tv.border, style: 1 }, horzLines: { color: tv.border, style: 1 } },
      crosshair: {
        mode: CrosshairMode.Magnet,
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
        lockVisibleTimeRangeOnResize: true,
        minBarSpacing: 2,
        // @ts-ignore
        tickMarkFormatter: (time: any, tickMarkType: any) => {
          const d = new Date((time as number) * 1000);
          if (tickMarkType === 0 /* Year */) return d.getFullYear().toString();
          if (tickMarkType === 1 /* Month */) return d.toLocaleString(undefined, { month: 'short' });
          if (tickMarkType === 2 /* Day */) return d.getDate().toString();
          return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },
      },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true, pressedMouseMove: true },
      localization: { priceFormatter: (price: number) => price.toFixed(2) },
      width: mainRef.current.clientWidth,
      height: mainRef.current.clientHeight,
    });

    const times = baseCandles.map((c: any) => c.time);
    const candleData = baseCandles.map((b: any) => ({
      time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close,
    }));

    let mainS;
    // Main series: enable labels like TradingView (last value on price scale)
    const mainOpts = { priceLineVisible: true, lastValueVisible: true };
    if (chartType === 'candles') {
      mainS = chart.addSeries(CandlestickSeries, {
        upColor: tv.green, downColor: tv.red,
        borderUpColor: tv.green, borderDownColor: tv.red,
        wickUpColor: tv.green, wickDownColor: tv.red,
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

    // Session breaks visual (TV-style markers for open/close, e.g. NSE)
    if (candleS && baseCandles.length > 0) {
      const firstTime = baseCandles[0].time;
      const lastTime = baseCandles[baseCandles.length - 1].time;
      createSeriesMarkers?.(candleS, [
        { time: firstTime as any, position: 'inBar', color: tv.amber, shape: 'circle', text: 'Open' },
        { time: lastTime as any, position: 'inBar', color: tv.amber, shape: 'circle', text: 'Close' },
      ]);
      // Add more if multi-day (simple mid point marker)
      if (baseCandles.length > 10) {
        const mid = baseCandles[Math.floor(baseCandles.length / 2)].time;
        createSeriesMarkers?.(candleS, [
          { time: mid as any, position: 'inBar', color: tv.dim, shape: 'circle', text: 'Session' },
        ]);
      }
    }

    const closes = baseCandles.map((c: any) => c.close);
    const highs = baseCandles.map((c: any) => c.high);
    const lows = baseCandles.map((c: any) => c.low);

    // EMA
    if (activeIndicators.has('ema')) {
      const e1 = ema(closes, params.ema1 || 9);
      const e2 = ema(closes, params.ema2 || 21);
      const e9s = chart.addSeries(LineSeries, { color: tv.blue, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
      seriesRefs.current.ema9 = e9s;
      e9s.setData(e1.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
      const e21s = chart.addSeries(LineSeries, { color: tv.orange, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
      seriesRefs.current.ema21 = e21s;
      e21s.setData(e2.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
    }

    // Bollinger
    if (activeIndicators.has('bb')) {
      const bb = bollingerBands(closes, params.bbPeriod || 20, params.bbStd || 2);
      const bbMid = chart.addSeries(LineSeries, { color: tv.cyan, lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: true });
      const bbUpper = chart.addSeries(LineSeries, { color: (tv.purple || '#a371f7') + '99', lineWidth: 1, priceLineVisible: false, lastValueVisible: true });
      const bbLower = chart.addSeries(LineSeries, { color: (tv.purple || '#a371f7') + '99', lineWidth: 1, priceLineVisible: false, lastValueVisible: true });
      seriesRefs.current.bbMid = bbMid; seriesRefs.current.bbUpper = bbUpper; seriesRefs.current.bbLower = bbLower;
      bbMid.setData(bb.map((b, i) => ({ time: times[i] as any, value: b.middle })));
      bbUpper.setData(bb.map((b, i) => ({ time: times[i] as any, value: b.upper })));
      bbLower.setData(bb.map((b, i) => ({ time: times[i] as any, value: b.lower })));
    }

    // VWAP
    if (activeIndicators.has('vwap')) {
      const v = vwap(baseCandles as any);
      const vs = chart.addSeries(LineSeries, { color: tv.purple, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
      seriesRefs.current.vwap = vs;
      vs.setData(v.map((p) => ({ time: p.time as any, value: p.value })));
    }

    // SuperTrend
    if (activeIndicators.has('st')) {
      const stData = supertrend(highs, lows, closes, params.stPeriod || 10, params.stMult || 3);
      const bullPts: { time: any; value: number }[] = [];
      const bearPts: { time: any; value: number }[] = [];
      stData.forEach((p, i) => {
        const pt = { time: times[i] as any, value: p.value };
        (p.direction === 'up' ? bullPts : bearPts).push(pt);
      });
      if (bullPts.length) {
        const s = chart.addSeries(LineSeries, { color: tv.green, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
        seriesRefs.current.stBull = s; s.setData(bullPts);
      }
      if (bearPts.length) {
        const s = chart.addSeries(LineSeries, { color: tv.red, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
        seriesRefs.current.stBear = s; s.setData(bearPts);
      }
    }

    // Volume
    if (activeIndicators.has('vol')) {
      const volS = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      seriesRefs.current.vol = volS;
      volS.setData(baseCandles.map((b: any) => ({
        time: b.time as any, value: b.volume || 0,
        color: b.close >= b.open ? `${tv.green}55` : `${tv.red}55`,
      })));
    }

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

    mainChartRef.current = chart;

    // Persisted zoom or fit
    const applyView = () => {
      try {
        if (persistedZoom) chart.timeScale().setVisibleRange(persistedZoom);
        else chart.timeScale().fitContent();
      } catch { chart.timeScale().fitContent(); }
    };
    setTimeout(applyView, 50);

    // Crosshair OHLC (pin-point)
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time || !param.seriesPrices) { setCurrentBarInfo(null); return; }
      const c = param.seriesPrices.get(candleS!);
      if (c && typeof c === 'object') {
        setCurrentBarInfo({ time: param.time, open: (c as any).open, high: (c as any).high, low: (c as any).low, close: (c as any).close });
      }
    });

    // Drawing placement via click
    chart.subscribeClick((param: any) => {
      const snapFn = (p: number, bc: any[], _r?: any) => snapToOHLC(p, bc, chart.timeScale().getVisibleRange());
      handleChartClick(param, baseCandles, chart, tv, snapFn);
    });

    const ro = new ResizeObserver(() => {
      if (mainRef.current) {
        chart.applyOptions({ width: mainRef.current.clientWidth, height: mainRef.current.clientHeight });
        setTimeout(drawHandles, 0);
      }
    });
    ro.observe(mainRef.current);

    const ts = chart.timeScale();
    const zh = (range: any) => { if (range && onZoomChange) onZoomChange(range); };
    ts.subscribeVisibleTimeRangeChange(zh);

    // Redraw handles on pan/zoom so point positions stay accurate (real coords)
    const handleSync = () => { if (selectedDrawingId) setTimeout(drawHandles, 0); };
    ts.subscribeVisibleTimeRangeChange(handleSync);

    // initial profile + handles
    setTimeout(() => { drawVolumeProfile(); drawHandles(); }, 120);

    return () => {
      try { ts.unsubscribeVisibleTimeRangeChange(zh); } catch {}
      try { ts.unsubscribeVisibleTimeRangeChange(handleSync); } catch {}
      ro.disconnect();
      chart.remove();
      mainChartRef.current = null;
      seriesRefs.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseCandles, activeIndicators, params, tv, drawings, isLogScale, isDark, persistedZoom, handleChartClick, snapToOHLC, onZoomChange, showVP, chartType]);

  // Sub RSI pane
  useEffect(() => {
    const el = rsiRef.current;
    const main = mainChartRef.current;
    if (!el || !activeIndicators.has('rsi') || !baseCandles.length) {
      if (subChartsRef.current.rsi) { subChartsRef.current.rsi.remove(); subChartsRef.current.rsi = undefined; }
      return;
    }
    const rChart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: tv.bg }, textColor: tv.dim, fontFamily: tv.fontFamily },
      grid: { vertLines: { color: tv.border }, horzLines: { color: tv.border } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      width: el.clientWidth, height: 108,
    });
    const closes = baseCandles.map((c: any) => c.close);
    const times = baseCandles.map((c: any) => c.time);
    const r = rsi(closes, params.rsiPeriod || 14);
    const line = rChart.addSeries(LineSeries, { color: tv.blue, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    line.setData(r.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
    const ob = rChart.addSeries(LineSeries, { color: tv.red + '66', lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: false });
    const os = rChart.addSeries(LineSeries, { color: tv.green + '66', lineWidth: 1, lineStyle: 2 as any, priceLineVisible: false, lastValueVisible: false });
    ob.setData(times.map(t => ({ time: t as any, value: 70 })));
    os.setData(times.map(t => ({ time: t as any, value: 30 })));
    subChartsRef.current.rsi = rChart;

    if (main) {
      const sync = (rg: any) => { try { rChart.timeScale().setVisibleRange(rg); } catch {} };
      main.timeScale().subscribeVisibleTimeRangeChange(sync);
    }
    const ro = new ResizeObserver(() => rChart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => { ro.disconnect(); rChart.remove(); subChartsRef.current.rsi = undefined; };
  }, [baseCandles, activeIndicators, params.rsiPeriod, tv]);

  // Sub MACD pane
  useEffect(() => {
    const el = macdRef.current;
    const main = mainChartRef.current;
    if (!el || !activeIndicators.has('macd') || !baseCandles.length) {
      if (subChartsRef.current.macd) { subChartsRef.current.macd.remove(); subChartsRef.current.macd = undefined; }
      return;
    }
    const mChart = createChart(el, {
      layout: { background: { type: ColorType.Solid, color: tv.bg }, textColor: tv.dim, fontFamily: tv.fontFamily },
      grid: { vertLines: { color: tv.border }, horzLines: { color: tv.border } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      width: el.clientWidth, height: 108,
    });
    const closes = baseCandles.map((c: any) => c.close);
    const times = baseCandles.map((c: any) => c.time);
    const m = macd(closes, params.macdFast || 12, params.macdSlow || 26, params.macdSig || 9);
    const ml = mChart.addSeries(LineSeries, { color: tv.blue, lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    const sl = mChart.addSeries(LineSeries, { color: tv.orange, lineWidth: 1, priceLineVisible: false, lastValueVisible: true });
    const hist = mChart.addSeries(HistogramSeries, { priceScaleId: 'hist' });
    ml.setData(m.flatMap((p, i) => p.macd != null ? [{ time: times[i] as any, value: p.macd }] : []));
    sl.setData(m.flatMap((p, i) => p.signal != null ? [{ time: times[i] as any, value: p.signal }] : []));
    hist.setData(m.flatMap((p, i) => p.hist != null ? [{ time: times[i] as any, value: p.hist, color: p.hist >= 0 ? tv.green + '88' : tv.red + '88' }] : []));
    subChartsRef.current.macd = mChart;

    if (main) {
      const sync = (rg: any) => { try { mChart.timeScale().setVisibleRange(rg); } catch {} };
      main.timeScale().subscribeVisibleTimeRangeChange(sync);
    }
    const ro = new ResizeObserver(() => mChart.applyOptions({ width: el.clientWidth }));
    ro.observe(el);
    return () => { ro.disconnect(); mChart.remove(); subChartsRef.current.macd = undefined; };
  }, [baseCandles, activeIndicators, params, tv]);

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
    rectRef.current = rect;
    const x = e.clientX - rect.left;
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

  // Right-click popover for drawing properties (TV style)
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!mainRef.current || !mainChartRef.current || drawings.length === 0) return;
    const rect = mainRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const chart: any = mainChartRef.current;
    let price = 0;
    let time = 0;
    try {
      price = chart.priceScale().coordinateToPrice?.(y) || 0;
      const logical = chart.timeScale().coordinateToLogical?.(x) || 0;
      if (baseCandles.length) {
        const idx = Math.floor(logical + baseCandles.length / 2);
        time = baseCandles[Math.max(0, Math.min(baseCandles.length-1, idx))]?.time || 0;
      }
    } catch {}
    // Simple hit test for nearest drawing point
    let hit: any = null;
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
    if (hit) {
      setEditingDrawingId(hit.id);
      setDrawingPopoverPos({x: e.clientX, y: e.clientY});
      setDrawingEditProps({...hit});
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

  // Toolbar helpers
  const toggleLog = () => {
    // parent usually owns isLogScale state; here we signal via zoom or no-op (parent re-renders with prop)
    // for standalone, we could lift but keep controlled from outside for InstrumentPane
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
      style={{
        width: 22, height: 20, padding: 0, margin: 0,
        border: `1px solid ${active ? accent : tv.border}`,
        background: active ? accent + '33' : 'transparent',
        color: active ? accent : tv.dim,
        borderRadius: 2,
        cursor: 'pointer',
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
      {/* TV EXACT top header bar */}
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
            style={{ 
              display: 'flex', alignItems: 'center', gap: 6, 
              padding: '2px 6px', border: `1px solid ${tv.border}`, borderRadius: 3,
              background: tv.surface, cursor: 'pointer', minWidth: 140 
            }}
          >
            <span style={{ fontWeight: 600, fontSize: 13, color: tv.text }}>{(symbol || '').split(':').pop() || symbol}</span>
            {baseCandles.length > 0 && (
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: tv.text }}>
                {baseCandles[baseCandles.length-1].close.toFixed(2)}
              </span>
            )}
            <span style={{ fontSize: 10, color: tv.dim }}>▼</span>
          </div>
          {showSymbolSearch && (
            <div style={{
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
          )}
        </div>

        {/* TV-style interval bar + dropdown for more */}
        <div style={{ display: 'flex', gap: 1, marginRight: 8, background: tv.bg, border: `1px solid ${tv.border}`, borderRadius: 2, padding: 1, position: 'relative' }}>
          {['1m','3m','5m','15m','30m','1H','2H','4H','D','W','M'].map((t) => (
            <button key={t} onClick={() => {
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
            style={{ padding: '1px 4px', fontSize: 9, color: tv.dim, background: 'transparent', border: 'none', cursor: 'pointer' }}
          >⋯</button>
          {showTfDropdown && (
            <div style={{ position: 'absolute', top: '100%', left: 0, zIndex: 100, background: tv.surface, border: `1px solid ${tv.border}`, borderRadius: 3, padding: 4, minWidth: 120, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
              {['1m','5m','15m','30m','60m','120m','240m','D','W','M'].map(t => (
                <div key={t} onClick={() => { if (onTfChange) onTfChange(t); setShowTfDropdown(false); }} style={{ padding: '3px 6px', cursor: 'pointer', fontSize: 10 }}>{t}</div>
              ))}
            </div>
          )}
        </div>

        {/* Chart type (TV style) */}
        <select 
          value={chartType} 
          onChange={(e) => setChartType(e.target.value as any)}
          style={{ fontSize: 10, background: tv.surface, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 2, padding: '1px 4px' }}
        >
          <option value="candles">Candles</option>
          <option value="bars">Bars</option>
          <option value="line">Line</option>
          <option value="area">Area</option>
        </select>
        <button onClick={() => { const next = !isHA; if (onIsHAChange) onIsHAChange(next); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${isHA ? tv.green : tv.border}`, background: isHA ? tv.green+'22' : 'transparent', color: isHA ? tv.green : tv.dim, borderRadius: 2 }}>HA</button>

        {/* Multi-chart layout switcher (TV 1/2/4/8) */}
        <div style={{ display: 'flex', gap: 2, marginLeft: 4, border: `1px solid ${tv.border}`, borderRadius: 2, padding: 1 }}>
          {(['1','2','4'] as const).map(m => (
            <button key={m} onClick={() => { 
              setLayoutMode(m); 
              console.log('Layout switched to', m, 'panes (use MultiPaneChart for full sync)'); 
            }} style={{ 
              fontSize: 8, padding: '1px 3px', background: layoutMode === m ? tv.blue : 'transparent', 
              color: layoutMode === m ? '#fff' : tv.dim, border: 'none', cursor: 'pointer' 
            }}>{m}</button>
          ))}
        </div>

        {/* Main TV actions - perfect clone style */}
        {/* Indicators - TV style button opening real dialog */}
        <button onClick={() => setShowStudies(!showStudies)} style={{ fontSize: 10, padding: '1px 6px', border: `1px solid ${tv.border}`, background: showStudies ? tv.blue + '22' : 'transparent', color: showStudies ? tv.blue : tv.dim, borderRadius: 2 }}>fx Indicators</button>
        <button onClick={() => { /* drawings in left */ }} style={{ fontSize: 10, padding: '1px 6px', border: `1px solid ${tv.border}`, background: 'transparent', color: tv.dim, borderRadius: 2 }}>🖊 Draw</button>

        <span style={{ color: tv.dim, margin: '0 4px' }}>|</span>

        <button onClick={() => { if (onIsLogScaleChange) onIsLogScaleChange(!isLogScale); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${isLogScale ? tv.blue : tv.border}`, background: isLogScale ? tv.blue+'22' : 'transparent', color: isLogScale ? tv.blue : tv.dim }}>Log</button>
        <button onClick={() => { /* toggle vp */ }} style={toolBtnStyle(showVP, tv, tv.amber)}>VP</button>
        <button onClick={() => setIsFullscreen(!isFullscreen)} title="Fullscreen" style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${tv.border}`, background: 'transparent' }}>⛶</button>

        <span style={{ flex: 1 }} />

        <span style={{ fontSize: 9, color: tv.dim }}>{baseCandles.length} bars</span>

        {currentBarInfo && (
          <span style={{ fontSize: 9, fontFamily: 'monospace', color: tv.text, background: tv.surface, padding: '1px 4px', borderRadius: 2, border: `1px solid ${tv.border}` }}>
            O {currentBarInfo.open?.toFixed(2) || currentBarInfo.o?.toFixed(2)} H {currentBarInfo.high?.toFixed(2) || currentBarInfo.h?.toFixed(2)} L {currentBarInfo.low?.toFixed(2) || currentBarInfo.l?.toFixed(2)} C {currentBarInfo.close?.toFixed(2) || currentBarInfo.c?.toFixed(2)}
          </span>
        )}

        <button onClick={() => { clearDrawings(); }} style={{ fontSize: 9, padding: '1px 4px', border: `1px solid ${tv.border}`, background: 'transparent' }} title="Clear drawings">✕</button>
      </div>

      {/* Main area: side vertical drawing toolbar + chart */}
      <div style={{ display: 'flex', flex: 1, minHeight: 180, overflow: 'hidden' }} onDoubleClick={startEditSelectedText}>
        {/* Side vertical toolbar (TV style) with icons */}
        <div style={vbarStyle}>
          {vBtn('crosshair', drawMode === 'crosshair', tv.blue, 'Crosshair / Select', '⌖')}
          {vBtn('hline', drawMode === 'hline', tv.amber, 'Horizontal Line', '—')}
          {vBtn('trend', drawMode === 'trend', tv.green, 'Trend Line', '↗')}
          {vBtn('ray', drawMode === 'ray', tv.cyan, 'Ray', '→')}
          <div style={{ height: 3 }} />
          {vBtn('fib', drawMode === 'fib', tv.purple, 'Fib Retracement', '𝜙')}
          {vBtn('fibext', drawMode === 'fibext', tv.purple, 'Fib Extension', '𝜙+')}
          {vBtn('fibfan', drawMode === 'fibfan', tv.purple, 'Fib Fan', '𝜙ᶠ')}
          <div style={{ height: 3 }} />
          {vBtn('rect', drawMode === 'rect', tv.red, 'Rectangle', '□')}
          {vBtn('pitchfork', drawMode === 'pitchfork', '#ff9800', "Andrew's Pitchfork", 'Ψ')}
          {vBtn('text', drawMode === 'text', tv.text, 'Text Annotation', 'Aa')}
        </div>

        {/* Chart container + overlays */}
        <div style={{ flex: 1, position: 'relative', background: tv.bg }}>
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
                position: 'fixed', left: drawingPopoverPos.x + 10, top: drawingPopoverPos.y + 10, 
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
                  setDrawings(updated);
                  if (onDrawingsChange) onDrawingsChange(updated);
                  setEditingDrawingId(null); setDrawingPopoverPos(null); setDrawingEditProps(null);
                }} style={{ fontSize: 9, padding: '2px 6px', marginRight: 4 }}>Apply</button>
                <button onClick={() => {
                  const updated = drawings.filter(d => d.id !== editingDrawingId);
                  setDrawings(updated);
                  if (onDrawingsChange) onDrawingsChange(updated);
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

      {/* Real Indicator Dialog (TV fx style modal) */}
      {showStudies && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)',
          zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center'
        }} onClick={() => setShowStudies(false)}>
          <div 
            style={{ 
              background: tv.surface, color: tv.text, width: 400, maxHeight: '70vh', 
              border: `1px solid ${tv.border}`, borderRadius: 6, overflow: 'hidden',
              boxShadow: '0 8px 30px rgba(0,0,0,0.4)'
            }} 
            onClick={e => e.stopPropagation()}
          >
            <div style={{ padding: 12, borderBottom: `1px solid ${tv.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: tv.bg }}>
              <strong style={{ fontSize: 14 }}>Indicators</strong>
              <button onClick={() => setShowStudies(false)} style={{ background: 'none', border: 'none', color: tv.dim, fontSize: 16, cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ padding: 8 }}>
              <input 
                placeholder="Search (e.g. EMA, RSI, MACD)..." 
                value={indicatorSearch} 
                onChange={e => setIndicatorSearch(e.target.value)}
                style={{ width: '100%', padding: 6, marginBottom: 8, background: tv.bg, color: tv.text, border: `1px solid ${tv.border}`, borderRadius: 3 }}
              />
              {filteredIndicators.map(ind => {
                const isActive = activeIndicators.has(ind.key);
                return (
                  <div key={ind.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 4px', borderBottom: `1px solid ${tv.border}` }}>
                    <div>
                      <div style={{ fontSize: 12 }}>{ind.label}</div>
                      <div style={{ fontSize: 9, color: tv.dim }}>{ind.category}</div>
                    </div>
                    <button 
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
                );
              })}
              {filteredIndicators.length === 0 && <div style={{ padding: 8, color: tv.dim, fontSize: 11 }}>No matches. Try EMA, RSI, etc.</div>}
            </div>
            <div style={{ padding: 8, fontSize: 9, color: tv.dim, borderTop: `1px solid ${tv.border}`, background: tv.bg }}>
              Click Add/Remove. Use parent toolbar for params. Close with X or outside.
            </div>
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
