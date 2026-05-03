import { useEffect, useRef } from 'react';
import { LineSeries } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import type { TrailStopState } from '../../../hooks/useTrailStop';

interface PositionOverlayProps {
  chart: IChartApi | null;
  entry: number;
  trailStop: TrailStopState | null;
  target: number;
}

export function PositionOverlay({ chart, entry, trailStop, target }: PositionOverlayProps) {
  const linesRef = useRef<any[]>([]);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!chart) return;

    if (!seriesRef.current) {
      seriesRef.current = chart.addSeries(LineSeries, { visible: false });
    }
    const series = seriesRef.current;

    linesRef.current.forEach((l) => { try { series.removePriceLine(l); } catch { /* ignore */ } });
    linesRef.current = [];

    if (entry > 0) {
      linesRef.current.push(series.createPriceLine({
        price: entry, color: '#44cc88', lineWidth: 1,
        lineStyle: 2, axisLabelVisible: true, title: `Entry $${entry.toFixed(0)}`,
      }));
    }
    if (trailStop?.stop) {
      linesRef.current.push(series.createPriceLine({
        price: trailStop.stop, color: '#cc4444', lineWidth: 1,
        lineStyle: 2, axisLabelVisible: true, title: `Stop $${trailStop.stop.toFixed(0)} (trailing)`,
      }));
    }
    if (target > 0) {
      linesRef.current.push(series.createPriceLine({
        price: target, color: '#f0c040', lineWidth: 1,
        lineStyle: 2, axisLabelVisible: true, title: `Target $${target.toFixed(0)}`,
      }));
    }

    return () => {
      linesRef.current.forEach((l) => { try { series.removePriceLine(l); } catch { /* ignore */ } });
    };
  }, [chart, entry, trailStop, target]);

  return null;
}
