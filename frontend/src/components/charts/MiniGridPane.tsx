import React, { useRef, useEffect } from 'react';
import {
  createChart, IChartApi, ColorType, CrosshairMode, PriceScaleMode,
  CandlestickSeries, LineSeries, HistogramSeries,
} from 'lightweight-charts';
import {
  ema, bollingerBands, vwap, supertrend,
  type Candle,
} from '../../utils/indicators';

// --- Synced multi-pane grid cell (layoutMode '2'/'4') ---
// A minimal, self-contained chart pane: same candles/indicators as the main
// chart, own createChart instance, no drawing tools/toolbar/right-click menus
// (those stay exclusive to the single-pane view - out of scope for this pass).
// Panning/zooming any registered pane broadcasts its visible range to every
// other registered pane, reusing the exact subscribeVisibleTimeRangeChange
// pattern already used in TradingViewKiteChart to sync the RSI/MACD sub-panes
// to the main chart.
//
// Extracted verbatim from TradingViewKiteChart.tsx (pure split, zero behavior
// change) except that the three SuperTrend variants now read their
// period/multiplier from `params` (stFastPeriod/stFastMult, stMidPeriod/
// stMidMult, stSlowPeriod/stSlowMult) instead of hardcoded literals, so the
// grid view's SuperTrend lines stay in sync with the new Indicators-modal
// param editor (see TradingViewKiteChart.tsx). Falls back to the same
// defaults (21/1, 14/2, 7/3) when a param is absent, so pre-existing
// persisted param blobs render identically to before.
export interface MiniGridPaneProps {
  paneIndex: number;
  baseCandles: Candle[];
  activeIndicators: Set<string>;
  params: any;
  tv: any;
  isLogScale: boolean;
  chartsRef: React.MutableRefObject<Map<number, IChartApi>>;
  syncGuardRef: React.MutableRefObject<boolean>;
}

export function MiniGridPane({ paneIndex, baseCandles, activeIndicators, params, tv, isLogScale, chartsRef, syncGuardRef }: MiniGridPaneProps) {
  const elRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!elRef.current || !baseCandles.length) return;

    const chart = createChart(elRef.current, {
      layout: { background: { type: ColorType.Solid, color: tv.bg }, textColor: tv.dim, fontFamily: tv.fontFamily },
      grid: { vertLines: { color: tv.border }, horzLines: { color: tv.border } },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: { borderVisible: false, mode: isLogScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal },
      timeScale: { borderVisible: false, timeVisible: true, rightBarStaysOnScroll: true, lockVisibleTimeRangeOnResize: true, minBarSpacing: 0.5 },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, mouseWheel: true, pinch: true },
      handleScroll: { vertTouchDrag: true, horzTouchDrag: true, mouseWheel: true, pressedMouseMove: true },
      kineticScroll: { mouse: true, touch: true },
      width: elRef.current.clientWidth,
      height: elRef.current.clientHeight,
    });

    const times = baseCandles.map(c => c.time);
    const candleS = chart.addSeries(CandlestickSeries, {
      upColor: tv.green, downColor: tv.red, borderUpColor: tv.green, borderDownColor: tv.red,
      wickUpColor: tv.green, wickDownColor: tv.red, borderVisible: true,
      priceLineVisible: true, lastValueVisible: true,
    });
    candleS.setData(baseCandles.map((b: any) => ({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close })));

    const closes = baseCandles.map((c: any) => c.close);
    const highs = baseCandles.map((c: any) => c.high);
    const lows = baseCandles.map((c: any) => c.low);

    if (activeIndicators.has('ema')) {
      const e1 = ema(closes, params.ema1 || 9);
      const e2 = ema(closes, params.ema2 || 21);
      const e9s = chart.addSeries(LineSeries, { color: tv.blue, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      e9s.setData(e1.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
      const e21s = chart.addSeries(LineSeries, { color: tv.orange, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      e21s.setData(e2.flatMap((v, i) => (v != null ? [{ time: times[i] as any, value: v }] : [])));
    }

    if (activeIndicators.has('bb')) {
      const bb = bollingerBands(closes, params.bbPeriod || 20, params.bbStd || 2);
      const bbUpper = chart.addSeries(LineSeries, { color: (tv.purple || '#a371f7') + '99', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      const bbLower = chart.addSeries(LineSeries, { color: (tv.purple || '#a371f7') + '99', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      bbUpper.setData(bb.map((b, i) => ({ time: times[i] as any, value: b.upper })));
      bbLower.setData(bb.map((b, i) => ({ time: times[i] as any, value: b.lower })));
    }

    if (activeIndicators.has('vwap')) {
      const v = vwap(baseCandles as any);
      const vs = chart.addSeries(LineSeries, { color: tv.purple, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      vs.setData(v.map((p) => ({ time: p.time as any, value: p.value })));
    }

    // Pale SuperTrend colors (unchanged formula: base color + '66' alpha),
    // matching the main chart's rendering exactly.
    const addST = (period: number, mult: number) => {
      const stData = supertrend(highs, lows, closes, period, mult);
      const bullPts: { time: any; value: number }[] = [];
      const bearPts: { time: any; value: number }[] = [];
      stData.forEach((p, i) => {
        const pt = { time: times[i] as any, value: p.value };
        (p.direction === 'up' ? bullPts : bearPts).push(pt);
      });
      if (bullPts.length) { const s = chart.addSeries(LineSeries, { color: tv.green + '66', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(bullPts); }
      if (bearPts.length) { const s = chart.addSeries(LineSeries, { color: tv.red + '66', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(bearPts); }
    };
    if (activeIndicators.has('st-fast')) addST(params.stFastPeriod || 21, params.stFastMult || 1);
    if (activeIndicators.has('st-mid')) addST(params.stMidPeriod || 14, params.stMidMult || 2);
    if (activeIndicators.has('st-slow')) addST(params.stSlowPeriod || 7, params.stSlowMult || 3);

    if (activeIndicators.has('vol')) {
      const volS = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
      chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
      volS.setData(baseCandles.map((b: any) => ({
        time: b.time as any, value: b.volume || 0,
        color: b.close >= b.open ? `${tv.green}55` : `${tv.red}55`,
      })));
    }

    try { chart.timeScale().fitContent(); } catch {}

    // Register + sync: broadcast this pane's visible-range changes to every
    // other registered pane (guarded to avoid feedback loops).
    chartsRef.current.set(paneIndex, chart);
    const ts = chart.timeScale();
    const onRangeChange = (range: any) => {
      if (!range || syncGuardRef.current) return;
      syncGuardRef.current = true;
      chartsRef.current.forEach((c, idx) => {
        if (idx === paneIndex) return;
        try { c.timeScale().setVisibleRange(range); } catch {}
      });
      syncGuardRef.current = false;
    };
    ts.subscribeVisibleTimeRangeChange(onRangeChange);

    const ro = new ResizeObserver(() => {
      if (elRef.current) chart.applyOptions({ width: elRef.current.clientWidth, height: elRef.current.clientHeight });
    });
    ro.observe(elRef.current);

    return () => {
      try { ts.unsubscribeVisibleTimeRangeChange(onRangeChange); } catch {}
      chartsRef.current.delete(paneIndex);
      ro.disconnect();
      chart.remove();
    };
  }, [baseCandles, activeIndicators, params, tv, isLogScale, paneIndex, chartsRef, syncGuardRef]);

  return <div ref={elRef} style={{ position: 'absolute', inset: 0 }} />;
}
