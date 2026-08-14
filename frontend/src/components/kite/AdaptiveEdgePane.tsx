import React, { useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { AdaptiveEdgePanel, type AdaptiveEdgeRow } from './AdaptiveEdgePanel';
import { openSettingsSection } from './config/registry';
import type { AdaptiveEdgeLeg, AdaptiveEdgeSnapshot } from '../../types/adaptiveEdge';

const C = {
  text: '#444', muted: '#9b9b9b', border: '#ededed', green: '#4caf50', red: '#df514c',
  amber: '#e6a23c', blue: '#387ed1', orange: '#f06428', surface: '#fafafa',
};

const MODES = ['MICRO', 'SCALP', 'EXTENDED_SCALP', 'INTRADAY'] as const;
const THESES = ['THESIS_STRONG', 'THESIS_VALID', 'THESIS_WEAKENING', 'THESIS_INVALID'] as const;
const STAGES = ['P0_RISK_CONTROLLED', 'P1_BREAKEVEN_PROTECTED', 'P2_PROFIT_PROTECTED', 'P3_AGGRESSIVE_TRAIL'] as const;

function pretty(value: string | null | undefined) {
  if (!value) return '—';
  return value.split('_').join(' ');
}

function fmt(v: number | null | undefined, d = 2) {
  return v == null || !Number.isFinite(v) ? '—' : v.toFixed(d);
}

function asNum(v: unknown) {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function asText(v: unknown) {
  return v == null ? '—' : String(v);
}

function when(value: string | null | undefined) {
  if (!value) return '—';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString('en-IN', { hour12: false });
}

function Chip({ label, ok, tone }: { label: string; ok?: boolean; tone?: 'good' | 'warn' | 'bad' | 'quiet' }) {
  const color = tone === 'good' || ok === true ? C.green
    : tone === 'bad' ? C.red
    : tone === 'quiet' ? C.muted
    : C.amber;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 8px', borderRadius: 99, border: `1px solid ${color}44`, background: `${color}12`, color, fontSize: 10, fontWeight: 700 }}>
      <i style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
      {label}
    </span>
  );
}

function Card({ title, children, wide }: { title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <section style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: 14, background: '#fff', minWidth: 0, gridColumn: wide ? '1 / -1' : undefined }}>
      <div style={{ fontSize: 10, letterSpacing: '.08em', color: C.muted, fontWeight: 700, marginBottom: 10 }}>{title}</div>
      {children}
    </section>
  );
}

function KV({ k: key, v }: { k: string; v: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 12, padding: '4px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ color: C.muted }}>{key}</span>
      <strong style={{ color: C.text, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{v ?? '—'}</strong>
    </div>
  );
}

function Ladder({ items, current, counts }: { items: readonly string[]; current?: string | null; counts?: Record<string, number> }) {
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {items.map((item) => {
        const on = current === item;
        return (
          <span
            key={item}
            style={{
              padding: '5px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: '.03em',
              border: `1px solid ${on ? C.orange : C.border}`,
              background: on ? 'rgba(240,100,40,.08)' : C.surface,
              color: on ? C.orange : C.muted,
            }}
          >
            {pretty(item)}{counts?.[item] != null ? ` · ${counts[item]}` : ''}
          </span>
        );
      })}
    </div>
  );
}

function tableHead(cols: string[]) {
  return (
    <thead>
      <tr>
        {cols.map((h) => (
          <th key={h} style={{ textAlign: 'left', color: C.muted, fontWeight: 500, padding: '6px 8px', borderBottom: `1px solid ${C.border}`, whiteSpace: 'nowrap' }}>{h}</th>
        ))}
      </tr>
    </thead>
  );
}

function boardRow(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow {
  const session = data.session;
  return {
    id: 'research-last',
    instrument: data.settings.symbol,
    observationTime: Date.now(),
    featureQuality: data.software_complete ? 'RESEARCH COMPLETE' : 'INCOMPLETE',
    edgeScore: null,
    edgeConfidence: null,
    expectedGrossValue: data.settings.stop_points,
    executionCost: 0,
    expectedNetValue: data.settings.stop_points,
    economicallyEligible: true,
    mode: session.last_mode,
    authorizedRisk: data.settings.stop_points,
    consumedRisk: session.current_pnl ?? null,
    quantity: session.last_position_quantity,
    entryPrice: null,
    ltp: session.last_poc ?? null,
    currentPnl: session.current_pnl ?? null,
    peakPnl: session.peak_pnl ?? null,
    profitGiveback: session.profit_giveback ?? null,
    protectionState: session.last_protection_stage,
    decision: (session.last_position_quantity ?? 0) > 0 ? 'HOLD' : session.exits ? 'EXIT' : 'REJECT',
    reason: data.live_trading ? undefined : 'Display only',
    formulaIds: ['F-101', 'F-007', 'F-008', 'F-002', 'F-003'],
  };
}

export function AdaptiveEdgePane() {
  const { data, isLoading, error, refetch, isFetching } = useAdaptiveEdgeSnapshot();
  const [showAllLegs, setShowAllLegs] = useState(false);
  const session = data?.session;
  const row = data ? boardRow(data) : null;
  const legs = data?.legs ?? [];
  const visibleLegs = showAllLegs ? legs : legs.slice(-12);
  const transitions = useMemo(() => (data?.mode_transitions ?? []).slice(-8).reverse(), [data?.mode_transitions]);
  const formulas = Object.entries(data?.formula_table ?? {});
  const quality = data?.quality ?? {};
  const coverage = data?.coverage ?? {};
  const holdout = data?.holdout ?? {};
  const walk = data?.walk_forward ?? {};

  return (
    <div style={{ padding: '18px 24px 32px', width: '100%', boxSizing: 'border-box', fontFamily: k.fontFamily }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: 16 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 17, fontWeight: 400, color: C.text }}>Adaptive Edge</h2>
            <div style={{ marginTop: 4, fontSize: 11, color: C.muted }}>
              {data?.settings.symbol ?? 'NIFTY-I'} · tick-by-tick board
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {data ? (
              <>
                <Chip label={data.software_complete ? 'BOARD READY' : 'BOARD INCOMPLETE'} ok={data.software_complete} />
                <Chip label={data.production_gate_authorized ? 'ORDERS ON' : 'ORDERS OFF'} tone={data.production_gate_authorized ? 'bad' : 'warn'} />
                <Chip label={data.meets_a197 ? 'HISTORY READY' : 'WAITING ON HISTORY'} ok={data.meets_a197} />
                <Chip label={data.live_trading ? 'LIVE' : 'DISPLAY ONLY'} tone={data.live_trading ? 'bad' : 'quiet'} />
              </>
            ) : (
              <Chip label={isLoading ? 'LOADING' : 'NO SNAPSHOT'} tone="quiet" />
            )}
            <button type="button" onClick={() => refetch()} style={{ border: `1px solid ${C.border}`, background: '#fff', borderRadius: 4, padding: '5px 10px', fontSize: 11, cursor: 'pointer' }}>
              {isFetching ? 'Refreshing…' : 'Refresh'}
            </button>
            <button type="button" onClick={() => openSettingsSection('adaptiveEdge')} style={{ border: 0, background: 'transparent', color: C.blue, fontSize: 11, cursor: 'pointer' }}>
              Settings
            </button>
          </div>
        </div>

        {isLoading && <div style={{ color: C.muted, fontSize: 12, marginBottom: 12 }}>Loading Adaptive Edge snapshot…</div>}
        {error && <div style={{ color: C.red, fontSize: 12, marginBottom: 12 }}>Could not load snapshot: {String((error as Error).message)}</div>}

        {data && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 14 }}>
              <Card title="MODE LADDER">
                <Ladder items={MODES} current={session?.last_mode} counts={data.mode_counts} />
                <div style={{ marginTop: 10 }}>
                  <KV k="Horizon" v={pretty(session?.last_horizon)} />
                  <KV k="Posture" v={pretty(session?.last_operating_mode)} />
                  <KV k="Lifecycle" v={pretty(session?.lifecycle_action)} />
                </div>
              </Card>
              <Card title="THESIS / PROTECTION">
                <Ladder items={THESES} current={session?.last_thesis} />
                <div style={{ height: 8 }} />
                <Ladder items={STAGES} current={session?.last_protection_stage} />
                <div style={{ marginTop: 10 }}>
                  <KV k="Peak P&L" v={fmt(session?.peak_pnl)} />
                  <KV k="Giveback" v={fmt(session?.profit_giveback)} />
                </div>
              </Card>
              <Card title="STRUCTURE / TBT">
                <KV k="POC" v={fmt(session?.last_poc, 1)} />
                <KV k="VWAP" v={fmt(session?.last_vwap, 2)} />
                <KV k="Location" v={pretty(session?.last_location)} />
                <KV k="Opening range" v={pretty(session?.last_or_location)} />
                <KV k="POC walk" v={pretty(session?.last_poc_migration)} />
                <KV k="CVD" v={fmt(session?.last_cvd, 0)} />
                <KV k="Bar delta" v={fmt(session?.last_bar_delta, 0)} />
              </Card>
              <Card title="SESSION">
                <KV k="Entries" v={session?.entries} />
                <KV k="Exits" v={session?.exits} />
                <KV k="Re-entries" v={session?.reentries} />
                <KV k="Pyramid blocked" v={session?.blocked_pyramid} />
                <KV k="Qty" v={session?.last_position_quantity} />
                <KV k="Current P&L" v={fmt(session?.current_pnl)} />
              </Card>
            </div>

            {!!session?.last_overlays?.length && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                {session.last_overlays.map((name) => (
                  <span key={name} style={{ fontSize: 10, padding: '3px 8px', borderRadius: 99, background: '#fff6f0', color: '#c05621', border: '1px solid #f0d2c2' }}>{name}</span>
                ))}
              </div>
            )}

            {!!data.incomplete_reasons.length && (
              <Card title="INCOMPLETE">
                {data.incomplete_reasons.map((reason) => <KV key={reason} k="reason" v={reason} />)}
              </Card>
            )}

            <div style={{ border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden', marginBottom: 14, minHeight: 240 }}>
              <AdaptiveEdgePanel rows={row ? [row] : []} selectedId={row?.id} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 14 }}>
              <Card title="QUALITY">
                <KV k="Status" v={asText(quality.status)} />
                <KV k="LI valid" v={fmt(asNum(quality.li_valid_rate), 3)} />
                <KV k="Missing scores" v={fmt(asNum(quality.missing_score_rate), 4)} />
                <KV k="Missing LI" v={asText(quality.missing_liquidity_imbalance)} />
                <KV k="Missing VR" v={asText(quality.missing_volatility_ratio)} />
                <KV k="Max quote lag s" v={asText(quality.max_li_quote_lag_seconds)} />
              </Card>
              <Card title="COVERAGE">
                <KV k="Symbol" v={asText(coverage.symbol)} />
                <KV k="Days" v={asText(coverage.trading_days)} />
                <KV k="Bars" v={asText(coverage.bar_count)} />
                <KV k="Ticks" v={asText(coverage.tick_count)} />
                <KV k="Valid scores" v={asText(coverage.valid_scores)} />
                <KV k="A197" v={coverage.meets_a197 ? 'yes' : 'no'} />
              </Card>
              <Card title="WALK-FORWARD">
                <KV k="Label" v={asText(walk.label)} />
                <KV k="Train" v={asText(walk.train)} />
                <KV k="Validation" v={asText(walk.validation)} />
                <KV k="Test" v={asText(walk.test)} />
                <KV k="Ineligible" v={asText(walk.ineligible)} />
                <KV k="Overlap" v={walk.train_test_overlap ? 'yes' : 'no'} />
              </Card>
              <Card title="HOLDOUT">
                <KV k="Label" v={asText(holdout.label)} />
                <KV k="Entries" v={asText(holdout.entries)} />
                <KV k="Exits" v={asText(holdout.exits)} />
                <KV k="Test bars" v={asText(holdout.test_bar_count)} />
                <KV k="Train params only" v={holdout.used_train_params_only ? 'yes' : 'no'} />
                <KV k="Complete" v={holdout.software_complete ? 'yes' : 'no'} />
              </Card>
            </div>

            <Card title="RESEARCH LEGS" wide>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8, fontSize: 11, color: C.muted }}>
                <span>{legs.length} legs · showing {visibleLegs.length}</span>
                {legs.length > 12 && (
                  <button type="button" onClick={() => setShowAllLegs((v) => !v)} style={{ border: 0, background: 'transparent', color: C.blue, cursor: 'pointer' }}>
                    {showAllLegs ? 'Show latest 12' : 'Show all'}
                  </button>
                )}
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  {tableHead(['Date', 'Entry', 'Exit', 'Path', 'Horizon', 'Thesis', 'Protection', 'Overlays', 'Qty'])}
                  <tbody>
                    {visibleLegs.map((leg: AdaptiveEdgeLeg, index) => (
                      <tr key={`${leg.entry_time ?? index}`}>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{asText(leg.session_date)}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{when(leg.entry_time)}</td>
                        <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>{when(leg.exit_time)}</td>
                        <td style={{ padding: '6px 8px' }}>{pretty(leg.entry_mode)} → {pretty(leg.peak_mode)} → {pretty(leg.exit_mode)}</td>
                        <td style={{ padding: '6px 8px' }}>{pretty(leg.horizon)}</td>
                        <td style={{ padding: '6px 8px' }}>{pretty(leg.thesis)}</td>
                        <td style={{ padding: '6px 8px' }}>{pretty(leg.protection_stage)}</td>
                        <td style={{ padding: '6px 8px' }}>{(leg.overlays ?? []).join(', ') || '—'}</td>
                        <td style={{ padding: '6px 8px' }}>{asText(leg.quantity)}</td>
                      </tr>
                    ))}
                    {!legs.length && <tr><td colSpan={9} style={{ padding: 12, color: C.muted }}>No research legs yet. Run the research E2E script to populate this board.</td></tr>}
                  </tbody>
                </table>
              </div>
            </Card>

            <div style={{ height: 14 }} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 14 }}>
              <Card title="DAILY LEDGER">
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    {tableHead(['Date', 'Entries', 'Exits', 'Flat', 'Qty'])}
                    <tbody>
                      {(data.daily as Array<Record<string, unknown>>).map((day) => (
                        <tr key={String(day.session_date)}>
                          <td style={{ padding: '6px 8px' }}>{asText(day.session_date)}</td>
                          <td style={{ padding: '6px 8px' }}>{asText(day.entries)}</td>
                          <td style={{ padding: '6px 8px' }}>{asText(day.exits)}</td>
                          <td style={{ padding: '6px 8px' }}>{day.flattened ? 'yes' : 'no'}</td>
                          <td style={{ padding: '6px 8px' }}>{asText(day.last_quantity)}</td>
                        </tr>
                      ))}
                      {!data.daily.length && <tr><td colSpan={5} style={{ padding: 12, color: C.muted }}>No daily ledger yet.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </Card>
              <Card title="RECENT MODE WALKS">
                {transitions.map((item, index) => (
                  <KV
                    key={`${item.timestamp ?? index}`}
                    k={when(item.timestamp)}
                    v={`${pretty(item.previous_mode)} → ${pretty(item.new_mode)} · ${fmt(item.favorable_points, 1)} pts`}
                  />
                ))}
                {!transitions.length && <div style={{ color: C.muted, fontSize: 12 }}>No mode transitions in the last artifact.</div>}
              </Card>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
              <Card title="READINESS">
                {(data.readiness || []).map((item) => (
                  <KV key={item.name} k={pretty(item.name)} v={item.ready ? 'ready' : 'blocked'} />
                ))}
              </Card>
              <Card title="FORMULA REGISTRY">
                {formulas.map(([id, row]) => (
                  <KV key={id} k={id} v={pretty(row.status)} />
                ))}
                {!formulas.length && <div style={{ color: C.muted, fontSize: 12 }}>No formula table in the last artifact.</div>}
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default AdaptiveEdgePane;
