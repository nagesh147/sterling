import React, { useState, useEffect } from 'react';
import {
  useSmartMoneyOptionsConfig,
  useSetSmartMoneyOptionsConfig,
  type SmartMoneyOptionsConfig,
  type StrikeSelectionPolicy,
  type ExpiryPolicy,
  type ExecutionMode,
} from '../hooks/useSmartMoneyOptions';
import {
  ChoiceRow,
  Field,
  NumberField,
  Section,
  Switch,
  TEXT,
  DIM,
} from './kite/kiteSettingsPrimitives';
import { PanelCard, SettingsDraftBar } from './kite/config/ConfigPrimitives';
import { EnginePowerHeader } from './kite/config/EnginePowerHeader';
import { k } from '../styles/kiteUI';

const STRIKE_OPTIONS: Array<{ value: StrikeSelectionPolicy; label: string; hint: string }> = [
  { value: 'OTM1', label: 'OTM 1 (Recommended)', hint: 'First Out-of-the-Money strike. Maximum gamma acceleration for Multi-X runs.' },
  { value: 'OTM2', label: 'OTM 2', hint: 'Second Out-of-the-Money strike. High leverage for extended momentum breakouts.' },
  { value: 'ATM', label: 'ATM', hint: 'At-The-Money strike. Higher delta, lower percentage multiplier.' },
];

const EXPIRY_OPTIONS: Array<{ value: ExpiryPolicy; label: string; hint: string }> = [
  { value: 'NEAREST_MONTHLY', label: 'Monthly Expiry (Recommended)', hint: 'Current month standard expiry. Best liquidity for swing options.' },
  { value: 'CURRENT_EXPIRY', label: 'Current Expiry', hint: 'Nearest listed weekly/monthly expiry.' },
  { value: 'NEXT_EXPIRY', label: 'Next Expiry', hint: 'Following contract cycle for longer swing trades.' },
];

const HTF_OPTIONS = [
  { value: '1d', label: 'Daily (1D)', hint: 'Standard institutional base identification timeframe.' },
  { value: '4h', label: '4-Hour (4H)', hint: 'Intermediate swing base structure.' },
  { value: '1h', label: '1-Hour (1H)', hint: 'Fast structural consolidation.' },
];

const LTF_OPTIONS = [
  { value: '1h', label: '1-Hour (1H)', hint: 'Primary breakout trigger timeframe.' },
  { value: '15m', label: '15-Minute (15M)', hint: 'Intraday entry precision.' },
  { value: '5m', label: '5-Minute (5M)', hint: 'High-frequency momentum trigger.' },
];

export function SmartMoneyOptionsSettings() {
  const { data, isLoading } = useSmartMoneyOptionsConfig();
  const setCfg = useSetSmartMoneyOptionsConfig();

  const [draft, setDraft] = useState<SmartMoneyOptionsConfig | null>(null);

  useEffect(() => {
    if (data?.config && !draft) {
      setDraft(data.config);
    }
  }, [data?.config]);

  if (isLoading || !draft) {
    return <p style={{ padding: 16, color: k.dim }}>Loading Smart Money Options Settings…</p>;
  }

  const isDirty = JSON.stringify(draft) !== JSON.stringify(data?.config);

  const update = <K extends keyof SmartMoneyOptionsConfig>(key: K, value: SmartMoneyOptionsConfig[K]) => {
    setDraft((prev) => (prev ? { ...prev, [key]: value } : null));
  };

  const handleSave = () => {
    if (!draft) return;
    setCfg.mutate(draft);
  };

  const handleReset = () => {
    if (data?.config) setDraft(data.config);
  };

  return (
    <div style={{ padding: '16px 20px', maxWidth: 800, margin: '0 auto', fontFamily: k.fontFamily }}>
      <SettingsDraftBar
        isDirty={isDirty}
        onSave={handleSave}
        onReset={handleReset}
        isSaving={setCfg.isPending}
      />

      <EnginePowerHeader
        name="Smart Money Multi-X Options"
        tagline="Institutional base consolidation + Smart Money volume surge breakout -> 2X, 3X, 5X Multi-X Option targets"
        on={draft.enabled}
        liveOn={data?.config?.enabled}
        onToggle={() => update('enabled', !draft.enabled)}
        runningNote="Scanning universe for consolidation breakouts and institutional footprint surges."
        offNote="Engine paused. No new breakout setups or Multi-X option orders placed."
      >
        <div style={{ marginTop: 12 }}>
          <ChoiceRow
            label="Execution Mode"
            hint="Paper simulation, shadow audit, or live exchange routing."
            value={draft.execution_mode}
            options={[
              { value: 'paper', label: 'Paper', hint: 'Simulated execution only' },
              { value: 'shadow', label: 'Shadow', hint: 'Audits live market without submitting orders' },
              { value: 'live', label: 'Live', hint: 'Routes real orders to broker' },
            ]}
            onChange={(m) => update('execution_mode', m as ExecutionMode)}
          />
        </div>
      </EnginePowerHeader>

      {/* Universe Section */}
      <PanelCard>
        <Section title="Asset Universe & Watchlist" hint="F&O equities and benchmark indices scanned for base consolidation.">
          <Field label="Universe Symbols" hint="Comma-separated stock symbols (e.g. ABB, RELIANCE, TATAMOTORS, NIFTY 50)">
            <input
              type="text"
              value={draft.universe.join(', ')}
              onChange={(e) =>
                update(
                  'universe',
                  e.target.value.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean)
                )
              }
              style={{
                width: '100%',
                background: k.bg,
                border: `1px solid ${k.border}`,
                color: k.text,
                padding: '6px 10px',
                borderRadius: 4,
                fontSize: 12,
              }}
            />
          </Field>
        </Section>
      </PanelCard>

      {/* Structure Section */}
      <PanelCard>
        <Section title="Market Structure & Consolidation" hint="Identifies accumulation bases and liquidity pools (SSL / BSL).">
          <ChoiceRow
            label="Higher Timeframe (HTF)"
            hint="Timeframe used to detect base range and resistance/support."
            value={draft.htf_timeframe}
            options={HTF_OPTIONS}
            onChange={(v) => update('htf_timeframe', v)}
          />

          <ChoiceRow
            label="Lower Timeframe (LTF)"
            hint="Trigger timeframe for breakout confirmation and volume surge."
            value={draft.ltf_timeframe}
            options={LTF_OPTIONS}
            onChange={(v) => update('ltf_timeframe', v)}
          />

          <NumberField
            label="Min Consolidation Bars"
            hint="Minimum number of candles required to form a valid base structure (default: 8 bars)."
            value={draft.min_consolidation_bars}
            step={1}
            min={3}
            max={50}
            onChange={(v) => update('min_consolidation_bars', Math.round(v))}
          />

          <NumberField
            label="Max Consolidation Range %"
            hint="Maximum allowed width between swing high and low in base (default: 8.0%)."
            value={draft.max_consolidation_range_pct}
            step={0.5}
            min={1}
            max={25}
            onChange={(v) => update('max_consolidation_range_pct', v)}
          />
        </Section>
      </PanelCard>

      {/* Smart Money Volume & Footprint */}
      <PanelCard>
        <Section title="Smart Money Footprint & Volume Surge" hint="Filters breakouts to ensure institutional participation.">
          <NumberField
            label="Volume Surge Multiplier (RVOL)"
            hint="Relative volume threshold over 20-period average volume (e.g. 1.8x - 2.5x)."
            value={draft.volume_surge_multiplier}
            step={0.1}
            min={1.0}
            max={10.0}
            onChange={(v) => update('volume_surge_multiplier', v)}
          />

          <NumberField
            label="Min Footprint Score"
            hint="Minimum institutional footprint score required to confirm entry (0 - 100)."
            value={draft.min_footprint_score}
            step={5}
            min={0}
            max={100}
            onChange={(v) => update('min_footprint_score', v)}
          />
        </Section>
      </PanelCard>

      {/* Option Strike Selection */}
      <PanelCard>
        <Section title="Option Contract & Moneyness Selection" hint="Determines option strike and expiry for buying calls/puts.">
          <ChoiceRow
            label="Strike Moneyness Policy"
            hint="OTM1 provides ideal asymmetric risk/reward for Multi-X gamma expansion."
            value={draft.strike_selection}
            options={STRIKE_OPTIONS}
            onChange={(v) => update('strike_selection', v)}
          />

          <ChoiceRow
            label="Expiry Selection"
            hint="Nearest monthly expiry offers optimal liquidity and theta decay profile for swing holding."
            value={draft.expiry_policy}
            options={EXPIRY_OPTIONS}
            onChange={(v) => update('expiry_policy', v)}
          />
        </Section>
      </PanelCard>

      {/* Multi-X Targets & Risk Management */}
      <PanelCard>
        <Section title="Multi-X Target Architecture & Swing Horizon" hint="Tiered profit targets with trailing stop and holding duration.">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <NumberField
              label="Target 1 (2X)"
              hint="Initial target (+100%)."
              value={draft.target_multiplier_1}
              step={0.5}
              min={1.5}
              max={10.0}
              onChange={(v) => update('target_multiplier_1', v)}
            />

            <NumberField
              label="Target 2 (3X)"
              hint="Secondary target (+200%)."
              value={draft.target_multiplier_2}
              step={0.5}
              min={2.0}
              max={15.0}
              onChange={(v) => update('target_multiplier_2', v)}
            />

            <NumberField
              label="Target 3 (5X Multi-X)"
              hint="Runner Multi-X (+400%)."
              value={draft.target_multiplier_3}
              step={0.5}
              min={3.0}
              max={25.0}
              onChange={(v) => update('target_multiplier_3', v)}
            />
          </div>

          <NumberField
            label="Stop Loss %"
            hint="Option premium risk limit (default: 35% of entry price)."
            value={draft.stop_loss_pct}
            step={5}
            min={10}
            max={80}
            onChange={(v) => update('stop_loss_pct', v)}
          />

          <NumberField
            label="Holding Horizon"
            hint="Swing trade holding window (default: 5 trading days as demonstrated in video)."
            value={draft.holding_period_days}
            step={1}
            min={1}
            max={30}
            onChange={(v) => update('holding_period_days', Math.round(v))}
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <NumberField
              label="Lots Per Trade"
              hint="Number of lots per signal execution."
              value={draft.lots_per_trade}
              step={1}
              min={1}
              max={20}
              onChange={(v) => update('lots_per_trade', Math.round(v))}
            />

            <NumberField
              label="Max Open Positions"
              hint="Portfolio limit for concurrent Smart Money positions."
              value={draft.max_open_positions}
              step={1}
              min={1}
              max={10}
              onChange={(v) => update('max_open_positions', Math.round(v))}
            />
          </div>
        </Section>
      </PanelCard>
    </div>
  );
}

export default SmartMoneyOptionsSettings;
