import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, IChartApi, ColorType, CandlestickSeries, LineSeries, HistogramSeries, LineStyle, CrosshairMode, createSeriesMarkers } from 'lightweight-charts';
import type { OHLCVBar } from '../../hooks/useCandles';
import { PositionOverlay } from './overlays/PositionOverlay';
import { ema, supertrend, supertrendSegments, heikinAshi } from '../../utils/indicators';
import { useKiteDrawings, type Drawing } from '../../hooks/useKiteDrawings';

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
  isLogScale?: boolean;
  isDark?: boolean; // for theme consistency
  isHA?: boolean;
  // Drawing support (full port)
  drawings?: Drawing[];
  onDrawingsChange?: (d: Drawing[]) => void;
  drawMode?: string;
  onDrawModeChange?: (m: string) => void;
  showDrawToolbar?: boolean;
}

export function LiveChart({
  candles, height = 400, position, showSupertrend, showEma, showVwap,
  isLogScale = false, isDark = true, isHA = false,
  drawings: externalDrawings, onDrawingsChange, showDrawToolbar = false,
}: LiveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<any>({});
  const [chart, setChart] = useState<IChartApi | null>(null);

  const [internalDrawings, setInternal] = useState<Drawing[]>(externalDrawings || []);
  const drawings = onDrawingsChange ? (externalDrawings || []) : internalDrawings;
  const setDrawings = onDrawingsChange || setInternal;

  const { drawMode, setDrawMode, drawingPoints, setDrawingPoints, selectedDrawingId, handleChartClick, snapToOHLC } =
    useKiteDrawings({ initialDrawings: drawings, onChange: setDrawings });

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: isDark ? '#0d1117' : 'transparent' },
        textColor: isDark ? '#c9d1d9' : '#888',
      },
      grid: {
        vertLines: { color: isDark ? '#30363d' : '#1e1e1e' },
        horzLines: { color: isDark ? '#30363d' : '#1e1e1e' },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: { 
        borderVisible: false, 
        scaleMargins: { top: 0.05, bottom: showSupertrend || showEma || showVwap ? 0.15 : 0.05 },
        mode: isLogScale ? 1 /* Logarithmic */ : 0,
      },
      timeScale: { borderVisible: false, timeVisible: true },
      width: containerRef.current.clientWidth,
      height,
    });

    const candleS = chart.addSeries(CandlestickSeries, {
      upColor: '#44cc88',
      downColor: '#cc4444',
      borderUpColor: '#44cc88',
      borderDownColor: '#cc4444',
      wickUpColor: '#44cc88',
      wickDownColor: '#cc4444',
    });
    seriesRefs.current.candle = candleS;

    chartRef.current = chart;
    setChart(chart);

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    // Drawings subscribe click (port)
    chart.subscribeClick((param: any) => {
      if (!param.time || !seriesRefs.current.candle) return;
      const snap = (p: number) => snapToOHLC(p, candles as any, chart.timeScale().getVisibleRange());
      const price = (param.seriesPrices && param.seriesPrices.size)
        ? (Array.from(param.seriesPrices.values())[0] as number)
        : (candles[candles.length-1]?.close || 0);
      // call with adapted shape
      handleChartClick({ time: param.time, seriesPrices: new Map([[seriesRefs.current.candle, price]]) }, candles as any, chart, { green: '#44cc88', red: '#cc4444', cyan: '#39c5cf', purple: '#a371f7', amber: '#d29922', text: '#c9d1d9' }, snap);
    });

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [height, showSupertrend, showEma, showVwap, isLogScale, isDark]);

  useEffect(() => {
    if (!chartRef.current || !candles.length) return;

    let displayCandles: any[] = candles;
    if (isHA) {
      displayCandles = heikinAshi(candles);
    }
    const candleData = displayCandles.map((b: any) => ({
      time: b.time as any,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume || 0,
    }));
    seriesRefs.current.candle?.setData(candleData);

    const closes = candles.map((b) => b.close);
    const highs = candles.map((b) => b.high);
    const lows = candles.map((b) => b.low);
    const times = candles.map((b) => b.time);

    // EMA
    if (showEma) {
      if (!seriesRefs.current.ema9) {
        seriesRefs.current.ema9 = chartRef.current.addSeries(LineSeries, { color: '#00d4ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      }
      if (!seriesRefs.current.ema21) {
        seriesRefs.current.ema21 = chartRef.current.addSeries(LineSeries, { color: '#f0a020', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      }
      const e9 = ema(closes, 9);
      const e21 = ema(closes, 21);
      seriesRefs.current.ema9.setData(e9.flatMap((v, i) => v != null ? [{ time: times[i] as any, value: v }] : []));
      seriesRefs.current.ema21.setData(e21.flatMap((v, i) => v != null ? [{ time: times[i] as any, value: v }] : []));
    }

    // Supertrend
    if (showSupertrend) {
      const st = supertrend(highs, lows, closes, 10, 3);
      if (!seriesRefs.current.stBull) {
        seriesRefs.current.stBull = chartRef.current.addSeries(LineSeries, { color: '#44cc88', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      }
      if (!seriesRefs.current.stBear) {
        seriesRefs.current.stBear = chartRef.current.addSeries(LineSeries, { color: '#cc4444', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      }
      // Full-length green/red segments with whitespace on the inactive-trend bars
      // so the two series don't each connect across the other's gaps (which drew
      // two crossing lines). See supertrendSegments.
      const { bull, bear } = supertrendSegments(st, times);
      seriesRefs.current.stBull.setData(bull as any);
      seriesRefs.current.stBear.setData(bear as any);
    }

    // VWAP (simple)
    if (showVwap) {
      if (!seriesRefs.current.vwap) {
        seriesRefs.current.vwap = chartRef.current.addSeries(LineSeries, { color: '#9c27b0', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      }
      let cumTPV = 0, cumV = 0;
      const vdata = candles.map((c) => {
        const tp = (c.high + c.low + c.close) / 3;
        cumTPV += tp * (c.volume || 1);
        cumV += (c.volume || 1);
        return { time: c.time as any, value: cumV > 0 ? cumTPV / cumV : c.close };
      });
      seriesRefs.current.vwap.setData(vdata);
    }

    chartRef.current.timeScale().fitContent();
  }, [candles, showSupertrend, showEma, showVwap, isHA]);

  // Render drawings on this chart (full port of basic types)
  useEffect(() => {
    const ch = chartRef.current;
    const cs = seriesRefs.current.candle;
    if (!ch || !cs || !drawings.length) return;

    // cleanup previous draw series
    Object.keys(seriesRefs.current).forEach(k => { if (k.startsWith('d_')) { try { seriesRefs.current[k].remove?.(); } catch {}; delete seriesRefs.current[k]; } });

    drawings.forEach((d, i) => {
      const key = `d_${i}`;
      if (d.type === 'hline' && d.price != null) {
        const pl = cs.createPriceLine({ price: d.price, color: d.color || '#d29922', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true });
        seriesRefs.current[key] = pl;
      } else if ((d.type === 'trend' || d.type === 'ray') && d.points?.length === 2) {
        let pts = d.points;
        if (d.type === 'ray') {
          const vr = ch.timeScale().getVisibleRange();
          const visTo = (vr?.to || pts[1].time + 100000) as number;
          const slope = (pts[1].price - pts[0].price) / Math.max(1, pts[1].time - pts[0].time);
          pts = [pts[0], { time: visTo, price: pts[1].price + slope * (visTo - pts[1].time) }];
        }
        const s = ch.addSeries(LineSeries, { color: d.color || (d.type === 'ray' ? '#39c5cf' : '#44cc88'), lineWidth: 2 as any, priceLineVisible: false, lastValueVisible: false });
        seriesRefs.current[key] = s;
        s.setData(pts.map(p => ({ time: p.time as any, value: p.price })));
      } else if (d.type === 'fib' && d.points?.length === 2) {
        const [p1, p2] = d.points;
        const minp = Math.min(p1.price, p2.price), maxp = Math.max(p1.price, p2.price);
        const ratios = d.variant === 'ext' ? [0, 0.382, 0.5, 0.618, 1, 1.618] : [0, 0.382, 0.5, 0.618, 1];
        ratios.forEach((r, j) => {
          const fp = minp + (maxp - minp) * r;
          const pl = cs.createPriceLine({ price: fp, color: d.color || '#a371f7', lineWidth: 1, lineStyle: (r === 0 || r === 1) ? LineStyle.Solid : LineStyle.Dashed, axisLabelVisible: true });
          seriesRefs.current[`${key}_f${j}`] = pl;
        });
      } else if (d.type === 'text' && d.time != null) {
        createSeriesMarkers?.(cs, [{ time: d.time as any, position: 'aboveBar', color: d.color || '#c9d1d9', shape: 'square', text: (d.text || 'N').slice(0, 10) }]);
      }
    });
  }, [drawings]);

  // Simple mouse drag support on container (for crosshair draw mode)
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current || !chartRef.current) return;
    // delegated click already set; for drag we can rely on hook mouse if desired
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height, display: 'flex' }}>
      {showDrawToolbar && (
        <div style={{ width: 22, display: 'flex', flexDirection: 'column', gap: 1, padding: '3px 1px', background: '#111', borderRight: '1px solid #333', fontSize: 9, alignItems: 'center' }}>
          {['crosshair','hline','trend','fib','rect','text'].map(m => (
            <button key={m} onClick={() => setDrawMode(m as any)} title={m} style={{ width:16, height:14, fontSize:8, padding:0, border: drawMode===m ? '1px solid #4af' : '1px solid #333', background: drawMode===m ? '#222' : 'transparent', color: drawMode===m ? '#4af' : '#888' }}>{m[0]}</button>
          ))}
        </div>
      )}
      <div style={{ flex: 1, position: 'relative' }}>
        <div
          ref={containerRef}
          style={{ width: '100%', height, background: 'transparent' }}
          onMouseDown={onMouseDown}
        />
        {position && chart && (
          <PositionOverlay
            chart={chart}
            entry={position.entry}
            trailStop={position.stop != null ? { stop: position.stop, mode: null, highest_seen: null, partial_25_done: false, partial_50_done: false, stop_moved_last_check: false } : null}
            target={position.target}
          />
        )}
      </div>
    </div>
  );
}
