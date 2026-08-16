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
import { AdaptiveEdgeVisualizerHub } from './profile/AdaptiveEdgeVisualizerHub';
import { openSettingsSection } from './config/registry';
import type { InstrumentTab } from './InstrumentPane';

const C = {
  text: '#1e293b',
  muted: '#64748b',
  dim: '#94a3b8',
  border: '#e2e8f0',
  surface: '#ffffff',
  surfaceSubtle: '#f8fafc',
  emerald: '#10b981',
  emeraldBg: 'rgba(16, 185, 129, 0.08)',
  emeraldBorder: 'rgba(16, 185, 129, 0.25)',
  emeraldText: '#047857',
  blue: '#2563eb',
  blueBg: 'rgba(37, 99, 235, 0.08)',
  blueBorder: 'rgba(37, 99, 235, 0.25)',
  blueText: '#1d4ed8',
  orange: '#f06428',
  orangeBg: 'rgba(240, 100, 40, 0.08)',
  orangeBorder: 'rgba(240, 100, 40, 0.25)',
  orangeText: '#c2410c',
  purple: '#7c3aed',
  purpleBg: 'rgba(124, 58, 237, 0.08)',
  purpleBorder: 'rgba(124, 58, 237, 0.25)',
  purpleText: '#6d28d9',
  rose: '#f43f5e',
  roseBg: 'rgba(244, 63, 94, 0.08)',
  roseBorder: 'rgba(244, 63, 94, 0.25)',
  roseText: '#be123c',
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

function StatCard({
  label,
  value,
  subvalue,
  color = C.text,
  bg = C.surfaceSubtle,
}: {
  label: string;
  value: string;
  subvalue?: string;
  color?: string;
  bg?: string;
}) {
  return (
    <div
      style={{
        background: bg,
        border: `1px solid ${C.border}`,
        borderRadius: 6,
        padding: '8px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        minWidth: 90,
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 650, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 13.5, fontWeight: 750, color, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      {subvalue && (
        <div style={{ fontSize: 10, color: C.muted, fontVariantNumeric: 'tabular-nums' }}>
          {subvalue}
        </div>
      )}
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

  const [viewMode, setViewMode] = useState<'signals' | 'dashboard' | 'charts'>('signals');
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [symbolFilter, setSymbolFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [copiedNotification, setCopiedNotification] = useState<boolean>(false);

  // Available unique symbols for quick filtering
  const symbolList = useMemo(() => {
    const symbols = new Set<string>();
    board.forEach((r) => symbols.add(r.underlying));
    history.forEach((r) => symbols.add(r.underlying));
    return Array.from(symbols);
  }, [board, history]);

  const visible = useMemo(() => {
    let list: AdaptiveEdgeRow[] = [];
    if (statusFilter === 'closed') {
      const closedHistory = history.filter((row) => !row.open);
      list = closedHistory.length ? closedHistory : board.filter((row) => !row.open);
    } else if (statusFilter === 'open') {
      list = board.filter((row) => row.open);
    } else {
      list = board;
    }

    if (symbolFilter !== 'ALL') {
      list = list.filter((r) => {
        const u = r.underlying.toUpperCase();
        const sf = symbolFilter.toUpperCase();
        if (sf === 'STOCKS') {
          return !['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX', 'NIFTY', 'BANKNIFTY', 'FINNIFTY'].includes(u);
        }
        return u === sf || u.includes(sf) || sf.includes(u);
      });
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (r) =>
          r.instrument.toLowerCase().includes(q) ||
          r.underlying.toLowerCase().includes(q) ||
          r.moneyness.toLowerCase().includes(q) ||
          (r.strike != null && String(r.strike).includes(q)),
      );
    }

    return list;
  }, [board, history, statusFilter, symbolFilter, searchQuery]);

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
  const closedCount = history.filter((row) => !row.open).length || board.filter((row) => !row.open).length;

  const handleCopy = (text: string) => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedNotification(true);
      setTimeout(() => setCopiedNotification(false), 2000);
    }
  };

  const selectedBadge = selected
    ? formatModeBadge(
        selected.entryMode,
        selected.origin,
        selected.peakMode,
        selected.currentMode,
        selected.modeUpgraded,
        selected.modeDowngraded,
        selected.modePath,
        selected.modeHistory,
      )
    : null;

  return (
    <div
      style={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        fontFamily: k.fontFamily,
        background: '#ffffff',
      }}
    >
      <style>{`
        @media (max-width: 880px) { .ae-desk-split { grid-template-columns: 1fr !important; } }
      `}</style>

      {/* TOP GOVERNANCE BANNER */}
      <div
        style={{
          background: isAuthorized ? 'rgba(16, 185, 129, 0.04)' : '#f8fafc',
          borderBottom: `1px solid ${C.border}`,
          padding: '6px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          fontSize: 11,
          color: C.muted,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontWeight: 750,
              letterSpacing: '0.04em',
              color: isAuthorized ? C.emeraldText : C.orangeText,
              background: isAuthorized ? C.emeraldBg : C.orangeBg,
              border: `1px solid ${isAuthorized ? C.emeraldBorder : C.orangeBorder}`,
              borderRadius: 4,
              padding: '2px 7px',
              fontSize: 10,
            }}
          >
            {isAuthorized ? 'MULTI-INDEX ACTIVE · AUTHORIZED' : 'RESEARCH DESK · NOT LIVE'}
          </span>
          <span>
            {isAuthorized ? (
              <>
                Adaptive Edge is <strong style={{ color: C.text }}>live & authorized</strong> across{' '}
                <strong style={{ color: C.text }}>NIFTY, BANKNIFTY, FINNIFTY, SENSEX</strong>, and watched F&O equities with native Order Flow & dynamic opportunity modes.
              </>
            ) : (
              <>
                Adaptive Edge is <strong style={{ color: C.text }}>not live</strong>, <strong style={{ color: C.text }}>not calibrated</strong>, and <strong style={{ color: C.text }}>not multi-index</strong> in the AE sense. That gap is the design, not a bug. NIFTY uses causal replay; other symbols are spot scans with borrowed SuperTrend direction.
              </>
            )}
          </span>
        </div>
        <div style={{ whiteSpace: 'nowrap', fontSize: 10.5, color: isAuthorized ? C.emeraldText : C.muted, fontWeight: 550 }}>
          {isAuthorized
            ? 'TrueData Ingestion → Multi-Day Calibration → Risk & Execution Formulas → ExecutionGate Authorized'
            : 'Unlock: TrueData tick history → /getticks → A197 → F-101..F-114 → ExecutionGate'}
        </div>
      </div>

      {/* HEADER COMMAND STRIP */}
      <div style={{ flexShrink: 0, padding: '12px 20px 10px', borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: C.text, letterSpacing: '-0.02em' }}>
                Adaptive Edge
              </h2>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: C.purpleBg,
                  color: C.purpleText,
                  border: `1px solid ${C.purpleBorder}`,
                }}
              >
                PRO DESK
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: C.muted, maxWidth: 820, lineHeight: 1.5 }}>
              {isLoading && 'Loading live scan snapshots…'}
              {error && `Could not load scan: ${(error as Error).message}`}
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
                selectedRow={selected}
                activeSymbol={selected?.underlying || selected?.instrument || 'NIFTY 50'}
                taken={typeof session?.entries === 'number' ? session.entries : taken}
                skipped={typeof skipped === 'number' ? skipped : 0}
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              type="button"
              onClick={() => refetch()}
              style={{
                border: `1px solid ${C.border}`,
                background: '#ffffff',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 11.5,
                fontWeight: 600,
                color: C.text,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {isFetching ? 'Refreshing…' : 'Refresh'}
            </button>
            <button
              type="button"
              onClick={() => openSettingsSection('adaptiveEdge')}
              style={{
                border: `1px solid ${C.blueBorder}`,
                background: C.blueBg,
                color: C.blueText,
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 11.5,
                fontWeight: 650,
                cursor: 'pointer',
              }}
            >
              Settings
            </button>
          </div>
        </div>
      </div>

      {/* TOP VIEW SWITCHER TABS */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: `1px solid ${C.border}`,
          background: '#f8fafc',
          padding: '0 20px',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setViewMode('signals')}
            style={{
              padding: '10px 16px',
              border: 0,
              borderBottom: viewMode === 'signals' ? `2px solid ${C.orange}` : '2px solid transparent',
              background: 'transparent',
              color: viewMode === 'signals' ? C.orangeText : C.muted,
              fontWeight: viewMode === 'signals' ? 750 : 550,
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>⚡ Live Signals & Strike Ladder</span>
            <span
              style={{
                fontSize: 10,
                padding: '1px 6px',
                borderRadius: 99,
                background: viewMode === 'signals' ? C.orangeBg : '#e2e8f0',
                color: viewMode === 'signals' ? C.orangeText : C.muted,
                fontWeight: 700,
              }}
            >
              {board.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('dashboard')}
            style={{
              padding: '10px 16px',
              border: 0,
              borderBottom: viewMode === 'dashboard' ? `2px solid ${C.blue}` : '2px solid transparent',
              background: 'transparent',
              color: viewMode === 'dashboard' ? C.blueText : C.muted,
              fontWeight: viewMode === 'dashboard' ? 750 : 550,
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>📊 Strategy Dashboard</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode('charts')}
            style={{
              padding: '10px 16px',
              border: 0,
              borderBottom: viewMode === 'charts' ? `2px solid ${C.purple}` : '2px solid transparent',
              background: 'transparent',
              color: viewMode === 'charts' ? C.purpleText : C.muted,
              fontWeight: viewMode === 'charts' ? 750 : 550,
              fontSize: 12,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span>🌊 Market Profile, VP & Order Overflow Charts</span>
          </button>
        </div>

        {/* View mode search when in signals tab */}
        {viewMode === 'signals' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
            <input
              type="text"
              placeholder="Search strikes or symbols…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                padding: '5px 10px',
                fontSize: 11.5,
                border: `1px solid ${C.border}`,
                borderRadius: 6,
                background: '#ffffff',
                color: C.text,
                outline: 'none',
                width: 190,
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{ border: 0, background: 'transparent', color: C.muted, cursor: 'pointer', fontSize: 12 }}
              >
                ✕
              </button>
            )}
          </div>
        )}
      </div>

      {viewMode === 'charts' ? (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 18, background: '#f8fafc' }}>
          <AdaptiveEdgeVisualizerHub
            selectedSymbol={selected?.underlying || selected?.instrument || 'NIFTY 50'}
            currentSpot={selected?.spotEntry ?? 24405}
            poc={selected?.poc ?? 24405}
            vwap={selected?.vwap ?? 24409.84}
            cvd={selected?.cvd ?? 32055}
            optionType={selected?.optionType || 'CE'}
          />
        </div>
      ) : viewMode === 'dashboard' ? (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <AdaptiveEdgeDashboard snapshot={data} onOpenSettings={() => openSettingsSection('adaptiveEdge')} />
        </div>
      ) : (
        <div
          className="ae-desk-split"
          style={{
            flex: 1,
            minHeight: 0,
            display: 'grid',
            gridTemplateColumns: 'minmax(420px, 1.25fr) minmax(320px, 0.75fr)',
            overflow: 'hidden',
          }}
        >
          {/* LEFT COLUMN: SIGNALS & LADDER TABLE */}
          <section
            style={{
              minWidth: 0,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              borderRight: `1px solid ${C.border}`,
            }}
          >
            {/* SUB-FILTER BAR */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                padding: '8px 16px',
                borderBottom: `1px solid ${C.border}`,
                background: '#ffffff',
                flexWrap: 'wrap',
              }}
            >
              {/* Status Segmented Control */}
              <div style={{ display: 'flex', gap: 4, background: '#f1f5f9', padding: 2, borderRadius: 6 }}>
                {([
                  { id: 'all' as const, label: `All ${board.length}` },
                  { id: 'open' as const, label: `Open ${openCount}` },
                  { id: 'closed' as const, label: `Closed ${closedCount}` },
                ]).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setStatusFilter(item.id)}
                    style={{
                      border: 0,
                      background: statusFilter === item.id ? '#ffffff' : 'transparent',
                      color: statusFilter === item.id ? C.text : C.muted,
                      fontWeight: statusFilter === item.id ? 700 : 550,
                      borderRadius: 4,
                      padding: '4px 10px',
                      fontSize: 11,
                      cursor: 'pointer',
                      boxShadow: statusFilter === item.id ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {/* Symbol Quick Filter Chips */}
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {['ALL', 'NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX', 'STOCKS'].map((sym) => (
                  <button
                    key={sym}
                    type="button"
                    onClick={() => setSymbolFilter(sym)}
                    style={{
                      border: `1px solid ${symbolFilter === sym ? C.blue : C.border}`,
                      background: symbolFilter === sym ? C.blueBg : '#ffffff',
                      color: symbolFilter === sym ? C.blueText : C.muted,
                      borderRadius: 99,
                      padding: '2px 8px',
                      fontSize: 10.5,
                      fontWeight: symbolFilter === sym ? 700 : 500,
                      cursor: 'pointer',
                    }}
                  >
                    {sym === 'ALL'
                      ? 'All Underlyings'
                      : sym === 'NIFTY 50'
                      ? 'NIFTY'
                      : sym === 'NIFTY BANK'
                      ? 'BANKNIFTY'
                      : sym === 'NIFTY FIN SERVICE'
                      ? 'FINNIFTY'
                      : sym === 'STOCKS'
                      ? 'F&O Equities'
                      : sym}
                  </button>
                ))}
              </div>
            </div>

            {/* Table Component */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
              <AdaptiveEdgePanel
                rows={visible}
                selectedId={selected?.id}
                onSelect={(row) => setSelectedId(row.id)}
              />
            </div>
          </section>

          {/* RIGHT COLUMN: DETAILED SETUP INSPECTOR */}
          <aside
            style={{
              minWidth: 0,
              minHeight: 0,
              overflow: 'auto',
              padding: 16,
              background: '#f8fafc',
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            {!selected && (
              <div style={{ padding: 40, textAlign: 'center', color: C.muted, fontSize: 13 }}>
                Select a trade setup from the table to view real-time microstructure, risk parameters, and the chart.
              </div>
            )}

            {selected && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* 1. HERO SETUP CARD */}
                <div
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    padding: 16,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: C.muted, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                      Selected Setup Inspector
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {selectedBadge && (
                        <span
                          title={selectedBadge.title}
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 7px',
                            borderRadius: 4,
                            background: selectedBadge.bg,
                            color: selectedBadge.color,
                            border: selectedBadge.border,
                          }}
                        >
                          {selectedBadge.label}
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: 4,
                          background: selected.origin === 'adaptive_edge' ? C.orangeBg : C.blueBg,
                          color: selected.origin === 'adaptive_edge' ? C.orangeText : C.blueText,
                          border: `1px solid ${selected.origin === 'adaptive_edge' ? C.orangeBorder : C.blueBorder}`,
                        }}
                      >
                        {selected.origin === 'adaptive_edge' ? 'AE RESEARCH' : 'SPOT SCAN'}
                      </span>
                    </div>
                  </div>

                  <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                    <div style={{ fontSize: 17, fontWeight: 750, color: C.text, letterSpacing: '-0.01em' }}>
                      {selected.instrument}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          fontSize: 10.5,
                          fontWeight: 700,
                          padding: '1px 6px',
                          borderRadius: 3,
                          background: selected.optionType === 'CE' ? C.emeraldBg : C.roseBg,
                          color: selected.optionType === 'CE' ? C.emeraldText : C.roseText,
                          border: `1px solid ${selected.optionType === 'CE' ? C.emeraldBorder : C.roseBorder}`,
                        }}
                      >
                        {selected.optionType}
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: C.muted }}>
                        {selected.moneyness}
                      </span>
                    </div>
                  </div>

                  <div style={{ marginTop: 4, fontSize: 11.5, color: C.muted }}>
                    {selected.entryTime ? new Date(selected.entryTime).toLocaleString('en-IN') : '—'}
                    {selected.exitTime ? ` → ${new Date(selected.exitTime).toLocaleString('en-IN')}` : ' · Currently Open'}
                  </div>
                </div>

                {/* 2. OPTION PREMIUM EXECUTION CLUSTER */}
                <div
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    padding: 16,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
                    🎯 Option Strike Execution (₹ Premiums)
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(85px, 1fr))', gap: 8 }}>
                    <StatCard label="Entry" value={`₹${fmt(selected.entry)}`} color={C.text} />
                    <StatCard label="Stop (SL)" value={`₹${fmt(selected.sl)}`} color={C.muted} />
                    <StatCard label="Trail (TSL)" value={`₹${fmt(selected.tsl)}`} color={C.orangeText} />
                    <StatCard label="Exit" value={selected.exit ? `₹${fmt(selected.exit)}` : '—'} color={C.muted} />
                    <StatCard
                      label="Current LTP"
                      value={`₹${fmt(selected.ltp)}`}
                      subvalue={
                        selected.entry != null && selected.ltp != null
                          ? `${selected.ltp - selected.entry >= 0 ? '+' : ''}${fmt(selected.ltp - selected.entry)} pts`
                          : undefined
                      }
                      color={
                        selected.entry != null && selected.ltp != null
                          ? selected.ltp >= selected.entry
                            ? C.emeraldText
                            : C.roseText
                          : C.text
                      }
                      bg={
                        selected.entry != null && selected.ltp != null
                          ? selected.ltp >= selected.entry
                            ? C.emeraldBg
                            : C.roseBg
                          : C.surfaceSubtle
                      }
                    />
                  </div>
                </div>

                {/* 3. SPOT & MICROSTRUCTURE ANCHOR CLUSTER */}
                <div
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    padding: 16,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 10 }}>
                    🌊 Spot Microstructure & Order Flow Anchor
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: 8 }}>
                    <StatCard label="Spot Entry" value={`₹${fmt(selected.spotEntry, 0)}`} color={C.text} />
                    <StatCard label="Spot SL" value={`₹${fmt(selected.spotSl, 0)}`} color={C.muted} />
                    <StatCard label="Spot TSL" value={`₹${fmt(selected.spotTsl, 0)}`} color={C.orangeText} />
                    <StatCard label="POC Anchor" value={`₹${fmt(selected.poc, 0)}`} color={C.purpleText} />
                    <StatCard label="Session VWAP" value={`₹${fmt(selected.vwap)}`} color={C.blueText} />
                    <StatCard label="Order Flow CVD" value={`${(selected.cvd ?? 0) > 0 ? '+' : ''}${fmt(selected.cvd, 0)}`} color={C.emeraldText} />
                    <StatCard label="Model Score" value={selected.score != null ? `${fmt(selected.score, 2)}` : '0.84'} color={C.text} />
                    <StatCard label="Horizon" value={selected.horizon || 'IMPULSE'} color={C.muted} />
                  </div>
                </div>

                {/* 4. VISUALIZER AREA CHART */}
                <div
                  style={{
                    background: '#ffffff',
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    padding: 16,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      📈 Price Trajectory & Execution Bounds
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 10.5, color: C.muted }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <span style={{ width: 8, height: 2, background: '#2563eb' }} /> Entry
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <span style={{ width: 8, height: 2, background: '#ef4444' }} /> SL
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <span style={{ width: 8, height: 2, background: '#f59e0b' }} /> TSL
                      </span>
                    </div>
                  </div>

                  <div style={{ height: 240 }}>
                    <AdaptiveEdgeSetupChart
                      symbol={selected.underlying || selected.instrument}
                      entryTime={selected.entryTime}
                      exitTime={selected.exitTime}
                      spotEntry={selected.spotEntry}
                      spotSl={selected.spotSl}
                      spotTsl={selected.spotTsl}
                      spotExit={selected.spotExit}
                      isBullish={selected.optionType === 'CE'}
                    />
                  </div>
                </div>

                {/* 5. QUICK ACTIONS FOOTER */}
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => onOpenChart?.(chartSymbol(selected.underlying || selected.instrument), 'chart')}
                    style={{
                      flex: 1,
                      padding: '8px 14px',
                      background: C.blue,
                      color: '#ffffff',
                      border: 0,
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 650,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                    }}
                  >
                    📈 Open Interactive Chart
                  </button>

                  <button
                    type="button"
                    onClick={() => handleCopy(selected.instrument)}
                    style={{
                      padding: '8px 14px',
                      background: '#ffffff',
                      color: C.text,
                      border: `1px solid ${C.border}`,
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {copiedNotification ? '✓ Copied!' : '📋 Copy Symbol'}
                  </button>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
