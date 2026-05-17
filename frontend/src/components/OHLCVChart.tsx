/**
 * OHLCVChart — SVG candlestick chart driven by the stored Delta Exchange data.
 * Shows OHLCV bars for BTCUSD (or any symbol) at selectable timeframes.
 * Data is pre-fetched by the backend and cached in SQLite; no live exchange calls.
 */
import React, { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useOhlcv, useOhlcvStatus, useTriggerOhlcvFetch,
  OHLCV_RESOLUTIONS, type OhlcvCandle, type OhlcvResolution,
} from '../hooks/useOhlcv';
import { api } from '../utils/api';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtPrice(p: number) {
  if (p >= 10000) return p.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (p >= 100)   return p.toLocaleString('en-US', { maximumFractionDigits: 1 });
  return p.toLocaleString('en-US', { maximumFractionDigits: 3 });
}

function fmtDate(ts: number, resolution: string): string {
  const d = new Date(ts * 1000);
  if (resolution === '1d') return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  if (['4h', '2h', '1h'].includes(resolution))
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ── SVG candlestick chart ─────────────────────────────────────────────────────

interface ChartProps {
  candles: OhlcvCandle[];
  resolution: string;
  width?: number;
  height?: number;
}

function CandlestickChart({ candles, resolution, width = 900, height = 260 }: ChartProps) {
  const [hovered, setHovered] = useState<OhlcvCandle | null>(null);
  const PADDING = { top: 16, right: 60, bottom: 32, left: 12 };
  const VOL_H   = 40;
  const chartH  = height - PADDING.top - PADDING.bottom - VOL_H - 8;
  const chartW  = width  - PADDING.left - PADDING.right;

  const visible = useMemo(() => {
    // Show at most ~150 bars so wicks are legible
    return candles.slice(-150);
  }, [candles]);

  const { minLow, maxHigh, maxVol } = useMemo(() => ({
    minLow:  Math.min(...visible.map(c => c.low)),
    maxHigh: Math.max(...visible.map(c => c.high)),
    maxVol:  Math.max(...visible.map(c => c.volume), 1),
  }), [visible]);

  const priceRange = maxHigh - minLow || 1;
  const barW = Math.max(2, (chartW / visible.length) * 0.7);

  const toY = (price: number) =>
    PADDING.top + chartH - ((price - minLow) / priceRange) * chartH;

  // Y-axis price ticks
  const priceTicks = useMemo(() => {
    const count = 5;
    return Array.from({ length: count }, (_, i) => {
      const v = minLow + (priceRange * i) / (count - 1);
      return { v, y: toY(v) };
    });
  }, [minLow, priceRange, chartH]); // eslint-disable-line react-hooks/exhaustive-deps

  if (visible.length === 0) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--t-dim)', fontSize: 12,
      }}>
        No candle data — click "Fetch Data" to load
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      {/* Hover tooltip */}
      {hovered && (
        <div style={{
          position: 'absolute', top: 8, left: PADDING.left + 8, zIndex: 10,
          background: 'rgba(13,17,26,0.95)', border: '1px solid var(--t-border)',
          borderRadius: 6, padding: '7px 11px', fontSize: 10,
          color: 'var(--t-bright)', fontVariantNumeric: 'tabular-nums',
          pointerEvents: 'none',
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 16px',
        }}>
          <span style={{ color: 'var(--t-dim)', gridColumn: '1 / -1', marginBottom: 2, fontSize: 9 }}>
            {fmtDate(hovered.time, resolution)}
          </span>
          <span style={{ color: 'var(--t-dim)' }}>O</span>
          <span>{fmtPrice(hovered.open)}</span>
          <span style={{ color: 'var(--t-dim)' }}>H</span>
          <span style={{ color: '#10B981' }}>{fmtPrice(hovered.high)}</span>
          <span style={{ color: 'var(--t-dim)' }}>L</span>
          <span style={{ color: '#EF4444' }}>{fmtPrice(hovered.low)}</span>
          <span style={{ color: 'var(--t-dim)' }}>C</span>
          <span>{fmtPrice(hovered.close)}</span>
          <span style={{ color: 'var(--t-dim)' }}>Vol</span>
          <span>{hovered.volume.toFixed(2)}</span>
        </div>
      )}

      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: 'block', cursor: 'crosshair' }}
      >
        {/* Background grid */}
        {priceTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={PADDING.left} y1={tick.y}
              x2={width - PADDING.right} y2={tick.y}
              stroke="rgba(255,255,255,0.04)" strokeWidth="1"
            />
            <text
              x={width - PADDING.right + 6} y={tick.y + 4}
              fill="rgba(100,130,160,0.7)" fontSize="9"
            >
              {fmtPrice(tick.v)}
            </text>
          </g>
        ))}

        {/* Candles */}
        {visible.map((c, i) => {
          const x    = PADDING.left + (i / visible.length) * chartW + (chartW / visible.length) * 0.15;
          const isUp = c.close >= c.open;
          const col  = isUp ? '#10B981' : '#EF4444';
          const bodyTop    = toY(Math.max(c.open, c.close));
          const bodyBottom = toY(Math.min(c.open, c.close));
          const bodyH      = Math.max(1, bodyBottom - bodyTop);
          const xCenter    = x + barW / 2;

          // Volume bar
          const volY  = PADDING.top + chartH + 8;
          const volH  = (c.volume / maxVol) * VOL_H;

          return (
            <g
              key={c.time}
              onMouseEnter={() => setHovered(c)}
              onMouseLeave={() => setHovered(null)}
            >
              {/* High/Low wick */}
              <line
                x1={xCenter} y1={toY(c.high)}
                x2={xCenter} y2={toY(c.low)}
                stroke={col} strokeWidth="1" opacity="0.7"
              />
              {/* Body */}
              <rect
                x={x} y={bodyTop}
                width={barW} height={bodyH}
                fill={isUp ? col : col}
                opacity={isUp ? 0.85 : 0.75}
                rx="0.5"
              />
              {/* Volume */}
              <rect
                x={x} y={volY + VOL_H - volH}
                width={barW} height={volH}
                fill={col} opacity="0.3"
              />
            </g>
          );
        })}

        {/* X-axis time labels */}
        {visible.filter((_, i) => i % Math.ceil(visible.length / 8) === 0).map((c, i) => {
          const idx = visible.indexOf(c);
          const x   = PADDING.left + (idx / visible.length) * chartW + (chartW / visible.length) * 0.15;
          return (
            <text
              key={i}
              x={x} y={height - 6}
              fill="rgba(100,130,160,0.6)" fontSize="8"
              textAnchor="middle"
            >
              {fmtDate(c.time, resolution)}
            </text>
          );
        })}

        {/* Volume label */}
        <text
          x={PADDING.left + 2} y={PADDING.top + chartH + 12}
          fill="rgba(100,130,160,0.4)" fontSize="7" letterSpacing="1"
        >
          VOL
        </text>
      </svg>
    </div>
  );
}

// ── Coverage badge ────────────────────────────────────────────────────────────

function CoverageBadge({ symbol, resolution, count, earliest, latest }: {
  symbol: string; resolution: string; count: number;
  earliest: number | null; latest: number | null;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 2,
      padding: '5px 10px',
      background: 'var(--t-bg)',
      border: '1px solid var(--t-border)',
      borderRadius: 6,
      fontSize: 9,
    }}>
      <span style={{ fontWeight: 700, color: 'var(--t-dim)', letterSpacing: '0.08em' }}>
        {symbol} · {resolution.toUpperCase()}
      </span>
      <span style={{ color: count > 0 ? '#10B981' : 'var(--t-dim)', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
        {count.toLocaleString()} candles
      </span>
      <span style={{ color: 'rgba(100,130,160,0.5)' }}>
        {fmtTs(earliest)} → {fmtTs(latest)}
      </span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const SYMBOLS = ['BTCUSD', 'ETHUSD', 'SOLUSD', 'XRPUSD'] as const;

export function OHLCVChart() {
  const [symbol,     setSymbol]     = useState<string>('BTCUSD');
  const [resolution, setResolution] = useState<OhlcvResolution>('1h');
  const [limit,      setLimit]      = useState(300);
  const [fetching,   setFetching]   = useState(false);
  const [fetchMsg,   setFetchMsg]   = useState('');

  const qc      = useQueryClient();
  const trigger = useTriggerOhlcvFetch();

  const { data, isLoading } = useOhlcv(symbol, resolution, limit);
  const { data: status }    = useOhlcvStatus();

  const handleFetch = async (sym?: string) => {
    setFetching(true);
    setFetchMsg('Fetching from Delta Exchange…');
    try {
      const url = sym ? `/api/v1/ohlcv/fetch?symbol=${sym}` : '/api/v1/ohlcv/fetch';
      await api.post<{ status: string }>(url, {});
      setFetchMsg('Fetch started — data arrives in ~30–90 seconds');
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['ohlcv'] });
        qc.invalidateQueries({ queryKey: ['ohlcv-status'] });
        setFetchMsg('');
      }, 5000);
    } catch (e) {
      setFetchMsg(`Error: ${(e as Error).message}`);
    } finally {
      setFetching(false);
    }
  };

  const candles = data?.candles ?? [];

  const pill = (active: boolean): React.CSSProperties => ({
    padding: '4px 10px', borderRadius: 5, fontSize: 9, fontWeight: 600,
    letterSpacing: '0.06em', cursor: 'pointer', fontFamily: 'inherit',
    border: active ? '1px solid var(--t-blue)44' : '1px solid var(--t-border)',
    background: active ? 'var(--t-bg3)' : 'transparent',
    color: active ? 'var(--t-blue)' : 'var(--t-dim)',
    transition: 'all 0.1s',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>

      {/* ── Toolbar ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 14px',
        background: 'var(--t-bg2)',
        borderBottom: '1px solid var(--t-border)',
        flexWrap: 'wrap',
      }}>
        {/* Symbol selector */}
        <div style={{ display: 'flex', gap: 3 }}>
          {SYMBOLS.map(s => (
            <button key={s} onClick={() => setSymbol(s)} style={pill(symbol === s)}>{s}</button>
          ))}
        </div>

        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

        {/* Resolution selector */}
        <div style={{ display: 'flex', gap: 3 }}>
          {OHLCV_RESOLUTIONS.map(r => (
            <button key={r} onClick={() => setResolution(r)} style={pill(resolution === r)}>
              {r.toUpperCase()}
            </button>
          ))}
        </div>

        <div style={{ width: 1, height: 16, background: 'var(--t-border)' }} />

        {/* Bar count */}
        <div style={{ display: 'flex', gap: 3 }}>
          {[100, 300, 500].map(l => (
            <button key={l} onClick={() => setLimit(l)} style={pill(limit === l)}>{l}</button>
          ))}
        </div>

        {/* Fetch button + status */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {fetchMsg && (
            <span style={{ fontSize: 9, color: 'var(--t-amber)' }}>{fetchMsg}</span>
          )}
          {status?.is_fetching && (
            <span style={{ fontSize: 9, color: 'var(--t-amber)', animation: 't-blink 0.8s infinite' }}>
              ● Fetching…
            </span>
          )}
          <button
            onClick={() => handleFetch(symbol)}
            disabled={fetching || status?.is_fetching}
            style={{
              ...pill(false),
              color: 'var(--t-green)', borderColor: 'var(--t-green)44',
              opacity: (fetching || status?.is_fetching) ? 0.5 : 1,
            }}
          >
            ↺ Fetch {symbol}
          </button>
          <button
            onClick={() => handleFetch()}
            disabled={fetching || status?.is_fetching}
            style={{
              ...pill(false),
              color: 'var(--t-dim)',
              opacity: (fetching || status?.is_fetching) ? 0.5 : 1,
            }}
          >
            Fetch All
          </button>
        </div>
      </div>

      {/* ── Chart ── */}
      <div style={{
        background: 'var(--t-bg)',
        padding: '8px 14px',
        borderBottom: '1px solid var(--t-border)',
      }}>
        {/* Meta row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
            <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--t-bright)', letterSpacing: '0.04em' }}>
              {symbol}
            </span>
            <span style={{ fontSize: 9, color: 'var(--t-dim)', letterSpacing: '0.1em' }}>
              {resolution.toUpperCase()} · {candles.length} bars
            </span>
            {data?.earliest && (
              <span style={{ fontSize: 9, color: 'rgba(100,130,160,0.5)', fontVariantNumeric: 'tabular-nums' }}>
                {fmtTs(data.earliest)} → {fmtTs(data.latest)}
              </span>
            )}
          </div>
          {candles.length > 0 && (
            <div style={{ display: 'flex', gap: 14, fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
              {(() => {
                const last = candles[candles.length - 1];
                const prev = candles[candles.length - 2];
                const chg  = prev ? ((last.close - prev.close) / prev.close) * 100 : 0;
                return (
                  <>
                    <span style={{ color: 'var(--t-bright)', fontWeight: 700 }}>
                      ${fmtPrice(last.close)}
                    </span>
                    <span style={{ color: chg >= 0 ? '#10B981' : '#EF4444', fontWeight: 600 }}>
                      {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
                    </span>
                  </>
                );
              })()}
            </div>
          )}
        </div>

        {isLoading ? (
          <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--t-dim)', fontSize: 11 }}>
            Loading…
          </div>
        ) : (
          <CandlestickChart candles={candles} resolution={resolution} height={260} />
        )}
      </div>

      {/* ── Coverage grid ── */}
      {status && status.coverage.length > 0 && (
        <div style={{
          padding: '10px 14px',
          background: 'var(--t-bg2)',
        }}>
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--t-dim)', marginBottom: 8 }}>
            STORED DATA COVERAGE
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {status.coverage.map(c => (
              <CoverageBadge
                key={`${c.symbol}:${c.resolution}`}
                symbol={c.symbol}
                resolution={c.resolution}
                count={c.count}
                earliest={c.earliest}
                latest={c.latest}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
