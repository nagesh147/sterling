import React from 'react';
import { useResetEngineConfig, useRunScan } from '../../hooks/useSterlingKiteEngine';
import {
  BORDER, ChoiceRow, DIM, Field, MUTED, Section, SOFT, Switch, TEXT,
} from './kiteSettingsPrimitives';
import {
  AppliesChip, ConfigNote, PanelCard, PanelHeader, SettingPointer,
} from './config/ConfigPrimitives';
import {
  EXIT_MODE_OPTIONS, FIELDS, TRAIL_OPTIONS, exitModeLabel, scanSourceLabel,
} from './config/registry';
import { useConfigPatch } from './config/useConfigPatch';

/**
 * The SuperTrend strategy itself — and nothing else.
 *
 * This panel used to also own strike coverage, the index expiries, position
 * sizing, the liquidity and session guards, and the protection mode. None of
 * those are SuperTrend's: the contract settings are read by Navigator through
 * the same call, and every execution setting is consumed by the shared
 * placement path that Navigator-originated orders reuse. They now live in
 * Market & Contracts and Trade Rules, and this page keeps only the four
 * settings that exist because the strategy has three SuperTrend lines.
 *
 * `hybrid_st_weight` is deliberately gone. It was rendered as a live numeric
 * input that saved and fired a full rescan, but nothing in
 * engines/sterling_kite_engine/ or services/kite_engine/ ever read it — the
 * grep hits belong to engines/directional/trailing_stop.py and paper_store.py,
 * which build their own config objects. The schema field stays so existing
 * stored configs still deserialise.
 */
export function SuperTrendEnginePanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const resetCfg = useResetEngineConfig();
  const runScan = useRunScan();

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading SuperTrend settings…</div>;
  }

  const trailLabel = TRAIL_OPTIONS.find((option) => option.value === cfg.trail_target)?.label ?? cfg.trail_target;

  return (
    <PanelCard>
      <PanelHeader
        title="SuperTrend strategy"
        description="How this engine grades a setup and how it gets out. What it scans is set in Market & Contracts; how the order is sized and guarded is set in Trade Rules."
        saving={saving}
      />

      <Section
        title="Entry"
        description="What arms a SuperTrend setup."
        summary="3 green lines + fresh signal"
        defaultOpen
      >
        <ConfigNote>
          Entry is fixed and not configurable: all three SuperTrend lines must be green and the
          signal must be fresh on the latest closed 1H bar. The filters that can <i>refuse</i> an
          automatic entry — trend strength, volatility, liquidity, time of day — are in Trade Rules,
          because they apply to Navigator setups too.
        </ConfigNote>
      </Section>

      <Section
        title="Trailing stop"
        description="Which line the stop follows once a trade is running."
        summary={`${trailLabel}${cfg.exit_aligned_trail ? ' · anchored to exit counter' : ''}`}
        defaultOpen
      >
        <Field
          label={FIELDS.trail_target.label}
          hint={FIELDS.trail_target.help}
          badge={<AppliesChip applies={FIELDS.trail_target.applies} evidence={FIELDS.trail_target.evidence} />}
        >
          <ChoiceRow
            value={cfg.trail_target} options={TRAIL_OPTIONS}
            onChange={(value) => patch({ trail_target: value }, 'trail_target',
              `Trailing changed to ${value}`)}
          />
        </Field>
        <Field
          label={FIELDS.exit_aligned_trail.label}
          hint={FIELDS.exit_aligned_trail.help}
          badge={<AppliesChip applies={FIELDS.exit_aligned_trail.applies} evidence={FIELDS.exit_aligned_trail.evidence} />}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch
              checked={cfg.exit_aligned_trail ?? false} label="Anchor stop to exit counter"
              onChange={() => patch({ exit_aligned_trail: !(cfg.exit_aligned_trail ?? false) }, 'exit_aligned_trail',
                'Stop anchor updated')}
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
        <Field
          label={FIELDS.exit_mode.label}
          hint={FIELDS.exit_mode.help}
          badge={<AppliesChip applies={FIELDS.exit_mode.applies} evidence={FIELDS.exit_mode.evidence} />}
        >
          <ChoiceRow
            value={cfg.exit_mode} options={EXIT_MODE_OPTIONS}
            onChange={(value) => patch({ exit_mode: value }, 'exit_mode',
              `Exit confirmation changed to ${value}`)}
          />
        </Field>
        <Field
          label={FIELDS.price_stop_exit.label}
          hint={FIELDS.price_stop_exit.help}
          badge={<AppliesChip applies={FIELDS.price_stop_exit.applies} evidence={FIELDS.price_stop_exit.evidence} />}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch
              checked={cfg.price_stop_exit ?? true} label="Enforce the trailing stop as a real exit"
              onChange={() => patch({ price_stop_exit: !(cfg.price_stop_exit ?? true) }, 'price_stop_exit',
                'Trailing-stop exit updated')}
            />
            <span style={{ color: TEXT, fontSize: 11.5 }}>
              {(cfg.price_stop_exit ?? true)
                ? 'Trail or exit counter, whichever fires first'
                : 'Exit counter only'}
            </span>
          </div>
        </Field>
        <ConfigNote>
          This governs what the board reports as a trade&apos;s exit. A position already held by the
          server-side tick monitor has its trail enforced regardless, so turning it off changes the
          board&apos;s reading rather than releasing a live stop.
        </ConfigNote>
      </Section>

      <Section
        title="What this engine scans"
        description="Shared with the Value-Flow Navigator, so it is set once in Market & Contracts."
        summary={`${scanSourceLabel(cfg.scan_source)} · ${cfg.strike_moneyness.length} strikes`}
      >
        <Field label={FIELDS.scan_source.label} hint={FIELDS.scan_source.help}>
          <SettingPointer value={scanSourceLabel(cfg.scan_source)} section="market" sectionLabel="Market & Contracts" />
        </Field>
        <Field label={FIELDS.strike_moneyness.label} hint={FIELDS.strike_moneyness.help}>
          <SettingPointer
            value={`${cfg.strike_moneyness.length} strike${cfg.strike_moneyness.length === 1 ? '' : 's'}`}
            section="market" sectionLabel="Market & Contracts"
          />
        </Field>
        <Field label="Instruments" hint="Both engines scan this same list.">
          <SettingPointer
            value={cfg.scan_all_stocks
              ? `${cfg.scan_indices.length} indices + all F&O stocks`
              : `${cfg.scan_indices.length} indices + ${cfg.scan_stocks.length} stocks`}
            section="market" sectionLabel="Market & Contracts"
          />
        </Field>
      </Section>

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        padding: '14px 18px', background: SOFT,
      }}>
        <span style={{ color: DIM, fontSize: 10.5, lineHeight: 1.45 }}>
          Paper/live and manual/automatic are set once, under Trading Mode.
        </span>
        <button
          type="button" disabled={resetCfg.isPending}
          onClick={() => {
            if (!window.confirm('Restore every engine setting to its default value? This also resets Market & Contracts and Trade Rules.')) return;
            resetCfg.mutate(undefined, { onSuccess: () => runScan.mutate() });
          }}
          style={{
            minHeight: 34, flexShrink: 0, border: `1px solid ${BORDER}`, borderRadius: 7,
            background: '#fff', color: '#c9433e', padding: '0 12px',
            fontSize: 10.5, fontWeight: 650, fontFamily: 'inherit', cursor: 'pointer',
          }}
        >
          {resetCfg.isPending ? 'Restoring…' : 'Restore engine defaults'}
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          .sk-config-summary { display: none; }
          .sk-config-section-body { padding: 0 14px 18px !important; }
          .sk-config-field { grid-template-columns: 1fr !important; gap: 8px !important; }
          .sk-config-check-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </PanelCard>
  );
}

export default SuperTrendEnginePanel;
