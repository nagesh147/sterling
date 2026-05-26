import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ColorType, LineSeries } from 'lightweight-charts';
import { useLivePnl } from '../hooks/useLivePnl';
import { c as t, tint } from '../styles/terminalUI';

export function EquityCurve() {
  const { data: pnlData } = useLivePnl();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: t.dim,
      },
      grid: { vertLines: { color: t.dim }, horzLines: { color: t.dim } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: false },
      width: containerRef.current.clientWidth,
      height: 80,
    });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);
    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !pnlData?.positions?.length) return;
    const now = Math.floor(Date.now() / 1000);
    const total = pnlData.total_estimated_pnl_usd ?? 0;
    const series = chartRef.current.addSeries(LineSeries, {
      color: total >= 0 ? t.green : t.red,
      lineWidth: 2,
      lastValueVisible: true,
      priceLineVisible: false,
    });
    series.setData([
      { time: (now - 3600) as any, value: 0 },
      { time: now as any, value: total },
    ]);
  }, [pnlData]);

  const total = pnlData?.total_estimated_pnl_usd ?? 0;
  const color = total >= 0 ? t.green : t.red;

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 4 }}>
        SESSION P&L
        <span style={{ color, marginLeft: 8, fontWeight: 700 }}>
          {total >= 0 ? '+' : ''}${total.toFixed(2)}
        </span>
      </div>
      <div ref={containerRef} style={{ width: '100%', height: 80 }} />
    </div>
  );
}
