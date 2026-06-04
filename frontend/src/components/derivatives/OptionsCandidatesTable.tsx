/**
 * OptionsCandidatesTable — options-only sibling of the signals table.
 *
 * Mounted after the signals SectionCard alongside FuturesCandidatesTable.
 * Each row is one selector-decided options candidate (strike, DTE, full
 * Greeks, premium, liquidity, expected R, projected theta-burn).
 *
 * When algo is ON AND the row's strategy profile has
 * `auto_execute_options=true`, the BACKGROUND scanner fires the row
 * automatically — the FE renders an "AUTO" pill in that case.
 *
 * Columns: Underlying · Strategy · CE/PE Strike DTE · Δ · Γ · Θ · ν ·
 * Premium · Liq · Expected R · θ-burn · EXECUTE/AUTO.
 */
import React, { useState } from 'react';
import { card, cardHead, cardBody, alpha, c } from '../../styles/terminalUI';
import { useAlgoMode } from '../../hooks/useSignalAlerts';
import { useRouterMode } from '../../hooks/useRouterMode';
import {
  useDerivativesOptionsCandidates,
  useDerivativesExecute,
  useDerivativesConfig,
  DerivativesCandidateRow,
} from '../../hooks/useDerivatives';
import { SourceBadge, cleanStrategy } from './SourceBadge';
import { useDerivativesPositionPnl } from '../../hooks/useDerivativesPositionPnl';
import { DetailGrid } from './DetailGrid';

const fmt = (v: number | null | undefined, d = 2): string =>
  v == null || !isFinite(v) ? '—' : v.toFixed(d);

const fmtUsd = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });

const fmtSigned = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : (v < 0 ? '-' : '+') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 2 });

const optionLabel = (row: DerivativesCandidateRow): { type: string; strikeK: string; dteTag: string } => {
  const parts = (row.option_symbol ?? '').split('-');
  const type = parts[0] === 'C' ? 'CE' : 'PE';
  const strikeK = row.strike != null ? `${Math.round(row.strike / 1000)}k` : '?';
  const dteTag = row.dte != null ? `${row.dte}d` : '?d';
  return { type, strikeK, dteTag };
};

const liquidityColor = (s: number | null): string => {
  if (s == null) return c.dim;
  if (s >= 0.7) return c.green;
  if (s >= 0.4) return c.amber;
  return c.red;
};

interface Props {
  strategy?: string;
  underlying?: string;
}

export const OptionsCandidatesTable: React.FC<Props> = ({ strategy, underlying }) => {
  const { data, isLoading, refetch } = useDerivativesOptionsCandidates(strategy, underlying);
  const cfg = useDerivativesConfig();
  const algoOn = useAlgoMode().data?.enabled ?? false;
  const { mode: routerMode } = useRouterMode();
  const execute = useDerivativesExecute();
  const pnl = useDerivativesPositionPnl('options');
  const [toast, setToast] = useState<string>('');
  const [expanded, setExpanded] = useState<string>('');
  const [tableExpanded, setTableExpanded] = useState<boolean>(true);

  let rows = [...(data?.candidates ?? []).filter((r) => r.instrument_type === 'options')];
  
  pnl.positions.filter(p => p.status === 'open' || p.status === 'partially_closed').forEach(p => {
    const dir = p.sized_trade?.structure?.direction || '';
    const match = (p.notes || '').match(/(?:scalping|edge|triple_st)\/[a-z_]+/);
      const leg = p.sized_trade?.structure?.legs?.[0];
      rows.push({
        freeze_token: `pos-${p.id}`,
        instrument_type: 'options',
        underlying: p.underlying,
        direction: dir,
        strategy: match ? match[0] : 'manual',
        source: 'position',
        timestamp_ms: p.entry_timestamp_ms || 0,
        contracts: p.sized_trade?.contracts || 0,
        notional_usd: (p.entry_price_real || 0) * (p.sized_trade?.contracts || 0),
        stop_loss: p.initial_sl || 0,
        take_profit: p.initial_tp || 0,
        expected_r: p.sized_trade?.structure?.risk_reward || 0,
        funding_cost_usd: 0,
        theta_burn_usd: p.expected_theta_burn_usd || 0,
        liquidity_score: leg?.health_score || null,
        reason: 'Active position',
        warnings: [],
        option_symbol: leg?.instrument_name || '',
        strike: leg?.strike || 0,
        dte: p.entry_dte ?? leg?.dte ?? 0,
        premium: p.entry_premium ?? p.entry_price_real ?? 0,
        delta: p.entry_greeks_snapshot?.delta ?? leg?.delta,
        gamma: p.entry_greeks_snapshot?.gamma ?? leg?.gamma,
        theta: p.entry_greeks_snapshot?.theta ?? leg?.theta,
        vega: p.entry_greeks_snapshot?.vega ?? leg?.vega,
        // @ts-ignore
        _rawPos: p,
        // @ts-ignore
        estimated_pnl_usd: p.estimated_pnl_usd,
      } as unknown as DerivativesCandidateRow);
    });

  const isAutoExec = (row: DerivativesCandidateRow): boolean => {
    if (!algoOn) return false;
    const prof = cfg.data?.profiles?.[row.strategy];
    return !!prof?.auto_execute_options;
  };

  const handleExecute = async (row: DerivativesCandidateRow) => {
    try {
      const resp = await execute.mutateAsync({ freeze_token: row.freeze_token, candidate_idx: 0 });
      if (resp.accepted) {
        setToast(`✓ ${resp.mode.toUpperCase()} ${resp.underlying} ${optionLabel(row).type} ${optionLabel(row).strikeK} — ${resp.order_id || resp.paper_position_id || ''}`);
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
        <span>DERIVATIVES · OPTIONS</span>
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
            No options candidates. Enable a strategy in <strong>DERIVATIVES</strong> settings, or wait for the next chain refresh.
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
                  { name: 'Contract', tooltip: 'Option contract details (Type, Strike, DTE)' },
                  { name: 'Δ', tooltip: 'Delta: Price sensitivity to $1 underlying move' },
                  { name: 'Γ', tooltip: 'Gamma: Rate of change of Delta' },
                  { name: 'Θ', tooltip: 'Theta: Daily time decay' },
                  { name: 'ν', tooltip: 'Vega: Sensitivity to 1% implied volatility change' },
                  { name: 'Premium', tooltip: 'Option price / Entry premium paid' },
                  { name: 'Liq', tooltip: 'Liquidity health score (0-100)' },
                  { name: 'R', tooltip: 'Expected Risk-Reward Ratio at take-profit' },
                  { name: 'θ burn', tooltip: 'Projected total theta burn over expected hold time' },
                  { name: 'P&L', tooltip: 'Estimated Live Profit/Loss' },
                  { name: '', tooltip: '' }
                ].map((h, i) => (
                  <th key={i} title={h.tooltip} style={{
                    padding: '5px 8px', verticalAlign: 'middle', textAlign: i >= 11 ? 'right' : 'left',
                    borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
                    cursor: h.tooltip ? 'help' : 'default'
                  }}>{h.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const auto = isAutoExec(row);
                const { type, strikeK, dteTag } = optionLabel(row);
                // @ts-ignore
                const rp = row.source === 'position' && row._rawPos 
                  // @ts-ignore
                  ? { 
                      pnl: (row._rawPos.status === 'open' || row._rawPos.status === 'partially_closed') ? (row._rawPos.estimated_pnl_usd ?? 0) : (row._rawPos.realized_pnl_usd ?? 0), 
                      realized: !(row._rawPos.status === 'open' || row._rawPos.status === 'partially_closed'), 
                      mode: (row._rawPos.notes || '').includes('[LIVE]') ? 'LIVE' : 'PAPER', 
                      status: row._rawPos.status 
                    } 
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
                      <SourceBadge source={row.source} />
                      {cleanStrategy(row.strategy)}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 600 }}>
                      <span style={{ color: type === 'CE' ? c.green : c.red }}>{type}</span>{' '}
                      <span>{strikeK}</span>{' '}
                      <span style={{ color: c.dim, fontSize: 9 }}>{dteTag}</span>
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.delta, 3)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.gamma, 5)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums', color: row.theta && row.theta < 0 ? c.red : c.text }}>
                      {fmt(row.theta, 2)}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.vega, 2)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontVariantNumeric: 'tabular-nums' }}>{fmtUsd(row.premium)}</td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <span style={{
                        display: 'inline-block', minWidth: 36, textAlign: 'center',
                        padding: '1px 6px', borderRadius: 4, fontSize: 10,
                        background: alpha(liquidityColor(row.liquidity_score), 0.12),
                        color: liquidityColor(row.liquidity_score),
                        border: `1px solid ${alpha(liquidityColor(row.liquidity_score), 0.3)}`,
                      }}>
                        {row.liquidity_score == null ? '—' : (row.liquidity_score * 100).toFixed(0)}
                      </span>
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: 700,
                                color: row.expected_r >= 2 ? c.green : row.expected_r >= 1 ? c.amber : c.red }}>
                      {fmt(row.expected_r, 2)}R
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 10, color: c.muted }}>
                      {fmtUsd(row.theta_burn_usd)}
                    </td>
                    <td style={{ padding: '4px 6px', verticalAlign: 'middle', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textAlign: 'right', fontWeight: 700 }}>
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
                            pausedAuto = isAuto && !algoOn && (pos?.status === 'open' || pos?.status === 'partially_closed');
                            if (pos && pos.is_paper !== undefined) {
                               posModeStr = pos.is_paper ? (routerMode === 'shadow' ? 'SHADOW' : 'PAPER') : 'LIVE';
                            }
                          } else {
                            isAuto = rp.mode.includes('AUTO');
                            pausedAuto = isAuto && !algoOn && !rp.realized;
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
                        } else if (auto && algoOn) {
                          const modeStr = routerMode.toUpperCase();
                          const color = modeStr === 'LIVE' ? c.red : (modeStr === 'SHADOW' ? c.amber : c.blue);
                          return (
                            <span title={`Algo is ON — auto-executes in ${modeStr} mode`} style={{
                              display: 'inline-block', width: 105, boxSizing: 'border-box', textAlign: 'center',
                              fontSize: 10, fontWeight: 700, padding: '4px 8px', borderRadius: 4,
                              background: alpha(color, 0.08), color: color,
                              border: `1px solid ${alpha(color, 0.27)}`,
                              whiteSpace: 'nowrap'
                            }}>
                              ⚡ AUTO·{modeStr}
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
                              color: '#fff', border: 'none',
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
                      <td colSpan={13} style={{ padding: '8px 14px' }}>
                        <DetailGrid items={[
                          ['Contract', `${type} ${strikeK} ${dteTag}`],
                          ['Option', row.option_symbol ?? '—'],
                          ['Direction', row.direction.toUpperCase()],
                          ['Strike', row.strike != null ? fmtUsd(row.strike) : '—'],
                          ['DTE', row.dte != null ? `${row.dte}d` : '—'],
                          ['Delta', fmt(row.delta, 3)],
                          ['Gamma', fmt(row.gamma, 5)],
                          ['Theta', fmt(row.theta, 2)],
                          ['Vega', fmt(row.vega, 2)],
                          ['Premium', fmtUsd(row.premium)],
                          ['Contracts', fmt(row.contracts, 4)],
                          ['Expected R', `${fmt(row.expected_r, 2)}R`],
                          ['θ burn', fmtUsd(row.theta_burn_usd)],
                          ['Liquidity', row.liquidity_score != null ? `${(row.liquidity_score * 100).toFixed(0)}` : '—'],
                          ...(rp ? [
                            ['Position', `${rp.mode} · ${rp.status.replace(/_/g, ' ')}`] as [string, string],
                            [rp.realized ? 'Realized P&L' : 'Unrealized P&L', fmtSigned(rp.pnl)] as [string, string],
                          ] : [['Position', 'not executed yet'] as [string, string]]),
                        ]} pnlVal={rp?.pnl ?? null} />
                        {row.structure_summary && (
                          <div style={{ marginTop: 8, fontSize: 10, color: c.text }}>
                            <b style={{ color: c.amber }}>STRUCTURE</b>{' '}
                            <span style={{ color: c.dim }}>{row.structure_summary}</span>
                            {' · '}max loss{' '}
                            <b style={{ color: c.red }}>{fmtUsd(row.structure_max_loss_usd)}</b>
                            {' · '}max profit{' '}
                            <b style={{ color: c.green }}>{fmtUsd(row.structure_max_profit_usd)}</b>
                          </div>
                        )}
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
