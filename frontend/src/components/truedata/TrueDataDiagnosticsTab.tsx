import React, { useState } from 'react';
import { useRunTrueDataDiagnostics, useTrueDataDiagnosticsSummary } from '../../hooks/useTrueData';
import type { DiagnosticCategoryResult, DiagnosticSuiteResult, DiagnosticStatus } from '../../types/truedata';

const S: Record<string, React.CSSProperties> = {
  card: {
    background: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: 10,
    padding: 16,
    marginBottom: 14,
    boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
    transition: 'all 0.15s ease',
  },
  headerBanner: {
    background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
    borderRadius: 12,
    padding: 20,
    color: '#fff',
    marginBottom: 20,
    boxShadow: '0 4px 12px rgba(15, 23, 42, 0.12)',
  },
  btnPrimary: {
    minHeight: 36,
    background: 'linear-gradient(135deg, #f06428 0%, #e05316 100%)',
    color: '#fff',
    border: 'none',
    padding: '0 16px',
    borderRadius: 7,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 0.3,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    boxShadow: '0 2px 6px rgba(240, 100, 40, 0.3)',
    transition: 'all 0.15s ease',
  },
  btnSecondary: {
    minHeight: 30,
    background: '#f8fafc',
    color: '#475569',
    border: '1px solid #cbd5e1',
    padding: '0 11px',
    borderRadius: 6,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 650,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    transition: 'all 0.15s ease',
  },
  statusBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 9px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 750,
    letterSpacing: 0.4,
  },
  metricChip: {
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: 7,
    padding: '8px 12px',
    minWidth: 110,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: 700,
    color: '#64748b',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  metricValue: {
    fontSize: 13.5,
    fontWeight: 750,
    color: '#0f172a',
    fontFamily: 'monospace',
  },
  fieldCheckRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '6px 10px',
    borderBottom: '1px solid #f1f5f9',
    fontSize: 11.5,
  },
  rawJsonBox: {
    background: '#0f172a',
    color: '#38bdf8',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: 11,
    padding: 12,
    borderRadius: 8,
    marginTop: 10,
    overflowX: 'auto' as const,
    maxHeight: 220,
    whiteSpace: 'pre-wrap' as const,
  },
};

function getStatusStyle(status: DiagnosticStatus) {
  switch (status) {
    case 'PASS':
      return { background: 'rgba(34, 197, 94, 0.12)', color: '#16a34a', border: '1px solid rgba(34, 197, 94, 0.3)' };
    case 'WARNING':
    case 'PARTIAL':
      return { background: 'rgba(234, 179, 8, 0.12)', color: '#ca8a04', border: '1px solid rgba(234, 179, 8, 0.3)' };
    case 'FAIL':
      return { background: 'rgba(239, 68, 68, 0.12)', color: '#dc2626', border: '1px solid rgba(239, 68, 68, 0.3)' };
    case 'TESTING':
      return { background: 'rgba(56, 189, 248, 0.12)', color: '#0284c7', border: '1px solid rgba(56, 189, 248, 0.3)' };
    default:
      return { background: '#f1f5f9', color: '#64748b', border: '1px solid #cbd5e1' };
  }
}

function CategoryDiagnosticCard({
  cat,
  onRunSingle,
  isTesting,
}: {
  cat: DiagnosticCategoryResult;
  onRunSingle: (id: string) => void;
  isTesting: boolean;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const statusStyle = getStatusStyle(isTesting ? 'TESTING' : cat.status);

  return (
    <div style={S.card}>
      {/* Top Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20 }}>{cat.icon}</span>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13.5, fontWeight: 750, color: '#0f172a' }}>{cat.name}</span>
              <span style={{ fontSize: 10, color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>
                {cat.symbol_tested}
              </span>
              <span style={{ fontSize: 9.5, color: '#94a3b8', background: '#f8fafc', padding: '1px 5px', borderRadius: 4 }}>
                {cat.source_origin.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <div style={{ fontSize: 11.5, color: '#475569', marginTop: 2 }}>{cat.summary}</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10.5, color: '#64748b', fontFamily: 'monospace' }}>
            ⚡ {cat.latency_ms} ms
          </span>
          <span style={{ ...S.statusBadge, ...statusStyle }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
            {isTesting ? 'TESTING…' : cat.status}
          </span>
          <button
            style={S.btnSecondary}
            disabled={isTesting}
            onClick={() => onRunSingle(cat.id)}
          >
            {isTesting ? '⌛' : '▶'} Test
          </button>
        </div>
      </div>

      {/* Metric Value Chips */}
      {cat.metrics && Object.keys(cat.metrics).length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '12px 0' }}>
          {Object.entries(cat.metrics).slice(0, 6).map(([key, val]) => (
            <div key={key} style={S.metricChip}>
              <span style={S.metricLabel}>{key.replace(/_/g, ' ')}</span>
              <span style={S.metricValue}>
                {typeof val === 'number' ? (val > 1000 ? val.toLocaleString(undefined, { maximumFractionDigits: 2 }) : val) : String(val)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Field Integrity Checks */}
      {cat.field_checks && cat.field_checks.length > 0 && (
        <div style={{ background: '#f8fafc', borderRadius: 7, border: '1px solid #e2e8f0', overflow: 'hidden', marginTop: 8 }}>
          {cat.field_checks.map((fc, idx) => {
            const checkStyle = getStatusStyle(fc.status);
            return (
              <div key={idx} style={S.fieldCheckRow}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: checkStyle.color, fontWeight: 700 }}>
                    {fc.status === 'PASS' ? '✓' : fc.status === 'WARNING' ? '⚠' : '✗'}
                  </span>
                  <span style={{ fontWeight: 650, color: '#334155' }}>{fc.name}</span>
                  <span style={{ color: '#94a3b8', fontSize: 11 }}>({fc.description})</span>
                </div>
                <span style={{ fontWeight: 700, fontFamily: 'monospace', color: '#0f172a' }}>
                  {fc.value}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Troubleshooting / Error Callout */}
      {cat.error_message && (
        <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: 6, padding: '8px 12px', marginTop: 10, fontSize: 11.5, color: '#b91c1c' }}>
          <strong>Error:</strong> {cat.error_message}
        </div>
      )}

      {cat.troubleshooting_tip && (
        <div style={{ fontSize: 11, color: '#64748b', marginTop: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
          <span>💡</span> <span>{cat.troubleshooting_tip}</span>
        </div>
      )}

      {/* Raw JSON Toggle */}
      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => setShowRaw(!showRaw)}
          style={{ background: 'transparent', border: 'none', color: '#64748b', fontSize: 10.5, cursor: 'pointer', textDecoration: 'underline' }}
        >
          {showRaw ? 'Hide Raw Decoded Payload' : 'Inspect Raw Decoded JSON Payload'}
        </button>
      </div>

      {showRaw && (
        <pre style={S.rawJsonBox}>
          {JSON.stringify(cat.raw_sample || cat.metrics, null, 2)}
        </pre>
      )}
    </div>
  );
}

export function TrueDataDiagnosticsTab() {
  const { data: summary } = useTrueDataDiagnosticsSummary();
  const runDiagnostics = useRunTrueDataDiagnostics();
  const [suiteResult, setSuiteResult] = useState<DiagnosticSuiteResult | null>(null);
  const [activeTestId, setActiveTestId] = useState<string | null>(null);

  const handleRunAll = () => {
    setActiveTestId('all');
    runDiagnostics.mutate(undefined, {
      onSuccess: (data) => {
        setSuiteResult(data);
        setActiveTestId(null);
      },
      onError: () => {
        setActiveTestId(null);
      },
    });
  };

  const handleRunSingle = (categoryId: string) => {
    setActiveTestId(categoryId);
    runDiagnostics.mutate(
      { category_id: categoryId },
      {
        onSuccess: (data) => {
          if (suiteResult && data.categories.length === 1) {
            const updated = suiteResult.categories.map((c) =>
              c.id === categoryId ? data.categories[0] : c
            );
            setSuiteResult({
              ...suiteResult,
              categories: updated,
              passed_count: updated.filter((c) => c.status === 'PASS').length,
              failed_count: updated.filter((c) => c.status === 'FAIL').length,
              warning_count: updated.filter((c) => c.status === 'WARNING').length,
            });
          } else {
            setSuiteResult(data);
          }
          setActiveTestId(null);
        },
        onError: () => {
          setActiveTestId(null);
        },
      }
    );
  };

  // Initial automatic load if not yet run
  React.useEffect(() => {
    if (!suiteResult && !runDiagnostics.isPending) {
      handleRunAll();
    }
  }, []);

  const overallStyle = getStatusStyle(suiteResult?.overall_status || 'IDLE');

  return (
    <div>
      {/* Top Banner Control Center */}
      <div style={S.headerBanner}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ fontSize: 20 }}>🧪</span>
              <span style={{ fontSize: 16, fontWeight: 800, letterSpacing: -0.2 }}>
                TrueData Live Feed & Analytics Diagnostic Center
              </span>
              <span style={{ ...S.statusBadge, ...overallStyle, fontSize: 10 }}>
                {suiteResult ? `OVERALL: ${suiteResult.overall_status}` : 'READY TO RUN'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.4 }}>
              Granular real-time verification across Market Data Streams (Indices, Spot, Futures, Options) and Microstructure Analytics (Volume, Greeks, Market Profile, CVD).
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              style={S.btnPrimary}
              disabled={runDiagnostics.isPending}
              onClick={handleRunAll}
            >
              <span>{runDiagnostics.isPending ? '⏳' : '⚡'}</span>
              <span>{runDiagnostics.isPending ? 'RUNNING DIAGNOSTICS…' : 'RUN ALL FEED TESTS'}</span>
            </button>
          </div>
        </div>

        {/* Quick Health Metrics Bar */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 18, paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#cbd5e1' }}>
            <span>Status:</span>
            <span style={{ fontWeight: 700, color: summary?.authenticated ? '#4ade80' : '#f87171' }}>
              {summary?.authenticated ? `Connected (${summary.username_hint || 'TrueData'})` : 'Local Tape / Offline Mode'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#cbd5e1' }}>
            <span>Passed:</span>
            <span style={{ fontWeight: 700, color: '#4ade80' }}>
              {suiteResult?.passed_count ?? 0} / {suiteResult?.total_tests ?? 9}
            </span>
          </div>
          {suiteResult && suiteResult.warning_count > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#cbd5e1' }}>
              <span>Warnings:</span>
              <span style={{ fontWeight: 700, color: '#facc15' }}>{suiteResult.warning_count}</span>
            </div>
          )}
          {suiteResult && suiteResult.failed_count > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#cbd5e1' }}>
              <span>Failed:</span>
              <span style={{ fontWeight: 700, color: '#f87171' }}>{suiteResult.failed_count}</span>
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#cbd5e1' }}>
            <span>Execution Duration:</span>
            <span style={{ fontWeight: 700, fontFamily: 'monospace', color: '#38bdf8' }}>
              {suiteResult?.total_duration_ms ?? 0} ms
            </span>
          </div>
        </div>
      </div>

      {/* Loading Skeleton if no result */}
      {runDiagnostics.isPending && !suiteResult && (
        <div style={{ padding: 30, textAlign: 'center', color: '#64748b', fontSize: 13 }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⚡</div>
          Executing live diagnostics against TrueData feeds, options chains, and analytical models…
        </div>
      )}

      {/* Diagnostic Category Cards Grid */}
      {suiteResult?.categories.map((cat) => (
        <CategoryDiagnosticCard
          key={cat.id}
          cat={cat}
          onRunSingle={handleRunSingle}
          isTesting={activeTestId === cat.id || activeTestId === 'all'}
        />
      ))}
    </div>
  );
}
