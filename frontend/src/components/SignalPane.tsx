import React from 'react';
import { useSnapshot } from '../hooks/useSnapshot';

interface Props {
  underlying: string;
}

function MiniBar({ value, max, color = 'var(--t-blue)' }: { value: number; max: number; color?: string }) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  return (
    <div style={{ flex: 1, height: 4, background: 'var(--t-border)', borderRadius: 2 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
    </div>
  );
}

const REGIME_COLORS: Record<string, string> = {
  BULL_TREND: '#00c87a',
  BEAR_TREND: '#f03050',
  VOLATILE:   '#f0a020',
  RANGING:    '#4a5a6a',
  IDLE:       '#4a5a6a',
};

export function SignalPane({ underlying }: Props) {
  const { data: snap } = useSnapshot(underlying);

  if (!snap) {
    return (
      <div style={{ padding: 12, color: 'var(--t-dim)', fontSize: 11 }}>
        Loading {underlying}…
      </div>
    );
  }

  const regime = snap.macro_regime ?? 'RANGING';
  const regimeColor = REGIME_COLORS[regime] ?? 'var(--t-dim)';

  const bd = snap.score_breakdown ?? {};
  const totalScore = snap.score_long > snap.score_short ? snap.score_long : snap.score_short;
  const tradeLabel = totalScore >= 85 ? 'TRADE' : totalScore >= 75 ? 'MONITOR' : 'WAIT';
  const tradeColor = totalScore >= 85 ? 'var(--t-green)' : totalScore >= 75 ? 'var(--t-amber)' : 'var(--t-dim)';

  const atrPct = snap.atr_percentile ?? 50;
  const adx = snap.adx ?? 0;
  const adxBar = Math.min((adx / 50) * 100, 100);
  const adxColor = adx >= 25 ? 'var(--t-green)' : 'var(--t-dim)';
  const adxLabel = adx >= 25 ? 'TRENDING' : 'WEAK';
  const atrColor = atrPct > 65 ? 'var(--t-amber)' : atrPct > 40 ? 'var(--t-blue)' : 'var(--t-dim)';

  const scoreRows: { label: string; key: string; max: number }[] = [
    { label: 'Macro Trend', key: 'macro_trend', max: 20 },
    { label: 'Signal',      key: 'signal',      max: 20 },
    { label: 'Entry Timing', key: 'entry',      max: 15 },
    { label: 'Contract',    key: 'contract_health', max: 20 },
    { label: 'DTE',         key: 'dte',         max: 10 },
    { label: 'Risk/Reward', key: 'rr',          max: 15 },
  ];

  const stTrends = snap.st_trends ?? [];
  const ST_LABELS = ['ST(7,3)', 'ST(14,2)', 'ST(21,1)'];
  const isArmed = snap.state?.includes('ARMED');

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--t-bright)', fontWeight: 700, letterSpacing: 1, fontSize: 13 }}>
          [{underlying}]
        </span>
        <span
          className="tag"
          style={{ background: regimeColor + '22', color: regimeColor, border: `1px solid ${regimeColor}44` }}
        >
          {regime}
        </span>
        {snap.direction && snap.direction !== 'neutral' && (
          <span
            className="tag"
            style={{ background: 'var(--t-bg3)', color: snap.direction === 'long' ? 'var(--t-green)' : 'var(--t-red)' }}
          >
            {snap.direction.toUpperCase()}
          </span>
        )}
      </div>

      {/* ATR percentile */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>ATR {Math.round(atrPct)}pct</span>
          {atrPct > 65 && <span style={{ color: 'var(--t-amber)', fontSize: 10 }}>HIGH VOL</span>}
        </div>
        <MiniBar value={atrPct} max={100} color={atrColor} />
      </div>

      {/* ADX gauge */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>ADX {Math.round(adx)}</span>
          <span className="tag" style={{ background: 'var(--t-bg3)', color: adxColor }}>{adxLabel}</span>
        </div>
        <MiniBar value={adxBar} max={100} color={adxColor} />
      </div>

      {/* Score waterfall */}
      <div style={{ borderTop: '1px solid var(--t-border)', paddingTop: 8 }}>
        {scoreRows.map(({ label, key, max }) => {
          const v = typeof bd[key] === 'number' ? (bd[key] as number) : null;
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
              <span style={{ color: 'var(--t-dim)', width: 88, flexShrink: 0, fontSize: 10 }}>{label}</span>
              {v !== null ? <MiniBar value={v} max={max} /> : (
                <div style={{ flex: 1, height: 4, background: 'var(--t-border)', borderRadius: 2 }} />
              )}
              <span className="num" style={{ color: 'var(--t-text)', width: 34, textAlign: 'right', fontSize: 10, flexShrink: 0 }}>
                {v !== null ? `${v}/${max}` : '--'}
              </span>
            </div>
          );
        })}

        {/* Veto reason */}
        {bd.veto_reason && (
          <div style={{ color: 'var(--t-red)', fontSize: 10, marginBottom: 4 }}>
            ✕ {bd.veto_reason}
          </div>
        )}

        {/* Total */}
        <div style={{
          borderTop: '1px solid var(--t-border)', marginTop: 4, paddingTop: 6,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>TOTAL</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="num" style={{ color: tradeColor, fontWeight: 700, fontSize: 13 }}>{totalScore}/100</span>
            <span className="tag" style={{ background: tradeColor + '22', color: tradeColor, border: `1px solid ${tradeColor}44` }}>
              {tradeLabel}
            </span>
          </div>
        </div>
      </div>

      {/* State badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {isArmed && (
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: 'var(--t-amber)',
            display: 'inline-block', animation: 't-blink 1s infinite',
          }} />
        )}
        <span
          className="tag"
          style={{
            background: 'var(--t-bg3)',
            color: isArmed ? 'var(--t-amber)' : 'var(--t-dim)',
            border: `1px solid ${isArmed ? 'var(--t-amber)44' : 'var(--t-border)'}`,
          }}
        >
          {snap.state || 'IDLE'}
        </span>
      </div>

      {/* SuperTrend status */}
      {stTrends.length > 0 && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {stTrends.map((t, i) => (
            <span key={i} style={{ fontSize: 10, color: 'var(--t-text)' }}>
              {ST_LABELS[i] ?? `ST${i + 1}`}{' '}
              <span style={{ color: t > 0 ? 'var(--t-green)' : 'var(--t-red)' }}>●</span>
            </span>
          ))}
        </div>
      )}

      {/* RSI / funding footer */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 'auto', paddingTop: 8, borderTop: '1px solid var(--t-border)' }}>
        {snap.rsi != null && (
          <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
            RSI <span className="num" style={{ color: 'var(--t-text)' }}>{snap.rsi.toFixed(0)}</span>
          </span>
        )}
        {snap.ivr != null && (
          <span style={{ fontSize: 10, color: 'var(--t-dim)' }}>
            IVR <span className="num" style={{ color: 'var(--t-text)' }}>{snap.ivr.toFixed(1)}</span>
          </span>
        )}
        {snap.funding_rate != null && (
          <span style={{ fontSize: 10, color: Math.abs(snap.funding_rate) > 0.025 ? 'var(--t-red)' : 'var(--t-dim)' }}>
            Fund <span className="num">{(snap.funding_rate * 100).toFixed(4)}%</span>
          </span>
        )}
      </div>
    </div>
  );
}
