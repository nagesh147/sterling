import React, { useEffect, useRef } from 'react';
import {
  createChart, createSeriesMarkers, CandlestickSeries, LineSeries, ColorType,
} from 'lightweight-charts';
import { k } from '../../styles/kiteUI';
import { MacChartSwitch } from './mac/MacChartSwitch';
import { useEngineSetup } from '../../hooks/useTripleSupertrend';
import type { SetupChart as SetupChartData } from '../../types/kiteEngine';

interface Props {
  token: number;
  underlying: string;
  onClose: () => void;
}

function dedupeSorted<T extends { time: number }>(arr: T[]): T[] {
  const valid = arr.filter((p) => p.time != null && !isNaN(p.time));
  const sorted = [...valid].sort((a, b) => a.time - b.time);
  return sorted.filter((v, i, a) => i === 0 || v.time !== a[i - 1].time);
}

function draw(container: HTMLDivElement, data: SetupChartData) {
  const chart = createChart(container, {
    layout: { background: { type: ColorType.Solid, color: k.bg }, textColor: k.dim, fontFamily: k.fontFamily },
    grid: { vertLines: { color: k.border }, horzLines: { color: k.border } },
    crosshair: { mode: 1 },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
    width: container.clientWidth,
    height: container.clientHeight,
  });

  const candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: k.green, downColor: k.red, borderUpColor: k.green,
    borderDownColor: k.red, wickUpColor: k.green, wickDownColor: k.red,
  });
  candleSeries.setData(dedupeSorted(data.candles).map((b) => ({
    time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close,
  })));

  const addLine = (rows: { time: number; value: number }[], color: string, title: string) => {
    const s = chart.addSeries(LineSeries, { color, lineWidth: 2, title, priceLineVisible: false, lastValueVisible: false });
    s.setData(dedupeSorted(rows).map((p) => ({ time: p.time as any, value: p.value })));
  };
  addLine(data.st_fast, k.blue, 'ST fast (21,1)');
  addLine(data.st_mid, k.orange, 'ST mid (14,2)');
  addLine(data.st_slow, k.dim, 'ST slow (7,3)');

  if (data.entry_index != null && data.candles[data.entry_index]) {
    createSeriesMarkers(candleSeries, [{
      time: data.candles[data.entry_index].time as any,
      position: 'belowBar', color: k.orange, shape: 'arrowUp', text: 'Entry',
    }]);
  }

  chart.timeScale().fitContent();
  const ro = new ResizeObserver(() => {
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
  });
  ro.observe(container);
  return () => { ro.disconnect(); chart.remove(); };
}

export function SetupChart({ token, underlying, onClose }: Props) {
  const { data, isLoading, isError } = useEngineSetup(token, underlying, true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !data?.candles?.length) return;
    return draw(containerRef.current, data);
  }, [data]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily }}>
      <div style={{ padding: '10px 16px', borderBottom: `1px solid ${k.border}`, display: 'flex', alignItems: 'center', gap: 16 }}>
        <button onClick={onClose} style={{ fontSize: 12, color: k.dim, background: 'none', border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 10px', cursor: 'pointer' }}>← Back</button>
        <span style={{ fontSize: 14, fontWeight: 600, color: k.text }}>{underlying}</span>
        <span style={{ fontSize: 11, color: k.dim }}>Heikin-Ashi 1H · triple SuperTrend · trail: {data?.trail_target ?? 'mid'}</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: k.dim, display: 'flex', gap: 12 }}>
          <span style={{ color: k.blue }}>— fast</span>
          <span style={{ color: k.orange }}>— mid</span>
          <span style={{ color: k.dim }}>— slow</span>
        </span>
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        {isLoading && <div style={{ padding: 32, color: k.dim, fontSize: 12 }}>Loading setup…</div>}
        {isError && <div style={{ padding: 32, color: k.red, fontSize: 12 }}>Could not load setup chart.</div>}
        <MacChartSwitch switchKey={underlying}>
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        </MacChartSwitch>
      </div>
    </div>
  );
}

export default SetupChart;
