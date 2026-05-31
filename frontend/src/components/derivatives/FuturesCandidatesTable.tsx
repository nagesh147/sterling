/**
 * FuturesCandidatesTable — futures-only sibling of the signals table.
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
import { useAlgoMode } from '../../hooks/useSignalAlerts';
import {
  useDerivativesFuturesCandidates,
  useDerivativesExecute,
  useDerivativesConfig,
  DerivativesCandidateRow,
} from '../../hooks/useDerivatives';
import { SourceBadge, cleanStrategy } from './SourceBadge';

const fmt = (v: number | null | undefined, d = 2): string =>
  v == null || !isFinite(v) ? '—' : v.toFixed(d);

const fmtUsd = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });

interface Props {
  strategy?: string;
  underlying?: string;
}

export const FuturesCandidatesTable: React.FC<Props> = ({ strategy, underlying }) => {
  const { data, isLoading, refetch } = useDerivativesFuturesCandidates(strategy, underlying);
  const cfg = useDerivativesConfig();
  const algoOn = useAlgoMode().data?.enabled ?? false;
  const execute = useDerivativesExecute();
  const [toast, setToast] = useState<string>('');

  const rows = (data?.candidates ?? []).filter((r) => r.instrument_type === 'futures');

  const isAutoExec = (row: DerivativesCandidateRow): boolean => {
    if (!algoOn) return false;
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
      <div style={cardHead}>
        <span>DERIVATIVES · FUTURES</span>
        <span style={{ marginLeft: 8, fontSize: 9, color: c.dim, letterSpacing: 0 }}>
          {strategy ? `strategy=${strategy}` : 'all strategies'}
          {underlying ? ` · ${underlying}` : ''}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: c.dim }}>
          {isLoading ? 'loading…' : `${rows.length} row${rows.length === 1 ? '' : 's'}`}
        </span>
      </div>
      <div style={{ ...cardBody, padding: 0, overflowX: 'auto' }}>
        {rows.length === 0 ? (
          <div style={{ padding: 24, fontSize: 10, color: c.dim, textAlign: 'center' }}>
            No futures candidates. Enable a strategy in <strong>DERIVATIVES</strong> settings, or wait for the next signal.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{
                background: c.surface, color: c.dim,
                fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}>
                {['Symbol', 'Strategy', 'Lev', 'Contracts', 'Notional', 'SL', 'TP', 'R', 'Funding', ''].map((h, i) => (
                  <th key={i} style={{
                    padding: '6px 8px', textAlign: i === 9 ? 'right' : 'left',
                    borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const auto = isAutoExec(row);
                return (
                  <tr key={row.freeze_token} style={{
                    borderBottom: `1px solid ${c.border2}`, color: c.text,
                  }}>
                    <td style={{ padding: '6px 8px', fontWeight: 700 }}>
                      <span style={{ color: row.direction === 'long' ? c.green : c.red }}>
                        {row.direction === 'long' ? '▲' : '▼'}
                      </span>{' '}{row.underlying}
                    </td>
                    <td style={{ padding: '6px 8px', fontSize: 9, color: c.dim, whiteSpace: 'nowrap' }}>
                      <SourceBadge source={row.source} />
                      {cleanStrategy(row.strategy)}
                    </td>
                    <td style={{ padding: '6px 8px', fontWeight: 700, color: c.amber }}>
                      {row.leverage.toFixed(0)}×
                    </td>
                    <td style={{ padding: '6px 8px' }}>{fmt(row.contracts, 4)}</td>
                    <td style={{ padding: '6px 8px' }}>{fmtUsd(row.notional_usd)}</td>
                    <td style={{ padding: '6px 8px', color: c.red }}>{fmtUsd(row.stop_loss)}</td>
                    <td style={{ padding: '6px 8px', color: c.green }}>{fmtUsd(row.take_profit)}</td>
                    <td style={{ padding: '6px 8px', fontWeight: 700,
                                color: row.expected_r >= 2 ? c.green : row.expected_r >= 1 ? c.amber : c.red }}>
                      {fmt(row.expected_r, 2)}R
                    </td>
                    <td style={{ padding: '6px 8px', fontSize: 10, color: c.dim }}>
                      {fmtUsd(row.funding_cost_usd)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                      {auto ? (
                        <span title="Algo is ON — auto-executes via background scanner" style={{
                          display: 'inline-block', padding: '3px 10px', borderRadius: 4,
                          background: alpha(c.amber, 0.16), border: `1px solid ${alpha(c.amber, 0.45)}`,
                          color: c.amber, fontSize: 9, fontWeight: 800, letterSpacing: '0.08em',
                        }}>
                          AUTO
                        </span>
                      ) : (
                        <button
                          disabled={execute.isPending}
                          onClick={() => handleExecute(row)}
                          style={{
                            padding: '4px 12px', borderRadius: 5,
                            background: alpha(c.green, 0.14),
                            border: `1px solid ${alpha(c.green, 0.4)}`,
                            color: c.green, fontSize: 10, fontWeight: 800,
                            letterSpacing: '0.06em', cursor: execute.isPending ? 'wait' : 'pointer',
                            fontFamily: 'inherit',
                          }}>
                          {execute.isPending ? '…' : 'EXECUTE'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
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
