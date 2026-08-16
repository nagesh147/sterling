import React, { useEffect, useRef } from 'react';
import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';
import { k } from '../../styles/kiteUI';

function chartSymbol(symbol: string) {
  const s = symbol.toUpperCase();
  if (s === 'NIFTY-I' || s === 'NIFTY' || s === 'NIFTY 50') return 'NSE:NIFTY 50';
  if (s === 'BANKNIFTY-I' || s === 'BANKNIFTY' || s === 'NIFTY BANK') return 'NSE:NIFTY BANK';
  if (s === 'FINNIFTY-I' || s === 'FINNIFTY' || s === 'NIFTY FIN SERVICE') return 'NSE:NIFTY FIN SERVICE';
  if (s === 'SENSEX-I' || s === 'SENSEX') return 'BSE:SENSEX';
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
  spotEntry,
  spotSl,
  spotTsl,
  spotExit,
  isBullish = true,
}: {
  symbol: string;
  entryTime?: string | null;
  exitTime?: string | null;
  spotEntry?: number | null;
  spotSl?: number | null;
  spotTsl?: number | null;
  spotExit?: number | null;
  isBullish?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const { data: candles, isLoading } = useCandles(chartSymbol(symbol), '5m', 500);

  const primaryColor = isBullish ? '#10b981' : '#f06428';
  const topColor = isBullish ? 'rgba(16, 185, 129, 0.28)' : 'rgba(240, 100, 40, 0.28)';
  const bottomColor = isBullish ? 'rgba(16, 185, 129, 0.01)' : 'rgba(240, 100, 40, 0.01)';

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#64748b',
        fontFamily: k.fontFamily,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(226, 232, 240, 0.6)' },
        horzLines: { color: 'rgba(226, 232, 240, 0.6)' },
      },
      crosshair: {
        vertLine: { color: '#94a3b8', width: 1, style: LineStyle.Dotted },
        horzLine: { color: '#94a3b8', width: 1, style: LineStyle.Dotted },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
      },
      width: el.clientWidth,
      height: el.clientHeight,
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: primaryColor,
      topColor,
      bottomColor,
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
  }, [primaryColor, topColor, bottomColor]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || !candles?.length) return;

    const points = candles
      .filter((bar) => bar.close > 0)
      .map((bar) => ({ time: toSec(bar.time) as Time, value: bar.close }));
    if (!points.length) return;

    series.setData(points);

    // Clear old price lines
    priceLinesRef.current.forEach((line) => {
      try {
        series.removePriceLine(line);
      } catch {}
    });
    priceLinesRef.current = [];

    // Add Entry Price Line
    if (spotEntry && spotEntry > 0) {
      const entryLine = series.createPriceLine({
        price: spotEntry,
        color: '#2563eb',
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: 'ENTRY',
      });
      priceLinesRef.current.push(entryLine);
    }

    // Add Stop Loss Price Line
    if (spotSl && spotSl > 0) {
      const slLine = series.createPriceLine({
        price: spotSl,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'STOP',
      });
      priceLinesRef.current.push(slLine);
    }

    // Add Trailing Stop Price Line
    if (spotTsl && spotTsl > 0) {
      const tslLine = series.createPriceLine({
        price: spotTsl,
        color: '#f59e0b',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'TSL',
      });
      priceLinesRef.current.push(tslLine);
    }

    // Add Exit Price Line if closed
    if (spotExit && spotExit > 0) {
      const exitLine = series.createPriceLine({
        price: spotExit,
        color: '#64748b',
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        title: 'EXIT',
      });
      priceLinesRef.current.push(exitLine);
    }

    const entry = toUnix(entryTime);
    const exit = toUnix(exitTime);

    createSeriesMarkers(series, [
      ...(entry
        ? [
            {
              time: entry as Time,
              position: (isBullish ? 'belowBar' : 'aboveBar') as 'belowBar' | 'aboveBar',
              color: isBullish ? '#10b981' : '#f06428',
              shape: (isBullish ? 'arrowUp' : 'arrowDown') as 'arrowUp' | 'arrowDown',
              text: 'Triggered',
            },
          ]
        : []),
      ...(exit
        ? [
            {
              time: exit as Time,
              position: (isBullish ? 'aboveBar' : 'belowBar') as 'belowBar' | 'aboveBar',
              color: '#64748b',
              shape: (isBullish ? 'arrowDown' : 'arrowUp') as 'arrowUp' | 'arrowDown',
              text: 'Closed',
            },
          ]
        : []),
    ]);

    if (entry) {
      const from = entry - 120 * 60;
      const to = (exit ?? entry) + 120 * 60;
      chart.timeScale().setVisibleRange({ from: from as Time, to: to as Time });
    } else {
      chart.timeScale().fitContent();
    }
  }, [candles, entryTime, exitTime, spotEntry, spotSl, spotTsl, spotExit, isBullish]);

  return (
    <div
      style={{
        position: 'relative',
        height: '100%',
        minHeight: 230,
        background: '#ffffff',
        border: `1px solid rgba(226, 232, 240, 0.8)`,
        borderRadius: 8,
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
      }}
    >
      <div ref={host} style={{ position: 'absolute', inset: 0 }} />
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#64748b',
            fontSize: 12,
            background: 'rgba(255,255,255,.8)',
            backdropFilter: 'blur(2px)',
          }}
        >
          Loading price history…
        </div>
      )}
      {!isLoading && !candles?.length && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#94a3b8',
            fontSize: 12,
          }}
        >
          No price candles recorded for this window.
        </div>
      )}
    </div>
  );
}
