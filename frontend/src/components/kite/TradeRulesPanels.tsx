import React from 'react';
import { useEngineSignals } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import {
  BORDER, ChoiceRow, DIM, Field, MUTED, Section, SOFT, Switch, TEXT, inputStyle,
  settingsCardStyle,
} from './kiteSettingsPrimitives';
import { AdvancedSection, ConfigNote, PanelCard, PanelHeader } from './config/ConfigPrimitives';
import { FIELDS, STOP_MODE_OPTIONS, openSettingsSection } from './config/registry';
import { useConfigPatch } from './config/useConfigPatch';
import { DirectionalModePanel } from './DirectionalModePanel';

/**
 * Manual and automatic trading rules, as two separate pages.
 *
 * Core controls stay visible. Filters, vehicle choice and edge-case guards
 * live under an Advanced section so the page stays scannable.
 */

/** Links to each engine’s own entry / exit page. */
function PerEngineEntryExit({ navigatorOn }: { navigatorOn: boolean }) {
  const link = (label: string, section: 'engine' | 'navigator', note: string) => (
    <button
      type="button" onClick={() => openSettingsSection(section)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left',
        minHeight: 44, padding: '10px 0', cursor: 'pointer',
        border: 'none', borderBottom: `1px solid ${BORDER}`, background: 'transparent',
        fontFamily: 'inherit',
      }}
    >
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'block', color: TEXT, fontSize: 12, fontWeight: 700 }}>{label}</span>
        <span style={{ display: 'block', color: MUTED, fontSize: 10.5, lineHeight: 1.35, marginTop: 2 }}>{note}</span>
      </span>
      <span aria-hidden style={{ color: 'var(--k-brand)', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>→</span>
    </button>
  );
  return (
    <div>
      {link('SuperTrend', 'engine', 'Entry, trail and exit.')}
      {link('Navigator', 'navigator',
        navigatorOn ? 'Entry, stop and target.' : 'Off — turn on under Signal Engines.')}
    </div>
  );
}

const STOP_LIVE_HELP: Record<'broker' | 'monitor' | 'both', string> = {
  both: 'Stop at Zerodha, and Sterling watches the price too.',
  broker: 'Stop only at Zerodha. Still works if the app is offline.',
  monitor: 'Sterling watches the price and exits. Needs the app online.',
};

/**
 * These pages are split into "Manual Trade" and "Algo Trade" precisely so a reader
 * knows which rules apply to them. But a few settings are ONE stored value rendered
 * on both pages (registry.ts marks them applies:'both'), so setting a stop mode for
 * your own hand-placed buys also moves it for the algo. Without saying so, the split
 * itself becomes the lie: the page implies a scope the value does not have.
 */
function AlsoAppliesTo({ where }: { where: 'manual' | 'automatic' }) {
  return (
    <div style={{ color: DIM, fontSize: 10, lineHeight: 1.45, marginTop: 6 }}>
      One setting, shared with <b>{where === 'manual' ? 'Manual Trade' : 'Algo Trade'}</b> — changing
      it here changes it there.
    </div>
  );
}

function ProtectionMode({ value, onChange, alsoOn }: {
  value: 'broker' | 'monitor' | 'both';
  onChange: (v: 'broker' | 'monitor' | 'both') => void;
  alsoOn: 'manual' | 'automatic';
}) {
  return (
    <Field label={FIELDS.stop_mode.label} hint={STOP_LIVE_HELP[value]}>
      <ChoiceRow value={value} options={STOP_MODE_OPTIONS} onChange={onChange} />
      <AlsoAppliesTo where={alsoOn} />
    </Field>
  );
}

function ExitSafeguards({ expiryDays, timeStop, onExpiry, onTimeStop, alsoOn }: {
  expiryDays: number;
  timeStop: number;
  onExpiry: (v: number) => void;
  onTimeStop: (v: number) => void;
  alsoOn: 'manual' | 'automatic';
}) {
  return (
    <>
      <Field
        label={FIELDS.expiry_square_off_days.label}
        hint={expiryDays > 0
          ? `Closes ${expiryDays} day${expiryDays === 1 ? '' : 's'} before expiry. Enter days; 0 turns this off.`
          : 'Off. Enter days before expiry; 0 turns this off.'}
      >
        <input
          data-testid="expiry-squareoff-input" aria-label="Exit before expiry days"
          type="number" min={0} max={10} step={1} value={expiryDays} style={inputStyle}
          onChange={(e) => onExpiry(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
        />
        <AlsoAppliesTo where={alsoOn} />
      </Field>
      <Field
        label={FIELDS.time_stop_bars.label}
        hint={timeStop > 0
          ? `Closes after about ${timeStop} hour${timeStop === 1 ? '' : 's'} on the chart. Enter hours; 0 turns this off.`
          : 'Off. Enter hours on the chart; 0 turns this off.'}
      >
        <input
          data-testid="time-stop-input" aria-label="Max hold time bars"
          type="number" min={0} max={500} step={1} value={timeStop} style={inputStyle}
          onChange={(e) => onTimeStop(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
        />
        <AlsoAppliesTo where={alsoOn} />
      </Field>
    </>
  );
}

// ── Manual rules ────────────────────────────────────────────────────────────

export function ManualRulesPanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const { data: navData } = useNavigatorConfig();
  if (!cfg) return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading…</div>;

  const protectOn = cfg.protect_manual_orders ?? true;
  const stopLabel = STOP_MODE_OPTIONS.find((o) => o.value === cfg.stop_mode)?.label ?? cfg.stop_mode;
  const expiryDays = cfg.expiry_square_off_days ?? 1;
  const timeStop = cfg.time_stop_bars ?? 0;

  return (
    <PanelCard>
      <PanelHeader saving={saving} />

      <Section
        title="Stop-loss"
        description="Attach a stop when your order fills."
        summary={protectOn ? stopLabel : 'Off'}
        defaultOpen
      >
        <Field label={FIELDS.protect_manual_orders.label} hint={FIELDS.protect_manual_orders.help}>
          <Switch
            checked={protectOn} label="Add stop when I buy"
            onChange={() => patch({ protect_manual_orders: !protectOn }, 'protect_manual_orders',
              `Manual stop ${!protectOn ? 'on' : 'off'}`)}
          />
        </Field>

        {protectOn ? (
          <ProtectionMode
            value={cfg.stop_mode}
            onChange={(v) => patch({ stop_mode: v }, 'stop_mode', `Stop set to ${v}`)}
            alsoOn="automatic"
          />
        ) : (
          <ConfigNote>
            With this off, no stop-loss or time limit runs on orders you place yourself.
          </ConfigNote>
        )}
      </Section>

      {protectOn && (
        <AdvancedSection count={2}>
          <Section
            title="Time limits"
            description="Close by expiry or max hold time, even if the signal has not flipped."
            summary={
              [
                expiryDays > 0 ? `${expiryDays}d before expiry` : null,
                timeStop > 0 ? `${timeStop}h max` : null,
              ].filter(Boolean).join(' · ') || 'Both off'
            }
          >
            <ExitSafeguards
              expiryDays={expiryDays}
              timeStop={timeStop}
              onExpiry={(v) => patch({ expiry_square_off_days: v }, 'expiry_square_off_days')}
              onTimeStop={(v) => patch({ time_stop_bars: v }, 'time_stop_bars')}
              alsoOn="automatic"
            />
            <ConfigNote>
              Applies to every protected position, including ones you bought by hand.
            </ConfigNote>
          </Section>

          <Section
            title="Signal rules"
            description="Entry and exit live on each engine."
            summary="Per engine"
          >
            <PerEngineEntryExit navigatorOn={!!navData?.record.config.enabled} />
          </Section>
        </AdvancedSection>
      )}

      {!protectOn && (
        <Section
          title="Signal rules"
          description="Entry and exit live on each engine."
          summary="Per engine"
        >
          <PerEngineEntryExit navigatorOn={!!navData?.record.config.enabled} />
        </Section>
      )}
    </PanelCard>
  );
}

// ── Automatic rules ─────────────────────────────────────────────────────────

export function AutomaticRulesPanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const { data: signals } = useEngineSignals();
  const { data: navData } = useNavigatorConfig();
  if (!cfg) return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading automatic rules…</div>;

  const autoOn = !!cfg.auto_execute;
  const rows = signals?.rows ?? [];
  const pick = rows.find((r) => r.is_fresh) ?? rows.find((r) => r.is_active) ?? rows[0];
  const leg = pick?.legs?.find((l) => l.moneyness === 'ATM') ?? pick?.legs?.[0];

  const entryFilterCount = [
    cfg.adx_min, cfg.atr_pct_min, cfg.max_spread_pct, cfg.min_oi,
  ].filter((v) => v != null).length
    + ((cfg.block_entry_minutes_before_close ?? 0) > 0 ? 1 : 0)
    + ((cfg.max_contract_staleness_bars ?? 0) > 0 ? 1 : 0);

  const advancedCount = entryFilterCount + 2 + 1 + 1; // time limits, portfolio, signal rules

  const num = (
    key: Parameters<typeof patch>[1] & string,
    testId: string,
    value: number | null | undefined,
    onChange: (v: number | null) => void,
    bounds: { min?: number; max?: number; step?: number } = {},
  ) => (
    <input
      data-testid={testId} aria-label={FIELDS[key as keyof typeof FIELDS].label}
      type="number" placeholder="off" style={inputStyle}
      min={bounds.min ?? 0} max={bounds.max} step={bounds.step ?? 1}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value === '' ? null : Math.max(bounds.min ?? 0, Number(e.target.value)))}
    />
  );

  return (
    <>
      <div style={{
        ...settingsCardStyle,
        display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '16px 18px',
        background: autoOn ? '#fff7f0' : SOFT,
        borderLeft: `3px solid ${autoOn ? 'var(--k-brand)' : '#c9c9c9'}`,
      }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: TEXT, fontSize: 13.5, fontWeight: 800 }}>
              {autoOn ? 'Algo is ON' : 'Algo is OFF'}
            </div>
            <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 3 }}>
              {autoOn
                ? 'Signals can place orders on the active account. Every rule below is in force.'
                : 'Rules below are saved. Nothing places until you arm Algo in Trading Mode.'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => openSettingsSection('mode')}
            style={{
              minHeight: 34, flexShrink: 0, border: `1px solid ${BORDER}`, borderRadius: 7,
              background: 'var(--k-bg)', color: 'var(--k-brand)', padding: '0 13px',
              fontSize: 11, fontWeight: 700, fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {autoOn ? 'Turn off in Trading Mode →' : 'Turn on in Trading Mode →'}
          </button>
        </div>
      

      <PanelCard>
        <PanelHeader saving={saving} />

        <Section
          title="Stop-loss"
          description="Where the stop-loss lives after a fill."
          summary={STOP_MODE_OPTIONS.find((o) => o.value === cfg.stop_mode)?.label ?? cfg.stop_mode}
          defaultOpen
        >
          <ProtectionMode
            value={cfg.stop_mode}
            onChange={(v) => patch({ stop_mode: v }, 'stop_mode', `Stop set to ${v}`)}
            alsoOn="manual"
          />
        </Section>

        <Section
          title="Position size"
          description="How many lots per order."
          summary={cfg.risk_sizing ? `${cfg.risk_pct}% risk · max ${cfg.max_lots} lots` : `Fixed · max ${cfg.max_lots} lots`}
          defaultOpen
        >
          <Field label={FIELDS.risk_sizing.label} hint={FIELDS.risk_sizing.help}>
            <Switch
              checked={cfg.risk_sizing} label="Size by risk"
              onChange={() => patch({ risk_sizing: !cfg.risk_sizing }, 'risk_sizing',
                `Risk sizing ${!cfg.risk_sizing ? 'enabled' : 'disabled'}`)}
            />
          </Field>
          {cfg.risk_sizing && (
            <Field
              label={FIELDS.risk_pct.label}
              hint={(FIELDS.risk_pct.help || 'Percent of capital risked per trade.') + ' Enter as %.'}
            >
              <input
                aria-label="Risk percent" type="number" min={0.1} max={25} step={0.5}
                value={cfg.risk_pct} style={inputStyle}
                onChange={(e) => patch({ risk_pct: Number(e.target.value) }, 'risk_pct')}
              />
            </Field>
          )}
          {cfg.risk_sizing && (
            <Field
              label={FIELDS.allow_min_lot_over_risk.label}
              hint={FIELDS.allow_min_lot_over_risk.help}
            >
              <Switch
                checked={cfg.allow_min_lot_over_risk ?? false}
                label="Allow 1 lot over risk"
                onChange={() => patch(
                  { allow_min_lot_over_risk: !(cfg.allow_min_lot_over_risk ?? false) },
                  'allow_min_lot_over_risk',
                  `Minimum lot over risk ${!(cfg.allow_min_lot_over_risk ?? false) ? 'allowed' : 'refused'}`)}
              />
              {(cfg.allow_min_lot_over_risk ?? false) && (
                <ConfigNote>
                  Positions opened this way risk more than <b>{cfg.risk_pct}%</b>. On a small
                  account one index-option lot can be several times that.
                </ConfigNote>
              )}
            </Field>
          )}
          <Field label={FIELDS.max_lots.label} hint={FIELDS.max_lots.help}>
            <input
              aria-label="Maximum lots" type="number" min={1} step={1}
              value={cfg.max_lots} style={inputStyle}
              onChange={(e) => patch({ max_lots: Math.max(1, Math.floor(Number(e.target.value) || 1)) }, 'max_lots')}
            />
          </Field>
        </Section>

        <Section
          title="What to buy"
          description="What the algo buys on a signal."
          summary={cfg.directional_mode ? cfg.vehicle.replace(/_/g, ' ') : 'Default option leg'}
          defaultOpen
        >
          <div style={{ marginTop: 4 }}>
            <DirectionalModePanel
              cfg={cfg}
              onUpdate={(values) => patch(values, undefined, 'Vehicle profile updated')}
              busy={saving}
              liveLotSize={leg?.lot_size ?? undefined}
              livePremium={leg?.premium_spot ?? undefined}
              liveUnderlying={pick?.underlying}
            />
          </div>
        </Section>

        <Section
          title="Daily loss limit"
          description="Stop new entries after a set daily loss. Never force-closes open trades."
          summary={cfg.max_daily_loss_pct != null ? `${cfg.max_daily_loss_pct}%` : 'Off'}
          defaultOpen
        >
          <Field label={FIELDS.max_daily_loss_pct.label} hint={FIELDS.max_daily_loss_pct.help}>
            {num('max_daily_loss_pct', 'daily-loss-input', cfg.max_daily_loss_pct,
              (v) => patch({ max_daily_loss_pct: v }, 'max_daily_loss_pct'), { max: 100, step: 0.5 })}
          </Field>
        </Section>

        <AdvancedSection count={advancedCount}>
          <Section
            title="Entry filters"
            description="Skip an entry when these are not met. Blank or zero = off."
            summary={`${entryFilterCount} active`}
          >
            <Field label={FIELDS.adx_min.label} hint={FIELDS.adx_min.help}>
              {num('adx_min', 'adx-min-input', cfg.adx_min, (v) => patch({ adx_min: v }, 'adx_min'), { max: 100 })}
            </Field>
            <Field label={FIELDS.atr_pct_min.label} hint={FIELDS.atr_pct_min.help}>
              {num('atr_pct_min', 'atr-pct-min-input', cfg.atr_pct_min, (v) => patch({ atr_pct_min: v }, 'atr_pct_min'), { max: 100, step: 5 })}
            </Field>
            <Field label={FIELDS.block_entry_minutes_before_close.label} hint={FIELDS.block_entry_minutes_before_close.help}>
              <input
                data-testid="block-entry-input" aria-label="Block late entries minutes"
                type="number" min={0} max={375} step={5}
                value={cfg.block_entry_minutes_before_close ?? 0} style={inputStyle}
                onChange={(e) => patch(
                  { block_entry_minutes_before_close: Math.max(0, Math.floor(Number(e.target.value) || 0)) },
                  'block_entry_minutes_before_close',
                )}
              />
            </Field>
            <Field label="Liquidity" hint="Skip a contract that is expensive or thin to trade.">
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <label style={{ color: MUTED, fontSize: 11 }}>
                  Max spread %{' '}
                  {num('max_spread_pct', 'max-spread-input', cfg.max_spread_pct, (v) => patch({ max_spread_pct: v }, 'max_spread_pct'), { step: 0.5 })}
                </label>
                <label style={{ color: MUTED, fontSize: 11 }}>
                  Min OI{' '}
                  {num('min_oi', 'min-oi-input', cfg.min_oi, (v) => patch({ min_oi: v == null ? null : Math.floor(v) }, 'min_oi'), { step: 50 })}
                </label>
              </div>
            </Field>
            <Field
              label={FIELDS.max_contract_staleness_bars.label}
              hint={FIELDS.max_contract_staleness_bars.help}
            >
              <input
                data-testid="staleness-input" aria-label="Max contract lag"
                type="number" min={0} max={12} step={1}
                value={cfg.max_contract_staleness_bars ?? 0} style={inputStyle}
                onChange={(e) => patch(
                  { max_contract_staleness_bars: Math.max(0, Math.floor(Number(e.target.value) || 0)) },
                  'max_contract_staleness_bars',
                )}
              />
              {(cfg.max_contract_staleness_bars ?? 0) > 0 && (
                <ConfigNote>
                  A contract that last traded up to <b>{cfg.max_contract_staleness_bars}h</b> ago can
                  still be bought automatically. Its signal is real, but the premium on the row is
                  that old too, so a market order may fill well away from it.
                </ConfigNote>
              )}
            </Field>
          </Section>

          <Section
            title="Time limits"
            description="Close by expiry or max hold time, even if the signal has not flipped."
            summary={`Expiry T-${cfg.expiry_square_off_days ?? 1}${(cfg.time_stop_bars ?? 0) > 0 ? ` · ${cfg.time_stop_bars} bars` : ''}`}
          >
            <ExitSafeguards
              expiryDays={cfg.expiry_square_off_days ?? 1}
              timeStop={cfg.time_stop_bars ?? 0}
              onExpiry={(v) => patch({ expiry_square_off_days: v }, 'expiry_square_off_days')}
              onTimeStop={(v) => patch({ time_stop_bars: v }, 'time_stop_bars')}
              alsoOn="manual"
            />
          </Section>

          <Section
            title="Portfolio risk"
            description="Drawdown and correlation feed into sizing."
            summary={cfg.wire_risk_infra ? 'On' : 'Off'}
          >
            <Field label={FIELDS.wire_risk_infra.label} hint={FIELDS.wire_risk_infra.help}>
              <Switch
                checked={cfg.wire_risk_infra} label="Portfolio risk guards"
                onChange={() => patch({ wire_risk_infra: !cfg.wire_risk_infra }, 'wire_risk_infra')}
              />
            </Field>
          </Section>

          <Section
            title="Signal rules"
            description="Entry and exit live on each engine."
            summary="Per engine"
          >
            <PerEngineEntryExit navigatorOn={!!navData?.record.config.enabled} />
          </Section>
        </AdvancedSection>
      </PanelCard>
    </>
  );
}
