import React from 'react';
import { useOrbConfig, useSetOrbConfig, type OrbConfig } from '../hooks/useOrbConfig';
import {
  BORDER, ChoiceRow, DefaultBadge, Field, NumberField, Section, Switch, TEXT,
} from './kite/kiteSettingsPrimitives';
import { AdvancedSection, ConfigNote, PanelCard, SettingsDraftBar } from './kite/config/ConfigPrimitives';
import { EnginePowerHeader } from './kite/config/EnginePowerHeader';
import { InstrumentsGroup } from './kite/config/ScanSettings';

/**
 * ORB + VWAP options settings.
 *
 * Deliberately the same order as SuperTrend and Navigator — draft bar → power →
 * chart source → instruments → contracts → engine-specific → advanced — so the
 * settings hub reads as one product rather than three conventions. Numeric
 * tuning lives under Advanced, where each field says whether it is still at the
 * engine's default.
 */
const DATA_SOURCE_OPTIONS = [
  { value: 'kite', label: 'Zerodha Kite', hint: 'Broker candles and quotes. The default, and the same feed that executes.' },
  { value: 'truedata', label: 'TrueData', hint: 'Independent feed with tick, OI and bid/ask depth for contract validation.' },
] as const;

const MONEYNESS_OPTIONS = [
  { value: 'ATM', label: 'ATM', hint: 'At the money. Highest liquidity, ~0.5 delta.' },
  { value: 'ITM', label: 'ITM', hint: 'In the money. Higher delta and cost, less time value.' },
  { value: 'OTM', label: 'OTM', hint: 'Out of the money. Cheaper, lower delta, decays faster.' },
] as const;

const EXPIRY_OPTIONS = [
  { value: 'nearest', label: 'Nearest', hint: 'Whichever eligible expiry is soonest.' },
  { value: 'weekly', label: 'Weekly', hint: 'Nearest eligible non-monthly contract. Refuses rather than substituting a monthly.' },
  { value: 'monthly', label: 'Monthly', hint: 'Nearest eligible monthly contract.' },
] as const;

/** Settings inside Advanced. Counts fields, the way every other panel labels it. */
const ADVANCED_SETTING_COUNT = 9;

const THRESHOLD_KEYS = [
  'min_breakout_atr', 'volume_multiplier', 'vwap_slope_lookback', 'trend_lookback', 'atr_period',
] as const;
const STOP_KEYS = ['stop_buffer_atr', 'target_r'] as const;
const PRICING_KEYS = ['risk_free_rate', 'max_quote_staleness_s'] as const;

export function NiftyOrbOptionsSettings() {
  const { data, isLoading } = useOrbConfig();
  const setCfg = useSetOrbConfig();

  const server = data?.config;
  const defaults = data?.defaults;
  const [draft, setDraft] = React.useState<OrbConfig | null>(null);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  const cfg = draft ?? server ?? null;
  const dirty = draft != null && server != null
    && (Object.keys(draft) as (keyof OrbConfig)[]).some((key) => JSON.stringify(draft[key]) !== JSON.stringify(server[key]));

  const patch = React.useCallback((next: Partial<OrbConfig>) => {
    setDraft((prev) => ({ ...(prev ?? server!), ...next }));
  }, [server]);

  if (isLoading || !cfg || !server) {
    return <div style={{ color: 'var(--t-dim)', fontSize: 11, padding: 16 }}>Loading ORB configuration…</div>;
  }

  const changedFrom = (base: OrbConfig) =>
    (Object.keys(cfg) as (keyof OrbConfig)[])
      .filter((key) => JSON.stringify(cfg[key]) !== JSON.stringify(base[key]));

  // Only send what moved: a full-object PUT would rewrite fields another session
  // changed between this page loading and the save.
  const handleApply = () => {
    if (!draft) return;
    const body: Partial<OrbConfig> = {};
    for (const key of changedFrom(server)) (body as Record<string, unknown>)[key] = cfg[key];
    setCfg.mutate(body, { onSuccess: () => setDraft(null) });
  };
  const handleDiscard = () => setDraft(null);
  const handleReset = () => {
    if (!defaults) return;
    if (!resetConfirm) { setResetConfirm(true); window.setTimeout(() => setResetConfirm(false), 4000); return; }
    setResetConfirm(false);
    // enabled is a power state, not a tuning value — a reset must not silently
    // start or stop the engine.
    setCfg.mutate({ ...defaults, enabled: cfg.enabled }, { onSuccess: () => setDraft(null) });
  };

  const nonDefaultCount = defaults ? changedFrom(defaults).filter((key) => key !== 'enabled').length : 0;
  /** Changed-from-default count for one section, so a summary never reports another section's edits. */
  const changedIn = (keys: readonly (keyof OrbConfig)[]) =>
    defaults ? keys.filter((key) => JSON.stringify(cfg[key]) !== JSON.stringify(defaults[key])).length : 0;
  const changedSummary = (keys: readonly (keyof OrbConfig)[], atDefault: string) => {
    const n = changedIn(keys);
    return n ? `${n} changed from default` : atDefault;
  };
  const universeSummary = cfg.scan_all_stocks
    ? `All F&O · ${cfg.scan_indices.length} indices`
    : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`;
  const num = (key: keyof OrbConfig) => Number(cfg[key]);
  const def = (key: keyof OrbConfig) => (defaults ? Number(defaults[key]) : undefined);

  /** The same default badge a NumberField shows, for choices and switches. */
  const defBadge = (key: keyof OrbConfig, show?: (v: unknown) => string) => {
    if (!defaults) return undefined;
    const fallback = defaults[key];
    const label = show ? show(fallback) : String(fallback);
    return (
      <DefaultBadge
        isDefault={JSON.stringify(cfg[key]) === JSON.stringify(fallback)}
        defaultLabel={label}
        onRestore={() => patch({ [key]: fallback } as Partial<OrbConfig>)}
      />
    );
  };
  const onOff = (v: unknown) => (v ? 'on' : 'off');

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
        name="ORB + VWAP Options"
        tagline="Opening-range breakout confirmed by VWAP. Buys calls on LONG and puts on SHORT — never sells."
        on={cfg.enabled}
        liveOn={server.enabled}
        busy={setCfg.isPending}
        onToggle={() => patch({ enabled: !cfg.enabled })}
        runningNote="Scanning the configured universe every interval and producing option plans."
        offNote="Not scanning. No ORB signals and no ORB entries."
      />

      {/* Panel-wide, so "Reset to defaults" is discoverable and its effect is known
          before it is pressed. Section summaries carry their own scoped counts. */}
      <ConfigNote>
        {nonDefaultCount
          ? <>{nonDefaultCount} setting{nonDefaultCount === 1 ? '' : 's'} differ from the engine defaults. Each one is badged
            with its default and restores on click; <b>Reset to defaults</b> restores all of them and leaves the engine on or off as it is.</>
          : <>Every setting is at the engine default.</>}
      </ConfigNote>

      <PanelCard>
        <Section
          title="Chart source"
          description="Which feed ORB reads bars and option quotes from."
          summary={cfg.data_source === 'kite' ? 'Zerodha Kite' : 'TrueData'}
          defaultOpen
          persistKey="orb-source">
          <Field label="Market data" hint="Order execution stays on Zerodha Kite either way." wide
            badge={defBadge('data_source', (v) => (v === 'kite' ? 'Zerodha Kite' : 'TrueData'))}>
            <ChoiceRow
              value={cfg.data_source}
              options={DATA_SOURCE_OPTIONS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
              onChange={(v) => patch({ data_source: v as OrbConfig['data_source'] })}
            />
          </Field>
        </Section>

        <Section
          title="Instruments"
          description="The indices and F&O stocks this engine watches."
          summary={universeSummary}
          defaultOpen
          persistKey="orb-instruments">
          <InstrumentsGroup
            idPrefix="NIFTY ORB"
            indices={cfg.scan_indices}
            stocks={cfg.scan_stocks}
            allStocks={cfg.scan_all_stocks}
            stockContracts={cfg.scan_stock_contracts}
            onChange={(next) => patch(next as Partial<OrbConfig>)}
            allowEmptyIndices={false}
          />
        </Section>

        <Section
          title="Contracts"
          description="Which strike and expiry the signal is expressed through."
          summary={`${cfg.option_moneyness}${cfg.option_moneyness === 'ATM' ? '' : ` ×${cfg.option_steps_itm}`} · ${cfg.expiry_selection} · ${cfg.expiry_dte_min}-${cfg.expiry_dte_max} DTE`}
          defaultOpen
          persistKey="orb-contracts">
          <Field label="Moneyness" hint="An unavailable moneyness is refused, not silently swapped for the nearest strike." wide
            badge={defBadge('option_moneyness')}>
            <ChoiceRow
              value={cfg.option_moneyness}
              options={MONEYNESS_OPTIONS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
              onChange={(v) => patch({ option_moneyness: v })}
            />
          </Field>
          {cfg.option_moneyness !== 'ATM' && (
            <NumberField
              label={`${cfg.option_moneyness} steps`}
              hint="How many strikes away from the money."
              value={num('option_steps_itm')} defaultValue={def('option_steps_itm')}
              onChange={(v) => patch({ option_steps_itm: v })} min={1} max={5} suffix="strikes"
            />
          )}
          <Field label="Expiry" hint="Weekly and monthly are separated by the venue calendar, not by DTE guesswork." wide
            badge={defBadge('expiry_selection')}>
            <ChoiceRow
              value={cfg.expiry_selection}
              options={EXPIRY_OPTIONS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
              onChange={(v) => patch({ expiry_selection: v })}
            />
          </Field>
          <NumberField
            label="Minimum days to expiry" value={num('expiry_dte_min')} defaultValue={def('expiry_dte_min')}
            onChange={(v) => patch({ expiry_dte_min: v })} min={0} max={365} suffix="days"
          />
          <NumberField
            label="Maximum days to expiry" value={num('expiry_dte_max')} defaultValue={def('expiry_dte_max')}
            onChange={(v) => patch({ expiry_dte_max: v })} min={0} max={365} suffix="days"
          />
          <Field label="Expiry day" hint="Expiry-day options gain and lose value fastest."
            badge={defBadge('avoid_expiry_day', (v) => (v ? 'skipped' : 'allowed'))}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <Switch
                checked={cfg.avoid_expiry_day} label="Avoid expiry-day entries"
                onChange={() => patch({ avoid_expiry_day: !cfg.avoid_expiry_day })}
              />
              <span style={{ color: TEXT, fontSize: 11.5 }}>{cfg.avoid_expiry_day ? 'Skipped' : 'Allowed'}</span>
            </div>
          </Field>
        </Section>

        <Section
          title="Session"
          description="When the range is measured and when entries may fire."
          summary={`${cfg.opening_range_minutes}m range · ${cfg.entry_start}–${cfg.entry_end} · ${cfg.interval_minutes}m bars`}
          defaultOpen
          persistKey="orb-session">
          <Field label="Entry window" hint="The opening range is always anchored to 09:15 IST regardless of this window." wide
            badge={defaults ? (
              <DefaultBadge
                isDefault={cfg.entry_start === defaults.entry_start && cfg.entry_end === defaults.entry_end}
                defaultLabel={`${defaults.entry_start}\u2013${defaults.entry_end}`}
                onRestore={() => patch({ entry_start: defaults.entry_start, entry_end: defaults.entry_end })}
              />
            ) : undefined}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input type="time" value={cfg.entry_start} onChange={(e) => patch({ entry_start: e.target.value })}
                style={{ border: `1px solid ${BORDER}`, borderRadius: 6, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 }} />
              <span style={{ color: TEXT, fontSize: 11 }}>to</span>
              <input type="time" value={cfg.entry_end} onChange={(e) => patch({ entry_end: e.target.value })}
                style={{ border: `1px solid ${BORDER}`, borderRadius: 6, padding: '6px 8px', fontFamily: 'inherit', fontSize: 12 }} />
            </div>
          </Field>
          <NumberField
            label="Opening range" hint="Minutes from 09:15 that define the range being broken."
            value={num('opening_range_minutes')} defaultValue={def('opening_range_minutes')}
            onChange={(v) => patch({ opening_range_minutes: v })} min={5} max={60} step={5} suffix="min"
          />
          <NumberField
            label="Bar interval" value={num('interval_minutes')} defaultValue={def('interval_minutes')}
            onChange={(v) => patch({ interval_minutes: v })} min={1} max={15} suffix="min"
          />
        </Section>

        <Section
          title="Risk"
          description="What one ORB trade may cost, and how many may run."
          summary={`₹${cfg.max_risk_inr.toLocaleString('en-IN')} · ${cfg.max_trades_per_day}/day`}
          defaultOpen
          persistKey="orb-risk">
          <NumberField
            label="Maximum risk per trade"
            hint="Sizing uses the full premium — a bought option can expire worthless, so this is the real ceiling."
            value={num('max_risk_inr')} defaultValue={def('max_risk_inr')}
            onChange={(v) => patch({ max_risk_inr: v })} min={500} step={500} suffix="₹"
          />
          <NumberField
            label="Maximum trades per day" value={num('max_trades_per_day')} defaultValue={def('max_trades_per_day')}
            onChange={(v) => patch({ max_trades_per_day: v })} min={1} max={20}
          />
          <ConfigNote>
            Paper/live and manual/automatic are <b>not</b> ORB settings — they belong to the universal
            Trading Mode, and ORB uses the shared safety, idempotency and position-protection path.
          </ConfigNote>
        </Section>

        <Section
          title="Liquidity"
          description="Contracts ORB refuses to trade."
          summary={`≤${cfg.max_spread_pct}% spread · ${cfg.min_option_volume.toLocaleString('en-IN')} vol · ${cfg.min_open_interest.toLocaleString('en-IN')} OI`}
          persistKey="orb-liquidity">
          <NumberField
            label="Maximum bid/ask spread" value={num('max_spread_pct')} defaultValue={def('max_spread_pct')}
            onChange={(v) => patch({ max_spread_pct: v })} min={0.1} max={10} step={0.1} suffix="%"
          />
          <NumberField
            label="Minimum option volume" value={num('min_option_volume')} defaultValue={def('min_option_volume')}
            onChange={(v) => patch({ min_option_volume: v })} min={0} step={100}
          />
          <NumberField
            label="Minimum open interest" value={num('min_open_interest')} defaultValue={def('min_open_interest')}
            onChange={(v) => patch({ min_open_interest: v })} min={0} step={1000}
          />
        </Section>

        {cfg.data_source === 'truedata' && (
          <Section
            title="TrueData validation"
            description="Which TrueData observations gate a contract."
            summary={[cfg.truedata_use_ticks && 'ticks', cfg.truedata_use_bid_ask && 'bid/ask', cfg.truedata_use_oi && 'OI', cfg.truedata_use_quote_freshness && 'freshness'].filter(Boolean).join(' · ') || 'all off'}
            persistKey="orb-truedata">
            <Field label="Realtime ticks" hint="Quote freshness is measured from the tick stamp, so it requires ticks."
              badge={defBadge('truedata_use_ticks', onOff)}>
              <Switch
                checked={cfg.truedata_use_ticks} label="Use ticks"
                onChange={() => patch({
                  truedata_use_ticks: !cfg.truedata_use_ticks,
                  ...(cfg.truedata_use_ticks ? { truedata_use_quote_freshness: false } : {}),
                })}
              />
            </Field>
            <Field label="Quote freshness" hint={cfg.truedata_use_ticks ? 'Reject a contract whose last tick is stale.' : 'Requires realtime ticks.'}
              badge={defBadge('truedata_use_quote_freshness', onOff)}>
              <Switch
                checked={cfg.truedata_use_quote_freshness} label="Reject stale quotes" disabled={!cfg.truedata_use_ticks}
                onChange={() => cfg.truedata_use_ticks && patch({ truedata_use_quote_freshness: !cfg.truedata_use_quote_freshness })}
              />
            </Field>
            <Field label="Bid / ask" hint="Enforce the spread ceiling and reject a crossed market."
              badge={defBadge('truedata_use_bid_ask', onOff)}>
              <Switch checked={cfg.truedata_use_bid_ask} label="Use bid/ask"
                onChange={() => patch({ truedata_use_bid_ask: !cfg.truedata_use_bid_ask })} />
            </Field>
            <Field label="Open interest" hint="Enforce the open-interest floor."
              badge={defBadge('truedata_use_oi', onOff)}>
              <Switch checked={cfg.truedata_use_oi} label="Use OI"
                onChange={() => patch({ truedata_use_oi: !cfg.truedata_use_oi })} />
            </Field>
          </Section>
        )}

        <AdvancedSection count={ADVANCED_SETTING_COUNT}>
          <Section
            title="Signal thresholds"
            description="The filters a bar must clear. Every value shows whether it is still the engine default."
            summary={changedSummary(THRESHOLD_KEYS, 'all at default')}
            defaultOpen
            persistKey="orb-thresholds">
            <NumberField
              label="Minimum breakout" hint="How far past the opening range the close must be, in ATR."
              value={num('min_breakout_atr')} defaultValue={def('min_breakout_atr')}
              onChange={(v) => patch({ min_breakout_atr: v })} min={0} step={0.05} suffix="ATR"
            />
            <NumberField
              label="Volume confirmation" hint="Current bar volume against this session's baseline. Must be above zero — zero is rejected, not treated as off."
              value={num('volume_multiplier')} defaultValue={def('volume_multiplier')}
              onChange={(v) => patch({ volume_multiplier: v })} min={0.1} step={0.05} suffix="×"
            />
            <NumberField
              label="VWAP slope lookback" value={num('vwap_slope_lookback')} defaultValue={def('vwap_slope_lookback')}
              onChange={(v) => patch({ vwap_slope_lookback: v })} min={1} max={20} suffix="bars"
            />
            <NumberField
              label="Trend lookback" hint="Bars used to classify TREND / EXPANSION / RANGE."
              value={num('trend_lookback')} defaultValue={def('trend_lookback')}
              onChange={(v) => patch({ trend_lookback: v })} min={2} max={50} suffix="bars"
            />
            <NumberField
              label="ATR period" value={num('atr_period')} defaultValue={def('atr_period')}
              onChange={(v) => patch({ atr_period: v })} min={5} max={100} suffix="bars"
            />
          </Section>

          <Section
            title="Stop and target"
            description="How the underlying stop and target are derived."
            summary={changedSummary(STOP_KEYS, `${cfg.stop_buffer_atr} ATR stop · ${cfg.target_r}R target`)}
            persistKey="orb-stop">
            <NumberField
              label="Stop buffer" hint="Underlying stop distance in ATR. The premium stop is derived from it via delta."
              value={num('stop_buffer_atr')} defaultValue={def('stop_buffer_atr')}
              onChange={(v) => patch({ stop_buffer_atr: v })} min={0} step={0.05} suffix="ATR"
            />
            <NumberField
              label="Target" value={num('target_r')} defaultValue={def('target_r')}
              onChange={(v) => patch({ target_r: v })} min={0.5} step={0.25} suffix="R"
            />
            <ConfigNote>
              Trailing is <b>not</b> an ORB setting. Once a position is open the universal Trading Mode
              owns the trail and the protection path.
            </ConfigNote>
          </Section>

          <Section
            title="Pricing and quotes"
            description="Inputs to the implied-volatility solve and the freshness gate."
            summary={changedSummary(PRICING_KEYS, `${(cfg.risk_free_rate * 100).toFixed(2)}% rate · ${cfg.max_quote_staleness_s}s`)}
            persistKey="orb-pricing">
            <NumberField
              label="Risk-free rate" hint="Used to solve implied volatility from the traded premium, which gives the delta behind the premium stop."
              value={num('risk_free_rate')} defaultValue={def('risk_free_rate')}
              onChange={(v) => patch({ risk_free_rate: v })} min={0} max={0.25} step={0.005}
              format={(v) => `${(v * 100).toFixed(2)}%`} suffix={`= ${(cfg.risk_free_rate * 100).toFixed(2)}%`}
            />
            <NumberField
              label="Maximum quote age" value={num('max_quote_staleness_s')} defaultValue={def('max_quote_staleness_s')}
              onChange={(v) => patch({ max_quote_staleness_s: v })} min={1} max={120} suffix="sec"
            />
          </Section>
        </AdvancedSection>
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

export default NiftyOrbOptionsSettings;
