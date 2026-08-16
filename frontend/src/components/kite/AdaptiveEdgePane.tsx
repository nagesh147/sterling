import React, { useEffect, useMemo, useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import {
  AdaptiveEdgePanel,
  fmt,
  formatModeBadge,
  historyRowsFromSnapshot,
  rowsFromSnapshot,
  watchedSignals,
  when,
  type AdaptiveEdgeRow,
} from './AdaptiveEdgePanel';
import { AdaptiveEdgeMetricsStrip } from './AdaptiveEdgeMetricsStrip';
import { AdaptiveEdgeSetupChart } from './AdaptiveEdgeSetupChart';
import { AdaptiveEdgeDashboard } from './AdaptiveEdgeDashboard';
import { openSettingsSection } from './config/registry';
import type { InstrumentTab } from './InstrumentPane';

const C = {
  text: '#444', muted: '#9b9b9b', border: '#ededed', green: '#4caf50',
  blue: '#387ed1', orange: '#f06428',
};

function chartSymbol(symbol: string) {
  if (symbol === 'NIFTY-I' || symbol === 'NIFTY' || symbol === 'NIFTY 50') return 'NSE:NIFTY 50';
  if (symbol === 'BANKNIFTY-I' || symbol === 'BANKNIFTY' || symbol === 'NIFTY BANK') return 'NSE:NIFTY BANK';
  if (symbol === 'FINNIFTY-I' || symbol === 'FINNIFTY' || symbol === 'NIFTY FIN SERVICE') return 'NSE:NIFTY FIN SERVICE';
  if (symbol === 'SENSEX-I' || symbol === 'SENSEX') return 'BSE:SENSEX';
  return symbol.includes(':') ? symbol : `NSE:${symbol}`;
}

export function playNotificationSound(type: 'upgrade' | 'downgrade' | 'exit') {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    const now = ctx.currentTime;
    if (type === 'upgrade') {
      osc.frequency.setValueAtTime(587.33, now); // D5
      osc.frequency.exponentialRampToValueAtTime(880.00, now + 0.15); // A5
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else if (type === 'downgrade') {
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.exponentialRampToValueAtTime(392.00, now + 0.2); // G4
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.start(now);
      osc.stop(now + 0.35);
    } else {
      osc.frequency.setValueAtTime(440, now);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.start(now);
      osc.stop(now + 0.25);
    }
  } catch {
    // Audio context not allowed without interaction
  }
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 88 }}>
      <div style={{ fontSize: 10, color: C.muted, letterSpacing: '.04em', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ marginTop: 2, fontSize: 14, fontWeight: 650, fontVariantNumeric: 'tabular-nums', color: C.text }}>{value}</div>
    </div>
  );
}

export function AdaptiveEdgePane({
  onOpenChart,
}: {
  onOpenChart?: (symbol: string, tab: InstrumentTab | 'chart' | 'option-chain') => void;
}) {
  const { data, isLoading, error, refetch, isFetching } = useAdaptiveEdgeSnapshot();
  const isAuthorized = Boolean(data?.production_gate_authorized);
  const board = data ? rowsFromSnapshot(data) : [];
  const history = data ? historyRowsFromSnapshot(data) : [];
  const watched = data ? watchedSignals(data) : [];
  const [viewMode, setViewMode] = useState<'signals' | 'dashboard'>('signals');
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visible = useMemo(() => {
    if (filter === 'closed') {
      const closedHistory = history.filter((row) => !row.open);
      return closedHistory.length ? closedHistory : board.filter((row) => !row.open);
    }
    if (filter === 'open') return board.filter((row) => row.open);
    return board;
  }, [board, filter, history]);

  useEffect(() => {
    if (!visible.some((row) => row.id === selectedId)) {
      setSelectedId(visible[0]?.id ?? null);
    }
  }, [visible, selectedId]);

  const selected: AdaptiveEdgeRow | undefined = visible.find((row) => row.id === selectedId) ?? visible[0];
  const session = data?.session;
  const coverage = data?.coverage ?? {};
  const scannedNames = Array.from(new Set((data?.signals ?? []).filter((item) => item.scanned).map((item) => item.underlying)));
  const allNames = Array.from(new Set((data?.signals ?? []).map((item) => item.underlying)));
  const watchedNames = (scannedNames.length ? scannedNames : allNames).join(', ') || (data?.settings.symbol ?? 'NIFTY-I');
  const days = typeof coverage.trading_days === 'number' ? coverage.trading_days : null;
  const skipped = session?.blocked_pyramid ?? 0;
  const taken = history.length || board.length;
  const openCount = board.filter((row) => row.open).length;

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', fontFamily: k.fontFamily, background: '#fff' }}>
      <style>{`@media (max-width: 860px) { .ae-desk { grid-template-columns: 1fr !important; } }`}</style>
      <div style={{ background: isAuthorized ? 'rgba(0,168,107,.04)' : '#fafafa', borderBottom: `1px solid ${C.border}`, padding: '7px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, fontSize: 11, color: C.muted, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontWeight: 700,
            letterSpacing: '0.04em',
            color: isAuthorized ? '#00875a' : C.orange,
            background: isAuthorized ? 'rgba(0,135,90,.1)' : 'rgba(240,100,40,.1)',
            border: isAuthorized ? '1px solid rgba(0,135,90,.25)' : '1px solid rgba(240,100,40,.25)',
            borderRadius: 3,
            padding: '1px 6px',
            fontSize: 10,
          }}>
            {isAuthorized ? 'MULTI-INDEX ACTIVE · AUTHORIZED' : 'RESEARCH DESK · NOT LIVE'}
          </span>
          <span>
            {isAuthorized ? (
              <>
                Adaptive Edge is <strong style={{ color: C.text }}>live & authorized</strong> across <strong style={{ color: C.text }}>NIFTY, BANKNIFTY, FINNIFTY, and SENSEX</strong> with native microstructure (POC, VWAP, Order Flow) and dynamic opportunity modes.
              </>
            ) : (
              <>
                Adaptive Edge is <strong style={{ color: C.text }}>not live</strong>, <strong style={{ color: C.text }}>not calibrated</strong>, and <strong style={{ color: C.text }}>not multi-index</strong> in the AE sense. That gap is the design, not a bug. NIFTY uses causal replay; other symbols are spot scans with borrowed SuperTrend direction.
              </>
            )}
          </span>
        </div>
        <div style={{ whiteSpace: 'nowrap', fontSize: 10.5, color: isAuthorized ? '#00875a' : C.muted }}>
          {isAuthorized ? 'TrueData Ingestion → Multi-Day Calibration → Risk & Execution Formulas → ExecutionGate Authorized' : 'Unlock: TrueData tick history → /getticks → A197 → F-101..F-114 → ExecutionGate'}
        </div>
      </div>

      <div style={{ flexShrink: 0, padding: '14px 22px 12px', borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: C.text }}>Adaptive Edge</h2>
            <p style={{ margin: '5px 0 0', fontSize: 12, color: C.muted, maxWidth: 760, lineHeight: 1.5 }}>
              {isLoading && 'Loading the last scan…'}
              {error && `Could not load the last scan: ${(error as Error).message}`}
              {data && (
                <>
                  Scanned <strong style={{ color: C.text, fontWeight: 650 }}>{watchedNames}</strong>
                  {days != null && <> across {days} session{days === 1 ? '' : 's'}</>}.
                  {openCount ? ` ${openCount} option row${openCount === 1 ? '' : 's'} still open.` : ''}
                </>
              )}
            </p>
            {data && (
              <AdaptiveEdgeMetricsStrip
                session={session}
                watched={watched}
                taken={typeof session?.entries === 'number' ? session.entries : taken}
                skipped={typeof skipped === 'number' ? skipped : 0}
              />
            )}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" onClick={() => refetch()} style={{ border: `1px solid ${C.border}`, background: '#fff', borderRadius: 4, padding: '6px 10px', fontSize: 11, cursor: 'pointer' }}>
              {isFetching ? 'Refreshing…' : 'Refresh'}
            </button>
            <button type="button" onClick={() => openSettingsSection('adaptiveEdge')} style={{ border: 0, background: 'transparent', color: C.blue, fontSize: 11, cursor: 'pointer' }}>
              Settings
            </button>
          </div>
        </div>
      </div>

      {/* Top View Mode Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', borderBottom: `1px solid ${C.border}`, background: '#fafafa', padding: '0 22px' }}>
        <button
          type="button"
          onClick={() => setViewMode('signals')}
          style={{
            padding: '10px 16px',
            border: 0,
            borderBottom: viewMode === 'signals' ? `2px solid ${C.orange}` : '2px solid transparent',
            background: 'transparent',
            color: viewMode === 'signals' ? C.orange : C.muted,
            fontWeight: viewMode === 'signals' ? 700 : 500,
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          ⚡ Live Signals & Option Ladder
        </button>
        <button
          type="button"
          onClick={() => setViewMode('dashboard')}
          style={{
            padding: '10px 16px',
            border: 0,
            borderBottom: viewMode === 'dashboard' ? `2px solid ${C.blue}` : '2px solid transparent',
            background: 'transparent',
            color: viewMode === 'dashboard' ? C.blue : C.muted,
            fontWeight: viewMode === 'dashboard' ? 700 : 500,
            fontSize: 12,
            cursor: 'pointer',
          }}
        >
          📊 Microstructure & Strategy Dashboard
        </button>
      </div>

      {viewMode === 'dashboard' ? (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <AdaptiveEdgeDashboard
            snapshot={data}
            onOpenSettings={() => openSettingsSection('adaptiveEdge')}
          />
        </div>
      ) : (
        <div className="ae-desk" style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: 'minmax(360px, 1.15fr) minmax(280px, .85fr)', overflow: 'hidden' }}>
          <section style={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', borderRight: `1px solid ${C.border}` }}>
            <div style={{ display: 'flex', gap: 6, padding: '10px 16px', borderBottom: `1px solid ${C.border}` }}>
              {([
                { id: 'all' as const, label: `All ${board.length}` },
                { id: 'open' as const, label: `Open ${openCount}` },
                { id: 'closed' as const, label: `Closed ${history.filter((row) => !row.open).length || board.filter((row) => !row.open).length}` },
              ]).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setFilter(item.id)}
                  style={{
                    border: `1px solid ${filter === item.id ? C.orange : C.border}`,
                    background: filter === item.id ? 'rgba(240,100,40,.08)' : '#fff',
                    color: filter === item.id ? C.orange : C.muted,
                    borderRadius: 99, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <AdaptiveEdgePanel
              rows={visible}
              selectedId={selected?.id}
              onSelect={(row) => setSelectedId(row.id)}
            />
          </div>
        </section>

        <aside style={{ minWidth: 0, minHeight: 0, overflow: 'auto', padding: 16, background: '#fcfcfc' }}>
          {!selected && <div style={{ color: C.muted, fontSize: 12 }}>Select a setup to see the numbers and the chart.</div>}
          {selected && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minHeight: '100%' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div style={{ fontSize: 11, color: C.muted, letterSpacing: '.04em', textTransform: 'uppercase' }}>This setup</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {(() => {
                      const badge = formatModeBadge(
                        selected.entryMode,
                        selected.origin,
                        selected.peakMode,
                        selected.currentMode,
                        selected.modeUpgraded,
                        selected.modeDowngraded,
                        selected.modePath,
                        selected.modeHistory,
                      );
                      return (
                        <span
                          title={badge.title}
                          style={{
                            fontSize: 9.5,
                            fontWeight: 750,
                            letterSpacing: '0.04em',
                            padding: '2px 6px',
                            borderRadius: 3,
                            background: badge.bg,
                            color: badge.color,
                            border: badge.border,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {badge.label}
                        </span>
                      );
                    })()}
                    {selected.origin === 'adaptive_edge' ? (
                      <span style={{ fontSize: 9.5, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'rgba(240,100,40,.12)', color: k.orange, border: '1px solid rgba(240,100,40,.25)' }}>
                        AE RESEARCH (NIFTY)
                      </span>
                    ) : (
                      <span style={{ fontSize: 9.5, fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'rgba(65,132,243,.10)', color: k.blue, border: '1px solid rgba(65,132,243,.25)' }}>
                        SPOT SCAN (ST)
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ marginTop: 4, fontSize: 16, fontWeight: 650, color: C.text }}>{selected.instrument}</div>
                <div style={{ marginTop: 4, fontSize: 12, color: C.muted }}>
                  {selected.entryTime ? new Date(selected.entryTime).toLocaleString('en-IN') : '—'}
                  {selected.exitTime ? ` → ${new Date(selected.exitTime).toLocaleString('en-IN')}` : ' · still open'}
                </div>
              </div>

              {(() => {
                const badge = formatModeBadge(
                  selected.entryMode,
                  selected.origin,
                  selected.peakMode,
                  selected.currentMode,
                  selected.modeUpgraded,
                  selected.modeDowngraded,
                  selected.modePath,
                  selected.modeHistory,
                );
                return (
                  <div style={{ padding: '8px 12px', background: badge.bg, border: badge.border, borderRadius: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 750, color: badge.color, letterSpacing: '.04em' }}>
                        {badge.isUpgraded ? `▲ SIGNAL UPGRADED: ${badge.label}` : badge.isDowngraded ? `▼ SIGNAL DOWNGRADED: ${badge.label}` : `SIGNAL TYPE: ${badge.label}`}
                      </span>
                      <span style={{ fontSize: 10, color: C.muted, fontWeight: 600 }}>{selected.horizon || 'IMPULSE'}</span>
                    </div>
                    <div style={{ fontSize: 11, color: C.text, marginTop: 3 }}>
                      {badge.title}
                    </div>
                    {badge.history && badge.history.length > 1 && (
                      <div style={{ marginTop: 6, paddingTop: 6, borderTop: `1px dashed ${badge.isDowngraded ? 'rgba(239, 68, 68, 0.3)' : 'rgba(22, 163, 74, 0.3)'}`, fontSize: 10.5, color: badge.isDowngraded ? '#991b1b' : '#166534', display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <strong>Lifecycle Path:</strong>
                          {badge.history.map((step, idx) => (
                            <span key={step} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                              <span style={{ padding: '1px 5px', borderRadius: 3, background: idx === badge.history!.length - 1 ? (badge.isDowngraded ? 'rgba(239,68,68,.2)' : 'rgba(22,163,74,.2)') : 'rgba(0,0,0,.06)', fontWeight: 700 }}>
                                {step}
                              </span>
                              {idx < badge.history!.length - 1 && (
                                <span style={{ color: C.muted, fontWeight: 700 }}>{badge.isDowngraded ? '↘' : '↗'}</span>
                              )}
                            </span>
                          ))}
                        </div>
                        <div style={{ display: 'flex', gap: 12, marginTop: 2 }}>
                          <span><strong>Entry:</strong> {badge.entryLabel}</span>
                          <span><strong>Current:</strong> {badge.promotedLabel}</span>
                          <span><strong>Trigger:</strong> {badge.isDowngraded ? 'Giveback / decay protection' : 'Continuous favorable expansion'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {(() => {
                const liveLtp = selected.ltp;
                const entryDiff = (liveLtp != null && selected.entry != null) ? liveLtp - selected.entry : null;
                const entryVal = selected.entry != null
                  ? `${fmt(selected.entry)}${entryDiff != null && Math.abs(entryDiff) > 0.001 ? ` (${entryDiff > 0 ? '+' : ''}${fmt(entryDiff)})` : ''}`
                  : '—';
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                    <Metric label="Entry" value={entryVal} />
                    <Metric label="SL" value={fmt(selected.sl)} />
                    <Metric label="TSL" value={fmt(selected.tsl)} />
                    <Metric label="Exit" value={fmt(selected.exit)} />
                  </div>
                );
              })()}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                <Metric label="Spot" value={fmt(selected.spotEntry, 0)} />
                <Metric label="Spot SL" value={fmt(selected.spotSl, 0)} />
                <Metric label="Spot TSL" value={fmt(selected.spotTsl, 0)} />
                <Metric label="LTP" value={fmt(selected.ltp)} />
              </div>
              {selected.origin === 'adaptive_edge' ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}>
                  <Metric label="Score" value={fmt(selected.score)} />
                  <Metric label="POC" value={fmt(selected.poc, 0)} />
                  <Metric label="VWAP" value={fmt(selected.vwap)} />
                  <Metric label="CVD" value={fmt(selected.cvd, 0)} />
                </div>
              ) : (
                <div style={{ fontSize: 11.5, color: C.muted, fontStyle: 'italic', padding: '6px 8px', background: '#f5f5f5', borderRadius: 4, border: `1px solid ${C.border}` }}>
                  Spot scan: direction borrowed from SuperTrend. No AE causal model, POC, or CVD evaluated.
                </div>
              )}

              {selected.resolutionReason && (
                <p style={{ margin: 0, fontSize: 12, color: C.muted }}>{selected.resolutionReason}</p>
              )}
              {selected.whyClosed && (
                <p style={{ margin: 0, fontSize: 12, color: C.muted }}>{selected.whyClosed}</p>
              )}

              <div style={{ flex: 1, minHeight: 240 }}>
                <AdaptiveEdgeSetupChart
                  symbol={selected.tapeSymbol || selected.underlying}
                  entryTime={selected.entryTime}
                  exitTime={selected.exitTime}
                />
              </div>

              {onOpenChart && (
                <button
                  type="button"
                  onClick={() => onOpenChart(chartSymbol(selected.tapeSymbol || selected.underlying), 'chart')}
                  style={{ alignSelf: 'flex-start', border: 0, background: 'transparent', color: C.blue, fontSize: 12, cursor: 'pointer', padding: 0 }}
                >
                  Open full chart
                </button>
              )}
            </div>
          )}
        </aside>
      </div>
      )}
    </div>
  );
}

export default AdaptiveEdgePane;
