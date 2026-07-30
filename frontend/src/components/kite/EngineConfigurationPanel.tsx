import React from 'react';
import {
  useEngineConfig,
  useResetEngineConfig,
  useRunScan,
  useSetEngineConfig,
  useStockRegistry,
} from '../../hooks/useSterlingKiteEngine';
import { notifyOrder } from '../../store/useKiteNotifications';
import type {
  EngineConfigModel,
  ExitMode,
  Moneyness,
  ScanExpiry,
  ScanSource,
  TrailTarget,
} from '../../types/kiteEngine';
import {
  BORDER, CheckOption, ChoiceRow, DIM, Field, MUTED, ORANGE, ORANGE_SOFT, Section, SOFT, Switch, TEXT, inputStyle,
} from './kiteSettingsPrimitives';

const GREEN = '#4caf50';

/** A setting that lives in the shared Scan Setup section, shown read-only
 *  here with a one-click jump — so it's obvious the value is real and in
 *  effect, but equally obvious this isn't the place to change it (changing
 *  it here would silently move Navigator too). */
export function SharedSettingPointer({ value }: { value: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
      <span style={{
        padding: '6px 11px', borderRadius: 7, background: SOFT, border: `1px solid ${BORDER}`,
        color: TEXT, fontSize: 12, fontWeight: 600,
      }}>
        {value}
      </span>
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent('kite-connect-section', { detail: 'sharedScan' }))}
        style={{
          border: 'none', background: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit',
          color: ORANGE, fontSize: 11, fontWeight: 700,
        }}
      >
        Change in Scan Setup →
      </button>
    </div>
  );
}

const SOURCE_OPTIONS: Array<{ value: ScanSource; label: string; description: string }> = [
  { value: 'spot', label: 'Spot', description: 'Signals from the underlying chart.' },
  { value: 'derivatives', label: 'Derivatives', description: 'Signals from each option premium chart.' },
  { value: 'both', label: 'Both', description: 'Run spot and premium scans side by side.' },
  { value: 'confluence', label: 'Confluence', description: 'Require spot and premium confirmation.' },
];

const STRIKE_GROUPS: Array<{ label: string; hint: string; values: Moneyness[] }> = [
  { label: 'Deep ITM', hint: 'δ ≈ 0.80+', values: ['ITM5', 'ITM4'] },
  { label: 'ITM', hint: 'δ ≈ 0.60–0.80', values: ['ITM3', 'ITM2', 'ITM1'] },
  { label: 'ATM', hint: 'δ ≈ 0.50', values: ['ATM'] },
  { label: 'OTM', hint: 'δ ≈ 0.30–0.45', values: ['OTM1', 'OTM2'] },
  { label: 'Far OTM', hint: 'δ ≲ 0.25', values: ['OTM3', 'OTM4', 'OTM5'] },
];

const INDEX_OPTIONS = [
  { value: 'NIFTY 50', label: 'NIFTY' },
  { value: 'NIFTY BANK', label: 'BANKNIFTY' },
  { value: 'NIFTY FIN SERVICE', label: 'FINNIFTY' },
  { value: 'SENSEX', label: 'SENSEX' },
];

const TRAIL_OPTIONS: Array<{ value: TrailTarget; label: string }> = [
  { value: 'fast', label: 'Tight' },
  { value: 'mid', label: 'Balanced' },
  { value: 'slow', label: 'Loose' },
];

const EXIT_OPTIONS: Array<{ value: ExitMode; label: string }> = [
  { value: 'one_red', label: '1 Red' },
  { value: 'two_red', label: '2 Red' },
  { value: 'three_red', label: '3 Red' },
  { value: 'three_red_signal', label: '3R + Signal' },
];

const STOP_OPTIONS: Array<{ value: EngineConfigModel['stop_mode']; label: string }> = [
  { value: 'both', label: 'Both' },
  { value: 'broker', label: 'Broker' },
  { value: 'monitor', label: 'Monitor' },
];

function sourceLabel(source: ScanSource): string {
  return SOURCE_OPTIONS.find((item) => item.value === source)?.label ?? source;
}

export function EngineConfigurationPanel() {
  const { data: cfg } = useEngineConfig();
  const { data: stockRegistry } = useStockRegistry();
  const setCfg = useSetEngineConfig();
  const runScan = useRunScan();
  const resetCfg = useResetEngineConfig();

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading engine configuration…</div>;
  }

  const patch = (values: Partial<EngineConfigModel>, message: string, rescan = false) => {
    setCfg.mutate({ ...cfg, ...values }, {
      onSuccess: () => {
        notifyOrder({ kind: 'info', title: 'Engine configuration updated', message });
        if (rescan) runScan.mutate();
      },
    });
  };

  const toggleListValue = <T extends string>(current: T[], value: T, fallback: T[]): T[] => {
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    return next.length ? next : fallback;
  };

  const toggleStrikeGroup = (values: Moneyness[]) => {
    const allSelected = values.every((value) => cfg.strike_moneyness.includes(value));
    const next = allSelected
      ? cfg.strike_moneyness.filter((value) => !values.includes(value))
      : [...new Set([...cfg.strike_moneyness, ...values])];
    patch({ strike_moneyness: next.length ? next : ['ATM'] }, 'Strike coverage updated', true);
  };

  const indexExpiries = cfg.scan_expiries_indices ?? cfg.scan_expiries;
  const enabledGuards = [
    (cfg.expiry_square_off_days ?? 0) > 0,
    (cfg.time_stop_bars ?? 0) > 0,
    (cfg.block_entry_minutes_before_close ?? 0) > 0,
    cfg.max_spread_pct != null,
    cfg.min_oi != null,
    cfg.max_daily_loss_pct != null,
  ].filter(Boolean).length;

  return (
    <section style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 9, overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 18px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ color: TEXT, fontSize: 14.5, fontWeight: 800 }}>Engine configuration</div>
          <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 3 }}>
            Signal discovery, market universe, exits and risk live here. Changes save automatically.
          </div>
        </div>
        <span aria-live="polite" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: setCfg.isPending ? MUTED : GREEN, fontSize: 10.5, fontWeight: 700 }}>
          <span aria-hidden style={{ width: 6, height: 6, borderRadius: '50%', background: setCfg.isPending ? '#c2c2c2' : GREEN }} />
          {setCfg.isPending ? 'Saving…' : 'Saved'}
        </span>
      </div>

      <Section
        title="Signal Discovery"
        description="Choose how setups are found and which contracts are evaluated."
        summary={`${sourceLabel(cfg.scan_source)} · ${cfg.strike_moneyness.length} strikes`}
        defaultOpen
      >
        <Field label="Signal source" hint="Shared with the Value-Flow Navigator, so it lives in Scan Setup.">
          <SharedSettingPointer value={sourceLabel(cfg.scan_source)} />
        </Field>
        <Field label="Strike coverage" hint="View and scan coverage; at least ATM remains selected.">
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(132px, 1fr))', gap: 7 }}>
            {STRIKE_GROUPS.map((group) => {
              const count = group.values.filter((value) => cfg.strike_moneyness.includes(value)).length;
              return (
                <CheckOption key={group.label} label={group.label} hint={group.hint}
                  checked={count === group.values.length} indeterminate={count > 0 && count < group.values.length}
                  onChange={() => toggleStrikeGroup(group.values)} />
              );
            })}
          </div>
        </Field>
        <Field label="Index expiries" hint="Contract cycles scanned for indices.">
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(120px, 190px))', gap: 7 }}>
            {(['weekly', 'monthly'] as ScanExpiry[]).map((expiry) => (
              <CheckOption key={expiry} label={expiry === 'weekly' ? 'Weekly indices' : 'Monthly indices'} checked={indexExpiries.includes(expiry)}
                onChange={() => patch({ scan_expiries_indices: toggleListValue(indexExpiries, expiry, ['weekly', 'monthly']) }, 'Index expiries updated', true)} />
            ))}
          </div>
        </Field>
        <Field label="Stock expiries" hint="Individual-stock derivatives do not have a weekly contract cycle.">
          <div style={{ minHeight: 42, maxWidth: 390, display: 'grid', gridTemplateColumns: '16px minmax(0, 1fr)', alignItems: 'center', gap: 9, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '7px 10px', background: SOFT, boxSizing: 'border-box' }}>
            <span aria-hidden style={{ width: 15, height: 15, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', borderRadius: 4, background: ORANGE, color: '#fff', fontSize: 10, fontWeight: 800 }}>✓</span>
            <span>
              <span style={{ display: 'block', color: TEXT, fontSize: 11.5, fontWeight: 700 }}>Monthly stock contracts</span>
              <span style={{ display: 'block', color: DIM, fontSize: 9.5, marginTop: 2 }}>Applied automatically to the selected F&amp;O stocks.</span>
            </span>
          </div>
        </Field>
      </Section>

      <Section
        title="Market Universe"
        description="Shared with the Value-Flow Navigator — edited once, in Scan Setup."
        summary={cfg.scan_all_stocks ? `All F&O · ${cfg.scan_indices.length} indices` : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`}
      >
        <Field label="Instruments" hint="Both engines scan this same list.">
          <SharedSettingPointer
            value={cfg.scan_all_stocks
              ? `${cfg.scan_indices.length} indices + all F&O stocks`
              : `${cfg.scan_indices.length} indices + ${cfg.scan_stocks.length} stocks`}
          />
        </Field>
      </Section>

      <Section
        title="Exit & Protection"
        description="Tune exit confirmation and broker/server protection."
        summary={`${TRAIL_OPTIONS.find((item) => item.value === cfg.trail_target)?.label} trail · ${EXIT_OPTIONS.find((item) => item.value === cfg.exit_mode)?.label}`}
      >
        <Field label="Trailing style">
          <ChoiceRow value={cfg.trail_target} options={TRAIL_OPTIONS}
            onChange={(value) => patch({ trail_target: value }, `Trailing changed to ${value}`, true)} />
        </Field>
        <Field label="Exit confirmation" hint="Entry always requires three green lines and a fresh green signal.">
          <ChoiceRow value={cfg.exit_mode} options={EXIT_OPTIONS}
            onChange={(value) => patch({ exit_mode: value }, `Exit confirmation changed to ${value}`, true)} />
        </Field>
        <Field label="Stop anchor" hint="Validated default follows the tight fast line.">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch checked={cfg.exit_aligned_trail ?? false} label="Anchor stop to exit counter"
              onChange={() => patch({ exit_aligned_trail: !(cfg.exit_aligned_trail ?? false) }, 'Stop anchor updated', true)} />
            <span style={{ color: TEXT, fontSize: 11.5 }}>{cfg.exit_aligned_trail ? 'Aligned to exit counter' : 'Tightest fast line'}</span>
          </div>
        </Field>
        <Field label="Trailing stop exits" hint="On: a trade is closed the first bar price trades through its trail. Off restores the old rule, where only the exit counter could close a trade — so a position could sit indefinitely below its own stop.">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch checked={cfg.price_stop_exit ?? true} label="Enforce the trailing stop as a real exit"
              onChange={() => patch({ price_stop_exit: !(cfg.price_stop_exit ?? true) }, 'Trailing-stop exit updated', true)} />
            <span style={{ color: TEXT, fontSize: 11.5 }}>
              {(cfg.price_stop_exit ?? true) ? 'Trail OR exit counter, whichever fires first' : 'Exit counter only'}
            </span>
          </div>
        </Field>
        <Field label="Hybrid weight" hint="SuperTrend weight from 0 to 1.">
          <input data-testid="hybrid-weight-input" aria-label="Hybrid weight" type="number" min={0} max={1} step={0.1}
            value={cfg.hybrid_st_weight ?? 0.5} style={inputStyle}
            onChange={(event) => patch({ hybrid_st_weight: Number(event.target.value) }, 'Hybrid trail weight updated', true)} />
        </Field>
        <Field label="Protection mode" hint="Both is recommended for live trading.">
          <ChoiceRow value={cfg.stop_mode} options={STOP_OPTIONS}
            onChange={(value) => patch({ stop_mode: value }, `Protection mode changed to ${value}`)} />
        </Field>
      </Section>

      <Section
        title="Risk & Safeguards"
        description="Position sizing and optional guardrails for automatic execution."
        summary={`${cfg.risk_sizing ? `${cfg.risk_pct}% risk` : 'Fixed size'} · ${enabledGuards} guards`}
      >
        <Field label="Risk sizing">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Switch checked={cfg.risk_sizing} label="Risk-based sizing"
              onChange={() => patch({ risk_sizing: !cfg.risk_sizing }, `Risk sizing ${!cfg.risk_sizing ? 'enabled' : 'disabled'}`)} />
            <span style={{ color: TEXT, fontSize: 11.5 }}>Size positions from available capital</span>
            {cfg.risk_sizing && <><input aria-label="Risk percent" type="number" min={0.1} max={25} step={0.5} value={cfg.risk_pct} style={inputStyle}
              onChange={(event) => patch({ risk_pct: Number(event.target.value) }, 'Risk percentage updated')} /><span style={{ color: DIM, fontSize: 11 }}>% per trade</span></>}
          </div>
        </Field>
        <Field label="Maximum lots">
          <input aria-label="Maximum lots" type="number" min={1} step={1} value={cfg.max_lots} style={inputStyle}
            onChange={(event) => patch({ max_lots: Math.max(1, Math.floor(Number(event.target.value) || 1)) }, 'Maximum lots updated')} />
        </Field>
        <details style={{ border: `1px solid ${BORDER}`, borderRadius: 8, marginTop: 8, overflow: 'hidden' }}>
          <summary style={{ minHeight: 40, display: 'flex', alignItems: 'center', padding: '0 12px', cursor: 'pointer', color: TEXT, background: SOFT, fontSize: 11.5, fontWeight: 700 }}>
            Advanced auto-execution guards <span style={{ color: DIM, fontWeight: 500 }}>· {enabledGuards} enabled</span>
          </summary>
          <div style={{ borderTop: `1px solid ${BORDER}`, padding: '4px 12px 12px' }}>
            <Field label="Expiry square-off" hint="0 disables the guard.">
              <input data-testid="expiry-squareoff-input" aria-label="Expiry square-off days" type="number" min={0} max={10} step={1}
                value={cfg.expiry_square_off_days ?? 1} style={inputStyle}
                onChange={(event) => patch({ expiry_square_off_days: Math.max(0, Math.floor(Number(event.target.value) || 0)) }, 'Expiry square-off updated')} />
            </Field>
            <Field label="Time stop" hint="1H bars; 0 disables.">
              <input data-testid="time-stop-input" aria-label="Time stop bars" type="number" min={0} max={500} step={1}
                value={cfg.time_stop_bars ?? 0} style={inputStyle}
                onChange={(event) => patch({ time_stop_bars: Math.max(0, Math.floor(Number(event.target.value) || 0)) }, 'Time stop updated')} />
            </Field>
            <Field label="Late-entry block" hint="Minutes before 15:30; 0 disables.">
              <input data-testid="block-entry-input" aria-label="Block entry minutes before close" type="number" min={0} max={375} step={5}
                value={cfg.block_entry_minutes_before_close ?? 0} style={inputStyle}
                onChange={(event) => patch({ block_entry_minutes_before_close: Math.max(0, Math.floor(Number(event.target.value) || 0)) }, 'Late-entry block updated')} />
            </Field>
            <Field label="Liquidity">
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <label style={{ color: MUTED, fontSize: 11 }}>Max spread % <input data-testid="max-spread-input" aria-label="Max spread percent" type="number" min={0} step={0.5} placeholder="off" value={cfg.max_spread_pct ?? ''} style={{ ...inputStyle, marginLeft: 5 }} onChange={(event) => patch({ max_spread_pct: event.target.value === '' ? null : Math.max(0, Number(event.target.value)) }, 'Spread guard updated')} /></label>
                <label style={{ color: MUTED, fontSize: 11 }}>Min OI <input data-testid="min-oi-input" aria-label="Minimum open interest" type="number" min={0} step={50} placeholder="off" value={cfg.min_oi ?? ''} style={{ ...inputStyle, marginLeft: 5 }} onChange={(event) => patch({ min_oi: event.target.value === '' ? null : Math.max(0, Math.floor(Number(event.target.value))) }, 'Open-interest guard updated')} /></label>
              </div>
            </Field>
            <Field label="Daily loss" hint="Percent of capital; blank disables.">
              <input data-testid="daily-loss-input" aria-label="Max daily loss percent" type="number" min={0} max={100} step={0.5} placeholder="off" value={cfg.max_daily_loss_pct ?? ''} style={inputStyle}
                onChange={(event) => patch({ max_daily_loss_pct: event.target.value === '' ? null : Math.max(0, Number(event.target.value)) }, 'Daily-loss guard updated')} />
            </Field>
          </div>
        </details>
      </Section>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '14px 18px', background: SOFT }}>
        <span style={{ color: DIM, fontSize: 10.5, lineHeight: 1.45 }}>Automatic/manual order placement is controlled once, in Trading mode above.</span>
        <button type="button" disabled={resetCfg.isPending} onClick={() => {
          if (!window.confirm('Restore every engine setting to its default value?')) return;
          resetCfg.mutate(undefined, { onSuccess: () => runScan.mutate() });
        }} style={{ minHeight: 34, flexShrink: 0, border: `1px solid ${BORDER}`, borderRadius: 7, background: '#fff', color: '#c9433e', padding: '0 12px', fontSize: 10.5, fontWeight: 650, fontFamily: 'inherit', cursor: 'pointer' }}>
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
    </section>
  );
}

export default EngineConfigurationPanel;
