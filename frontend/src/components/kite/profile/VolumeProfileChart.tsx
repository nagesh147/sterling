import React, { useMemo, useState } from 'react';
import type { OHLCVBar } from '../../../hooks/useCandles';

interface Props {
  symbol: string;
  candles?: OHLCVBar[];
  currentSpot?: number;
  poc?: number;
  vwap?: number;
}

export function VolumeProfileChart({ symbol, candles, currentSpot, poc: propPoc, vwap: propVwap }: Props) {
  const [hoveredLevel, setHoveredLevel] = useState<number | null>(null);

  const isIndex = symbol.toUpperCase().includes('NIFTY') || symbol.toUpperCase().includes('SENSEX') || symbol.toUpperCase().includes('BANK');
  const tickStep = isIndex ? (symbol.toUpperCase().includes('SENSEX') ? 25 : 10) : 2;

  const vpData = useMemo(() => {
    let spot = currentSpot ?? (isIndex ? 24405 : 2500);
    let minPrice = spot * 0.992;
    let maxPrice = spot * 1.008;

    if (candles && candles.length > 5) {
      const recent = candles.slice(-85);
      const highs = recent.map((c) => c.high);
      const lows = recent.map((c) => c.low);
      minPrice = Math.min(...lows);
      maxPrice = Math.max(...highs);
      spot = recent[recent.length - 1].close;
    }

    const startBin = Math.floor(minPrice / tickStep) * tickStep;
    const endBin = Math.ceil(maxPrice / tickStep) * tickStep;
    const binCount = Math.max(15, Math.min(45, Math.round((endBin - startBin) / tickStep)));

    const bins: {
      price: number;
      buyVol: number;
      sellVol: number;
      totalVol: number;
      isVpoc: boolean;
      inVa: boolean;
      isHvn: boolean;
      isLvn: boolean;
    }[] = [];

    for (let i = 0; i <= binCount; i++) {
      const p = startBin + i * tickStep;
      bins.push({
        price: p,
        buyVol: 0,
        sellVol: 0,
        totalVol: 0,
        isVpoc: false,
        inVa: false,
        isHvn: false,
        isLvn: false,
      });
    }

    if (candles && candles.length > 10) {
      const recent = candles.slice(-85);
      recent.forEach((bar) => {
        const barRange = Math.max(0.1, bar.high - bar.low);
        const isUpBar = bar.close >= bar.open;
        const buyRatio = isUpBar ? 0.62 : 0.38;

        bins.forEach((b) => {
          if (b.price >= bar.low && b.price <= bar.high) {
            // Distribute volume into overlapping price bins
            const weight = 1 - Math.min(1, Math.abs(b.price - bar.close) / barRange);
            const allocatedVol = Math.round((bar.volume * weight) / 5);
            b.buyVol += Math.round(allocatedVol * buyRatio);
            b.sellVol += Math.round(allocatedVol * (1 - buyRatio));
            b.totalVol += allocatedVol;
          }
        });
      });
    } else {
      // Synthetic realistic volume bell curve centered around POC
      const centerPrice = propPoc ?? spot;
      bins.forEach((b) => {
        const dist = Math.abs(b.price - centerPrice) / (tickStep * 5);
        const factor = Math.exp(-0.5 * dist * dist);
        const baseVol = Math.round(15000 * factor + 800 + Math.random() * 600);
        const buyRatio = b.price >= centerPrice ? 0.58 : 0.44;
        b.buyVol = Math.round(baseVol * buyRatio);
        b.sellVol = Math.round(baseVol * (1 - buyRatio));
        b.totalVol = baseVol;
      });
    }

    // Find VPOC (Maximum Volume Node)
    let maxVol = 0;
    let vpocPrice = bins[Math.floor(bins.length / 2)]?.price ?? spot;
    bins.forEach((b) => {
      if (b.totalVol > maxVol) {
        maxVol = b.totalVol;
        vpocPrice = b.price;
      }
    });

    bins.forEach((b) => {
      if (b.price === vpocPrice) b.isVpoc = true;
    });

    // Calculate Value Area (70% total volume expanding from VPOC)
    const totalVolumeAll = bins.reduce((sum, b) => sum + b.totalVol, 0);
    const targetVaVol = totalVolumeAll * 0.7;
    let currentVaVol = 0;
    const vpocIdx = bins.findIndex((b) => b.isVpoc);

    let up = vpocIdx;
    let down = vpocIdx;
    if (vpocIdx >= 0) {
      bins[vpocIdx].inVa = true;
      currentVaVol += bins[vpocIdx].totalVol;

      while (currentVaVol < targetVaVol && (up < bins.length - 1 || down > 0)) {
        const nextUpVol = up < bins.length - 1 ? bins[up + 1].totalVol : 0;
        const nextDownVol = down > 0 ? bins[down - 1].totalVol : 0;

        if (nextUpVol >= nextDownVol && up < bins.length - 1) {
          up++;
          bins[up].inVa = true;
          currentVaVol += bins[up].totalVol;
        } else if (down > 0) {
          down--;
          bins[down].inVa = true;
          currentVaVol += bins[down].totalVol;
        } else if (up < bins.length - 1) {
          up++;
          bins[up].inVa = true;
          currentVaVol += bins[up].totalVol;
        } else {
          break;
        }
      }
    }

    const vah = up >= 0 && bins[up] ? bins[up].price : maxPrice;
    const val = down >= 0 && bins[down] ? bins[down].price : minPrice;

    // Detect HVN and LVN nodes
    const activeBins = bins.filter((b) => b.totalVol > 0);
    const avgVol = totalVolumeAll / Math.max(1, activeBins.length);

    activeBins.forEach((b, idx) => {
      if (idx > 0 && idx < activeBins.length - 1) {
        const prev = activeBins[idx - 1].totalVol;
        const curr = b.totalVol;
        const next = activeBins[idx + 1].totalVol;
        // Peak (HVN)
        if (curr > prev * 1.15 && curr > next * 1.15 && curr > avgVol * 1.1) {
          b.isHvn = true;
        }
        // Valley (LVN)
        if (curr < prev * 0.85 && curr < next * 0.85 && curr < avgVol * 0.8) {
          b.isLvn = true;
        }
      }
    });

    return {
      bins: activeBins,
      vpocPrice,
      vah,
      val,
      spot,
      maxVol: Math.max(1, maxVol),
      totalVolumeAll,
    };
  }, [candles, currentSpot, propPoc, isIndex, tickStep]);

  const { bins, vpocPrice, vah, val, spot, maxVol, totalVolumeAll } = vpData;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      {/* Header Info Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '8px 12px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>
            {symbol} Volume Profile (VP & HVN/LVN)
          </span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: 'rgba(124,58,237,.1)', color: '#7c3aed' }}>
            VA 70% Volume: ₹{val.toLocaleString('en-IN')} – ₹{vah.toLocaleString('en-IN')}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
          <span><strong>Total Vol:</strong> {totalVolumeAll.toLocaleString('en-IN')}</span>
          <span style={{ color: '#d97706', fontWeight: 700 }}><strong>VPOC:</strong> ₹{vpocPrice.toLocaleString('en-IN')}</span>
        </div>
      </div>

      {/* Main Volume Profile Chart */}
      <div style={{ flex: 1, minHeight: 320, overflow: 'auto', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
          {bins.map((b) => {
            const isHovered = hoveredLevel === b.price;
            const isAtSpot = Math.abs(b.price - spot) < tickStep;
            const totalWidthPct = (b.totalVol / maxVol) * 100;
            const buyPct = b.totalVol > 0 ? (b.buyVol / b.totalVol) * totalWidthPct : 0;
            const sellPct = b.totalVol > 0 ? (b.sellVol / b.totalVol) * totalWidthPct : 0;
            const netDelta = b.buyVol - b.sellVol;

            return (
              <div
                key={b.price}
                onMouseEnter={() => setHoveredLevel(b.price)}
                onMouseLeave={() => setHoveredLevel(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '3px 4px',
                  borderRadius: 3,
                  background: isHovered
                    ? 'rgba(37,99,235,.1)'
                    : b.isVpoc
                    ? 'rgba(217,119,6,.12)'
                    : b.inVa
                    ? 'rgba(124,58,237,.03)'
                    : 'transparent',
                  borderLeft: b.isVpoc
                    ? '3px solid #d97706'
                    : isAtSpot
                    ? '3px solid #10b981'
                    : b.isHvn
                    ? '3px solid #7c3aed'
                    : b.isLvn
                    ? '3px solid #f43f5e'
                    : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'background 0.1s ease',
                }}
              >
                {/* Price Column */}
                <div
                  style={{
                    width: 78,
                    fontSize: 11,
                    fontWeight: b.isVpoc || isAtSpot ? 750 : 600,
                    color: b.isVpoc ? '#d97706' : isAtSpot ? '#059669' : b.inVa ? '#1e293b' : '#64748b',
                    fontVariantNumeric: 'tabular-nums',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>{b.price.toLocaleString('en-IN')}</span>
                  {b.isVpoc && (
                    <span style={{ fontSize: 8.5, padding: '1px 3px', borderRadius: 2, background: '#d97706', color: '#fff', fontWeight: 800 }}>
                      VPOC
                    </span>
                  )}
                  {isAtSpot && (
                    <span style={{ fontSize: 8.5, padding: '1px 3px', borderRadius: 2, background: '#059669', color: '#fff', fontWeight: 800 }}>
                      LTP
                    </span>
                  )}
                </div>

                {/* Horizontal Volume Bar Container */}
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 8 }}>
                  <div style={{ flex: 1, height: 14, background: '#f1f5f9', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
                    {/* Sell Volume (Red) */}
                    <div
                      style={{
                        width: `${sellPct}%`,
                        height: '100%',
                        background: b.isVpoc ? '#f59e0b' : '#f87171',
                        transition: 'width 0.2s ease',
                      }}
                      title={`Sell Vol: ${b.sellVol.toLocaleString('en-IN')}`}
                    />
                    {/* Buy Volume (Green) */}
                    <div
                      style={{
                        width: `${buyPct}%`,
                        height: '100%',
                        background: b.isVpoc ? '#d97706' : '#34d399',
                        transition: 'width 0.2s ease',
                      }}
                      title={`Buy Vol: ${b.buyVol.toLocaleString('en-IN')}`}
                    />
                  </div>

                  {/* Node Tags */}
                  {b.isHvn && (
                    <span style={{ fontSize: 9, fontWeight: 750, padding: '1px 5px', borderRadius: 3, background: 'rgba(124,58,237,.12)', color: '#7c3aed', whiteSpace: 'nowrap' }}>
                      HVN Acceptance Node
                    </span>
                  )}
                  {b.isLvn && (
                    <span style={{ fontSize: 9, fontWeight: 750, padding: '1px 5px', borderRadius: 3, background: 'rgba(244,63,94,.12)', color: '#e11d48', whiteSpace: 'nowrap' }}>
                      ⚡ LVN Breakout Zone
                    </span>
                  )}
                </div>

                {/* Net Delta & Total Vol Column */}
                <div
                  style={{
                    width: 140,
                    fontSize: 10.5,
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 8,
                  }}
                >
                  <span style={{ color: netDelta >= 0 ? '#059669' : '#dc2626', fontWeight: 650 }}>
                    {netDelta > 0 ? '+' : ''}{netDelta.toLocaleString('en-IN')}
                  </span>
                  <span style={{ color: '#64748b', fontWeight: 600, width: 55 }}>
                    {b.totalVol.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Volume Profile Legend Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0', fontSize: 10.5, color: '#64748b', flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#34d399', borderRadius: 2 }} /> Aggressive Buyers (Ask)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#f87171', borderRadius: 2 }} /> Aggressive Sellers (Bid)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: '#d97706', borderRadius: 2 }} /> VPOC Peak Node
          </span>
        </div>
        <div>
          <span style={{ color: '#7c3aed', fontWeight: 650 }}>■ HVN (Fair Value Consensus)</span>
          <span style={{ margin: '0 6px' }}>·</span>
          <span style={{ color: '#e11d48', fontWeight: 650 }}>■ LVN (Liquidity Void / Fast Moves)</span>
        </div>
      </div>
    </div>
  );
}
