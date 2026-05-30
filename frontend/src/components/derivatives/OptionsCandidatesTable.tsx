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
import {
  useDerivativesOptionsCandidates,
  useDerivativesExecute,
  useDerivativesConfig,
  DerivativesCandidateRow,
} from '../../hooks/useDerivatives';
import { SourceBadge, cleanStrategy } from './SourceBadge';

const fmt = (v: number | null | undefined, d = 2): string =>
  v == null || !isFinite(v) ? '—' : v.toFixed(d);

const fmtUsd = (v: number | null | undefined): string =>
  v == null || !isFinite(v) ? '—' : '$' + v.toLocaleString('en-US', { maximumFractionDigits: 2 });

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
  const execute = useDerivativesExecute();
  const [toast, setToast] = useState<string>('');

  const rows = (data?.candidates ?? []).filter((r) => r.instrument_type === 'options');

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
      if (msg.includes('stale_candidate') || msg.includes('409')) {
        setToast('Candidates refreshed — re-confirm');
      } else {
        setToast(`✗ ${msg}`);
      }
      refetch();
    }
    setTimeout(() => setToast(''), 4500);
  };

  return (
    <div style={card}>
      <div style={cardHead}>
        <span>DERIVATIVES · OPTIONS</span>
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
            No options candidates. Enable a strategy in <strong>DERIVATIVES</strong> settings, or wait for the next chain refresh.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{
                background: c.surface, color: c.dim,
                fontSize: 9, fontWeight: 700, letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}>
                {['Symbol', 'Strategy', 'Contract', 'Δ', 'Γ', 'Θ', 'ν', 'Premium', 'Liq', 'R', 'θ burn', ''].map((h, i) => (
                  <th key={i} style={{
                    padding: '6px 8px', textAlign: i === 11 ? 'right' : 'left',
                    borderBottom: `1px solid ${c.border}`, whiteSpace: 'nowrap',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const auto = isAutoExec(row);
                const { type, strikeK, dteTag } = optionLabel(row);
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
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>
                      <span style={{ color: type === 'CE' ? c.green : c.red }}>{type}</span>{' '}
                      <span>{strikeK}</span>{' '}
                      <span style={{ color: c.dim, fontSize: 9 }}>{dteTag}</span>
                    </td>
                    <td style={{ padding: '6px 8px' }}>{fmt(row.delta, 3)}</td>
                    <td style={{ padding: '6px 8px' }}>{fmt(row.gamma, 5)}</td>
                    <td style={{ padding: '6px 8px', color: row.theta && row.theta < 0 ? c.red : c.text }}>
                      {fmt(row.theta, 2)}
                    </td>
                    <td style={{ padding: '6px 8px' }}>{fmt(row.vega, 2)}</td>
                    <td style={{ padding: '6px 8px' }}>{fmtUsd(row.premium)}</td>
                    <td style={{ padding: '6px 8px' }}>
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
                    <td style={{ padding: '6px 8px', fontWeight: 700,
                                color: row.expected_r >= 2 ? c.green : row.expected_r >= 1 ? c.amber : c.red }}>
                      {fmt(row.expected_r, 2)}R
                    </td>
                    <td style={{ padding: '6px 8px', fontSize: 10, color: c.dim }}>
                      {fmtUsd(row.theta_burn_usd)}
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
