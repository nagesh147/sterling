import { useEffect, useRef } from 'react';
import { LineSeries } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import { supertrendRuns } from '../../../utils/indicators';

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
      // One line series per contiguous same-direction run (green up / red down).
      // NOT two full-length green/red series — v5 LineSeries connects across
      // whitespace, so those drew two crossing lines. See supertrendRuns.
      supertrendRuns(data, data.map((p) => p.time)).forEach((run) => {
        const s = chart.addSeries(LineSeries, { color: run.up ? '#44cc88' : '#cc4444', lineWidth: width as any, lastValueVisible: false, priceLineVisible: false });
        s.setData(run.points as any);
        seriesRefs.current.push(s);
      });
    });

    return () => {
      seriesRefs.current.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
    };
  }, [chart, st1, st2, st3]);

  return null;
}
