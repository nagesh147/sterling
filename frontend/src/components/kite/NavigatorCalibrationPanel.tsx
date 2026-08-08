import React from 'react';
import { BORDER, DIM, MUTED, TEXT } from './kiteSettingsPrimitives';
import { Icons } from '../../styles/kiteUI';
import {
  useDemoteCalibration, useGenerateCalibrationReport, useNavigatorCalibration, usePromoteCalibration,
} from '../../hooks/useNavigator';
import type { CalibrationCriteria, CalibrationReport } from '../../types/navigator';

const GREEN = '#4caf50';
const RED = '#df514c';
const AMBER = '#f5a623';

function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v * 100)}%`;
}

function CriterionRow({ passed, label, detail }: { passed: boolean; label: string; detail: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, padding: '7px 0', borderTop: `1px solid ${BORDER}` }}>
      <span
        aria-label={passed ? 'Passing' : 'Not yet met'}
        style={{
          flexShrink: 0, marginTop: 1, width: 15, height: 15, borderRadius: '50%',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, fontWeight: 800, color: '#fff', background: passed ? GREEN : '#c2c2c2',
        }}
      >
        {passed ? '✓' : '·'}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 11.5, color: TEXT, fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: 10.5, color: passed ? MUTED : AMBER, marginTop: 1 }}>{detail}</div>
      </div>
    </div>
  );
}

function WindowSummary({ title, w }: { title: string; w: CalibrationReport['evaluation'] }) {
  return (
    <div style={{ flex: 1, minWidth: 150 }}>
      <div style={{ color: DIM, fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', marginBottom: 5 }}>{title}</div>
      <div style={{ fontSize: 11, color: MUTED, lineHeight: 1.7 }}>
        <div>{w.sessions} sessions · {w.total_decisions} decisions</div>
        <div>{w.actionable_scored} scored{w.unscorable ? ` · ${w.unscorable} too recent to judge` : ''}</div>
        <div>
          Right {w.hit_rate == null ? '—' : `${w.actionable_hits}/${w.actionable_scored} (${pct(w.hit_rate)})`}
        </div>
        <div>Average move {w.mean_return_pct == null ? '—' : `${w.mean_return_pct > 0 ? '+' : ''}${w.mean_return_pct.toFixed(2)}%`}</div>
      </div>
    </div>
  );
}

export function NavigatorCalibrationPanel() {
  const { data, isLoading } = useNavigatorCalibration();
  const generate = useGenerateCalibrationReport();
  const promote = usePromoteCalibration();
  const demote = useDemoteCalibration();
  const [promoteConfirm, setPromoteConfirm] = React.useState(false);

  // The freshly-generated report wins over the stored one, so the panel
  // reflects what you just ran without waiting on a refetch.
  const criteria: CalibrationCriteria | null = generate.data?.criteria ?? data?.criteria ?? null;
  const report = generate.data?.report ?? null;
  const reportId = generate.data?.report_id ?? data?.calibration_report_id ?? null;
  const ready = data?.calibration_readiness === 'ready';
  const revision = data?.revision;

  if (isLoading) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading calibration status…</div>;
  }

  const outstanding = criteria ? criteria.criteria.filter((c) => !c.passed).length : null;
  const canPromote = !!criteria?.eligible && !!reportId && revision != null && !ready;

  return (
    <details
      style={{
        background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 9,
        overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)',
      }}
    >
      <summary style={{
        listStyle: 'none', cursor: 'pointer', padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 10, userSelect: 'none',
        background: '#fff',
      }}>
        <span aria-hidden style={{ width: 14, color: DIM, fontSize: 12, fontWeight: 700, flexShrink: 0 }}>›</span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ color: TEXT, fontSize: 12, fontWeight: 700 }}>Calibration &amp; Gate readiness</div>
          <div style={{ color: MUTED, fontSize: 10.5, lineHeight: 1.4, marginTop: 1, maxWidth: 440 }}>
            Gate stays locked until calibration passes. Expand to score and promote.
          </div>
        </div>
        <span style={{
          flexShrink: 0, fontSize: 9.5, fontWeight: 700, borderRadius: 4, padding: '3px 9px',
          color: ready ? GREEN : DIM, background: ready ? '#e8f5e9' : '#f2f2f3',
          border: `1px solid ${ready ? `${GREEN}55` : BORDER}`,
        }}>
          {ready ? 'Ready — gate unlocked' : 'Not yet calibrated'}
        </span>
      </summary>

      <div style={{ padding: '0 16px 16px', borderTop: `1px solid ${BORDER}` }}>
        <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, margin: '12px 0 0', maxWidth: 440 }}>
          Scores every call Navigator has made against what the market actually did next. Gate mode
          stays locked until this passes — and even then, promoting is your decision, never automatic.
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button
            type="button" onClick={() => generate.mutate()} disabled={generate.isPending}
            style={{ ...primaryButton, opacity: generate.isPending ? 0.5 : 1 }}
          >
            {generate.isPending ? 'Scoring decisions…' : 'Generate report'}
          </button>
          {!ready && (
            <button
              type="button"
              disabled={!canPromote || promote.isPending}
              title={canPromote ? undefined : 'Every criterion below has to pass first'}
              onClick={() => {
                if (!promoteConfirm) { setPromoteConfirm(true); return; }
                if (reportId && revision != null) {
                  promote.mutate({ report_id: reportId, expected_revision: revision },
                    { onSuccess: () => setPromoteConfirm(false) });
                }
              }}
              style={{ ...pillButton, color: promoteConfirm ? RED : MUTED, opacity: canPromote ? 1 : 0.5 }}
            >
              {promoteConfirm ? 'Click again to confirm promotion' : 'Promote to ready'}
            </button>
          )}
          {ready && revision != null && (
            <button
              type="button" onClick={() => demote.mutate({ expected_revision: revision })}
              disabled={demote.isPending} style={{ ...pillButton, color: RED }}
            >
              <Icons.Reload /> Revoke
            </button>
          )}
        </div>

        {generate.isError && (
          <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 7, background: '#fff0f0', border: '1px solid #e2a4a4', color: RED, fontSize: 11 }}>
            Couldn&apos;t generate a report: {String(generate.error?.message ?? 'unknown error')}
          </div>
        )}
        {promote.isError && (
          <div style={{ marginTop: 10, padding: '9px 11px', borderRadius: 7, background: '#fff0f0', border: '1px solid #e2a4a4', color: RED, fontSize: 11 }}>
            {String(promote.error?.message ?? 'promotion failed')}
          </div>
        )}
      </div>

      <div style={{ padding: '14px 18px' }}>
        {!criteria ? (
          <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.6 }}>
            No report yet. Navigator records every decision it makes as it runs — generate a report once
            it has been running for a while and this will show exactly how far along it is.
          </div>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ color: DIM, fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase' }}>
                Promotion criteria
              </span>
              <span style={{ fontSize: 10, color: outstanding ? AMBER : GREEN, fontWeight: 700 }}>
                {outstanding ? `${outstanding} still outstanding` : 'all clear'}
              </span>
            </div>
            {criteria.criteria.map((c) => (
              <CriterionRow key={c.key} passed={c.passed} label={c.label} detail={c.detail} />
            ))}
          </>
        )}

        {!!report?.warnings?.length && (
          <div style={{ marginTop: 14, padding: '10px 12px', borderRadius: 7, background: '#fff5f0', border: '1px solid #e2b6a4' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: TEXT, fontSize: 11.5, fontWeight: 700, marginBottom: 4 }}>
              <Icons.Warning /> This report couldn&apos;t score everything
            </div>
            {report.warnings.map((wn) => (
              <div key={wn} style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 3 }}>{wn}</div>
            ))}
          </div>
        )}

        {report && (
          <>
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 16, paddingTop: 12, borderTop: `1px dashed ${BORDER}` }}>
              <WindowSummary title="Tuning window" w={report.calibration} />
              <WindowSummary title="Untouched check" w={report.evaluation} />
            </div>
            <ul style={{ margin: '12px 0 0', paddingLeft: 16, color: DIM, fontSize: 10.5, lineHeight: 1.6 }}>
              {report.caveats.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </>
        )}
      </div>
    </details>
  );
}

const pillButton: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, border: `1px solid ${BORDER}`, background: '#fff',
  color: MUTED, borderRadius: 7, padding: '7px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
};

const primaryButton: React.CSSProperties = {
  border: 'none', background: '#f06428', color: '#fff', borderRadius: 7, padding: '8px 16px',
  fontSize: 11.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
};

export default NavigatorCalibrationPanel;
