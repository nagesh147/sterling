import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { TradingViewKiteChart as LegacyTradingViewKiteChart } from './TradingViewKiteChartLegacy';
import { useKiteQuote } from '../../hooks/useKite';
import { heikinAshi, supertrend } from '../../utils/indicators';
import { NAVIGATOR_INDICATORS } from './navigatorOverlay';
import {
  CHART_CROSSHAIR_EVENT,
  CHART_RANGE_KEYS,
  installChartParityRuntime,
  normalizeChartCandles,
  removeChartParityContext,
  setChartParityContext,
  setChartVisibleRange,
  type ChartCrosshairEventDetail,
  type ChartRangeKey,
} from './chartParityRuntime';
import './tradingViewKiteParity.css';

installChartParityRuntime();

const MemoLegacyTradingViewKiteChart = React.memo(LegacyTradingViewKiteChart);
type LegacyProps = React.ComponentProps<typeof LegacyTradingViewKiteChart>;
type TradingViewKiteChartProps = LegacyProps & { onIsDarkChange?: (dark: boolean) => void };

type ChartType = 'candles' | 'bars' | 'line' | 'area';
type ChartStyle = 'regular' | 'heikin-ashi' | 'bars' | 'line' | 'area';

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', 'D', 'W', 'M'];
const CHART_STYLES: Array<{ value: ChartStyle; label: string; chartType: ChartType; heikinAshi: boolean }> = [
  { value: 'regular', label: 'Regular candles', chartType: 'candles', heikinAshi: false },
  { value: 'heikin-ashi', label: 'Heikin Ashi', chartType: 'candles', heikinAshi: true },
  { value: 'bars', label: 'Bars', chartType: 'bars', heikinAshi: false },
  { value: 'line', label: 'Line', chartType: 'line', heikinAshi: false },
  { value: 'area', label: 'Area', chartType: 'area', heikinAshi: false },
];
const INDICATORS = [
  ['vol', 'Volume'],
  ['st-fast', 'SuperTrend 21 1'],
  ['st-mid', 'SuperTrend 14 2'],
  ['st-slow', 'SuperTrend 7 3'],
  ['ema', 'EMA'],
  ['bb', 'Bollinger Bands'],
  ['vwap', 'VWAP'],
  ['rsi', 'RSI'],
  ['macd', 'MACD'],
  ['sma', 'SMA'],
  ['atr', 'ATR'],
  ['stoch', 'Stochastic'],
  // Navigator's own evidence, served by the backend rather than computed here
  // — see navigatorOverlay.ts for why it is never recomputed client-side.
  ...NAVIGATOR_INDICATORS,
] as const;

function formatPrice(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—';
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCompact(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—';
  return Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function Icon({ name }: { name: 'search' | 'plus' | 'candle' | 'indicator' | 'layout' | 'draw' | 'undo' | 'redo' | 'save' | 'theme' | 'settings' | 'camera' | 'more' | 'calendar' | 'chevron' }) {
  const common = { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  if (name === 'search') return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>;
  if (name === 'plus') return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
  if (name === 'candle') return <svg {...common}><path d="M7 3v4M7 17v4M4 7h6v10H4zM17 3v7M17 18v3M14 10h6v8h-6z"/></svg>;
  if (name === 'indicator') return <svg {...common}><path d="M4 17c3-8 5-8 8 0s5 8 8 0"/><path d="M4 7h16"/></svg>;
  if (name === 'layout') return <svg {...common}><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M12 4v16"/></svg>;
  if (name === 'draw') return <svg {...common}><path d="m4 20 4-1 11-11-3-3L5 16z"/><path d="m14 7 3 3"/></svg>;
  if (name === 'undo') return <svg {...common}><path d="M9 7 4 12l5 5"/><path d="M5 12h8a6 6 0 0 1 6 6"/></svg>;
  if (name === 'redo') return <svg {...common}><path d="m15 7 5 5-5 5"/><path d="M19 12h-8a6 6 0 0 0-6 6"/></svg>;
  if (name === 'save') return <svg {...common}><path d="M5 4h12l2 2v14H5z"/><path d="M8 4v6h8V4M8 20v-6h8v6"/></svg>;
  if (name === 'theme') return <svg {...common}><path d="M20 15a8 8 0 1 1-11-11 7 7 0 0 0 11 11Z"/></svg>;
  if (name === 'settings') return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 15 6l-.3-2.6h-4L10.4 6A7 7 0 0 0 8 7.1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1A7 7 0 0 0 10.4 18l.3 2.6h4L15 18a7 7 0 0 0 1.5-1.1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z"/></svg>;
  if (name === 'camera') return <svg {...common}><path d="M4 7h4l2-2h4l2 2h4v12H4z"/><circle cx="12" cy="13" r="4"/></svg>;
  if (name === 'calendar') return <svg {...common}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></svg>;
  if (name === 'chevron') return <svg {...common} width="12" height="12"><path d="m7 9 5 5 5-5"/></svg>;
  return <svg {...common}><circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/></svg>;
}

function ToolButton({ title, active, className, onClick, children }: { title: string; active?: boolean; className?: string; onClick?: () => void; children: React.ReactNode }) {
  return <button type="button" title={title} aria-label={title} aria-pressed={active || undefined} className={`zk-tool${active ? ' is-active' : ''}${className ? ` ${className}` : ''}`} onClick={onClick}>{children}</button>;
}

function studyLabel(key: string, params: Record<string, any>) {
  if (key === 'st-fast') return `SuperTrend ${Number(params.stFastPeriod) || 21} ${Number(params.stFastMult) || 1}`;
  if (key === 'st-mid') return `SuperTrend ${Number(params.stMidPeriod) || 14} ${Number(params.stMidMult) || 2}`;
  if (key === 'st-slow') return `SuperTrend ${Number(params.stSlowPeriod) || 7} ${Number(params.stSlowMult) || 3}`;
  return INDICATORS.find(([id]) => id === key)?.[1] || key;
}

export function TradingViewKiteChart(props: TradingViewKiteChartProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const reactId = useId();
  const contextId = useMemo(() => `kite-chart-${reactId.replace(/:/g, '')}`, [reactId]);
  const [range, setRange] = useState<ChartRangeKey>('ALL');
  const [hoveredBar, setHoveredBar] = useState<any>(null);
  const [timeMenu, setTimeMenu] = useState(false);
  const [chartStyleMenu, setChartStyleMenu] = useState(false);
  const [indicatorMenu, setIndicatorMenu] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [chartType, setChartType] = useState<ChartType>('candles');
  const [layout, setLayout] = useState<'1' | '2' | '4'>('1');
  const [localDark, setLocalDark] = useState(!!props.isDark);
  const [clock, setClock] = useState(() => Date.now());
  const effectiveDark = props.onIsDarkChange ? !!props.isDark : localDark;
  const selectedChartStyle: ChartStyle = props.isHA ? 'heikin-ashi' : chartType === 'candles' ? 'regular' : chartType;
  const selectedChartStyleMeta = CHART_STYLES.find((option) => option.value === selectedChartStyle) || CHART_STYLES[0];

  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);
  const studyCandles = useMemo(() => props.isHA ? heikinAshi(candles) : candles, [candles, props.isHA]);
  const activeKey = useMemo(() => Array.from(props.activeIndicators).sort().join(','), [props.activeIndicators]);
  const barIndex = useMemo(() => {
    if (!candles.length) return -1;
    if (hoveredBar?.time == null) return candles.length - 1;
    const index = candles.findIndex((bar) => bar.time === Number(hoveredBar.time));
    return index >= 0 ? index : candles.length - 1;
  }, [candles, hoveredBar?.time]);
  const displayBar = hoveredBar || candles[barIndex];
  const previous = barIndex > 0 ? candles[barIndex - 1] : undefined;
  const change = displayBar && previous ? Number(displayBar.close) - previous.close : 0;
  const changePct = previous?.close ? change / previous.close * 100 : 0;
  const positive = change >= 0;

  const studies = useMemo(() => {
    if (!studyCandles.length) return [] as Array<{ key: string; label: string; values?: any[] }>;
    const highs = studyCandles.map((bar) => bar.high);
    const lows = studyCandles.map((bar) => bar.low);
    const closes = studyCandles.map((bar) => bar.close);
    const out: Array<{ key: string; label: string; values?: any[] }> = [];
    for (const key of Array.from(props.activeIndicators)) {
      let values: any[] | undefined;
      if (key === 'st-fast') values = supertrend(highs, lows, closes, Number(props.params?.stFastPeriod) || 21, Number(props.params?.stFastMult) || 1);
      if (key === 'st-mid') values = supertrend(highs, lows, closes, Number(props.params?.stMidPeriod) || 14, Number(props.params?.stMidMult) || 2);
      if (key === 'st-slow') values = supertrend(highs, lows, closes, Number(props.params?.stSlowPeriod) || 7, Number(props.params?.stSlowMult) || 3);
      out.push({ key, label: studyLabel(key, props.params || {}), values });
    }
    return out;
  }, [studyCandles, activeKey, props.activeIndicators, props.params]);

  const quoteSymbols = useMemo(() => [props.symbol], [props.symbol]);
  const { data: quotes } = useKiteQuote(quoteSymbols, !!props.symbol, 30_000, 'quote');
  const quote = quotes?.[props.symbol];
  const bid = Number(quote?.depth?.buy?.[0]?.price ?? quote?.last_price ?? displayBar?.close ?? 0) || null;
  const ask = Number(quote?.depth?.sell?.[0]?.price ?? quote?.last_price ?? displayBar?.close ?? 0) || null;
  const spread = bid != null && ask != null ? Math.max(0, ask - bid) : null;

  useEffect(() => {
    setLocalDark(!!props.isDark);
  }, [props.isDark]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    setChartParityContext({
      id: contextId,
      symbol: props.symbol,
      tf: props.tf,
      rawCandles: props.rawCandles,
      isHA: !!props.isHA,
      activeIndicators: props.activeIndicators,
      params: props.params || {},
      theme: props.theme || {},
    });
  }, [contextId, props.symbol, props.tf, props.rawCandles, props.isHA, props.activeIndicators, props.params, props.theme]);

  useEffect(() => () => removeChartParityContext(contextId), [contextId]);

  useEffect(() => {
    const onCrosshair = (event: Event) => {
      const detail = (event as CustomEvent<ChartCrosshairEventDetail>).detail;
      if (detail?.contextId !== contextId) return;
      setHoveredBar(detail.bar || null);
    };
    window.addEventListener(CHART_CROSSHAIR_EVENT, onCrosshair);
    return () => window.removeEventListener(CHART_CROSSHAIR_EVENT, onCrosshair);
  }, [contextId]);

  useEffect(() => {
    const chartHost = sectionRef.current?.parentElement;
    const candidate = chartHost?.previousElementSibling as HTMLElement | null;
    if (!candidate) return;
    const instrument = props.symbol.split(':').pop() || props.symbol;
    const text = candidate.textContent || '';
    if (!text.includes(instrument) || !/\bbars?\b/i.test(text)) return;
    const previousDisplay = candidate.style.display;
    candidate.style.display = 'none';
    return () => { candidate.style.display = previousDisplay; };
  }, [props.symbol]);

  useEffect(() => {
    if (!timeMenu && !chartStyleMenu && !indicatorMenu) return;

    const closeMenus = () => {
      setTimeMenu(false);
      setChartStyleMenu(false);
      setIndicatorMenu(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenus();
    };
    const closeOnOutsidePointer = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest('.zk-menu-host')) return;
      closeMenus();
    };

    window.addEventListener('keydown', closeOnEscape);
    document.addEventListener('pointerdown', closeOnOutsidePointer, true);
    return () => {
      window.removeEventListener('keydown', closeOnEscape);
      document.removeEventListener('pointerdown', closeOnOutsidePointer, true);
    };
  }, [timeMenu, chartStyleMenu, indicatorMenu]);

  const selectRange = (nextRange: ChartRangeKey) => {
    setRange(nextRange);
    setChartVisibleRange(contextId, nextRange);
  };

  const legacyButtons = () => Array.from(sectionRef.current?.querySelectorAll<HTMLButtonElement>('.sterling-zerodha-chart__legacy button') || []);
  const clickLegacy = (...needles: string[]) => {
    const normalized = needles.map((value) => value.toLowerCase());
    const button = legacyButtons().find((candidate) => {
      const haystack = `${candidate.title || ''} ${candidate.textContent || ''} ${candidate.getAttribute('aria-label') || ''}`.toLowerCase();
      return normalized.some((needle) => haystack.includes(needle));
    });
    button?.click();
  };

  const changeChartStyle = (next: ChartStyle) => {
    const option = CHART_STYLES.find((candidate) => candidate.value === next);
    if (!option) return;
    setChartType(option.chartType);
    props.onIsHAChange?.(option.heikinAshi);
    const selects = Array.from(sectionRef.current?.querySelectorAll<HTMLSelectElement>('.sterling-zerodha-chart__legacy select') || []);
    const select = selects.find((candidate) => Array.from(candidate.options).some((entry) => entry.value === 'candles'));
    if (select) {
      select.value = option.chartType;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    setChartStyleMenu(false);
  };

  const changeLayout = () => {
    const next = layout === '1' ? '2' : layout === '2' ? '4' : '1';
    setLayout(next);
    const button = legacyButtons().find((candidate) => candidate.textContent?.trim() === next);
    button?.click();
  };

  const toggleIndicator = (key: string) => {
    if (props.onToggleIndicator) props.onToggleIndicator(key);
    else if (props.onActiveIndicatorsChange) {
      const next = new Set(props.activeIndicators);
      if (next.has(key)) next.delete(key); else next.add(key);
      props.onActiveIndicatorsChange(Array.from(next));
    }
  };

  const toggleDark = () => {
    const next = !effectiveDark;
    setLocalDark(next);
    props.onIsDarkChange?.(next);
  };

  const rangeLabel = (key: ChartRangeKey) => key === 'ALL' ? 'All' : key.toLowerCase();
  const exchange = props.symbol.includes(':') ? props.symbol.split(':')[0] : 'NSE';
  const instrument = props.symbol.split(':').pop() || props.symbol;
  const clockLabel = new Date(clock).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false });

  return (
    <section
      ref={sectionRef}
      className={`sterling-zerodha-chart${effectiveDark ? ' is-dark' : ''}${advancedOpen ? ' show-advanced' : ''}`}
      style={{ height: props.height ?? '100%' }}
      aria-label={`${props.symbol} chart workspace`}
    >
      <div className="zk-toolbar" role="toolbar" aria-label="Chart tools">
        <ToolButton title="Search symbol" className="zk-symbol" onClick={() => clickLegacy('search symbol')}>
          <Icon name="search"/><span>{instrument}</span>
        </ToolButton>
        <ToolButton title="Compare symbol" onClick={() => clickLegacy('compare')}><Icon name="plus"/></ToolButton>
        <div className="zk-menu-host">
          <ToolButton title="Timeframe" active={timeMenu} onClick={() => { setTimeMenu((open) => !open); setChartStyleMenu(false); setIndicatorMenu(false); }}><span className="zk-tf">{props.tf}</span></ToolButton>
          {timeMenu && <div className="zk-popover zk-timeframes">{TIMEFRAMES.map((tf) => <button key={tf} type="button" className={props.tf === tf ? 'is-selected' : undefined} onClick={() => { props.onTfChange?.(tf); setTimeMenu(false); }}>{tf}</button>)}</div>}
        </div>
        <div className="zk-menu-host zk-optional-small">
          <ToolButton title="Chart type" active={chartStyleMenu} onClick={() => { setChartStyleMenu((open) => !open); setTimeMenu(false); setIndicatorMenu(false); }}>
            <Icon name="candle"/><span className="zk-tool-label">{selectedChartStyleMeta.label}</span><span className="zk-tool-chevron"><Icon name="chevron"/></span>
          </ToolButton>
          {chartStyleMenu && (
            <div className="zk-popover zk-chart-types" role="menu" aria-label="Chart type">
              {CHART_STYLES.map((option) => {
                const selected = selectedChartStyle === option.value;
                return (
                  <button key={option.value} type="button" role="menuitemradio" aria-checked={selected} className={selected ? 'is-selected' : undefined} onClick={() => changeChartStyle(option.value)}>
                    <span className="zk-check">{selected ? '✓' : ''}</span>
                    <span className="zk-chart-type-copy"><strong>{option.label}</strong></span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="zk-menu-host">
          <ToolButton title="Indicators" active={indicatorMenu} onClick={() => { setIndicatorMenu((open) => !open); setTimeMenu(false); setChartStyleMenu(false); }}><Icon name="indicator"/><span className="zk-tool-label">Indicators</span></ToolButton>
          {indicatorMenu && <div className="zk-popover zk-indicators">{INDICATORS.map(([key, label]) => <button key={key} type="button" className={props.activeIndicators.has(key) ? 'is-selected' : undefined} onClick={() => toggleIndicator(key)}><span className="zk-check">{props.activeIndicators.has(key) ? '✓' : ''}</span>{label}</button>)}</div>}
        </div>
        <ToolButton title="Chart layout" className="zk-optional" onClick={changeLayout}><Icon name="layout"/><span className="zk-tool-label">{layout}</span></ToolButton>
        <ToolButton title="Drawing tools" className="zk-optional" onClick={() => setAdvancedOpen((open) => !open)}><Icon name="draw"/></ToolButton>
        <ToolButton title="Undo" className="zk-optional" onClick={() => clickLegacy('undo')}><Icon name="undo"/></ToolButton>
        <ToolButton title="Redo" className="zk-optional" onClick={() => clickLegacy('redo')}><Icon name="redo"/></ToolButton>
        <div className="zk-toolbar-spacer"/>
        <ToolButton title="Save template" className="zk-optional" onClick={() => clickLegacy('template')}><Icon name="save"/></ToolButton>
        <ToolButton title="Toggle theme" active={effectiveDark} onClick={toggleDark}><Icon name="theme"/></ToolButton>
        <ToolButton title="Chart settings" onClick={() => clickLegacy('chart settings', 'settings')}><Icon name="settings"/></ToolButton>
        <ToolButton title="Screenshot" className="zk-optional-small" onClick={() => clickLegacy('png', 'screenshot', 'export')}><Icon name="camera"/></ToolButton>
        <ToolButton title="More chart controls" active={advancedOpen} onClick={() => setAdvancedOpen((open) => !open)}><Icon name="more"/></ToolButton>
      </div>

      <div className="sterling-zerodha-chart__legacy">
        <MemoLegacyTradingViewKiteChart {...props} isDark={effectiveDark} height="100%" />
      </div>

      {displayBar && (
        <div className="zk-overlay" aria-label="Chart values">
          <div className="zk-instrument-line"><strong>{instrument}</strong><span>{props.tf}</span><span>{exchange}</span></div>
          <div className="zk-ohlc">
            <span><b>O</b>{formatPrice(displayBar.open)}</span>
            <span><b>H</b>{formatPrice(displayBar.high)}</span>
            <span><b>L</b>{formatPrice(displayBar.low)}</span>
            <span><b>C</b>{formatPrice(displayBar.close)}</span>
            <span className={positive ? 'is-positive' : 'is-negative'}>{positive ? '+' : ''}{formatPrice(change)} ({positive ? '+' : ''}{changePct.toFixed(2)}%)</span>
          </div>
          <div className="zk-quotes">
            <div className="zk-quote is-sell"><small>SELL</small><strong>{formatPrice(bid)}</strong></div>
            <span className="zk-spread">{spread == null ? '—' : spread.toFixed(2)}</span>
            <div className="zk-quote is-buy"><small>BUY</small><strong>{formatPrice(ask)}</strong></div>
          </div>
          <div className="zk-study-list">
            {studies.map((study, index) => {
              const point = study.values?.[barIndex];
              const value = study.key === 'vol' ? formatCompact(displayBar.volume) : point?.value != null ? formatPrice(point.value) : '';
              const directionClass = point?.direction === 'down' ? 'is-negative' : point?.direction === 'up' ? 'is-positive' : '';
              return <div className="zk-study-row" key={study.key}><i className={`zk-study-dot study-${index % 3}`}/><span>{study.label}</span>{value && <b className={directionClass}>{value}</b>}</div>;
            })}
          </div>
        </div>
      )}

      <div className="sterling-zerodha-chart__range-bar" role="toolbar" aria-label="Chart date range">
        <div className="sterling-zerodha-chart__ranges">
          {CHART_RANGE_KEYS.filter((key) => key !== 'YTD').map((key) => <button type="button" key={key} className={range === key ? 'is-active' : undefined} aria-pressed={range === key} onClick={() => selectRange(key)}>{rangeLabel(key)}</button>)}
          <button type="button" title="Go to date" onClick={() => clickLegacy('go to date', 'replay')}><Icon name="calendar"/></button>
        </div>
        <div className="sterling-zerodha-chart__status">
          <span>{clockLabel} IST</span>
          <button type="button" title="Percentage scale">%</button>
          <button type="button" className={props.isLogScale ? 'is-active' : undefined} onClick={() => props.onIsLogScaleChange?.(!props.isLogScale)}>log</button>
          <button type="button" onClick={() => selectRange('ALL')}>auto</button>
          <button type="button" title="Chart settings" onClick={() => clickLegacy('chart settings', 'settings')}><Icon name="settings"/></button>
        </div>
      </div>
    </section>
  );
}
