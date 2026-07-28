import React from 'react';
import { BORDER, DIM, MUTED, TEXT } from './kiteSettingsPrimitives';
import type { DirectionalEvidence, NavigatorDecision, NavigatorStatus } from '../../types/navigator';

const STATUS_COLOR: Record<NavigatorStatus, string> = {
  NO_DATA: '#9b9b9b',
  WAIT: '#9b9b9b',
  WATCH: '#4184f3',
  CONFLICT: '#df514c',
  CONFIRMED: '#4caf50',
  HIGH_CONVICTION: '#2e7d32',
};

const STATUS_LABEL: Record<NavigatorStatus, string> = {
  NO_DATA: 'No data',
  WAIT: 'Wait',
  WATCH: 'Watch',
  CONFLICT: 'Conflict',
  CONFIRMED: 'Confirmed',
  HIGH_CONVICTION: 'High conviction',
};

function ComponentRow({ evidence }: { evidence: DirectionalEvidence | null }) {
  if (!evidence) {
    return null;
  }
  const dirLabel = evidence.direction === 1 ? 'bullish' : evidence.direction === -1 ? 'bearish' : 'neutral';
  const qualityColor = evidence.quality === 'ok' ? '#4caf50' : evidence.quality === 'degraded' ? '#f5a623' : '#9b9b9b';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '90px 70px 60px minmax(0,1fr)', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${BORDER}`, fontSize: 10.5 }}>
      <span style={{ color: TEXT, fontWeight: 700, textTransform: 'capitalize' }}>{evidence.component.replace('_', ' ')}</span>
      <span style={{ color: MUTED }}>{dirLabel}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: qualityColor, fontWeight: 700 }}>
        <span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: qualityColor }} />
        {evidence.quality}
      </span>
      <span style={{ color: DIM, fontSize: 9.5 }}>
        {Math.round(evidence.confidence_100)}% · {evidence.reason_codes.join(', ')}
      </span>
    </div>
  );
}

/** Full evidence breakdown for one signal row's detail view. Never reduces
 * NO_DATA/WAIT/CONFLICT to an unexplained dot — every state is inspectable. */
export function NavigatorEvidencePanel({ decision }: { decision: NavigatorDecision }) {
  const staleAgeMs = Date.now() - decision.generated_at_ms;
  const staleAgeS = Math.max(0, Math.round(staleAgeMs / 1000));

  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 8, padding: 12, background: '#fbfbfb' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 8px', borderRadius: 5,
          background: `${STATUS_COLOR[decision.status]}18`, color: STATUS_COLOR[decision.status], fontSize: 10.5, fontWeight: 800,
        }}>
          <span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: STATUS_COLOR[decision.status] }} />
          {STATUS_LABEL[decision.status]}
        </span>
        <span style={{ color: DIM, fontSize: 9.5 }}>as of {staleAgeS}s ago</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 10, marginBottom: 10 }}>
        <ScoreTile label="Raw (base)" value={decision.base_score} />
        <ScoreTile label="Suite" value={decision.suite_score} />
        <ScoreTile label="Effective" value={decision.effective_score} emphasize />
      </div>

      {decision.status === 'NO_DATA' || decision.status === 'WAIT' || decision.status === 'CONFLICT' || decision.status === 'WATCH' ? (
        <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>
          Reasons: {decision.reason_codes.join(', ') || 'none reported'}
        </div>
      ) : null}

      <div>
        <ComponentRow evidence={decision.avwap} />
        <ComponentRow evidence={decision.volatility} />
        <ComponentRow evidence={decision.option_flow} />
        <ComponentRow evidence={decision.gamma} />
      </div>

      <div style={{ marginTop: 8, fontSize: 9.5, color: DIM }}>
        Execution eligible: {decision.execution_eligible ? 'yes' : 'no'} · config rev {decision.config_revision} · trigger {decision.trigger}
      </div>
    </div>
  );
}

function ScoreTile({ label, value, emphasize = false }: { label: string; value: number | null; emphasize?: boolean }) {
  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 6, padding: '8px 10px', textAlign: 'center' }}>
      <div style={{ color: DIM, fontSize: 9, textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
      <div style={{ color: TEXT, fontSize: emphasize ? 17 : 14, fontWeight: 800, marginTop: 2 }}>
        {value == null ? '—' : Math.round(value)}
      </div>
    </div>
  );
}

export default NavigatorEvidencePanel;
