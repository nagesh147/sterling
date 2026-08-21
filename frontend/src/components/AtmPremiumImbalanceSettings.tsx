import React from 'react';
import {
  useAtmPremiumImbalanceConfig,
  useAtmPremiumImbalanceSnapshot,
  useSetAtmPremiumImbalanceConfig,
  type AtmPremiumImbalanceConfig,
  type EntryPricePolicy,
  type ExitPolicy,
  type ExpiryPolicy,
  type FirstTickSource,
  type ProtectionMode,
  type QuoteMode,
  type SizingMode,
  type StopBasis,
} from '../hooks/useAtmPremiumImbalance';
import {
  ChoiceRow, DefaultBadge, Field, NumberField, Section, Switch, TEXT, DIM,
} from './kite/kiteSettingsPrimitives';
import { AdvancedSection, ConfigNote, PanelCard, SettingsDraftBar } from './kite/config/ConfigPrimitives';
import { EnginePowerHeader } from './kite/config/EnginePowerHeader';

/**
 * ATM Premium Imbalance settings.
 *
 * Same order as the other engine panels — draft bar → power → universe →
 * signal → entry → exit → advanced — so the settings hub reads as one product.
 *
 * Two things this panel does that the others do not, because this strategy was
 * reverse-engineered rather than designed:
 *
 *  - It states its provenance up front. Nothing here has been through a
 *    walk-forward, so the panel says so instead of looking like a validated
 *    engine.
 *  - Options the backend will refuse in live mode are rendered disabled, using
 *    the `research_only` list the server publishes. The recurring bug in this
 *    codebase is a UI that offers behaviour the backend does not honour.
 */
const QUOTE_MODE_OPTIONS: Array<{ value: QuoteMode; label: string; hint: string }> = [
  { value: 'COMPATIBILITY', label: 'Compatibility', hint: 'Independently cached last-traded price per leg. Reproduces the observed bot exactly. Paper only.' },
  { value: 'SYNCHRONIZED', label: 'Synchronized', hint: 'CE and PE aligned by exchange timestamp. Research view: tests whether the asynchronous cache is itself doing the work.' },
  { value: 'EXECUTABLE', label: 'Executable', hint: 'Compares the two asks — what could actually be bought. Required for live.' },
];

const SIZING_MODE_OPTIONS: Array<{ value: SizingMode; label: string; hint: string }> = [
  { value: 'LOTS', label: 'Lots', hint: 'Say how many lots. The lot size comes from the contract, so the order is always a whole number of lots.' },
  { value: 'QUANTITY', label: 'Quantity', hint: 'Say the exact number of contracts. Must be a whole multiple of the lot size — the broker rejects anything else.' },
];

const ENTRY_POLICY_OPTIONS: Array<{ value: EntryPricePolicy; label: string; hint: string }> = [
  { value: 'MARKETABLE_ASK', label: 'Ask + buffer', hint: 'Limit set through the ask by the buffer, then capped at the upper circuit. The default.' },
  { value: 'PERCENT_THROUGH', label: 'Ask + %', hint: 'Limit a percentage through the ask. Mimics the very aggressive observed limit as a rule.' },
  { value: 'FIRST_TICK_PERCENT', label: 'First tick + %', hint: 'The observed rule: the selected leg\'s first price times (1 + percent), to one decimal. The recorded sessions used 10%.' },
  { value: 'MANUAL_FILE', label: 'Price file', hint: 'Operator-maintained price per strike, as the observed bot read from strike_prices.txt.' },
  { value: 'FIRST_TICK_PLUS_BUFFER', label: 'First tick + points', hint: 'A points variant. No single points buffer fits both recorded sessions, so it is research-only.' },
];

const EXIT_POLICY_OPTIONS: Array<{ value: ExitPolicy; label: string; hint: string }> = [
  { value: 'FIXED_POINT_TARGET', label: 'Fixed target', hint: 'Exit at the entry fill plus the target points. This is what the observed bot did.' },
  { value: 'PREMIUM_CONVERGENCE', label: 'Convergence', hint: 'Exit when the bought leg reaches the other leg. An older hypothesis — research only.' },
  { value: 'TRAILING_STOP', label: 'Trailing stop', hint: 'No fixed target: a stop that only ever moves up. Safer than the observed policy, but it is ours — the recordings show no stop of any kind.' },
];

const STOP_BASIS_OPTIONS: Array<{ value: StopBasis; label: string; hint: string }> = [
  { value: 'PERCENT', label: 'Percent', hint: 'Distances as a share of the entry premium. Safer here: these options trade from ~50 to ~500, so one number of points means very different risk at each end.' },
  { value: 'POINTS', label: 'Points', hint: 'Distances as absolute rupees, whatever the premium.' },
];

const EXPIRY_OPTIONS: Array<{ value: ExpiryPolicy; label: string; hint: string }> = [
  { value: 'SAME_DAY', label: 'Same day', hint: 'Refuses to arm unless a contract expires today, rather than sliding to the next one.' },
  { value: 'NEAREST', label: 'Nearest', hint: 'Soonest listed expiry, today included.' },
  { value: 'NEXT', label: 'Next', hint: 'Soonest expiry strictly after today.' },
  { value: 'EXPLICIT', label: 'Explicit', hint: 'A named expiry. Must be listed.' },
];

const FIRST_TICK_SOURCE_OPTIONS: Array<{ value: FirstTickSource; label: string; hint: string }> = [
  { value: 'SESSION_TICK', label: 'First session tick', hint: 'The first tick whose trade is stamped inside this session. What the observed bot meant to use.' },
  { value: 'OFFICIAL_OPEN', label: 'Exchange open', hint: "The exchange's own published open. Needs no dating, so a carried-over price can never be mistaken for it." },
];

const PROTECTION_OPTIONS: Array<{ value: ProtectionMode; label: string; hint: string }> = [
  { value: 'NONE', label: 'None', hint: 'Reproduces the observed bot, which had none. If this process dies while holding, nothing exits. Paper only — live refuses this.' },
  { value: 'RESTING_TARGET_LIMIT', label: 'Resting limit', hint: 'Parks a sell at the target on the exchange the moment the entry fills, so a crash still takes the profit.' },
  { value: 'GTT', label: 'Broker GTT', hint: 'A server-side trigger instead of a resting order, for when a resting limit is not wanted.' },
];

const DATA_SOURCE_OPTIONS = [
  { value: 'kite' as const, label: 'Zerodha Kite', hint: 'Broker quotes and depth. The same feed that executes.' },
  { value: 'truedata' as const, label: 'TrueData', hint: 'Independent tick feed, for replay and cross-checking.' },
];

const ADVANCED_SETTING_COUNT = 12;

export function AtmPremiumImbalanceSettings() {
  const { data, isLoading } = useAtmPremiumImbalanceConfig();
  const setCfg = useSetAtmPremiumImbalanceConfig();

  // The lot size is a property of the resolved contract, not of the config, so
  // the hints can only be exact once the pair is known. Shares the board's query
  // key, so this costs no extra request.
  const snapshot = useAtmPremiumImbalanceSnapshot();
  const lotSize = snapshot.data?.resolved?.ce.lot_size ?? 0;

  const server = data?.config;
  const defaults = data?.defaults;
  const strategy = data?.strategy;
  const researchOnly = data?.research_only;

  const [draft, setDraft] = React.useState<AtmPremiumImbalanceConfig | null>(null);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  const cfg = draft ?? server ?? null;
  // Which half of each distance pair is live. Only one is ever shown, so a
  // number on screen always means what its suffix says.
  const pct = cfg?.stop_basis === 'PERCENT';
  const dirty = draft != null && server != null
    && (Object.keys(draft) as (keyof AtmPremiumImbalanceConfig)[])
      .some((key) => JSON.stringify(draft[key]) !== JSON.stringify(server[key]));

  const patch = React.useCallback((next: Partial<AtmPremiumImbalanceConfig>) => {
    setDraft((prev) => ({ ...(prev ?? server!), ...next }));
  }, [server]);

  const handleApply = React.useCallback(() => {
    if (draft) setCfg.mutate(draft, { onSuccess: () => setDraft(null) });
  }, [draft, setCfg]);
  const handleDiscard = React.useCallback(() => setDraft(null), []);
  const handleReset = React.useCallback(() => {
    if (!resetConfirm) { setResetConfirm(true); return; }
    if (defaults) setDraft({ ...defaults });
    setResetConfirm(false);
  }, [defaults, resetConfirm]);

  if (isLoading || !cfg || !server || !defaults || !strategy) {
    return <PanelCard><div style={{ color: DIM, fontSize: 12 }}>Loading strategy settings…</div></PanelCard>;
  }

  const isDefault = <K extends keyof AtmPremiumImbalanceConfig>(key: K) =>
    JSON.stringify(cfg[key]) === JSON.stringify(defaults[key]);
  const restore = <K extends keyof AtmPremiumImbalanceConfig>(key: K) =>
    () => patch({ [key]: defaults[key] } as Partial<AtmPremiumImbalanceConfig>);

  const entryOptions = ENTRY_POLICY_OPTIONS.map((o) => ({
    ...o,
    hint: researchOnly?.entry_price_policy.includes(o.value)
      ? `${o.hint} Cannot run live.`
      : o.hint,
  }));
  const exitOptions = EXIT_POLICY_OPTIONS.map((o) => ({
    ...o,
    hint: researchOnly?.exit_policy.includes(o.value) ? `${o.hint} Cannot run live.` : o.hint,
  }));

  return (
    <>
      <SettingsDraftBar
        dirty={dirty}
        saving={setCfg.isPending}
        onApply={handleApply}
        onDiscard={handleDiscard}
        onReset={handleReset}
        resetConfirm={resetConfirm}
      />

      <EnginePowerHeader
        name={strategy.name}
        tagline={strategy.tagline}
        on={cfg.enabled}
        liveOn={server.enabled}
        busy={setCfg.isPending}
        onToggle={() => patch({ enabled: !cfg.enabled })}
        runningNote="Armed. Watching the ATM pair from the session open and will place one round trip."
        offNote="Off. No quotes are compared and no orders can be placed."
      />

      <ConfigNote>
        Reverse-engineered from screen recordings of a third-party bot, not designed here.
        Two constants are directly evidenced — a <strong>+{defaults.target_points} point target</strong> off
        the broker fill, and an exit limit at <strong>best bid − {defaults.exit_buffer_points}</strong> —
        and both were identical across two builds. Everything about the entry <em>price</em> was
        operator-supplied per session, so it is a policy here rather than a discovered rule.
        Nothing has been through a walk-forward. See{' '}
        <code>docs/strategy/atm-premium-imbalance/</code> for the evidence behind every value.
        {!strategy.live_ready && ' Live execution stays blocked until the readiness gate passes,'}
        {!strategy.live_ready && ' and will then require broker-side protection and executable quotes.'}
      </ConfigNote>

      <Section
        title="Universe"
        description="Which index, which expiry, and which strike the two legs come from."
        summary={`${cfg.underlying} · ${cfg.expiry_policy} · ${cfg.strike_policy}`}
        persistKey="api-universe"
        defaultOpen
      >
        <Field label="Underlying" hint="Index whose at-the-money call and put are compared.">
          <input
            value={cfg.underlying}
            onChange={(e) => patch({ underlying: e.target.value.toUpperCase() })}
            style={{
              background: 'transparent', color: TEXT, border: 'none', outline: 'none',
              font: 'inherit', width: 120, textAlign: 'right',
            }}
          />
        </Field>
        <Field label="Expiry" hint="Same-day refuses to arm if nothing expires today." wide>
          <ChoiceRow
            value={cfg.expiry_policy}
            options={EXPIRY_OPTIONS}
            onChange={(expiry_policy) => patch({ expiry_policy })}
          />
        </Field>
        {cfg.expiry_policy === 'EXPLICIT' && (
          <Field label="Explicit expiry" hint="ISO date. Must be a listed expiry.">
            <input
              value={cfg.explicit_expiry}
              onChange={(e) => patch({ explicit_expiry: e.target.value })}
              placeholder="YYYY-MM-DD"
              style={{
                background: 'transparent', color: TEXT, border: 'none', outline: 'none',
                font: 'inherit', width: 120, textAlign: 'right',
              }}
            />
          </Field>
        )}
        <Field
          label="Strike"
          hint="Nearest listed strike to the index price. Ties break to the lower strike, so replay is deterministic."
        >
          <span style={{ color: DIM, fontSize: 12 }}>ATM (nearest listed)</span>
        </Field>
        <Field label="Market data" hint="Where quotes come from." wide>
          <ChoiceRow
            value={cfg.data_source}
            options={DATA_SOURCE_OPTIONS}
            onChange={(data_source) => patch({ data_source })}
          />
        </Field>
      </Section>

      <Section
        title="Signal"
        description="Buys whichever at-the-money leg is cheaper. No indicators are involved."
        summary={`Cheaper leg · ${cfg.quote_mode}`}
        persistKey="api-signal"
        defaultOpen
      >
        <Field
          label="Quote mode"
          hint="Which prices the comparison reads. Compatibility reproduces the observed bot; live requires Executable."
          wide
        >
          <ChoiceRow
            value={cfg.quote_mode}
            options={QUOTE_MODE_OPTIONS}
            onChange={(quote_mode) => patch({ quote_mode })}
          />
        </Field>
        <Field
          label="Size"
          hint="How you want to state the trade size. Lots is safer — the exchange only accepts whole lots."
          wide
        >
          <ChoiceRow
            value={cfg.sizing_mode}
            options={SIZING_MODE_OPTIONS}
            onChange={(sizing_mode) => patch({ sizing_mode })}
          />
        </Field>
        {cfg.sizing_mode === 'LOTS' ? (
          <NumberField
            label="Lots"
            hint={lotSize
              ? `One lot is ${lotSize} contracts, so this orders ${(cfg.lots || 0) * lotSize}.`
              : 'One lot per the contract. SENSEX is 20 contracts per lot.'}
            value={cfg.lots}
            defaultValue={defaults.lots}
            onChange={(lots) => patch({ lots })}
            min={0}
            max={lotSize ? Math.floor(cfg.max_quantity / lotSize) : undefined}
            step={1}
          />
        ) : (
          <NumberField
            label="Quantity"
            hint={lotSize
              ? `Total contracts. Must be a multiple of ${lotSize}. The observed sessions used 20 (one lot) and 100.`
              : 'Total contracts, not lots. The observed sessions used 20 (one SENSEX lot) and 100.'}
            value={cfg.quantity}
            defaultValue={defaults.quantity}
            onChange={(quantity) => patch({ quantity })}
            min={0}
            max={cfg.max_quantity}
            step={lotSize || 1}
          />
        )}
        <NumberField
          label="Max trades per session"
          hint="The observed bot stopped after one round trip."
          value={cfg.max_trades_per_session}
          defaultValue={defaults.max_trades_per_session}
          onChange={(max_trades_per_session) => patch({ max_trades_per_session })}
          min={1}
          max={10}
        />
      </Section>

      <Section
        title="Entry"
        description="A limit deliberately through the market, so it fills like a market order. Always capped at the upper circuit."
        summary={`${cfg.entry_price_policy} · up to ${cfg.max_entry_attempts} attempts`}
        persistKey="api-entry"
        defaultOpen
      >
        <Field label="Limit price" hint="How the buy limit is derived." wide>
          <ChoiceRow
            value={cfg.entry_price_policy}
            options={entryOptions}
            onChange={(entry_price_policy) => patch({ entry_price_policy })}
          />
        </Field>
        {(cfg.entry_price_policy === 'MARKETABLE_ASK'
          || cfg.entry_price_policy === 'FIRST_TICK_PLUS_BUFFER') && (
          <NumberField
            label="Entry buffer"
            hint="Points added to the reference price. Rounded up to the tick, so alignment can only help the fill."
            value={cfg.entry_buffer_points}
            defaultValue={defaults.entry_buffer_points}
            onChange={(entry_buffer_points) => patch({ entry_buffer_points })}
            min={0}
            max={200}
            step={0.05}
            suffix="pts"
          />
        )}
        {(cfg.entry_price_policy === 'PERCENT_THROUGH'
          || cfg.entry_price_policy === 'FIRST_TICK_PERCENT') && (
          <NumberField
            label="Through the ask"
            hint="Fraction above the ask. The observed limit sat about 0.72 above its ask."
            value={cfg.entry_through_pct}
            defaultValue={defaults.entry_through_pct}
            onChange={(entry_through_pct) => patch({ entry_through_pct })}
            min={0}
            max={5}
            step={0.01}
          />
        )}
        {cfg.entry_price_policy === 'MANUAL_FILE' && (
          <Field label="Price file" hint="One line per strike, e.g. 77600CE 288.75">
            <input
              value={cfg.manual_price_file}
              onChange={(e) => patch({ manual_price_file: e.target.value })}
              placeholder="strike_prices.txt"
              style={{
                background: 'transparent', color: TEXT, border: 'none', outline: 'none',
                font: 'inherit', width: 180, textAlign: 'right',
              }}
            />
          </Field>
        )}
        <Field
          label="Reject stale quotes"
          hint="Refuse to signal or price from a quote whose trade is stamped before the session open. The observed bot priced an entry from a day-old price; live cannot disable this."
        >
          <Switch
            checked={cfg.require_session_origin_tick}
            label="Reject stale quotes"
            onChange={() => patch({ require_session_origin_tick: !cfg.require_session_origin_tick })}
          />
        </Field>
        {(cfg.entry_price_policy === 'FIRST_TICK_PERCENT'
          || cfg.entry_price_policy === 'FIRST_TICK_PLUS_BUFFER') && (
          <Field label="Price reference" hint="Which session price the entry limit is derived from." wide>
            <ChoiceRow
              value={cfg.first_tick_source}
              options={FIRST_TICK_SOURCE_OPTIONS}
              onChange={(first_tick_source) => patch({ first_tick_source })}
            />
          </Field>
        )}
        <NumberField
          label="Max attempts"
          hint="An unacknowledged order is reconciled against the broker before anything is sent again."
          value={cfg.max_entry_attempts}
          defaultValue={defaults.max_entry_attempts}
          onChange={(max_entry_attempts) => patch({ max_entry_attempts })}
          min={1}
          max={10}
        />
      </Section>

      <Section
        title="Exit"
        description="Target measured from the broker's average fill, never from the requested limit."
        summary={`+${cfg.target_points} pts · bid − ${cfg.exit_buffer_points}`}
        persistKey="api-exit"
        defaultOpen
      >
        <Field label="Policy" wide>
          <ChoiceRow
            value={cfg.exit_policy}
            options={exitOptions}
            onChange={(exit_policy) => patch({ exit_policy })}
          />
        </Field>
        <Field
          label="Broker-side protection"
          hint="Where the protective exit lives. Anything but None survives this process dying while a position is open."
          wide
        >
          <ChoiceRow
            value={cfg.protection_mode}
            options={PROTECTION_OPTIONS}
            onChange={(protection_mode) => patch({ protection_mode })}
          />
        </Field>
        <NumberField
          label="Target"
          hint="Points above the entry fill. Directly evidenced in both observed builds."
          value={cfg.target_points}
          defaultValue={defaults.target_points}
          onChange={(target_points) => patch({ target_points })}
          min={0.05}
          max={500}
          step={0.05}
          suffix="pts"
        />
        <NumberField
          label="Exit buffer"
          hint="Subtracted from the best bid to price the sell. 0.50 in both observed builds."
          value={cfg.exit_buffer_points}
          defaultValue={defaults.exit_buffer_points}
          onChange={(exit_buffer_points) => patch({ exit_buffer_points })}
          min={0}
          max={50}
          step={0.05}
          suffix="pts"
        />
        <Field
          label="Stop loss"
          hint="No stop appeared in any recording. Enabling one is a change to the strategy, not a reproduction of it."
          badge={(
            <DefaultBadge
              isDefault={isDefault('stop_enabled')}
              defaultLabel={defaults.stop_enabled ? 'on' : 'off'}
              onRestore={restore('stop_enabled')}
            />
          )}
        >
          <Switch
            checked={cfg.stop_enabled}
            label="Stop loss"
            onChange={() => patch({ stop_enabled: !cfg.stop_enabled })}
          />
        </Field>
        {cfg.stop_enabled && (
          <>
            <Field
              label="Distances in"
              hint="One basis for every stop and trail distance below, so a distance can never be ambiguous about its unit."
              wide
            >
              <ChoiceRow
                value={cfg.stop_basis}
                options={STOP_BASIS_OPTIONS}
                onChange={(stop_basis) => patch({ stop_basis })}
              />
            </Field>
            {pct ? (
              <NumberField
                label="Stop distance"
                hint="The most this trade may lose, as a share of the entry premium."
                value={cfg.stop_percent}
                defaultValue={defaults.stop_percent}
                onChange={(stop_percent) => patch({ stop_percent })}
                min={0} max={99} step={0.5} suffix="%"
              />
            ) : (
              <NumberField
                label="Stop distance"
                hint="Rupees below the entry fill. The most this trade may lose."
                value={cfg.stop_points}
                defaultValue={defaults.stop_points}
                onChange={(stop_points) => patch({ stop_points })}
                min={0} max={500} step={0.05} suffix="pts"
              />
            )}
            <NumberField
              label="Break even at"
              hint="Profit at which the stop moves to the entry fill, after which the trade can no longer lose. 0 never moves it."
              value={pct ? cfg.breakeven_percent : cfg.breakeven_points}
              defaultValue={pct ? defaults.breakeven_percent : defaults.breakeven_points}
              onChange={(v) => patch(pct ? { breakeven_percent: v } : { breakeven_points: v })}
              min={0} max={pct ? 200 : 500} step={pct ? 0.5 : 0.05}
              suffix={pct ? '%' : 'pts'}
            />
            <NumberField
              label="Trail starts at"
              hint="Profit before the stop begins following the high-water mark. 0 follows from entry."
              value={pct ? cfg.trail_start_percent : cfg.trail_start_points}
              defaultValue={pct ? defaults.trail_start_percent : defaults.trail_start_points}
              onChange={(v) => patch(pct ? { trail_start_percent: v } : { trail_start_points: v })}
              min={0} max={pct ? 200 : 500} step={pct ? 0.5 : 0.05}
              suffix={pct ? '%' : 'pts'}
            />
            <NumberField
              label="Trail distance"
              hint="How far behind the best price seen the stop sits. 0 means no trailing — the stop stays where the rungs above put it."
              value={pct ? cfg.trail_percent : cfg.trail_points}
              defaultValue={pct ? defaults.trail_percent : defaults.trail_points}
              onChange={(v) => patch(pct ? { trail_percent: v } : { trail_points: v })}
              min={0} max={pct ? 99 : 500} step={pct ? 0.5 : 0.05}
              suffix={pct ? '%' : 'pts'}
            />
            <ConfigNote>
              The stop only ever moves up. Whichever of these rungs is highest is
              the stop in force, and none of them can pull it back down.
            </ConfigNote>
          </>
        )}
      </Section>

      <AdvancedSection count={ADVANCED_SETTING_COUNT}>
        <NumberField
          label="Entry window"
          hint="How long after the open an entry may still be taken. Buying at the open is what this strategy is; without a window it would enter whenever it was armed. 0 removes the window."
          value={cfg.entry_window_seconds}
          defaultValue={defaults.entry_window_seconds}
          onChange={(entry_window_seconds) => patch({ entry_window_seconds })}
          min={0}
          max={21600}
          step={30}
          suffix="s"
        />
        <Field
          label="Close at session end"
          hint="Held past the close — and on expiry day, held to expiry — a bought option can settle worthless. This wins over every exit policy."
          badge={(
            <DefaultBadge
              isDefault={isDefault('close_at_session_end')}
              defaultLabel={defaults.close_at_session_end ? 'on' : 'off'}
              onRestore={restore('close_at_session_end')}
            />
          )}
        >
          <Switch
            checked={cfg.close_at_session_end}
            label="Close at session end"
            onChange={() => patch({ close_at_session_end: !cfg.close_at_session_end })}
          />
        </Field>
        <NumberField
          label="Max quote age"
          hint="Stale quotes suppress entry. The observed bot had no freshness gate; this is ours."
          value={cfg.max_quote_age_ms}
          defaultValue={defaults.max_quote_age_ms}
          onChange={(max_quote_age_ms) => patch({ max_quote_age_ms })}
          min={100}
          max={60000}
          step={100}
          suffix="ms"
        />
        <NumberField
          label="Max CE/PE skew"
          hint="Only used by the Synchronized research view."
          value={cfg.max_ce_pe_skew_ms}
          defaultValue={defaults.max_ce_pe_skew_ms}
          onChange={(max_ce_pe_skew_ms) => patch({ max_ce_pe_skew_ms })}
          min={1}
          max={60000}
          step={50}
          suffix="ms"
        />
        <NumberField
          label="Attempt timeout"
          hint="After this, the attempt is reconciled rather than retried."
          value={cfg.entry_attempt_timeout_ms}
          defaultValue={defaults.entry_attempt_timeout_ms}
          onChange={(entry_attempt_timeout_ms) => patch({ entry_attempt_timeout_ms })}
          min={100}
          max={60000}
          step={100}
          suffix="ms"
        />
        <NumberField
          label="Minimum difference"
          hint="Off by default: the observed bot entered on whatever gap existed."
          value={cfg.minimum_difference}
          defaultValue={defaults.minimum_difference}
          onChange={(minimum_difference) => patch({ minimum_difference })}
          min={0}
          max={1000}
          step={0.05}
          suffix="pts"
        />
        <NumberField
          label="Minimum difference %"
          hint="Off by default. Relative to the cheaper leg."
          value={cfg.minimum_difference_percent}
          defaultValue={defaults.minimum_difference_percent}
          onChange={(minimum_difference_percent) => patch({ minimum_difference_percent })}
          min={0}
          max={500}
          step={0.5}
          suffix="%"
        />
        <NumberField
          label="Max hold"
          hint="Zero disables the time stop. No time stop was observed."
          value={cfg.max_hold_seconds}
          defaultValue={defaults.max_hold_seconds}
          onChange={(max_hold_seconds) => patch({ max_hold_seconds })}
          min={0}
          max={23400}
          step={5}
          suffix="s"
        />
        <NumberField
          label="Max quantity"
          hint="Hard ceiling on contracts, independent of the configured quantity."
          value={cfg.max_quantity}
          defaultValue={defaults.max_quantity}
          onChange={(max_quantity) => patch({ max_quantity })}
          min={1}
          max={10000}
          step={1}
        />
        <NumberField
          label="Max premium at risk"
          hint="Rupee ceiling on the premium paid for one entry."
          value={cfg.max_premium_at_risk_inr}
          defaultValue={defaults.max_premium_at_risk_inr}
          onChange={(max_premium_at_risk_inr) => patch({ max_premium_at_risk_inr })}
          min={1}
          step={500}
          suffix="₹"
        />
        <NumberField
          label="Daily loss limit"
          hint="Sterling risk requirement. The observed bot had none."
          value={cfg.daily_loss_limit_inr}
          defaultValue={defaults.daily_loss_limit_inr}
          onChange={(daily_loss_limit_inr) => patch({ daily_loss_limit_inr })}
          min={1}
          step={500}
          suffix="₹"
        />
        <Field
          label="Session"
          hint="The observed bot idled until 09:15 IST and traded the open."
        >
          <span style={{ color: DIM, fontSize: 12 }}>{cfg.session_start} – {cfg.session_end}</span>
        </Field>
      </AdvancedSection>
    </>
  );
}

export default AtmPremiumImbalanceSettings;
