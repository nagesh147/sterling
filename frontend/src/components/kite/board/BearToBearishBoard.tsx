import React from 'react';
import {
  useBearToBearishScan,
  useBearToBearishSnapshot,
  useExecuteBearToBearishOrder,
  useUpdateBearToBearishConfig,
} from '../../../hooks/useBearToBearish';
import { bearToBearishToBoard } from './bearToBearishAdapter';
import { BOARD_COLUMNS, SignalBoard } from './SignalBoard';
import { useBoardRowActions } from './useBoardRowActions';
import { BoardFilters } from './BoardFilters';
import { BoardTicket } from './BoardTicket';
import { useBoardView } from './useBoardView';
import type { BoardSignal } from './boardTypes';
import { k } from '../../../styles/kiteUI';

const note: React.CSSProperties = {
  padding: '10px 12px',
  margin: 0,
  fontSize: 11,
  color: k.dim,
  lineHeight: 1.6,
};

export function BearToBearishBoard({
  nowMs,
  onOpenDetail,
  onOpenChart,
}: {
  onOpenChart?: (quoteKey: string) => void;
  nowMs: number;
  onOpenDetail?: (signal: BoardSignal) => void;
}) {
  const rowActions = useBoardRowActions({ onOpenChart });
  const [pollMs, setPollMs] = React.useState(3000);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const snapshot = useBearToBearishSnapshot(true, pollMs);
  const scan = useBearToBearishScan();
  const updateConfig = useUpdateBearToBearishConfig();
  const executeOrder = useExecuteBearToBearishOrder();

  const data = snapshot.data;
  const signals = React.useMemo(() => bearToBearishToBoard(data), [data]);
  const view = useBoardView(signals, { endedByDefault: true, storageKey: 'bear_to_bearish' });

  if (snapshot.isLoading && !data) return <p style={note}>Loading Bear to Bearish Strategy...</p>;
  if (snapshot.error) {
    return (
      <p style={{ ...note, color: k.red }}>
        Unavailable: {(snapshot.error as Error).message}
      </p>
    );
  }

  const armedRows = signals.filter((s) => s.status === 'armed');
  const autoExecute = data?.auto_execute ?? false;

  return (
    <div>
      {/* Strategy Toolbar Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          padding: '8px 12px',
          borderBottom: `1px solid ${k.border}`,
          background: 'var(--k-bg2, #07090d)',
        }}
      >
        <button
          type="button"
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          title="Run intraday PCR + Lower High momentum short scan"
          style={{
            background: 'transparent',
            border: `1px solid ${k.border}`,
            color: k.text,
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: 11,
            fontWeight: 600,
            cursor: scan.isPending ? 'progress' : 'pointer',
          }}
        >
          {scan.isPending ? 'Scanning...' : 'Scan now'}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: k.dim }}>
          <span>PCR &lt; 0.60 Short Momentum</span>
          <span>·</span>
          <strong style={{ color: data?.is_paper === false ? k.green : k.amber }}>
            {data?.is_paper === false ? 'LIVE' : 'PAPER'}
          </strong>
          <span>·</span>
          <button
            type="button"
            onClick={() => updateConfig.mutate({ auto_execute: !autoExecute })}
            style={{
              background: autoExecute ? 'rgba(46,160,67,0.18)' : 'transparent',
              border: `1px solid ${autoExecute ? k.green : k.border}`,
              color: autoExecute ? k.green : k.dim,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 10,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            AUTO EXECUTE: {autoExecute ? 'ON' : 'OFF'}
          </button>
        </div>

        {armedRows.length > 0 && (
          <span style={{ fontSize: 11, color: k.green, marginLeft: 'auto', fontWeight: 600 }}>
            ⚡ {armedRows.length} Armed Short Setup{armedRows.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* PCR Live trajectory summary */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '6px 12px',
          fontSize: 10.5,
          color: k.dim,
          borderBottom: `1px solid ${k.border}`,
          background: 'var(--k-bg, #07090d)',
        }}
      >
        <span>
          PCR Trend: <b style={{ color: k.purple }}>0.80 → 0.58</b> (Sellers Active at Resistance)
        </span>
        <span>·</span>
        <span>Invalidation: PCR Jump &ge; +0.20 in 5-10m</span>
        <span>·</span>
        <span>Chart Structure: 1m / 3m / 5m Lower Highs</span>
      </div>

      {signals.length > 0 && <BoardFilters view={view} columns={BOARD_COLUMNS} />}

      {/* Main Signal Board */}
      <SignalBoard
        renderTrade={rowActions.renderTrade}
        renderChart={rowActions.renderChart}
        signals={view.visible}
        columns={BOARD_COLUMNS}
        hidden={view.hidden}
        openId={openId}
        onToggle={(id) => setOpenId((p) => (p === id ? null : id))}
        renderDetail={(sig) => (
          <div>
            <BoardTicket signal={sig} tag="BEAR_TO_BEARISH" />
            {sig.status === 'armed' && (
              <button
                type="button"
                onClick={() => executeOrder.mutate(sig.id)}
                disabled={executeOrder.isPending}
                style={{
                  margin: '8px 12px',
                  background: 'transparent',
                  border: `1px solid ${k.green}`,
                  color: k.green,
                  borderRadius: 6,
                  padding: '4px 12px',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
              >
                {executeOrder.isPending ? 'Executing...' : `Execute ${sig.direction.toUpperCase()} ${sig.instrument.symbol}`}
              </button>
            )}
          </div>
        )}
        onOpenDetail={onOpenDetail}
        nowMs={nowMs}
        emptyLabel="No active Bear to Bearish setup found. Press Scan now to scan intraday PCR dynamics."
      />
    </div>
  );
}
