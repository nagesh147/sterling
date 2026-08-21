import React from 'react';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import { useOrbConfig, useSetOrbEnabled } from '../../hooks/useOrbConfig';
import { useKiteQuote } from '../../hooks/useKite';
import type { OrbFeedEntry } from '../../utils/niftyOrbSignalAdapter';
import { openSettingsSection } from './config/registry';
import { EngineOffNotice } from './EngineOffNotice';
import { DepthLadder, QuoteStats } from './MarketDepthPanel';
import { AdaptiveEdgePositionCalculator } from './AdaptiveEdgePositionCalculator';
import { SignalBoard } from './board/SignalBoard';
import { StatCard } from './board/StatCard';
import { orbToBoard } from './board/orbAdapter';
import { ACTIONABLE, type BoardSignal } from './board/boardTypes';
import { k, tint } from '../../styles/kiteUI';

/**
 * ORB signal board.
 *
 * Renders through the shared `SignalBoard`, so the columns, the day grouping,
 * the row anatomy and the expand behaviour are the same ones SuperTrend and
 * Adaptive Edge use. What is specific to ORB lives in two places and only two:
 * the adapter, which decides what each column means for a bought option, and
 * `OrbTicket` below, which is the order surface.
 *
 * Candidates that did not fire sit behind one disclosure. They are real
 * information — a scan that refuses to trade must say why — but they are not a
 * call to action, and putting them in the main list buries the ones that are.
 */
function OrbTicket({ signal }: { signal: BoardSignal }) {
  const key = signal.instrument.quoteKey;
  // 'full' carries the 5-level book; fetched per contract on expand, never for
  // the whole universe, so opening a row does not subscribe 18 instruments.
  const { data } = useKiteQuote(key ? [key] : [], !!key, 5_000, 'full');
  const quote = key ? (data as Record<string, any> | undefined)?.[key] : undefined;

  return (
    <>
      <StatCard title="Position sizing & trade plan" dense>
        <AdaptiveEdgePositionCalculator
          key={signal.id}
          symbol={signal.underlying}
          tradingsymbol={signal.instrument.symbol}
          exchange={signal.instrument.exchange}
          expiry={signal.instrument.expiry ?? undefined}
          lotSize={signal.instrument.lotSize ?? undefined}
          defaultEntryPrice={signal.levels.entry ?? undefined}
          defaultSl={signal.levels.stop ?? undefined}
          defaultExit={signal.levels.target ?? undefined}
          currentLtp={quote?.last_price ?? signal.levels.ltp ?? undefined}
          optionType={(signal.instrument.optionType ?? 'CE') as 'CE' | 'PE'}
          exitState="HOLD"
        />
      </StatCard>

      <StatCard title="Market depth" summary={signal.instrument.symbol} dense>
        <DepthLadder quote={quote} />
        <QuoteStats
          quote={quote}
          extra={[{ label: 'Expiry', value: signal.instrument.expiry ?? '—' }]}
        />
      </StatCard>
    </>
  );
}

function QuietRow({ entry }: { entry: OrbFeedEntry }) {
  const color = entry.state === 'ERROR' ? k.red : k.dim;
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '5px 12px 5px 26px', borderBottom: `1px solid ${k.surface}`, fontSize: 10 }}>
      <span style={{ fontWeight: 600, color: k.text, minWidth: 82 }}>{entry.underlying}</span>
      <span style={{ color: k.dim, fontVariantNumeric: 'tabular-nums', minWidth: 62 }}>
        {entry.spot == null ? '—' : entry.spot.toFixed(2)}
      </span>
      <span style={{ color, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {entry.reason || entry.state.toLowerCase().replace(/_/g, ' ')}
      </span>
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden
      style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .14s ease', flexShrink: 0 }}>
      <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function NiftyOrbSignalsFeed({ onOpenDetail }: {
  onOpenDetail?: (signal: BoardSignal) => void;
} = {}) {
  const config = useOrbConfig();
  const setEnabled = useSetOrbEnabled();
  const enabled = config.data?.config?.enabled;
  const { signals, isLoading, error } = useOrbSignals(enabled !== false);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [showQuiet, setShowQuiet] = React.useState(false);
  // Read once per render rather than per row, so every day label in one paint
  // agrees about when "today" is.
  const nowMs = Date.now();

  if (config.isLoading) return <p style={{ padding: 12, margin: 0, fontSize: 11, color: k.dim }}>Loading ORB configuration…</p>;

  if (enabled === false) {
    return (
      <EngineOffNotice
        engine="ORB + VWAP"
        detail="The opening-range engine is switched off, so nothing is being scanned and no setups can appear here. Turning it on starts the scan; it buys calls on LONG and puts on SHORT, and never sells options."
        onEnable={() => setEnabled.mutate(true)}
        pending={setEnabled.isPending}
        onConfigure={() => openSettingsSection('orbOptions')}
        configureLabel="ORB settings"
        error={setEnabled.error ? (setEnabled.error as Error).message : null}
      />
    );
  }

  if (isLoading) return <p style={{ padding: 12, margin: 0, fontSize: 11, color: k.dim }}>Scanning ORB universe…</p>;
  if (error) return <p style={{ padding: 12, margin: 0, fontSize: 11, color: k.red }}>ORB feed unavailable: {(error as Error).message}</p>;
  if (!signals.length) {
    return (
      <EngineOffNotice
        engine="ORB universe"
        detail="ORB is on, but no underlyings are configured for it to scan. Add indices or single-stock underlyings in ORB settings."
        onConfigure={() => openSettingsSection('orbOptions')}
        configureLabel="Choose underlyings"
      />
    );
  }

  const board = signals.map(orbToBoard);
  const tradable = board.filter((s) => ACTIONABLE.includes(s.status));
  const quiet = signals.filter((s) => s.state !== 'SIGNAL');
  const failed = quiet.filter((s) => s.state === 'ERROR');

  return (
    <div>
      {failed.length === signals.length && (
        <p style={{ margin: 0, padding: '8px 12px', borderBottom: `1px solid ${k.border}`, background: tint(k.red, 8), color: k.red, fontSize: 10, lineHeight: 1.5 }}>
          Scan failed for all {failed.length} underlyings — {failed[0].reason}
        </p>
      )}

      <div style={{ padding: '7px 12px', borderBottom: `1px solid ${k.border}`, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '.06em', color: k.dim }}>BUY-ONLY · CE / PE</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: k.dim }}>
          <b style={{ color: tradable.length ? k.green : k.dim }}>{tradable.length}</b> tradable · {signals.length} scanned
        </span>
      </div>

      <SignalBoard
        signals={tradable}
        requested={['instrument', 'status', 'exchange', 'leg', 'ltp', 'entry', 'stop', 'target', 'qty', 'risk', 'time']}
        openId={openId}
        onToggle={(id) => setOpenId((prev) => (prev === id ? null : id))}
        renderDetail={(s) => <OrbTicket signal={s} />}
        onOpenDetail={onOpenDetail}
        nowMs={nowMs}
        emptyLabel="No tradable ORB setup right now. The universe is being scanned — the list below says what each underlying is waiting on."
      />

      {quiet.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowQuiet((v) => !v)}
            aria-expanded={showQuiet}
            style={{
              width: '100%', textAlign: 'left', padding: '7px 12px', cursor: 'pointer',
              border: 'none', borderTop: `1px solid ${k.border}`, borderBottom: showQuiet ? `1px solid ${k.border}` : 'none',
              background: k.surface, color: k.dim, fontFamily: 'inherit', fontSize: 9.5,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Chevron open={showQuiet} />
            {quiet.length} not signalling
            {failed.length > 0 && <span style={{ color: k.red }}>· {failed.length} errored</span>}
          </button>
          {showQuiet && quiet.map((entry) => <QuietRow key={entry.id} entry={entry} />)}
        </>
      )}
    </div>
  );
}

export default NiftyOrbSignalsFeed;
