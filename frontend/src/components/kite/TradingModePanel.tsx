import React from 'react';
import { useKiteSettings } from '../../store/useKiteSettings';
import { useEngineConfig, usePatchEngineConfig } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import { BORDER, DIM, MUTED, SOFT, Switch, TEXT } from './kiteSettingsPrimitives';
import { PanelCard, PanelSectionHeading } from './config/ConfigPrimitives';
import { openSettingsSection } from './config/registry';
import { TradingModeControls } from './TradingModeControls';

/**
 * The two questions that decide whether real money moves — paper or live, and
 * who places the order — plus which engines are actually running.
 *
 * These used to sit inside the page titled "SuperTrend Engine", so a user who
 * had turned SuperTrend off had no reason to look there for the switch that
 * also arms Navigator. `auto_execute` is user-global (keyed by uid alone) and
 * Navigator's automatic placement reuses the same path, so it belongs on its
 * own page above both engines.
 *
 * It is also the first place both arming switches appear together.
 * `auto_execute` and Navigator's `auto_execute_originated` are independent
 * switches that both place real orders, and neither surface previously
 * mentioned the other.
 */

function RunningRow({ label, description, on, children }: {
  label: string;
  description: string;
  on: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
      padding: '13px 0', borderTop: `1px solid ${BORDER}`,
    }}>
      <span aria-hidden style={{
        width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
        background: on ? 'var(--k-green)' : '#c7c7c7',
      }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ color: TEXT, fontSize: 12.5, fontWeight: 700 }}>{label}</div>
        <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 2 }}>{description}</div>
      </div>
      {children}
    </div>
  );
}

/**
 * The strategies a re-scan can cover.
 *
 * ATM Premium Imbalance is deliberately absent: it has no scan. It resolves one
 * option pair and arms it, so there is no universe to sweep and nothing for this
 * button to do. Listing it would offer a choice that changes nothing.
 */
const RESCANNABLE: Array<{ engine: string; label: string; note: string }> = [
  { engine: 'supertrend', label: 'SuperTrend', note: 'Triple SuperTrend across the configured universe' },
  { engine: 'navigator', label: 'Value-Flow Navigator', note: 'AVWAP and flow evidence, its own source' },
  { engine: 'orb', label: 'ORB + VWAP', note: 'Opening range breakout on the index options' },
  { engine: 'gamma_move', label: 'Gamma Move', note: 'Open-interest unwind around the levels' },
  { engine: 'adaptive_edge', label: 'Adaptive Edge', note: 'Order-flow scalping' },
  { engine: 'oi_wall_flow', label: 'OI Wall Flow', note: 'First-resistance CE / first-support PE the chain is writing' },
];

export function TradingModePanel() {
  const { data: cfg } = useEngineConfig();
  const setCfg = usePatchEngineConfig();
  const { data: navData } = useNavigatorConfig();

  const navCfg = navData?.record.config;
  const navigatorOn = !!navCfg?.enabled;
  const navigatorAuto = !!navCfg?.auto_execute_originated;
  const engineOn = !!cfg?.engine_enabled;
  const rescanStrategies = useKiteSettings((s) => s.rescanStrategies);
  const toggleRescanStrategy = useKiteSettings((s) => s.toggleRescanStrategy);
  const autoOn = !!cfg?.auto_execute;

  return (
    <>
      <TradingModeControls />

      <PanelCard>
        <PanelSectionHeading
          title="What is running"
          description="Which signal engines are active. Turning both off leaves Kite as a normal manual trading platform — market watch, charts and your own orders all still work."
        />
        <div style={{ padding: '2px 18px 16px' }}>
          <RunningRow
            label="SuperTrend engine"
            description={engineOn
              ? 'Scanning, producing signals, and eligible for automatic execution.'
              : 'Off — no SuperTrend scanning and no SuperTrend signals.'}
            on={engineOn}
          >
            {cfg && (
              <Switch
                checked={engineOn} label="Sterling Kite engine"
                disabled={setCfg.isPending}
                onChange={() => setCfg.mutate({ engine_enabled: !engineOn })}
              />
            )}
          </RunningRow>

          <RunningRow
            label="Value-Flow Navigator"
            description={navigatorOn
              ? navigatorAuto
                ? 'On, and placing its own originated setups automatically — a second arming switch, independent of the one above.'
                : 'On. It can confirm SuperTrend setups and originate its own, but places nothing automatically.'
              : 'Off — no Navigator evidence and no Navigator-originated setups.'}
            on={navigatorOn}
          >
            <button
              type="button"
              onClick={() => openSettingsSection('navigator')}
              style={{
                minHeight: 32, border: `1px solid ${BORDER}`, borderRadius: 7, background: 'var(--k-bg)',
                color: 'var(--k-brand)', padding: '0 12px', fontFamily: 'inherit',
                fontSize: 11, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
              }}
            >
              Configure →
            </button>
          </RunningRow>
        </div>

        {autoOn && navigatorAuto && (
          <div style={{
            padding: '11px 18px', background: '#fff7f0', borderTop: `1px solid #edd6c6`,
            color: '#9a4b16', fontSize: 11.5, lineHeight: 1.5,
          }}>
            ⚠ <strong>Two automatic order paths are armed.</strong> SuperTrend signals place through
            AUTO above, and Navigator places its own originated setups through its separate switch.
            Both reach the same broker account.
          </div>
        )}

        <div style={{
          padding: '12px 18px', background: SOFT, borderTop: `1px solid ${BORDER}`,
          color: DIM, fontSize: 10.5, lineHeight: 1.5,
        }}>
          Paper/live is set per account. Automatic execution is set once for your user and applies to
          whichever account is active.
        </div>
      </PanelCard>

      <PanelCard>
        <PanelSectionHeading
          title="Included in re-scan"
          description="Which strategies the re-scan button covers. They share one historical-data budget and run one at a time, so a scan of five costs five times a scan of one — an operator working a single strategy can stop paying for the other four without switching them off for everyone."
        />
        <div style={{ padding: '2px 18px 16px', display: 'grid', gap: 2 }}>
          {RESCANNABLE.map(({ engine, label, note }) => {
            // Absent means included: the map holds only exclusions, so a new
            // engine is covered from the day it appears rather than silently
            // missing from every saved map.
            const on = rescanStrategies[engine] !== false;
            return (
              <label
                key={engine}
                title={note}
                style={{
                  minHeight: 30, display: 'flex', alignItems: 'center', gap: 8,
                  color: 'var(--k-text)', fontSize: 11, cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => toggleRescanStrategy(engine)}
                  style={{ width: 14, height: 14, margin: 0, accentColor: 'var(--k-orange)' }}
                />
                <span style={{ fontWeight: 600 }}>{label}</span>
                <span style={{ color: 'var(--k-dim)', fontSize: 10 }}>{note}</span>
              </label>
            );
          })}
          <div style={{ marginTop: 8, fontSize: 10, lineHeight: 1.5, color: 'var(--k-dim)' }}>
            A strategy switched off above is skipped whatever is ticked here — the
            running switch wins, because scanning a stopped engine is work you have
            already declined.
          </div>
        </div>
      </PanelCard>
    </>
  );
}

export default TradingModePanel;
