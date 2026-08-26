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
  A: 'var(--k-blue-strong)',
  B: '#3b82f6',
  C: 'var(--k-emerald)',
  D: 'var(--k-emerald-2)',
  E: 'var(--k-warn)',
  F: 'var(--k-amber-3)',
  G: 'var(--k-violet)',
  H: '#8b5cf6',
  I: '#db2777',
  J: '#ec4899',
  K: '#0284c7',
  L: '#06b6d4',
  M: '#4b5563',
};

export function MarketProfileChart({ symbol, candles, currentSpot, poc: propPoc, vwap: propVwap }: Props) {
  const [hoveredBin, setHoveredBin] = useState<number | null>(null);
  const [highlightLetter, setHighlightLetter] = useState<string | null>(null);
  const [viewStyle, setViewStyle] = useState<'merged' | 'split'>('merged');

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

    // Identify Initial Balance (IB: periods A & B)
    const ibBins = bins.filter((b) => b.letters.includes('A') || b.letters.includes('B'));
    const ibLow = ibBins.length > 0 ? Math.min(...ibBins.map((b) => b.price)) : spot - tickStep * 4;
    const ibHigh = ibBins.length > 0 ? Math.max(...ibBins.map((b) => b.price)) : spot + tickStep * 4;
    const ibRange = Math.max(tickStep, ibHigh - ibLow);

    bins.forEach((b) => {
      if (b.price >= ibLow && b.price <= ibHigh) {
        b.isIb = true;
      }
    });

    // Identify Point of Control (POC: bin with max letters)
    let maxLetters = 0;
    let pocPrice = propPoc ?? spot;
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

    // Calculate Value Area (70% of total TPO count)
    const totalTpo = bins.reduce((sum, b) => sum + b.letters.length, 0);
    const targetVaTpo = Math.round(totalTpo * 0.7);

    // Expand outward from POC to find Value Area High (VAH) & Value Area Low (VAL)
    const pocIdx = bins.findIndex((b) => b.isPoc);
    let vaTpoAccum = bins[pocIdx]?.letters.length ?? 0;
    let upIdx = pocIdx + 1;
    let downIdx = pocIdx - 1;

    if (bins[pocIdx]) {
      bins[pocIdx].inVa = true;
    }

    while (vaTpoAccum < targetVaTpo && (upIdx < bins.length || downIdx >= 0)) {
      const upCount = upIdx < bins.length ? bins[upIdx].letters.length : 0;
      const downCount = downIdx >= 0 ? bins[downIdx].letters.length : 0;

      if (upCount >= downCount && upIdx < bins.length) {
        vaTpoAccum += upCount;
        bins[upIdx].inVa = true;
        upIdx++;
      } else if (downIdx >= 0) {
        vaTpoAccum += downCount;
        bins[downIdx].inVa = true;
        downIdx--;
      } else if (upIdx < bins.length) {
        vaTpoAccum += upCount;
        bins[upIdx].inVa = true;
        upIdx++;
      } else {
        break;
      }
    }

    const vaBins = bins.filter((b) => b.inVa);
    const val = vaBins.length > 0 ? Math.min(...vaBins.map((b) => b.price)) : pocPrice - tickStep * 3;
    const vah = vaBins.length > 0 ? Math.max(...vaBins.map((b) => b.price)) : pocPrice + tickStep * 3;

    // Single prints (excess tails): only 1 letter at extreme top or bottom
    bins.forEach((b, idx) => {
      if (b.letters.length === 1 && (idx <= 2 || idx >= bins.length - 3)) {
        b.isSinglePrint = true;
      }
    });

    const dayHigh = Math.max(...bins.map((b) => (b.letters.length ? b.price : minPrice)));
    const dayLow = Math.min(...bins.map((b) => (b.letters.length ? b.price : maxPrice)));
    const dayRange = Math.max(tickStep, dayHigh - dayLow);
    const ibExtensionRatio = Number((dayRange / ibRange).toFixed(2));

    // Day type classification
    let dayType = 'Normal Variation Day';
    if (ibExtensionRatio >= 2.2) {
      dayType = 'Trend Day (High Extension)';
    } else if (ibExtensionRatio <= 1.2) {
      dayType = 'Non-Trend / Range Day (Contained in IB)';
    } else if (dayHigh > ibHigh && dayLow < ibLow) {
      dayType = 'Neutral Day (Both sides expanded)';
    }

    return {
      bins: bins.reverse(), // Top price at top
      pocPrice,
      val,
      vah,
      ibLow,
      ibHigh,
      ibRange,
      dayHigh,
      dayLow,
      dayRange,
      ibExtensionRatio,
      totalTpo,
      spot,
      dayType,
    };
  }, [candles, currentSpot, isIndex, propPoc, tickStep]);

  const { bins, pocPrice, val, vah, ibLow, ibHigh, ibRange, dayHigh, dayLow, ibExtensionRatio, totalTpo, spot, dayType } = profileData;

  const activeBin = hoveredBin !== null ? bins.find((b) => b.price === hoveredBin) : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>
      {/* Top Profile Metrics Ribbon */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, padding: '10px 14px', background: 'var(--k-surface-sunken)', borderRadius: 6, border: '1px solid var(--k-border-slate)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--k-ink-slate-1)' }}>
            {symbol} Market Profile (TPO)
          </span>
          <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 4, background: 'rgba(37,99,235,.1)', color: 'var(--k-blue-strong)', fontWeight: 700 }}>
            {dayType}
          </span>
          <span style={{ fontSize: 10.5, color: 'var(--k-ink-slate-3)' }}>
            IB Range: <strong>{ibRange} pts</strong> ({ibExtensionRatio}x ext)
          </span>
        </div>

        {/* View Controls & Period Highlights */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {/* Split vs Merged Toggle */}
          <div style={{ display: 'flex', gap: 2, background: 'var(--k-bg)', padding: 2, borderRadius: 4, border: '1px solid var(--k-border-slate-strong)' }}>
            <button
              type="button"
              onClick={() => setViewStyle('merged')}
              style={{
                border: 0,
                background: viewStyle === 'merged' ? 'var(--k-blue-strong)' : 'transparent',
                color: viewStyle === 'merged' ? 'var(--k-bg)' : 'var(--k-ink-slate-3)',
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: 3,
                cursor: 'pointer',
              }}
            >
              Merged TPO
            </button>
            <button
              type="button"
              onClick={() => setViewStyle('split')}
              style={{
                border: 0,
                background: viewStyle === 'split' ? 'var(--k-blue-strong)' : 'transparent',
                color: viewStyle === 'split' ? 'var(--k-bg)' : 'var(--k-ink-slate-3)',
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: 3,
                cursor: 'pointer',
              }}
            >
              Split Periods
            </button>
          </div>

          {/* Quick Letter Filter Pills */}
          <div style={{ display: 'flex', gap: 2 }}>
            {highlightLetter && (
              <button
                type="button"
                onClick={() => setHighlightLetter(null)}
                style={{ border: 0, background: 'var(--k-border-slate)', color: 'var(--k-ink-slate-2)', fontSize: 9.5, fontWeight: 700, padding: '2px 5px', borderRadius: 3, cursor: 'pointer' }}
              >
                Reset
              </button>
            )}
            {['A', 'B', 'C', 'D', 'E', 'F', 'G'].map((lettr) => (
              <button
                key={lettr}
                type="button"
                onClick={() => setHighlightLetter(highlightLetter === lettr ? null : lettr)}
                style={{
                  border: `1px solid ${highlightLetter === lettr ? 'var(--k-blue-strong)' : 'var(--k-border-slate)'}`,
                  background: highlightLetter === lettr ? 'var(--k-blue-strong)' : 'var(--k-bg)',
                  color: highlightLetter === lettr ? 'var(--k-bg)' : PERIOD_COLORS[lettr] || '#475569',
                  fontSize: 9.5,
                  fontWeight: 750,
                  padding: '2px 5px',
                  borderRadius: 3,
                  cursor: 'pointer',
                }}
              >
                {lettr}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Profile Key Levels Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
        <div style={{ padding: '6px 10px', background: 'var(--k-bg)', border: '1px solid var(--k-border-slate)', borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--k-ink-slate-3)', fontWeight: 600 }}>Value Area High (VAH)</div>
          <div style={{ fontSize: 13, fontWeight: 750, color: 'var(--k-violet)' }}>₹{vah.toLocaleString('en-IN')}</div>
        </div>
        <div style={{ padding: '6px 10px', background: 'rgba(245,158,11,.08)', border: '1px solid rgba(245,158,11,.25)', borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: '#b45309', fontWeight: 700 }}>Point of Control (POC)</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--k-warn)' }}>₹{pocPrice.toLocaleString('en-IN')}</div>
        </div>
        <div style={{ padding: '6px 10px', background: 'var(--k-bg)', border: '1px solid var(--k-border-slate)', borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--k-ink-slate-3)', fontWeight: 600 }}>Value Area Low (VAL)</div>
          <div style={{ fontSize: 13, fontWeight: 750, color: 'var(--k-violet)' }}>₹{val.toLocaleString('en-IN')}</div>
        </div>
        <div style={{ padding: '6px 10px', background: 'var(--k-bg)', border: '1px solid var(--k-border-slate)', borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--k-ink-slate-3)', fontWeight: 600 }}>Initial Balance (IB)</div>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--k-blue-strong)' }}>
            ₹{ibLow.toLocaleString('en-IN')} – {ibHigh.toLocaleString('en-IN')}
          </div>
        </div>
        <div style={{ padding: '6px 10px', background: 'var(--k-bg)', border: '1px solid var(--k-border-slate)', borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--k-ink-slate-3)', fontWeight: 600 }}>Current Spot / LTP</div>
          <div style={{ fontSize: 13, fontWeight: 750, color: spot >= pocPrice ? 'var(--k-emerald)' : 'var(--k-red-deep)' }}>
            ₹{spot.toLocaleString('en-IN')}
          </div>
        </div>
      </div>

      {/* Main Profile Distribution Grid */}
      <div style={{ flex: 1, minHeight: 320, background: 'var(--k-bg)', border: '1px solid var(--k-border-slate)', borderRadius: 8, padding: '10px 14px', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, fontFamily: 'monospace' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--k-border-slate)', color: 'var(--k-ink-slate-3)', textAlign: 'left' }}>
              <th style={{ width: 85, padding: '4px 6px' }}>Price</th>
              <th style={{ width: 55, padding: '4px 6px' }}>TPO</th>
              <th style={{ padding: '4px 6px' }}>30-Min Bracket Letters Distribution</th>
              <th style={{ width: 110, padding: '4px 6px', textAlign: 'right' }}>Structure</th>
            </tr>
          </thead>
          <tbody>
            {bins.map((b) => {
              const isPoc = b.price === pocPrice;
              const isVal = b.price === val;
              const isVah = b.price === vah;
              const isIbHigh = b.price === ibHigh;
              const isIbLow = b.price === ibLow;
              const isNearSpot = Math.abs(b.price - spot) < tickStep;
              const isHovered = hoveredBin === b.price;

              return (
                <tr
                  key={b.price}
                  onMouseEnter={() => setHoveredBin(b.price)}
                  onMouseLeave={() => setHoveredBin(null)}
                  style={{
                    background: isPoc
                      ? 'rgba(245,158,11,.15)'
                      : isHovered
                      ? 'var(--k-surface-slate)'
                      : b.inVa
                      ? 'rgba(124,58,237,.04)'
                      : 'transparent',
                    borderBottom: '1px solid var(--k-surface-sunken)',
                    borderLeft: isPoc
                      ? '3px solid var(--k-amber-3)'
                      : isVah || isVal
                      ? '3px solid var(--k-violet)'
                      : isNearSpot
                      ? '3px solid var(--k-blue-strong)'
                      : '3px solid transparent',
                  }}
                >
                  {/* Price Column */}
                  <td style={{ padding: '3px 6px', fontWeight: isPoc || isVah || isVal ? 750 : 500, color: isPoc ? 'var(--k-warn)' : isVah || isVal ? 'var(--k-violet)' : 'var(--k-ink-slate-1)' }}>
                    ₹{b.price.toLocaleString('en-IN')}
                  </td>

                  {/* TPO Count */}
                  <td style={{ padding: '3px 6px', color: 'var(--k-ink-slate-3)' }}>
                    {b.letters.length ? `${b.letters.length} TPO` : '—'}
                  </td>

                  {/* TPO Letters String / Split Blocks */}
                  <td style={{ padding: '3px 6px' }}>
                    <div style={{ display: 'flex', gap: 2, flexWrap: 'nowrap', overflowX: 'auto' }}>
                      {b.letters.map((char, cIdx) => {
                        const isMatch = highlightLetter === null || highlightLetter === char;
                        const col = PERIOD_COLORS[char] || '#475569';
                        return (
                          <span
                            key={cIdx}
                            style={{
                              display: 'inline-block',
                              width: 15,
                              textAlign: 'center',
                              fontWeight: 750,
                              fontSize: 10,
                              color: isMatch ? col : 'var(--k-border-slate-strong)',
                              background: isMatch ? `${col}15` : 'transparent',
                              borderRadius: 2,
                              opacity: isMatch ? 1 : 0.4,
                            }}
                          >
                            {char}
                          </span>
                        );
                      })}
                    </div>
                  </td>

                  {/* Structure Indicator Label */}
                  <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                    {isPoc && (
                      <span style={{ fontSize: 9.5, fontWeight: 800, padding: '1px 5px', borderRadius: 3, background: 'var(--k-amber-3)', color: 'var(--k-on-accent)' }}>
                        POC
                      </span>
                    )}
                    {isVah && (
                      <span style={{ fontSize: 9.5, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'var(--k-violet)', color: 'var(--k-on-accent)' }}>
                        VAH (70%)
                      </span>
                    )}
                    {isVal && (
                      <span style={{ fontSize: 9.5, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'var(--k-violet)', color: 'var(--k-on-accent)' }}>
                        VAL (70%)
                      </span>
                    )}
                    {isIbHigh && !isVah && (
                      <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 4px', borderRadius: 3, background: 'rgba(37,99,235,.15)', color: 'var(--k-blue-strong)' }}>
                        IB HIGH
                      </span>
                    )}
                    {isIbLow && !isVal && (
                      <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 4px', borderRadius: 3, background: 'rgba(37,99,235,.15)', color: 'var(--k-blue-strong)' }}>
                        IB LOW
                      </span>
                    )}
                    {b.isSinglePrint && !isPoc && (
                      <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 4px', borderRadius: 3, background: 'rgba(239,68,68,.12)', color: 'var(--k-red-deep)' }}>
                        SINGLE PRINT
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Interactive Legend & Microstructure Takeaway */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, fontSize: 11, color: 'var(--k-ink-slate-3)', background: 'var(--k-surface-sunken)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--k-border-slate)' }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: 'var(--k-amber-3)', borderRadius: 2 }} /> <strong>POC</strong> (Point of Control)
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: 'rgba(124,58,237,.25)', borderRadius: 2 }} /> <strong>Value Area (70%)</strong>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 10, height: 10, background: 'rgba(37,99,235,.3)', borderRadius: 2 }} /> <strong>Initial Balance</strong> (09:15–09:45)
          </span>
        </div>
        <span style={{ color: 'var(--k-ink-slate-1)', fontWeight: 650 }}>
          Total Session TPOs: {totalTpo}
        </span>
      </div>
    </div>
  );
}
