import React from 'react';
import { useAdaptiveEdgeEngineConfig } from '../../hooks/useAdaptiveEdge';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';

/* The Master Specification engine's own scan.
   Deliberately not folded into the board beside it: that board renders a
   spot-scan row model built for the moving-average strategy this one replaced,
   and mapping option-contract candidates onto `spotEntry` / `spotSl` / `score`
   would put numbers under headings that do not mean what they say. This shows
   what the engine actually produced, including the reason nothing is armable. */

interface EngineScan {
  underlyings?: number;
  chains_read?: number;
  listed?: number;
  tradeable?: number;
  candidates?: Array<Record<string, unknown>>;
  skipped?: Record<string, string>;
  dropped?: Record<string, number>;
  errors?: string[];
}

interface EngineSnapshot {
  readiness?: { executable?: boolean; reason?: string | null; promotion_gate_reason?: string | null };
  scan?: EngineScan & { signals?: Array<Record<string, unknown>> };
  session?: Record<string, unknown> | null;
  warnings?: string[];
}

const MUTED = 'var(--k-muted, #8b949e)';
const TEXT = 'var(--k-text, #e6edf3)';
const LINE = 'var(--k-line, #30363d)';

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 74 }}>
      <span style={{ color: MUTED, fontSize: 10.5, letterSpacing: 0.3, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ color: TEXT, fontSize: 14, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

export function AdaptiveEdgeEngineScan() {
  const config = useAdaptiveEdgeEngineConfig();
  const snapshot = useQuery<EngineSnapshot>({
    queryKey: ['adaptive-edge-engine-snapshot'],
    queryFn: () => api.get<EngineSnapshot>('/api/v1/config/adaptive-edge/snapshot'),
    refetchInterval: 10000,
  });

  const scan = snapshot.data?.scan;
  const candidates = scan?.candidates ?? [];
  const dropped = Object.entries(scan?.dropped ?? {});
  const skipped = Object.entries(scan?.skipped ?? {});

  return (
    <section style={{ border: `1px solid ${LINE}`, borderRadius: 8, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <header style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: 13, color: TEXT }}>Engine scan</h3>
        <span style={{ color: MUTED, fontSize: 11.5 }}>
          {config.data?.strategy.name ?? 'Adaptive Edge'} · paper only
        </span>
      </header>

      {config.data && !config.data.strategy.validated ? (
        <p style={{ margin: 0, color: MUTED, fontSize: 11.5, lineHeight: 1.5 }}>
          {config.data.strategy.headline_finding}
        </p>
      ) : null}

      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
        <Stat label="Underlyings" value={scan?.underlyings ?? '—'} />
        <Stat label="Chains" value={scan?.chains_read ?? '—'} />
        <Stat label="Listed" value={scan?.listed ?? '—'} />
        <Stat label="Tradeable" value={scan?.tradeable ?? '—'} />
        <Stat label="Candidates" value={candidates.length} />
      </div>

      {/* An empty board has several very different causes, so it says which. */}
      {candidates.length === 0 ? (
        <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.6 }}>
          {skipped.length === 0 && dropped.length === 0 ? (
            <span>No scan has run yet, or the session window is closed.</span>
          ) : (
            <>
              {skipped.map(([name, reason]) => (
                <div key={name}>{name}: {reason}</div>
              ))}
              {dropped.map(([reason, count]) => (
                <div key={reason}>{count} contract{count === 1 ? '' : 's'} dropped — {reason}</div>
              ))}
            </>
          )}
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 11.5, width: '100%' }}>
            <thead>
              <tr style={{ color: MUTED, textAlign: 'left' }}>
                {['Contract', 'Strike', 'Type', 'DTE', 'Premium', 'OI', 'Status'].map((h) => (
                  <th key={h} style={{ padding: '4px 10px 4px 0', fontWeight: 500 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {candidates.slice(0, 25).map((row, index) => (
                <tr key={String(row.symbol ?? index)} style={{ color: TEXT, borderTop: `1px solid ${LINE}` }}>
                  <td style={{ padding: '5px 10px 5px 0' }}>{String(row.symbol ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0', fontVariantNumeric: 'tabular-nums' }}>{String(row.strike ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0' }}>{String(row.option_type ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0', fontVariantNumeric: 'tabular-nums' }}>{String(row.dte ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0', fontVariantNumeric: 'tabular-nums' }}>{String(row.last_price ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0', fontVariantNumeric: 'tabular-nums' }}>{String(row.oi ?? '—')}</td>
                  <td style={{ padding: '5px 10px 5px 0', color: MUTED }}>Not armable — uncalibrated</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {snapshot.data?.readiness?.executable === false ? (
        <p style={{ margin: 0, color: MUTED, fontSize: 11.5 }}>
          Live execution blocked: {snapshot.data.readiness.promotion_gate_reason ?? snapshot.data.readiness.reason}
        </p>
      ) : null}

      {(scan?.errors ?? []).map((error) => (
        <p key={error} style={{ margin: 0, color: 'var(--k-danger, #f85149)', fontSize: 11.5 }}>{error}</p>
      ))}
    </section>
  );
}

export default AdaptiveEdgeEngineScan;
