import React from 'react';
import { useEngineConfig, usePatchEngineConfig } from '../../hooks/useSterlingKiteEngine';
import { useNavigatorConfig } from '../../hooks/useNavigator';
import { BORDER, DIM, MUTED, SOFT, Switch, TEXT } from './kiteSettingsPrimitives';
import { PanelCard, PanelHeader } from './config/ConfigPrimitives';
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
        background: on ? '#4caf50' : '#c7c7c7',
      }} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ color: TEXT, fontSize: 12.5, fontWeight: 700 }}>{label}</div>
        <div style={{ color: MUTED, fontSize: 11, lineHeight: 1.5, marginTop: 2 }}>{description}</div>
      </div>
      {children}
    </div>
  );
}

export function TradingModePanel() {
  const { data: cfg } = useEngineConfig();
  const setCfg = usePatchEngineConfig();
  const { data: navData } = useNavigatorConfig();

  const navCfg = navData?.record.config;
  const navigatorOn = !!navCfg?.enabled;
  const navigatorAuto = !!navCfg?.auto_execute_originated;
  const engineOn = !!cfg?.engine_enabled;
  const autoOn = !!cfg?.auto_execute;

  return (
    <>
      <TradingModeControls />

      <PanelCard>
        <PanelHeader
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
                minHeight: 32, border: `1px solid ${BORDER}`, borderRadius: 7, background: '#fff',
                color: '#f06428', padding: '0 12px', fontFamily: 'inherit',
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
    </>
  );
}

export default TradingModePanel;
