import { useEffect, useRef } from 'react';
import { LineSeries } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import { supertrendSegments } from '../../../utils/indicators';

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
      // Full-length green/red segments with whitespace on the inactive-trend bars
      // so each colour line breaks at the flips instead of the two series each
      // connecting across the other's gaps (which drew two crossing lines). See
      // supertrendSegments.
      const { bull, bear } = supertrendSegments(data, data.map((p) => p.time));
      const bs = chart.addSeries(LineSeries, { color: '#44cc88', lineWidth: width as any, lastValueVisible: false, priceLineVisible: false });
      bs.setData(bull as any);
      seriesRefs.current.push(bs);
      const rs = chart.addSeries(LineSeries, { color: '#cc4444', lineWidth: width as any, lastValueVisible: false, priceLineVisible: false });
      rs.setData(bear as any);
      seriesRefs.current.push(rs);
    });

    return () => {
      seriesRefs.current.forEach((s) => { try { chart.removeSeries(s); } catch { /* ignore */ } });
    };
  }, [chart, st1, st2, st3]);

  return null;
}
