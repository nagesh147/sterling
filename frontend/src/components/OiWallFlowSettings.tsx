import React from 'react';
import {
  useOiWallFlowConfig,
  useUpdateOiWallFlow,
  type ExpirySelection,
  type OIWallFlowConfig,
  type StopMode,
} from '../hooks/useOiWallFlow';
import {
  ChoiceRow, Field, NumberField, Section, Switch, DIM,
} from './kite/kiteSettingsPrimitives';
import { AdvancedSection, ConfigNote, PanelCard, SettingsDraftBar } from './kite/config/ConfigPrimitives';
import { InstrumentsGroup } from './kite/config/ScanSettings';
import { OptionContractsPicker } from './kite/config/OptionContractsPicker';
import { EnginePowerHeader } from './kite/config/EnginePowerHeader';

const EXPIRY_SELECTION_OPTIONS: Array<{ value: ExpirySelection; label: string; hint: string }> = [
  { value: 'nearest', label: 'Nearest', hint: 'The soonest eligible contract.' },
  { value: 'weekly', label: 'Weekly', hint: 'Weekly series only. Indices have them; NSE lists no weekly stock options.' },
  { value: 'monthly', label: 'Monthly', hint: 'Monthly series only — the only series single stocks have.' },
  { value: 'any', label: 'Any', hint: 'No preference beyond the days-to-expiry window.' },
];

const STOP_MODE_OPTIONS: Array<{ value: StopMode; label: string; hint: string }> = [
  { value: 'both', label: 'Broker + monitor', hint: 'A GTT at Zerodha that survives this process dying, plus our own tick loop for intrabar exits. The production answer.' },
  { value: 'broker', label: 'Broker only', hint: 'A GTT and nothing else. Survives a crash, but only exits on a completed trigger — no intrabar exit.' },
  { value: 'monitor', label: 'Monitor only', hint: 'Our tick loop and nothing at the broker. If this process dies while holding, the position is unprotected.' },
];

const ADVANCED_SETTING_COUNT = 5;

export function OiWallFlowSettings() {
  const { data, isLoading } = useOiWallFlowConfig();
  const setCfg = useUpdateOiWallFlow();

  const server = data?.config;
  const defaults = data?.defaults;
  const strategy = data?.strategy;
  const eligible = data?.vocabularies?.scan_stocks ?? [];
  const warnings = data?.warnings ?? [];

  const [draft, setDraft] = React.useState<OIWallFlowConfig | null>(null);
  const [resetConfirm, setResetConfirm] = React.useState(false);

  const cfg = draft ?? server ?? null;
  const dirty = draft != null && server != null
    && (Object.keys(draft) as (keyof OIWallFlowConfig)[])
      .some((key) => JSON.stringify(draft[key]) !== JSON.stringify(server[key]));

  const patch = React.useCallback((next: Partial<OIWallFlowConfig>) => {
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

  const judgement = (key: string, hint: string): string => {
    const note = strategy.calibration?.[key];
    return note ? `${hint} Judgement: ${note}.` : hint;
  };

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
        runningNote="Reading option chains for writer covering at the first-resistance CE or first-support PE."
        offNote="Off. Nothing is scanned and no orders can be placed."
      />

      <ConfigNote>
        <span>
          <strong>Not validated.</strong> {strategy.headline_finding}
          {strategy.what_to_do ? ` ${strategy.what_to_do}` : ''}
        </span>
      </ConfigNote>
      {strategy.evidence && (
        <ConfigNote><span>{strategy.evidence}</span></ConfigNote>
      )}
      <ConfigNote>
        <span>{strategy.how_it_works} {strategy.provenance}</span>
      </ConfigNote>
      <ConfigNote>
        <span>
          <strong>Paper or live, manual or auto</strong> are set in{' '}
          <strong>Trading Mode</strong> and apply to every Kite strategy. This page
          does not carry its own copy.
        </span>
      </ConfigNote>

      {warnings.map((w) => (
        <ConfigNote key={w}><span>{w}</span></ConfigNote>
      ))}

      <Section
        title="Instruments"
        description="The indices and F&O stocks this engine watches. SENSEX is skipped in v1 — it lives on BFO."
        summary={cfg.stock_contracts
          ? (cfg.scan_all_stocks
            ? `all ${eligible.length} high-liquidity stocks`
            : `${cfg.scan_stocks.length} of ${eligible.length} stocks`)
          : 'indices only'}
        persistKey="oiwf-instruments"
        defaultOpen
      >
        <InstrumentsGroup
          idPrefix="oiwf"
          indices={cfg.scan_indices}
          stocks={cfg.scan_stocks}
          allStocks={cfg.scan_all_stocks}
          stockContracts={cfg.stock_contracts}
          allowEmptyIndices
          onChange={(next) => patch({
            ...(next.scan_indices !== undefined ? { scan_indices: next.scan_indices } : {}),
            ...(next.scan_stocks !== undefined ? { scan_stocks: next.scan_stocks } : {}),
            ...(next.scan_all_stocks !== undefined
              ? { scan_all_stocks: next.scan_all_stocks } : {}),
            ...(next.scan_stock_contracts !== undefined
              ? { stock_contracts: next.scan_stock_contracts } : {}),
          })}
        />
      </Section>

      <Section
        title="Contracts"
        description="Which expiry the chain is read from."
        summary={`${cfg.expiry_selection} · ${cfg.expiry_dte_min}-${cfg.expiry_dte_max} DTE`}
        persistKey="oiwf-contracts"
        defaultOpen
      >
        <Field label="Expiry" hint="Which listed contract the signal is expressed through.">
          <ChoiceRow
            value={cfg.expiry_selection}
            options={EXPIRY_SELECTION_OPTIONS}
            onChange={(v) => patch({ expiry_selection: v })}
          />
        </Field>
        <NumberField
          label="Minimum days to expiry"
          hint={judgement('avoid_expiry_day', 'Contracts closer than this are not eligible.')}
          value={cfg.expiry_dte_min} defaultValue={defaults.expiry_dte_min}
          onChange={(v) => patch({ expiry_dte_min: v })} min={0} max={60} step={1}
        />
        <NumberField
          label="Maximum days to expiry"
          hint="The BSE motivating chain was 32 DTE. Far-dated OI is a different picture."
          value={cfg.expiry_dte_max} defaultValue={defaults.expiry_dte_max}
          onChange={(v) => patch({ expiry_dte_max: v })} min={0} max={90} step={1}
        />
        <Field label="Expiry day" hint="On expiry day OI is settlement, not positioning.">
          <Switch
            checked={cfg.avoid_expiry_day}
            label="Avoid expiry-day entries"
            onChange={() => patch({ avoid_expiry_day: !cfg.avoid_expiry_day })}
          />
        </Field>
        <NumberField
          label="Minimum premium"
          hint={judgement('min_option_premium', 'Contracts cheaper than this are skipped.')}
          value={cfg.min_option_premium} defaultValue={defaults.min_option_premium}
          onChange={(v) => patch({ min_option_premium: v })} min={0.05} max={200} step={1} suffix="₹"
        />
        <NumberField
          label="Minimum open interest"
          hint="A contract with thin open interest has no writers to squeeze."
          value={cfg.min_option_oi} defaultValue={defaults.min_option_oi}
          onChange={(v) => patch({ min_option_oi: v })} min={0} step={50}
        />
        <OptionContractsPicker
          title="Option contracts"
          config={{
            scan_indices: cfg.scan_indices,
            scan_stocks: cfg.scan_stocks,
            scan_all_stocks: cfg.scan_all_stocks,
            scan_weekly_series_indices: cfg.scan_weekly_series_indices,
            scan_monthly_series_indices: cfg.scan_monthly_series_indices,
            scan_monthly_series_stocks: cfg.scan_monthly_series_stocks,
          }}
          saving={setCfg.isPending}
          onSave={(p) => patch(p as Partial<OIWallFlowConfig>)}
        />
      </Section>

      <Section
        title="Chain reading"
        description="How the engine classifies flow and picks a strike."
        summary={`deadband ${cfg.oi_chg_deadband_pct}% · ATM ±${cfg.atm_window_strikes} · score ≥ ${cfg.min_bias_score}`}
        persistKey="oiwf-chain"
        defaultOpen
      >
        <NumberField
          label="OI change deadband"
          hint={judgement('oi_chg_deadband_pct', 'A print inside this is noise, not a buildup.')}
          value={cfg.oi_chg_deadband_pct} defaultValue={defaults.oi_chg_deadband_pct}
          onChange={(v) => patch({ oi_chg_deadband_pct: v })} min={0} max={5} step={0.1} suffix="%"
        />
        <NumberField
          label="Premium change deadband"
          hint={judgement('ltp_chg_deadband_pct', 'Same, for the option premium.')}
          value={cfg.ltp_chg_deadband_pct} defaultValue={defaults.ltp_chg_deadband_pct}
          onChange={(v) => patch({ ltp_chg_deadband_pct: v })} min={0} max={5} step={0.1} suffix="%"
        />
        <NumberField
          label="ATM window"
          hint={judgement('atm_window_strikes', 'Strikes inside this carry the directional vote.')}
          value={cfg.atm_window_strikes} defaultValue={defaults.atm_window_strikes}
          onChange={(v) => patch({ atm_window_strikes: v })} min={0} max={10} step={1}
        />
        <NumberField
          label="Minimum bias score"
          hint={judgement('min_bias_score', 'Three confirming flow votes before a trade, on the motivating chain.')}
          value={cfg.min_bias_score} defaultValue={defaults.min_bias_score}
          onChange={(v) => patch({ min_bias_score: v })} min={0.5} max={10} step={0.5}
        />
        <Field label="Prefer the wall" hint={judgement('prefer_wall_strike', 'Buy the wall when it is the first OTM strike in the trade’s direction — the BSE 3500 CE case.')}>
          <Switch
            checked={cfg.prefer_wall_strike}
            label="Buy the wall, not the nearest OTM"
            onChange={() => patch({ prefer_wall_strike: !cfg.prefer_wall_strike })}
          />
        </Field>
        <Field label="Skip ATM" hint="ATM premia pay more theta for a worse RR. The BSE chain’s 3400 CE is ATM and must never be the trade.">
          <Switch
            checked={cfg.skip_atm}
            label="Never buy ATM"
            onChange={() => patch({ skip_atm: !cfg.skip_atm })}
          />
        </Field>
      </Section>

      <Section
        title="Exit and stop"
        description="Stops are on the premium. A second kill is the opposing wall breaking on the underlying."
        summary={`−${cfg.stop_premium_pct}% / +${cfg.target_premium_pct}% / +${cfg.target_2_premium_pct}%`}
        persistKey="oiwf-exit"
      >
        <NumberField
          label="Premium stop"
          hint={judgement('stop_premium_pct', 'The option itself lost this much.')}
          value={cfg.stop_premium_pct} defaultValue={defaults.stop_premium_pct}
          onChange={(v) => patch({ stop_premium_pct: v })} min={1} max={95} step={1} suffix="%"
        />
        <NumberField
          label="First target"
          hint={judgement('target_premium_pct', 'First scale, roughly spot into the wall.')}
          value={cfg.target_premium_pct} defaultValue={defaults.target_premium_pct}
          onChange={(v) => patch({ target_premium_pct: v })} min={1} max={400} step={5} suffix="%"
        />
        <NumberField
          label="Runner target"
          hint={judgement('target_2_premium_pct', 'If the wall gives way.')}
          value={cfg.target_2_premium_pct} defaultValue={defaults.target_2_premium_pct}
          onChange={(v) => patch({ target_2_premium_pct: v })} min={1} max={500} step={5} suffix="%"
        />
        <Field label="Wall invalidation" hint="Exit if spot prints through the opposing OI wall, even if the premium has not caught up.">
          <Switch
            checked={cfg.wall_invalidation}
            label="Kill on opposing-wall break"
            onChange={() => patch({ wall_invalidation: !cfg.wall_invalidation })}
          />
        </Field>
        <Field label="Where the stop lives" hint="What watches the position if this process dies.">
          <ChoiceRow value={cfg.stop_mode} options={STOP_MODE_OPTIONS}
                     onChange={(v) => patch({ stop_mode: v })} />
        </Field>
      </Section>

      <Section
        title="Size and risk"
        description="How large each trade is, and what stops it trading."
        summary={`${cfg.lots} lots · cap ₹${cfg.max_premium_at_risk_inr.toLocaleString('en-IN')}`}
        persistKey="oiwf-risk"
      >
        <NumberField
          label="Lots" hint="Exchange lots per trade. The lot size comes from the contract."
          value={cfg.lots} defaultValue={defaults.lots}
          onChange={(v) => patch({ lots: v })} min={1} max={100} step={1}
        />
        <NumberField
          label="Premium at risk cap"
          hint="(entry − stop) × quantity may not exceed this."
          value={cfg.max_premium_at_risk_inr} defaultValue={defaults.max_premium_at_risk_inr}
          onChange={(v) => patch({ max_premium_at_risk_inr: v })} min={1000} step={1000} suffix="₹"
        />
        <NumberField
          label="Concurrent positions"
          value={cfg.max_concurrent_positions} defaultValue={defaults.max_concurrent_positions}
          onChange={(v) => patch({ max_concurrent_positions: v })} min={1} max={20} step={1}
        />
        <NumberField
          label="Daily loss limit"
          value={cfg.daily_loss_limit_inr} defaultValue={defaults.daily_loss_limit_inr}
          onChange={(v) => patch({ daily_loss_limit_inr: v })} min={1000} step={1000} suffix="₹"
        />
        <NumberField
          label="De-scale after losses"
          value={cfg.descale_after_losses} defaultValue={defaults.descale_after_losses}
          onChange={(v) => patch({ descale_after_losses: v })} min={1} max={10} step={1}
        />
      </Section>

      <AdvancedSection count={ADVANCED_SETTING_COUNT}>
        <NumberField
          label="Scan interval" hint="How often the background scan runs."
          value={cfg.scan_interval_seconds} defaultValue={defaults.scan_interval_seconds}
          onChange={(v) => patch({ scan_interval_seconds: v })} min={60} max={3600} step={60} suffix="s"
        />
        <NumberField
          label="New trades per day"
          value={cfg.max_new_trades_per_day} defaultValue={defaults.max_new_trades_per_day}
          onChange={(v) => patch({ max_new_trades_per_day: v })} min={1} max={20} step={1}
        />
        <NumberField
          label="Re-scale after wins"
          value={cfg.rescale_after_wins} defaultValue={defaults.rescale_after_wins}
          onChange={(v) => patch({ rescale_after_wins: v })} min={1} max={10} step={1}
        />
        <Field label="Session start" hint="A few minutes after the open so session OI has something to difference against. Kite quotes have no previous-close OI — the first quote of the day is the baseline.">
          <input
            type="time" value={cfg.session_start}
            onChange={(e) => patch({ session_start: e.target.value })}
            style={{ background: 'transparent', border: '1px solid var(--k-border)',
                     borderRadius: 6, color: 'var(--k-text)', padding: '4px 8px', fontSize: 12 }}
          />
        </Field>
        <Field label="Session end" hint="Scanning stops here; open positions are still watched out.">
          <input
            type="time" value={cfg.session_end}
            onChange={(e) => patch({ session_end: e.target.value })}
            style={{ background: 'transparent', border: '1px solid var(--k-border)',
                     borderRadius: 6, color: 'var(--k-text)', padding: '4px 8px', fontSize: 12 }}
          />
        </Field>
      </AdvancedSection>
    </>
  );
}
