/**
 * CommonFuturesCandidatesTable — futures-only sibling of the signals table.
 *
 * Rendered after the signals SectionCard in every strategy tab. Each
 * row is one selector-decided futures candidate (with leverage, SL/TP,
 * funding cost, expected R). EXECUTE submits the row's freeze_token.
 *
 * When algo is ON AND the row's strategy profile has
 * `auto_execute_futures=true`, the BACKGROUND scanner fires this row
 * automatically — the FE renders an "AUTO" pill in that case so the
 * operator knows the human EXECUTE button is informational only.
 *
 * Columns: Underlying · Strategy · Lev · Contracts · Notional · SL · TP ·
 * Expected R · Funding · EXECUTE/AUTO.
 */
import React, { useState } from 'react';
import { card, cardHead, cardBody, alpha, c } from '../../styles/terminalUI';
import {
  useDerivativesFuturesCandidates,
  useDerivativesExecute,
  useDerivativesConfig,
  DerivativesCandidateRow,
} from '../../hooks/useDerivatives';
import { CommonSourceBadge, cleanStrategy } from './CommonSourceBadge';
import { useDerivativesPositionPnl } from '../../hooks/useDerivativesPositionPnl';
import { CommonDetailGrid } from './CommonDetailGrid';

const fmt = (v: number | null | undefined, d = 2): string =>
  v == null || !isFinite(v) ? '—' : v.toFixed(d);

const fmtUsd = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });

const fmtSigned = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : (v < 0 ? '-' : '+') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 2 });

interface Props {
  engine?: 'sterling' | 'grok';
  strategy?: string;
  underlying?: string;
}

export const CommonFuturesCandidatesTable: React.FC<Props> = ({ engine, strategy, underlying }) => {
  const { data, isLoading, refetch } = useDerivativesFuturesCandidates(strategy, underlying);
  const cfg = useDerivativesConfig();
  const execute = useDerivativesExecute();
  const pnl = useDerivativesPositionPnl('futures');
  const [toast, setToast] = useState<string>('');
  const [expanded, setExpanded] = useState<string>('');
  const [tableExpanded, setTableExpanded] = useState<boolean>(true);

  let rows = [...(data?.candidates ?? []).filter((r) => r.instrument_type === 'futures')];

  if (engine === 'grok') {
    rows = rows.filter(r => 
      r.strategy.startsWith('directional') ||
      r.strategy.startsWith('edge') || 
      r.strategy.startsWith('scalping') ||
      r.strategy.startsWith('conservative') ||
      r.strategy.startsWith('balanced') ||
      r.strategy.startsWith('aggressive')
    );
  } else if (engine === 'sterling') {
    rows = rows.filter(r => 
      r.strategy.startsWith('scalping') || 
      r.strategy.startsWith('edge') || 
      r.strategy.startsWith('conservative') || 
      r.strategy.startsWith('balanced') || 
      r.strategy.startsWith('aggressive')
    );
  }

  pnl.positions.filter(p => p.status === 'open' || p.status === 'partially_closed').forEach(p => {
    if (engine === 'grok' && !p.notes?.includes('[GROK]')) return;
    if (engine === 'sterling' && p.notes?.includes('[GROK]')) return;

    const dir = p.sized_trade?.structure?.direction || '';
    const match = (p.notes || '').match(/(?:scalping|edge|conservative|balanced|aggressive)\/[a-z_]+/);
    rows.push({
      freeze_token: `pos-${p.id}`,
      instrument_type: 'futures',
      underlying: p.underlying,
      direction: dir,
      strategy: match ? match[0] : 'manual',
      source: 'position',
      timestamp_ms: p.entry_timestamp_ms || 0,
      leverage: p.sized_trade?.structure?.legs?.[0]?.leverage || 1,
      contracts: p.sized_trade?.contracts || 0,
      notional_usd: (p.entry_price_real || 0) * (p.sized_trade?.contracts || 0),
      stop_loss: p.initial_sl || 0,
      take_profit: p.initial_tp || 0,
      expected_r: p.sized_trade?.structure?.risk_reward || 0,
      funding_cost_usd: (p as any).funding_cost_usd ?? 0,
      liquidity_score: null,
      reason: 'Active position',
      warnings: [],
      // @ts-ignore
      _rawPos: p,
      // @ts-ignore
      estimated_pnl_usd: p.estimated_pnl_usd,
    } as unknown as DerivativesCandidateRow);
  });

  const isAutoExec = (row: DerivativesCandidateRow): boolean => {
    const prof = cfg.data?.profiles?.[row.strategy];
    return !!prof?.auto_execute_futures;
  };

  const handleExecute = async (row: DerivativesCandidateRow) => {
    try {
      const resp = await execute.mutateAsync({ freeze_token: row.freeze_token, candidate_idx: 0 });
      if (resp.accepted) {
        setToast(`✓ ${resp.mode.toUpperCase()} ${resp.underlying} FUT ${resp.leverage}× — ${resp.order_id || resp.paper_position_id || ''}`);
      } else {
        setToast(`✗ ${resp.reason || resp.code}`);
      }
        } catch (err) {
      const msg = (err as Error)?.message || String(err);
      
      let parsed = msg;
      let isLocked = false;
      try {
        const obj = JSON.parse(msg);
        if (obj.code === 'daily_loss_halt' || obj.error?.includes('Daily loss')) isLocked = true;
        parsed = obj.error || obj.reason || obj.code || msg;
      } catch (e) {
        // Not JSON
        if (msg.includes('daily_loss_halt')) isLocked = true;
      }

      if (parsed.includes('stale_candidate') || parsed.includes('409') || parsed.includes('freeze_token')) {
        setToast('✗ Candidates refreshed — re-confirm (Stale 409)');
      } else if (isLocked || parsed.includes('Locked') || parsed.includes('423')) {
        setToast(`🔒 LOCKED: ${parsed}`);
      } else {
        setToast(`✗ ${parsed}`);
      }
      refetch();
    }
    setTimeout(() => setToast(''), 4500);
  };

  return (
    <div style={card}>
      <div 
        style={{ ...cardHead, cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setTableExpanded(!tableExpanded)}
      >
        <span style={{ marginRight: 6, fontSize: 10, color: c.dim }}>{tableExpanded ? '▾' : '▸'}</span>
        <span>DERIVATIVES · FUTURES</span>
        <span style={{ marginLeft: 8, fontSize: 9, color: c.dim, letterSpacing: 0 }}>
          leveraged execution candidates
          {strategy ? ` · ${strategy}` : ''}
          {underlying ? ` · ${underlying}` : ''}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: c.dim }}>
          {isLoading ? 'loading…' : `${rows.length} row${rows.length === 1 ? '' : 's'}`}
        </span>
      </div>
      {tableExpanded && (
      <div style={{ ...cardBody, padding: 0, overflowX: 'auto' }}>
        {rows.length === 0 ? (
          <div style={{ padding: 24, fontSize: 10, color: c.dim, textAlign: 'center' }}>
            No futures candidates. Enable a strategy in <strong>DERIVATIVES</strong> settings, or wait for the next signal.
          </div>
        ) : (
          <table style={{ width: '100%', minWidth: 920, tableLayout: 'fixed', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{
                background: c.surface, color: c.muted,
                fontSize: 9, fontWeight: 600, letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}>
                {[
                  { name: 'Symbol', tooltip: 'Underlying asset' },
                  { name: 'Strategy', tooltip: 'Originating strategy' },
                  { name: 'Lev', tooltip: 'Calculated optimal leverage' },
                  { name: 'Contracts', tooltip: 'Position size in coins/contracts' },
                  { name: 'Notional', tooltip: 'Total notional value USD' },
                  { name: 'SL', tooltip: 'Stop Loss price level' },
                  { name: 'TP', tooltip: 'Take Profit price level' },
                  { name: 'R', tooltip: 'Expected Risk-Reward Ratio at take-profit' },
                  { name: 'Funding', tooltip: 'Estimated funding rate cost' },
                  { name: 'P&L', tooltip: 'Estimated Live Profit/Loss' },
                  { name: '', tooltip: '' }
                ].map((h, i) => (
                  <th key={i} title={h.tooltip} style={{
                    padding: '5px 8px', verticalAlign: 'middle', textAlign: i >= 9 ? 'right' : 'left',
                    borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
                    cursor: h.tooltip ? 'help' : 'default'
                  }}>{h.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const auto = isAutoExec(row);
                // @ts-ignore
                const rp = row.source === 'position' && row._rawPos 
                  // @ts-ignore
                  ? { pnl: row._rawPos.estimated_pnl_usd || 0, realized: false, mode: row._rawPos.is_paper ? 'paper' : 'live', status: row._rawPos.status } 
                  : pnl.pnlForRow(row.underlying, row.direction, row.strategy);
                const isExp = expanded === row.freeze_token;
                return (
                  <React.Fragment key={row.freeze_token}>
                  <tr
                    onClick={() => setExpanded(isExp ? '' : row.freeze_token)}
                    style={{
                      borderBottom: isExp ? 'none' : `1px solid ${c.border2}`, color: c.text,
                      cursor: 'pointer', background: isExp ? alpha(c.blue, 0.06) : undefined,
                    }}>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 600 }}>
                      <span style={{ color: c.dim, fontSize: 10, marginRight: 3 }}>{isExp ? '▾' : '▸'}</span>
                      <span style={{ color: row.direction === 'long' ? c.green : c.red }}>
                        {row.direction === 'long' ? '▲' : '▼'}
                      </span>{' '}{row.underlying}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 10, fontWeight: 600, color: c.muted }}>
                      <CommonSourceBadge source={row.source} />
                      {cleanStrategy(row.strategy)}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 700, color: c.amber }}>
                      {row.leverage.toFixed(0)}×
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.contracts, 4)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmtUsd(row.notional_usd)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums', color: c.red }}>{fmtUsd(row.stop_loss)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums', color: c.green }}>{fmtUsd(row.take_profit)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 700, fontVariantNumeric: 'tabular-nums',
                                color: row.expected_r >= 2 ? c.green : row.expected_r >= 1 ? c.amber : c.red }}>
                      {fmt(row.expected_r, 2)}R
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 10, color: c.muted, fontVariantNumeric: 'tabular-nums' }}>
                      {fmtUsd(row.funding_cost_usd)}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                      {rp && rp.pnl != null ? (
                        <span style={{ color: rp.pnl >= 0 ? c.green : c.red }}
                              title={`${rp.mode} · ${rp.realized ? 'realized' : 'unrealized'} · ${rp.status}`}>
                          {fmtSigned(rp.pnl)}
                        </span>
                      ) : <span style={{ color: c.dim }}>—</span>}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right' }}>
                      {(() => {
                        if (rp) {
                          let isAuto = false;
                          let pausedAuto = false;
                          let posModeStr = 'PAPER';

                          if (row.source === 'position') {
                            const pos = (row as any)._rawPos;
                            isAuto = /\[AUTO\]/.test(pos?.notes || '');
                            pausedAuto = false;
                            if (pos && pos.is_paper !== undefined) {
                               posModeStr = pos.is_paper ? 'PAPER' : 'LIVE';
                            }
                          } else {
                            isAuto = rp.mode.includes('AUTO');
                            pausedAuto = false;
                            posModeStr = rp.mode.replace('·AUTO', '');
                          }

                          const color = posModeStr === 'LIVE' ? c.red : (posModeStr === 'SHADOW' ? c.amber : c.blue);
                          return (
                            <span title={pausedAuto ? 'Opened by Algo, which is now OFF — runs to SL/TP, no re-entry' : undefined} style={{
                              display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center',
                              fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4,
                              background: pausedAuto ? alpha(c.amber, 0.12) : alpha(color, 0.09),
                              color: pausedAuto ? c.amber : color,
                              border: `1px solid ${pausedAuto ? alpha(c.amber, 0.44) : alpha(color, 0.27)}`,
                              whiteSpace: 'nowrap'
                            }}>
                              {rp.realized ? '✓ CLOSED' : `✓ ${isAuto ? 'AUTO·' : ''}${posModeStr}${pausedAuto ? ' ⏸' : ''}`}
                            </span>
                          );
                        } else if (auto) {
                          // The crypto-era global algo switch and its router
                          // mode (paper/shadow/live) are gone; the per-strategy
                          // auto_execute_* flag is the whole gate now.
                          const color = c.blue;
                          return (
                            <span title="Auto-execute is on for this strategy" style={{
                              display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center',
                              fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4,
                              background: alpha(color, 0.08), color: color,
                              border: `1px solid ${alpha(color, 0.27)}`,
                              whiteSpace: 'nowrap'
                            }}>
                              ⚡ AUTO
                            </span>
                          );
                        }

                        return (
                          <button
                            disabled={execute.isPending}
                            onClick={(e) => { e.stopPropagation(); handleExecute(row); }}
                            style={{
                              display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center',
                              fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4,
                              background: row.direction === 'long' ? c.green : c.red,
                              color: 'var(--k-bg)', border: 'none',
                              cursor: execute.isPending ? 'wait' : 'pointer',
                              whiteSpace: 'nowrap'
                            }}>
                            {execute.isPending ? '…' : 'EXECUTE'}
                          </button>
                        );
                      })()}
                    </td>
                  </tr>
                  {isExp && (
                    <tr style={{ borderBottom: `1px solid ${c.border2}`, background: alpha(c.blue, 0.04) }}>
                      <td colSpan={11} style={{ padding: '8px 14px' }}>
                        <CommonDetailGrid items={[
                          ['Direction', row.direction.toUpperCase()],
                          ['Leverage', `${row.leverage.toFixed(0)}×`],
                          ['Contracts', fmt(row.contracts, 4)],
                          ['Notional', fmtUsd(row.notional_usd)],
                          ['Entry SL', fmtUsd(row.stop_loss)],
                          ['Entry TP', fmtUsd(row.take_profit)],
                          ['Expected R', `${fmt(row.expected_r, 2)}R`],
                          ['Funding', fmtUsd(row.funding_cost_usd)],
                          ['Liquidity', row.liquidity_score != null ? fmt(row.liquidity_score, 1) : '—'],
                          ...(rp ? [
                            ['Position', `${rp.mode} · ${rp.status.replace(/_/g, ' ')}`] as [string, string],
                            [rp.realized ? 'Realized P&L' : 'Unrealized P&L', fmtSigned(rp.pnl)] as [string, string],
                          ] : [['Position', 'not executed yet'] as [string, string]]),
                        ]} pnlVal={rp?.pnl ?? null} />
                        {row.reason && <div style={{ marginTop: 8, fontSize: 9.5, color: c.dim }}>{row.reason}</div>}
                        {row.warnings?.length > 0 && (
                          <div style={{ marginTop: 4, fontSize: 9.5, color: c.amber }}>⚠ {row.warnings.join(' · ')}</div>
                        )}
                      </td>
                    </tr>
                  )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      )}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
          padding: '8px 14px', borderRadius: 6,
          background: c.surface, border: `1px solid ${c.border}`,
          color: c.bright, fontSize: 11, fontWeight: 600, fontFamily: 'inherit',
        }}>
          {toast}
        </div>
      )}
    </div>
  );
};
