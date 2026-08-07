import React from 'react';
import { useEngineSignals } from '../../hooks/useSterlingKiteEngine';
import {
  BORDER, ChoiceRow, DIM, Field, MUTED, Section, Switch, TEXT, inputStyle,
} from './kiteSettingsPrimitives';
import {
  AppliesChip, ConfigNote, PanelCard, PanelHeader, ScopeFilter, SettingPointer,
  inScope, type Scope,
} from './config/ConfigPrimitives';
import {
  EXIT_MODE_OPTIONS, FIELDS, STOP_MODE_OPTIONS, TRAIL_OPTIONS,
  exitModeLabel, type FieldKey,
} from './config/registry';
import { useConfigPatch } from './config/useConfigPatch';
import { DirectionalModePanel } from './DirectionalModePanel';

/**
 * How a trade is sized, guarded and protected once a signal exists.
 *
 * Organised on the axis the settings actually differ along — who placed the
 * order. Every field carries a MANUAL / AUTO / MANUAL+AUTO chip taken from the
 * registry, and the chip's tooltip names the backend line that justifies it.
 *
 * The tags are a property of one shared field, not two duplicated fields. The
 * backend cannot honour a manual stop mode that disagrees with the automatic
 * one: `arm_manual_option_buy` and the automatic path both call
 * `protection.arm_position` with the same `cfg.stop_mode`. A UI
 * offering two values would be describing behaviour that does not exist.
 *
 * It also corrects a real mislabel. Expiry square-off and the time stop were
 * filed under "Advanced auto-execution guards", but both iterate
 * `positions.open_positions(uid)` — the whole registry, which includes
 * hand-placed orders armed by manual protection. They
 * are tagged MANUAL+AUTO here, because that is what they do.
 */

const ORDERED_STAGES: Array<{
  id: string;
  title: string;
  description: string;
  keys: FieldKey[];
}> = [
  {
    id: 'entry', title: '1 · Entry',
    description: 'What is allowed to open a position, and which contract it opens.',
    keys: ['adx_min', 'atr_pct_min', 'block_entry_minutes_before_close', 'max_spread_pct', 'min_oi'],
  },
  {
    id: 'size', title: '2 · Position size',
    description: 'How many lots go on.',
    keys: ['risk_sizing', 'risk_pct', 'max_lots'],
  },
  {
    id: 'stop', title: '3 · Stop loss',
    description: 'Where the protective stop lives, and which orders get one.',
    keys: ['stop_mode', 'protect_manual_orders'],
  },
  {
    id: 'trail', title: '4 · Trailing stop',
    description: 'How the stop follows price once a trade is running.',
    keys: [],
  },
  {
    id: 'target', title: '5 · Target',
    description: 'Where a trade takes profit.',
    keys: [],
  },
  {
    id: 'exit', title: '6 · Exit',
    description: 'Everything else that closes a position.',
    keys: ['expiry_square_off_days', 'time_stop_bars'],
  },
  {
    id: 'guard', title: '7 · Safety net',
    description: 'Limits that stop the engine trading at all.',
    keys: ['max_daily_loss_pct', 'wire_risk_infra'],
  },
];

const SCOPE_KEY = 'kite_trade_rules_scope';

function readScope(): Scope {
  const stored = localStorage.getItem(SCOPE_KEY);
  return stored === 'manual' || stored === 'auto' ? stored : 'all';
}

/** A number input that treats an empty string as "off" (null). */
function OptionalNumber({ field, testId, value, onChange, min = 0, max, step = 1 }: {
  field: FieldKey;
  /** Kept stable across the reorg so existing coverage keeps pointing at the
   *  same control even though it lives on a different page now. */
  testId: string;
  value: number | null | undefined;
  onChange: (next: number | null) => void;
  min?: number; max?: number; step?: number;
}) {
  return (
    <input
      data-testid={testId}
      aria-label={FIELDS[field].label}
      type="number" min={min} max={max} step={step} placeholder="off"
      value={value ?? ''} style={inputStyle}
      onChange={(event) => onChange(event.target.value === '' ? null : Math.max(min, Number(event.target.value)))}
    />
  );
}

export function TradeRulesPanel() {
  const { cfg, patch, saving } = useConfigPatch();
  const { data: signals } = useEngineSignals();
  const [scope, setScope] = React.useState<Scope>(readScope);

  const changeScope = (next: Scope) => {
    setScope(next);
    localStorage.setItem(SCOPE_KEY, next);
  };

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading trade rules…</div>;
  }

  /** Renders a field only when it survives the scope filter. */
  const visible = (key: FieldKey) => inScope(FIELDS[key].applies, scope);
  const chip = (key: FieldKey) => (
    <AppliesChip applies={FIELDS[key].applies} evidence={FIELDS[key].evidence} />
  );

  const activeCount = (keys: FieldKey[]) => keys.filter(visible).length;

  // A representative lot size and premium so the impact preview opens with real
  // numbers rather than placeholders.
  const rows = signals?.rows ?? [];
  const pick = rows.find((row) => row.is_fresh) ?? rows.find((row) => row.is_active) ?? rows[0];
  const leg = pick?.legs?.find((item) => item.moneyness === 'ATM') ?? pick?.legs?.[0];

  const guardsOn = [
    (cfg.expiry_square_off_days ?? 0) > 0,
    (cfg.time_stop_bars ?? 0) > 0,
    (cfg.block_entry_minutes_before_close ?? 0) > 0,
    cfg.max_spread_pct != null,
    cfg.min_oi != null,
    cfg.max_daily_loss_pct != null,
  ].filter(Boolean).length;

  const entryStage = ORDERED_STAGES[0];
  const showVehicle = scope !== 'manual';

  return (
    <PanelCard>
      <PanelHeader
        title="Trade rules"
        description="How an order is sized, guarded and protected once a signal exists. These apply to whichever engine produced the signal."
        saving={saving}
      />

      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        padding: '13px 18px', borderBottom: `1px solid ${BORDER}`, background: '#fbfbfc',
      }}>
        <span style={{ color: MUTED, fontSize: 11, fontWeight: 700 }}>Show rules for</span>
        <ScopeFilter value={scope} onChange={changeScope} />
        <span style={{ color: DIM, fontSize: 10.5, marginLeft: 'auto' }}>
          {guardsOn} guard{guardsOn === 1 ? '' : 's'} on
          {scope === 'manual' && ' · automatic-only rules hidden'}
          {scope === 'auto' && ' · manual-only rules hidden'}
        </span>
      </div>

      {/* 1 · Entry ─────────────────────────────────────────────────────────── */}
      <Section
        title={entryStage.title}
        description={entryStage.description}
        summary={scope === 'manual' ? 'You choose every entry' : `${activeCount(entryStage.keys)} filters`}
        defaultOpen
      >
        {scope === 'manual' ? (
          <ConfigNote>
            Nothing here gates an order you place yourself — you decide when and what to buy. The
            entry filters below only ever skip an <b>automatic</b> entry. Switch the filter above to
            All or Automatic to see them.
          </ConfigNote>
        ) : (
          <>
            {visible('adx_min') && (
              <Field label={FIELDS.adx_min.label} hint={FIELDS.adx_min.help} badge={chip('adx_min')}>
                <OptionalNumber field="adx_min" testId="adx-min-input" value={cfg.adx_min} min={0} max={100} step={1}
                  onChange={(next) => patch({ adx_min: next }, 'adx_min')} />
              </Field>
            )}
            {visible('atr_pct_min') && (
              <Field label={FIELDS.atr_pct_min.label} hint={FIELDS.atr_pct_min.help} badge={chip('atr_pct_min')}>
                <OptionalNumber field="atr_pct_min" testId="atr-pct-min-input" value={cfg.atr_pct_min} min={0} max={100} step={5}
                  onChange={(next) => patch({ atr_pct_min: next }, 'atr_pct_min')} />
              </Field>
            )}
            {visible('block_entry_minutes_before_close') && (
              <Field
                label={FIELDS.block_entry_minutes_before_close.label}
                hint={FIELDS.block_entry_minutes_before_close.help}
                badge={chip('block_entry_minutes_before_close')}
              >
                <input
                  data-testid="block-entry-input" aria-label="Block entry minutes before close"
                  type="number" min={0} max={375} step={5}
                  value={cfg.block_entry_minutes_before_close ?? 0} style={inputStyle}
                  onChange={(event) => patch(
                    { block_entry_minutes_before_close: Math.max(0, Math.floor(Number(event.target.value) || 0)) },
                    'block_entry_minutes_before_close',
                  )}
                />
              </Field>
            )}
            {visible('max_spread_pct') && (
              <Field label="Liquidity" hint="Skip an automatic entry into a contract that is expensive or thin to trade." badge={chip('max_spread_pct')}>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <label style={{ color: MUTED, fontSize: 11 }}>
                    Max spread %
                    <input
                      data-testid="max-spread-input" aria-label="Max spread percent"
                      type="number" min={0} step={0.5} placeholder="off"
                      value={cfg.max_spread_pct ?? ''} style={{ ...inputStyle, marginLeft: 5 }}
                      onChange={(event) => patch(
                        { max_spread_pct: event.target.value === '' ? null : Math.max(0, Number(event.target.value)) },
                        'max_spread_pct',
                      )}
                    />
                  </label>
                  <label style={{ color: MUTED, fontSize: 11 }}>
                    Min OI
                    <input
                      data-testid="min-oi-input" aria-label="Minimum open interest"
                      type="number" min={0} step={50} placeholder="off"
                      value={cfg.min_oi ?? ''} style={{ ...inputStyle, marginLeft: 5 }}
                      onChange={(event) => patch(
                        { min_oi: event.target.value === '' ? null : Math.max(0, Math.floor(Number(event.target.value))) },
                        'min_oi',
                      )}
                    />
                  </label>
                </div>
              </Field>
            )}
          </>
        )}
      </Section>

      {/* Vehicle & entry quality — the contract an automatic order buys ────── */}
      {showVehicle && (
        <Section
          title="1b · Vehicle"
          description="Which instrument an automatic order buys when a signal fires."
          summary={cfg.directional_mode ? cfg.vehicle.replace(/_/g, ' ') : 'Default option leg'}
        >
          <ConfigNote>
            <b>Automatic orders only.</b> When you place an order yourself you pick the contract in
            the order window, so none of this applies to a manual trade.
          </ConfigNote>
          <div style={{ marginTop: 12 }}>
            <DirectionalModePanel
              cfg={cfg}
              // This panel patches a variable set of fields (vehicle, delta,
              // depth, futures series, the ADX/ATR filters), so let the keys be
              // read off the patch rather than naming one and applying its
              // rescan policy to the rest.
              onUpdate={(values) => patch(values, undefined, 'Vehicle profile updated')}
              busy={saving}
              liveLotSize={leg?.lot_size ?? undefined}
              livePremium={leg?.premium_spot ?? undefined}
              liveUnderlying={pick?.underlying}
            />
          </div>
        </Section>
      )}

      {/* 2 · Position size ─────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[1].title}
        description={ORDERED_STAGES[1].description}
        summary={scope === 'manual'
          ? 'You choose the quantity'
          : cfg.risk_sizing ? `${cfg.risk_pct}% risk · max ${cfg.max_lots} lots` : `Fixed · max ${cfg.max_lots} lots`}
      >
        {scope === 'manual' ? (
          <ConfigNote>
            Quantity on a hand-placed order is whatever you type into the order window. Risk-based
            sizing below applies to automatic orders only.
          </ConfigNote>
        ) : (
          <>
            <Field label={FIELDS.risk_sizing.label} hint={FIELDS.risk_sizing.help} badge={chip('risk_sizing')}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <Switch
                  checked={cfg.risk_sizing} label="Risk-based sizing"
                  onChange={() => patch({ risk_sizing: !cfg.risk_sizing }, 'risk_sizing',
                    `Risk sizing ${!cfg.risk_sizing ? 'enabled' : 'disabled'}`)}
                />
                <span style={{ color: TEXT, fontSize: 11.5 }}>Size positions from available capital</span>
              </div>
            </Field>
            {cfg.risk_sizing && (
              <Field label={FIELDS.risk_pct.label} hint={FIELDS.risk_pct.help} badge={chip('risk_pct')}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input
                    aria-label="Risk percent" type="number" min={0.1} max={25} step={0.5}
                    value={cfg.risk_pct} style={inputStyle}
                    onChange={(event) => patch({ risk_pct: Number(event.target.value) }, 'risk_pct')}
                  />
                  <span style={{ color: DIM, fontSize: 11 }}>% per trade</span>
                </div>
              </Field>
            )}
            <Field label={FIELDS.max_lots.label} hint={FIELDS.max_lots.help} badge={chip('max_lots')}>
              <input
                aria-label="Maximum lots" type="number" min={1} step={1}
                value={cfg.max_lots} style={inputStyle}
                onChange={(event) => patch(
                  { max_lots: Math.max(1, Math.floor(Number(event.target.value) || 1)) }, 'max_lots',
                )}
              />
            </Field>
          </>
        )}
      </Section>

      {/* 3 · Stop loss ─────────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[2].title}
        description={ORDERED_STAGES[2].description}
        summary={`${STOP_MODE_OPTIONS.find((o) => o.value === cfg.stop_mode)?.label} · manual ${(cfg.protect_manual_orders ?? true) ? 'protected' : 'unprotected'}`}
        defaultOpen
      >
        {visible('stop_mode') && (
          <Field label={FIELDS.stop_mode.label} hint={FIELDS.stop_mode.help} badge={chip('stop_mode')}>
            <ChoiceRow
              value={cfg.stop_mode} options={STOP_MODE_OPTIONS}
              onChange={(value) => patch({ stop_mode: value }, 'stop_mode',
                `Protection mode changed to ${value}`)}
            />
          </Field>
        )}
        {visible('protect_manual_orders') && (
          <Field
            label={FIELDS.protect_manual_orders.label}
            hint={FIELDS.protect_manual_orders.help}
            badge={chip('protect_manual_orders')}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Switch
                checked={cfg.protect_manual_orders ?? true}
                label="Protect orders I place by hand"
                onChange={() => patch(
                  { protect_manual_orders: !(cfg.protect_manual_orders ?? true) },
                  'protect_manual_orders',
                  `Manual-order protection ${!(cfg.protect_manual_orders ?? true) ? 'enabled' : 'disabled'}`,
                )}
              />
              <span style={{ color: TEXT, fontSize: 11.5 }}>
                {(cfg.protect_manual_orders ?? true)
                  ? 'Registered, stopped and squared off at expiry like an automatic entry'
                  : 'No stop, no monitor — the order response will say UNPROTECTED'}
              </span>
            </div>
          </Field>
        )}
      </Section>

      {/* 4 · Trailing stop ─────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[3].title}
        description={ORDERED_STAGES[3].description}
        summary={TRAIL_OPTIONS.find((o) => o.value === cfg.trail_target)?.label ?? cfg.trail_target}
      >
        <Field
          label={FIELDS.trail_target.label}
          hint="Owned by the engine that produced the signal, because the trail is drawn from that engine's own lines."
          badge={chip('trail_target')}
        >
          <SettingPointer
            value={TRAIL_OPTIONS.find((o) => o.value === cfg.trail_target)?.label ?? cfg.trail_target}
            section="engine" sectionLabel="SuperTrend"
          />
        </Field>
        <ConfigNote>
          A trade you place by hand is armed with the stop this board is already showing for that
          contract, so the trailing style applies to manual entries too — provided manual protection
          is on above. Navigator-originated setups carry their own AVWAP stop instead.
        </ConfigNote>
      </Section>

      {/* 5 · Target ────────────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[4].title}
        description={ORDERED_STAGES[4].description}
        summary="Trend-following · no fixed target"
      >
        <ConfigNote>
          There is deliberately no target setting for SuperTrend. It is a trend-following strategy
          that exits on the trail and the exit counter, so quoting a fixed target would invent a rule
          the engine does not run. Navigator-originated setups <i>do</i> carry a target — an
          R-multiple of their accepted stop — configured under <b>Value-Flow Navigator</b>.
        </ConfigNote>
      </Section>

      {/* 6 · Exit ──────────────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[5].title}
        description={ORDERED_STAGES[5].description}
        summary={`${exitModeLabel(cfg.exit_mode)} · expiry T-${cfg.expiry_square_off_days ?? 1}`}
      >
        <Field
          label={FIELDS.exit_mode.label}
          hint="Owned by the engine that produced the signal."
          badge={chip('exit_mode')}
        >
          <SettingPointer value={exitModeLabel(cfg.exit_mode)} section="engine" sectionLabel="SuperTrend" />
        </Field>
        {visible('expiry_square_off_days') && (
          <Field
            label={FIELDS.expiry_square_off_days.label}
            hint={FIELDS.expiry_square_off_days.help}
            badge={chip('expiry_square_off_days')}
          >
            <input
              data-testid="expiry-squareoff-input" aria-label="Expiry square-off days"
              type="number" min={0} max={10} step={1}
              value={cfg.expiry_square_off_days ?? 1} style={inputStyle}
              onChange={(event) => patch(
                { expiry_square_off_days: Math.max(0, Math.floor(Number(event.target.value) || 0)) },
                'expiry_square_off_days',
              )}
            />
          </Field>
        )}
        {visible('time_stop_bars') && (
          <Field label={FIELDS.time_stop_bars.label} hint={FIELDS.time_stop_bars.help} badge={chip('time_stop_bars')}>
            <input
              data-testid="time-stop-input" aria-label="Time stop bars"
              type="number" min={0} max={500} step={1}
              value={cfg.time_stop_bars ?? 0} style={inputStyle}
              onChange={(event) => patch(
                { time_stop_bars: Math.max(0, Math.floor(Number(event.target.value) || 0)) },
                'time_stop_bars',
              )}
            />
          </Field>
        )}
        <ConfigNote>
          Expiry square-off and the time stop run over every registered position, including one you
          placed by hand while manual protection was on. They are not automatic-only, which is how
          they used to be filed.
        </ConfigNote>
      </Section>

      {/* 7 · Safety net ────────────────────────────────────────────────────── */}
      <Section
        title={ORDERED_STAGES[6].title}
        description={ORDERED_STAGES[6].description}
        summary={cfg.max_daily_loss_pct != null ? `Daily loss ${cfg.max_daily_loss_pct}%` : 'No daily limit'}
      >
        {scope === 'manual' ? (
          <ConfigNote>
            The daily-loss limit only ever blocks a <b>new automatic entry</b>; it never force-closes
            anything and never stops you placing an order yourself.
          </ConfigNote>
        ) : (
          <>
            <Field
              label={FIELDS.max_daily_loss_pct.label}
              hint={FIELDS.max_daily_loss_pct.help}
              badge={chip('max_daily_loss_pct')}
            >
              <OptionalNumber
                field="max_daily_loss_pct" testId="daily-loss-input" value={cfg.max_daily_loss_pct} min={0} max={100} step={0.5}
                onChange={(next) => patch({ max_daily_loss_pct: next }, 'max_daily_loss_pct')}
              />
            </Field>
            <Field
              label={FIELDS.wire_risk_infra.label}
              hint={FIELDS.wire_risk_infra.help}
              badge={chip('wire_risk_infra')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Switch
                  checked={cfg.wire_risk_infra} label="Portfolio risk infrastructure"
                  onChange={() => patch({ wire_risk_infra: !cfg.wire_risk_infra }, 'wire_risk_infra')}
                />
                <span style={{ color: TEXT, fontSize: 11.5 }}>
                  {cfg.wire_risk_infra ? 'Drawdown breaker and correlation penalty feed sizing' : 'Sizing ignores portfolio-level risk'}
                </span>
              </div>
            </Field>
          </>
        )}
      </Section>
    </PanelCard>
  );
}

export default TradeRulesPanel;
