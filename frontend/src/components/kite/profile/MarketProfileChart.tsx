import React, { useMemo, useState } from 'react';
import type { OHLCVBar } from '../../../hooks/useCandles';

interface Props {
  symbol: string;
  candles?: OHLCVBar[];
  currentSpot?: number;
  poc?: number;
  vwap?: number;
}

const PERIOD_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'];

const PERIOD_COLORS: Record<string, string> = {
  A: '#2563eb',
  B: '#3b82f6',
  C: '#059669',
  D: '#10b981',
  E: '#d97706',
  F: '#f59e0b',
  G: '#7c3aed',
  H: '#8b5cf6',
  I: '#db2777',
  J: '#ec4899',
  K: '#0284c7',
  L: '#06b6d4',
  M: '#4b5563',
};

export function MarketProfileChart({ symbol, candles, currentSpot, poc: propPoc, vwap: propVwap }: Props) {
  const [hoveredBin, setHoveredBin] = useState<number | null>(null);

  const isIndex = symbol.toUpperCase().includes('NIFTY') || symbol.toUpperCase().includes('SENSEX') || symbol.toUpperCase().includes('BANK');
  const tickStep = isIndex ? (symbol.toUpperCase().includes('SENSEX') ? 20 : 10) : 2;

  // Process candles into TPO structure
  const profileData = useMemo(() => {
    let spot = currentSpot ?? (isIndex ? 24405 : 2500);
    let minPrice = spot * 0.992;
    let maxPrice = spot * 1.008;

    if (candles && candles.length > 5) {
      const recent = candles.slice(-75); // recent session bars
      const highs = recent.map((c) => c.high);
      const lows = recent.map((c) => c.low);
      minPrice = Math.min(...lows);
      maxPrice = Math.max(...highs);
      spot = recent[recent.length - 1].close;
    }

    // Align to tickStep
    const startBin = Math.floor(minPrice / tickStep) * tickStep;
    const endBin = Math.ceil(maxPrice / tickStep) * tickStep;
    const binCount = Math.max(12, Math.min(45, Math.round((endBin - startBin) / tickStep)));

    const bins: {
      price: number;
      letters: string[];
      isIb: boolean;
      isPoc: boolean;
      inVa: boolean;
      isSinglePrint: boolean;
    }[] = [];

    for (let i = 0; i <= binCount; i++) {
      const p = startBin + i * tickStep;
      bins.push({
        price: p,
        letters: [],
        isIb: false,
        isPoc: false,
        inVa: false,
        isSinglePrint: false,
      });
    }

    if (candles && candles.length > 10) {
      const recent = candles.slice(-75);
      recent.forEach((bar, bIdx) => {
        const periodIdx = Math.min(PERIOD_LETTERS.length - 1, Math.floor(bIdx / 6)); // 6 bars of 5m = 30m period
        const letter = PERIOD_LETTERS[periodIdx];
        bins.forEach((b) => {
          if (b.price >= bar.low && b.price <= bar.high) {
            if (!b.letters.includes(letter)) {
              b.letters.push(letter);
            }
          }
        });
      });
    } else {
      // Synthetic realistic session distribution around POC
      const centerPrice = propPoc ?? spot;
      bins.forEach((b) => {
        const dist = Math.abs(b.price - centerPrice) / (tickStep * 4);
        const prob = Math.max(0, 1 - dist * 0.22);
        PERIOD_LETTERS.forEach((letter, lIdx) => {
          if (lIdx < 2 && Math.abs(b.price - (centerPrice - tickStep * 2)) < tickStep * 8) {
            b.letters.push(letter); // Initial balance range
          } else if (Math.random() < prob * (1 - lIdx * 0.05)) {
            b.letters.push(letter);
          }
        });
      });
    }

    // Initial Balance (A & B periods)
    let ibHigh = -Infinity;
    let ibLow = Infinity;
    bins.forEach((b) => {
      if (b.letters.includes('A') || b.letters.includes('B')) {
        b.isIb = true;
        if (b.price > ibHigh) ibHigh = b.price;
        if (b.price < ibLow) ibLow = b.price;
      }
    });

    // POC calculation (bin with max letters)
    let maxLetters = 0;
    let pocPrice = bins[Math.floor(bins.length / 2)]?.price ?? spot;
    bins.forEach((b) => {
      if (b.letters.length > maxLetters) {
        maxLetters = b.letters.length;
        pocPrice = b.price;
      }
    });

    bins.forEach((b) => {
      if (b.price === pocPrice) {
        b.isPoc = true;
      }
    });

    // Value Area calculation (70% total TPOs expanding outward from POC)
    const totalTpos = bins.reduce((sum, b) => sum + b.letters.length, 0);
    const targetVaTpos = Math.floor(totalTpos * 0.7);
    let currentVaTpos = 0;
    const pocIdx = bins.findIndex((b) => b.isPoc);

    let up = pocIdx;
    let down = pocIdx;
    if (pocIdx >= 0) {
      bins[pocIdx].inVa = true;
      currentVaTpos += bins[pocIdx].letters.length;

      while (currentVaTpos < targetVaTpos && (up < bins.length - 1 || down > 0)) {
        const nextUpCount = up < bins.length - 1 ? bins[up + 1].letters.length : 0;
        const nextDownCount = down > 0 ? bins[down - 1].letters.length : 0;

        if (nextUpCount >= nextDownCount && up < bins.length - 1) {
          up++;
          bins[up].inVa = true;
          currentVaTpos += bins[up].letters.length;
        } else if (down > 0) {
          down--;
          bins[down].inVa = true;
          currentVaTpos += bins[down].letters.length;
        } else if (up < bins.length - 1) {
          up++;
          bins[up].inVa = true;
          currentVaTpos += bins[up].letters.length;
        } else {
          break;
        }
      }
    }

    const vaHigh = up >= 0 && bins[up] ? bins[up].price : maxPrice;
    const vaLow = down >= 0 && bins[down] ? bins[down].price : minPrice;

    // Single prints (excess tails)
    bins.forEach((b) => {
      if (b.letters.length === 1 && !b.inVa && (b.price > vaHigh || b.price < vaLow)) {
        b.isSinglePrint = true;
      }
    });

    return {
      bins: bins.filter((b) => b.letters.length > 0),
      ibHigh: ibHigh === -Infinity ? null : ibHigh,
      ibLow: ibLow === Infinity ? null : ibLow,
      pocPrice,
      vaHigh,
      vaLow,
      spot,
      maxLetters: Math.max(1, maxLetters),
    };
  }, [candles, currentSpot, propPoc, isIndex, tickStep]);

  const { bins, ibHigh, ibLow, pocPrice, vaHigh, vaLow, spot, maxLetters } = profileData;

  // Day type calculation
  const dayType = useMemo(() => {
    if (!ibHigh || !ibLow) return 'Normal Variation Day';
    const rangeAboveIb = bins.filter((b) => b.price > ibHigh).length;
    const rangeBelowIb = bins.filter((b) => b.price < ibLow).length;
    if (rangeAboveIb > 6 && rangeBelowIb === 0) return 'Trend Day (Bullish Extension)';
    if (rangeBelowIb > 6 && rangeAboveIb === 0) return 'Trend Day (Bearish Extension)';
    if (rangeAboveIb > 0 && rangeBelowIb > 0) return 'Neutral Day (Two-Sided Auction)';
    if (rangeAboveIb > 0) return 'Normal Variation Day (Upward Extension)';
    if (rangeBelowIb > 0) return 'Normal Variation Day (Downward Extension)';
    return 'Normal Day (Contained within Initial Balance)';
  }, [bins, ibHigh, ibLow]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      {/* Header Info Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '8px 12px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>
            {symbol} Market Profile (TPO)
          </span>
          <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: 'rgba(37,99,235,.1)', color: '#2563eb' }}>
            {dayType}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
          <span><strong>VAH:</strong> ₹{vaHigh.toLocaleString('en-IN')}</span>
          <span style={{ color: '#7c3aed', fontWeight: 700 }}><strong>POC:</strong> ₹{pocPrice.toLocaleString('en-IN')}</span>
          <span><strong>VAL:</strong> ₹{vaLow.toLocaleString('en-IN')}</span>
          {ibHigh != null && ibLow != null && (
            <span style={{ color: '#2563eb' }}><strong>IB:</strong> ₹{ibLow.toLocaleString('en-IN')}–{ibHigh.toLocaleString('en-IN')}</span>
          )}
        </div>
      </div>

      {/* Main TPO Profile Chart Matrix */}
      <div style={{ flex: 1, minHeight: 320, overflow: 'auto', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
          {bins.map((b) => {
            const isHovered = hoveredBin === b.price;
            const isAtSpot = Math.abs(b.price - spot) < tickStep;

            return (
              <div
                key={b.price}
                onMouseEnter={() => setHoveredBin(b.price)}
                onMouseLeave={() => setHoveredBin(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '2px 4px',
                  borderRadius: 3,
                  background: isHovered
                    ? 'rgba(37,99,235,.1)'
                    : b.isPoc
                    ? 'rgba(124,58,237,.14)'
                    : b.inVa
                    ? 'rgba(124,58,237,.03)'
                    : b.isSinglePrint
                    ? 'rgba(239,68,68,.08)'
                    : 'transparent',
                  borderLeft: b.isPoc
                    ? '3px solid #7c3aed'
                    : isAtSpot
                    ? '3px solid #10b981'
                    : b.isIb
                    ? '3px solid #3b82f6'
                    : '3px solid transparent',
                  cursor: 'pointer',
                  transition: 'background 0.1s ease',
                }}
              >
                {/* Price Label Column */}
                <div
                  style={{
                    width: 75,
                    fontSize: 11,
                    fontWeight: b.isPoc || isAtSpot ? 750 : 600,
                    color: b.isPoc ? '#7c3aed' : isAtSpot ? '#059669' : b.inVa ? '#1e293b' : '#64748b',
                    fontVariantNumeric: 'tabular-nums',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>{b.price.toLocaleString('en-IN')}</span>
                  {b.isPoc && (
                    <span style={{ fontSize: 8.5, padding: '1px 3px', borderRadius: 2, background: '#7c3aed', color: '#fff', fontWeight: 800 }}>
                      POC
                    </span>
                  )}
                  {isAtSpot && (
                    <span style={{ fontSize: 8.5, padding: '1px 3px', borderRadius: 2, background: '#059669', color: '#fff', fontWeight: 800 }}>
                      LTP
                    </span>
                  )}
                </div>

                {/* TPO Letters String Matrix */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 3, flex: 1, paddingLeft: 8 }}>
                  {b.letters.map((char, cIdx) => (
                    <span
                      key={`${char}-${cIdx}`}
                      style={{
                        fontFamily: 'monospace',
                        fontSize: 11,
                        fontWeight: 700,
                        color: PERIOD_COLORS[char] || '#4b5563',
                        minWidth: 12,
                        textAlign: 'center',
                      }}
                    >
                      {char}
                    </span>
                  ))}

                  {/* Single Print Rejection Alert */}
                  {b.isSinglePrint && (
                    <span style={{ fontSize: 9.5, fontWeight: 700, color: '#dc2626', marginLeft: 8 }}>
                      ⚡ Excess / Single Print (Rejection Tail)
                    </span>
                  )}
                </div>

                {/* TPO Bar Length Meter */}
                <div
                  style={{
                    width: 60,
                    fontSize: 10,
                    color: '#94a3b8',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {b.letters.length} TPO{b.letters.length === 1 ? '' : 's'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Period Legend Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', background: '#f8fafc', borderRadius: 6, border: '1px solid #e2e8f0', fontSize: 10.5, color: '#64748b', flexWrap: 'wrap', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <strong style={{ color: '#1e293b' }}>30-Min Periods:</strong>
          {PERIOD_LETTERS.map((p, idx) => (
            <span key={p} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
              <strong style={{ color: PERIOD_COLORS[p] }}>{p}</strong>
              <span style={{ fontSize: 9.5, opacity: 0.8 }}>({9 + Math.floor(idx / 2)}:{idx % 2 === 0 ? '15' : '45'})</span>
            </span>
          ))}
        </div>
        <div>
          <span style={{ color: '#2563eb', fontWeight: 650 }}>■ Initial Balance (A+B)</span>
          <span style={{ margin: '0 6px' }}>·</span>
          <span style={{ color: '#7c3aed', fontWeight: 650 }}>■ Value Area (70%)</span>
        </div>
      </div>
    </div>
  );
}
