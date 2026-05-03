import { useEffect, useRef } from 'react';
import { LineSeries } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';

interface STPoint { time: number; value: number; direction: 'up' | 'down' }

interface SupertrendOverlayProps {
  chart: IChartApi | null;
  st1: STPoint[];
  st2: STPoint[];
  st3: STPoint[];
}

export function SupertrendOverlay({ chart, st1, st2, st3 }: SupertrendOverlayProps) {
  const seriesRefs = useRef<any[]>([]);

  useEffect(() => {
    if (!chart) return;
    seriesRefs.current.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
    seriesRefs.current = [];

    const configs = [
      { data: st1, width: 1.5 },
      { data: st2, width: 1.0 },
      { data: st3, width: 0.5 },
    ];

    configs.forEach(({ data, width }) => {
      if (!data.length) return;
      const bullPoints = data.filter((p) => p.direction === 'up')
        .map((p) => ({ time: p.time as any, value: p.value }));
      const bearPoints = data.filter((p) => p.direction === 'down')
        .map((p) => ({ time: p.time as any, value: p.value }));

      if (bullPoints.length) {
        const s = chart.addSeries(LineSeries, { color: '#44cc88', lineWidth: width as any, lastValueVisible: false, priceLineVisible: false });
        s.setData(bullPoints);
        seriesRefs.current.push(s);
      }
      if (bearPoints.length) {
        const s = chart.addSeries(LineSeries, { color: '#cc4444', lineWidth: width as any, lastValueVisible: false, priceLineVisible: false });
        s.setData(bearPoints);
        seriesRefs.current.push(s);
      }
    });

    return () => {
      seriesRefs.current.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
    };
  }, [chart, st1, st2, st3]);

  return null;
}
