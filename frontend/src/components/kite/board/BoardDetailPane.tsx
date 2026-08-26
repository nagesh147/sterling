/**
 * One signal, full width, whichever engine produced it.
 *
 * The inline expand on the board is a ticket: enough to decide and act without
 * losing your place in the list. This is the other thing — the whole record of
 * a signal, with room for the book, the sizing, and every piece of evidence the
 * engine kept.
 *
 * It renders from `BoardSignal` alone, so an engine gets a detail page by
 * having an adapter, not by having a page written for it. SuperTrend keeps its
 * own older pane for now because that one fetches a richer server-side detail
 * record; when its board moves onto BoardSignal, this replaces it.
 */
import React from 'react';
import { useKiteQuote } from '../../../hooks/useKite';
import { DepthLadder, QuoteStats } from '../MarketDepthPanel';
import { AdaptiveEdgePositionCalculator } from '../AdaptiveEdgePositionCalculator';
import { StatCard, StatCardGrid, type Stat } from './StatCard';
import { ENGINE_LABEL, STATUS_LABEL, type BoardSignal, type BoardStatus } from './boardTypes';
import { k, tint } from '../../../styles/kiteUI';

const STATUS_TONE: Record<BoardStatus, string> = {
  armed: k.blue, running: k.green, weakening: k.amber,
  ended: k.dim, watching: k.dim, error: k.red,
};

const px = (v: number | null | undefined, dp = 2) =>
  v == null || !Number.isFinite(v) ? '—' : v.toFixed(dp);

const inr = (v: number | null | undefined) =>
  v == null || !Number.isFinite(v) ? '—' : `₹${Math.round(v).toLocaleString('en-IN')}`;

/**
 * Reward against risk, from the levels the engine published.
 *
 * Only computed when entry, stop and target are all real — a partial ladder
 * gives a ratio that looks authoritative and means nothing.
 */
function riskReward(signal: BoardSignal): string | undefined {
  const { entry, stop, target } = signal.levels;
  if (entry == null || stop == null || target == null) return undefined;
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return undefined;
  return `${(Math.abs(target - entry) / risk).toFixed(2)}R`;
}

function Header({ signal, onClose }: { signal: BoardSignal; onClose: () => void }) {
  const tone = signal.direction === 'long' ? k.green : k.red;
  const statusTone = STATUS_TONE[signal.status];
  return (
    <header style={{
      display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
      padding: '10px 16px', borderBottom: `1px solid ${k.border}`, background: k.bg,
    }}>
      <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: k.text }}>{signal.underlying}</h2>
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '.05em', color: tone,
        background: tint(tone, 12), border: `1px solid ${tint(tone, 35)}`, borderRadius: 3, padding: '1px 5px',
      }}>
        {signal.instrument.optionType ?? signal.instrument.kind.toUpperCase()} · {signal.direction.toUpperCase()}
      </span>
      <span style={{
        fontSize: 9, fontWeight: 700, letterSpacing: '.05em', color: statusTone,
        background: tint(statusTone, 12), border: `1px solid ${tint(statusTone, 35)}`, borderRadius: 3, padding: '1px 5px',
      }}>
        {STATUS_LABEL[signal.status]}
      </span>
      <span style={{ fontSize: 11, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
        {signal.instrument.exchange}:{signal.instrument.symbol}
      </span>
      <span style={{ fontSize: 10, color: k.dim, marginLeft: 'auto' }}>
        {ENGINE_LABEL[signal.engine]}
        {signal.atMs != null && ` · ${new Date(signal.atMs).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })}`}
      </span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close detail"
        className="sb-tool"
        style={{
          width: 24, height: 24, border: `1px solid ${k.border}`, borderRadius: 4,
          background: k.bg, color: k.dim, cursor: 'pointer', fontSize: 13, lineHeight: 1,
        }}
      >
        ×
      </button>
    </header>
  );
}

export function BoardDetailPane({ signal, onClose }: { signal: BoardSignal; onClose: () => void }) {
  const key = signal.instrument.quoteKey;
  const { data } = useKiteQuote(key ? [key] : [], !!key, 5_000, 'full');
  const quote = key ? (data as Record<string, any> | undefined)?.[key] : undefined;
  const live = quote?.last_price ?? signal.levels.ltp ?? null;

  const rr = riskReward(signal);
  const ladder: Stat[] = [
    { label: 'Last traded', value: px(live), hint: 'Live where a quote is available, otherwise the price at scan' },
    { label: 'Entry', value: px(signal.levels.entry) },
    { label: 'Stop', value: px(signal.levels.stop), color: signal.levels.stop == null ? undefined : k.red, hint: 'The hard stop set at entry — the original risk' },
    { label: 'Trailing stop', value: px(signal.levels.trail), color: signal.levels.trail == null ? undefined : k.amber, hint: 'Where the ratchet has reached' },
    { label: 'Exit', value: px(signal.levels.target), color: signal.levels.target == null ? undefined : k.green, hint: 'Where the plan gets out' },
    { label: 'Exited at', value: px(signal.levels.exit) },
  ].filter((s) => s.value !== '—' || s.label === 'Entry' || s.label === 'Stop');

  const size: Stat[] = [
    { label: 'Quantity', value: signal.sizing.quantity ?? '—', hint: 'Units, not lots' },
    { label: 'Lots', value: signal.sizing.lots ?? '—' },
    { label: 'Lot size', value: signal.instrument.lotSize ?? '—' },
    { label: 'Capital deployed', value: inr(signal.sizing.deployedInr) },
    { label: 'At risk', value: inr(signal.sizing.atRiskInr), color: signal.sizing.atRiskInr == null ? undefined : k.red },
  ];

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', background: k.surface, fontFamily: k.fontFamily }}>
      <Header signal={signal} onClose={onClose} />

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {signal.reason && (
          <p style={{
            margin: 0, padding: '9px 11px', borderRadius: 4, fontSize: 11.5, lineHeight: 1.55,
            background: signal.status === 'error' ? tint(k.red, 8) : k.bg,
            border: `1px solid ${signal.status === 'error' ? tint(k.red, 30) : k.border}`,
            color: signal.status === 'error' ? k.red : k.text,
          }}>
            {signal.reason}
          </p>
        )}

        <StatCardGrid min={250}>
          <StatCard
            title="Price ladder"
            summary={rr}
            summaryColor={rr ? k.green : undefined}
            stats={ladder}
          />
          <StatCard
            title="Size & exposure"
            summary={signal.sizing.quantity == null ? 'not sized' : undefined}
            stats={size}
          />
        </StatCardGrid>

        {/* The engine's own evidence, verbatim from its adapter. */}
        {signal.sections.length > 0 && (
          <StatCardGrid min={250}>
            {signal.sections.map((section) => (
              <StatCard
                key={section.title}
                title={section.title}
                summary={section.summary}
                layout={section.layout ?? 'tiles'}
                stats={section.stats}
              />
            ))}
          </StatCardGrid>
        )}

        {key && (
          <StatCard title="Market depth" summary={signal.instrument.symbol}>
            <DepthLadder quote={quote} />
            <QuoteStats quote={quote} extra={[{ label: 'Expiry', value: signal.instrument.expiry ?? '—' }]} />
          </StatCard>
        )}

        <StatCard title="Position sizing & order">
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
            currentLtp={live ?? undefined}
            optionType={(signal.instrument.optionType ?? 'CE') as 'CE' | 'PE'}
            exitState={signal.status === 'weakening' ? 'EXIT' : 'HOLD'}
          />
        </StatCard>
      </div>
    </div>
  );
}
