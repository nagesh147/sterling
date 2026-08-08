import React from 'react';
import { useResetEngineConfig, useRunScan } from '../../hooks/useSterlingKiteEngine';
import {
  BORDER, ChoiceRow, DIM, Field, MUTED, Section, SOFT, Switch, TEXT,
} from './kiteSettingsPrimitives';
import { ConfigNote, PanelCard, PanelHeader } from './config/ConfigPrimitives';
import { EnginePowerHeader } from './config/EnginePowerHeader';
import { ContractsGroup, InstrumentsGroup, SignalSourceGroup } from './config/ScanSettings';
import {
  EXIT_MODE_OPTIONS, FIELDS, TRAIL_OPTIONS, exitModeLabel, scanSourceLabel,
} from './config/registry';
import { useConfigPatch } from './config/useConfigPatch';

/**
 * The SuperTrend engine, end to end: whether it runs, what it scans, and how it
 * enters and exits.
 *
 * What it scans used to live on a separate page shared with Navigator. That
 * page could not express "SuperTrend on the full strike ladder, Navigator on
 * ATM only", and it claimed a sharing that the backend only partly does. Each
 * engine now owns its own scan settings; Navigator's page offers an explicit
 * per-group "Same as SuperTrend" for the parts a user does want to keep in
 * step.
 */
export function SuperTrendEnginePanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const resetCfg = useResetEngineConfig();
  const runScan = useRunScan();

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading SuperTrend settings…</div>;
  }

  const on = cfg.engine_enabled;
  const trailLabel = TRAIL_OPTIONS.find((o) => o.value === cfg.trail_target)?.label ?? cfg.trail_target;
  const indexExpiries = cfg.scan_expiries_indices ?? cfg.scan_expiries;
  const instruments = cfg.scan_indices.length + (cfg.scan_all_stocks ? 0 : cfg.scan_stocks.length);

  return (
    <>
      <EnginePowerHeader
        name="SuperTrend"
        tagline="Triple SuperTrend on a 1H Heikin-Ashi chart."
        on={on}
        busy={saving}
        onToggle={() => patch({ engine_enabled: !on }, 'engine_enabled',
          `SuperTrend ${!on ? 'enabled' : 'disabled'}`)}
        runningNote="Scanning, producing signals, and eligible for automatic execution."
        offNote="Not scanning. Navigator can still run on its own."
      />

      <PanelCard>
        <PanelHeader
          title="What SuperTrend scans"
          description="This engine's own instruments, signal source and contract coverage."
          saving={saving}
        />

        <Section
          title="Instruments"
          description="The indices and F&O stocks this engine watches."
          summary={!(cfg.scan_stock_contracts ?? true)
            ? `${cfg.scan_indices.length} indices · no stocks`
            : cfg.scan_all_stocks
              ? `All F&O · ${cfg.scan_indices.length} indices`
              : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`}
          defaultOpen
        >
          <InstrumentsGroup
            idPrefix="SuperTrend"
            indices={cfg.scan_indices}
            stocks={cfg.scan_stocks}
            allStocks={cfg.scan_all_stocks}
            stockContracts={cfg.scan_stock_contracts ?? true}
            onChange={(next) => patch(next, undefined, 'SuperTrend universe updated')}
          />
        </Section>

        <Section
          title="Signal source"
          description="Which chart SuperTrend reads a setup from."
          summary={scanSourceLabel(cfg.scan_source)}
          defaultOpen
        >
          <SignalSourceGroup
            name="supertrend-signal-source"
            value={cfg.scan_source}
            onChange={(v) => patch({ scan_source: v }, 'scan_source', `SuperTrend source changed to ${scanSourceLabel(v)}`)}
          />
        </Section>

        <Section
          title="Contracts"
          description="Which strikes and expiry cycles SuperTrend resolves."
          summary={`${cfg.strike_moneyness.length} strikes · ${indexExpiries.join(' + ')}`}
        >
          <ContractsGroup
            strikes={cfg.strike_moneyness}
            indexExpiries={indexExpiries}
            onChange={(next) => patch(next, undefined, 'SuperTrend contracts updated')}
          />
        </Section>

        <div style={{ padding: '11px 18px', background: SOFT, borderTop: `1px solid ${BORDER}`, color: DIM, fontSize: 10.5 }}>
          {instruments} instrument{instruments === 1 ? '' : 's'} · {cfg.strike_moneyness.length} strike
          {cfg.strike_moneyness.length === 1 ? '' : 's'} · source {scanSourceLabel(cfg.scan_source)}
        </div>
      </PanelCard>

      <PanelCard>
        <PanelHeader
          title="How SuperTrend trades"
          description="How a setup is armed, how the stop follows price, and what closes the trade."
          saving={saving}
        />

        <Section
          title="Entry"
          description="What arms a SuperTrend setup."
          summary="3 green lines + fresh signal"
          defaultOpen
        >
          <ConfigNote>
            Entry is fixed: all three SuperTrend lines must be green and the signal fresh on the
            latest closed 1H bar. Filters that can <i>refuse</i> an automatic entry — trend strength,
            volatility, liquidity, time of day — are under <b>Automatic rules</b>, because they apply
            to Navigator setups too.
          </ConfigNote>
        </Section>

        <Section
          title="Trailing stop"
          description="Which line the stop follows once a trade is running."
          summary={`${trailLabel}${cfg.exit_aligned_trail ? ' · anchored to exit counter' : ''}`}
          defaultOpen
        >
          <Field label={FIELDS.trail_target.label} hint={FIELDS.trail_target.help}>
            <ChoiceRow
              value={cfg.trail_target} options={TRAIL_OPTIONS}
              onChange={(v) => patch({ trail_target: v }, 'trail_target', `Trailing changed to ${v}`)}
            />
          </Field>
          <Field label={FIELDS.exit_aligned_trail.label} hint={FIELDS.exit_aligned_trail.help}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <Switch
                checked={cfg.exit_aligned_trail ?? false} label="Anchor stop to exit counter"
                onChange={() => patch({ exit_aligned_trail: !(cfg.exit_aligned_trail ?? false) },
                  'exit_aligned_trail', 'Stop anchor updated')}
              />
              <span style={{ color: TEXT, fontSize: 11.5 }}>
                {cfg.exit_aligned_trail ? 'Aligned to exit counter' : 'Tightest fast line'}
              </span>
            </div>
          </Field>
        </Section>

        <Section
          title="Exit"
          description="What closes a SuperTrend trade."
          summary={`${exitModeLabel(cfg.exit_mode)}${(cfg.price_stop_exit ?? true) ? ' · trail enforced' : ' · counter only'}`}
          defaultOpen
        >
          <Field label={FIELDS.exit_mode.label} hint={FIELDS.exit_mode.help}>
            <ChoiceRow
              value={cfg.exit_mode} options={EXIT_MODE_OPTIONS}
              onChange={(v) => patch({ exit_mode: v }, 'exit_mode', `Exit confirmation changed to ${v}`)}
            />
          </Field>
          <Field label={FIELDS.price_stop_exit.label} hint={FIELDS.price_stop_exit.help}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <Switch
                checked={cfg.price_stop_exit ?? true} label="Enforce the trailing stop as a real exit"
                onChange={() => patch({ price_stop_exit: !(cfg.price_stop_exit ?? true) },
                  'price_stop_exit', 'Trailing-stop exit updated')}
              />
              <span style={{ color: TEXT, fontSize: 11.5 }}>
                {(cfg.price_stop_exit ?? true) ? 'Trail or exit counter, whichever fires first' : 'Exit counter only'}
              </span>
            </div>
          </Field>
          <ConfigNote>
            This governs what the board reports as a trade&apos;s exit. A position already held by the
            server-side tick monitor has its trail enforced regardless.
          </ConfigNote>
        </Section>

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          padding: '14px 18px', background: SOFT,
        }}>
          <span style={{ color: DIM, fontSize: 10.5, lineHeight: 1.45 }}>
            Sizing, order guards and protection are under Manual and Automatic rules.
          </span>
          <button
            type="button" disabled={resetCfg.isPending}
            onClick={() => {
              if (!window.confirm('Restore every SuperTrend setting to its default value? This also resets what it scans, and the shared trade rules.')) return;
              resetCfg.mutate(undefined, { onSuccess: () => runScan.mutate() });
            }}
            style={{
              minHeight: 34, flexShrink: 0, border: `1px solid ${BORDER}`, borderRadius: 7,
              background: '#fff', color: '#c9433e', padding: '0 12px',
              fontSize: 10.5, fontWeight: 650, fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {resetCfg.isPending ? 'Restoring…' : 'Restore defaults'}
          </button>
        </div>
      </PanelCard>

      <style>{`
        @media (max-width: 640px) {
          .sk-config-summary { display: none; }
          .sk-config-section-body { padding: 0 14px 18px !important; }
          .sk-config-field { grid-template-columns: 1fr !important; gap: 8px !important; }
          .sk-config-check-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  );
}

export default SuperTrendEnginePanel;
