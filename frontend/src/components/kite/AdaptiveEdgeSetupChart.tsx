import React, { useEffect, useRef } from 'react';
import { ColorType, createChart, createSeriesMarkers, LineSeries, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';
import { k } from '../../styles/kiteUI';

function chartSymbol(symbol: string) {
  if (symbol === 'NIFTY-I' || symbol === 'NIFTY') return 'NSE:NIFTY 50';
  if (symbol === 'BANKNIFTY-I' || symbol === 'BANKNIFTY') return 'NSE:NIFTY BANK';
  return symbol.includes(':') ? symbol : `NSE:${symbol}`;
}

function toUnix(time: string | null | undefined) {
  if (!time) return null;
  const ms = Date.parse(time);
  return Number.isNaN(ms) ? null : Math.floor(ms / 1000);
}

function toSec(time: number) {
  return time > 1e12 ? Math.floor(time / 1000) : time;
}

export function AdaptiveEdgeSetupChart({
  symbol,
  entryTime,
  exitTime,
}: {
  symbol: string;
  entryTime?: string | null;
  exitTime?: string | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const { data: candles, isLoading } = useCandles(chartSymbol(symbol), '5m', 500);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#fff' },
        textColor: k.dim,
        fontFamily: k.fontFamily,
        fontSize: 11,
      },
      grid: { vertLines: { color: '#f3f3f3' }, horzLines: { color: '#f3f3f3' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      width: el.clientWidth,
      height: el.clientHeight,
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });
    const series = chart.addSeries(LineSeries, {
      color: k.orange,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const ro = new ResizeObserver(() => {
      if (!host.current) return;
      chart.applyOptions({ width: host.current.clientWidth, height: host.current.clientHeight });
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || !candles?.length) return;
    const points = candles
      .filter((bar) => bar.close > 0)
      .map((bar) => ({ time: toSec(bar.time) as Time, value: bar.close }));
    if (!points.length) return;
    series.setData(points);
    const entry = toUnix(entryTime);
    const exit = toUnix(exitTime);
    createSeriesMarkers(series, [
      ...(entry ? [{ time: entry as Time, position: 'belowBar' as const, color: k.green, shape: 'arrowUp' as const, text: 'Triggered' }] : []),
      ...(exit ? [{ time: exit as Time, position: 'aboveBar' as const, color: k.red, shape: 'arrowDown' as const, text: 'Closed' }] : []),
    ]);
    if (entry) {
      const from = entry - 90 * 60;
      const to = (exit ?? entry) + 90 * 60;
      chart.timeScale().setVisibleRange({ from: from as Time, to: to as Time });
    } else {
      chart.timeScale().fitContent();
    }
  }, [candles, entryTime, exitTime]);

  return (
    <div style={{ position: 'relative', height: '100%', minHeight: 220, background: '#fff', border: `1px solid ${k.border}`, borderRadius: 8, overflow: 'hidden' }}>
      <div ref={host} style={{ position: 'absolute', inset: 0 }} />
      {isLoading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.dim, fontSize: 12, background: 'rgba(255,255,255,.7)' }}>
          Loading price…
        </div>
      )}
      {!isLoading && !candles?.length && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.dim, fontSize: 12 }}>
          No price history for this window.
        </div>
      )}
    </div>
  );
}
