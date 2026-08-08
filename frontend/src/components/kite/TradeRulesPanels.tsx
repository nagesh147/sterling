import React from 'react';
import { useEngineSignals } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import {
  BORDER, ChoiceRow, DIM, Field, MUTED, Section, SOFT, Switch, TEXT, inputStyle,
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

/** Marks a control that is the same single setting on both rule pages. */
function AlsoAppliesTo({ where }: { where: 'manual' | 'automatic' }) {
  return (
    <div style={{ color: DIM, fontSize: 10, lineHeight: 1.45, marginTop: 6 }}>
      One setting, shared with <b>{where === 'manual' ? 'Manual' : 'Automatic'} rules</b> — changing
      it here changes it there.
    </div>
  );
}

/** Where entry and exit actually live: with the engine that produced the signal. */
function PerEngineEntryExit({ navigatorOn }: { navigatorOn: boolean }) {
  const link = (label: string, section: 'engine' | 'navigator', note: string) => (
    <button
      type="button" onClick={() => openSettingsSection(section)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left',
        minHeight: 52, padding: '10px 12px', borderRadius: 7, cursor: 'pointer',
        border: `1px solid ${BORDER}`, background: '#fff', fontFamily: 'inherit', marginBottom: 8,
      }}
    >
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: 'block', color: TEXT, fontSize: 12, fontWeight: 700 }}>{label}</span>
        <span style={{ display: 'block', color: MUTED, fontSize: 10.5, lineHeight: 1.4, marginTop: 2 }}>{note}</span>
      </span>
      <span aria-hidden style={{ color: '#f06428', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>→</span>
    </button>
  );
  return (
    <>
      <ConfigNote>
        Entry and exit are not the same thing in the two engines — SuperTrend arms on three green
        lines and leaves on a red counter, Navigator arms on AVWAP structure and leaves on its own
        stop and target. So each engine keeps its own, rather than one blended set of rules here.
      </ConfigNote>
      <div style={{ marginTop: 12 }}>
        {link('SuperTrend — entry, trailing stop, exit', 'engine',
          'Three-line entry, which line the stop follows, and the red counter that closes a trade.')}
        {link('Navigator — entry, stop, target', 'navigator',
          navigatorOn
            ? 'AVWAP structure entry, its stop buffer and its R-multiple target.'
            : 'Currently off. Its rules apply only once Navigator is running.')}
      </div>
    </>
  );
}

// ── Shared control renderers ────────────────────────────────────────────────

function ProtectionMode({ value, onChange, alsoOn }: {
  value: 'broker' | 'monitor' | 'both';
  onChange: (v: 'broker' | 'monitor' | 'both') => void;
  alsoOn: 'manual' | 'automatic';
}) {
  return (
    <Field label={FIELDS.stop_mode.label} hint={FIELDS.stop_mode.help}>
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
      <Field label={FIELDS.expiry_square_off_days.label} hint={FIELDS.expiry_square_off_days.help}>
        <input
          data-testid="expiry-squareoff-input" aria-label="Force exit before expiry days"
          type="number" min={0} max={10} step={1} value={expiryDays} style={inputStyle}
          onChange={(e) => onExpiry(Math.max(0, Math.floor(Number(e.target.value) || 0)))}
        />
        <AlsoAppliesTo where={alsoOn} />
      </Field>
      <Field label={FIELDS.time_stop_bars.label} hint={FIELDS.time_stop_bars.help}>
        <input
          data-testid="time-stop-input" aria-label="Max holding time bars"
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
  if (!cfg) return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading manual rules…</div>;

  const protectOn = cfg.protect_manual_orders ?? true;

  return (
    <PanelCard>
      <PanelHeader
        title="Orders you place yourself"
        description="What happens to a trade you put on by hand. Nothing here can block your order — you decide when and what to buy."
        saving={saving}
      />

      {/* ── Core ── */}
      <Section
        title="Protection"
        description="Whether a hand-placed BUY gets the stop this board is already showing for it."
        summary={protectOn ? 'Protected like an automatic entry' : 'Unprotected — yours to manage'}
        defaultOpen
      >
        <Field label={FIELDS.protect_manual_orders.label} hint={FIELDS.protect_manual_orders.help}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Switch
              checked={protectOn} label="Protect my manual orders"
              onChange={() => patch({ protect_manual_orders: !protectOn }, 'protect_manual_orders',
                `Manual-order protection ${!protectOn ? 'enabled' : 'disabled'}`)}
            />
            <span style={{ color: TEXT, fontSize: 11.5 }}>
              {protectOn
                ? 'Registered, stopped and squared off at expiry like an automatic entry'
                : 'No stop, no monitor — the order response will say UNPROTECTED'}
            </span>
          </div>
        </Field>
        {protectOn ? (
          <ProtectionMode
            value={cfg.stop_mode}
            onChange={(v) => patch({ stop_mode: v }, 'stop_mode', `Stop location changed to ${v}`)}
            alsoOn="automatic"
          />
        ) : (
          <ConfigNote>
            With protection off, the rest of this page does not apply — your order gets no stop, no
            tick monitor and no force-exit before expiry, and the board's SL/TSL columns are a plan you
            have to execute yourself.
          </ConfigNote>
        )}
      </Section>

      {/* ── Advanced ── */}
      {protectOn && (
        <AdvancedSection count={3}>
          <Section
            title="Exit safeguards"
            description="Backstops that close a protected position regardless of the signal."
            summary={`Expiry T-${cfg.expiry_square_off_days ?? 1}${(cfg.time_stop_bars ?? 0) > 0 ? ` · ${cfg.time_stop_bars} bars` : ''}`}
          >
            <ExitSafeguards
              expiryDays={cfg.expiry_square_off_days ?? 1}
              timeStop={cfg.time_stop_bars ?? 0}
              onExpiry={(v) => patch({ expiry_square_off_days: v }, 'expiry_square_off_days')}
              onTimeStop={(v) => patch({ time_stop_bars: v }, 'time_stop_bars')}
              alsoOn="automatic"
            />
            <ConfigNote>
              These run over every position the server is tracking, including ones you placed by
              hand while protection was on. That is what makes a physically-settled stock option safe
              to hold — without the force-exit it can go to delivery.
            </ConfigNote>
          </Section>

          <Section
            title="Entry & exit rules"
            description="Set per engine, because the two engines mean different things by them."
            summary="Per engine"
          >
            <PerEngineEntryExit navigatorOn={!!navData?.record.config.enabled} />
          </Section>
        </AdvancedSection>
      )}

      {!protectOn && (
        <Section
          title="Entry & exit rules"
          description="Set per engine, because the two engines mean different things by them."
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

  // Rough count of advanced controls for the badge
  const advancedCount = entryFilterCount + 1 /* vehicle */ + 2 /* exit safeguards */ + 1 /* portfolio risk */ + 1 /* per-engine */;

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
      {/* Status banner — is any of this live? */}
      <PanelCard>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '16px 18px',
          background: autoOn ? '#fff7f0' : SOFT,
          borderLeft: `3px solid ${autoOn ? '#f06428' : '#c9c9c9'}`,
        }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ color: TEXT, fontSize: 13.5, fontWeight: 800 }}>
              {autoOn ? 'Automatic execution is ON' : 'Automatic execution is OFF'}
            </div>
            <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 3 }}>
              {autoOn
                ? 'Ready signals place real orders on the active account, under the live-safety gate. Every rule below is in force.'
                : 'You place every order yourself. The rules below are saved, but none of them are doing anything yet.'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => openSettingsSection('mode')}
            style={{
              minHeight: 34, flexShrink: 0, border: `1px solid ${BORDER}`, borderRadius: 7,
              background: '#fff', color: '#f06428', padding: '0 13px',
              fontSize: 11, fontWeight: 700, fontFamily: 'inherit', cursor: 'pointer',
            }}
          >
            {autoOn ? 'Turn off in Trading Mode →' : 'Turn on in Trading Mode →'}
          </button>
        </div>
      </PanelCard>

      <PanelCard>
        <PanelHeader
          title="Orders the engine places"
          description="What the engine is allowed to open, how big, and what closes it."
          saving={saving}
        />

        {/* ═══════════════ CORE ═══════════════ */}
        <Section
          title="Stop location"
          description="Where the protective stop lives once the order fills."
          summary={STOP_MODE_OPTIONS.find((o) => o.value === cfg.stop_mode)?.label ?? cfg.stop_mode}
          defaultOpen
        >
          <ProtectionMode
            value={cfg.stop_mode}
            onChange={(v) => patch({ stop_mode: v }, 'stop_mode', `Stop location changed to ${v}`)}
            alsoOn="manual"
          />
        </Section>

        <Section
          title="Position size"
          description="How many lots go on."
          summary={cfg.risk_sizing ? `${cfg.risk_pct}% risk · max ${cfg.max_lots} lots` : `Fixed · max ${cfg.max_lots} lots`}
          defaultOpen
        >
          <Field label={FIELDS.risk_sizing.label} hint={FIELDS.risk_sizing.help}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Switch
                checked={cfg.risk_sizing} label="Size by risk"
                onChange={() => patch({ risk_sizing: !cfg.risk_sizing }, 'risk_sizing',
                  `Risk sizing ${!cfg.risk_sizing ? 'enabled' : 'disabled'}`)}
              />
              <span style={{ color: TEXT, fontSize: 11.5 }}>Size positions from available capital</span>
            </div>
          </Field>
          {cfg.risk_sizing && (
            <Field label={FIELDS.risk_pct.label} hint={FIELDS.risk_pct.help}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  aria-label="Risk percent" type="number" min={0.1} max={25} step={0.5}
                  value={cfg.risk_pct} style={inputStyle}
                  onChange={(e) => patch({ risk_pct: Number(e.target.value) }, 'risk_pct')}
                />
                <span style={{ color: DIM, fontSize: 11 }}>% per trade</span>
              </div>
            </Field>
          )}
          {cfg.risk_sizing && (
            <Field
              label={FIELDS.allow_min_lot_over_risk.label}
              hint={FIELDS.allow_min_lot_over_risk.help}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <Switch
                  checked={cfg.allow_min_lot_over_risk ?? false}
                  label="Allow 1 lot over risk"
                  onChange={() => patch(
                    { allow_min_lot_over_risk: !(cfg.allow_min_lot_over_risk ?? false) },
                    'allow_min_lot_over_risk',
                    `Minimum lot over risk ${!(cfg.allow_min_lot_over_risk ?? false) ? 'allowed' : 'refused'}`)}
                />
                <span style={{ color: TEXT, fontSize: 11.5 }}>
                  {(cfg.allow_min_lot_over_risk ?? false)
                    ? 'Takes one lot even when that exceeds the cap'
                    : 'Skips the entry when one lot exceeds the cap'}
                </span>
              </div>
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
          title="Daily loss limit"
          description="Halt new automatic entries once the day's realised losses reach this share of F&O capital. Never force-closes."
          summary={cfg.max_daily_loss_pct != null ? `${cfg.max_daily_loss_pct}%` : 'Off'}
          defaultOpen
        >
          <Field label={FIELDS.max_daily_loss_pct.label} hint={FIELDS.max_daily_loss_pct.help}>
            {num('max_daily_loss_pct', 'daily-loss-input', cfg.max_daily_loss_pct,
              (v) => patch({ max_daily_loss_pct: v }, 'max_daily_loss_pct'), { max: 100, step: 0.5 })}
          </Field>
        </Section>

        {/* ═══════════════ ADVANCED ═══════════════ */}
        <AdvancedSection count={advancedCount}>
          <Section
            title="Entry filters"
            description="Refuse an automatic entry when these conditions are not met. Blank or zero disables one."
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
            <Field label="Liquidity" hint="Refuse a contract that is expensive or thin to trade.">
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  data-testid="staleness-input" aria-label="Max contract lag"
                  type="number" min={0} max={12} step={1}
                  value={cfg.max_contract_staleness_bars ?? 0} style={inputStyle}
                  onChange={(e) => patch(
                    { max_contract_staleness_bars: Math.max(0, Math.floor(Number(e.target.value) || 0)) },
                    'max_contract_staleness_bars',
                  )}
                />
                <span style={{ color: DIM, fontSize: 11 }}>hours behind the underlying</span>
              </div>
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
            title="Order vehicle"
            description="Which instrument an automatic order takes when a signal fires."
            summary={cfg.directional_mode ? cfg.vehicle.replace(/_/g, ' ') : 'Default option leg'}
          >
            <ConfigNote>
              Only automatic orders. When you place an order yourself you pick the contract in the
              order window.
            </ConfigNote>
            <div style={{ marginTop: 12 }}>
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
            title="Exit safeguards"
            description="Backstops that close a position regardless of the signal."
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
            description="Feed drawdown and correlation into automatic sizing."
            summary={cfg.wire_risk_infra ? 'On' : 'Off'}
          >
            <Field label={FIELDS.wire_risk_infra.label} hint={FIELDS.wire_risk_infra.help}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Switch
                  checked={cfg.wire_risk_infra} label="Portfolio risk guards"
                  onChange={() => patch({ wire_risk_infra: !cfg.wire_risk_infra }, 'wire_risk_infra')}
                />
                <span style={{ color: TEXT, fontSize: 11.5 }}>
                  {cfg.wire_risk_infra ? 'Drawdown breaker and correlation penalty feed sizing' : 'Sizing ignores portfolio-level risk'}
                </span>
              </div>
            </Field>
          </Section>

          <Section
            title="Entry & exit rules"
            description="Set per engine, because the two engines mean different things by them."
            summary="Per engine"
          >
            <PerEngineEntryExit navigatorOn={!!navData?.record.config.enabled} />
          </Section>
        </AdvancedSection>
      </PanelCard>
    </>
  );
}
