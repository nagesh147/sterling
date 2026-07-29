import React from 'react';
import {
  useEngineConfig, useRunScan, useSetEngineConfig, useStockRegistry,
} from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import { notifyOrder } from '../../store/useKiteNotifications';
import type { EngineConfigModel, ScanSource } from '../../types/kiteEngine';
import {
  BORDER, CheckOption, DIM, Field, MUTED, ORANGE, ORANGE_SOFT, Section, Switch, TEXT,
} from './kiteSettingsPrimitives';

const GREEN = '#4caf50';

const INDEX_OPTIONS = [
  { value: 'NIFTY 50', label: 'NIFTY' },
  { value: 'NIFTY BANK', label: 'BANKNIFTY' },
  { value: 'NIFTY FIN SERVICE', label: 'FINNIFTY' },
  { value: 'SENSEX', label: 'SENSEX' },
];

const SOURCE_OPTIONS: Array<{ value: ScanSource; label: string; description: string }> = [
  { value: 'spot', label: 'Spot', description: 'Read the underlying chart itself.' },
  { value: 'derivatives', label: 'Options', description: "Read each option's own premium chart." },
  { value: 'both', label: 'Both', description: 'Run both, side by side.' },
  { value: 'confluence', label: 'Confluence', description: 'Only when both agree — strictest.' },
];

/** Which engines are currently following this shared setup. Navigator only
 *  follows it while its scan scope is "shared"; if the user gave Navigator
 *  its own universe, saying "both engines use this" would be a lie. */
function FollowerChips({ navigatorFollows, navigatorEnabled }: { navigatorFollows: boolean; navigatorEnabled: boolean }) {
  const chip = (label: string, on: boolean, note: string) => (
    <span
      key={label} title={note}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 20,
        fontSize: 10.5, fontWeight: 700, border: `1px solid ${on ? `${GREEN}55` : BORDER}`,
        background: on ? '#e8f5e9' : '#f6f6f7', color: on ? '#2e7d32' : DIM,
      }}
    >
      <span aria-hidden style={{ width: 5, height: 5, borderRadius: '50%', background: on ? GREEN : '#c2c2c2' }} />
      {label}
    </span>
  );
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {chip('SuperTrend', true, 'The SuperTrend engine always scans this universe.')}
      {chip(
        navigatorFollows ? 'Navigator' : 'Navigator — on its own',
        navigatorFollows,
        navigatorFollows
          ? navigatorEnabled
            ? 'Navigator is set to follow this shared setup.'
            : 'Navigator would follow this, but Navigator is currently off.'
          : 'Navigator has its own universe — change it in the Value-Flow Navigator section.',
      )}
    </div>
  );
}

/**
 * The settings BOTH signal engines read: which instruments get scanned, and
 * which chart a signal is read from. These used to live inside the SuperTrend
 * engine's own panel, which made them look like SuperTrend's settings that
 * Navigator borrowed. They aren't — they're one shared set of values, so they
 * get their own home.
 */
export function SharedScanSetupPanel() {
  const { data: cfg } = useEngineConfig();
  const { data: navData } = useNavigatorConfig();
  const { data: stockRegistry } = useStockRegistry();
  const setCfg = useSetEngineConfig();
  const runScan = useRunScan();

  if (!cfg) {
    return <div style={{ padding: 18, color: DIM, fontSize: 12 }}>Loading scan setup…</div>;
  }

  const navCfg = navData?.record.config;
  const navigatorFollows = (navCfg?.scan_scope_mode ?? 'shared') === 'shared';
  const navigatorEnabled = !!navCfg?.enabled;

  const patch = (values: Partial<EngineConfigModel>, message: string, rescan = true) => {
    setCfg.mutate({ ...cfg, ...values }, {
      onSuccess: () => {
        notifyOrder({ kind: 'info', title: 'Scan setup updated', message });
        if (rescan) runScan.mutate();
      },
    });
  };

  const toggleListValue = <T extends string>(current: T[], value: T, fallback: T[]): T[] => {
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    return next.length ? next : fallback;
  };

  return (
    <section style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 9, overflow: 'hidden', marginBottom: 16, boxShadow: '0 1px 2px rgba(0,0,0,.025)' }}>
      <div style={{ padding: '16px 18px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ color: TEXT, fontSize: 13.5, fontWeight: 800 }}>Shared by both engines</div>
        <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.55, margin: '3px 0 10px' }}>
          What gets scanned, and which chart a signal is read from. Set it once here — you don&apos;t
          need to configure it separately for each engine.
        </div>
        <FollowerChips navigatorFollows={navigatorFollows} navigatorEnabled={navigatorEnabled} />
        {!navigatorFollows && (
          <div style={{ marginTop: 10, padding: '8px 11px', borderRadius: 7, background: '#f6f6f7', border: `1px solid ${BORDER}`, color: MUTED, fontSize: 10.5, lineHeight: 1.5 }}>
            Navigator is currently set to its own universe, so changes here affect SuperTrend only.
            Switch it back under <b>Value-Flow Navigator → What Navigator scans</b> if you want them
            to move together again.
          </div>
        )}
      </div>

      <Section
        title="Instruments"
        description="The indices and F&O stocks included in every scan."
        summary={cfg.scan_all_stocks ? `All F&O · ${cfg.scan_indices.length} indices` : `${cfg.scan_stocks.length} stocks · ${cfg.scan_indices.length} indices`}
        defaultOpen
      >
        <Field label="Indices">
          <div className="sk-config-check-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 7 }}>
            {INDEX_OPTIONS.map((option) => (
              <CheckOption
                key={option.value} label={option.label}
                checked={cfg.scan_indices.includes(option.value)}
                onChange={() => patch({ scan_indices: toggleListValue(cfg.scan_indices, option.value, ['NIFTY 50']) }, 'Index universe updated')}
              />
            ))}
          </div>
        </Field>
        <Field label="F&O stocks" hint="Use the full eligible universe, or curate a smaller list.">
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Switch
              checked={cfg.scan_all_stocks} label="Scan all F&O stocks"
              onChange={() => patch({ scan_all_stocks: !cfg.scan_all_stocks }, `All F&O stocks ${!cfg.scan_all_stocks ? 'enabled' : 'disabled'}`)}
            />
            <span style={{ color: TEXT, fontSize: 12 }}>Scan all eligible F&amp;O stocks</span>
          </div>
        </Field>
        {!cfg.scan_all_stocks && (
          <Field label="Selected stocks" hint={`${cfg.scan_stocks.length} selected`}>
            <div style={{ maxHeight: 260, overflow: 'auto', paddingRight: 4 }}>
              {(stockRegistry ?? []).map((group) => (
                <div key={group.liquidity} style={{ marginBottom: 10 }}>
                  <div style={{ color: DIM, fontSize: 9, fontWeight: 700, letterSpacing: .5, marginBottom: 5 }}>{group.liquidity.toUpperCase()}</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(118px, 1fr))', gap: 3 }}>
                    {group.stocks.map((stock) => (
                      <CheckOption
                        key={stock.name} label={stock.label || stock.name} compact
                        checked={cfg.scan_stocks.includes(stock.name)}
                        onChange={() => patch({ scan_stocks: toggleListValue(cfg.scan_stocks, stock.name, []) }, `${stock.name} ${cfg.scan_stocks.includes(stock.name) ? 'removed' : 'added'}`)}
                      />
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
        title="Contracts to scan"
        description="Which chart a signal is read from."
        summary={SOURCE_OPTIONS.find((o) => o.value === cfg.scan_source)?.label ?? cfg.scan_source}
        defaultOpen
      >
        <Field label="Signal source" hint="Changes what both engines look at, and runs a fresh scan.">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(165px, 1fr))', gap: 8 }}>
            {SOURCE_OPTIONS.map((option) => {
              const selected = cfg.scan_source === option.value;
              return (
                <label key={option.value} style={{
                  minHeight: 58, display: 'grid', gridTemplateColumns: '17px minmax(0, 1fr)', alignItems: 'start', gap: 9,
                  textAlign: 'left', padding: '10px 11px', borderRadius: 7, cursor: 'pointer', fontFamily: 'inherit',
                  border: `1px solid ${selected ? '#e2b6a4' : BORDER}`,
                  background: selected ? ORANGE_SOFT : '#fff', boxSizing: 'border-box',
                }}>
                  <input
                    type="radio" name="shared-signal-source" checked={selected}
                    onChange={() => patch({ scan_source: option.value }, `Signal source changed to ${option.label}`)}
                    style={{ width: 15, height: 15, margin: '1px 0 0', accentColor: ORANGE }}
                  />
                  <span>
                    <span style={{ display: 'block', color: TEXT, fontSize: 11.5, fontWeight: 700 }}>{option.label}</span>
                    <span style={{ display: 'block', color: DIM, fontSize: 9.5, lineHeight: 1.35, marginTop: 3 }}>{option.description}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </Field>
      </Section>
    </section>
  );
}

export default SharedScanSetupPanel;
