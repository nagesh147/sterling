import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ColorType, CandlestickSeries } from 'lightweight-charts';
import type { OHLCVBar } from '../../hooks/useCandles';
import { PositionOverlay } from './overlays/PositionOverlay';

export interface PositionOverlayData {
  entry: number;
  stop: number | null;
  target: number;
}

interface LiveChartProps {
  underlying: string;
  tf: string;
  candles: OHLCVBar[];
  height?: number;
  showSupertrend?: boolean;
  showEma?: boolean;
  showVwap?: boolean;
  position?: PositionOverlayData | null;
}

export function LiveChart({ candles, height = 400, position }: LiveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<any>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#888',
      },
      grid: {
        vertLines: { color: '#1e1e1e' },
        horzLines: { color: '#1e1e1e' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      width: containerRef.current.clientWidth,
      height,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#44cc88',
      downColor: '#cc4444',
      borderUpColor: '#44cc88',
      borderDownColor: '#cc4444',
      wickUpColor: '#44cc88',
      wickDownColor: '#cc4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;
    setChart(chart);

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !candles.length) return;
    const data = candles.map((b) => ({
      time: b.time as any,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height, background: 'transparent' }}
    >
      {position && chart && (
        <PositionOverlay
          chart={chart}
          entry={position.entry}
          trailStop={position.stop != null ? { stop: position.stop, mode: null, highest_seen: null, partial_25_done: false, partial_50_done: false, stop_moved_last_check: false } : null}
          target={position.target}
        />
      )}
    </div>
  );
}
