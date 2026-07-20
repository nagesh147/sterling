import React, { useLayoutEffect, useMemo, useState } from 'react';
import { TradingViewKiteChart as LegacyTradingViewKiteChart } from './TradingViewKiteChartLegacy';
import {
  CHART_RANGE_KEYS,
  installChartParityRuntime,
  normalizeChartCandles,
  setChartParityContext,
  setChartVisibleRange,
  type ChartRangeKey,
} from './chartParityRuntime';
import './tradingViewKiteParity.css';

installChartParityRuntime();

type TradingViewKiteChartProps = React.ComponentProps<typeof LegacyTradingViewKiteChart>;

function formatPrice(value: number) {
  if (!Number.isFinite(value)) return '—';
  return value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function supertrendLabels(active: Set<string>, params: Record<string, any>) {
  return [
    active.has('st-fast') ? `SuperTrend ${Number(params.stFastPeriod) || 21} ${Number(params.stFastMult) || 1}` : null,
    active.has('st-mid') ? `SuperTrend ${Number(params.stMidPeriod) || 14} ${Number(params.stMidMult) || 2}` : null,
    active.has('st-slow') ? `SuperTrend ${Number(params.stSlowPeriod) || 7} ${Number(params.stSlowMult) || 3}` : null,
  ].filter((label): label is string => !!label);
}

/**
 * Zerodha-style presentation shell around the existing advanced chart. The
 * underlying chart remains the single source of truth for drawings, templates,
 * replay, indicators and persistence; this shell adds the missing market strip,
 * range controls and the SuperTrend marker runtime without duplicating them.
 */
export function TradingViewKiteChart(props: TradingViewKiteChartProps) {
  const [range, setRange] = useState<ChartRangeKey>('ALL');
  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);
  const last = candles[candles.length - 1];
  const previous = candles[candles.length - 2];
  const change = last && previous ? last.close - previous.close : 0;
  const changePct = previous?.close ? change / previous.close * 100 : 0;
  const positive = change >= 0;
  const labels = useMemo(
    () => supertrendLabels(props.activeIndicators, props.params || {}),
    [props.activeIndicators, props.params],
  );

  useLayoutEffect(() => {
    setChartParityContext({
      symbol: props.symbol,
      tf: props.tf,
      rawCandles: props.rawCandles,
      isHA: !!props.isHA,
      activeIndicators: props.activeIndicators,
      params: props.params || {},
      theme: props.theme || {},
    });
  }, [
    props.symbol,
    props.tf,
    props.rawCandles,
    props.isHA,
    props.activeIndicators,
    props.params,
    props.theme,
  ]);

  const selectRange = (nextRange: ChartRangeKey) => {
    setRange(nextRange);
    setChartVisibleRange(nextRange);
  };

  return (
    <section
      className="sterling-zerodha-chart"
      style={{ height: props.height ?? '100%' }}
      aria-label={`${props.symbol} chart workspace`}
    >
      {last && (
        <div className="sterling-zerodha-chart__market-strip">
          <div className="sterling-zerodha-chart__ohlc" aria-label="Latest candle values">
            <span><b>O</b>{formatPrice(last.open)}</span>
            <span><b>H</b>{formatPrice(last.high)}</span>
            <span><b>L</b>{formatPrice(last.low)}</span>
            <span><b>C</b>{formatPrice(last.close)}</span>
            <span className={positive ? 'is-positive' : 'is-negative'}>
              {positive ? '+' : ''}{formatPrice(change)} ({positive ? '+' : ''}{changePct.toFixed(2)}%)
            </span>
          </div>
          <div className="sterling-zerodha-chart__study-legend" aria-label="Active SuperTrend studies">
            {labels.map((label, index) => (
              <span className="sterling-zerodha-chart__study" key={label}>
                <i className={`sterling-zerodha-chart__study-dot study-${index + 1}`} />
                {label}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="sterling-zerodha-chart__legacy">
        <LegacyTradingViewKiteChart {...props} height="100%" />
      </div>

      <div className="sterling-zerodha-chart__range-bar" role="toolbar" aria-label="Chart date range">
        <div className="sterling-zerodha-chart__ranges">
          {CHART_RANGE_KEYS.map((key) => (
            <button
              type="button"
              key={key}
              className={range === key ? 'is-active' : undefined}
              aria-pressed={range === key}
              onClick={() => selectRange(key)}
            >
              {key === 'ALL' ? 'All' : key}
            </button>
          ))}
        </div>
        <div className="sterling-zerodha-chart__status">
          <span>{props.isHA ? 'Heikin Ashi' : 'Candles'}</span>
          <span>{props.tf}</span>
          <span>IST</span>
        </div>
      </div>
    </section>
  );
}
