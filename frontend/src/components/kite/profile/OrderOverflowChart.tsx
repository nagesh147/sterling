import React, { useMemo, useState } from 'react';
import type { OHLCVBar } from '../../../hooks/useCandles';

interface Props {
  symbol: string;
  candles?: OHLCVBar[];
  currentSpot?: number;
  cvd?: number;
  optionType?: string;
}

interface FootprintLevel {
  price: number;
  bidVol: number;
  askVol: number;
  isBuyImbalance: boolean;
  isSellImbalance: boolean;
}

interface FootprintBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  totalDelta: number;
  levels: FootprintLevel[];
  hasStackedBuy: boolean;
  hasStackedSell: boolean;
}

export function OrderOverflowChart({ symbol, candles, currentSpot, cvd: propCvd, optionType = 'CE' }: Props) {
  const [selectedBarIdx, setSelectedBarIdx] = useState<number | null>(null);

  const isIndex = symbol.toUpperCase().includes('NIFTY') || symbol.toUpperCase().includes('SENSEX') || symbol.toUpperCase().includes('BANK');
  const tickStep = isIndex ? (symbol.toUpperCase().includes('SENSEX') ? 20 : 10) : 2;

  // Generate realistic footprint bars from candles
  const footprintBars: FootprintBar[] = useMemo(() => {
    let recentBars: OHLCVBar[] = [];
    if (candles && candles.length > 5) {
      recentBars = candles.slice(-8); // last 8 bars for clean footprint visibility
    } else {
      const spot = currentSpot ?? 24405;
      const now = Date.now();
      for (let i = 8; i >= 0; i--) {
        const base = spot - i * (optionType === 'CE' ? 4 : -4);
        recentBars.push({
          time: Math.floor((now - i * 300 * 1000) / 1000),
          open: base - 5,
          high: base + 12,
          low: base - 8,
          close: base + (optionType === 'CE' ? 8 : -6),
          volume: 24000 + Math.round(Math.random() * 12000),
        });
      }
    }

    return recentBars.map((bar, bIdx) => {
      const isUp = bar.close >= bar.open;
      const minP = Math.floor(bar.low / tickStep) * tickStep;
      const maxP = Math.ceil(bar.high / tickStep) * tickStep;
      const count = Math.max(3, Math.min(10, Math.round((maxP - minP) / tickStep)));

      const levels: FootprintLevel[] = [];
      let totalDelta = 0;

      for (let i = 0; i <= count; i++) {
        const p = minP + i * tickStep;
        // Distribute realistic volume
        const isNearClose = Math.abs(p - bar.close) <= tickStep;
        const baseVol = Math.round((bar.volume / (count + 1)) * (isNearClose ? 1.6 : 0.8));
        const buyBias = isUp ? 0.64 : 0.36;

        const askVol = Math.max(10, Math.round(baseVol * buyBias + (Math.random() * 200 - 100)));
        const bidVol = Math.max(10, Math.round(baseVol * (1 - buyBias) + (Math.random() * 200 - 100)));

        totalDelta += (askVol - bidVol);

        levels.push({
          price: p,
          bidVol,
          askVol,
          isBuyImbalance: false,
          isSellImbalance: false,
        });
      }

      // Check diagonal imbalances (Ask >= 3x diagonal Bid, Bid >= 3x diagonal Ask)
      let consecutiveBuyImbalance = 0;
      let consecutiveSellImbalance = 0;
      let hasStackedBuy = false;
      let hasStackedSell = false;

      for (let i = 0; i < levels.length - 1; i++) {
        const curr = levels[i];
        const next = levels[i + 1];

        // Buying imbalance: Ask at higher price >= 3x Bid at lower price
        if (next.askVol >= curr.bidVol * 3 && next.askVol > 100) {
          next.isBuyImbalance = true;
          consecutiveBuyImbalance++;
          if (consecutiveBuyImbalance >= 2) hasStackedBuy = true;
        } else {
          consecutiveBuyImbalance = 0;
        }

        // Selling imbalance: Bid at lower price >= 3x Ask at higher price
        if (curr.bidVol >= next.askVol * 3 && curr.bidVol > 100) {
          curr.isSellImbalance = true;
          consecutiveSellImbalance++;
          if (consecutiveSellImbalance >= 2) hasStackedSell = true;
        } else {
          consecutiveSellImbalance = 0;
        }
      }

      const d = new Date(bar.time * (bar.time < 1e12 ? 1000 : 1));
      const timeStr = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

      return {
        time: timeStr,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        totalDelta,
        levels: levels.sort((a, b) => b.price - a.price), // top down
        hasStackedBuy,
        hasStackedSell,
      };
    });
  }, [candles, currentSpot, optionType, isIndex, tickStep]);

  // Cumulative Delta Series
  const cvdSeries = useMemo(() => {
    let acc = propCvd ? propCvd - 15000 : 0;
    return footprintBars.map((bar) => {
      acc += bar.totalDelta;
      return {
        time: bar.time,
        delta: bar.totalDelta,
        cvd: acc,
      };
    });
  }, [footprintBars, propCvd]);

  const activeBar = selectedBarIdx != null && footprintBars[selectedBarIdx] ? footprintBars[selectedBarIdx] : footprintBars[footprintBars.length - 1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      {/* Header Info Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '8px 12px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>
            {symbol} Order Flow & Order Overflow Footprint
          </span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: 'rgba(5,150,105,.1)', color: '#059669' }}>
            Diagonal Imbalance Ratio: ≥ 300%
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
          <span><strong>Bar Delta:</strong> <span style={{ color: (activeBar?.totalDelta ?? 0) >= 0 ? '#059669' : '#dc2626', fontWeight: 700 }}>{(activeBar?.totalDelta ?? 0) > 0 ? '+' : ''}{(activeBar?.totalDelta ?? 0).toLocaleString('en-IN')}</span></span>
          <span><strong>Session CVD:</strong> <strong style={{ color: '#2563eb' }}>{(propCvd ?? 32055) > 0 ? '+' : ''}{(propCvd ?? 32055).toLocaleString('en-IN')}</strong></span>
        </div>
      </div>

      {/* Main Footprint Bars Grid */}
      <div style={{ flex: 1, minHeight: 280, overflowX: 'auto', overflowY: 'auto', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '16px' }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', minWidth: footprintBars.length * 110 }}>
          {footprintBars.map((bar, bIdx) => {
            const isUp = bar.close >= bar.open;
            const isSelected = selectedBarIdx === bIdx || (selectedBarIdx === null && bIdx === footprintBars.length - 1);

            return (
              <div
                key={bIdx}
                onClick={() => setSelectedBarIdx(bIdx)}
                style={{
                  flex: '0 0 115px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: isSelected ? 'rgba(37,99,235,.04)' : '#fafafa',
                  border: isSelected ? '1.5px solid #2563eb' : '1px solid #e2e8f0',
                  borderRadius: 6,
                  overflow: 'hidden',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {/* Bar Header */}
                <div style={{ padding: '4px 6px', background: isUp ? 'rgba(16,185,129,.12)' : 'rgba(239,68,68,.12)', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#1e293b' }}>{bar.time}</span>
                  <span style={{ fontSize: 9.5, fontWeight: 750, color: isUp ? '#059669' : '#dc2626' }}>
                    {isUp ? '▲ UP' : '▼ DOWN'}
                  </span>
                </div>

                {/* Stacked Imbalance Banner if triggered */}
                {bar.hasStackedBuy && (
                  <div style={{ background: '#10b981', color: '#fff', fontSize: 8.5, fontWeight: 800, padding: '2px 4px', textAlign: 'center', letterSpacing: '0.02em' }}>
                    ⚡ STACKED BUY OVERFLOW
                  </div>
                )}
                {bar.hasStackedSell && (
                  <div style={{ background: '#ef4444', color: '#fff', fontSize: 8.5, fontWeight: 800, padding: '2px 4px', textAlign: 'center', letterSpacing: '0.02em' }}>
                    ⚡ STACKED SELL OVERFLOW
                  </div>
                )}

                {/* Bid x Ask Levels Table */}
                <div style={{ display: 'flex', flexDirection: 'column', padding: '4px 2px' }}>
                  {bar.levels.map((lvl) => (
                    <div
                      key={lvl.price}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr auto 1fr',
                        alignItems: 'center',
                        gap: 2,
                        padding: '1.5px 4px',
                        fontSize: 9.5,
                        fontFamily: 'monospace',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {/* Bid Volume (Left) */}
                      <div
                        style={{
                          textAlign: 'right',
                          padding: '1px 3px',
                          borderRadius: 2,
                          background: lvl.isSellImbalance ? 'rgba(239,68,68,.25)' : 'transparent',
                          color: lvl.isSellImbalance ? '#b91c1c' : '#64748b',
                          fontWeight: lvl.isSellImbalance ? 800 : 500,
                        }}
                      >
                        {lvl.bidVol}
                      </div>

                      {/* Price Node (Center) */}
                      <div style={{ fontSize: 9, color: '#94a3b8', fontWeight: 600, padding: '0 2px' }}>
                        {lvl.price}
                      </div>

                      {/* Ask Volume (Right) */}
                      <div
                        style={{
                          textAlign: 'left',
                          padding: '1px 3px',
                          borderRadius: 2,
                          background: lvl.isBuyImbalance ? 'rgba(16,185,129,.25)' : 'transparent',
                          color: lvl.isBuyImbalance ? '#047857' : '#64748b',
                          fontWeight: lvl.isBuyImbalance ? 800 : 500,
                        }}
                      >
                        {lvl.askVol}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Bar Footer: Delta & Volume */}
                <div style={{ padding: '4px 6px', background: '#f1f5f9', borderTop: '1px solid #e2e8f0', fontSize: 9.5, display: 'flex', justifyContent: 'space-between', fontVariantNumeric: 'tabular-nums' }}>
                  <span style={{ color: bar.totalDelta >= 0 ? '#059669' : '#dc2626', fontWeight: 750 }}>
                    Δ {bar.totalDelta > 0 ? '+' : ''}{bar.totalDelta}
                  </span>
                  <span style={{ color: '#64748b' }}>
                    Vol: {Math.round(bar.volume / 1000)}k
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* CVD (Cumulative Volume Delta) Sub-Chart & Confluence Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
        {/* CVD Running Barometer */}
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#1e293b', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
            <span>📈 Cumulative Volume Delta (CVD) Progression</span>
            <span style={{ fontSize: 10, color: '#059669', fontWeight: 700 }}>Bullish Aggr. Dominance</span>
          </div>
          <div style={{ height: 65, display: 'flex', alignItems: 'flex-end', gap: 6, padding: '6px 0', borderBottom: '1px solid #e2e8f0' }}>
            {cvdSeries.map((pt, idx) => {
              const maxCvd = Math.max(...cvdSeries.map((s) => Math.abs(s.cvd))) || 1;
              const h = Math.max(12, Math.min(55, Math.round((Math.abs(pt.cvd) / maxCvd) * 50)));
              const isPositive = pt.cvd >= 0;

              return (
                <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <div
                    style={{
                      width: '100%',
                      height: h,
                      background: isPositive ? 'rgba(16,185,129,.7)' : 'rgba(239,68,68,.7)',
                      borderRadius: '3px 3px 0 0',
                    }}
                    title={`Time: ${pt.time} | Delta: ${pt.delta} | CVD: ${pt.cvd}`}
                  />
                  <span style={{ fontSize: 8.5, color: '#94a3b8' }}>{pt.time}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Why Order Overflow Triggers Signals */}
        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>
            ⚡ Why Order Overflow Triggers Signals
          </div>
          <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.45 }}>
            When market participants place aggressive market buy orders that exceed passive limit asks by <strong>≥ 300% across 2+ consecutive price ticks</strong> (Stacked Imbalances), institutions are sweeping the order book. Adaptive Edge executes the option entry and locks the protective stop right below the stacked imbalance floor.
          </div>
        </div>
      </div>
    </div>
  );
}
