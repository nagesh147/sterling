import { useEffect, useRef } from 'react';
import { createChart, IChartApi, ColorType, LineSeries } from 'lightweight-charts';

export function PaperEquityCurve({ points, height = 220 }: {
  points: number[]; height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'var(--text-dim)',
      },
      grid: { vertLines: { visible: false }, horzLines: { color: 'var(--border)' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: false, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height,
    });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); chartRef.current = null; };
  }, [height]);

  useEffect(() => {
    if (!chartRef.current || !points?.length) return;
    const up = points[points.length - 1] >= points[0];
    const series = chartRef.current.addSeries(LineSeries, {
      color: up ? '#22c55e' : '#ef4444',
      lineWidth: 2,
      lastValueVisible: true,
      priceLineVisible: false,
    });
    // x = trade sequence (synthetic daily spacing); date axis labels hidden above.
    const t0 = 1700000000;
    series.setData(points.map((value, i) => ({ time: (t0 + i * 86400) as never, value })));
    chartRef.current.timeScale().fitContent();
    return () => { chartRef.current?.removeSeries(series); };
  }, [points]);

  return <div ref={containerRef} style={{ width: '100%' }} />;
}
