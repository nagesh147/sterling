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

const ORANGE = '#f06428';
const BLUE = '#387ed1';
const GREEN = '#4caf50';
const BORDER = '#e0e0e0';
const TEXT = '#444';
const MUTED = '#777';
const DIM = '#9b9b9b';

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

const inputStyle: React.CSSProperties = {
  width: 86,
  padding: '6px 8px',
  border: `1px solid ${BORDER}`,
  borderRadius: 5,
  background: '#fff',
  color: TEXT,
  fontFamily: 'inherit',
  fontSize: 12,
};

function Section({ title, description, summary, defaultOpen = false, children }: {
  title: string;
  description: string;
  summary: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  return (
    <details
      open={isOpen}
      onToggle={(event) => setIsOpen(event.currentTarget.open)}
      style={{ borderBottom: `1px solid ${BORDER}` }}
    >
      <summary style={{
        listStyle: 'none', cursor: 'pointer', padding: '16px 18px', display: 'flex',
        alignItems: 'center', gap: 14, userSelect: 'none',
      }}>
        <span aria-hidden style={{ width: 26, height: 26, borderRadius: 13, background: 'rgba(240,100,40,.09)', color: ORANGE, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, flexShrink: 0, transform: isOpen ? 'rotate(90deg)' : 'none', transition: 'transform .16s ease' }}>›</span>
        <span style={{ minWidth: 0, flex: 1 }}>
          <span style={{ display: 'block', color: TEXT, fontSize: 13, fontWeight: 700 }}>{title}</span>
          <span style={{ display: 'block', color: MUTED, fontSize: 11, lineHeight: 1.45, marginTop: 2 }}>{description}</span>
        </span>
        <span style={{ color: DIM, fontSize: 10.5, textAlign: 'right', maxWidth: 210 }}>{summary}</span>
      </summary>
      <div style={{ padding: '0 18px 18px 58px' }}>{children}</div>
    </details>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '132px minmax(0, 1fr)', gap: 14, padding: '12px 0', alignItems: 'start' }}>
      <div>
        <div style={{ color: TEXT, fontSize: 11.5, fontWeight: 700 }}>{label}</div>
        {hint && <div style={{ color: DIM, fontSize: 10, lineHeight: 1.4, marginTop: 3 }}>{hint}</div>}
      </div>
      <div style={{ minWidth: 0 }}>{children}</div>
    </div>
  );
}

function ChoiceRow<T extends string>({ value, options, onChange }: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div style={{ display: 'inline-flex', maxWidth: '100%', border: `1px solid ${BORDER}`, borderRadius: 6, overflow: 'hidden', flexWrap: 'wrap' }}>
      {options.map((option, index) => {
        const selected = option.value === value;
        return (
          <button key={option.value} type="button" aria-pressed={selected} onClick={() => onChange(option.value)} style={{
            border: 'none', borderLeft: index ? `1px solid ${BORDER}` : 'none',
            background: selected ? ORANGE : '#fff', color: selected ? '#fff' : TEXT,
            padding: '6px 12px', fontSize: 11, fontWeight: selected ? 700 : 500,
            fontFamily: 'inherit', cursor: 'pointer',
          }}>
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function Switch({ checked, label, onChange, color = ORANGE }: {
  checked: boolean;
  label: string;
  onChange: () => void;
  color?: string;
}) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={onChange} style={{
      width: 38, height: 22, borderRadius: 11, border: 'none', padding: 0,
      position: 'relative', cursor: 'pointer', background: checked ? color : '#c7c7c7',
      transition: 'background .16s ease',
    }}>
      <span style={{ position: 'absolute', width: 18, height: 18, borderRadius: 9, top: 2, left: checked ? 18 : 2, background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,.2)', transition: 'left .16s ease' }} />
    </button>
  );
}

function ToggleChip({ label, hint, active, onClick }: {
  label: string;
  hint?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} title={hint} style={{
      border: `1px solid ${active ? ORANGE : BORDER}`,
      background: active ? 'rgba(240,100,40,.07)' : '#fff',
      color: active ? '#d35400' : TEXT,
      borderRadius: 999, padding: '5px 10px', fontFamily: 'inherit', cursor: 'pointer',
      fontSize: 10.5, fontWeight: active ? 700 : 500,
    }}>
      {label}{hint && <span style={{ marginLeft: 5, color: active ? ORANGE : DIM, fontSize: 9.5 }}>{hint}</span>}
    </button>
  );
}

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
    <section style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 7, overflow: 'hidden', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '16px 18px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ color: TEXT, fontSize: 14, fontWeight: 800 }}>Engine configuration</div>
          <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 3 }}>
            Signal discovery, market universe, exits and risk live here. Changes save automatically.
          </div>
        </div>
        <span style={{ color: setCfg.isPending ? ORANGE : GREEN, fontSize: 10.5, fontWeight: 700 }}>
          {setCfg.isPending ? 'Saving…' : 'Saved'}
        </span>
      </div>

      <Section
        title="Signal discovery"
        description="Choose how setups are found and which contracts are evaluated."
        summary={`${sourceLabel(cfg.scan_source)} · ${cfg.strike_moneyness.length} strikes`}
        defaultOpen
      >
        <Field label="Signal source" hint="Changes scanner behavior and runs a fresh scan.">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 7 }}>
            {SOURCE_OPTIONS.map((option) => {
              const selected = cfg.scan_source === option.value;
              return (
                <button key={option.value} type="button" aria-pressed={selected} onClick={() => patch({ scan_source: option.value }, `Signal source changed to ${option.label}`, true)} style={{
                  textAlign: 'left', padding: '10px 11px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
                  border: `1px solid ${selected ? ORANGE : BORDER}`,
                  background: selected ? 'rgba(240,100,40,.06)' : '#fff',
                }}>
                  <span style={{ display: 'block', color: selected ? '#d35400' : TEXT, fontSize: 11.5, fontWeight: 700 }}>{option.label}</span>
                  <span style={{ display: 'block', color: DIM, fontSize: 9.5, lineHeight: 1.35, marginTop: 3 }}>{option.description}</span>
                </button>
              );
            })}
          </div>
        </Field>
        <Field label="Strike coverage" hint="View and scan coverage; at least ATM remains selected.">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {STRIKE_GROUPS.map((group) => (
              <ToggleChip key={group.label} label={group.label} hint={group.hint}
                active={group.values.some((value) => cfg.strike_moneyness.includes(value))}
                onClick={() => toggleStrikeGroup(group.values)} />
            ))}
          </div>
        </Field>
        <Field label="Index expiries" hint="Contract cycles scanned for indices.">
          <div style={{ display: 'flex', gap: 6 }}>
            {(['weekly', 'monthly'] as ScanExpiry[]).map((expiry) => (
              <ToggleChip key={expiry} label={expiry === 'weekly' ? 'Weekly' : 'Monthly'} active={indexExpiries.includes(expiry)}
                onClick={() => patch({ scan_expiries_indices: toggleListValue(indexExpiries, expiry, ['weekly', 'monthly']) }, 'Index expiries updated', true)} />
            ))}
          </div>
        </Field>
      </Section>

      <Section
        title="Market universe"
        description="Control the indices and F&O stocks included in every scan."
        summary={cfg.scan_all_stocks ? `All F&O · ${cfg.scan_indices.length} indices` : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`}
      >
        <Field label="Indices">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {INDEX_OPTIONS.map((option) => (
              <ToggleChip key={option.value} label={option.label} active={cfg.scan_indices.includes(option.value)}
                onClick={() => patch({ scan_indices: toggleListValue(cfg.scan_indices, option.value, ['NIFTY 50']) }, 'Index universe updated', true)} />
            ))}
          </div>
        </Field>
        <Field label="F&O stocks" hint="Use the full eligible universe or curate a smaller list.">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch checked={cfg.scan_all_stocks} label="Scan all F&O stocks" color={BLUE}
              onChange={() => patch({ scan_all_stocks: !cfg.scan_all_stocks }, `All F&O stocks ${!cfg.scan_all_stocks ? 'enabled' : 'disabled'}`, true)} />
            <span style={{ color: TEXT, fontSize: 11.5 }}>Scan all eligible F&amp;O stocks</span>
          </div>
        </Field>
        {!cfg.scan_all_stocks && (
          <Field label="Selected stocks" hint={`${cfg.scan_stocks.length} selected`}>
            <div style={{ maxHeight: 260, overflow: 'auto', paddingRight: 4 }}>
              {(stockRegistry ?? []).map((group) => (
                <div key={group.liquidity} style={{ marginBottom: 10 }}>
                  <div style={{ color: DIM, fontSize: 9, fontWeight: 700, letterSpacing: .5, marginBottom: 5 }}>{group.liquidity.toUpperCase()}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {group.stocks.map((stock) => (
                      <ToggleChip key={stock.name} label={stock.label || stock.name} active={cfg.scan_stocks.includes(stock.name)}
                        onClick={() => patch({ scan_stocks: toggleListValue(cfg.scan_stocks, stock.name, []) }, `${stock.name} ${cfg.scan_stocks.includes(stock.name) ? 'removed' : 'added'}`, true)} />
                    ))}
                  </div>
                </div>
              ))}
              {!stockRegistry?.length && <div style={{ color: DIM, fontSize: 11 }}>Stock universe unavailable.</div>}
            </div>
          </Field>
        )}
      </Section>

      <Section
        title="Exit & protection"
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
            <Switch checked={cfg.exit_aligned_trail ?? false} label="Anchor stop to exit counter" color={BLUE}
              onChange={() => patch({ exit_aligned_trail: !(cfg.exit_aligned_trail ?? false) }, 'Stop anchor updated', true)} />
            <span style={{ color: TEXT, fontSize: 11.5 }}>{cfg.exit_aligned_trail ? 'Aligned to exit counter' : 'Tightest fast line'}</span>
          </div>
        </Field>
        <Field label="Hybrid weight" hint="SuperTrend weight from 0 to 1.">
          <input data-testid="hybrid-weight-input" aria-label="Hybrid Weight" type="number" min={0} max={1} step={0.1}
            value={cfg.hybrid_st_weight ?? 0.5} style={inputStyle}
            onChange={(event) => patch({ hybrid_st_weight: Number(event.target.value) }, 'Hybrid trail weight updated', true)} />
        </Field>
        <Field label="Protection mode" hint="Both is recommended for live trading.">
          <ChoiceRow value={cfg.stop_mode} options={STOP_OPTIONS}
            onChange={(value) => patch({ stop_mode: value }, `Protection mode changed to ${value}`)} />
        </Field>
      </Section>

      <Section
        title="Risk & safeguards"
        description="Position sizing and optional guardrails for automatic execution."
        summary={`${cfg.risk_sizing ? `${cfg.risk_pct}% risk` : 'Fixed size'} · ${enabledGuards} guards`}
      >
        <Field label="Risk sizing">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Switch checked={cfg.risk_sizing} label="Risk-based sizing" color={BLUE}
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
        <details style={{ border: `1px solid ${BORDER}`, borderRadius: 6, marginTop: 8 }}>
          <summary style={{ padding: '10px 12px', cursor: 'pointer', color: TEXT, fontSize: 11.5, fontWeight: 700 }}>
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

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '13px 18px', background: '#fafafa' }}>
        <span style={{ color: DIM, fontSize: 10.5 }}>Automatic/manual order placement is controlled once, in Trading mode above.</span>
        <button type="button" disabled={resetCfg.isPending} onClick={() => {
          if (!window.confirm('Restore every engine setting to its default value?')) return;
          resetCfg.mutate(undefined, { onSuccess: () => runScan.mutate() });
        }} style={{ border: `1px solid ${BORDER}`, borderRadius: 5, background: '#fff', color: '#e53935', padding: '6px 10px', fontSize: 10.5, fontFamily: 'inherit', cursor: 'pointer' }}>
          {resetCfg.isPending ? 'Restoring…' : 'Restore engine defaults'}
        </button>
      </div>
    </section>
  );
}

export default EngineConfigurationPanel;
