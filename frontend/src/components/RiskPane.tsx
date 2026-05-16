import React from 'react';
import { useDrawdownBreaker, useResetDrawdownBreaker } from '../hooks/useDrawdownBreaker';
import { useGreeksBudget } from '../hooks/useGreeksBudget';
import { usePortfolioSummary } from '../hooks/usePortfolioSummary';
import { usePositions } from '../hooks/usePositions';
import { useAnalytics } from '../hooks/useAnalytics';
import { useQueryClient } from '@tanstack/react-query';

const STATE_COLORS: Record<string, { dot: string; text: string }> = {
  clear:   { dot: 'var(--t-dim)',   text: 'var(--t-dim)' },
  warning: { dot: 'var(--t-amber)', text: 'var(--t-amber)' },
  halt:    { dot: 'var(--t-red)',   text: 'var(--t-red)' },
  reset:   { dot: 'var(--t-red)',   text: 'var(--t-red)' },
};

function BudgetBar({ label, value, max, color = 'var(--t-blue)' }: {
  label: string; value: number; max: number; color?: string;
}) {
  const absPct = Math.min(Math.abs(value / max) * 100, 100);
  const exceed = Math.abs(value) > max;
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>{label}</span>
        <span className="num" style={{ fontSize: 10, color: exceed ? 'var(--t-red)' : 'var(--t-text)' }}>
          {(Math.abs(value) * 100).toFixed(0)}% / {(max * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ height: 4, background: 'var(--t-border)', borderRadius: 2 }}>
        <div style={{
          height: '100%', width: `${absPct}%`,
          background: exceed ? 'var(--t-red)' : color,
          borderRadius: 2,
          transition: 'width 0.3s',
        }} />
      </div>
    </div>
  );
}

export function RiskPane() {
  const { data: cb } = useDrawdownBreaker();
  const { data: greeks } = useGreeksBudget();
  const { data: summary } = usePortfolioSummary();
  const { data: posData } = usePositions();
  const { data: analytics } = useAnalytics();
  const { mutate: resetCb, isPending: resetting } = useResetDrawdownBreaker();
  const qc = useQueryClient();

  const cbState = cb?.state ?? 'clear';
  const cbColors = STATE_COLORS[cbState] ?? STATE_COLORS.clear;
  const isHalted = cbState === 'halt' || cbState === 'reset';

  const winRate = analytics?.win_rate_pct ?? 0;
  const totalPnl = summary?.total_realized_pnl_usd ?? 0;
  const pnlColor = totalPnl >= 0 ? 'var(--t-green)' : 'var(--t-red)';
  const ddPct = cb ? (Math.abs(cb.current_drawdown) * 100).toFixed(1) : '--';

  const positions = posData?.positions?.filter((p) => p.status === 'open') ?? [];
  const hasOptions = positions.some((p) =>
    p.sized_trade?.structure?.structure_type?.toLowerCase().includes('option') ||
    p.sized_trade?.structure?.structure_type?.toLowerCase().includes('spread') ||
    p.sized_trade?.structure?.structure_type?.toLowerCase().includes('naked')
  );

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Circuit breaker summary */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        padding: '6px 8px', background: 'var(--t-bg3)', borderRadius: 4,
        border: `1px solid ${isHalted ? 'var(--t-red)44' : 'var(--t-border)'}`,
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: cbColors.dot,
          display: 'inline-block', flexShrink: 0,
          animation: isHalted ? 't-blink 0.8s infinite' : undefined,
        }} />
        <span className="tag" style={{ color: cbColors.text, background: 'transparent' }}>
          {cbState.toUpperCase()}
        </span>
        {cb && (
          <>
            <span style={{ color: pnlColor, fontSize: 11 }} className="num">
              {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(0)} USD
            </span>
            <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>
              DD: <span className="num" style={{ color: isHalted ? 'var(--t-red)' : 'var(--t-text)' }}>{ddPct}%</span>
            </span>
            <span style={{ color: 'var(--t-dim)', fontSize: 10 }}>
              WR: <span className="num" style={{ color: 'var(--t-text)' }}>{winRate.toFixed(0)}%</span>
            </span>
          </>
        )}
        {cbState === 'reset' && (
          <button
            disabled={resetting}
            onClick={() => resetCb(undefined, { onSuccess: () => qc.invalidateQueries({ queryKey: ['dd-circuit-breaker'] }) })}
            style={{
              marginLeft: 'auto', background: 'var(--t-bg2)', color: 'var(--t-blue)',
              border: '1px solid var(--t-blue)', borderRadius: 3, padding: '2px 8px',
              cursor: 'pointer', fontFamily: 'inherit', fontSize: 10,
            }}
          >
            {resetting ? 'Resetting…' : 'Reset CB'}
          </button>
        )}
      </div>

      {/* Open positions micro-table */}
      <div>
        <div style={{ color: 'var(--t-dim)', fontSize: 10, marginBottom: 6, letterSpacing: 1 }}>
          POSITIONS ({positions.length})
        </div>
        {positions.length === 0 ? (
          <div style={{ color: 'var(--t-dim)', fontSize: 10, padding: '4px 0' }}>No open positions</div>
        ) : (
          <div style={{ maxHeight: 180, overflow: 'auto' }}>
            {positions.slice(0, 6).map((p) => {
              const dir = p.sized_trade?.structure?.direction ?? 'long';
              const pnl = p.realized_pnl_usd ?? 0;
              const risk = p.sized_trade?.max_risk_usd ?? 0;
              const pnlColor = pnl >= 0 ? 'var(--t-green)' : 'var(--t-red)';
              const dirColor = dir === 'long' ? 'var(--t-green)' : 'var(--t-red)';
              const structType = p.sized_trade?.structure?.structure_type ?? '';
              return (
                <div key={p.id} style={{
                  display: 'grid', gridTemplateColumns: '1fr auto auto auto',
                  gap: 6, padding: '4px 0', borderBottom: '1px solid var(--t-border)',
                  alignItems: 'center', fontSize: 10,
                }}>
                  <span style={{ color: 'var(--t-bright)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.underlying} {structType && <span style={{ color: 'var(--t-dim)' }}>{structType}</span>}
                  </span>
                  <span style={{ color: dirColor }}>{dir === 'long' ? 'L' : 'S'}</span>
                  <span className="num" style={{ color: pnlColor }}>
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}
                  </span>
                  <span style={{ color: 'var(--t-dim)', fontSize: 9 }}>
                    R:{risk.toFixed(0)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Greeks budget bars (options only) */}
      {greeks && hasOptions && (
        <div style={{ borderTop: '1px solid var(--t-border)', paddingTop: 8 }}>
          <div style={{ color: 'var(--t-dim)', fontSize: 10, marginBottom: 6, letterSpacing: 1 }}>GREEKS</div>
          <BudgetBar
            label="δ net delta"
            value={greeks.net_delta}
            max={greeks.budget.max_net_delta}
            color="var(--t-cyan)"
          />
          <BudgetBar
            label="ν net vega"
            value={greeks.net_vega}
            max={greeks.budget.max_net_vega}
            color="var(--t-purple)"
          />
          {!greeks.within_limits && (
            <div style={{ color: 'var(--t-red)', fontSize: 10, marginTop: 4 }}>
              ⚠ Greeks budget exceeded
            </div>
          )}
        </div>
      )}

      {/* Portfolio stats */}
      {summary && (
        <div style={{ borderTop: '1px solid var(--t-border)', paddingTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: 'var(--t-dim)', fontSize: 9, marginBottom: 2 }}>OPEN</div>
            <span className="num" style={{ color: 'var(--t-text)', fontSize: 11 }}>{summary.open_count}</span>
          </div>
          <div>
            <div style={{ color: 'var(--t-dim)', fontSize: 9, marginBottom: 2 }}>CLOSED</div>
            <span className="num" style={{ color: 'var(--t-text)', fontSize: 11 }}>{summary.closed_count}</span>
          </div>
          <div>
            <div style={{ color: 'var(--t-dim)', fontSize: 9, marginBottom: 2 }}>REALIZED P&L</div>
            <span className="num" style={{ color: pnlColor, fontSize: 11 }}>
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(0)}
            </span>
          </div>
          {analytics && (
            <div>
              <div style={{ color: 'var(--t-dim)', fontSize: 9, marginBottom: 2 }}>WIN RATE</div>
              <span className="num" style={{ color: 'var(--t-text)', fontSize: 11 }}>{winRate.toFixed(0)}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
