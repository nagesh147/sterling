import React, { useState } from 'react';
import { useKiteAccounts, useUpdateKiteAccount } from '../../hooks/useKite';
import { useEngineConfig, useSetEngineConfig } from '../../hooks/useTripleSupertrend';
import type { EngineConfigModel } from '../../types/kiteEngine';
import { ModeToggle } from './ModeToggle';

function vehicleOrderLabel(cfg?: EngineConfigModel | null): string {
  if (!cfg) return 'option BUY orders';
  if (cfg.vehicle === 'futures') return 'futures BUY orders';
  if (cfg.vehicle === 'deep_itm_options') return 'Deep ITM option BUY orders';
  const d = cfg.target_delta;
  if (d != null && d < 0.35) return 'OTM option BUY orders';
  if (d != null && d > 0.65) return 'ITM option BUY orders';
  return 'ATM option BUY orders';
}

// Central trading-mode panel for the active Kite account. Two orthogonal axes:
//   • EXECUTION  — PAPER vs LIVE  (account.is_paper; where orders actually go)
//   • SIGNALS    — MANUAL vs AUTO (engine.auto_execute; who places them)
// Both read/write existing backend state, so this stays in sync with the
// per-account row toggles and the engine sidebar's Auto-execute switch.

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: '1px solid #e0e0e0', borderRadius: 4, padding: 16, marginBottom: 14 },
  title: { color: '#9b9b9b', fontSize: 11, letterSpacing: 1, marginBottom: 12, fontWeight: 700 },
  hint: { color: '#9b9b9b', fontSize: 11, lineHeight: 1.5 },
  row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' },
  modeLabel: { fontSize: 10, letterSpacing: 1, color: '#9b9b9b', fontWeight: 700, marginBottom: 2 },
  modeDesc: { fontSize: 11, color: '#666' },
  divider: { height: 1, background: '#eee', margin: '2px 0' },
};

type ConfirmKind = null | 'go-live' | 'enable-auto';

export function TradingModeControls() {
  const { data } = useKiteAccounts();
  const update = useUpdateKiteAccount();
  const { data: cfg } = useEngineConfig();
  const setCfg = useSetEngineConfig();
  const [confirm, setConfirm] = useState<ConfirmKind>(null);

  const active = data?.accounts.find((a) => a.is_active);
  const hasKeys = !!active?.has_credentials;
  const connected = !!active?.connected;
  const isPaper = active ? active.is_paper : true;
  const isLive = !!active && !active.is_paper;
  const auto = cfg?.auto_execute ?? false;
  const execBusy = update.isPending;
  const autoBusy = setCfg.isPending;

  if (!active) {
    return (
      <div style={S.card}>
        <div style={S.title}>TRADING MODE</div>
        <div style={S.hint}>Add and activate a Kite account below to set paper/live and manual/auto.</div>
      </div>
    );
  }

  // EXECUTION: arming (→LIVE) confirms; de-arming (→PAPER) is immediate.
  const onExec = (side: 'left' | 'right') => {
    if (side === 'right') { setConfirm('go-live'); return; }
    update.mutate({ id: active.id, is_paper: true });
  };
  const confirmGoLive = () =>
    update.mutate({ id: active.id, is_paper: false }, { onSuccess: () => setConfirm(null) });

  // SIGNALS: arming (→AUTO) confirms; de-arming (→MANUAL) is immediate.
  const onSignals = (side: 'left' | 'right') => {
    if (!cfg) return;
    if (side === 'right') { setConfirm('enable-auto'); return; }
    setCfg.mutate({ ...cfg, auto_execute: false });
  };
  const confirmEnableAuto = () =>
    cfg && setCfg.mutate({ ...cfg, auto_execute: true }, { onSuccess: () => setConfirm(null) });

  return (
    <div style={S.card}>
      <div style={S.title}>TRADING MODE — {active.label}</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* EXECUTION — PAPER / LIVE */}
        <div style={S.row}>
          <div style={{ minWidth: 0 }}>
            <div style={S.modeLabel}>EXECUTION</div>
            <div style={S.modeDesc}>
              {isLive ? 'Orders execute on your real Zerodha account.' : 'Orders are simulated — no real money at risk.'}
            </div>
          </div>
          <ModeToggle
            left="PAPER" right="LIVE"
            value={isPaper ? 'left' : 'right'}
            onSelect={onExec}
            leftColor="#387ed1" rightColor="#4caf50"
            rightDotWhenActive busy={execBusy}
            rightDisabled={!hasKeys}
            rightTitle={hasKeys ? undefined : 'Add API keys first (below) to trade live.'}
          />
        </div>

        <div style={S.divider} />

        {/* SIGNALS — MANUAL / AUTO */}
        <div style={S.row}>
          <div style={{ minWidth: 0 }}>
            <div style={S.modeLabel}>SIGNALS</div>
            <div style={S.modeDesc}>
              {auto
                ? 'The engine auto-places ready signals (live-safety gated).'
                : 'You place every order yourself from the signal list.'}
            </div>
          </div>
          <ModeToggle
            left="MANUAL" right="AUTO"
            value={auto ? 'right' : 'left'}
            onSelect={onSignals}
            leftColor="#387ed1" rightColor="#ff9800"
            rightDotWhenActive busy={autoBusy}
          />
        </div>
      </div>

      {/* Combined-state callouts */}
      {isLive && auto && (
        <div style={{ marginTop: 12, padding: '8px 11px', borderRadius: 4, background: '#fff3e0', border: '1px solid #ff980055', fontSize: 11, color: '#e65100', lineHeight: 1.5 }}>
          ⚠ <strong>LIVE + AUTO</strong> — the engine will place <strong>real option orders automatically</strong> on ready signals. Funds are at risk without per-order confirmation.
        </div>
      )}
      {auto && !connected && (
        <div style={{ marginTop: 8, ...S.hint }}>
          Auto-execute is on, but this account isn’t connected — log in below for the engine to trade.
        </div>
      )}

      {confirm === 'go-live' && (
        <ConfirmModal
          title="⚡ Switch to LIVE" accent="#4caf50" busy={execBusy}
          confirmLabel={execBusy ? 'Switching…' : 'Go Live'}
          onCancel={() => setConfirm(null)} onConfirm={confirmGoLive}
          body={<>Orders on <strong>{active.label}</strong> will execute on your <strong>real Zerodha account</strong>
            {auto ? ', and AUTO-execute is ON — the engine will trade automatically' : ''}. Continue?</>}
        />
      )}
      {confirm === 'enable-auto' && (
        <ConfirmModal
          title="⚡ Enable AUTO-execute" accent="#ff9800" busy={autoBusy}
          confirmLabel={autoBusy ? 'Enabling…' : 'Enable Auto'}
          onCancel={() => setConfirm(null)} onConfirm={confirmEnableAuto}
          body={<>Ready signals will place <strong>1-lot {vehicleOrderLabel(cfg)}</strong> on{' '}
            {isLive ? <strong>your real Zerodha account</strong> : 'the paper account'} under the live-safety gate. Continue?</>}
        />
      )}
    </div>
  );
}

function ConfirmModal({ title, accent, body, confirmLabel, busy, onConfirm, onCancel }: {
  title: string; accent: string; body: React.ReactNode; confirmLabel: string;
  busy: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onCancel(); }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <div style={{ width: 380, background: '#fff', border: '1px solid #e0e0e0', borderRadius: 6, padding: '22px 24px' }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: accent, marginBottom: 8 }}>{title}</div>
        <div style={{ fontSize: 12, color: '#444', lineHeight: 1.6, marginBottom: 18 }}>{body}</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} disabled={busy}
            style={{ background: '#fff', color: '#666', border: '1px solid #e0e0e0', padding: '7px 14px', borderRadius: 4, cursor: busy ? 'wait' : 'pointer', fontFamily: 'inherit', fontSize: 12 }}>
            Cancel
          </button>
          <button onClick={onConfirm} disabled={busy}
            style={{ background: accent, color: '#fff', border: `1px solid ${accent}`, padding: '7px 16px', borderRadius: 4, cursor: busy ? 'wait' : 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 }}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default TradingModeControls;
