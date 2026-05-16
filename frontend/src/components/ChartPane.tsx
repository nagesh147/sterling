import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from 'lightweight-charts';
import { useCandles } from '../hooks/useCandles';
import { useSnapshot } from '../hooks/useSnapshot';

interface Props {
  underlying: string;
}

const TFS = ['15m', '1H', '4H', 'D'];

function computeEma(closes: number[], period: number): (number | null)[] {
  if (closes.length < period) return closes.map(() => null);
  const k = 2 / (period + 1);
  const result: (number | null)[] = new Array(closes.length).fill(null);
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = ema;
  for (let i = period; i < closes.length; i++) {
    ema = closes[i] * k + ema * (1 - k);
    result[i] = ema;
  }
  return result;
}

const REGIME_BG: Record<string, string> = {
  BULL_TREND: '#00c87a08',
  BEAR_TREND: '#f0305008',
  VOLATILE:   '#f0a02008',
  RANGING:    'transparent',
  IDLE:       'transparent',
};

export function ChartPane({ underlying }: Props) {
  const [tf, setTf] = useState('4H');
  const { data: candles = [], isLoading } = useCandles(underlying, tf, 120);
  const { data: snap } = useSnapshot(underlying);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<any>(null);
  const ema21Ref = useRef<any>(null);
  const ema55Ref = useRef<any>(null);
  const volRef = useRef<any>(null);

  const regime = snap?.macro_regime ?? 'RANGING';
  const bgTint = REGIME_BG[regime] ?? 'transparent';

  /* create chart once */
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#07090d' },
        textColor: '#4a5a6a',
      },
      grid: {
        vertLines: { color: '#1e2d3d' },
        horzLines: { color: '#1e2d3d' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderVisible: false, textColor: '#4a5a6a' },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor:        '#00c87a',
      downColor:      '#f03050',
      borderUpColor:  '#00c87a',
      borderDownColor:'#f03050',
      wickUpColor:    '#00c87a',
      wickDownColor:  '#f03050',
    });

    ema21Ref.current = chart.addSeries(LineSeries, {
      color: '#00d4ff',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    ema55Ref.current = chart.addSeries(LineSeries, {
      color: '#f0a020',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    /* volume pane — use price scale 'vol' */
    volRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    chart.priceScale('vol').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  /* update data when candles change */
  useEffect(() => {
    if (!candleRef.current || !candles.length) return;

    const candleData = candles.map((b) => ({
      time: b.time as any,
      open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    candleRef.current.setData(candleData);

    const closes = candles.map((b) => b.close);
    const times = candles.map((b) => b.time);

    const ema21 = computeEma(closes, 21);
    const ema55 = computeEma(closes, 55);

    ema21Ref.current?.setData(
      ema21.flatMap((v, i) => v !== null ? [{ time: times[i] as any, value: v }] : [])
    );
    ema55Ref.current?.setData(
      ema55.flatMap((v, i) => v !== null ? [{ time: times[i] as any, value: v }] : [])
    );

    volRef.current?.setData(
      candles.map((b) => ({
        time: b.time as any,
        value: b.volume,
        color: b.close >= b.open ? '#00c87a40' : '#f0305040',
      }))
    );

    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: bgTint }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
        borderBottom: '1px solid var(--t-border)', flexShrink: 0,
      }}>
        <span style={{ color: 'var(--t-bright)', fontWeight: 700, fontSize: 12, letterSpacing: 1, marginRight: 4 }}>
          {underlying}
        </span>
        {TFS.map((t) => (
          <button
            key={t}
            onClick={() => setTf(t)}
            style={{
              background: t === tf ? '#2090f022' : 'none',
              color: t === tf ? 'var(--t-blue)' : 'var(--t-dim)',
              border: `1px solid ${t === tf ? 'var(--t-blue)' : 'var(--t-border)'}`,
              borderRadius: 3, padding: '2px 8px', cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
            }}
          >
            {t}
          </button>
        ))}
        {/* Regime badge */}
        <span style={{ marginLeft: 'auto', fontSize: 10, color: REGIME_BG[regime] === 'transparent' ? 'var(--t-dim)' : '#dce8f0' }}>
          <span className="tag" style={{
            background: `${snap ? (REGIME_BG[regime] === 'transparent' ? 'var(--t-bg3)' : REGIME_BG[regime].replace('08', '22')) : 'var(--t-bg3)'}`,
            color: regime.includes('BULL') ? 'var(--t-green)' : regime.includes('BEAR') ? 'var(--t-red)' : regime === 'VOLATILE' ? 'var(--t-amber)' : 'var(--t-dim)',
          }}>
            {regime}
          </span>
        </span>
        {snap?.spot_price && (
          <span className="num" style={{ color: 'var(--t-bright)', fontSize: 12, marginLeft: 8 }}>
            ${snap.spot_price.toLocaleString('en-US', { maximumFractionDigits: snap.spot_price < 100 ? 2 : 0 })}
          </span>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, padding: '4px 10px', borderBottom: '1px solid var(--t-border)', flexShrink: 0 }}>
        <span style={{ fontSize: 9, color: 'var(--t-cyan)' }}>── EMA21</span>
        <span style={{ fontSize: 9, color: 'var(--t-amber)' }}>── EMA55</span>
        <span style={{ fontSize: 9, color: 'var(--t-dim)' }}>Vol</span>
      </div>

      {isLoading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--t-dim)', fontSize: 11 }}>
          Loading candles…
        </div>
      )}
      <div ref={containerRef} style={{ flex: 1, minHeight: 0, opacity: isLoading ? 0.3 : 1 }} />
    </div>
  );
}
